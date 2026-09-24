"""Merkur.si (EUR, Slovenia) — batched sitemaps, root-slug product URLs.

media/sitemap/sitemap-1-1.xml .. sitemap-1-2.xml hold ~23k URLs; products are
root-level slugs like /karton-valoviti-450x350x380-mm-3-1/ (verified
2026-09-24), categories are short slugs with no digits. Discovery keeps only
digit-bearing slugs, and handle() drops anything without a real price.

Product pages: itemprop="price" content="9.99" + og:image (verified
2026-09-24). Currency EUR.
"""
import re
from common import get, sane_price, write_jsonl, scrape_urls

BASE = "https://www.merkur.si"
OUT = "data/latest/merkur_si.jsonl"


def fetch_url_list(limit=None):
    urls = []
    rest = []
    seen = set()
    for i in range(1, 40):   # sitemap-1-1 .. sitemap-1-39 (404 ends the loop)
        try:
            xml = get(f"{BASE}/media/sitemap/sitemap-1-{i}.xml")
        except Exception:
            break
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            u = u.strip()
            slug = u.rstrip("/").rsplit("/", 1)[-1] if u else ""
            # products carry digits (dimensions, model, pack counts);
            # categories ('aparati', 'vrtni-naradi') do not
            if not slug or not re.search(r"\d", slug) or u in seen:
                continue
            seen.add(u)
            # dimension slugs (450x350x380, 8x60) are products — front-load
            # them so smoke runs (small limit) hit real pages, not the
            # DIN-numbered category section at the head of each sitemap
            if re.search(r"\d+x\d+", slug):
                urls.append(u)
            else:
                rest.append(u)
        if limit and len(urls) >= limit:
            break
    all_urls = urls + rest
    return all_urls[:limit] if limit else all_urls


def handle(u, html):
    # product pages only — category/listing pages also carry prices in carousels
    if 'property="og:type" content="product"' not in html \
            and "og:type\" content=\"product\"" not in html:
        return []
    m = re.search(r'itemprop="price"\s+content="([0-9.]+)"', html)
    if not m:
        m = re.search(r'"price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    img = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 1)[-1])
    ean = re.search(r'"gtin\d*"\s*:\s*"?(\d{8,14})"?', html)
    return [{
        "chain": "merkur_si",
        "country": "si",
        "currency": "EUR",
        "sku": None,
        "ean": ean.group(1) if ean else None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
        "image": img.group(1).strip() if img else None,
    }]


def scrape(limit=None):
    return scrape_urls(fetch_url_list(limit), handle)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("merkur_si: %d products -> %s" % (len(rows), OUT))
