"""Bouwmaat (EUR, Netherlands — trade building supplies; Shopify).

Replaces the bot-walled praxis/gamma/karwei (Maxeda): Praxis serves a "Human
Verification" 405 and Gamma a Vercel checkpoint even from residential IPs
(verified 2026-09-25), while Bouwmaat serves plain sitemaps to anyone.

sitemap.xml -> sitemap_products_{1..N}.xml?from=X&to=Y (query params are part
of the URL and required). Product URLs: /products/<slug>-f<id>.

Product pages: Shopify JSON '"price":{"amount":143.8,"currencyCode":"EUR"}'
— matches the displayed incl-VAT price (verified 2026-09-25).
"""
import re
from common import get, sane_price, valid_ean, write_jsonl, scrape_urls

BASE = "https://www.bouwmaat.nl"
OUT = "data/latest/bouwmaat_nl.jsonl"


def fetch_url_list(limit=None):
    idx = get(f"{BASE}/sitemap.xml")
    prod_maps = [m for m in re.findall(r"<loc>([^<]+)</loc>", idx)
                 if "sitemap_products_" in m]
    urls = []
    seen = set()
    for pm in prod_maps:
        try:
            xml = get(pm)
        except Exception:
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            u = u.strip()
            if u in seen or "/products/" not in u:
                continue
            seen.add(u)
            urls.append(u)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = re.search(r'"price"\s*:\s*\{\s*"amount"\s*:\s*([0-9.]+)'
                  r'\s*,\s*"currencyCode"\s*:\s*"EUR"', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    sk = re.search(r"-f(\d+)$", u)
    img = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    import html as _html
    if t:
        raw = t.group(1).split("&ndash;")[0]
        name = _html.unescape(raw).strip().strip("\n").strip()
    else:
        name = u.rsplit("/", 1)[-1]
    ean = re.search(r'"barcode"\s*:\s*"?(\d{8,14})"?', html)
    return [{
        "chain": "bouwmaat_nl",
        "country": "nl",
        "currency": "EUR",
        "sku": sk.group(1) if sk else None,
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
    print("bouwmaat_nl: %d products -> %s" % (len(rows), OUT))
