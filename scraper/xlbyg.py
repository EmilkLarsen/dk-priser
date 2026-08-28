"""XL-BYG.dk — product sitemaps (b2c-1..N) -> product pages -> ld+json price."""
import re
from common import get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl

BASE = "https://www.xl-byg.dk"
OUT = "data/latest/xlbyg.jsonl"


def fetch_url_list(limit):
    idx = get(BASE + "/sitemap.xml")
    files = sitemap_urls(idx)
    urls = []
    for f in files:
        if "product-sitemap" not in f:
            continue
        xml = get(f)
        us = [u for u in sitemap_urls(xml) if "/produkt/" in u]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def scrape(limit= None) :
    rows = []
    for u in fetch_url_list(limit):
        try:
            html = get(u)
        except Exception as e:
            print(f"  ! {u}: {e}")
            continue
        for p in ldjson_products(html):
            off = offer_from_ld(p)
            if not off:
                continue
            rows.append({
                "chain": "xlbyg",
                "sku": u.rsplit("-", 1)[-1],
                "ean": None,
                "name": p.get("name"),
                "url": u,
                "price": off["price"],
                "in_stock": off["in_stock"],
            })
            break
    return rows


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print(f"xlbyg: {len(rows)} products -> {OUT}")
