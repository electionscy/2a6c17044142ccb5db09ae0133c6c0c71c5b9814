# connectors/scraper.py — έκδοση χωρίς Playwright
import re
import httpx
from bs4 import BeautifulSoup

def list_links(
    list_url: str,
    item_selector: str,
    title_selector: str | None = None,
    allow_path_regex: str | None = None,
    required_keywords_any: list[str] | None = None,
    negative_keywords_any: list[str] | None = None,
) -> list[tuple[str, str]]:
    allow_re = re.compile(allow_path_regex, re.I) if allow_path_regex else None
    req = [s.lower() for s in (required_keywords_any or [])]
    neg = [s.lower() for s in (negative_keywords_any or [])]

    r = httpx.get(list_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # CSS selection
    nodes = soup.select(item_selector)
    out: list[tuple[str, str]] = []

    for a in nodes:
        href = a.get("href")
        if not href:
            continue
        if allow_re and not allow_re.search(href):
            continue

        node = a.select_one(title_selector) if title_selector else a
        title = (node.get_text(strip=True) if node else a.get_text(strip=True)) or ""
        text_l = f"{title} {href}".lower()

        if req and not any(k in text_l for k in req):
            continue
        if neg and any(k in text_l for k in neg):
            continue

        out.append((href, title))

    # unique by href, keep order
    seen = set()
    uniq: list[tuple[str, str]] = []
    for h, t in out:
        if h in seen:
            continue
        seen.add(h)
        uniq.append((h, t))
    return uniq
