from typing import Optional
import logging
import re
import base64
import requests
from io import BytesIO
from ..config import (
    CONFLUENCE_URL,
    CONFLUENCE_EMAIL,
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_SPACE_KEY,
    CONFLUENCE_PARENT_PAGE_ID,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)


def generate_diagram_image_with_gemini(description: str) -> Optional[bytes]:
    """Generate diagram image - try Gemini first, fallback to PIL-based generation."""

    # Берём ключ напрямую из config.py (захардкожен)
    api_key = GEMINI_API_KEY

    # Try Gemini first if API key is available
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            # Try different model names (updated for current API)
            for model_name in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"]:
                try:
                    model = genai.GenerativeModel(model_name)

                    prompt = f"""На основе описания проекта создай список ключевых шагов бизнес-процесса.

Описание проекта:
{description}

Требования:
- Верни 6-8 ключевых шагов процесса
- Каждый шаг на новой строке
- Формат: просто текст шага (без номеров, без символов)
- Логическая последовательность: от начала до конца
- Шаги должны быть конкретными и понятными
- На русском языке
- Включи: инициацию, анализ, разработку, внедрение, мониторинг

Пример формата ответа:
Инициация проекта
Анализ текущего состояния
Сбор требований
Разработка решения
Тестирование
Внедрение
Мониторинг результатов
Завершение проекта"""

                    response = model.generate_content(prompt)
                    steps_text = response.text.strip()

                    # Parse steps
                    steps = []
                    for line in steps_text.split("\n"):
                        line = line.strip()
                        # Remove numbering if present
                        line = re.sub(r"^\d+[\.\)]\s*", "", line)
                        line = re.sub(r"^[-*•]\s*", "", line)
                        line = re.sub(r"^\*\*.*?\*\*:?\s*", "", line)  # Remove **bold** prefixes
                        if line and 3 < len(line) < 80:
                            steps.append(line[:60])

                    if len(steps) >= 4:
                        logger.info(f"Gemini generated {len(steps)} steps using {model_name}")
                        return _generate_diagram_image(steps[:8], "Диаграмма бизнес-процесса")

                except Exception as e:
                    logger.warning(f"Model {model_name} failed: {e}")
                    continue

        except Exception as exc:
            logger.warning(f"Gemini generation failed: {exc}")

    # Fallback: Parse description and generate diagram
    logger.info("Using fallback diagram generation")
    return _generate_diagram_from_description(description)


def _generate_diagram_from_description(description: str) -> Optional[bytes]:
    """Generate diagram by parsing description."""
    try:
        steps = []

        # Extract key information from description
        lines = description.split("\n")

        # Look for use cases with main_flow
        for line in lines:
            line = line.strip()
            if "Use Case" in line and "->" in line:
                # Parse use case flow
                parts = line.split("->")
                for part in parts[:8]:
                    clean = part.strip().split(":")[-1].strip()
                    clean = re.sub(r"^\d+[\.\)]\s*", "", clean)
                    if clean and len(clean) > 3:
                        steps.append(clean[:60])

        # If no use cases, extract from other fields
        if not steps:
            for line in lines:
                line = line.strip()
                if line and not any(x in line for x in ["Проект:", "Цель:", "KPI:"]):
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            value = parts[1].strip()
                            if value and 5 < len(value) < 70:
                                steps.append(value)

        # Default steps if nothing extracted
        if not steps:
            steps = [
                "Инициация проекта",
                "Сбор и анализ требований",
                "Проектирование решения",
                "Разработка и тестирование",
                "Внедрение системы",
                "Обучение пользователей",
                "Мониторинг и оптимизация",
                "Завершение проекта",
            ]

        # Limit to 8 steps
        steps = steps[:8]

        logger.info(f"Extracted {len(steps)} steps from description")
        return _generate_diagram_image(steps, "Диаграмма бизнес-процесса")

    except Exception as exc:
        logger.error(f"Failed to parse description: {exc}")
        return None


def _generate_diagram_image(steps: list, title: str) -> Optional[bytes]:
    """Generate diagram image using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO

        # Calculate image height
        img_height = 100 + len(steps) * 85
        img = Image.new("RGB", (850, img_height), color="#f8fafc")
        draw = ImageDraw.Draw(img)

        def _ttf(paths, size):
            for p in paths:
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
            return None

        import os
        import platform
        sysname = platform.system().lower()
        win_fonts = [
            os.path.expandvars(r"%WINDIR%\Fonts\arial.ttf"),
            os.path.expandvars(r"%WINDIR%\Fonts\segoeui.ttf"),
            os.path.expandvars(r"%WINDIR%\Fonts\calibri.ttf"),
            os.path.expandvars(r"%WINDIR%\Fonts\times.ttf"),
        ]
        win_fonts_bold = [
            os.path.expandvars(r"%WINDIR%\Fonts\arialbd.ttf"),
            os.path.expandvars(r"%WINDIR%\Fonts\segoeuib.ttf"),
            os.path.expandvars(r"%WINDIR%\Fonts\calibrib.ttf"),
            os.path.expandvars(r"%WINDIR%\Fonts\timesbd.ttf"),
        ]
        nix_regular = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        ]
        nix_bold = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        ]
        reg_paths = win_fonts if "windows" in sysname else nix_regular
        bold_paths = win_fonts_bold if "windows" in sysname else nix_bold
        font = _ttf(reg_paths, 14) or ImageFont.load_default()
        title_font = _ttf(bold_paths, 18) or ImageFont.load_default()
        small_font = _ttf(reg_paths, 11) or ImageFont.load_default()

        # Draw header background
        draw.rectangle([0, 0, 850, 60], fill="#2563eb")
        draw.text((25, 18), title, fill="white", font=title_font)

        y_pos = 85
        x_center = 425

        for i, step_text in enumerate(steps):
            # Determine if this is a decision point
            is_decision = any(word in step_text.lower() for word in ["?", "решение", "выбор", "проверка"])

            # Draw box
            if is_decision:
                # Diamond shape for decisions
                box_width = 380
                box_height = 60
                points = [
                    (x_center, y_pos),  # top
                    (x_center + box_width // 2, y_pos + box_height // 2),  # right
                    (x_center, y_pos + box_height),  # bottom
                    (x_center - box_width // 2, y_pos + box_height // 2),  # left
                ]
                draw.polygon(points, fill="#fef3c7", outline="#f59e0b", width=3)
                text_y = y_pos + box_height // 2 - 8
                y2_actual = y_pos + box_height
                x1 = x_center - box_width // 2  # for consistency
            else:
                # Rectangle for regular steps
                box_width = 400
                box_height = 65
                x1 = x_center - box_width // 2
                y1 = y_pos
                x2 = x1 + box_width
                y2 = y1 + box_height

                # Gradient colors
                colors = ["#dbeafe", "#e0e7ff", "#e0f2fe", "#ddd6fe"]
                fill_color = colors[i % len(colors)]

                draw.rounded_rectangle(
                    [x1, y1, x2, y2], radius=8, fill=fill_color, outline="#2563eb", width=3
                )

                # Draw step number badge
                badge_x = x1 + 15
                badge_y = y1 + 12
                draw.ellipse([badge_x, badge_y, badge_x + 30, badge_y + 30], fill="#2563eb")
                step_num = str(i + 1)
                num_bbox = draw.textbbox((0, 0), step_num, font=title_font)
                num_width = num_bbox[2] - num_bbox[0]
                draw.text((badge_x + 15 - num_width // 2, badge_y + 5), step_num, fill="white", font=title_font)

                text_y = y1 + 22
                y2_actual = y2

            # Draw text - wrap if too long (упрощённо: просто режем по длине)
            text = step_text[:55]
            if not is_decision:
                text_x = x1 + 55
                draw.text((text_x, text_y), text, fill="#1e293b", font=font)
            else:
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_x = x_center - text_width // 2
                draw.text((text_x, text_y), text, fill="#92400e", font=font)

            # Draw arrow to next
            if i < len(steps) - 1:
                arrow_start_y = y2_actual + 3
                arrow_end_y = y2_actual + 17
                draw.line(
                    [(x_center, arrow_start_y), (x_center, arrow_end_y)],
                    fill="#2563eb",
                    width=4,
                )
                # Arrow head
                draw.polygon(
                    [
                        (x_center, arrow_end_y),
                        (x_center - 7, arrow_end_y - 12),
                        (x_center + 7, arrow_end_y - 12),
                    ],
                    fill="#2563eb",
                )

            y_pos += 85

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG", quality=95)
        logger.info(f"Diagram image generated successfully with {len(steps)} steps")
        return buffer.getvalue()

    except Exception as exc:
        logger.error(f"Failed to generate diagram image: {exc}")
        return None


def upload_attachment_to_confluence(page_id: str, filename: str, image_data: bytes) -> Optional[str]:
    """Upload an image attachment to a Confluence page."""
    if not (CONFLUENCE_URL and CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN):
        return None

    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/attachment"

    headers = {
        "X-Atlassian-Token": "nocheck",
    }

    files = {
        "file": (filename, BytesIO(image_data), "image/png"),
    }

    try:
        # Check if attachment exists
        check_url = f"{url}?filename={filename}"
        resp = requests.get(check_url, auth=auth, timeout=15)
        resp.raise_for_status()
        existing = resp.json().get("results", [])

        if existing:
            # Update existing attachment
            att_id = existing[0]["id"]
            update_url = (
                f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/attachment/{att_id}/data"
            )
            resp = requests.post(update_url, files=files, auth=auth, headers=headers, timeout=30)
        else:
            # Create new attachment
            resp = requests.post(url, files=files, auth=auth, headers=headers, timeout=30)

        resp.raise_for_status()
        logger.info("Uploaded attachment '%s' to page %s", filename, page_id)
        return filename

    except Exception as exc:
        logger.error("Failed to upload attachment: %s", exc)
        return None


def extract_mermaid_from_html(html: str) -> Optional[str]:
    """Extract Mermaid code from HTML."""
    # Pattern to find <pre><code class="language-mermaid">...</code></pre>
    pattern = r'<pre><code class="language-mermaid">([\s\S]*?)</code></pre>'
    match = re.search(pattern, html)
    if match:
        code = match.group(1)
        code = (
            code.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
        )
        return code

    # Also try raw ```mermaid blocks
    raw_pattern = r"```mermaid\s*([\s\S]*?)```"
    match = re.search(raw_pattern, html)
    if match:
        return match.group(1).strip()

    return None


def replace_mermaid_with_image(html: str, image_filename: str) -> str:
    """Replace Mermaid code block with image reference in HTML."""
    # Replace <pre><code class="language-mermaid">...</code></pre>
    pattern = r'<pre><code class="language-mermaid">[\s\S]*?</code></pre>'
    replacement = (
        f'<ac:image ac:align="center" ac:layout="center">'
        f'<ri:attachment ri:filename="{image_filename}"/></ac:image>'
    )
    html = re.sub(pattern, replacement, html)

    # Also replace raw ```mermaid blocks
    raw_pattern = r"```mermaid[\s\S]*?```"
    html = re.sub(raw_pattern, replacement, html)

    return html


def publish_to_confluence(title: str, html: str) -> Optional[str]:
    """Создать новую страницу в Confluence (без обновления существующей)."""
    if not (CONFLUENCE_URL and CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN and CONFLUENCE_SPACE_KEY):
        logger.info("Confluence credentials are not configured; skipping publish.")
        return None

    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    headers = {"Content-Type": "application/json"}

    # Extract Mermaid code for diagram generation
    mermaid_code = extract_mermaid_from_html(html)
    diagram_image = None

    if mermaid_code:
        logger.info("Found Mermaid diagram, generating image with Gemini...")
        diagram_image = generate_diagram_image_with_gemini(mermaid_code)

    # First create the page (no search), include ancestors only on create
    html_to_publish = html
    if diagram_image:
        html_to_publish = replace_mermaid_with_image(html, "process_diagram.png")

    payload = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE_KEY},
        "body": {"storage": {"value": html_to_publish, "representation": "storage"}},
    }

    if CONFLUENCE_PARENT_PAGE_ID:
        payload["ancestors"] = [{"id": int(CONFLUENCE_PARENT_PAGE_ID)}]

    try:
        url = f"{CONFLUENCE_URL}/rest/api/content"
        resp = requests.post(url, json=payload, auth=auth, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info("Created Confluence page '%s'.", title)
        js = resp.json()

        page_id = js.get("id")

        # Upload diagram image as attachment
        if diagram_image and page_id:
            upload_attachment_to_confluence(page_id, "process_diagram.png", diagram_image)

    except Exception as exc:
        logger.error("Confluence publish failed: %s", exc)
        if hasattr(exc, "response") and exc.response is not None:
            logger.error("Response: %s", exc.response.text)
        return None

    link = js.get("_links", {}).get("webui")
    if link and CONFLUENCE_URL:
        return f"{CONFLUENCE_URL}{link}"
    return None


def publish_to_confluence_with_diagram(
    title: str, html: str, diagram_image: Optional[bytes] = None
) -> Optional[str]:
    """Publish to Confluence with a pre-generated diagram image (create or update)."""
    if not (CONFLUENCE_URL and CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN and CONFLUENCE_SPACE_KEY):
        logger.info("Confluence credentials are not configured; skipping publish.")
        return None

    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    headers = {"Content-Type": "application/json"}
    search_url = f"{CONFLUENCE_URL}/rest/api/content"
    params = {
        "title": title,
        "spaceKey": CONFLUENCE_SPACE_KEY,
        "expand": "version",
    }

    try:
        resp = requests.get(search_url, params=params, auth=auth, headers=headers, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as exc:
        logger.error("Confluence search failed: %s", exc)
        return None

    # Если есть диаграмма — добавляем секцию с изображением в конец страницы
    html_to_publish = html
    if diagram_image:
        diagram_section = """
<h2>Диаграмма бизнес-процесса</h2>
<ac:image ac:align="center" ac:layout="center" ac:width="800">
    <ri:attachment ri:filename="process_diagram.png"/>
</ac:image>
"""
        html_to_publish = html + diagram_section

    is_update = bool(results)

    data = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE_KEY},
        "body": {"storage": {"value": html_to_publish, "representation": "storage"}},
    }

    # ВАЖНО: ancestors только при СОЗДАНИИ, при обновлении не трогаем родителя
    if CONFLUENCE_PARENT_PAGE_ID and not is_update:
        data["ancestors"] = [{"id": int(CONFLUENCE_PARENT_PAGE_ID)}]

    try:
        if is_update:
            page = results[0]
            page_id = page["id"]
            version = page.get("version", {}).get("number", 1) + 1
            data["version"] = {"number": version}

            url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"
            resp = requests.put(url, json=data, auth=auth, headers=headers, timeout=15)
            resp.raise_for_status()
            logger.info("Updated Confluence page '%s' (v%s).", title, version)
            js = resp.json()
        else:
            url = f"{CONFLUENCE_URL}/rest/api/content"
            resp = requests.post(url, json=data, auth=auth, headers=headers, timeout=15)
            resp.raise_for_status()
            logger.info("Created Confluence page '%s'.", title)
            js = resp.json()
            page_id = js.get("id")

        page_id = js.get("id")

        # Upload diagram image as attachment
        if diagram_image and page_id:
            upload_attachment_to_confluence(page_id, "process_diagram.png", diagram_image)
            logger.info("Uploaded diagram to Confluence page %s", page_id)

    except Exception as exc:
        logger.error("Confluence publish failed: %s", exc)
        if hasattr(exc, "response") and exc.response is not None:
            logger.error("Response: %s", exc.response.text)
        return None

    link = js.get("_links", {}).get("webui")
    if link and CONFLUENCE_URL:
        return f"{CONFLUENCE_URL}{link}"
    return None
