import re
from jinja2 import Template
from .session_logic import SessionContext

BRD_TEMPLATE = Template(
    """
    # {{ title }}

    ## 1. Цель
    {{ goal or 'TBD' }}

    ## 2. Контекст и описание
    {{ description or 'TBD' }}

    ## 3. Scope
    **Входит**
    {% if scope_in_list %}{% for item in scope_in_list %}- {{ item }}
    {% endfor %}{% else %}- TBD{% endif %}

    **Не входит**
    {% if scope_out_list %}{% for item in scope_out_list %}- {{ item }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 4. Бизнес-правила
    {% if rules %}{% for r in rules %}- {{ r }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 5. Ограничения
    {% if constraints %}{% for c in constraints %}- {{ c }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 6. Приоритеты
    {% if priorities %}{% for p in priorities %}- {{ p }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 7. KPI
    {% if kpi %}{% for k in kpi %}- {{ k }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 8. Use Case
    **Основной сценарий**
    {% if use_cases %}{% for u in use_cases %}{{ loop.index }}. {{ u }}
    {% endfor %}{% else %}1. TBD{% endif %}

    **Альтернативы**
    {% if alt_flows %}{% for alt in alt_flows %}- {{ alt }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 9. User Stories
    {% if user_stories %}{% for story in user_stories %}{{ loop.index }}. {{ story }}
    {% endfor %}{% else %}1. TBD{% endif %}

    ## 10. Leading Indicators
    {% if leading_indicators %}{% for li in leading_indicators %}- {{ li }}
    {% endfor %}{% else %}- TBD{% endif %}

    ## 11. Диаграмма процесса (Mermaid)
    ```mermaid
    {{ mermaid }}
    ```
    """
)


def generate_brd_markdown(ctx: SessionContext, title: str) -> str:
    data = ctx.slots.copy()
    data["title"] = title
    data["scope_in_list"] = _normalize_multiline(data.get("scope_in"))
    data["scope_out_list"] = _normalize_multiline(data.get("scope_out"))
    data["rules"] = data.get("rules") or []
    data["constraints"] = data.get("constraints") or []
    data["priorities"] = data.get("priorities") or []
    data["kpi"] = data.get("kpi") or []
    data["use_cases"] = data.get("use_cases") or default_use_cases(ctx)
    data["alt_flows"] = data.get("alternative_flows") or _deduce_alternatives(data["use_cases"])
    data["user_stories"] = data.get("user_stories") or default_user_stories(ctx)
    data["leading_indicators"] = data.get("leading_indicators") or default_leading_indicators(ctx)
    data["mermaid"] = data.get("process_diagram") or default_mermaid(ctx)
    md = BRD_TEMPLATE.render(**data)
    lines = [l.rstrip() for l in md.splitlines()]
    return "\n".join(lines)


def default_use_cases(ctx: SessionContext):
    g = ctx.slots.get("goal") or "ключевая цель"
    return [
        f"Заказчик описывает исходные данные, чтобы инициировать достижение цели «{g}».",
        "Система валидирует ответы и подсвечивает пробелы в требованиях.",
        "Бизнес-аналитик получает структурированный документ и согласует его со стейкхолдерами.",
    ]


def default_user_stories(ctx: SessionContext):
    g = ctx.slots.get("goal") or "заявленная цель"
    return [
        f"Как сотрудник банка, я хочу фиксировать ответы заказчика структурированно, чтобы ускорить согласование '{g}'.",
        f"Как product owner, я хочу видеть приоритеты и ограничения, чтобы планировать релизы по '{g}'.",
        f"Как риск-менеджер, я хочу видеть KPI и leading indicators, чтобы контролировать движение к '{g}'.",
    ]


def default_leading_indicators(ctx: SessionContext):
    kpis = ctx.slots.get("kpi") or []
    if kpis:
        return [f"Ранний сигнал достижения KPI «{kpis[0]}»: еженедельный тренд ≥ 80% от целевого значения."]
    return [
        "Скорость закрытия уточняющих вопросов ≤ 24 часов.",
        "Не менее 70% требований фиксируются за одну итерацию интервью.",
    ]


def default_mermaid(ctx: SessionContext):
    return (
        "flowchart LR\n"
        "subgraph Заказчик\n"
        "A[Старт интервью] --> B[Сбор ответов]\n"
        "end\n"
        "subgraph Система\n"
        "B --> C{Достаточно данных?}\n"
        "C -->|нет| D[Уточнить ошибки]\n"
        "C -->|да| E[Генерация артефактов]\n"
        "end\n"
        "subgraph Аналитик\n"
        "E --> F[Проверка качества]\n"
        "F --> G[Выдача BRD]\n"
        "end\n"
    )


def _normalize_multiline(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    parts = [seg.strip(" -•\t") for seg in re.split(r"[\n;]+", value) if seg.strip()]
    return parts


def _deduce_alternatives(use_cases):
    if not use_cases or len(use_cases) < 2:
        return ["Пользователь корректирует ответы, если система выявила неконсистентность."]
    return use_cases[1:]
