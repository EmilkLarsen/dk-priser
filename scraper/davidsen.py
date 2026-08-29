"""Davidsen.dk — pure category pages embed full product JSON.
{"id","name","url":"...-p-<id>", ..., "price":{"value":"5.590,00"}}
Product sitemap URLs are paginated category walks (-c-id...-p-<id>) that
also embed data, so we harvest both. Runs cheaply: 1 request serves ~30 products."""
import re
from common import html_gtin, sane_price, get, sitemap_urls, parse_dk_price, write_jsonl, pmap

BASE = "https://www.davidsen.dk"
OUT = "data/latest/davidsen.jsonl"

# variant block: productVariantId -> name -> priceInformation.price
VAR_RE = re.compile(
    r'"productVariantId":"(\d+)","name":"([^"]{3,200})",'
    r'"priceInformation":\{"price":\{"value":"([\d.,]+)"\}'
    r'(?:.{0,200}?"priceDescription":"([^"]{0,40})")?', re.S)
# listing block: id -> name -> url (-p-<id>) ... price
BLOCK_RE = re.compile(
    r'\{"id":"(\d+)","name":"([^"]+)","url":"(/[a-z0-9-]+-p-\d+)".{0,1500}?'
    r'"price":\{"value":"([\d.,]+)"\}', re.S)


def fetch_url_list(limit=None):
    urls = set()
    for f in ("sitemap-1.xml", "sitemap-2.xml"):
        try:
            xml = get(f"{BASE}/{f}")
        except Exception:
            continue
        for u in sitemap_urls(xml):
            if "-c-id" in u and "-p-" in u:
                urls.add(u)  # paginated listing pages, each ~30 products
    urls = sorted(urls)
    return urls[:limit] if limit else urls


def handle(cu, html):
    rows, seen = [], set()
    for m in VAR_RE.finditer(html):
        pid, name, price = m.group(1), m.group(2), m.group(3)
        unit = (m.group(4) or "").replace("kr./", "") or None
        key = "v" + pid
        if key in seen:
            continue
        p = sane_price(parse_dk_price(price))
        if not p:
            continue
        seen.add(key)
        rows.append({
            "chain": "davidsen",
            "sku": pid,
            "ean": html_gtin(html),
            "name": name,
            "url": "%s/search?q=%s" % (BASE, pid),  # variant-level URL fallback
            "price": p,
            "unit": unit,
            "in_stock": None,
        })
    for m in BLOCK_RE.finditer(html):
        pid, name, url, price = m.groups()
        if url in seen:
            continue
        p = parse_dk_price(price)
        p = sane_price(p)
        if not p:
            continue
        seen.add(url)
        rows.append({
            "chain": "davidsen",
            "sku": pid,
            "ean": html_gtin(html),
            "name": name,
            "url": BASE + url,
            "price": p,
            "unit": None,
            "in_stock": None,
        })
    return rows


def scrape(limit=None):
    def work(cu):
        try:
            return handle(cu, get(cu))
        except Exception as e:
            print(f"  ! {cu}: {e}")
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("davidsen: %d products -> %s" % (len(rows), OUT))
