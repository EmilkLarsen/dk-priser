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
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
TIMEOUT = 25
WORKERS = int(os.environ.get("SCRAPE_WORKERS", "24"))

_last_req = {}
_inflight = {}
import threading
_lock = threading.Lock()
# Per-host lane control: up to 3 concurrent connections, >=0.45s between
# request starts. ~2.2 req/s/host max — comparable to an active shopper,
# 3x faster than the old single-lane throttle (which made full-catalog
# runs exceed CI time limits).
MAX_LANES = int(os.environ.get("SCRAPE_LANES", "3"))
MIN_GAP = float(os.environ.get("SCRAPE_GAP", "0.45"))


def _throttle(host):
    while True:
        with _lock:
            now = time.time()
            if _inflight.get(host, 0) < MAX_LANES and \
                    now - _last_req.get(host, 0) >= MIN_GAP:
                _last_req[host] = now
                _inflight[host] = _inflight.get(host, 0) + 1
                return
        time.sleep(0.05)


def _release(host):
    with _lock:
        _inflight[host] = max(0, _inflight.get(host, 1) - 1)


def get(url, binary=False, max_bytes=40000000):
    """Polite GET: per-host lane throttle + jitter, realistic UA."""
    host = re.match(r"https?://([^/]+)", url).group(1)
    _throttle(host)
    try:
        return _get_inner(url, binary, max_bytes)
    finally:
        _release(host)


def _get_inner(url, binary, max_bytes):
    last_err = None
    data = None
    for attempt in range(3):
        try:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None  # manual redirect handling

            opener = urllib.request.build_opener(NoRedirect)
            cur = url
            for _ in range(5):
                req = urllib.request.Request(cur, headers={"User-Agent": UA, "Accept": "*/*"})
                try:
                    with opener.open(req, timeout=TIMEOUT) as r:
                        data = r.read(max_bytes)
                    break
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                        cur = urllib.parse.urljoin(cur, e.headers["Location"])
                        continue
                    raise
            if data is None:
                raise RuntimeError("redirect loop: " + url)
            if urllib.parse.urlsplit(cur).path.rstrip("/") != urllib.parse.urlsplit(url).path.rstrip("/"):
                # a "product" URL that lands elsewhere = wrong product data
                raise ValueError(f"redirected: {url} -> {cur}")
            last_err = None
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise  # dead URL — retrying is pointless
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


def valid_ean(e):
    """GTIN-8/12/13/14 checksum validation — drops retailer junk GTINs.
    Weights run 3,1,3,1... from the rightmost DATA digit (check digit excluded)."""
    if e is None:
        return None
    s = str(e).strip()
    if not s.isdigit() or len(s) not in (8, 12, 13, 14):
        return None
    digits = [int(c) for c in s]
    check = digits.pop()
    total = sum(d * (3 if i % 2 == 0 else 1)
                for i, d in enumerate(reversed(digits)))
    return s if (10 - total % 10) % 10 == check else None


def first_str(v):
    """ld+json 'image' can be str, list or nested — normalize to first URL."""
    if isinstance(v, str):
        return v or None
    if isinstance(v, list):
        for it in v:
            if isinstance(it, str) and it:
                return it
            if isinstance(it, dict) and it.get('url'):
                return it['url']
    if isinstance(v, dict):
        return v.get('url')
    return None


HTML_GTIN_RE = re.compile(r'"(?:gtin(?:13)?|ean)"\s*:\s*"(\d{8,14})"')


def html_gtin(html):
    """Fallback: many chains embed gtin in a JSON state blob outside ld+json.
    Returns first checksum-valid GTIN on the page."""
    for m in HTML_GTIN_RE.finditer(html):
        v = valid_ean(m.group(1))
        if v:
            return v
    return None
