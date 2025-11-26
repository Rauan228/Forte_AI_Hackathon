from typing import Optional
import logging
import requests
from ..config import (
    CONFLUENCE_URL,
    CONFLUENCE_EMAIL,
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_SPACE_KEY,
    CONFLUENCE_PARENT_PAGE_ID,
)

logger = logging.getLogger(__name__)


def publish_to_confluence(title: str, html: str) -> Optional[str]:
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

    data = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE_KEY},
        "body": {"storage": {"value": html, "representation": "storage"}},
    }
    if CONFLUENCE_PARENT_PAGE_ID:
        data["ancestors"] = [{"id": int(CONFLUENCE_PARENT_PAGE_ID)}]

    try:
        if results:
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
    except Exception as exc:
        logger.error("Confluence publish failed: %s", exc)
        if hasattr(exc, "response") and exc.response is not None:
            logger.error("Response: %s", exc.response.text)
        return None

    link = js.get("_links", {}).get("webui")
    if link and CONFLUENCE_URL:
        return f"{CONFLUENCE_URL}{link}"
    return None

