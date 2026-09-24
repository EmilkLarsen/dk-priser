"""Hagebau.at (EUR, Austria) — direct product sitemap chunks.

sitemap.xml lists /sitemap/product/?index=N (13 chunks x 10k URLs, ~130k
products, verified 2026-09-24). Each <url> carries an optional image:loc,
collected into a url->image map by fetch_url_list and used by handle().

Product pages: JSON price blob ("price": 15.99) + gtin13 EAN (verified
2026-09-24; no itemprop markup, no og:image). Product URLs end in
.../p/<slug>-anP<id>/ — the anP<digits> token is the sku.
"""
import re
from common import get, sane_price, write_jsonl, scrape_urls

BASE = "https://www.hagebau.at"
OUT = "data/latest/hagebau_at.jsonl"

_IMAGES = {}   # url -> image (filled by fetch_url_list)
_URL_OK = re.compile(r"^https://www\.hagebau\.at/p/.+anP\d+/?$")
_SKU_RE = re.compile(r"anP(\d+)")


def _decode(body):
    if isinstance(body, bytes):
        if body[:2] == b"\x1f\x8b":
            import gzip
            body = gzip.decompress(body)
        body = body.decode("utf-8", errors="replace")
    return body


def fetch_url_list(limit=None):
    idx = _decode(get(f"{BASE}/sitemap.xml"))
    chunks = re.findall(r"<loc>([^<]+/sitemap/product/\?index=\d+)</loc>", idx)
    urls = []
    seen = set()
    for cp in chunks:
        try:
            xml = _decode(get(cp))
        except Exception:
            continue
        for m in re.finditer(
                r"<loc>(https://www\.hagebau\.at/p/[^<]+)</loc>"
                r"(?:.*?<image:loc>([^<]+)</image:loc>)?", xml, re.S):
            u, img = m.group(1), m.group(2)
            if not _URL_OK.match(u) or u in seen:
                continue
            seen.add(u)
            if img:
                _IMAGES[u] = img.strip()
            urls.append(u)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    # price: itemprop first (future-proof), then the JSON blob
    m = re.search(r'itemprop="price"\s+content="([0-9.]+)"', html)
    if not m:
        m = re.search(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    gt = re.search(r'"gtin\d*"\s*:\s*"?(\d{8,14})"?', html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).rsplit(" - ", 1)[0].strip() if t else u.rsplit("/", 1)[-1])
    sk = _SKU_RE.search(u)
    return [{
        "chain": "hagebau_at",
        "country": "at",
        "currency": "EUR",
        "sku": sk.group(1) if sk else None,
        "ean": gt.group(1) if gt else None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
        "image": _IMAGES.get(u),
    }]


def scrape(limit=None):
    return scrape_urls(fetch_url_list(limit), handle)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("hagebau_at: %d products -> %s" % (len(rows), OUT))
