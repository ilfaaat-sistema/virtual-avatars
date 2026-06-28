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
VEO_MODEL: str = os.getenv("VEO_MODEL", "veo-3.1-generate-preview")
VEO_AUDIO: bool = os.getenv("VEO_AUDIO", "false").lower() == "true"
VEO_RESOLUTION: str = os.getenv("VEO_RESOLUTION", "720p")
# Vertex AI auth (alternative to VEO_API_KEY — uses $300 GCP credits)
GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GOOGLE_SA_JSON: str | None = os.getenv("GOOGLE_SA_JSON")
VIDEO_DAILY_LIMIT_PER_USER: int = int(os.getenv("VIDEO_DAILY_LIMIT_PER_USER", "2"))
VIDEO_TARGET_DURATION: int = int(os.getenv("VIDEO_TARGET_DURATION", "8"))
IDENTITY_DIR: Path = Path(os.getenv("IDENTITY_DIR", "identity"))
# Референс-фото лица в base64 (на Render identity/ пустая — фото кладём сюда приватно)
IDENTITY_IMAGE_B64: str | None = os.getenv("IDENTITY_IMAGE_B64") or None

# Цены провайдеров для отчёта /costs (env-переопределяемо; дефолты на ~2026)
PRICE_CLAUDE_IN: float = float(os.getenv("PRICE_CLAUDE_IN_USD_PER_MTOK", "1.0"))       # Haiku 4.5 вход
PRICE_CLAUDE_OUT: float = float(os.getenv("PRICE_CLAUDE_OUT_USD_PER_MTOK", "5.0"))     # Haiku 4.5 выход
PRICE_CLAUDE_CACHE_READ: float = float(os.getenv("PRICE_CLAUDE_CACHE_READ_USD_PER_MTOK", "0.10"))
PRICE_CLAUDE_CACHE_WRITE: float = float(os.getenv("PRICE_CLAUDE_CACHE_WRITE_USD_PER_MTOK", "1.25"))
PRICE_ELEVEN_PER_1K: float = float(os.getenv("PRICE_ELEVENLABS_USD_PER_1K_CHARS", "0.10"))
PRICE_VEO_PER_SEC: float = float(os.getenv("PRICE_VEO_USD_PER_SEC", "0.15"))           # Veo 3.1 Fast
USD_RUB_RATE: float = float(os.getenv("USD_RUB_RATE", "100"))                          # фолбэк, если ЦБ недоступен
VIDEO_CLIPS_DIR: Path = Path(os.getenv("VIDEO_CLIPS_DIR", "video_clips"))
