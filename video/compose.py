from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from pathlib import Path

import config
from video.ffmpeg_bin import get_ffmpeg

logger = logging.getLogger(__name__)


def _mux_sync(video_path: str, audio_bytes: bytes) -> str:
    """
    Blocking: saves audio to tmp file, then runs ffmpeg to replace
    the video's audio track with the ElevenLabs dub.
    Returns path to the muxed mp4.
    """
    tmp_dir = config.DATA_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex
    audio_tmp = tmp_dir / f"audio_{uid}.ogg"
    out_path = tmp_dir / f"muxed_{uid}.mp4"

    audio_tmp.write_bytes(audio_bytes)

    try:
        # -map 0:v:0  — video from Veo mp4
        # -map 1:a:0  — audio from ElevenLabs ogg (discards Veo audio)
        # -shortest   — trim to the shorter of video / audio
        # -c:v copy   — no re-encoding of video (fast)
        # -c:a aac    — encode audio to AAC (required for Telegram mp4)
        cmd = [
            get_ffmpeg(), "-y",
            "-i", str(video_path),
            "-i", str(audio_tmp),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg mux failed:\n{result.stderr[-1000:]}")
    finally:
        if audio_tmp.exists():
            audio_tmp.unlink()

    logger.info("compose: мукс готов → %s", out_path)
    return str(out_path)


async def add_voice(video_path: str, spoken_line: str) -> str:
    """
    Generates ElevenLabs audio for spoken_line and muxes it over video_path.
    Returns path to the muxed mp4 (video_path is left untouched).
    """
    from bot.voice import tts

    audio_bytes = await tts(spoken_line)
    if not audio_bytes:
        raise RuntimeError("ElevenLabs TTS вернул пустой результат")

    return await asyncio.to_thread(_mux_sync, video_path, audio_bytes)
