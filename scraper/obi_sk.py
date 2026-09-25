"""OBI.de (EUR, Germany #2) — gzipped sitemap index -> product sitemaps
(sitemap_obi-products_N.xml); URLs /p/<id>/<slug>; ld+json offers list with
price + priceCurrency + availability."""
import re
import gzip
from common import get, sitemap_urls, sane_price, valid_ean, write_jsonl, pmap

BASE = "https://www.obi.sk"
OUT = "data/latest/obi_sk.jsonl"
PROD_RE = re.compile(r"/p/\d+")


def _get_maybe_gz(url):
    """Some OBI sitemap endpoints return gzip regardless of extension."""
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def fetch_url_list(limit=None):
    """robots.txt -> sitemap_index.xml -> product urlsets. The index names the
    numbered chunk files (sitemap_4159.xml etc.); only urlsets (not the store/
    rental sitemaps) contain /p/<id> product URLs. Handle both index and bare
    urlset responses, since obi.sk serves chunks either way (verified 2026-09-25)."""
    idx = _get_maybe_gz(f"{BASE}/sitemaps/obi_sk_sk/sitemap_index.xml")
    candidates = sitemap_urls(idx) or [f"{BASE}/sitemaps/obi_sk_sk/sitemap_4159.xml"]
    urls = []
    for f in candidates:
        xml = _get_maybe_gz(f)
        # an index of chunks: recurse one level
        if "<sitemapindex" in xml:
            candidates.extend(sitemap_urls(xml))
            continue
        us = [u for u in sitemap_urls(xml) if PROD_RE.search(u)]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    # Verified 2026-09-25: obi.sk pages carry an embedded cartData JSON blob
    # ("id": "2613255", "price": "37.39" = ex-VAT) plus the visible incl-VAT
    # price "= 45,99 EUR" (37.39 + 23% DPH). The old ld+json offers markup is
    # gone from the page. Customers pay the incl-VAT figure, so prefer it and
    # fall back to the cartData price only if the visible one is missing.
    sku = u.rstrip("/").split("/p/")[-1].split("/")[0]
    cart = re.search(r'"id"\s*:\s*"' + re.escape(sku) + r'"\s*,\s*"price"\s*:\s*"([0-9.,]+)"', html)
    incl = re.search(r'=\s*([0-9]+(?:[.,][0-9]{2}))\s*EUR', html)
    raw = None
    if incl:
        raw = incl.group(1)
    elif cart:
        raw = cart.group(1)   # ex-VAT fallback - still a real price, flag via unit? keep simple
    else:
        return []
    p = sane_price(float(raw.replace(".", "").replace(",", "."))
                   if "," in raw and raw.count(",") == 1 and raw.count(".") <= 1 and len(raw.split(",")[-1]) == 2
                   else float(raw))
    if not p:
        return []
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).split(" nakúpiť")[0].strip() if t else u.rsplit("/", 1)[-1])
    og = re.search(r'(https://bilder\.obi\.[a-z.]*/[^"\s>]+)', html)
    image = og.group(1) if og else None
    return [{
        "chain": "obi_sk",
        "country": "sk",
        "currency": "EUR",
        "sku": sku,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
        "image": image,
    }]


def scrape(limit=None):
    def work(u):
        try:
            return handle(u, get(u))
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("obi_de: %d products -> %s" % (len(rows), OUT))
