import re
import json
import pandas as pd
import requests
from playwright.sync_api import sync_playwright, TimeoutError

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

API_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/json',
    'origin': 'https://www.zillow.com',
    'referer': 'https://www.zillow.com/newton-ma/',
    'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': DEFAULT_UA
}

CITY_PAGES = [
    "https://www.zillow.com/newton-ma/",
    "https://www.zillow.com/newton-ma/2_p/",
    "https://www.zillow.com/newton-ma/3_p/",
]

def _extract_json_data(page) -> dict:
    """Extract property data from JSON/JavaScript on the page."""
    try:
        # Try multiple JavaScript data sources with more specific extraction
        js_extractions = [
            # NextJS Data
            '''() => {
                try {
                    const nextData = document.getElementById('__NEXT_DATA__');
                    if (nextData) {
                        const data = JSON.parse(nextData.textContent);
                        const props = data?.props?.pageProps;
                        if (props?.data?.property) {
                            return {
                                property: props.data.property,
                                source: 'nextjs'
                            };
                        }
                    }
                } catch (e) {}
                return null;
            }''',
            # Apollo/Redux State
            '''() => {
                try {
                    if (window.__PRELOADED_STATE__) {
                        const state = window.__PRELOADED_STATE__;
                        if (state.apollo?.ROOT_QUERY) {
                            const entries = Object.entries(state.apollo.ROOT_QUERY);
                            const propEntry = entries.find(([k]) => k.includes('property('));
                            if (propEntry) return {
                                property: propEntry[1],
                                source: 'apollo'
                            };
                        }
                        if (state.property) return {
                            property: state.property,
                            source: 'redux'
                        };
                    }
                } catch (e) {}
                return null;
            }''',
            # Zillow's HDPJS variable
            '''() => {
                try {
                    if (window.HDPJS) {
                        const hdp = window.HDPJS;
                        if (hdp.property || hdp.data?.property) {
                            return {
                                property: hdp.property || hdp.data.property,
                                source: 'hdpjs'
                            };
                        }
                    }
                } catch (e) {}
                return null;
            }''',
            # Search for property data in rendered JSON scripts
            '''() => {
                try {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                    for (const script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            if (data['@type'] === 'SingleFamilyResidence' || data['@type'] === 'House') {
                                return {
                                    property: data,
                                    source: 'jsonld'
                                };
                            }
                        } catch (e) {}
                    }
                } catch (e) {}
                return null;
            }'''
        ]
        
        for js in js_extractions:
            try:
                result = page.evaluate(js)
                if result and isinstance(result, dict) and 'property' in result:
                    print(f"[zillow] Found property data in {result['source']}")
                    return result['property']
            except Exception as e:
                print(f"[zillow] JS extraction error: {str(e)}")
                continue
                
        # Last resort - try extracting from global window properties
        try:
            props = page.evaluate('''() => {
                const props = {};
                if (window.dataLayer) {
                    const dlData = window.dataLayer.find(d => d.propertyId || d.listingId);
                    if (dlData) Object.assign(props, dlData);
                }
                ['propertyId', 'zpid', 'listingId'].forEach(key => {
                    if (window[key]) props[key] = window[key];
                });
                return props;
            }''')
            if props:
                print("[zillow] Found property IDs in window scope")
                return props
        except:
            pass
                
        return {}
    except Exception as e:
        print(f"[zillow] Failed to extract JSON data: {str(e)}")
        return {}

def _extract_data(page) -> dict:
    """Extract property data from various sources using a multi-layered approach."""
    data = {}
    
    try:
        # Wait for critical content to load
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_selector('h1', timeout=10000)
        
        # Force scroll to trigger lazy loading
        page.evaluate('window.scrollTo(0, document.body.scrollHeight/2)')
        page.wait_for_timeout(2000)  # Wait for dynamic content
            
            # Inject MutationObserver to detect dynamic content
            page.evaluate('''() => {
                window.dynamicElementsFound = false;
                const observer = new MutationObserver((mutations) => {
                    for (const mutation of mutations) {
                        if (mutation.addedNodes.length) {
                            const added = Array.from(mutation.addedNodes);
                            if (added.some(node => {
                                if (node.nodeType === 1) {  // Element node
                                    return node.querySelector?.('[data-testid], [class*="price"], [class*="address"]');
                                }
                                return false;
                            })) {
                                window.dynamicElementsFound = true;
                            }
                        }
                    }
                });
                observer.observe(document.body, { 
                    childList: true, 
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['data-testid', 'class']
                });
            }''')
            
            # Wait for dynamic content
            try:
                page.wait_for_function('window.dynamicElementsFound === true', timeout=3000)
            except:
                pass  # Continue even if no dynamic content detected
                
        except TimeoutError:
            print("[zillow] Initial page load timeout, continuing with partial content")
            
        # 2. Try getting data from JavaScript first
        json_data = _extract_json_data(page)
        if json_data:
            # Extract from various JSON structures
            try:
                if isinstance(json_data, dict):
                    # Map common property fields from various Zillow data structures
                    field_mappings = {
                        'address': ['streetAddress', 'address.streetAddress', 'location.address', 'fullAddress'],
                        'price': ['price', 'listPrice', 'homePrice', 'unformattedPrice'],
                        'beds': ['bedrooms', 'numberOfBedrooms', 'beds', 'numBeds'],
                        'baths': ['bathrooms', 'numberOfBathrooms', 'baths', 'numBaths'],
                        'lot_size': ['lotSize', 'lotSizeSquareFeet', 'lotAreaValue', 'lotArea']
                    }

                    def get_nested(obj: dict, path: str):
                        """Get value from nested dict using dot notation."""
                        parts = path.split('.')
                        for part in parts:
                            if not isinstance(obj, dict):
                                return None
                            obj = obj.get(part, {})
                        return obj if obj != {} else None

                    # Extract values using field mappings
                    for target_field, possible_fields in field_mappings.items():
                        if target_field not in data or not data[target_field]:
                            for field in possible_fields:
                                value = None
                                if '.' in field:
                                    value = get_nested(json_data, field)
                                else:
                                    value = json_data.get(field)
                                    if value is None and isinstance(json_data.get('property'), dict):
                                        value = json_data['property'].get(field)
                                if value is not None:
                                    if target_field in ['price', 'lot_size']:
                                        value = str(value).replace(',', '').replace('$', '')
                                    data[target_field] = value
                                    break

            except Exception as e:
                print(f"[zillow] Failed to extract from JSON: {str(e)}")
                
        # 3. If we're missing any data, try HTML extraction
        if not all(data.values()):
            # Scroll and expand content
            page.evaluate('window.scrollTo(0, document.body.scrollHeight/2)')
            page.wait_for_timeout(1000)

            # Try to accept any cookie banners that might be in the way
            try:
                cookie_selectors = [
                    'button:has-text("Accept")',
                    'button:has-text("Accept All")',
                    'button:has-text("Got it")',
                    'button[aria-label*="Accept"]',
                    '#onetrust-accept-btn-handler'
                ]
                for selector in cookie_selectors:
                    try:
                        page.locator(selector).first.click(timeout=1000)
                        page.wait_for_timeout(500)
                    except:
                        continue
            except:
                pass

            # Try expanding content sections
            expand_selectors = [
                'button:has-text("Show more")',
                'button:has-text("See more")',
                'button:has-text("Expand")',
                '[aria-label*="expand"]',
                '[data-testid*="expand"]'
            ]
            for selector in expand_selectors:
                try:
                    elements = page.locator(selector).all()
                    for el in elements:
                        if el.is_visible():
                            el.click()
                            page.wait_for_timeout(500)
                except:
                    continue

            # Extract missing fields from the DOM
            try:
                # Extract address if missing
                if not data.get('address'):
                    address_selectors = [
                        'h1',
                        '[data-testid="property-address"]',
                        '[data-testid="address"]',
                        '[itemprop="streetAddress"]',
                        '[class*="address"]',
                        'h1:has-text("Newton")'
                    ]
                    for selector in address_selectors:
                        try:
                            elements = page.locator(selector).all()
                            for el in elements:
                                if el.is_visible():
                                    text = el.inner_text().strip()
                                    if ',' in text:
                                        text = text.split(',')[0].strip()
                                    if 'Newton' in text and any(x in text.lower() for x in ['street', 'st', 'road', 'rd', 'ave', 'dr', 'ln', 'way']):
                                        data['address'] = text
                                        break
                            if data.get('address'):
                                break
                        except:
                            continue

                # Extract price if missing
                if not data.get('price'):
                    price_selectors = [
                        '[data-testid*="price"]',
                        'span[class*="price"]',
                        'div[class*="price"]'
                    ]
                    for selector in price_selectors:
                        try:
                            elements = page.locator(selector).all()
                            for el in elements:
                                if el.is_visible():
                                    text = el.inner_text()
                                    price_match = re.search(r'\$?([\d,]+)(?:,\d{3})*', text)
                                    if price_match:
                                        data['price'] = price_match.group(1).replace(',', '')
                                        break
                            if data.get('price'):
                                break
                        except:
                            continue

                # Extract beds/baths if missing
                bed_bath_selectors = [
                    '[data-testid="bed-bath-item"]',
                    '[data-testid="facts-list"]',
                    '[class*="home-facts"]',
                    '[class*="summary-list"]'
                ]
                
                for selector in bed_bath_selectors:
                    try:
                        elements = page.locator(selector).all()
                        for el in elements:
                            if el.is_visible():
                                text = el.inner_text().lower()
                                if not data.get('beds') and 'bed' in text:
                                    bed_match = re.search(r'(\d+)\s*(?:bed|br)', text)
                                    if bed_match:
                                        data['beds'] = int(bed_match.group(1))
                                if not data.get('baths') and 'bath' in text:
                                    bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|ba)', text)
                                    if bath_match:
                                        data['baths'] = float(bath_match.group(1))
                                
                                # Break if we found both
                                if data.get('beds') and data.get('baths'):
                                    break
                        if data.get('beds') and data.get('baths'):
                            break
                    except:
                        continue

                # Extract lot size if missing
                if not data.get('lot_size'):
                    lot_size_selectors = [
                        '[data-testid="facts-list"]',
                        '[class*="fact-group"]',
                        '[class*="home-facts"]'
                    ]
                    for selector in lot_size_selectors:
                        try:
                            elements = page.locator(selector).all()
                            for el in elements:
                                if el.is_visible():
                                    text = el.inner_text().lower()
                                    lot_patterns = [
                                        r'lot (?:size|area|dimensions?|sq\.?\s*ft\.?):\s*([\d,]+)',
                                        r'([\d,]+)\s*sq\.?\s*ft\.?\s*lot',
                                        r'lot.*?([\d,]+)\s*sq\.?\s*ft',
                                        r'([\d,.]+)\s*acres?'
                                    ]
                                    for pattern in lot_patterns:
                                        match = re.search(pattern, text)
                                        if match:
                                            value = match.group(1).replace(',', '')
                                            if 'acre' in text:
                                                # Convert acres to square feet
                                                value = str(int(float(value) * 43560))
                                            data['lot_size'] = value
                                            break
                                    if data.get('lot_size'):
                                        break
                            if data.get('lot_size'):
                                break
                        except:
                            continue

            except Exception as e:
                print(f"[zillow] Failed to extract from HTML: {str(e)}")

    except Exception as e:
        print(f"[zillow] Data extraction failed: {str(e)}")

    # Clean and validate data
    if data:
        # Clean address
        if data.get('address'):
            data['address'] = data['address'].strip()
            if ',' in data['address']:
                data['address'] = data['address'].split(',')[0].strip()

        # Clean numeric fields
        for field in ['price', 'lot_size']:
            if data.get(field):
                data[field] = str(data[field]).replace('$', '').replace(',', '')
                # Verify it's numeric
                if not data[field].replace('.', '').isdigit():
                    data[field] = None

        # Convert and validate beds/baths
        try:
            if data.get('beds'):
                data['beds'] = int(str(data['beds']).strip())
            if data.get('baths'):
                data['baths'] = float(str(data['baths']).strip())
        except:
            if 'beds' in data: data['beds'] = None
            if 'baths' in data: data['baths'] = None
            
    return data

def fetch_zillow(city: str) -> pd.DataFrame:
    """
    Fetch property listings from Zillow using Playwright's stealth mode.
    Uses multiple data extraction strategies for reliability.
    """
    data = []
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,  # Run in non-headless mode for better stability
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-web-security',
            ]
        )
        
        # Create context with stealth mode
        context = browser.new_context(
            user_agent=DEFAULT_UA,
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            java_script_enabled=True,
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 42.3371, "longitude": -71.2092},  # Newton, MA coordinates
            permissions=['geolocation'],
            color_scheme='light',
            device_scale_factor=1,
        )
        
        # Stealth mode scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = {
                runtime: {}
            };
        """)
        
        page = context.new_page()
        page.set_default_navigation_timeout(30000)
        page.set_default_timeout(30000)
        
        # Collect property URLs using browser
        urls = []
        for page_url in CITY_PAGES:
            try:
                print(f"[zillow] Fetching listings from {page_url}")
                page.goto(page_url)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                
                # Wait for property cards to load
                page.wait_for_selector('a[href*="/homedetails/"]', timeout=10000)
                
                # Scroll to load more content
                for _ in range(3):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(2000)
                
                # Extract property URLs
                elements = page.locator('a[href*="/homedetails/"]').all()
                for el in elements:
                    try:
                        url = el.get_attribute('href')
                        if url and url.startswith('/'):
                            url = f"https://www.zillow.com{url}"
                        if url:
                            urls.append(url)
                    except:
                        continue
                        
                page.wait_for_timeout(2000)  # Pause between pages
                
            except Exception as e:
                print(f"[zillow] Error fetching listings from {page_url}: {str(e)}")
                continue
        
        # Filter URLs to ensure they're in Newton
        from app.scraper.url_filters import filter_newton_urls
        urls = list(set(filter_newton_urls("zillow", urls)))

        # Process each property
        for url in urls[:20]:
            try:
                print(f"\n[zillow] Fetching {url}")
                
                # Navigate with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        page.goto(url)
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        print(f"[zillow] Retry {attempt + 1} for {url}: {str(e)}")
                        page.wait_for_timeout(2000 * (attempt + 1))

                # Extract property data
                page_data = _extract_data(page)
                
                # Only add if we have all required fields
                if all(page_data.get(field) for field in ['address', 'price', 'beds', 'baths', 'lot_size']):
                    row = {
                        "address": page_data['address'],
                        "city": city,
                        "state": "MA",
                        "price": page_data['price'],
                        "beds": page_data['beds'],
                        "baths": page_data['baths'],
                        "lot_sqft": page_data['lot_size'],
                        "url": url,
                        "source": "zillow"
                    }
                    
                    print(f"[zillow] Extracted: {row['address']} - ${row['price']} - {row['beds']}bd {row['baths']}ba - {row['lot_sqft']}sqft")
                    data.append(row)
                else:
                    missing = [field for field in ['address', 'price', 'beds', 'baths', 'lot_size'] if not page_data.get(field)]
                    print(f"[zillow] Skipping incomplete listing. Missing fields: {', '.join(missing)}")
                
            except Exception as e:
                print(f"[zillow] Failed to process {url}: {str(e)}")
                continue  # Skip this property and continue with the next

            # Short pause between properties
            page.wait_for_timeout(1000)

        # Clean up
        page.close()
        context.close()
        browser.close()

    # Create DataFrame and clean up data
    df = pd.DataFrame(data)
    
    # Convert numeric columns
    for col in ['price', 'beds', 'baths', 'lot_sqft']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Drop any rows with missing required fields
    df = df.dropna(subset=['address', 'price', 'beds', 'baths', 'lot_sqft'])
    
    print(f"[zillow] Scraped {len(df)} complete properties successfully")
    return df