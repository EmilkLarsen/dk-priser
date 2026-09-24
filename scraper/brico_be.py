"""Brico/BricoPlanète (EUR, Belgium — fr + nl shops).

Product sitemaps: /fr/bricoproductpagessitemapindex<N>.xml and /nl/...
(5 indexes each, 50k URLs per file, verified 2026-09-24). Every URL in these
files is a real product page; product URLs end with /<sku>.

Product pages: JSON blob "price": 8.49 with adjacent "priceCurrency":"EUR"
(verified; no itemprop). og:image on cloudfront, title in <title>.
"""
import re
from common import get, sane_price, write_jsonl, scrape_urls

BASE = "https://www.brico.be"
OUT = "data/latest/brico_be.jsonl"


def fetch_url_list(limit=None):
    urls = []
    seen = set()
    for lang in ("fr", "nl"):
        for i in range(1, 7):
            try:
                xml = get(f"{BASE}/{lang}/bricoproductpagessitemapindex{i}.xml")
            except Exception:
                break
            for u in re.findall(r"<loc>([^<]+)</loc>", xml):
                u = u.strip()
                if u in seen or not re.search(r"/\d{5,9}/?$", u):
                    continue
                seen.add(u)
                urls.append(u)
            if limit and len(urls) >= limit:
                break
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    # price anchored to priceCurrency within a small window (the page's JSON
    # is compact; currency may sit up to ~120 chars after the price key)
    m = re.search(r'"price"\s*:\s*"?([0-9]+(?:[.,][0-9]{1,2})?)"?'
                  r'[^{}]{0,120}?"priceCurrency"\s*:\s*"(?:EUR|€)"', html)
    if not m and '"priceCurrency"' in html:
        # currency present but far away — take the first plain price key
        m = re.search(r'"price"\s*:\s*"?([0-9]+(?:[.,][0-9]{1,2})?)"?', html)
    if not m:
        return []
    p = sane_price(float(m.group(1).replace(",", ".")))
    if not p:
        return []
    skm = re.search(r"/(\d{5,9})/?$", u)
    img = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).strip() if t else u.rsplit("/", 1)[-1])
    ean = re.search(r'"gtin\d*"\s*:\s*"?(\d{8,14})"?', html)
    return [{
        "chain": "brico_be",
        "country": "be",
        "currency": "EUR",
        "sku": skm.group(1) if skm else None,
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
    print("brico_be: %d products -> %s" % (len(rows), OUT))
