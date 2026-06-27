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
- Schema: `avatar_bot` (таблицы: `users`, `chat_history`, `video_jobs`)

## Фото для лица в видео (identity/)
Папка `identity/` в .gitignore → на Render она **пустая**.
Видео будут генерироваться без референса лица.
Чтобы добавить лицо на Render: загрузи `master.png` как секрет или используй URL в .env.

## Google Veo (кружочки)
- Veo — **платная функция**. Нужен биллинг: https://console.cloud.google.com/billing
- Модель: `veo-3.1-generate-preview` (с референсом лица) или `veo-3.1-lite-generate-preview` (дешевле, без лица)
- При квоте 429 → включить биллинг и подождать ~30 мин до активации

## Переменные окружения (все в Render)
BOT_TOKEN, ADMIN_TELEGRAM_ID, ANTHROPIC_API_KEY,
ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID,
VEO_API_KEY, VEO_MODEL, SUPABASE_URL, SUPABASE_KEY, MODEL

## Архитектура
```
main.py          — точка входа, запускает бота + video worker
bot/
  handlers.py    — маршрутизация сообщений (text/voice/video)
  brain.py       — LLM + парсинг формата [FORMAT:video/voice/text]
  jobs.py        — очередь видео-задач (asyncio worker)
  voice.py       — ElevenLabs TTS/STT
  memory.py      — per-chat история
video/
  veo.py         — Google Veo генерация
  compose.py     — мукс голоса (ElevenLabs) поверх видео
  postprocess.py — crop 9:16 → 640×640, face detection
db/
  store.py       — SQLite (dev) / Supabase (prod)
config.py        — все настройки из env
identity/        — фото лица (gitignored, не деплоится)
video_clips/     — готовые клипы-кэш (gitignored)
```
