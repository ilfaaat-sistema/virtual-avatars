from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)

_ffmpeg_path: str | None = None


def get_ffmpeg() -> str:
    """
    Returns an absolute path to a usable ffmpeg binary, caching the result.

    Resolution order (first hit wins):
      1. FFMPEG_PATH env override (if the file exists);
      2. static-ffmpeg downloaded binary (fetched once, cached on disk);
      3. imageio-ffmpeg bundled binary (shipped inside the wheel, no download);
      4. system ffmpeg on PATH.

    Raises RuntimeError if none are available — the message bubbles up to the
    admin alert in bot/jobs.py so the real cause is visible.
    """
    global _ffmpeg_path
    if _ffmpeg_path:
        return _ffmpeg_path

    tried: list[str] = []

    # 1. Explicit override
    env_path = os.getenv("FFMPEG_PATH")
    if env_path:
        if os.path.exists(env_path):
            _ffmpeg_path = env_path
            logger.info("ffmpeg: using FFMPEG_PATH override (%s)", env_path)
            return _ffmpeg_path
        tried.append(f"FFMPEG_PATH={env_path} (not found)")

    # 2. static-ffmpeg (downloads once, then cached)
    try:
        from static_ffmpeg import run as _sf_run

        ffmpeg_path, _ffprobe_path = _sf_run.get_or_fetch_platform_executables_else_raise()
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            _ffmpeg_path = ffmpeg_path
            logger.info("ffmpeg: using static-ffmpeg (%s)", ffmpeg_path)
            return _ffmpeg_path
        tried.append("static-ffmpeg (returned no usable path)")
    except Exception as e:
        tried.append(f"static-ffmpeg ({e})")

    # 3. imageio-ffmpeg bundled binary (no download — shipped in the wheel)
    try:
        import imageio_ffmpeg

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            _ffmpeg_path = ffmpeg_path
            logger.info("ffmpeg: using imageio-ffmpeg (%s)", ffmpeg_path)
            return _ffmpeg_path
        tried.append("imageio-ffmpeg (returned no usable path)")
    except Exception as e:
        tried.append(f"imageio-ffmpeg ({e})")

    # 4. System ffmpeg on PATH
    system_path = shutil.which("ffmpeg")
    if system_path:
        _ffmpeg_path = system_path
        logger.info("ffmpeg: using system PATH (%s)", system_path)
        return _ffmpeg_path
    tried.append("PATH (shutil.which returned None)")

    raise RuntimeError(
        "ffmpeg binary not found. Tried: " + "; ".join(tried)
    )
