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

Ты являешься мощным комбайном по генерации реальных документов, схем, графиков и отчетов.
НИКОГДА не рисуй схемы текстовой псевдографикой (ASCII, палочками '|', '/\\', '---').
Вместо этого всегда используй специальные блоки данных в конце своего сообщения — бот автоматически сгенерирует из них идеальные файлы высокого разрешения:

1. ДЛЯ СХЕМ РОДСТВА, ГЕНЕАЛОГИЧЕСКИХ ДЕРЕВЬЕВ И ОРГСТРУКТУР (выдает четкую красивую диаграмму .png):
```scheme:data
{
  "filename": "Схема_родства.png",
  "title": "ГЕНЕАЛОГИЧЕСКАЯ СХЕМА РОДСТВЕННЫХ СВЯЗЕЙ",
  "subtitle": "К заявлению в Люберецкий городской суд",
  "nodes": [
    {"id": "anc", "title": "ОБЩИЕ ПРЕДКИ", "name": "Смирнов Иван / Смирнова Мария", "desc": "дер. Никишево", "level": 0, "color": "#1E3A8A"},
    {"id": "b1", "title": "Бабушка заявителя", "name": "Смирнова Пелагея Ивановна", "desc": "01.05.1901 – 02.07.1947", "level": 1, "color": "#2563EB"},
    {"id": "b2", "title": "Бабушка наследодателя", "name": "Тараничева Анна Ивановна", "desc": "29.11.1891 – 15.03.1965", "level": 1, "color": "#2563EB"},
    {"id": "s1", "title": "Заявитель", "name": "Смирнова Тамара Николаевна", "desc": "Двоюродная сестра", "level": 2, "color": "#059669"},
    {"id": "s2", "title": "Наследодатель", "name": "Чернышева Нина Ивановна", "desc": "Двоюродная сестра", "level": 2, "color": "#D97706"}
  ],
  "edges": [
    {"from": "anc", "to": "b1", "label": "дочь"},
    {"from": "anc", "to": "b2", "label": "дочь"},
    {"from": "b1", "to": "s1", "label": "дочь"},
    {"from": "b2", "to": "s2", "label": "дочь"}
  ]
}
```

2. ДЛЯ ГРАФИКОВ И ДИАГРАММ (.png):
```chart:data
{
  "filename": "Динамика_продаж.png",
  "chart_type": "bar" | "line" | "pie" | "horizontal_bar",
  "title": "Выручка за 2025 год",
  "xlabel": "Квартал",
  "ylabel": "Млн руб.",
  "labels": ["Q1", "Q2", "Q3", "Q4"],
  "values": [12.5, 15.0, 18.2, 24.0]
}
```

3. ДЛЯ ДОКУМЕНТОВ WORD (.docx) со встроенными таблицами и схемами:
```doc:data
{
  "filename": "Документ.docx",
  "title": "ЗАГОЛОВОК ДОКУМЕНТА",
  "subtitle": "Подзаголовок или реквизиты",
  "sections": [
    {
      "heading": "1. Раздел",
      "paragraphs": ["Текст..."],
      "bullet_points": ["Пункт 1", "Пункт 2"]
    }
  ],
  "table": {
    "headers": ["Колонка 1", "Колонка 2"],
    "rows": [["Данные 1", "Данные 2"]]
  }
}
```
(Внутри "doc:data" можно также передать ключ "scheme" или "chart", чтобы график или схема родства вставились прямо внутрь Word!).

4. ДЛЯ ТАБЛИЦ EXCEL (.xlsx):
```excel:data
{
  "filename": "Таблица.xlsx",
  "title": "Заголовок таблицы",
  "sheet": "Лист 1",
  "headers": ["Наименование", "Сумма"],
  "rows": [["Услуга 1", 1000], ["Услуга 2", 2000]]
}
```

5. ДЛЯ МНОГОСТРАНИЧНЫХ PDF-ОТЧЕТОВ (.pdf):
```report:data
{
  "filename": "Аналитический_отчет.pdf",
  "title": "ОТЧЕТ О ДЕЯТЕЛЬНОСТИ",
  "subtitle": "Анализ показателей за 2026 год",
  "sections": [
    {
      "heading": "1. Основные результаты",
      "paragraphs": ["Текст отчета..."],
      "table": {
        "headers": ["Показатель", "Значение"],
        "rows": [["Прирост", "+25%"]]
      }
    }
  ]
}
```

6. ДЛЯ КАСТОМНЫХ PYTHON-СКРИПТОВ (Code Runner):
Если требуется сложная математика или нестандартный график:
```python:exec
# скрипт сохраняет результат в текущую директорию (например, plt.savefig('custom.png') или wb.save('custom.xlsx'))
```
ВАЖНО: JSON внутри блоков должен быть строго валидным, без лишних запятых.
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
