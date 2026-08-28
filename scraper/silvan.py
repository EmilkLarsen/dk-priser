"""Silvan.dk — sitemap -> product pages -> schema.org ld+json price."""
import re
from common import get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl

BASE = "https://www.silvan.dk"
SITEMAP = BASE + "/sitemapvariantfeed.xml"
OUT = "data/latest/silvan.jsonl"


def fetch_url_list(limit):
    urls = sitemap_urls(get(SITEMAP))
    # product pages live under /produkt/
    urls = [u for u in urls if "/produkt/" in u]
    if limit:
        urls = urls[:limit]
    return urls


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
            sku = p.get("sku") or u.rsplit("-", 1)[-1]
            rows.append({
                "chain": "silvan",
                "sku": str(sku),
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
    print(f"silvan: {len(rows)} products -> {OUT}")
