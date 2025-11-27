import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from app.ai.model import AIModel
from app.integrations.confluence import _generate_diagram_image

def test_fill_sections():
    ai = AIModel()
    slots = {
        "goal": "Сократить время обслуживания",
        "description": "Система сбора обратной связи клиентов банка",
        "scope_in": [
            "Сбор оценок и комментариев",
            "Формирование отчётов",
        ],
        "scope_out": [
            "Изменения в процессах отделений",
        ],
        "kpi": [
            "Среднее время ожидания",
            "Средняя оценка клиента",
        ],
    }
    md = (
        "# Бизнес-требования\n\n"
        "## 1. Цель проекта\n—\n\n"
        "## 2. Описание задачи\n—\n\n"
        "## 3. Scope: входит / не входит\n\n**Входит**\n—\n\n**Не входит**\n—\n\n"
        "## 7. KPI и метрики успеха\n—\n\n"
        "## 8. Сценарии использования (Use Case)\n**Основной сценарий**\n—\n\n**Альтернативы**\n—\n\n"
        "## 9. Пользовательские истории (User Stories)\n—\n\n"
        "## 10. Leading Indicators\n—\n"
    )
    out = ai._fill_missing_sections(md, slots, "Бизнес-требования")
    print("=== Filled Markdown ===")
    print(out)

def test_diagram_image():
    steps = [
        "Инициация проекта",
        "Сбор и анализ требований",
        "Проектирование решения",
        "Разработка и тестирование",
    ]
    img = _generate_diagram_image(steps, "Диаграмма бизнес-процесса")
    print("=== Diagram Bytes ===")
    print(len(img) if img else None)

if __name__ == "__main__":
    test_fill_sections()
    try:
        test_diagram_image()
    except Exception as e:
        print("Diagram generation error:", e)
