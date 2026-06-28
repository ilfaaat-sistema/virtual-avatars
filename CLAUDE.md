# CLAUDE.md — Virtual Avatar Bot

## Что это
Telegram-бот виртуального аватара: отвечает текстом, голосом (ElevenLabs), видеокружочками (Google Veo).
Бот: @vityualniy_avatar_bot

## Деплой

**Render Background Worker** (работает 24/7, имя: `virtual-avatar-bot`):
- Service ID: `srv-d904pkmgvqtc73966mu0`
- Dashboard: https://dashboard.render.com → My project → virtual-avatar-bot
- Region: Frankfurt
- Runtime: Python 3
- Build: `pip install -r requirements.txt`
- Start: `python main.py`
- GitHub repo: https://github.com/ilfaaat-sistema/virtual-avatars (ветка main)
- **AutoDeploy включён** — каждый `git push main` → автоматический деплой

НЕ трогать: `svoya-kuhnya-app` на Render — это совсем другой проект (Node.js).

## База данных
- Supabase project: `kcfkhebtlyqgbzaajgiv` (eu-central-1)
- URL: `https://kcfkhebtlyqgbzaajgiv.supabase.co`
- Schema: `avatar_bot` (таблицы: `users`, `messages`, `daily_counters`, `video_jobs`, `usage_log`)
- Доступ к Data API: схема должна быть в Settings → API → Exposed schemas, + GRANT'ы на
  service_role/authenticated/anon (см. db/schema.sql). Без этого PGRST106.

## ⚠️ Репозиторий ПУБЛИЧНЫЙ
`github.com/ilfaaat-sistema/virtual-avatars` — публичный. Секреты только в env (Render),
никогда в коде/репо. Фото лица не коммитим.

## Фото для лица в видео (identity/)
Папка `identity/` в .gitignore → на Render она **пустая**. Фото доставляется приватно
через env `IDENTITY_IMAGE_B64` (base64); `_ensure_identity()` в main.py декодирует его в
`identity/master.jpg` на старте. Локальный исходник — `identity/master.png` (gitignored).

## Google Veo (кружочки)
- Veo — **платная функция**. Нужен биллинг: https://console.cloud.google.com/billing
- Модель (env `VEO_MODEL`): сейчас **`veo-3.1-fast-generate-001`** (Fast — поддерживает
  референс лица, дешевле полной). Lite (`veo-3.1-lite-generate-001`) лицо НЕ умеет;
  Full (`veo-3.1-generate-001`) — дороже. Доставка лица — через `IDENTITY_IMAGE_B64`.
- При квоте 429 → включить биллинг и подождать ~30 мин до активации

## Лимиты и расходы
- `VIDEO_DAILY_LIMIT_PER_USER` — кружочков/день на юзера (**0 = безлимит**).
- Админ-команда `/costs` (или `/расходы`) — отчёт расходов (Veo секунды + ₽/$ по
  Veo/ElevenLabs/Claude) из таблицы `usage_log`. Цены — env `PRICE_*`, курс — `USD_RUB_RATE`
  (фолбэк; live — ЦБ РФ). Это **оценка**, без бесплатных кредитов/тарифов.

## Переменные окружения (все в Render)
BOT_TOKEN, ADMIN_TELEGRAM_ID, ANTHROPIC_API_KEY, MODEL,
ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID,
VEO_API_KEY, VEO_MODEL, SUPABASE_URL, SUPABASE_KEY,
GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_SA_JSON (Vertex-авторизация Veo),
IDENTITY_IMAGE_B64 (фото лица base64),
VIDEO_DAILY_LIMIT_PER_USER (0=безлимит),
PRICE_* / USD_RUB_RATE (для /costs, опционально)

## Архитектура
```
main.py          — точка входа, запускает бота + video worker
bot/
  handlers.py    — маршрутизация сообщений (text/voice/video)
  admin.py       — админ-команды (/stats, /costs, /reload_kb, загрузка KB)
  brain.py       — LLM + парсинг формата [FORMAT:video/voice/text]
  jobs.py        — очередь видео-задач (asyncio worker) + статус «записывает видео»
  voice.py       — ElevenLabs TTS/STT
  memory.py      — per-chat история
  persona_kb.py  — загрузка persona.md + knowledge/
video/
  veo.py         — Google Veo генерация (референс лица для fast/full)
  compose.py     — мукс голоса (ElevenLabs) поверх видео
  postprocess.py — crop 9:16 → 640×640, face detection
  ffmpeg_bin.py  — резолв абсолютного пути к ffmpeg (static/imageio-ffmpeg)
db/
  store.py       — SQLite (dev) / Supabase (prod), + usage_log (расходы)
config.py        — все настройки из env
identity/        — фото лица (gitignored, не деплоится)
video_clips/     — готовые клипы-кэш (gitignored)
```
