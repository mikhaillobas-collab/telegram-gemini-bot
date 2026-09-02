import asyncio
import logging
from typing import Dict, List, Optional
import httpx
from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

POPULAR_OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat:free",
    "deepseek/deepseek-r1:free",
    "qwen/qwen-2.5-72b-instruct:free",
]


class GeminiService:
    def __init__(self):
        self.openrouter_api_key = config.OPENROUTER_API_KEY
        self.gemini_api_key = config.GEMINI_API_KEY
        self.model = config.GEMINI_MODEL
        self.system_instruction = config.SYSTEM_INSTRUCTION

        self.mode = "openrouter" if self.openrouter_api_key else "gemini"

        # История сообщений для OpenRouter: user_id -> list of message dicts
        self._user_messages: Dict[int, List[dict]] = {}

        # Клиент и чаты для прямого Gemini API
        self.client: Optional[genai.Client] = None
        self._user_chats: Dict[int, types.Chat] = {}

    def _get_gemini_client(self) -> genai.Client:
        if self.client is None:
            http_options_kwargs = {}
            if config.PROXY_URL:
                logger.info("Используется прокси для Gemini API: %s", config.PROXY_URL)
                http_options_kwargs["async_client_args"] = {"proxy": config.PROXY_URL}
                http_options_kwargs["client_args"] = {"proxy": config.PROXY_URL}
            if config.GEMINI_BASE_URL:
                logger.info("Используется кастомный базовый URL: %s", config.GEMINI_BASE_URL)
                http_options_kwargs["base_url"] = config.GEMINI_BASE_URL

            http_options = types.HttpOptions(**http_options_kwargs) if http_options_kwargs else None
            self.client = genai.Client(api_key=self.gemini_api_key, http_options=http_options)
        return self.client

    def _get_or_create_gemini_chat(self, user_id: int):
        client = self._get_gemini_client()
        if user_id not in self._user_chats:
            gen_config = types.GenerateContentConfig(
                system_instruction=self.system_instruction
            ) if self.system_instruction else None

            chat = client.aio.chats.create(
                model=self.model,
                config=gen_config,
            )
            self._user_chats[user_id] = chat
        return self._user_chats[user_id]

    async def _send_openrouter(self, user_id: int, text: str) -> str:
        if user_id not in self._user_messages:
            history = []
            if self.system_instruction:
                history.append({"role": "system", "content": self.system_instruction})
            self._user_messages[user_id] = history

        history = self._user_messages[user_id]
        history.append({"role": "user", "content": text})

        # Ограничиваем историю последними 20 сообщениями + system
        if len(history) > 21:
            system_msg = [m for m in history if m["role"] == "system"]
            history = system_msg + history[-20:]
            self._user_messages[user_id] = history

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mikhaillobas-collab/telegram-gemini-bot",
            "X-Title": "Telegram AI Assistant",
        }
        payload = {
            "model": self.model,
            "messages": history,
        }

        async with httpx.AsyncClient(timeout=90.0) as http_client:
            resp = await http_client.post(OPENROUTER_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error("OpenRouter error %s: %s", resp.status_code, resp.text)
                return f"❌ Ошибка OpenRouter ({resp.status_code}): {resp.text}"

            data = resp.json()
            choices = data.get("choices", [])
            if not choices or not choices[0].get("message"):
                return "Модель вернула пустой ответ."

            assistant_text = choices[0]["message"].get("content", "")
            history.append({"role": "assistant", "content": assistant_text})
            return assistant_text

    async def send_message(self, user_id: int, text: str) -> str:
        """
        Отправляет текстовое сообщение в контекст диалога пользователя.
        """
        try:
            if self.mode == "openrouter":
                return await self._send_openrouter(user_id, text)

            # Режим прямого Gemini API
            chat = self._get_or_create_gemini_chat(user_id)
            response = await chat.send_message(text)
            if response and response.text:
                return response.text
            return "Модель вернула пустой ответ. Попробуйте сформулировать запрос иначе."

        except Exception as e:
            logger.exception("Ошибка при обращении к ИИ API: %s", e)
            error_str = str(e)
            if "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
                return "❌ Ошибка: Неверный API-ключ."
            if "RESOURCE_EXHAUSTED" in error_str:
                return "⏳ Превышен лимит запросов (Rate Limit). Пожалуйста, подождите минуту и повторите попытку."
            if "PERMISSIONDENIED" in error_str or "PERMISSION_DENIED" in error_str:
                return (
                    "❌ **Ошибка 403 (PERMISSION_DENIED)**\n\n"
                    "Google требует настроить биллинг (Set up billing) в Google Cloud для этого проекта.\n"
                    "Рекомендуется переключиться на бесплатный OpenRouter (указав `OPENROUTER_API_KEY`)."
                )
            return f"❌ Ошибка при обработке запроса: {e}"

    async def send_image_message(self, user_id: int, caption: str, image_b64: str) -> str:
        """
        Отправляет изображение с подписью/запросом модели.
        """
        prompt_text = caption.strip() if caption else "Опиши подробно, что изображено на этом фото/документе, и извлеки любой текст, если он есть."
        try:
            if self.mode == "openrouter":
                if user_id not in self._user_messages:
                    history = []
                    if self.system_instruction:
                        history.append({"role": "system", "content": self.system_instruction})
                    self._user_messages[user_id] = history

                history = self._user_messages[user_id]
                history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                    ]
                })

                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mikhaillobas-collab/telegram-gemini-bot",
                    "X-Title": "Telegram AI Assistant",
                }
                payload = {
                    "model": self.model,
                    "messages": history,
                }

                async with httpx.AsyncClient(timeout=90.0) as http_client:
                    resp = await http_client.post(OPENROUTER_URL, headers=headers, json=payload)
                    if resp.status_code != 200:
                        logger.error("OpenRouter error %s: %s", resp.status_code, resp.text)
                        return f"❌ Ошибка OpenRouter ({resp.status_code}): {resp.text}"

                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices or not choices[0].get("message"):
                        return "Модель вернула пустой ответ."

                    assistant_text = choices[0]["message"].get("content", "")
                    history.append({"role": "assistant", "content": assistant_text})
                    return assistant_text
            else:
                import base64
                chat = self._get_or_create_gemini_chat(user_id)
                part = types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/jpeg"
                )
                response = await chat.send_message([part, prompt_text])
                if response and response.text:
                    return response.text
                return "Модель вернула пустой ответ."

        except Exception as e:
            logger.exception("Ошибка при обработке изображения: %s", e)
            return f"❌ Ошибка при обработке изображения: {e}"


    def reset_chat(self, user_id: int) -> bool:
        """
        Сбрасывает контекст беседы для пользователя.
        """
        cleared = False
        if user_id in self._user_messages:
            del self._user_messages[user_id]
            cleared = True
        if user_id in self._user_chats:
            del self._user_chats[user_id]
            cleared = True
        return cleared

    def set_model(self, new_model: str) -> None:
        """
        Устанавливает новую модель и сбрасывает текущие сессии.
        """
        self.model = new_model.strip()
        self._user_chats.clear()
        self._user_messages.clear()

    async def list_models(self) -> list[str]:
        """
        Возвращает список доступных моделей для текущего провайдера.
        """
        if self.mode == "openrouter":
            return POPULAR_OPENROUTER_MODELS

        client = self._get_gemini_client()
        models = []
        try:
            async for m in await client.aio.models.list():
                name = m.name or ""
                if "gemini" in name.lower():
                    clean_name = name.replace("models/", "")
                    models.append(clean_name)
        except Exception as e:
            logger.exception("Ошибка при получении списка моделей: %s", e)
            raise e
        return models
