import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject

import config
from gemini_service import GeminiService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация сервиса Gemini
gemini_service = GeminiService()


class WhitelistMiddleware(BaseMiddleware):
    """
    Middleware безопасности: пропускает только пользователей из белого списка ALLOWED_USER_IDS.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        if user.id not in config.ALLOWED_USER_IDS:
            logger.warning(
                "Попытка несанкционированного доступа: user_id=%s, username=%s",
                user.id,
                user.username,
            )
            if isinstance(event, Message):
                await event.answer(
                    f"⛔ **Доступ ограничен**\n\n"
                    f"Ваш Telegram ID: `{user.id}`\n"
                    f"Этот бот является частным и доступен только авторизованным пользователям.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return None

        return await handler(event, data)


dp = Dispatcher()
# Регистрируем проверку прав на сообщения
dp.message.middleware(WhitelistMiddleware())


async def send_chunked_message(message: Message, text: str):
    """
    Отправляет сообщение частями (до 4000 символов), с безопасным fallback
    на случай ошибок парсинга Markdown в ответе ИИ.
    """
    max_length = 4000
    chunks = []
    
    while len(text) > max_length:
        # Ищем перенос строки ближе к концу блока
        split_idx = text.rfind("\n", 0, max_length)
        if split_idx == -1:
            split_idx = max_length
        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    if text:
        chunks.append(text)

    for chunk in chunks:
        if not chunk:
            continue
        try:
            # Сначала пробуем отправить с Markdown
            await message.answer(chunk, parse_mode=ParseMode.MARKDOWN)
        except TelegramBadRequest as e:
            logger.warning("Не удалось отправить Markdown (%s), отправка обычным текстом", e)
            # Если в ответе Gemini были незакрытые теги/символы markdown — шлем без разметки
            await message.answer(chunk, parse_mode=None)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_name = message.from_user.first_name if message.from_user else "пользователь"
    await message.answer(
        f"👋 Привет, {user_name}!\n\n"
        f"Я персональный ИИ-ассистент на базе Google Gemini (`{config.GEMINI_MODEL}`).\n\n"
        f"💡 **Возможности:**\n"
        f"• Вы можете задавать любые вопросы, ставить задачи, просить написать код.\n"
        f"• Я сохраняю контекст нашей беседы.\n\n"
        f"📌 **Команды:**\n"
        f"• /reset или /clear — сбросить контекст текущей беседы и начать заново\n"
        f"• /id — узнать ваш Telegram ID\n"
        f"• /model — текущая модель",
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message(Command("reset", "clear"))
async def cmd_reset(message: Message):
    if message.from_user:
        gemini_service.reset_chat(message.from_user.id)
    await message.answer("🔄 **Контекст беседы очищен.** Можем начать с чистого листа!", parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("id"))
async def cmd_id(message: Message):
    user_id = message.from_user.id if message.from_user else "неизвестно"
    await message.answer(f"Ваш Telegram ID: `{user_id}`", parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("model"))
async def cmd_model(message: Message):
    await message.answer(f"Текущая модель: `{config.GEMINI_MODEL}`", parse_mode=ParseMode.MARKDOWN)


@dp.message(F.text)
async def handle_text(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_text = message.text

    # Показываем статус "печатает..." в Telegram
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # Получаем ответ от Gemini
    response_text = await gemini_service.send_message(user_id=user_id, text=user_text)

    # Отправляем ответ пользователю
    await send_chunked_message(message, response_text)


async def main():
    config.validate_config()

    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    logger.info("Бот запускается...")
    logger.info("Разрешенные ID пользователей: %s", config.ALLOWED_USER_IDS)
    logger.info("Модель: %s", config.GEMINI_MODEL)

    try:
        # Сбрасываем ожидающие обновления, чтобы бот не обрабатывал старые сообщения
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
