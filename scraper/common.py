"""DK Byggepriser — nightly price snapshots from Danish building-supply chains.

10 chains, all public retail prices, no logins. Sources verified 2026-08-28.

Output:
  data/latest/<chain>.jsonl          full snapshot (overwritten each run)
  data/latest/prices.jsonl           merged all chains (what the API reads)
  data/history/<chain>/<date>.jsonl  only price CHANGES vs previous day
"""
import re
import os
import time
import random
import json
import gzip
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
TIMEOUT = 25
WORKERS = int(os.environ.get("SCRAPE_WORKERS", "12"))

_last_req = {}
import threading
_lock = threading.Lock()


def get(url, binary=False, max_bytes=40000000):
    """Polite GET: per-host throttle + jitter, realistic UA."""
    host = re.match(r"https?://([^/]+)", url).group(1)
    with _lock:
        now = time.time()
        wait = 1.0 + random.random() * 0.5 - (now - _last_req.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_req[host] = time.time()
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read(max_bytes)
            last_err = None
            break
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503):
                time.sleep(45 + random.random() * 30)  # WAF cooldown
            else:
                time.sleep(1.5 * (attempt + 1) + random.random())
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1) + random.random())
    if last_err is not None:
        raise last_err
    if url.endswith(".gz") and not binary:
        data = gzip.decompress(data)
    return data if binary else data.decode("utf-8", errors="replace")


def get_json(url):
    return json.loads(get(url))


def pmap(fn, items, workers=None):
    """Threaded map that preserves order and never raises."""
    rows = []
    with ThreadPoolExecutor(max_workers=workers or WORKERS) as ex:
        for r in ex.map(fn, items):
            rows.extend(r or [])
    return rows


def sitemap_urls(xml):
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


LD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _iter_products(obj):
    """Yield Product/ProductGroup dicts from parsed ld+json (incl @graph)."""
    if isinstance(obj, dict):
        if obj.get("@type") in ("Product", "ProductGroup"):
            yield obj
        for v in obj.values():
            yield from _iter_products(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_products(it)


def ldjson_products(html):
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


def scrape_urls(urls, handle):
    """Parallel scrape: handle(url, html) -> list of row dicts."""
    def work(u):
        try:
            return handle(u, get(u)) or []
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    return pmap(work, urls)


def write_jsonl(path, rows):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


MIN_PRICE, MAX_PRICE = 0.5, 250000.0  # DKK sanity bounds


def sane_price(p):
    """Reject zeros, negatives and absurd values that signal parse errors."""
    try:
        p = float(p)
    except (TypeError, ValueError):
        return None
    return p if MIN_PRICE <= p <= MAX_PRICE else None
