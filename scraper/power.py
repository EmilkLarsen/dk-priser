"""Power.dk — appliances/electronics. sitemap products-{1..N} (5k each)
-> ld+json price."""
from common import get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl

BASE = "https://www.power.dk"
OUT = "data/latest/power.jsonl"


def fetch_url_list(limit):
    idx = get(f"{BASE}/services/sitemap.xml")
    files = [u for u in sitemap_urls(idx) if "products-" in u]
    urls = []
    for f in files:
        xml = get(f)
        urls.extend(sitemap_urls(xml))
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
            sku = u.rstrip("/").rsplit("-", 1)[-1].lstrip("p-")
            rows.append({
                "chain": "power",
                "sku": sku,
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
    print(f"power: {len(rows)} products -> {OUT}")
