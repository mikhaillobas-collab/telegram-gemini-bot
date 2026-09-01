# Telegram Gemini Bot (с белым списком пользователей)

Персональный Telegram-бот на базе Google Gemini API (`google-genai`) с контролем доступа по `user_id` и сохранением контекста беседы.

---

## 🔒 Разрешённые пользователи (Whitelist)
Бот обрабатывает запросы только от пользователей из белого списка в `.env`:
`ALLOWED_USER_IDS=276482250,381811957,387548739`

Всем остальным пользователям бот сообщает, что доступ ограничен, и указывает их `user_id`.

---

## ⚙️ Настройка переменных окружения

В файле `.env` (или в переменных окружения на сервере):

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
GEMINI_API_KEY=ваш_ключ_от_Google_AI_Studio
ALLOWED_USER_IDS=276482250,381811957,387548739
GEMINI_MODEL=gemini-3.6-flash
SYSTEM_INSTRUCTION=Ты умный, вежливый и полезный персональный ИИ-ассистент. Отвечай структурированно, емко и по существу на том языке, на котором к тебе обратились.
```

### Где взять ключи:
1. **`TELEGRAM_BOT_TOKEN`**: у официального бота [@BotFather](https://t.me/BotFather) в Telegram (команда `/newbot`).
2. **`GEMINI_API_KEY`**: бесплатно на [Google AI Studio](https://aistudio.google.com/app/apikey) (кнопка *Create API key*).

---

## 🚀 Варианты запуска на сервере

### Вариант А: Запуск через Docker Compose (Рекомендуется)
1. Установите Docker на сервере.
2. Перенесите папку `telegram_bot` на сервер.
3. Заполните `.env`.
4. Запустите:
```bash
docker compose up -d --build
```
Просмотр логов:
```bash
docker compose logs -f
```

---

### Вариант Б: Запуск как системный сервис Linux (systemd)
1. Установите зависимости:
```bash
pip install -r requirements.txt
```
2. Создайте файл сервиса `/etc/systemd/system/telegram-bot.service`:
```ini
[Unit]
Description=Telegram Gemini Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/telegram_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10
EnvironmentFile=/path/to/telegram_bot/.env

[Install]
WantedBy=multi-user.target
```
3. Активируйте и запустите:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

---

## 💻 Локальный запуск на Windows
1. Заполните `.env`.
2. Запустите `run_bot.bat` (или выполните `python bot.py` в терминале).
