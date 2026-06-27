from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Polling interval and total timeout for Veo generation
_POLL_INTERVAL = 20        # seconds between status checks
_TIMEOUT_SECONDS = 240     # 4 minutes max

# Suffix appended to every prompt — forces portrait composition suitable for video notes
_COMPOSITION_SUFFIX = (
    "Square-friendly portrait framing: 9:16 vertical video. "
    "Centered close-up portrait, face fills upper-center of frame. "
    "Head fully visible with slight headroom, shoulders visible. "
    "Subject stays centered and in frame at all times, camera keeps the face framed. "
    "Natural subtle movement only, no sudden turns away from camera."
)

_NEGATIVE_PROMPT = (
    "blurry, distorted face, out of frame, cropped head, low quality, "
    "subject leaving frame, back turned to camera, extreme wide shot"
)

# Identity image extensions to scan
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _pick_identity_images(override: list[str]) -> list[str]:
    """Return identity image paths: explicit list → master.* → up to 3 photos → empty."""
    if override:
        return override[:3]

    d = config.IDENTITY_DIR
    if not d.exists():
        logger.warning("Папка identity/ не найдена — генерируем без референсов лица")
        return []

    # Prefer master / character_sheet
    for stem in ("master", "character_sheet"):
        for ext in _IMG_EXTS:
            p = d / f"{stem}{ext}"
            if p.exists():
                logger.info("Идентичность: мастер-картинка %s", p.name)
                return [str(p)]

    # Fallback: up to 3 photos, sorted for determinism
    photos = sorted(p for p in d.iterdir() if p.suffix.lower() in _IMG_EXTS)[:3]
    if photos:
        logger.info("Идентичность: %d фото (мастер-картинка не найдена)", len(photos))
    else:
        logger.warning("Папка identity/ пуста — генерируем без референсов лица")
    return [str(p) for p in photos]


def _build_prompt(scene: str, talking: bool, spoken_line: Optional[str]) -> str:
    if talking and spoken_line:
        body = (
            f'Person says "{spoken_line}" directly to camera. '
            f"Clean dialogue only, no background music. "
            f"Lips clearly visible, natural speech movement. "
            f"Scene: {scene}. "
        )
    else:
        body = (
            f"Scene: {scene}. "
            f"No visible speaker, no dialogue, ambient atmosphere only. "
        )
    return f"{body}{_COMPOSITION_SUFFIX}"


def _make_client():
    """Build genai client: Vertex AI (GOOGLE_SA_JSON) → API key fallback."""
    from google import genai

    if config.GOOGLE_SA_JSON and config.GOOGLE_CLOUD_PROJECT:
        import json, os, tempfile
        sa = json.loads(config.GOOGLE_SA_JSON)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(sa, tmp)
        tmp.close()
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", tmp.name)
        logger.info("Veo: Vertex AI auth (project=%s)", config.GOOGLE_CLOUD_PROJECT)
        return genai.Client(
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.GOOGLE_CLOUD_LOCATION,
        )

    logger.info("Veo: API key auth")
    return genai.Client(api_key=config.VEO_API_KEY)


def _generate_sync(prompt: str, identity_paths: list[str]) -> str:
    """Blocking call: submit → poll → save mp4. Returns temp file path."""
    from google.genai import types

    client = _make_client()

    # Lite/Fast models don't support reference images or resolution param
    supports_refs = not any(x in config.VEO_MODEL for x in ("lite", "fast"))

    ref_images: list = []
    if supports_refs:
        for path in identity_paths:
            try:
                img = types.Image.from_file(location=path)
                ref_images.append(
                    types.VideoGenerationReferenceImage(image=img, reference_type="asset")
                )
            except Exception as e:
                logger.warning("Не удалось загрузить референс %s: %s", path, e)

    cfg_kwargs: dict = {"aspect_ratio": "9:16", "negative_prompt": _NEGATIVE_PROMPT}
    if supports_refs:
        cfg_kwargs["resolution"] = config.VEO_RESOLUTION
    if ref_images:
        cfg_kwargs["reference_images"] = ref_images

    gen_config = types.GenerateVideosConfig(**cfg_kwargs)

    logger.info("Veo: отправляем задачу (модель=%s, референсов=%d)", config.VEO_MODEL, len(ref_images))
    operation = client.models.generate_videos(
        model=config.VEO_MODEL,
        prompt=prompt,
        config=gen_config,
    )

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while not operation.done:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Veo: превышен таймаут {_TIMEOUT_SECONDS}с")
        time.sleep(_POLL_INTERVAL)
        operation = client.operations.get(operation)
        logger.debug("Veo: статус операции — %s", operation.metadata)

    videos = getattr(operation.result, "generated_videos", None) or []
    if not videos:
        raise RuntimeError("Veo вернул пустой список видео")

    generated_video = videos[0]
    video = generated_video.video

    tmp_dir = config.DATA_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"veo_{uuid.uuid4().hex}.mp4"

    if getattr(video, "video_bytes", None):
        # Vertex AI returns bytes inline
        out_path.write_bytes(video.video_bytes)
    else:
        # AI Studio returns a file URI — download first
        client.files.download(file=video)
        video.save(str(out_path))

    logger.info("Veo: видео сохранено → %s (%d байт)", out_path, out_path.stat().st_size)
    return str(out_path)


class VeoProvider:
    async def generate_scene(
        self,
        scene_prompt: str,
        identity_images: list[str],
        talking: bool,
        spoken_line: Optional[str],
        duration_sec: int,  # TODO: scene extension for longer clips (not in MVP)
    ) -> str:
        if not config.VEO_API_KEY:
            raise RuntimeError("VEO_API_KEY не задан")

        paths = _pick_identity_images(identity_images)
        prompt = _build_prompt(scene_prompt, talking, spoken_line)
        logger.info("Veo промпт (первые 150 симв.): %s", prompt[:150])

        return await asyncio.to_thread(_generate_sync, prompt, paths)
