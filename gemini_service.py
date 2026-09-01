import asyncio
import logging
from typing import Dict, Optional
from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.model = config.GEMINI_MODEL
        self.system_instruction = config.SYSTEM_INSTRUCTION
        self.client: Optional[genai.Client] = None
        self._user_chats: Dict[int, types.Chat] = {}

    def _get_client(self) -> genai.Client:
        if self.client is None:
            self.client = genai.Client(api_key=self.api_key)
        return self.client

    def _get_or_create_chat(self, user_id: int):
        client = self._get_client()
        if user_id not in self._user_chats:
            gen_config = types.GenerateContentConfig(
                system_instruction=self.system_instruction
            ) if self.system_instruction else None

            # Создаем новую сессию чата для пользователя (асинхронный клиент)
            chat = client.aio.chats.create(
                model=self.model,
                config=gen_config,
            )
            self._user_chats[user_id] = chat
        return self._user_chats[user_id]

    async def send_message(self, user_id: int, text: str) -> str:
        """
        Отправляет сообщение в контекст диалога пользователя и возвращает ответ модели.
        """
        try:
            chat = self._get_or_create_chat(user_id)
            response = await chat.send_message(text)
            if response and response.text:
                return response.text
            return "Модель вернула пустой ответ. Попробуйте сформулировать запрос иначе."
        except Exception as e:
            logger.exception("Ошибка при обращении к Gemini API: %s", e)
            error_str = str(e)
            if "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
                return "❌ Ошибка: Указан неверный GEMINI_API_KEY. Проверьте настройки API-ключа."
            if "RESOURCE_EXHAUSTED" in error_str:
                return "⏳ Превышен лимит запросов (Rate Limit). Пожалуйста, подождите минуту и повторите попытку."
            return f"❌ Ошибка при обработке запроса: {e}"

    def reset_chat(self, user_id: int) -> bool:
        """
        Сбрасывает контекст беседы для пользователя.
        """
        if user_id in self._user_chats:
            del self._user_chats[user_id]
            return True
        return False
