import os, orjson, httpx

SYSTEM_PROMPT = None
if os.path.exists("PROMPT_SYSTEM_EL.txt"):
    SYSTEM_PROMPT = open("PROMPT_SYSTEM_EL.txt", encoding="utf-8").read()
else:
    SYSTEM_PROMPT = "Είσαι συντάκτης elections.cy· γράψε σύντομη ουδέτερη σύνοψη σε JSON."

def to_json_article(src_name: str, src_url: str, raw_html: str, raw_title: str, published_iso: str|None) -> dict:
    content = f"URL: {src_url}\nTITLE: {raw_title}\nHTML:\n{raw_html}"
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    payload = {
        "model": "gpt-4.1-mini",
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        "response_format": {"type": "json_object"}
    }
    r = httpx.post("https://api.openai.com/v1/responses", json=payload, timeout=120,
                   headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    r.raise_for_status()
    data = r.json()
    text = (
        data.get("output", [{}])[0].get("content", [{}])[0].get("text")
        or data.get("choices", [{}])[0].get("message", {}).get("content")
    )
    obj = orjson.loads(text)
    if obj.get("reject"):
        return obj
    obj.setdefault("source", {"name": src_name, "url": src_url, "published_at": published_iso or ""})
    return obj
