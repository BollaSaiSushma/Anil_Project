import re
import pandas as pd
import requests
from app.scraper.browser_fetch import harvest_many
from app.scraper.url_filters import filter_newton_urls

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

# --------- REDFIN ----------
from app.scraper.redfin_scraper import RedfinScraper

def fetch_redfin(city: str) -> pd.DataFrame:
    CITY_PAGES = [f"https://www.redfin.com/city/11619/MA/Newton"]
    raw = harvest_many(CITY_PAGES, site="redfin", scroll_passes=12, wait_ms=3000, headless=False)
    urls = filter_newton_urls("redfin", raw)
    scraper = RedfinScraper()
    data = []

    for u in urls[:15]:
        try:
            r = requests.get(u, headers={"User-Agent": DEFAULT_UA}, timeout=15)
            html = r.text
            
            property_data = scraper.parse_property_page(html)
            property_data.update({
                "city": city,
                "state": "MA",
                "url": u,
                "source": "redfin"
            })
            data.append(property_data)
        except Exception as e:
            print(f"[redfin] failed {u}: {e}")
    return pd.DataFrame(data)


# --------- ZILLOW ----------
from app.scraper.zillow_scraper_simple import fetch_zillow  # Using simplified DOM scraping implementation


# --------- REALTOR ----------
def fetch_realtor(city: str) -> pd.DataFrame:
    CITY_PAGES = [f"https://www.realtor.com/realestateandhomes-search/Newton_MA"]
    raw = harvest_many(CITY_PAGES, site="realtor", scroll_passes=10, wait_ms=3000, headless=False)
    urls = filter_newton_urls("realtor", raw)
    data = []

    for u in urls[:15]:
        try:
            r = requests.get(u, headers={"User-Agent": DEFAULT_UA}, timeout=15)
            html = r.text

            addr = re.search(r'"street":"([^"]+)"', html) or re.search(r'"address":"([^"]+)"', html)
            price = re.search(r'"price":\s*"?\$?([\d,]+)"?', html)
            beds = re.search(r'"beds":(\d+)', html)
            baths = re.search(r'"baths":(\d+)', html)

            data.append({
                "address": addr.group(1) if addr else None,
                "city": city,
                "state": "MA",
                "price": price.group(1) if price else None,
                "beds": beds.group(1) if beds else None,
                "baths": baths.group(1) if baths else None,
                "lot_sqft": None,
                "url": u,
                "source": "realtor",
            })
        except Exception as e:
            print(f"[realtor] failed {u}: {e}")
    return pd.DataFrame(data)
