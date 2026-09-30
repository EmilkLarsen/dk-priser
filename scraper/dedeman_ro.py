"""Dedeman.ro (RON, Romania's BIGGEST) — sitemap-products{0..N}.xml;
URLs /<slug>/p/<id>; Magento itemprop price + sku (no ld+json)."""
import re
from common import get, sitemap_urls, sane_price, valid_ean, write_jsonl, scrape_urls, scrape_with_checkpoint

BASE = "https://www.dedeman.ro"
OUT = "data/latest/dedeman_ro.jsonl"
PROD_RE = re.compile(r"/p/\d+$")
PRICE_RE = re.compile(r'itemprop="price" content="([0-9.]+)"')
SKU_RE = re.compile(r'itemprop="sku" content="([^"]+)"')
TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>")


def fetch_url_list(limit=None):
    urls = []
    i = 0
    while True:
        try:
            xml = get(f"{BASE}/media/sitemap/sitemap-products{i}.xml")
        except Exception:
            break
        us = [u for u in sitemap_urls(xml) if PROD_RE.search(u)]
        urls.extend(us)
        i += 1
        if i > 30 or (limit and len(urls) >= limit):
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = PRICE_RE.search(html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    sk = SKU_RE.search(html)
    t = TITLE_RE.search(html)
    name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 2)[-2])
    og = re.search(r'og:image"\s*content="([^"]+)"', html)
    image = og.group(1) if og else None
    return [{
        "chain": "dedeman_ro",
        "country": "ro",
        "currency": "RON",
        "sku": sk.group(1) if sk else None,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
        "image": image,
    }]


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("dedeman_ro", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("dedeman_ro: %d products -> %s" % (len(rows), OUT))
