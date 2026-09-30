"""Castorama.pl (PLN, Poland — Kingfisher market leader) — static product
sitemaps sitemap_products{1..3}.xml; URLs /<slug>/<id>_CAPL.prd; ld+json Product."""
import re
from common import get, sitemap_urls, sane_price, valid_ean, first_str, ldjson_products, offer_from_ld, write_jsonl, scrape_urls, scrape_with_checkpoint

BASE = "https://www.castorama.pl"
OUT = "data/latest/castorama_pl.jsonl"
PROD_RE = re.compile(r"\.prd$")


def fetch_url_list(limit=None):
    urls = []
    for i in (1, 2, 3):
        try:
            xml = get(f"{BASE}/static/sitemap_products{i}.xml")
        except Exception:
            break
        us = [u for u in sitemap_urls(xml) if PROD_RE.search(u)]
        urls.extend(us)
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
        m = re.search(r"/([0-9_]+)\.prd$", u)
        t = re.search(r"<title[^>]*>([^<]+)</title>", html)
        name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 1)[-1])
        rows.append({
            "chain": "castorama_pl",
            "country": "pl",
            "currency": off["currency"],
            "sku": m.group(1) if m else None,
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")),
            "name": name,
            "url": u,
            "price": off["price"],
            "in_stock": off["in_stock"],
            "image": first_str(p.get("image")),
        })
        break
    return rows


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("castorama_pl", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("castorama_pl: %d products -> %s" % (len(rows), OUT))
