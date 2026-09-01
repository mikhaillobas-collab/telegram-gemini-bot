import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла в директории проекта
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
SYSTEM_INSTRUCTION = os.getenv(
    "SYSTEM_INSTRUCTION",
    "Ты умный, вежливый и полезный персональный ИИ-ассистент. Отвечай структурированно, емко и по существу на том языке, на котором к тебе обратились.",
).strip()

# Парсинг белого списка ID
allowed_ids_raw = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = set()

for item in allowed_ids_raw.split(","):
    item = item.strip()
    if item.isdigit():
        ALLOWED_USER_IDS.add(int(item))

def validate_config() -> None:
    errors = []
    if not TELEGRAM_BOT_TOKEN or "your_telegram_bot_token" in TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не задан или содержит плейсхолдер.")
    if not GEMINI_API_KEY or "your_gemini_api_key" in GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY не задан или содержит плейсхолдер.")
    if not ALLOWED_USER_IDS:
        errors.append("ALLOWED_USER_IDS пуст. Ни у кого не будет доступа к боту.")

    if errors:
        print("\n[ОШИБКА КОНФИГУРАЦИИ]")
        for err in errors:
            print(f" - {err}")
        print("\nПожалуйста, укажите валидные переменные в .env или в системном окружении сервера.\n")
        sys.exit(1)
