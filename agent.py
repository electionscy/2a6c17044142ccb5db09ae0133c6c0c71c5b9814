import os, yaml, sys
from slugify import slugify
from connectors import rss_connector, scraper
from processors.normalize import extract_clean_html
from processors.summarizer import to_json_article
from publisher.wordpress import publish
from state import db
from classifiers.politics import is_election_related

CONFIG_PATHS = ["config/feeds.yaml", "feeds.yaml"]

def load_config():
    for p in CONFIG_PATHS:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if isinstance(cfg, dict) and "sources" in cfg:
                entries = [(s.get("id") or f"src_{i}", s) for i, s in enumerate(cfg["sources"])]
            elif isinstance(cfg, dict):
                entries = list(cfg.items())
            elif isinstance(cfg, list):
                entries = [(s.get("id") or f"src_{i}", s) for i, s in enumerate(cfg)]
            else:
                raise ValueError("Μη έγκυρο σχήμα feeds.yaml")
            return entries
    raise FileNotFoundError("Δεν βρέθηκε ούτε config/feeds.yaml ούτε feeds.yaml")

def run_once():
    db.ensure()
    sources = load_config()
    for name, feed in sources:
        ftype = feed.get('type', 'rss')
        try:
            if ftype == 'rss':
                items = rss_connector.fetch(name, feed['url'])
                for it in items:
                    if db.seen(it.url):
                        continue
                    raw_title, raw_html = extract_clean_html(it.url)
                    ok, labels = is_election_related(raw_title + "\n" + raw_html, it.url)
                    if not ok:
                        continue
                    art = to_json_article(name, it.url, raw_html, raw_title, it.published.isoformat() if it.published else None)
                    if art.get("reject"):
                        continue
                    art['slug'] = slugify(art['title'])
                    art.setdefault('category', feed.get('category','news'))
                    art.setdefault('tags', list(set(feed.get('tags', []) + labels)))
                    post_id = publish(art)
                    if post_id != -1:
                        db.mark(name, it.url)
                        print(f"Published {post_id}: {art['title']}")
            elif ftype == 'scrape':
                links = scraper.list_links(
                    list_url = feed['url'],
                    item_selector = feed.get('item_selector', "a[href]"),
                    title_selector = feed.get('title_selector'),
                    allow_path_regex = feed.get('allow_path_regex'),
                    required_keywords_any = feed.get('required_keywords_any'),
                    negative_keywords_any = feed.get('negative_keywords_any'),
                )
                for href, ttl in links[:30]:
                    if db.seen(href):
                        continue
                    raw_title, raw_html = extract_clean_html(href)
                    ok, labels = is_election_related((ttl or '') + "\n" + raw_html, href)
                    if not ok:
                        continue
                    art = to_json_article(name, href, raw_html, raw_title or ttl, None)
                    if art.get("reject"):
                        continue
                    art['slug'] = slugify(art['title'])
                    art.setdefault('category', feed.get('category','news'))
                    art.setdefault('tags', list(set(feed.get('tags', []) + labels)))
                    post_id = publish(art)
                    if post_id != -1:
                        db.mark(name, href)
                        print(f"Published {post_id}: {art['title']}")
        except Exception as e:
            print(f"[{name}] ERROR:", e, file=sys.stderr)

if __name__ == "__main__":
    run_once()
