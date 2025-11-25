from typing import Optional
import requests
from ..config import (
    CONFLUENCE_URL,
    CONFLUENCE_EMAIL,
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_SPACE_KEY,
    CONFLUENCE_PARENT_PAGE_ID,
)

def publish_to_confluence(title: str, html: str) -> Optional[str]:
    if not (CONFLUENCE_URL and CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN and CONFLUENCE_SPACE_KEY):
        return None
    url = f"{CONFLUENCE_URL}/rest/api/content"
    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
    data = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE_KEY},
        "body": {"storage": {"value": html, "representation": "storage"}},
    }
    if CONFLUENCE_PARENT_PAGE_ID:
        data["ancestors"] = [{"id": int(CONFLUENCE_PARENT_PAGE_ID)}]
    r = requests.post(url, json=data, auth=auth)
    r.raise_for_status()
    js = r.json()
    link = js.get("_links", {}).get("webui")
    if link and CONFLUENCE_URL:
        return f"{CONFLUENCE_URL}{link}"
    return None

