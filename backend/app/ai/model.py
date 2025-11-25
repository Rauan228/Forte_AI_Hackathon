import os
from typing import List, Tuple
from ..config import OPENAI_API_KEY, GEMINI_API_KEY
import json

SYSTEM_PROMPT = (
    "Ты — AI-бизнес-аналитик. Проводишь мини-интервью и собираешь поля: Цель, Описание проблемы/возможности, Scope (входит/не входит), Бизнес-правила, KPI, Use Case, User Stories, Leading Indicators. "
    "Задавай по одному вопросу за раз, анализируя какие поля ещё не заполнены. Когда данных достаточно — скажи, что готово, и перестань задавать вопросы. "
    "Каждый ответ возвращай в формате: сначала краткий JSON-обновление слотов одной строкой, затем пустая строка, затем текст для пользователя. JSON должен содержать только изменённые ключи из: goal, description, scope_in, scope_out, rules, kpi, use_cases, user_stories, leading_indicators."
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
            self._gemini_model_names = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro",
            ]
        elif self.use_openai:
            import openai
            openai.api_key = OPENAI_API_KEY
            self._openai = openai

    def reply_and_slots(self, history: List[Tuple[str, str]], user_message: str, current_slots: dict) -> Tuple[str, dict, bool]:
        if self.use_gemini:
            text = self._gemini_chat_text(history, f"Текущие слоты: {json.dumps(current_slots, ensure_ascii=False)}\nСообщение пользователя: {user_message}\nВерни JSON и текст, как описано.")
            if text is not None:
                j, reply = self._split_json_text(text)
                if not j:
                    j = self._local_extract_slots(user_message)
                base = j.get("delta", j) if isinstance(j, dict) else j
                if not self._has_expected_keys(base):
                    base = self._local_extract_slots(user_message)
                ready = self._infer_ready(current_slots, base)
                return reply, base, ready
        if self.use_openai:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for role, text in history:
                messages.append({"role": role, "content": text})
            messages.append({"role": "user", "content": f"Текущие слоты: {json.dumps(current_slots, ensure_ascii=False)}\nСообщение пользователя: {user_message}\nВерни JSON и текст, как описано."})
            resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            content = resp["choices"][0]["message"]["content"]
            j, reply = self._split_json_text(content)
            if not j:
                j = self._local_extract_slots(user_message)
            base = j.get("delta", j) if isinstance(j, dict) else j
            if not self._has_expected_keys(base):
                base = self._local_extract_slots(user_message)
            ready = self._infer_ready(current_slots, base)
            return reply, base, ready
        reply = self._mock_reply(history, user_message)
        delta = self._local_extract_slots(user_message)
        return reply, delta, False

    def generate_document(self, history: List[Tuple[str, str]], title: str) -> str:
        prompt = (
            f"Собранный диалог:\n{_format_context(history)}\n"
            f"Сформируй документ требований в Markdown с разделами: Цель, Описание проблемы/возможности, Scope, Бизнес-правила, KPI, Use Case, User Stories, Диаграмма процесса (текст), Leading Indicators. Заголовок: {title}"
        )
        if self.use_gemini:
            text = self._gemini_generate_text([SYSTEM_PROMPT, prompt])
            if text is not None:
                return text or ""
        elif self.use_openai:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            return resp["choices"][0]["message"]["content"] or ""
        else:
            return self._mock_document(history, title)

    def generate_document_from_slots(self, slots: dict, title: str) -> str:
        prompt = (
            "На основе следующих данных сформируй структурированный документ требований (BRD) в Markdown:\n"
            + json.dumps(slots, ensure_ascii=False)
            + f"\nЗаголовок: {title}"
        )
        if self.use_gemini:
            text = self._gemini_generate_text([SYSTEM_PROMPT, prompt])
            if text:
                return text
        if self.use_openai:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
            resp = self._openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            content = resp["choices"][0]["message"]["content"]
            if content:
                return content
        from .generators import generate_brd_markdown
        from .session_logic import SessionContext
        return generate_brd_markdown(SessionContext(slots), title)

    def _split_json_text(self, content: str):
        s = content.strip()
        j = {}
        reply = s
        try:
            if "```" in s:
                start = s.find("```json")
                if start == -1:
                    start = s.find("```")
                if start != -1:
                    end = s.find("```", start + 3)
                    if end != -1:
                        js = s[start + (7 if s[start:start+7]=="```json" else 3): end].strip()
                        j = json.loads(js)
                        reply = (s[:start] + s[end+3:]).strip()
                        return j, reply
            lb = s.find("{")
            rb = s.rfind("}")
            if lb != -1 and rb != -1 and rb > lb:
                js = s[lb: rb+1]
                j = json.loads(js)
                reply = (s[:lb] + s[rb+1:]).strip()
        except Exception:
            j = {}
            reply = s
        return j, reply

    def _infer_ready(self, current_slots: dict, delta: dict) -> bool:
        merged = dict(current_slots or {})
        for k, v in (delta or {}).items():
            merged[k] = v
        from .session_logic import SessionContext
        return SessionContext(merged).is_complete()

    def _local_extract_slots(self, text: str) -> dict:
        t = (text or "").lower()
        out = {}
        if "цель" in t:
            out["goal"] = text.split(":",1)[-1].strip() if ":" in text else text
        if "scope" in t or "входит" in t or "не входит" in t:
            if "входит" in t:
                out["scope_in"] = text
            if "не входит" in t:
                out["scope_out"] = text
        if "kpi" in t or "показател" in t:
            out["kpi"] = [text]
        if "правил" in t:
            out["rules"] = [text]
        if "use case" in t:
            out["use_cases"] = [text]
        if ("user stor" in t) or ("как " in t and "я хочу" in t):
            out["user_stories"] = [text]
        if "leading" in t or "индикатор" in t:
            out["leading_indicators"] = [text]
        return out

    def _has_expected_keys(self, d: dict) -> bool:
        if not isinstance(d, dict):
            return False
        keys = {"goal","description","scope_in","scope_out","rules","kpi","use_cases","user_stories","leading_indicators"}
        return any(k in d for k in keys)

    def _gemini_chat_text(self, history: List[Tuple[str, str]], prompt: str) -> str:
        try:
            for name in getattr(self, "_gemini_model_names", []):
                model = self._genai.GenerativeModel(name)
                chat_history = []
                chat_history.append({"role": "user", "parts": [SYSTEM_PROMPT]})
                for role, text in history:
                    chat_history.append({"role": "user" if role == "user" else "model", "parts": [text]})
                chat = model.start_chat(history=chat_history)
                resp = chat.send_message(prompt)
                text = getattr(resp, "text", None)
                if not text:
                    try:
                        c = getattr(resp, "candidates", None)
                        if c and len(c) > 0:
                            parts = getattr(c[0], "content", {}).get("parts", [])
                            if parts and hasattr(parts[0], "text"):
                                text = parts[0].text
                    except Exception:
                        text = None
                if text:
                    return text
        except Exception:
            return None
        return None

    def _gemini_generate_text(self, parts) -> str:
        try:
            for name in getattr(self, "_gemini_model_names", []):
                model = self._genai.GenerativeModel(name)
                resp = model.generate_content(parts)
                text = getattr(resp, "text", None)
                if not text:
                    try:
                        c = getattr(resp, "candidates", None)
                        if c and len(c) > 0:
                            parts2 = getattr(c[0], "content", {}).get("parts", [])
                            if parts2 and hasattr(parts2[0], "text"):
                                text = parts2[0].text
                    except Exception:
                        text = None
                if text:
                    return text
        except Exception:
            return None
        return None

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

