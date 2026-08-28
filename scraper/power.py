"""Power.dk — appliances/electronics. products-{1..N} sitemaps -> ld+json."""
from common import valid_ean, first_str, sane_price, get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl, scrape_urls

BASE = "https://www.power.dk"
OUT = "data/latest/power.jsonl"


def fetch_url_list(limit=None):
    idx = get(BASE + "/services/sitemap.xml")
    files = [u for u in sitemap_urls(idx) if "products-" in u]
    urls = []
    for f in files:
        urls.extend(sitemap_urls(get(f)))
        if limit and len(urls) >= limit:
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
        if not off:
            continue
        sku = u.rstrip("/").rsplit("-", 1)[-1].lstrip("p-")
        rows.append({
            "chain": "power",
            "sku": sku,
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")),
            "image": first_str(p.get("image")),
            "name": p.get("name"),
            "url": u,
            "price": off["price"],
            "in_stock": off["in_stock"],
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
    print("power: %d products -> %s" % (len(rows), OUT))
