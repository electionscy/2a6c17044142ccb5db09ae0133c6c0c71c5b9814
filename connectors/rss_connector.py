import feedparser
from dataclasses import dataclass
from typing import Iterator
from datetime import datetime

@dataclass
class RawItem:
    source: str
    url: str
    title: str
    published: datetime | None

def fetch(source: str, url: str) -> Iterator[RawItem]:
    feed = feedparser.parse(url)
    for e in feed.entries:
        ts = None
        if getattr(e, 'published_parsed', None):
            ts = datetime(*e.published_parsed[:6])
        yield RawItem(source, e.link, getattr(e, 'title', ''), ts)
