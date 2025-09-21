import os, httpx

BASE = os.getenv("WORDPRESS_BASE_URL", "").rstrip("/")
USER = os.getenv("WORDPRESS_USER")
APP_PWD = os.getenv("WORDPRESS_APP_PASSWORD")

sess = httpx.Client(auth=(USER, APP_PWD), headers={"Content-Type":"application/json"}, timeout=60)

def ensure_tag(name: str) -> int:
    r = sess.get(f"{BASE}/wp-json/wp/v2/tags", params={"search": name})
    r.raise_for_status()
    items = r.json()
    if items:
        return items[0]['id']
    r = sess.post(f"{BASE}/wp-json/wp/v2/tags", json={"name": name})
    r.raise_for_status()
    return r.json()['id']

def publish(article: dict) -> int:
    if article.get("reject"):
        return -1
    tags = [ensure_tag(t) for t in article.get("tags", [])]
    payload = {
        "title": article["title"],
        "status": "publish",
        "content": article["body_html"],
        "excerpt": article.get("excerpt",""),
        "tags": tags,
    }
    r = sess.post(f"{BASE}/wp-json/wp/v2/posts", json=payload)
    r.raise_for_status()
    return r.json()['id']
