import re
import requests
import pandas as pd
from app.scraper.browser_fetch import harvest_many
from app.scraper.url_filters import filter_newton_urls

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

CITY_PAGES = [
    "https://www.realtor.com/realestateandhomes-search/Newton_MA",
    "https://www.realtor.com/realestateandhomes-search/Newton_MA/pg-2",
    "https://www.realtor.com/realestateandhomes-search/Newton_MA/pg-3",
]

def _match_first(html: str, patterns: list[str]):
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m
    return None

def fetch_realtor(city: str) -> pd.DataFrame:
    raw = harvest_many(CITY_PAGES, site="realtor", scroll_passes=8, wait_ms=3000, headless=False)
    urls = filter_newton_urls("realtor", raw)
    data = []

    for u in urls[:20]:
        try:
            html = requests.get(u, headers={"User-Agent": DEFAULT_UA}, timeout=15).text

            # address
            addr_m = re.search(r'"street":"([^"]+)"', html) or re.search(r'"addressLine":"([^"]+)"', html)
            address_value = addr_m.group(1) if addr_m else None

            # price (normalized string)
            price_m = _match_first(html, [
                r'"price":\s*"?\$?([\d,]+)"?',       # "price":"$1,234,000"
                r'"list_price":\s*([\d,]+)',         # list_price:1234000
                r'"price_raw":\s*([\d,]+)',          # price_raw:1234000
            ])
            price_value = price_m.group(1) if price_m else None

            # optional details
            beds_m  = re.search(r'"beds":\s*(\d+)', html)
            baths_m = re.search(r'"baths":\s*(\d+)', html)
            lot_m   = re.search(r'"lot_size":\s*{[^}]*"size":\s*([\d]+)', html)  # sometimes nested

            row = {
                "address": address_value,
                "city": city,
                "state": "MA",
                "price": price_value,  # string like "1,250,000" is OK
                "beds": int(beds_m.group(1)) if beds_m else None,
                "baths": int(baths_m.group(1)) if baths_m else None,
                "lot_sqft": int(lot_m.group(1)) if lot_m else None,
                "url": u,
                "source": "realtor",
            }
            data.append(row)
        except Exception as e:
            print("[realtor] failed:", u, e)

    return pd.DataFrame(data)
