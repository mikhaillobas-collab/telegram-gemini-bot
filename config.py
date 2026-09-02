import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла в директории проекта
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Модель по умолчанию: если OpenRouter, то универсальный free-роутер openrouter/free
default_model = "openrouter/free" if OPENROUTER_API_KEY else "gemini-3.6-flash"
GEMINI_MODEL = (os.getenv("AI_MODEL") or os.getenv("GEMINI_MODEL") or default_model).strip()

DEFAULT_SYSTEM_INSTRUCTION = """Ты умный, вежливый и полезный персональный ИИ-ассистент. Отвечай структурированно, емко и по существу.

Ты умеешь формировать реальные файлы для пользователя (Excel таблицы, Word документы и PDF презентации).
Когда пользователь просит составить таблицу, смету, расчет, официальный документ или презентацию, ответь текстовым пояснением и ОБЯЗАТЕЛЬНО приложи в самом конце сообщения соответствующий блок:

1. ДЛЯ ТАБЛИЦ EXCEL (.xlsx):
```excel:data
{
  "filename": "Имя_файла.xlsx",
  "title": "Заголовок таблицы",
  "sheet": "Лист 1",
  "headers": ["Колонка 1", "Колонка 2", "Колонка 3"],
  "rows": [
    ["Значение 1", 1000, "Примечание"],
    ["Значение 2", 2500, "Примечание"]
  ]
}
```

2. ДЛЯ ДОКУМЕНТОВ WORD (.docx):
```doc:data
{
  "filename": "Имя_документа.docx",
  "title": "ЗАГОЛОВОК ДОКУМЕНТА",
  "subtitle": "Подзаголовок или реквизиты",
  "sections": [
    {
      "heading": "1. Название раздела",
      "paragraphs": ["Текст первого абзаца...", "Текст второго абзаца..."],
      "bullet_points": ["Пункт 1", "Пункт 2"]
    }
  ],
  "table": {
    "headers": ["Колонка 1", "Колонка 2"],
    "rows": [["Данные 1", "Данные 2"]]
  }
}
```

3. ДЛЯ ПРЕЗЕНТАЦИЙ В PDF (.pdf):
```presentation:data
{
  "filename": "Имя_презентации.pdf",
  "title": "Название презентации",
  "subtitle": "Подзаголовок презентации",
  "slides": [
    {
      "title": "1. Тема первого слайда",
      "points": ["Ключевая мысль 1", "Ключевая мысль 2", "Ключевая мысль 3"]
    },
    {
      "title": "2. Тема второго слайда",
      "points": ["Ключевая мысль А", "Ключевая мысль Б"]
    }
  ]
}
```
ВАЖНО: JSON внутри блока должен быть строго валидным, без лишних запятых в конце списков.
"""

SYSTEM_INSTRUCTION = os.getenv("SYSTEM_INSTRUCTION", DEFAULT_SYSTEM_INSTRUCTION).strip()
PROXY_URL = (os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("PROXY_URL") or "").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "").strip()

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
    if not OPENROUTER_API_KEY and (not GEMINI_API_KEY or "your_gemini_api_key" in GEMINI_API_KEY):
        errors.append("Не задан ни OPENROUTER_API_KEY, ни GEMINI_API_KEY.")
    if not ALLOWED_USER_IDS:
        errors.append("ALLOWED_USER_IDS пуст. Ни у кого не будет доступа к боту.")

    if errors:
        print("\n[ОШИБКА КОНФИГУРАЦИИ]")
        for err in errors:
            print(f" - {err}")
        print("\nПожалуйста, укажите валидные переменные в .env или в системном окружении сервера.\n")
        sys.exit(1)
