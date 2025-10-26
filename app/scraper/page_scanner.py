import time, re
from typing import List, Dict
import httpx, pandas as pd
from bs4 import BeautifulSoup
from app.utils.logger import logger

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/123.0.0.0 Safari/537.36")
REQUEST_TIMEOUT = 20
DELAY = 0.9

PHRASES_RE = re.compile(
    r"tear[\s-]?down|\bbuilder\b|contractor[s]?\s+special|development\s+opportunit(?:y|ies)|\bdeveloper[s]?\b|fixer[\s-]?upper|\bas[-\s]?is\b",
    re.I
)
NEWTON_TEXT_RE = re.compile(r"\bNewton\b.*\bMA\b|\b0245\d\b", re.I)

def _fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text

def _text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Prefer longer description-like areas
    candidates = []
    for sel in [
        "[data-rf-test-id='abp-description']",
        ".ds-overview-section",
        "section#property-details",
        "main", "article", "section", "div"
    ]:
        for n in soup.select(sel):
            t = n.get_text(" ", strip=True)
            if t and len(t) > 120:
                candidates.append(t)
    t = max(candidates, key=len) if candidates else soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", t or "").strip()

def _title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return ((soup.title.string if soup.title else "") or "").strip()

def _address_from_title(html: str) -> str:
    t = _title(html)
    m = re.search(r"\b\d{1,6}\s+[A-Za-z0-9'.-]+\s+(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court)\b", t, re.I)
    return m.group(0) if m else t

def scan_urls(urls: List[str], site: str, city: str) -> pd.DataFrame:
    out: List[Dict] = []
    kept = 0
    for i, u in enumerate(urls, 1):
        time.sleep(DELAY)
        try:
            html = _fetch(u)
        except Exception as e:
            logger.debug("[Fetch] %s %d/%d failed: %s", site, i, len(urls), e)
            continue

        t = _text(html)
        title = _title(html)

        # Must mention Newton, MA (title or body)
        if not (NEWTON_TEXT_RE.search(t) or NEWTON_TEXT_RE.search(title)):
            continue

        # Must mention at least one target phrase (title or body)
        hits = set(m.group(0).lower() for m in PHRASES_RE.finditer(t))
        if not hits:
            hits = set(m.group(0).lower() for m in PHRASES_RE.finditer(title))
        if not hits:
            continue

        kept += 1
        out.append({
            "address": _address_from_title(html) or "",
            "city": city, "state": "MA",
            "price": None, "beds": None, "baths": None, "lot_sqft": None,
            "url": u, "source": site,
            "matched_keywords": ", ".join(sorted(hits)),
        })

    logger.info("[Scan] %s kept %d / %d", site, kept, len(urls))
    if not out:
        return pd.DataFrame(columns=["address","city","state","price","beds","baths","lot_sqft","url","source","matched_keywords"])
    return pd.DataFrame(out).drop_duplicates(subset=["url"]).reset_index(drop=True)
