# processors/normalize.py — έκδοση χωρίς readability-lxml
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

COMMON_CONTENT_SELECTORS = [
    "article",                     # καθαρό article container
    "main article",
    "main .post-content", "main .entry-content", "main .article-content",
    ".post-content", ".entry-content", ".article-content",
    "#content article", "#content .entry-content",
]

TITLE_SELECTORS = [
    "h1.entry-title", "article h1", "h1.post-title", "h1.title", "h1"
]

def _first(sel_list, soup):
    for css in sel_list:
        node = soup.select_one(css)
        if node and node.get_text(strip=True):
            return node
    return None

def extract_clean_html(url: str) -> tuple[str, str]:
    r = httpx.get(url, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # τίτλος
    title_node = _first(TITLE_SELECTORS, soup) or soup.find("title")
    title = title_node.get_text(strip=True) if title_node else ""

    # βασικό περιεχόμενο
    content = _first(COMMON_CONTENT_SELECTORS, soup) or soup.body or soup
    # καθάρισε scripts/styles/iframes
    for tag in content.find_all(["script","style","iframe","noscript"]):
        tag.decompose()

    # φτιάξε absolute URLs για εικόνες/links
    for img in content.find_all("img"):
        src = img.get("src")
        if src:
            img["src"] = urljoin(url, src)
    for a in content.find_all("a"):
        href = a.get("href")
        if href:
            a["href"] = urljoin(url, href)

    html = str(content)
    return title, html
