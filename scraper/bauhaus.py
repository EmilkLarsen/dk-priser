"""Bauhaus.dk — Magento sitemap -> product pages -> data-price-amount."""
import re
from common import get, sitemap_urls, write_jsonl

BASE = "https://www.bauhaus.dk"
OUT = "data/latest/bauhaus.jsonl"
PRICE_RE = re.compile(r'data-price-amount="([0-9.]+)"')
MD_PRICE_RE = re.compile(r'itemprop="price" content="([0-9.]+)"')
MD_SKU_RE = re.compile(r'itemprop="sku" content="([^"]+)"')
NAME_RE = re.compile(r'<title[^>]*>([^<]+)</title>')


# Bauhaus sitemap interleaves categories, blog posts and products with no
# order. These patterns separate product URLs (12/12 verified hit rate on
# itemprop microdata): dimension patterns (2400x520x18), specs (-4-w-,
# -2000-k-, 320-lm), unit tokens (3-stk, oe95cm) or Magento -p-<id>.
PRODUCT_PAT = re.compile(
    r"(\d+x\d+|-p-\d{4,}|-\d+-\d+-|-\d+-w-|-\d+-v-|-\d+-a-|-\d+-k-"
    r"|o\d+-\d+-cm-|\d+-stk|\d+-lm-|oe\d+cm|\d+,\d+-v)")


def _looks_like_product(u):
    return bool(PRODUCT_PAT.search(u))



OG_RE = re.compile(r'og:image"\s+content="([^"]+)"')  # newline between attrs

def fetch_url_list(limit=None):
    idx = get(f"{BASE}/media/sitemap_dk/sitemap.xml")
    files = sitemap_urls(idx)
    urls = []
    for f in files:
        us = [u for u in sitemap_urls(get(f))
              if u != BASE + "/" and _looks_like_product(u)]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    # itemprop microdata is emitted once per page = the MAIN product.
    # data-price-amount also matches related-product boxes -> fallback only.
    m = MD_PRICE_RE.search(html)
    if m:
        price = float(m.group(1))
    else:
        prices = PRICE_RE.findall(html)
        if not prices:
            return []
        price = float(prices[0])
    if not (0.5 <= price <= 250000):
        return []
    sk = MD_SKU_RE.search(html)
    t = NAME_RE.search(html)
    title = t.group(1).strip() if t else ""
    # category pages repeat a featured product's microdata; their titles
    # look like "X - Køb produkter til X hos BAUHAUS" -> skip them
    if "hos BAUHAUS" in title or "Køb produkter" in title:
        return []
    if not sk:
        return []  # real product pages always carry itemprop sku
    og = OG_RE.search(html)
    return [{
        "chain": "bauhaus",
        "image": og.group(1) if og else None,
        "sku": sk.group(1) if sk else None,
        "ean": None,
        "name": title.split("|")[0] or u.rsplit("/", 1)[-1],
        "url": u,
        "price": price,
        "in_stock": None,
    }]


def scrape(limit=None):
    from common import pmap

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
    print("bauhaus: %d products -> %s" % (len(rows), OUT))
