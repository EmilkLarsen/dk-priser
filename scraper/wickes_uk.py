"""Wickes.co.uk (GBP, UK) — product sitemaps sitemap-products-{1..N}.xml,
URLs end /p/<id>; clean schema.org Product ld+json with GBP price."""
import re
from common import get, sitemap_urls, ldjson_products, offer_from_ld, sane_price, valid_ean, first_str, write_jsonl, scrape_urls

BASE = "https://www.wickes.co.uk"
OUT = "data/latest/wickes_uk.jsonl"
PROD_RE = re.compile(r"/p/\d+$")


def fetch_url_list(limit=None):
    urls = []
    i = 1
    while True:
        try:
            xml = get(f"{BASE}/sitemap-products-{i}.xml")
        except Exception:
            break
        us = [u for u in sitemap_urls(xml) if PROD_RE.search(u)]
        urls.extend(us)
        i += 1
        if i > 30 or (limit and len(urls) >= limit):
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    rows = []
    for p in ldjson_products(html):
        off = offer_from_ld(p)
        if off:
            off["price"] = sane_price(off["price"])
        if not off or not off["price"]:
            continue
        sku = u.rstrip("/").rsplit("/", 1)[-1].lstrip("p-")
        rows.append({
            "chain": "wickes_uk",
            "country": "uk",
            "currency": off["currency"],
            "sku": sku,
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")),
            "name": p.get("name"),
            "url": u,
            "price": off["price"],
            "in_stock": off["in_stock"],
            "image": first_str(p.get("image")),
        })
        break
    return rows


def scrape(limit=None):
    return scrape_urls(fetch_url_list(limit), handle)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("wickes_uk: %d products -> %s" % (len(rows), OUT))
