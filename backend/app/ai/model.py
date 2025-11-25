import os
from typing import List, Tuple
from ..config import OPENAI_API_KEY, GEMINI_API_KEY

SYSTEM_PROMPT = (
    "Ты опытный бизнес-аналитик. Собирать цель, проблему/возможность, scope, бизнес-правила, KPI. "
    "Веди диалог по шагам, уточняй недостающее. Итог — строго структурированный документ."
)

def _format_context(history: List[Tuple[str, str]]) -> str:
    return "\n".join([f"{role}: {text}" for role, text in history])

class AIModel:
    def __init__(self):
        self.use_gemini = bool(GEMINI_API_KEY)
        self.use_openai = bool(OPENAI_API_KEY) and not self.use_gemini
        if self.use_gemini:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self._genai = genai
            self._gemini_model = genai.GenerativeModel("gemini-1.0-pro")
        elif self.use_openai:
            import openai
            openai.api_key = OPENAI_API_KEY
            self._openai = openai

    def reply(self, history: List[Tuple[str, str]], user_message: str) -> str:
        if self.use_gemini:
            try:
                chat_history = []
                chat_history.append({"role": "user", "parts": [SYSTEM_PROMPT]})
                for role, text in history:
                    chat_history.append({"role": "user" if role == "user" else "model", "parts": [text]})
                chat = self._gemini_model.start_chat(history=chat_history)
                resp = chat.send_message(user_message)
                return getattr(resp, "text", str(resp))
            except Exception:
                if self.use_openai:
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    for role, text in history:
                        messages.append({"role": role, "content": text})
                    messages.append({"role": "user", "content": user_message})
                    resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
                    return resp["choices"][0]["message"]["content"]
                return self._mock_reply(history, user_message)
        if self.use_openai:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for role, text in history:
                messages.append({"role": role, "content": text})
            messages.append({"role": "user", "content": user_message})
            resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            return resp["choices"][0]["message"]["content"]
        else:
            return self._mock_reply(history, user_message)

    def generate_document(self, history: List[Tuple[str, str]], title: str) -> str:
        prompt = (
            f"Собранный диалог:\n{_format_context(history)}\n"
            f"Сформируй документ требований в Markdown с разделами: Цель, Описание проблемы/возможности, Scope, Бизнес-правила, KPI, Use Case, User Stories, Диаграмма процесса (текст), Leading Indicators. Заголовок: {title}"
        )
        if self.use_gemini:
            try:
                resp = self._gemini_model.generate_content([SYSTEM_PROMPT, prompt])
                return getattr(resp, "text", str(resp))
            except Exception:
                if self.use_openai:
                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ]
                    resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
                    return resp["choices"][0]["message"]["content"]
                return self._mock_document(history, title)
        if self.use_openai:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            return resp["choices"][0]["message"]["content"]
        else:
            return self._mock_document(history, title)

    def _mock_reply(self, history: List[Tuple[str, str]], user_message: str) -> str:
        if not history:
            return "Здравствуйте. Опишите цель проекта и ожидаемый бизнес-результат."
        if "цель" in user_message.lower():
            return "Опишите границы (scope): что входит и что не входит в проект."
        if "scope" in user_message.lower() or "границ" in user_message.lower():
            return "Перечислите ключевые бизнес-правила, ограничения и зависимости."
        if "правил" in user_message.lower() or "огранич" in user_message.lower():
            return "Назовите KPI: метрики успеха и целевые значения."
        return "Принято. Уточните цель, scope, правила и KPI, если что-то не указано."

    def _mock_document(self, history: List[Tuple[str, str]], title: str) -> str:
        user_text = "\n".join([t for r, t in history if r == "user"]) or ""
        return f"# {title}\n\n**Цель:**\n{user_text[:200] or 'TBD'}\n\n**Описание проблемы/возможности:**\nTBD\n\n**Scope:**\nTBD\n\n**Бизнес-правила:**\nTBD\n\n**KPI:**\nTBD\n\n**Use Case:**\nTBD\n\n**User Stories:**\n- Как пользователь, я хочу ...\n\n**Диаграмма процесса:**\nШаги: ...\n\n**Leading Indicators:**\n- ..."

