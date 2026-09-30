"""Bauhaus.se (SEK) — same Vaimo Magento stack as bauhaus.dk; sitemap index
/media/sitemap/sitemap-{1..N}-*.xml; product pages carry itemprop microdata
(exactly one per page) + itemprop sku. Category pages filtered by title."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl, pmap, scrape_with_checkpoint

BASE = "https://www.bauhaus.sk"
OUT = "data/latest/bauhaus_sk.jsonl"
MD_PRICE_RE = re.compile(r'itemprop="price" content="([0-9.]+)"')
MD_SKU_RE = re.compile(r'itemprop="sku" content="([^"]+)"')
OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')
NAME_RE = re.compile(r"<title[^>]*>([^<]+)</title>")


# bauhaus.sk moved its sitemap (verified 2026-09-30): flat root /sitemap.xml with
# 50,000 <loc> entries — categories end in SMALL ids (zeleziarstvo-7347), products
# in LARGE ids (mako-stierka-na-lepidlo-21058657, 7-8 digits). Pages carry the same
# itemprop microdata as before (verified: itemprop="price" content="2.05").
PRODUCT_PAT = re.compile(r"-\d{7,}$")


def fetch_url_list(limit=None):
    xml = get(f"{BASE}/sitemap.xml")
    urls = [u.strip().rstrip("/") for u in re.findall(r"<loc>([^<]+)</loc>", xml)
            if u.strip().rstrip("/").count("/") == 3
            and PRODUCT_PAT.search(u)]
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
        "chain": "bauhaus_sk",
        "country": "sk",
        "currency": "EUR",
        "sku": sk.group(1),
        "ean": None,
        "name": title.split("|")[0] or u.rsplit("/", 1)[-1],
        "url": u,
        "price": p,
        "in_stock": None,
        "image": og.group(1) if og else None,
    }]


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("bauhaus_sk", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("bauhaus_se: %d products -> %s" % (len(rows), OUT))
