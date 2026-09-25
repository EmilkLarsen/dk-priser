"""Woodie's (EUR, Ireland — DIY chain, Grafton group; replaces the 403-blocked
Chadwicks trade site).

Batched sitemaps: /media/sitemap/sitemap-1-{1..N}.xml (verified 2026-09-25).
Chunk 1 is categories; later chunks are root-slug product URLs. Discovery
keeps single-segment URLs (products), drops /catalog/ system paths and
two-segment category paths; handle() requires an ld+json Offer, which filters
any stragglers.

Product pages: ld+json '"availability": "http://schema.org/OnlineOnly",
"price": 1069, "priceCurrency": "EUR"' (verified).
"""
import re
from common import get, sane_price, valid_ean, write_jsonl, scrape_urls

BASE = "https://www.woodies.ie"
OUT = "data/latest/woodies_ie.jsonl"


def fetch_url_list(limit=None):
    urls = []
    seen = set()
    for i in range(1, 60):   # chunks end with a 404
        try:
            xml = get(f"{BASE}/media/sitemap/sitemap-1-{i}.xml")
        except Exception:
            break
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            u = u.strip().rstrip("/")
            if u in seen or "/catalog/" in u or u == BASE:
                continue
            path = u[len(BASE):].lstrip("/")
            if not path or "/" in path:   # categories are 2+ segments
                continue
            seen.add(u)
            urls.append(u)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = re.search(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*"priceCurrency"\s*:\s*"EUR"', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    img = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    if t:
        name = t.group(1).split(" | ")[0].strip()
    else:
        name = u.rsplit("/", 1)[-1]
    ean = re.search(r'"gtin\d*"\s*:\s*"?(\d{8,14})"?', html)
    sk = re.search(r'"sku"\s*:\s*"([^"]+)"', html)
    return [{
        "chain": "woodies_ie",
        "country": "ie",
        "currency": "EUR",
        "sku": sk.group(1) if sk else None,
        "ean": ean.group(1) if ean else None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
        "image": img.group(1).strip() if img else None,
    }]


def scrape(limit=None):
    return scrape_urls(fetch_url_list(limit), handle)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("woodies_ie: %d products -> %s" % (len(rows), OUT))
