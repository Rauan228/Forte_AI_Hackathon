import json
from typing import Dict, List, Optional

class SessionContext:
    def __init__(self, slots: Optional[Dict] = None, meta: Optional[Dict] = None):
        self.slots = slots or {
            "goal": None,
            "description": None,
            "scope_in": None,
            "scope_out": None,
            "rules": [],
            "kpi": [],
            "use_cases": [],
            "user_stories": [],
            "leading_indicators": [],
        }
        self.meta = meta or { k: {"confidence": 0.0, "updated": None} for k in self.slots.keys() }

    def is_complete(self) -> bool:
        required = ["goal", "description", "scope_in", "rules", "kpi"]
        for k in required:
            v = self.slots.get(k)
            if v is None:
                return False
            if isinstance(v, list) and len(v) == 0:
                return False
        return True

    def update(self, delta: Dict):
        for k, v in (delta or {}).items():
            if k in ["rules", "kpi", "use_cases", "user_stories", "leading_indicators"]:
                if v:
                    cur = self.slots.get(k) or []
                    if isinstance(v, list):
                        self.slots[k] = list({*cur, *v})
                    else:
                        if v not in cur:
                            cur.append(v)
                            self.slots[k] = cur
            else:
                if v:
                    self.slots[k] = v
            if k in self.meta:
                self.meta[k]["confidence"] = max(self.meta[k].get("confidence", 0.0), 0.7)

    def to_json(self) -> str:
        return json.dumps({"slots": self.slots, "meta": self.meta}, ensure_ascii=False)

    @staticmethod
    def from_json(s: Optional[str]):
        if not s:
            return SessionContext()
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "slots" in data:
                return SessionContext(slots=data.get("slots"), meta=data.get("meta"))
            return SessionContext(slots=data)
        except Exception:
            return SessionContext()

class SessionContextStore:
    def __init__(self, db_session):
        self.db = db_session

    def get(self, session_id: str) -> SessionContext:
        from ..models import SessionContextState
        row = self.db.query(SessionContextState).filter(SessionContextState.session_id == session_id).one_or_none()
        if not row:
            return SessionContext()
        return SessionContext.from_json(row.slots_json)

    def save(self, session_id: str, ctx: SessionContext):
        from ..models import SessionContextState
        row = self.db.query(SessionContextState).filter(SessionContextState.session_id == session_id).one_or_none()
        if not row:
            row = SessionContextState(session_id=session_id, slots_json=ctx.to_json())
            self.db.add(row)
        else:
            row.slots_json = ctx.to_json()
        self.db.commit()

def plan_next_question(ctx: SessionContext) -> str:
    if not ctx.slots.get("goal"):
        return "Какова главная бизнес-цель проекта? Опишите её измеримо."
    if not ctx.slots.get("description"):
        return "Опишите проблему/возможность: почему инициирован проект и какие боли решаем?"
    if not ctx.slots.get("scope_in"):
        return "Что входит в scope? Перечислите функциональные области и процессы."
    if len(ctx.slots.get("rules") or []) == 0:
        return "Перечислите ключевые бизнес-правила, ограничения и зависимости."
    if len(ctx.slots.get("kpi") or []) == 0:
        return "Назовите KPI с целевыми значениями и периодичностью измерения."
    if len(ctx.slots.get("use_cases") or []) == 0:
        return "Опишите основной Use Case: актор, предусловия, шаги основного сценария, альтернативы."
    if len(ctx.slots.get("user_stories") or []) < 3:
        return "Сформулируйте не менее 3 User Stories в формате: Как [роль] я хочу [действие], чтобы [ценность]."
    if len(ctx.slots.get("leading_indicators") or []) == 0:
        return "Назовите leading indicators — ранние признаки, что движение к цели успешно."
    return "Уточните детали, которые считаете важными для полноты документа."

def extract_slots_from_history(history: List[tuple]) -> Dict:
    slots = {}
    user_text = "\n".join([t for r, t in history if r == "user"]) or ""
    low = user_text.lower()
    def after(label: str):
        idx = low.find(label)
        if idx != -1:
            seg = user_text[idx:]
            parts = seg.split(":",1)
            if len(parts) == 2:
                return parts[1].strip()
        return None
    g = after("цель")
    if g:
        slots["goal"] = g
    d = after("описание") or after("проблема") or after("возможность")
    if d:
        slots["description"] = d
    if "scope" in low or "входит" in low or "не входит" in low:
        lines = [l.strip() for l in user_text.splitlines()]
        in_lines = [l for l in lines if ("входит" in l.lower())]
        out_lines = [l for l in lines if ("не входит" in l.lower())]
        if in_lines:
            slots["scope_in"] = "; ".join(in_lines)
        if out_lines:
            slots["scope_out"] = "; ".join(out_lines)
    rules = []
    kpi = []
    for l in user_text.splitlines():
        tl = l.strip().lower()
        if tl.startswith("-") or tl.startswith("•"):
            if "kpi" in tl or "показател" in tl:
                kpi.append(l.strip("-• "))
            else:
                rules.append(l.strip("-• "))
    if rules:
        slots["rules"] = rules
    if kpi:
        slots["kpi"] = kpi
    return slots
