"""Skousen.dk — premium appliances (kitchen, laundry, HVAC).
sitemap-skou-products.xml -> /product/ pages -> ld+json price."""
from common import get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl

BASE = "https://www.skousen.dk"
OUT = "data/latest/skousen.jsonl"


def fetch_url_list(limit):
    urls = sitemap_urls(get(f"{BASE}/seo/sitemap-skou-products.xml"))
    urls = [u for u in urls if "/product/" in u]
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
                "chain": "skousen",
                "sku": None,
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
    print(f"skousen: {len(rows)} products -> {OUT}")
