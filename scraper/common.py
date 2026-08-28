"""Shared HTTP + parsing helpers for the DK byggepriser scrapers."""
import json
import re
import time
import urllib.request
import gzip
import io
import os
import random

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
TIMEOUT = 25

_last_req = {}


def get(url, binary=False, max_bytes=40000000):
    """Polite GET: per-host throttle (1.2s) + jitter, realistic UA."""
    host = re.match(r"https?://([^/]+)", url).group(1)
    now = time.time()
    prev = _last_req.get(host, 0)
    wait = 1.2 + random.random() * 0.8 - (now - prev)
    if wait > 0:
        time.sleep(wait)
    _last_req[host] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read(max_bytes)
    if url.endswith(".gz") and not binary:
        data = gzip.decompress(data)
    return data if binary else data.decode("utf-8", errors="replace")


def get_json(url: str):
    return json.loads(get(url))


def sitemap_urls(xml: str) :
    """Extract <loc> URLs from a sitemap (plain or index)."""
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


LD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _iter_products(obj):
    """Yield Product dicts from parsed ld+json, incl. nested @graph/lists."""
    if isinstance(obj, dict):
        if obj.get("@type") in ("Product", "ProductGroup"):
            yield obj
        for v in obj.values():
            yield from _iter_products(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_products(it)


def ldjson_products(html: str) -> list:
    out = []
    for m in LD_RE.findall(html):
        try:
            d = json.loads(m)
        except json.JSONDecodeError:
            continue
        out.extend(_iter_products(d))
    return out


def offer_from_ld(product):
    off = product.get("offers") or {}
    if isinstance(off, list):
        off = off[0] if off and isinstance(off[0], dict) else {}
    price = off.get("price")
    if price in (None, "", 0):
        return None
    return {
        "price": float(price),
        "currency": off.get("priceCurrency", "DKK"),
        "in_stock": "InStock" in str(off.get("availability", "")),
    }


def parse_dk_price(s):
    """'5.590,00' -> 5590.0 ; '49.95' -> 49.95 ; None if unparseable."""
    if not s:
        return None
    s = s.strip().replace("kr", "").replace(" ", "").replace("\xa0", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def unescape_html(s: str) -> str:
    return (s.replace("&quot;", '"').replace("&#248;", "ø")
             .replace("&aelig;", "æ").replace("&aring;", "å")
             .replace("&amp;", "&").replace("\\u0026", "&"))


def write_jsonl(path: str, rows: list[dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
