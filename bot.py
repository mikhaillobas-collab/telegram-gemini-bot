import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message, TelegramObject
import base64

import config
import file_extractor
import file_generator
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


async def send_response_and_files(message: Message, raw_response: str):
    """
    Извлекает сгенерированные файлы (Excel, Word, PDF), отправляет пользователю
    чистый текстовый ответ без JSON-блоков и прикрепляет созданные файлы.
    """
    cleaned_text, generated_files = file_generator.extract_and_generate_files(raw_response)
    if cleaned_text:
        await send_chunked_message(message, cleaned_text)

    for file_bytes, filename in generated_files:
        try:
            input_file = BufferedInputFile(file_bytes, filename=filename)
            await message.answer_document(document=input_file)
        except Exception as e:
            logger.exception("Ошибка отправки файла %s: %s", filename, e)
            await message.answer(f"❌ Не удалось отправить сформированный файл `{filename}`: {e}")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_name = message.from_user.first_name if message.from_user else "пользователь"
    await message.answer(
        f"👋 Привет, {user_name}!\n\n"
        f"Я персональный ИИ-ассистент на базе `{gemini_service.model}`.\n\n"
        f"💡 **Возможности:**\n"
        f"• Задавайте любые вопросы, ставьте задачи, просите написать код.\n"
        f"• **Генерация файлов**: попросите «создай смету в Excel», «напиши договор в Word» или «сделай презентацию в PDF» — и я сгенерирую готовый файл!\n"
        f"• **Чтение документов**: отправляйте файлы (PDF, Word DOCX, TXT, код, таблицы) — я проанализирую их и отвечу на вопросы!\n"
        f"• **Чтение фото и сканов**: отправляйте фото — я распознаю текст и опишу детали.\n"
        f"• Я сохраняю контекст нашей беседы.\n\n"
        f"📌 **Команды:**\n"
        f"• /reset или /clear — сбросить контекст беседы\n"
        f"• /models — список моделей\n"
        f"• /setmodel <имя> — сменить модель\n"
        f"• /id — узнать ваш Telegram ID",
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
    await message.answer(f"Текущая активная модель: `{gemini_service.model}`", parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("models"))
async def cmd_models(message: Message):
    await message.answer("🔍 Запрашиваю список доступных моделей у Google API...")
    try:
        models = await gemini_service.list_models()
        if not models:
            await message.answer("Не удалось получить список моделей или список пуст.")
            return

        text = "📋 **Доступные модели для вашего API-ключа:**\n\n"
        for m in models:
            prefix = "👉 " if m == gemini_service.model else "• "
            text += f"{prefix}`{m}`\n"
        text += "\nЧтобы переключить модель, отправьте:\n`/setmodel <название_модели>`"
        await send_chunked_message(message, text)
    except Exception as e:
        await message.answer(f"❌ Ошибка при запросе списка моделей: `{e}`", parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("setmodel"))
async def cmd_setmodel(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Укажите модель. Пример:\n`/setmodel gemini-3.6-flash`", parse_mode=ParseMode.MARKDOWN)
        return

    new_model = args[1].strip()
    gemini_service.set_model(new_model)
    await message.answer(f"✅ Модель успешно изменена на: `{new_model}`.\nКонтекст беседы сброшен.", parse_mode=ParseMode.MARKDOWN)



@dp.message(F.text)
async def handle_text(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_text = message.text

    # Показываем статус "печатает..." в Telegram
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # Получаем ответ от Gemini
    response_text = await gemini_service.send_message(user_id=user_id, text=user_text)

    # Отправляем ответ пользователю (включая сгенерированные файлы)
    await send_response_and_files(message, response_text)


@dp.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    user_id = message.from_user.id
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    try:
        photo = message.photo[-1]
        file_io = await bot.download(photo)
        if not file_io:
            await message.answer("Не удалось скачать фотографию.")
            return

        file_bytes = file_io.getvalue()
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        caption = message.caption or ""
        response_text = await gemini_service.send_image_message(user_id=user_id, caption=caption, image_b64=b64)
        await send_response_and_files(message, response_text)
    except Exception as e:
        logger.exception("Ошибка при обработке фото: %s", e)
        await message.answer(f"❌ Ошибка при обработке фото: {e}")


@dp.message(F.document)
async def handle_document(message: Message, bot: Bot):
    user_id = message.from_user.id
    doc = message.document
    if not doc:
        return

    # Ограничение по размеру 20 МБ
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer("⚠️ Файл слишком большой. Максимальный размер: 20 МБ.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    status_msg = await message.answer(f"⏳ Читаю документ `{doc.file_name}`...")

    try:
        file_io = await bot.download(doc)
        if not file_io:
            await status_msg.edit_text("Не удалось скачать файл из Telegram.")
            return

        file_bytes = file_io.getvalue()
        content, is_image = file_extractor.process_file_bytes(
            file_bytes=file_bytes,
            filename=doc.file_name or "document",
            mime_type=doc.mime_type
        )

        if is_image:
            response_text = await gemini_service.send_image_message(
                user_id=user_id,
                caption=message.caption or "",
                image_b64=content
            )
        else:
            caption = message.caption or "Проанализируй этот документ и предоставь подробный разбор/резюме его содержания."
            prompt = (
                f"📁 [Прикреплённый документ: {doc.file_name}]\n\n"
                f"{content}\n\n"
                f"---\n"
                f"Запрос пользователя к документу: {caption}"
            )
            response_text = await gemini_service.send_message(user_id=user_id, text=prompt)

        # Удаляем временное статус-сообщение
        try:
            await status_msg.delete()
        except Exception:
            pass

        await send_response_and_files(message, response_text)
    except Exception as e:
        logger.exception("Ошибка при обработке документа: %s", e)
        await message.answer(f"❌ Ошибка при обработке документа: {e}")



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
