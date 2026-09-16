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
            if e.code in (429, 503, 403):
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
    avail = str(off.get("availability") or "")
    in_stock = ("InStock" in avail) if avail else None  # absent = unknown
    return {
        "price": float(price),
        "currency": off.get("priceCurrency", "DKK"),
        "in_stock": in_stock,
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
    """Parallel scrape: handle(url, html) -> list of row dicts.
    Resume support: SCRAPE_OFFSET skips the first N urls (previous run died
    there); results then get APPENDED by the caller instead of overwriting."""
    off = int(os.environ.get("SCRAPE_OFFSET", "0"))
    slc = os.environ.get("SCRAPE_SLICE")
    if off:
        urls = urls[off:]
    if slc:
        urls = urls[:int(slc)]
    if off or slc:
        print(f"  slice: offset={off} max={slc or 'all'} -> {len(urls)} urls")
    def work(u):
        try:
            return handle(u, get(u)) or []
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    return pmap(work, urls)


def scrape_with_checkpoint(chain, urls, handle, limit=None):
    """For catalogs too large for one CI job to finish (Silvan ~41k URLs,
    XL-BYG ~35k+ across 7 sub-sitemaps, Stark 100k+ variant URLs, many dead)
    - every nightly run for these three has been getting killed by CI's own
    timeout partway through, every single day, since this project started.
    Plain scrape_urls()/pmap() can't survive that: results only exist in a
    Python list held in memory, and CI's timeout SIGKILLs the process with
    no chance to run any cleanup code, so 100% of an interrupted run's work
    was lost - the "resume" the workflow re-dispatches for restarts from
    URL #1 every time, re-scraping (and duplicating, since nothing
    de-duplicated on append) the same first few hundred URLs and never
    making net progress. This instead:

    1. Writes each URL's outcome to data/latest/.seen-<chain>.txt and each
       resulting row to data/latest/.checkpoint-<chain>.jsonl AS IT GOES
       (flushed per URL), not at the end - however far a run gets before
       being killed is durably on disk already.
    2. On the NEXT invocation (today's next continue-check retry, or
       literally the same cron slot tomorrow if the catalog is bigger than
       one day's realistic throughput at the deliberately polite request
       rate), reads that seen-set back and skips every URL already
       attempted - real forward progress instead of restarting.
    3. Returns the full CUMULATIVE checkpoint (de-duplicated by url/sku) -
       everything attempted across however many invocations it took so
       far, not just this one's slice - so the per-chain output file gets
       progressively MORE complete every time this runs, rather than an
       all-or-nothing wait for one invocation to somehow get through a
       100k-URL list. Once the full list is actually covered, the
       seen-set/checkpoint reset so tomorrow starts a clean pass against
       that day's re-fetched sitemap (real catalog changes still show up).

    Only engages when `limit` is falsy - an explicit smoke-test slice skips
    all of this and behaves exactly like plain scrape_urls, so a deliberate
    small test run can never be confused with (or pollute) real daily
    progress.
    """
    if limit:
        return scrape_urls(urls[:limit], handle)

    seen_path = f"data/latest/.seen-{chain}.txt"
    checkpoint_path = f"data/latest/.checkpoint-{chain}.jsonl"
    os.makedirs(os.path.dirname(seen_path), exist_ok=True)

    seen = set()
    if os.path.exists(seen_path):
        with open(seen_path, encoding="utf-8") as f:
            seen = {line.rstrip("\n") for line in f if line.strip()}

    remaining = [u for u in urls if u not in seen]
    if seen:
        print(f"  resume: {len(seen)} already attempted today, {len(remaining)} left of {len(urls)}")

    if remaining:
        def work(u):
            try:
                return u, (handle(u, get(u)) or [])
            except Exception as e:
                print(f"  ! {u}: {e}")
                return u, []

        with open(seen_path, "a", encoding="utf-8") as seen_f, \
                open(checkpoint_path, "a", encoding="utf-8") as ckpt_f:
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                for u, rows in ex.map(work, remaining):
                    seen_f.write(u + "\n")
                    seen_f.flush()
                    for row in rows:
                        ckpt_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    if rows:
                        ckpt_f.flush()
        with open(seen_path, encoding="utf-8") as f:
            seen = {line.rstrip("\n") for line in f if line.strip()}

    cumulative, dedup_keys = [], set()
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = row.get("url") or row.get("sku")
                if key in dedup_keys:
                    continue
                dedup_keys.add(key)
                cumulative.append(row)

    if len(seen) >= len(urls):
        print(f"  {chain}: full catalog covered today ({len(cumulative)} rows) - resetting checkpoint for tomorrow")
        for p in (seen_path, checkpoint_path):
            if os.path.exists(p):
                os.remove(p)
    else:
        print(f"  {chain}: {len(seen)}/{len(urls)} urls covered so far today, {len(cumulative)} rows checkpointed")

    return cumulative


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
