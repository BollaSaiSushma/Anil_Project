# app/scraper/llm_browser.py
import os
import re
import time
from typing import List, Dict
import httpx
import pandas as pd
from bs4 import BeautifulSoup

from app.utils.logger import logger

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- OpenAI (legacy 0.27.x) ---
try:
    import openai  # type: ignore
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
except Exception:
    openai = None

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 25
DELAY = 1.0  # polite delay between page fetches

# Regex prefilter (cheap)
PHRASES = [
    r"tear[\s-]?down",
    r"\bbuilder\b",
    r"contractor[s]?\s+special",
    r"development\s+opportunit(y|ies)",
    r"\bdeveloper[s]?\b",
    r"fixer[\s-]?upper",
    r"\bas[-\s]?is\b",
]
PHRASES_RE = re.compile("|".join(PHRASES), re.IGNORECASE)

NEWTON_TEXT_RE = re.compile(r"\bNewton\b.*\bMA\b|\b0245\d\b", re.IGNORECASE)

def _fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text

def _page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Try common long-content areas first
    candidates = []
    for sel in [
        "[data-rf-test-id='abp-description']",  # redfin often
        ".ds-overview-section",                 # zillow sometimes
        "section#property-details",             # realtor sometimes
        "main", "article", "section", "div"
    ]:
        for n in soup.select(sel):
            t = n.get_text(" ", strip=True)
            if t and len(t) > 120:
                candidates.append(t)
    text = max(candidates, key=len) if candidates else soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text or "").strip()

def _title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return ((soup.title.string if soup.title else "") or "").strip()

def _address_from_title(html: str) -> str:
    t = _title(html)
    m = re.search(
        r"\b\d{1,6}\s+[A-Za-z0-9'.-]+\s+(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court)\b",
        t, re.IGNORECASE
    )
    return m.group(0) if m else t

def _llm_confirm(text: str) -> Dict:
    """
    Use OpenAI to confirm redevelopment signal.
    If OpenAI isn't available, fall back to regex-only.
    """
    # If regex already matches, accept immediately (recall-first)
    if PHRASES_RE.search(text or ""):
        return {"is_candidate": True, "matched": list({m.group(0).lower() for m in PHRASES_RE.finditer(text or "")}), "reason": "regex"}

    if not openai or not OPENAI_API_KEY:
        return {"is_candidate": False, "matched": [], "reason": "no-openai"}

    prompt = (
        "You filter real estate listings for redevelopment signals in Newton, MA.\n"
        "Given TEXT, answer JSON: {\"is_candidate\":true/false, \"matched\":[...], \"reason\":\"...\"}.\n"
        "True only if clearly implied: tear down, builder project, contractor special, development opportunity, developer terms, fixer-upper, as-is.\n\n"
        f"TEXT:\n{text[:4000]}"
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = resp["choices"][0]["message"]["content"]
        import json
        s, e = content.find("{"), content.rfind("}")
        if s != -1 and e != -1 and e > s:
            return json.loads(content[s:e+1])
    except Exception as e:
        logger.debug("OpenAI check failed: %s", e)

    return {"is_candidate": False, "matched": [], "reason": "openai-fallback-false"}

def scan_listing_urls(urls: List[str], site: str, city: str) -> pd.DataFrame:
    """
    Fetch each URL, ensure Newton, MA is referenced, detect phrases (regex or LLM),
    return rows compatible with your pipeline.
    """
    rows: List[Dict] = []
    kept = 0

    for i, u in enumerate(urls, 1):
        time.sleep(DELAY)
        try:
            html = _fetch(u)
        except Exception as e:
            logger.debug("[%s] fetch fail (%d/%d): %s", site, i, len(urls), e)
            continue

        title = _title(html)
        text  = _page_text(html)
        if not (NEWTON_TEXT_RE.search(title) or NEWTON_TEXT_RE.search(text)):
            continue

        # decide with regex+LLM
        verdict = _llm_confirm(title + "\n" + text)
        if not verdict.get("is_candidate"):
            continue

        kept += 1
        rows.append({
            "address": _address_from_title(html) or "",
            "city": city,
            "state": "MA",
            "price": None, "beds": None, "baths": None, "lot_sqft": None,
            "url": u,
            "source": site,
            "matched_keywords": ", ".join(sorted(set(verdict.get("matched", [])))),
            "llm_reason": verdict.get("reason", ""),
        })

    logger.info("[scan] %s kept %d / %d", site, kept, len(urls))
    if not rows:
        return pd.DataFrame(columns=["address","city","state","price","beds","baths","lot_sqft","url","source","matched_keywords","llm_reason"])
    return pd.DataFrame(rows).drop_duplicates(subset=["url"]).reset_index(drop=True)
