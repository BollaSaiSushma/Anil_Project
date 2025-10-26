import re, json
from pathlib import Path
from typing import Dict, List
import httpx
from app.utils.config_loader import SETTINGS
from app.utils.logger import logger

SERPAPI_API_KEY = SETTINGS.serpapi_key
RESULTS_PER_PAGE = 10
PAGES = 8
MAX_URLS_PER_SITE = 150
REQUEST_TIMEOUT = 20
LOG_DIR = Path("data/logs"); LOG_DIR.mkdir(parents=True, exist_ok=True)

def _serpapi(query: str, start: int = 0) -> Dict:
    if not SERPAPI_API_KEY:
        raise RuntimeError("SERPAPI_API_KEY missing (.env)")
    params = {"engine":"google","q":query,"start":start,"num":RESULTS_PER_PAGE,"api_key":SERPAPI_API_KEY,"hl":"en","no_cache":"true"}
    with httpx.Client(timeout=REQUEST_TIMEOUT) as c:
        r = c.get("https://serpapi.com/search.json", params=params)
        r.raise_for_status()
        data = r.json()
        (LOG_DIR / f"serpapi_{abs(hash(query))}_{start}.json").write_text(json.dumps(data, indent=2))
        if "error" in data:
            raise RuntimeError(f"SerpAPI error: {data['error']}")
        return data

# Keep only listing-like paths per site
RED_FIN_PAT  = re.compile(r"redfin\.com/.+/(home|house|property)|/MA/Newton", re.I)
REALTOR_PAT  = re.compile(r"realtor\.com/.+/(realestateandhomes-detail|property/)", re.I)
ZILLOW_PAT   = re.compile(r"zillow\.com/.+/(homedetails|b/)", re.I)
NEWTON_HINT  = re.compile(r"newton(?:[-\s]?center|ville|highlands)?[, -]?\s*ma|0245\d", re.I)

def _listing_like(site: str, url: str) -> bool:
    if site == "redfin":   return bool(RED_FIN_PAT.search(url))
    if site == "realtor":  return bool(REALTOR_PAT.search(url))
    if site == "zillow":   return bool(ZILLOW_PAT.search(url))
    return False

def harvest_urls(site_filter: str, city: str) -> List[str]:
    # Broad queries (with and without quotes) to maximize recall
    queries = [f'{site_filter} "{city}"', f"{site_filter} {city}"]
    urls, seen = [], set()
    site = "redfin" if "redfin" in site_filter else "realtor" if "realtor" in site_filter else "zillow"

    for q in queries:
        for page in range(PAGES):
            start = page * RESULTS_PER_PAGE
            data = _serpapi(q, start=start)
            organic = data.get("organic_results") or []
            logger.info("[SerpAPI] %s page %d -> %d results", site, page, len(organic))
            for res in organic:
                u = (res.get("link") or "").strip()
                if not u or u in seen:
                    continue
                # domain gate
                if site not in u:
                    continue
                # keep only listing-like URLs and prefer Newton/0245x
                if _listing_like(site, u) and NEWTON_HINT.search(u):
                    urls.append(u); seen.add(u)
                # Still allow a few neutral Newton URLs; body scan will filter later
                elif NEWTON_HINT.search(u) and len(urls) < MAX_URLS_PER_SITE//3:
                    urls.append(u); seen.add(u)
                if len(urls) >= MAX_URLS_PER_SITE:
                    break
            if len(organic) < RESULTS_PER_PAGE or len(urls) >= MAX_URLS_PER_SITE:
                break

    logger.info("[SerpAPI] %s collected %d urls", site, len(urls))
    return urls[:MAX_URLS_PER_SITE]
