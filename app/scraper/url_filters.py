# app/scraper/url_filters.py
import re
from typing import List

# Redfin stays strict — detail pages look like /MA/Newton/.../home/<id>
REDFIN_NEWTON  = re.compile(r"^https?://(?:www\.)?redfin\.com/MA/Newton/.+/home/\d+/?$", re.IGNORECASE)

# Realtor detail pages vary; allow Newton-neighborhood names and MA, with optional zip & query
_REALTOR_CITY = r"(?:Newton|West-Newton|Newtonville|Newton-Center|Auburndale|Waban|Chestnut-Hill|Nonantum|Oak-Hill)"
REALTOR_NEWTON = re.compile(
    rf"^https?://(?:www\.)?realtor\.com/realestateandhomes-detail/.+{_REALTOR_CITY}.*-MA(?:-\d{{5}})?(?:[/?#].*)?$",
    re.IGNORECASE,
)

# Zillow can be /homedetails/.../_zpid or /b/... styles; accept Newton* + MA or zip 0245x anywhere
_ZILLOW_CITY = r"(?:Newton|West-Newton|Newtonville|Newton-Center|Auburndale|Waban|Chestnut-Hill|Nonantum|Oak-Hill)"
ZILLOW_NEWTON = re.compile(
    rf"^https?://(?:www\.)?zillow\.com/(?:homedetails|b)/.+(?:{_ZILLOW_CITY}).*-MA(?:-0245\d)?/.+?(?:_zpid)?/?(?:[?#].*)?$",
    re.IGNORECASE,
)

def filter_newton_urls(site: str, urls: List[str]) -> List[str]:
    if site == "redfin":
        keep = [u for u in urls if REDFIN_NEWTON.match((u or "").strip())]
    elif site == "realtor":
        keep = [u for u in urls if REALTOR_NEWTON.match((u or "").strip())]
    elif site == "zillow":
        keep = [u for u in urls if ZILLOW_NEWTON.match((u or "").strip())]
    else:
        keep = []
    seen, out = set(), []
    for u in keep:
        if u not in seen:
            out.append(u); seen.add(u)
    return out
