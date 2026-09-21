"""Bauhaus.se (SEK) — same Vaimo Magento stack as bauhaus.dk; sitemap index
/media/sitemap/sitemap-{1..N}-*.xml; product pages carry itemprop microdata
(exactly one per page) + itemprop sku. Category pages filtered by title."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl, pmap

BASE = "https://www.bauhaus.se"
OUT = "data/latest/bauhaus_se.jsonl"
MD_PRICE_RE = re.compile(r'itemprop="price" content="([0-9.]+)"')
MD_SKU_RE = re.compile(r'itemprop="sku" content="([^"]+)"')
OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')
NAME_RE = re.compile(r"<title[^>]*>([^<]+)</title>")


# same product-shape filter proven on bauhaus.dk: dimensions/specs/unit tokens
PRODUCT_PAT = re.compile(
    r"(\d+x\d+|-p-\d{4,}|-\d+-\d+-|-\d+-w-|-\d+-v-|-\d+-a-|-\d+-k-"
    r"|o\d+-\d+-cm-|\d+-stk|\d+-lm-|oe\d+cm|\d+,\d+-v|\d+-mm|\d+-cm)")


def fetch_url_list(limit=None):
    idx = get(f"{BASE}/media/sitemap/sitemap.xml")
    files = sitemap_urls(idx)
    urls = []
    for f in files:
        us = [u for u in sitemap_urls(get(f))
              if u != BASE + "/" and "catalog/category" not in u
              and PRODUCT_PAT.search(u)]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = MD_PRICE_RE.search(html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    sk = MD_SKU_RE.search(html)
    t = NAME_RE.search(html)
    title = t.group(1).strip() if t else ""
    if "hos BAUHAUS" in title or "Köp produkter" in title:
        return []
    if not sk:
        return []
    og = OG_RE.search(html)
    return [{
        "chain": "bauhaus_se",
        "country": "se",
        "currency": "SEK",
        "sku": sk.group(1),
        "ean": None,
        "name": title.split("|")[0] or u.rsplit("/", 1)[-1],
        "url": u,
        "price": p,
        "in_stock": None,
        "image": og.group(1) if og else None,
    }]


def scrape(limit=None):
    def work(u):
        try:
            return handle(u, get(u))
        except Exception:
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("bauhaus_se: %d products -> %s" % (len(rows), OUT))
