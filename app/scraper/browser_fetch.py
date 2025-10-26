# app/scraper/browser_fetch.py
from contextlib import contextmanager
from typing import List, Optional
from pathlib import Path
import time
import json
import re

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Response

from app.scraper.url_filters import REDFIN_NEWTON, REALTOR_NEWTON, ZILLOW_NEWTON

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

SNAP_HTML_DIR = Path("data/logs/browser_html")
SNAP_JSON_DIR = Path("data/logs/network_json")
SNAP_HTML_DIR.mkdir(parents=True, exist_ok=True)
SNAP_JSON_DIR.mkdir(parents=True, exist_ok=True)

@contextmanager
def _playwright_context(headless: bool = False):
    pw = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-web-security",
            ],
        )
        context = browser.new_context(
            user_agent=DEFAULT_UA,
            java_script_enabled=True,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        # light stealth
        context.add_init_script("""Object.defineProperty(navigator,'webdriver',{get:()=>undefined});""")
        yield context
        context.close()
        browser.close()
    finally:
        if pw:
            pw.stop()

def _try_click(page, selectors: List[str], timeout_ms: int = 1500) -> bool:
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=timeout_ms)
            page.wait_for_timeout(300)
            return True
        except Exception:
            pass
    return False

def _accept_cookies(page, site: str):
    common = [
        'button:has-text("Accept")',
        'button:has-text("Accept All Cookies")',
        'button:has-text("I agree")',
        'button:has-text("Got it")',
        '#onetrust-accept-btn-handler',
        'button#truste-consent-button',
        'button[aria-label="Accept"]',
        'button:has-text("Continue")',
        'button:has-text("Agree & proceed")',
    ]
    extras_realtor = [
        'button:has-text("Accept all cookies")',
        'button:has-text("Accept All")',
        'button[aria-label*="Accept"]',
    ]
    extras_zillow = [
        'button:has-text("Accept all")',
        'button:has-text("Accept Cookies")',
    ]
    _try_click(page, common, 2500)
    if site == "realtor": _try_click(page, extras_realtor, 2500)
    if site == "zillow":  _try_click(page, extras_zillow, 2500)

def _base_for(site: str) -> str:
    return {
        "redfin":  "https://www.redfin.com",
        "realtor": "https://www.realtor.com",
        "zillow":  "https://www.zillow.com",
    }[site]

def _selectors_for(site: str) -> List[str]:
    if site == "redfin":
        return [
            'a[data-rf-test-id="basic-card-click"]',
            'a[data-rf-test-name="basic-card-click"]',
            'a[href*="/MA/Newton/"]',
            'a[href*="/home/"]',
        ]
    if site == "realtor":
        return [
            'a[data-testid="property-anchor"]',
            'li[data-testid="result-card"] a[href*="/realestateandhomes-detail/"]',
            'a[href*="/realestateandhomes-detail/"]',
            'a[href*="/property/"]',
        ]
    # zillow
    return [
        'a[data-test="property-card-link"]',
        'a.property-card-link',
        'a[href*="/homedetails/"]',
        'a[href*="/newton-ma/"]',
    ]

def _validator_for(site: str):
    return {
        "redfin":  REDFIN_NEWTON,
        "realtor": REALTOR_NEWTON,
        "zillow":  ZILLOW_NEWTON,
    }[site]

def _wait_for_any_listing_selector(page, site: str, timeout_ms: int) -> bool:
    sels = _selectors_for(site)
    try:
        for sel in sels:
            page.locator(sel).first.wait_for(timeout=timeout_ms)
            return True
    except PWTimeout:
        return False
    return False

def _extract_urls_from_dom(page, site: str, base: str, pat) -> list[str]:
    """Fallback DOM extraction via anchors."""
    sels = _selectors_for(site)
    seen = set()
    for sel in sels:
        for a in page.locator(sel).all():
            href = (a.get_attribute("href") or "").strip()
            if not href:
                continue
            if href.startswith("//"): href = "https:" + href
            if href.startswith("/"):  href = base + href
            if not pat.match(href):
                continue
            seen.add(href)
    return list(seen)

def _extract_urls_from_network_payloads(site: str, texts: List[str], pat) -> list[str]:
    """Parse captured JSON bodies (GraphQL/Apollo/NextData) for detail URLs."""
    urls = set()
    for body in texts:
        # Zillow: detailUrl, hdpUrl, and sometimes "canonicalUrl"
        if site == "zillow":
            for rx in [
                r'"detailUrl"\s*:\s*"([^"]+)"',
                r'"hdpUrl"\s*:\s*"([^"]+)"',
                r'"canonicalUrl"\s*:\s*"([^"]+)"',
            ]:
                for m in re.finditer(rx, body):
                    u = m.group(1)
                    if u.startswith("/"):
                        u = "https://www.zillow.com" + u
                    if pat.match(u):
                        urls.add(u)

        # Realtor: full URLs, path-only "detailUrl", sometimes "property_url" or "href"
        if site == "realtor":
            for rx in [
                r'https?://www\.realtor\.com/realestateandhomes-detail/[^"\s]+',
                r'"detailUrl"\s*:\s*"(/realestateandhomes-detail/[^"]+)"',
                r'"property_url"\s*:\s*"(/realestateandhomes-detail/[^"]+)"',
                r'"href"\s*:\s*"(/realestateandhomes-detail/[^"]+)"',
            ]:
                for m in re.finditer(rx, body):
                    u = m.group(1) if m.group(0).startswith('"') else m.group(0)
                    if u.startswith("/"):
                        u = "https://www.realtor.com" + u
                    if pat.match(u):
                        urls.add(u)
    return list(urls)


def harvest_listing_links_playwright(
    url: str,
    site: str,
    scroll_passes: int = 12,
    wait_ms: int = 3000,
    headless: bool = False,
    snapshot_name: Optional[str] = None,
) -> List[str]:
    """
    Navigate to results page, accept cookies, scroll, capture XHR/GraphQL JSON,
    extract Newton detail URLs from network payloads; fallback to DOM anchors.
    """
    base = _base_for(site)
    pat  = _validator_for(site)

    # Capture JSON responses
    captured_texts: List[str] = []

    with _playwright_context(headless=headless) as ctx:
        page = ctx.new_page()
        page.set_default_timeout(45000)

        def _on_response(resp: Response):
            try:
                url_l = resp.url.lower()
                ct = (resp.headers or {}).get("content-type", "")
                # Be permissive: many endpoints use text/plain or text/html even for JSON payloads.
                if any(k in url_l for k in [
                    "graphql", "search", "list-results", "searchresults", "apollo",
                    "getsearchpagestate", "searchResults", "api", "listings"
                ]) or "json" in ct or "javascript" in ct or "plain" in ct:
                    try:
                        txt = resp.text()
                    except Exception:
                        txt = ""
                    if txt and len(txt) > 400:  # lower threshold slightly
                        captured_texts.append(txt)

                        # Write a small sample
                        filename = SNAP_JSON_DIR / f"{site}_{int(time.time()*1000)}.json"
                        try:
                            filename.write_text(txt[:200000], encoding="utf-8", errors="ignore")
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", _on_response)

        # Go + wait a bit
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)

        _accept_cookies(page, site)

        # Scroll to trigger XHRs
        for _ in range(scroll_passes):
            page.mouse.wheel(0, 2200)
            page.wait_for_timeout(600)

        # Optional snapshot of final DOM
        if snapshot_name:
            SNAP_HTML_DIR.joinpath(snapshot_name).write_text(page.content(), encoding="utf-8", errors="ignore")

        # 1) Prefer network JSON extraction
        urls = set(_extract_urls_from_network_payloads(site, captured_texts, pat))

        # 2) Fallback to DOM anchors if needed
        if not urls:
            urls = set(_extract_urls_from_dom(page, site, base, pat))

        return list(urls)

def harvest_many(urls: List[str], site: str, **kw) -> List[str]:
    all_seen = set()
    for i, u in enumerate(urls, 1):
        snap = f"{site}_page_{i}.html"
        links = harvest_listing_links_playwright(u, site=site, snapshot_name=snap, **kw)
        for h in links:
            all_seen.add(h)
        time.sleep(0.8)
    return list(all_seen)
