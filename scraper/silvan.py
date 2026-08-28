"""Silvan.dk — sitemap -> product pages -> schema.org ld+json price."""
import re
from common import valid_ean, first_str, sane_price, get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl, scrape_urls

BASE = "https://www.silvan.dk"
SITEMAP = BASE + "/sitemapvariantfeed.xml"
OUT = "data/latest/silvan.jsonl"



OG_RE = re.compile(r'<meta property="og:image" content="([^"]+)"')

def fetch_url_list(limit=None):
    urls = [u for u in sitemap_urls(get(SITEMAP)) if "/produkt/" in u]
    return urls[:limit] if limit else urls


def handle(u, html):
    rows = []
    og = OG_RE.search(html)
    img = og.group(1) if og else None
    for p in ldjson_products(html):
        off = offer_from_ld(p)
        if off:
            off["price"] = sane_price(off["price"])
        if not off or not off["price"]:
            continue
        if not off:
            continue
        rows.append({
            "chain": "silvan",
            "sku": str(p.get("sku") or u.rsplit("-", 1)[-1]),
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")),
            "image": first_str(p.get("image")),
            "name": p.get("name"),
            "url": u,
            "price": off["price"],
            "in_stock": off["in_stock"],
            "image": img,
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
    print("silvan: %d products -> %s" % (len(rows), OUT))
