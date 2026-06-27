from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
ADMIN_TELEGRAM_ID: int = int(os.environ["ADMIN_TELEGRAM_ID"])
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]

HISTORY_MESSAGES: int = int(os.getenv("HISTORY_MESSAGES", "30"))
KNOWLEDGE_DIR: Path = Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))
PERSONA_FILE: Path = Path(os.getenv("PERSONA_FILE", "persona.md"))
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))

MODEL: str = os.getenv("MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS: int = 1024

# Stage 4: Supabase (если пусто — локальный SQLite)
SUPABASE_URL: str | None = os.getenv("SUPABASE_URL") or None
SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY") or None

# Stage 2: ElevenLabs
ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID: str | None = os.getenv("ELEVENLABS_VOICE_ID")
ELEVENLABS_MODEL_ID: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
VOICE_MAX_CHARS: int = int(os.getenv("VOICE_MAX_CHARS", "600"))

# Stage 3: Video
VIDEO_PROVIDER: str = os.getenv("VIDEO_PROVIDER", "veo")
VEO_API_KEY: str | None = os.getenv("VEO_API_KEY")
VEO_MODEL: str = os.getenv("VEO_MODEL", "veo-3.1-lite")
VEO_AUDIO: bool = os.getenv("VEO_AUDIO", "false").lower() == "true"
VEO_RESOLUTION: str = os.getenv("VEO_RESOLUTION", "720p")
VIDEO_DAILY_LIMIT_PER_USER: int = int(os.getenv("VIDEO_DAILY_LIMIT_PER_USER", "2"))
VIDEO_TARGET_DURATION: int = int(os.getenv("VIDEO_TARGET_DURATION", "8"))
IDENTITY_DIR: Path = Path(os.getenv("IDENTITY_DIR", "identity"))
VIDEO_CLIPS_DIR: Path = Path(os.getenv("VIDEO_CLIPS_DIR", "video_clips"))
