import os
import re
import json
import logging
from typing import List, Tuple, Optional
from ..config import OPENAI_API_KEY, GEMINI_API_KEY

# Setup logger for corrections
logger = logging.getLogger("corrector")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler("corrections.log")
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

LIST_SLOTS = {"rules", "kpi", "constraints", "priorities", "use_cases", "user_stories", "leading_indicators"}
KEYWORD_TERMS = {
    "goal": ["цель", "результат", "target"],
    "description": ["описани", "проблем", "возможност"],
    "scope_in": ["scope", "входит", "охватывает"],
    "scope_out": ["не входит", "исключен"],
    "rules": ["правил", "policy", "регламент"],
    "kpi": ["kpi", "показател", "метрик"],
    "constraints": ["огранич", "зависим", "комплаенс", "риск"],
    "priorities": ["приоритет", "mvp", "важност"],
    "use_cases": ["use case", "сценарий"],
    "user_stories": ["user story", "как ", "я хочу"],
    "leading_indicators": ["leading", "индикатор", "ранний признак"],
}

SYSTEM_PROMPT = (
    "Ты — AI-агент бизнес-аналитик для внутреннего использования в банке. "
    "Твоя задача — собирать, формализовать и структурировать бизнес-требования от сотрудников, генерировать аналитические артефакты и документацию.\n"
    "ТРЕБОВАНИЯ К ПОВЕДЕНИЮ:\n"
    "1. Веди диалог в формате чат-бота, уточняя детали задачи и контекста.\n"
    "2. Системно собирай данные по слотам: цель, описание, scope, бизнес-правила, KPI, а также constraints, priorities, use_cases, user_stories, leading_indicators.\n"
    "3. Генерируй аналитические артефакты: Use Case, диаграммы процессов, user stories, лидирующие индикаторы.\n"
    "4. Помни об интеграции с Confluence — собранные данные пойдут в документ, который мы публикуем автоматически.\n"
    "5. Формулируй ответы кратко, структурировано, исключительно в деловом стиле, без воды или юмора.\n"
    "6. Если вопрос непонятен — уточни детали, не выдумывай ответа.\n"
    "7. Стремись завершить сбор требований за ≤5 минут реального времени разговора.\n"
    "8. Ключевые метрики: скорость/точность генерации требований (Performance), снижение нагрузки на аналитиков (Business), доля пользователей, завершивших диалог без помощи (Usability).\n"
    "9. Не повторяй слово «бизнес» без необходимости. Если сообщение пользователя уже по теме, просто продолжай уточнение. "
    "Только если реплика явно не относится к задачам банка, аккуратно направь его обратно к бизнес-задаче, но не подсказывай.\n"
    "10. Всегда действуй как аналитик, сосредоточенный на фактах и документации, без личного мнения и отвлечений.\n\n"
    "ФОРМАТ ОТВЕТА (строго валидный JSON):\n"
    "```json\n"
    "{\n"
    "  \"analysis\": \"Только если сообщение не по теме или мешает бизнес-диалогу; иначе 'OK'\",\n"
    "  \"delta\": { \"goal\": \"...\", \"rules\": [\"...\"] },\n"
    "  \"reply\": \"Краткий ответ с направляющей репликой и (при необходимости) одним уточняющим вопросом\"\n"
    "}\n"
    "```\n"
    "Где `reply` всегда один блок и следует правилам."
)

def _format_context(history: List[Tuple[str, str]]) -> str:
    return "\n".join([f"{role}: {text}" for role, text in history])

class AIModel:
    def __init__(self):
        self.use_gemini = bool(GEMINI_API_KEY)
        self.use_openai = bool(OPENAI_API_KEY) and not self.use_gemini
        if self.use_gemini:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=GEMINI_API_KEY)
            self._genai = genai
            self._gemini_model_names = [
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "gemini-flash-latest",
                "gemini-pro-latest",
            ]
        elif self.use_openai:
            import openai  # type: ignore
            openai.api_key = OPENAI_API_KEY
            self._openai = openai

    def reply_and_slots(self, history: List[Tuple[str, str]], user_message: str, current_slots: dict) -> Tuple[str, dict, bool]:
        prompt = (
            f"Текущие заполненные данные (slots): {json.dumps(current_slots, ensure_ascii=False)}\n"
            f"Последнее сообщение пользователя: \"{user_message}\"\n"
            "Проанализируй сообщение, исправь ошибки, обнови слоты и верни JSON, где reply использует многострочные списки и задаёт следующий вопрос."
        )
        
        response_text = None
        if self.use_gemini:
            response_text = self._gemini_chat_text(history, prompt)
        elif self.use_openai:
            response_text = self._openai_chat_text(history, prompt)
        
        if not response_text:
            # Fallback
            delta = self._local_extract_slots(user_message)
            fallback_reply = self._format_reply_style(
                "Извините. Сервис недоступен.\n\nПожалуйста, повторите последнее сообщение."
            )
            return fallback_reply, delta, False

        # Parse JSON
        data, raw_text = self._parse_json_response(response_text)
        
        analysis = data.get("analysis")
        if analysis and analysis != "OK":
            logger.info(f"Correction applied: {analysis}")

        reply = data.get("reply", raw_text)
        delta = data.get("delta", {})
        
        # If extraction failed but we have text, try local fallback for safety
        if not delta and not data:
             delta = self._local_extract_slots(user_message)
             reply = raw_text

        ready = self._infer_ready(current_slots, delta)
        reply = self._format_reply_style(reply)
        return reply, delta, ready

    def generate_document_from_slots(self, slots: dict, title: str) -> str:
        prompt = (
            f"Ты — AI Business Analyst. На основе собранных данных сформируй полный документ BRD (Business Requirements Document).\n"
            f"Данные: {json.dumps(slots, ensure_ascii=False)}\n"
            f"Заголовок: {title}\n"
            "ТРЕБОВАНИЯ К ДОКУМЕНТУ:\n"
            "1. Используй Markdown с заголовками и списками.\n"
            "2. Обязательные разделы: Цель, Контекст/Описание, Scope (In/Out), Бизнес-правила, KPI, Ограничения, Приоритеты.\n"
            "3. Артефакты: подробный Use Case (акторы, предусловия, основной/альтернативные потоки), минимум 3 User Stories, Leading Indicators, процесс в ```mermaid```.\n"
            "4. Делай выводы строго по данным: исправляй противоречия, подсвечивай предположения, если данных мало.\n"
            "5. Соблюдай дружелюбный деловой тон; списки и нумерация должны быть на отдельных строках.\n"
        )
        
        text = None
        if self.use_gemini:
            text = self._gemini_generate_text([prompt])
        elif self.use_openai:
            text = self._openai_generate_text(prompt)
            
        if text:
            return text
            
        # Fallback
        from .generators import generate_brd_markdown
        from .session_logic import SessionContext
        return generate_brd_markdown(SessionContext(slots), title)

    def _parse_json_response(self, text: str) -> Tuple[dict, str]:
        """Extracts JSON from text, returns (dict, remaining_text)"""
        s = text.strip()
        try:
            # Find JSON block
            start_idx = s.find("```json")
            if start_idx != -1:
                end_idx = s.find("```", start_idx + 7)
                if end_idx != -1:
                    json_str = s[start_idx+7:end_idx].strip()
                    data = json.loads(json_str)
                    # If the LLM put the reply INSIDE the json, great. 
                    # If it put text outside, we ignore outside text or append it if 'reply' is missing.
                    return data, data.get("reply", "")
            
            # Try finding raw {}
            start_idx = s.find("{")
            end_idx = s.rfind("}")
            if start_idx != -1 and end_idx > start_idx:
                json_str = s[start_idx:end_idx+1]
                data = json.loads(json_str)
                return data, data.get("reply", "")
                
        except Exception:
            pass
        
        return {}, s

    def _infer_ready(self, current_slots: dict, delta: dict) -> bool:
        merged = dict(current_slots or {})
        for k, v in (delta or {}).items():
            merged[k] = v
        
        # Check completeness
        required = ["goal", "description", "scope_in", "rules", "kpi", "constraints", "priorities"]
        for k in required:
            val = merged.get(k)
            if not val:
                return False
            if isinstance(val, list) and len(val) == 0:
                return False
        return True

    def _local_extract_slots(self, text: str) -> dict:
        t = (text or "").strip()
        out = {}
        if not t:
            return out
        segments = [seg.strip() for seg in re.split(r"[.\n;]+", t) if seg.strip()]
        for seg in segments:
            seg_low = seg.lower()
            for slot, terms in KEYWORD_TERMS.items():
                if any(term in seg_low for term in terms):
                    value = seg.split(":", 1)[-1].strip() if ":" in seg else seg
                    if slot in LIST_SLOTS:
                        bucket = out.setdefault(slot, [])
                        if value not in bucket:
                            bucket.append(value)
                    else:
                        out[slot] = value
        return out
        return out

    def _format_reply_style(self, text: Optional[str]) -> str:
        if not text:
            return ""
        lines = []
        for raw in text.splitlines():
            stripped = raw.rstrip()
            if not stripped.strip():
                if lines and lines[-1] == "":
                    continue
                lines.append("")
                continue
            working = stripped.strip()
            bullet_prefix = ""
            if working.startswith(("-", "•", "*")):
                bullet_prefix = "- "
                working = working[1:].strip()
            working = re.sub(r"^\d+\.\s*", "", working)
            cleaned = f"{bullet_prefix}{working}" if bullet_prefix else working
            lines.append(cleaned)
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines).strip()

    def _gemini_chat_text(self, history: List[Tuple[str, str]], prompt: str) -> Optional[str]:
        for name in getattr(self, "_gemini_model_names", []):
            try:
                model = self._genai.GenerativeModel(name)
                chat_history = [{"role": "user", "parts": [SYSTEM_PROMPT]}]
                for role, text in history:
                    if not text:
                        continue
                    chat_history.append({"role": "user" if role == "user" else "model", "parts": [text]})
                chat = model.start_chat(history=chat_history)
                resp = chat.send_message(prompt)
                text = getattr(resp, "text", None)
                if text:
                    return text
                candidates = getattr(resp, "candidates", None)
                if not candidates:
                    continue
                parts = getattr(candidates[0].content, "parts", []) if getattr(candidates[0], "content", None) else []
                for part in parts:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        return part_text
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", name, exc)
                continue
        return None

    def _gemini_generate_text(self, parts) -> Optional[str]:
        for name in getattr(self, "_gemini_model_names", []):
            try:
                model = self._genai.GenerativeModel(name)
                resp = model.generate_content(parts)
                text = getattr(resp, "text", None)
                if text:
                    return text
                candidates = getattr(resp, "candidates", None)
                if candidates:
                    parts_seq = getattr(candidates[0].content, "parts", []) if getattr(candidates[0], "content", None) else []
                    for part in parts_seq:
                        part_text = getattr(part, "text", None)
                        if part_text:
                            return part_text
            except Exception as exc:
                logger.warning("Gemini model %s (doc) failed: %s", name, exc)
                continue
        return None

    def _openai_chat_text(self, history: List[Tuple[str, str]], prompt: str) -> Optional[str]:
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for role, text in history:
                messages.append({"role": role, "content": text})
            messages.append({"role": "user", "content": prompt})
            resp = self._openai.ChatCompletion.create(model="gpt-4o", messages=messages)
            return resp["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("OpenAI chat failed: %s", exc)
            return None

    def _openai_generate_text(self, prompt: str) -> Optional[str]:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            resp = self._openai.ChatCompletion.create(model="gpt-4o", messages=messages)
            return resp["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("OpenAI doc generation failed: %s", exc)
            return None

