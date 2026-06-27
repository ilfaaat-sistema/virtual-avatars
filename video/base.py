from __future__ import annotations

from typing import Optional, Protocol


class VideoProvider(Protocol):
    async def generate_scene(
        self,
        scene_prompt: str,
        identity_images: list[str],
        talking: bool,
        spoken_line: Optional[str],
        duration_sec: int,
    ) -> str:
        """Генерирует видео. Возвращает путь к сырому mp4."""
        ...
