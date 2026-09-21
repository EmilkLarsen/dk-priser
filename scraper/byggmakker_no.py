"""Byggmakker.no (NOK, Norway's largest pro+DIY chain) — product sitemaps
/sitemap/products{0..N}.xml; URLs /produkt/<slug>/<id>; price JSON blob:
{"price":959,"comparisonPriceUnit":"STK",...,"vatPercentage":25}."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl

BASE = "https://www.byggmakker.no"
OUT = "data/latest/byggmakker_no.jsonl"
PROD_RE = re.compile(r"/produkt/")
PRICE_RE = re.compile(r'"price":([0-9.]+),"basePriceUnit"')
UNIT_RE = re.compile(r'"comparisonPriceUnit":"(\w+)"')
NAME_RE = re.compile(r"<title[^>]*>([^<]+)</title>")


def fetch_url_list(limit=None):
    urls = []
    i = 0
    while True:
        try:
            xml = get(f"{BASE}/sitemap/products{i}.xml")
        except Exception:
            break
        us = [u for u in sitemap_urls(xml) if PROD_RE.search(u)]
        urls.extend(us)
        i += 1
        if i > 40 or (limit and len(urls) >= limit):
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = PRICE_RE.search(html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    um = UNIT_RE.search(html)
    unit = um.group(1).lower() if um else None
    if unit in ("stk", "stykk"):
        unit = "stk"
    t = NAME_RE.search(html)
    name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 1)[-1])
    sku = u.rstrip("/").rsplit("/", 1)[-1]
    return [{
        "chain": "byggmakker_no",
        "country": "no",
        "currency": "NOK",
        "sku": sku,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "unit": unit,
        "in_stock": None,
        "image": None,
    }]


def scrape(limit=None):
    from common import pmap

    def work(u):
        try:
            return handle(u, get(u))
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("byggmakker_no: %d products -> %s" % (len(rows), OUT))
