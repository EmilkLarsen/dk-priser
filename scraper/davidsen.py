"""Davidsen.dk — Bizzkit commerce. Category pages embed full product JSON:
{"url":"/<slug>-p-<id>","name":"...", "priceInformation":{"price":{"value":"5.590,00"},...}}
We walk category pages (URLs ending -c-id<id>) and harvest products from
each — far fewer requests than per-product pages.
Category inventory: sitemap-1.xml / sitemap-2.xml (filter -c-id)."""
import re
import json
from common import get, sitemap_urls, parse_dk_price, write_jsonl

BASE = "https://www.davidsen.dk"
OUT = "data/latest/davidsen.jsonl"

CAT_RE = re.compile(r'/[a-z0-9-]+-c-id\d+"')
BLOCK_RE = re.compile(
    r'\{"id":"(\d+)","name":"([^"]+)","url":"(/[a-z0-9-]+-p-\d+)".{0,900}?'
    r'"price":\{"value":"([\d.,]+)"\}', re.S)


def fetch_category_list() :
    cats = set()
    for f in ("sitemap-1.xml", "sitemap-2.xml"):
        try:
            xml = get(f"{BASE}/{f}")
        except Exception:
            continue
        for u in sitemap_urls(xml):
            # pure category pages only (no -p- suffix; those are product pages)
            if "-c-id" in u and "-p-" not in u:
                cats.add(u)
    return sorted(cats)


def scrape(limit= None) :
    rows, seen = [], set()
    cats = fetch_category_list()
    if limit:
        cats = cats[:limit]
    for cu in cats:
        try:
            html = get(cu)
        except Exception as e:
            print(f"  ! {cu}: {e}")
            continue
        for m in BLOCK_RE.finditer(html):
            pid, name, url, price = m.groups()
            if url in seen:
                continue
            p = parse_dk_price(price)
            if not p:
                continue
            seen.add(url)
            rows.append({
                "chain": "davidsen",
                "sku": pid,
                "ean": None,
                "name": name,
                "url": BASE + url,
                "price": p,
                "in_stock": None,
            })
    return rows


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print(f"davidsen: {len(rows)} products -> {OUT}")
