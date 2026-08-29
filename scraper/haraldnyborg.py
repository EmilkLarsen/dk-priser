"""Harald Nyborg — sitemap-products.xml -> ld+json price."""
from common import html_gtin, valid_ean, first_str, sane_price, get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl, scrape_urls

BASE = "https://www.harald-nyborg.dk"
OUT = "data/latest/haraldnyborg.jsonl"


def fetch_url_list(limit=None):
    urls = sitemap_urls(get(BASE + "/sitemap-products.xml"))
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
        rows.append({
            "chain": "haraldnyborg",
            "sku": None,
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")) or html_gtin(html),
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
    print("haraldnyborg: %d products -> %s" % (len(rows), OUT))
