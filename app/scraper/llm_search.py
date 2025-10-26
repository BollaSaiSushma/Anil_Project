import os
import re
import time
from typing import List, Dict, Tuple
import httpx
import pandas as pd
from bs4 import BeautifulSoup

from app.utils.logger import logger

# ---- Config ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CITY = "Newton, MA"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

# Site search entry points (public browse pages for Newton, MA)
SEARCH_PAGES: List[Tuple[str, str]] = [
    ("redfin",  "https://www.redfin.com/city/12180/MA/Newton"),          # city hub
    ("realtor", "https://www.realtor.com/realestateandhomes-search/Newton_MA"),
    ("zillow",  "https://www.zillow.com/newton-ma/"),
]

# How many listing links to inspect per site
MAX_LINKS_PER_SITE = 25
REQUEST_TIMEOUT = 20
DELAY_BETWEEN_REQUESTS = 1.2  # seconds

# Phrases to detect
PHRASES = [
    r"tear[\s-]?down",                   # tear down / teardown
    r"\bbuilder\b",                      # builder
    r"contractor[s]?\s+special",         # contractor special
    r"development\s+opportunit(y|ies)",  # development opportunity/opportunities
    r"\bdeveloper[s]?\b",
    r"fixer[\s-]?upper",
    r"\bas[-\s]?is\b",
]
PHRASES_RE = re.compile("|".join(PHRASES), re.IGNORECASE)

# ---- OpenAI helper (legacy openai==0.27.x style) ----
try:
    import openai  # type: ignore
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
except Exception:
    openai = None


def _llm_filter(text: str) -> Dict:
    """
    Ask OpenAI to confirm whether the text really implies a redevelopment / builder
    scenario. Returns dict with {is_candidate: bool, matched: [..], reason: str}.
    If OpenAI is unavailable, falls back to regex-only judgement.
    """
    # Fast path: if no LLM, rely on regex only
    if not openai or not OPENAI_API_KEY:
        return {
            "is_candidate": bool(PHRASES_RE.search(text or "")),
            "matched": list(set(m.group(0).lower() for m in PHRASES_RE.finditer(text or ""))),
            "reason": "Regex-only (no OpenAI key found)"
        }

    prompt = (
        "You are filtering real estate listings for redevelopment potential.\n"
        "Given the text below (title + description/snippet), decide if it clearly "
        "signals any of these concepts: tear down, builder project, contractor special, "
        "development opportunity, developer terms, fixer-upper, as-is.\n"
        "Return STRICT JSON with keys: is_candidate (true/false), matched (array of strings), reason (string).\n"
        "Be conservative; only true if it's clearly implied.\n\n"
        f"TEXT:\n{text}\n"
    )

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user", "content": prompt}],
            temperature=0.0,
        )
        content = resp["choices"][0]["message"]["content"]
        # Very defensive parse: try to find JSON object in response
        import json
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start:end+1])
        # Fallback to regex if we couldn't parse
        return {
            "is_candidate": bool(PHRASES_RE.search(text or "")),
            "matched": list(set(m.group(0).lower() for m in PHRASES_RE.finditer(text or ""))),
            "reason": "LLM returned non-JSON; used regex fallback",
        }
    except Exception as e:
        logger.warning("OpenAI check failed; falling back to regex: %s", e)
        return {
            "is_candidate": bool(PHRASES_RE.search(text or "")),
            "matched": list(set(m.group(0).lower() for m in PHRASES_RE.finditer(text or ""))),
            "reason": "OpenAI error; regex fallback",
        }


def _fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def _extract_links(site: str, html: str) -> List[str]:
    """
    Best-effort extraction of listing links from a site search page.
    We err on the side of collecting extra links, LLM/regex narrows later.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Normalize relative links
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("/"):
            base = {
                "redfin":  "https://www.redfin.com",
                "realtor": "https://www.realtor.com",
                "zillow":  "https://www.zillow.com",
            }.get(site, "")
            href = base + href

        # Heuristic filters per site to prefer property pages
        if site == "redfin" and "redfin.com" in href and re.search(r"/home/|/house/|/MA/Newton", href):
            links.append(href)
        elif site == "realtor" and "realtor.com" in href and re.search(r"/realestateandhomes-detail/|/property", href):
            links.append(href)
        elif site == "zillow" and "zillow.com" in href and re.search(r"/homedetails/|/b/|/newton-ma", href):
            links.append(href)

    # Deduplicate & limit
    out = []
    seen = set()
    for h in links:
        if h not in seen:
            out.append(h)
            seen.add(h)
        if len(out) >= MAX_LINKS_PER_SITE:
            break
    return out


def _extract_text_from_listing(html: str) -> str:
    """
    Extract visible text chunks likely to contain marketing remarks.
    Very simple: strip tags and collapse whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try common description containers first
    candidates = []
    for sel in [
        "[data-rf-test-id='abp-description']",  # redfin (often)
        ".ds-overview-section",                 # zillow (varies)
        "section#property-details",             # realtor (varies)
        "article", "main", "section", "div"
    ]:
        for node in soup.select(sel):
            txt = node.get_text(" ", strip=True)
            if txt and len(txt) > 80:
                candidates.append(txt)

    # Fallback to whole-page text
    if not candidates:
        txt = soup.get_text(" ", strip=True)
    else:
        # choose the longest chunk
        txt = max(candidates, key=len)

    # collapse whitespace
    return re.sub(r"\s+", " ", txt or "").strip()


def _extract_address_from_title_or_meta(html: str, default: str = "") -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string if soup.title else "") or ""
    # meta og:title / twitter:title
    for prop in ["og:title", "twitter:title"]:
        m = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if m and m.get("content"):
            title = m["content"]
            break

    # Heuristic: number + street + type
    m = re.search(
        r"\b\d{1,6}\s+[A-Za-z0-9'.-]+\s+(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court)\b",
        title, flags=re.IGNORECASE
    )
    return m.group(0) if m else default or title.strip()


def llm_powered_search(city: str = CITY) -> pd.DataFrame:
    """
    Crawl site search pages for Redfin/Realtor/Zillow, gather listing links,
    fetch each listing, run regex + OpenAI check for redevelopment phrases.
    Returns pipeline-compatible DataFrame.
    """
    if not OPENAI_API_KEY:
        logger.warning("[LLM Search] OPENAI_API_KEY not set; using regex-only classification.")
    logger.info("[LLM Search] Starting LLM search for %s", city)

    all_rows: List[Dict] = []

    for site, url in SEARCH_PAGES:
        try:
            logger.info("[LLM Search] Fetching %s search page: %s", site, url)
            html = _fetch(url)
            links = _extract_links(site, html)
            logger.info("[LLM Search] %s: collected %d candidate links", site, len(links))
        except Exception as e:
            logger.warning("[LLM Search] Failed to fetch search page %s: %s", url, e)
            continue

        for link in links:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            try:
                page = _fetch(link)
            except Exception as e:
                logger.debug("[LLM Search] Skip %s (fetch failed: %s)", link, e)
                continue

            text = _extract_text_from_listing(page)
            # Quick regex gate to avoid spending tokens on random pages
            if not PHRASES_RE.search(text):
                # Still let LLM try the title/meta in case copy is short
                llm = _llm_filter(text[:2000])
                if not llm.get("is_candidate"):
                    continue
                matched = llm.get("matched", [])
                reason = llm.get("reason", "LLM said true (no regex match)")
            else:
                llm = _llm_filter(text[:2000])
                if not llm.get("is_candidate"):
                    # Regex matched but LLM rejected; keep it conservative
                    continue
                matched = llm.get("matched", [])
                reason = llm.get("reason", "regex+LLM match")

            address = _extract_address_from_title_or_meta(page)
            all_rows.append({
                "address": address or "",
                "city": city,
                "state": "MA",
                "price": None,
                "beds": None,
                "baths": None,
                "lot_sqft": None,
                "url": link,
                "source": site,
                "matched_keywords": ", ".join(sorted(set(matched))) if matched else "",
                "llm_reason": reason,
            })

    if not all_rows:
        logger.info("[LLM Search] No matches found.")
        return pd.DataFrame(columns=[
            "address","city","state","price","beds","baths","lot_sqft","url","source","matched_keywords","llm_reason"
        ])

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["url"]).reset_index(drop=True)
    logger.info("[LLM Search] Yielding %d flagged listings", len(df))
    return df
