from __future__ import annotations

import config
from video.base import VideoProvider


def get_provider() -> VideoProvider:
    if config.VIDEO_PROVIDER == "veo":
        from video.veo import VeoProvider
        return VeoProvider()
    raise ValueError(f"Неизвестный VIDEO_PROVIDER: {config.VIDEO_PROVIDER}")
