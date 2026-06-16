import logging
from pathlib import Path

import config

logger = logging.getLogger(__name__)

TOKEN_LIMIT = 80_000

_persona_text: str = ""
_kb_text: str = ""


def _estimate_tokens(text: str) -> int:
    return len(text) // 3


def load() -> None:
    global _persona_text, _kb_text

    persona_path = config.PERSONA_FILE
    if persona_path.exists():
        _persona_text = persona_path.read_text(encoding="utf-8")
    else:
        logger.warning("persona.md not found at %s", persona_path)
        _persona_text = "Ты — полезный ассистент."

    kb_parts: list[str] = []
    kb_dir = config.KNOWLEDGE_DIR
    if kb_dir.is_dir():
        for f in sorted(kb_dir.iterdir()):
            if f.suffix in (".md", ".txt"):
                kb_parts.append(f"### {f.name}\n\n{f.read_text(encoding='utf-8')}")

    _kb_text = "\n\n---\n\n".join(kb_parts)

    total = _estimate_tokens(_persona_text) + _estimate_tokens(_kb_text)
    logger.info(
        "KB loaded: %d file(s), ~%d tokens total (persona ~%d, kb ~%d)",
        len(kb_parts),
        total,
        _estimate_tokens(_persona_text),
        _estimate_tokens(_kb_text),
    )

    if total > TOKEN_LIMIT:
        logger.warning(
            "KB exceeds %d token limit (~%d). Tool-use mode not yet implemented — "
            "full KB is still passed in-context; implement tool-use in Stage 2+.",
            TOKEN_LIMIT,
            total,
        )


def get_persona() -> str:
    return _persona_text


def get_kb() -> str:
    return _kb_text


def list_files() -> list[str]:
    kb_dir = config.KNOWLEDGE_DIR
    if not kb_dir.is_dir():
        return []
    return [f.name for f in sorted(kb_dir.iterdir()) if f.suffix in (".md", ".txt")]
