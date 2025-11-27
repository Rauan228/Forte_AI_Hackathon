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

LIST_SLOTS = {
    "rules", "kpi", "constraints", "use_cases", "user_stories",
    "business_requirements", "functional_requirements", "non_functional_requirements",
    "recommendations"
}
KEYWORD_TERMS = {
    "goal": ["цель", "результат", "target", "задача"],
    "description": ["описани", "проблем", "возможност", "контекст"],
    "scope_in": ["scope", "входит", "охватывает", "включает"],
    "scope_out": ["не входит", "исключен", "out of scope"],
    "business_requirements": ["бизнес-требован", "business requirement"],
    "functional_requirements": ["функциональн", "functional"],
    "non_functional_requirements": ["нефункциональн", "non-functional", "nfr"],
    "rules": ["правил", "policy", "регламент", "бизнес-правил"],
    "kpi": ["kpi", "показател", "метрик", "успех"],
    "constraints": ["огранич", "зависим", "комплаенс", "риск"],
    "use_cases": ["use case", "сценарий", "актер", "поток"],
    "user_stories": ["user story", "как ", "я хочу", "чтобы"],
    "glossary": ["термин", "определени", "словарь", "глоссарий"],
    "recommendations": ["рекомендац", "улучшен", "предложен"],
}

SYSTEM_PROMPT = (
    "Ты — AI-агент, выполняющий функции профессионального бизнес-аналитика в крупном банке.\n"
    "Ты заменяешь рутинную работу аналитиков и автоматически формируешь качественные "
    "бизнес-требования, артефакты и документацию для Confluence. Вся валюта в тенге.\n\n"
    "═══════════════════════════════════════════════════════════════\n"
    "ТВОЯ РОЛЬ\n"
    "═══════════════════════════════════════════════════════════════\n"
    "Ты — виртуальный бизнес-аналитик уровня Senior. Ты умеешь:\n"
    "• понимать бизнес-контекст по ключевым словам;\n"
    "• грамотно вести диалог с сотрудником без лишних вопросов;\n"
    "• уточнять только то, что критически важно;\n"
    "• анализировать проблему так же глубоко, как живой аналитик;\n"
    "• формировать структурированные артефакты и документацию.\n\n"
    "═══════════════════════════════════════════════════════════════\n"
    "ПОВЕДЕНИЕ И АЛГОРИТМ\n"
    "═══════════════════════════════════════════════════════════════\n"
    "1. Пользователь пишет задачу в свободной форме.\n"
    "2. Ты автоматически извлекаешь: цели, проблемы, участников, источники данных, процессы, ограничения, KPI.\n"
    "3. Сам заполняешь пробелы логически, используя свою модель опыта бизнес-аналитика.\n"
    "4. Формируешь полный Confluence-документ без просьбы.\n"
    "5. Если чего-то критически не хватает — задаёшь один умный, короткий вопрос (не более одного раза).\n"
    "6. Умеешь писать документацию с максимально высокой степенью ясности и формализации.\n\n"
    "═══════════════════════════════════════════════════════════════\n"
    "СТИЛЬ\n"
    "═══════════════════════════════════════════════════════════════\n"
    "• Чётко, ясно, структурировано.\n"
    "• Никаких фраз вроде «я думаю» или «возможно».\n"
    "• Аналитично, уверенно, профессионально.\n"
    "• Никаких общих рассуждений: только конкретика.\n\n"
    "═══════════════════════════════════════════════════════════════\n"
    "СТРУКТУРА CONFLUENCE-ДОКУМЕНТА\n"
    "═══════════════════════════════════════════════════════════════\n"
    "1. **Заголовок**\n"
    "2. **Цель проекта**\n"
    "3. **Описание задачи**\n"
    "4. **Scope: входит / не входит**\n"
    "5. **Бизнес-требования**\n"
    "6. **Функциональные требования**\n"
    "7. **KPI и метрики успеха**\n"
    "8. **User Stories** (формат: «Как <роль>, я хочу <действие>, чтобы <ценность>»)\n"
    "9. **Use Case** (Актеры, Предусловия, Постусловия, Основной поток, Альтернативный поток)\n"
    "10. **Диаграмма процесса** (в формате Mermaid)\n\n"
    "═══════════════════════════════════════════════════════════════\n"
    "ФОРМАТ ОТВЕТА (строго валидный JSON)\n"
    "═══════════════════════════════════════════════════════════════\n"
    "```json\n"
    "{\n"
    "  \"corrections\": [\n"
    "    {\n"
    "      \"type\": \"typo|logic|arithmetic|requirement\",\n"
    "      \"original\": \"исходный фрагмент\",\n"
    "      \"corrected\": \"исправленный фрагмент\",\n"
    "      \"explanation\": \"пояснение\"\n"
    "    }\n"
    "  ],\n"
    "  \"delta\": {\n"
    "    \"title\": \"заголовок документа\",\n"
    "    \"goal\": \"цель проекта\",\n"
    "    \"description\": \"описание задачи\",\n"
    "    \"scope_in\": \"что входит в scope\",\n"
    "    \"scope_out\": \"что не входит в scope\",\n"
    "    \"business_requirements\": [\"бизнес-требования\"],\n"
    "    \"functional_requirements\": [\"функциональные требования\"],\n"
    "    \"kpi\": [\"KPI и метрики успеха\"],\n"
    "    \"user_stories\": [\"Как <роль>, я хочу <действие>, чтобы <ценность>\"],\n"
    "    \"use_cases\": [{\n"
    "      \"name\": \"название\",\n"
    "      \"actors\": [\"актеры\"],\n"
    "      \"preconditions\": \"предусловия\",\n"
    "      \"postconditions\": \"постусловия\",\n"
    "      \"main_flow\": [\"шаги\"],\n"
    "      \"alternative_flow\": [\"альтернативы\"]\n"
    "    }],\n"
    "    \"process_diagram\": \"mermaid-код диаграммы\"\n"
    "  },\n"
    "  \"validation\": {\n"
    "    \"is_valid\": true,\n"
    "    \"issues\": []\n"
    "  },\n"
    "  \"reply\": \"Ответ пользователю: готовый документ ИЛИ один уточняющий вопрос\"\n"
    "}\n"
    "```\n\n"
    "ПРАВИЛА:\n"
    "• corrections — массив исправлений; если ошибок нет, пустой массив [].\n"
    "• delta — только заполненные слоты; пустые не включать.\n"
    "• reply — готовый Confluence-документ в Markdown ИЛИ один короткий вопрос.\n\n"
    "ЗАВЕРШЕНИЕ:\n"
    "Цель твоей работы — получать любую формулировку задачи от сотрудника → "
    "превращать её в полный, качественный, формализованный Confluence-документ "
    "уровня Senior BA, с минимумом уточнений и максимумом точности.\n"
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
        
        # Log corrections if any
        corrections = data.get("corrections", [])
        for corr in corrections:
            corr_type = corr.get("type", "unknown")
            original = corr.get("original", "")
            corrected = corr.get("corrected", "")
            explanation = corr.get("explanation", "")
            logger.info(f"Correction [{corr_type}]: '{original}' -> '{corrected}' | {explanation}")
        
        # Log validation issues
        validation = data.get("validation", {})
        if not validation.get("is_valid", True):
            issues = validation.get("issues", [])
            for issue in issues:
                logger.warning(f"Validation issue: {issue}")

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
            f"Ты — Senior AI Business Analyst. На основе собранных данных сформируй полный Confluence-документ.\n"
            f"Данные: {json.dumps(slots, ensure_ascii=False)}\n"
            f"Заголовок: {title}\n\n"
            "СТРУКТУРА ДОКУМЕНТА:\n"
            "1. **Заголовок**\n"
            "2. **Цель проекта**\n"
            "3. **Описание задачи**\n"
            "4. **Scope: входит / не входит**\n"
            "5. **Бизнес-требования**\n"
            "6. **Функциональные требования**\n"
            "7. **KPI и метрики успеха**\n"
            "8. **User Stories** (формат: «Как <роль>, я хочу <действие>, чтобы <ценность>»)\n"
            "9. **Use Case** (Актеры, Предусловия, Постусловия, Основной поток, Альтернативный поток)\n"
            "10. **Диаграмма процесса** (в формате ```mermaid```)\n\n"
            "ТРЕБОВАНИЯ:\n"
            "• Используй Markdown с заголовками и списками.\n"
            "• Заполняй пробелы логически, используя опыт бизнес-аналитика.\n"
            "• Чётко, ясно, структурировано. Никаких «возможно» или «я думаю».\n"
            "• Документ должен быть готов к копированию в Confluence без правок.\n"
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
        
        # Check completeness - minimum required for a valid document
        required = ["goal", "description"]
        for k in required:
            val = merged.get(k)
            if not val:
                return False
        
        # At least some requirements should be present
        has_requirements = any([
            merged.get("business_requirements"),
            merged.get("functional_requirements"),
            merged.get("user_stories"),
            merged.get("use_cases")
        ])
        return has_requirements

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

