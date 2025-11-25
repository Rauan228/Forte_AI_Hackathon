from jinja2 import Template
from .session_logic import SessionContext

BRD_TEMPLATE = Template(
    """
    # {{ title }}

    **Цель:**
    {{ goal or 'TBD' }}

    **Описание проблемы/возможности:**
    {{ description or 'TBD' }}

    **Scope — входит:**
    {{ scope_in or 'TBD' }}

    **Scope — не входит:**
    {{ scope_out or 'TBD' }}

    **Бизнес-правила:**
    {% if rules %}{% for r in rules %}- {{ r }}
    {% endfor %}{% else %}- TBD{% endif %}

    **KPI:**
    {% if kpi %}{% for k in kpi %}- {{ k }}
    {% endfor %}{% else %}- TBD{% endif %}

    **Use Case:**
    {% if use_cases %}{% for u in use_cases %}- {{ u }}
    {% endfor %}{% else %}- TBD{% endif %}

    **User Stories:**
    {% if user_stories %}{% for s in user_stories %}- {{ s }}
    {% endfor %}{% else %}- TBD{% endif %}

    **Leading Indicators:**
    {% if leading_indicators %}{% for li in leading_indicators %}- {{ li }}
    {% endfor %}{% else %}- TBD{% endif %}
    """
)

def generate_brd_markdown(ctx: SessionContext, title: str) -> str:
    data = ctx.slots.copy()
    data["title"] = title
    md = BRD_TEMPLATE.render(**data)
    lines = [l.rstrip() for l in md.splitlines()]
    cleaned = []
    seen = set()
    for l in lines:
        key = l.strip().lower()
        if key in seen and key != "":
            continue
        seen.add(key)
        cleaned.append(l)
    return "\n".join(cleaned)

def default_use_cases(ctx: SessionContext):
    g = ctx.slots.get("goal") or ""
    return [f"Инициировать процесс: {g}" or "Инициировать ключевой процесс"]

def default_user_stories(ctx: SessionContext):
    g = ctx.slots.get("goal") or "Цель"
    return [
        f"Как сотрудник, я хочу видеть ключевые метрики, чтобы оценивать прогресс к '{g}'.",
        f"Как клиент, я хочу простой процесс, чтобы быстрее достигать '{g}'.",
        f"Как руководитель, я хочу сводку KPI, чтобы контролировать достижение '{g}'.",
    ]

def default_mermaid(ctx: SessionContext):
    return """flowchart TD\nA[Старт] --> B[Сбор требований]\nB --> C{Уточнения}\nC -->|Достаточно| D[Генерация документа]\nC -->|Недостаточно| B\nD --> E[Экспорт в Confluence]\nE --> F[Готово]\n"""
