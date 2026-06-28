from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from pathlib import Path

import config
from video.ffmpeg_bin import get_ffmpeg

logger = logging.getLogger(__name__)

TARGET_SIZE = 640  # Telegram video note requirement


def _detect_face_crop(video_path: str) -> tuple[int, int, int, int] | None:
    """
    Samples a middle frame, detects the largest face via OpenCV Haar cascade.
    Returns (x, y, w, h) of the face bounding box in the original frame, or None.
    """
    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 3))
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None

        # Pick the largest face
        largest = max(faces, key=lambda f: f[2] * f[3])
        return tuple(int(v) for v in largest)  # (x, y, w, h)
    except Exception as e:
        logger.warning("Детекция лица не удалась: %s", e)
        return None


def _compute_crop(video_w: int, video_h: int, face: tuple | None) -> tuple[int, int, int]:
    """
    Returns (crop_size, crop_x, crop_y) for a square crop that keeps the face
    in the upper-center of the resulting square.
    """
    crop_size = min(video_w, video_h)

    if face is not None:
        fx, fy, fw, fh = face
        face_cx = fx + fw // 2
        # Center the square horizontally on the face, clamp to bounds
        crop_x = max(0, min(face_cx - crop_size // 2, video_w - crop_size))
        # Vertically: place face in the upper third of the square (a bit below top)
        face_top = fy
        crop_y_ideal = face_top - int(crop_size * 0.15)  # 15% headroom above face
        crop_y = max(0, min(crop_y_ideal, video_h - crop_size))
        logger.info("Постобработка: лицо найдено @ (%d,%d %dx%d), кроп (%d,%d,%d)", fx, fy, fw, fh, crop_x, crop_y, crop_size)
    else:
        # Fallback: center horizontally, take top portion (faces are usually above mid)
        crop_x = (video_w - crop_size) // 2
        crop_y = max(0, (video_h - crop_size) // 4)  # upper quarter, not geometric center
        logger.info("Постобработка: лицо не найдено, кроп по верху (%d,%d,%d)", crop_x, crop_y, crop_size)

    return crop_size, crop_x, crop_y


def _get_video_dimensions(video_path: str) -> tuple[int, int]:
    """Returns (width, height) of the video via OpenCV (no ffprobe needed)."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if w <= 0 or h <= 0:
        raise RuntimeError(f"Не удалось определить размеры видео: {video_path}")
    return w, h


def _postprocess_sync(video_path: str) -> str:
    """
    Blocking: detects face, crops to square around it, scales to 640×640,
    re-encodes as H.264 + AAC mp4. Returns path to final mp4.
    """
    video_w, video_h = _get_video_dimensions(video_path)

    face = _detect_face_crop(video_path)
    crop_size, crop_x, crop_y = _compute_crop(video_w, video_h, face)

    tmp_dir = config.DATA_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"final_{uuid.uuid4().hex}.mp4"

    # crop=w:h:x:y  then scale to 640x640
    vf = f"crop={crop_size}:{crop_size}:{crop_x}:{crop_y},scale={TARGET_SIZE}:{TARGET_SIZE}"
    cmd = [
        get_ffmpeg(), "-y",
        "-threads", "1",          # меньше per-thread буферов x264 → ниже пик памяти
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",    # меньше lookahead-буферов; на 640×640 качество ок
        "-profile:v", "baseline",
        "-level", "3.0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg postprocess failed:\n{result.stderr[-1000:]}")

    face_status = "лицо в кадре" if face else "лицо не найдено (кроп по умолчанию)"
    logger.info("Постобработка готова → %s [%s, %d байт]", out_path, face_status, out_path.stat().st_size)
    return str(out_path)


async def process(video_path: str) -> str:
    """Crop to 640×640 around face, encode for Telegram sendVideoNote."""
    return await asyncio.to_thread(_postprocess_sync, video_path)
