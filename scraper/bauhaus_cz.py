"""Bauhaus.cz (CZK, Czech Republic) — replaces the dead oba.cz splash site.

sitemap.xml (50k URLs) + sitemap-1.xml; product pages end in a 7-9 digit id
(e.g. -26078146) while categories carry 6-digit ids (-243812). Verified
2026-09-24: itemprop="price" content="1090.00" is the incl-VAT CZK price
(the JSON "price" key is ex-VAT — do not use), og:image present.
"""
import re
from common import get, sane_price, write_jsonl, scrape_urls

BASE = "https://www.bauhaus.cz"
OUT = "data/latest/bauhaus_cz.jsonl"


def fetch_url_list(limit=None):
    urls = []
    seen = set()
    for sm in ("sitemap.xml", "sitemap-1.xml"):
        try:
            xml = get(f"{BASE}/{sm}")
        except Exception:
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            u = u.strip()
            if u in seen or not re.search(r"-\d{7,9}$", u):
                continue
            seen.add(u)
            urls.append(u)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = re.search(r'itemprop="price"\s+content="([0-9.]+)"', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    img = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).rsplit(" | ", 1)[0].strip() if t else u.rsplit("/", 1)[-1])
    ean = re.search(r'"gtin\d*"\s*:\s*"?(\d{8,14})"?', html)
    skm = re.search(r"-(\d{7,9})$", u)
    return [{
        "chain": "bauhaus_cz",
        "country": "cz",
        "currency": "CZK",
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
    print("bauhaus_cz: %d products -> %s" % (len(rows), OUT))
