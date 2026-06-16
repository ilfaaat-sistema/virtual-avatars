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

MODEL: str = "claude-sonnet-4-6"
MAX_TOKENS: int = 1024
