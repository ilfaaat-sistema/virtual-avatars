import asyncio
import logging
from functools import wraps

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, Document

import config
import db.store as store
from bot import persona_kb

logger = logging.getLogger(__name__)
router = Router()


def admin_only(handler):
    @wraps(handler)
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user and message.from_user.id == config.ADMIN_TELEGRAM_ID:
            return await handler(message, *args, **kwargs)
        await message.answer("Нет доступа.")
    return wrapper


@router.message(Command("reload_kb"))
@admin_only
async def cmd_reload_kb(message: Message) -> None:
    persona_kb.load()
    await message.answer("КБ перезагружена.")


@router.message(Command("kb"))
@admin_only
async def cmd_kb(message: Message) -> None:
    files = persona_kb.list_files()
    text = (
        "Файлы в knowledge/:\n" + "\n".join(f"• {f}" for f in files)
        if files
        else "knowledge/ пуст или не найден."
    )
    await message.answer(text)


@router.message(Command("persona"))
@admin_only
async def cmd_persona(message: Message) -> None:
    text = persona_kb.get_persona()
    if len(text) > 4000:
        text = text[:4000] + "\n\n[обрезано]"
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")


@router.message(Command("stats"))
@admin_only
async def cmd_stats(message: Message) -> None:
    stats = await store.get_stats()
    await message.answer(
        f"Пользователей: {stats['users']}\nСообщений: {stats['messages']}"
    )


@router.message(Command("reset_chat"))
@admin_only
async def cmd_reset_chat(message: Message) -> None:
    await store.reset_history(message.chat.id)
    await message.answer("История этого чата удалена.")


async def _usd_rub() -> tuple[float, str]:
    """Курс USD→RUB: живьём с ЦБ РФ, иначе фолбэк из env."""
    import json, urllib.request

    def _fetch() -> float:
        with urllib.request.urlopen("https://www.cbr-xml-daily.ru/daily_json.js", timeout=8) as r:
            return float(json.loads(r.read())["Valute"]["USD"]["Value"])

    try:
        return await asyncio.to_thread(_fetch), "ЦБ"
    except Exception:
        return config.USD_RUB_RATE, "env"


def _tok(n: float) -> str:
    n = int(n)
    return f"{n/1000:.0f}k" if n >= 1000 else str(n)


def _period_costs(agg: dict) -> dict:
    claude = (
        agg["in_tokens"] * config.PRICE_CLAUDE_IN
        + agg["out_tokens"] * config.PRICE_CLAUDE_OUT
        + agg["cache_read"] * config.PRICE_CLAUDE_CACHE_READ
        + agg["cache_write"] * config.PRICE_CLAUDE_CACHE_WRITE
    ) / 1_000_000
    eleven = agg["chars"] / 1000 * config.PRICE_ELEVEN_PER_1K
    veo = float(agg["video_seconds"]) * config.PRICE_VEO_PER_SEC
    return {"claude": claude, "eleven": eleven, "veo": veo, "total": claude + eleven + veo}


@router.message(Command("costs", "expenses", "расходы"))
@admin_only
async def cmd_costs(message: Message) -> None:
    rep = await store.get_cost_report()
    rate, src = await _usd_rub()

    def money(usd: float) -> str:
        return f"${usd:.2f} · {usd * rate:.0f}₽"

    def line_total(label: str, agg: dict) -> str:
        return f"{label}: Σ ≈ {money(_period_costs(agg)['total'])}"

    t = rep["today"]
    c = _period_costs(t)
    dur = float(t["video_seconds"])
    n_vid = int(dur / config.VIDEO_TARGET_DURATION) if config.VIDEO_TARGET_DURATION else 0
    since = rep["since"].strftime("%Y-%m-%d") if rep.get("since") else "—"

    text = (
        "💰 <b>Расходы</b> (оценка)\n\n"
        "📅 <b>Сегодня</b>\n"
        f"🎥 Veo: {dur:.0f}с (~{n_vid} видео) → {money(c['veo'])}\n"
        f"🔊 ElevenLabs: {int(t['chars'])} симв → {money(c['eleven'])}\n"
        f"🧠 Claude: {_tok(t['in_tokens'])}→{_tok(t['out_tokens'])} ток "
        f"(кэш {_tok(t['cache_read'])}) → {money(c['claude'])}\n"
        f"<b>Σ ≈ {money(c['total'])}</b>\n\n"
        f"🗓 {line_total('Месяц', rep['month'])}\n"
        f"♾ {line_total('Всё время', rep['all'])}\n\n"
        f"<i>Курс 1$={rate:.1f}₽ ({src}) · учёт с {since}\n"
        "Оценка по тарифам, без бесплатных кредитов.</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(lambda m: m.document is not None)
@admin_only
async def handle_document(message: Message) -> None:
    doc: Document = message.document
    if not (doc.file_name.endswith(".md") or doc.file_name.endswith(".txt")):
        await message.answer("Принимаю только .md и .txt файлы.")
        return

    config.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.KNOWLEDGE_DIR / doc.file_name
    await message.bot.download(doc, destination=dest)
    persona_kb.load()
    await message.answer(
        f"Файл {doc.file_name} сохранён в knowledge/ и КБ перезагружена."
    )
