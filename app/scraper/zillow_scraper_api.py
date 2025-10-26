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

def _extract_data(page) -> dict:
    """Extract property data from various sources using a multi-layered approach."""
    data = {}
    
    try:
        # Wait for critical content to load
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_selector('h1', timeout=10000)
        
        # Scroll to trigger lazy loading
        page.evaluate('window.scrollTo(0, document.body.scrollHeight/2)')
        page.wait_for_timeout(2000)
        
        # 1. Extract address - multiple attempts with different selectors
        address_selectors = [
            'h1[class*="address"]',
            '[data-testid="property-address"]',
            '[data-testid="address"]',
            '[class*="Address"]',
            'h1'
        ]
        
        for selector in address_selectors:
            try:
                element = page.locator(selector).first
                if element and element.is_visible():
                    text = element.inner_text().strip()
                    if text and ('Newton' in text or any(x in text.lower() for x in ['st', 'rd', 'ave', 'dr', 'ln'])):
                        if ',' in text:
                            text = text.split(',')[0].strip()
                        data['address'] = text
                        break
            except:
                continue
                
        # 2. Extract price - multiple patterns
        price_selectors = [
            '[data-testid="price"]',
            '[class*="Price"]',
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

        # 3. Extract beds/baths
        summary_selectors = [
            '[data-testid="bed-bath-living-area-container"]',
            '[data-testid="bed-bath-item"]',
            '[class*="bed-bath-summary"]',
            '[class*="summary-container"]'
        ]

        for selector in summary_selectors:
            try:
                summary = page.locator(selector).first
                if summary and summary.is_visible():
                    text = summary.inner_text().lower()
                    
                    # Extract beds
                    bed_match = re.search(r'(\d+)\s*(?:bed|br)', text)
                    if bed_match:
                        data['beds'] = int(bed_match.group(1))
                    
                    # Extract baths
                    bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|ba)', text)
                    if bath_match:
                        data['baths'] = float(bath_match.group(1))
                        
                    if data.get('beds') and data.get('baths'):
                        break
            except:
                continue

        # 4. Extract lot size
        facts_selectors = [
            '[data-testid="facts-container"]',
            '[class*="facts-container"]',
            '[class*="fact-group"]',
            '[class*="home-facts"]'
        ]
        
        for selector in facts_selectors:
            try:
                facts = page.locator(selector).first
                if facts and facts.is_visible():
                    text = facts.inner_text().lower()
                    
                    # Try different lot size patterns
                    lot_patterns = [
                        r'lot (?:size|area):\s*([\d,]+)\s*(?:square\s*feet|sq\s*ft|sf)',
                        r'lot.*?([\d,]+)\s*(?:square\s*feet|sq\s*ft|sf)',
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
            except:
                continue
                
        # 5. Fallback to script data if needed
        if not all(key in data for key in ['address', 'price', 'beds', 'baths', 'lot_size']):
            try:
                script_data = page.evaluate('''() => {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                    for (const script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            if (data['@type'] === 'SingleFamilyResidence' || data['@type'] === 'House') {
                                return data;
                            }
                        } catch {}
                    }
                    return null;
                }''')
                
                if script_data:
                    if not data.get('address') and script_data.get('address'):
                        data['address'] = script_data['address'].get('streetAddress')
                    if not data.get('price') and script_data.get('price'):
                        data['price'] = str(script_data['price']).replace('$', '').replace(',', '')
                    if not data.get('beds') and script_data.get('numberOfBedrooms'):
                        data['beds'] = int(script_data['numberOfBedrooms'])
                    if not data.get('baths') and script_data.get('numberOfBathrooms'):
                        data['baths'] = float(script_data['numberOfBathrooms'])
                    if not data.get('lot_size') and script_data.get('lotSize'):
                        lot_size = script_data['lotSize']
                        if isinstance(lot_size, dict) and lot_size.get('value'):
                            data['lot_size'] = str(lot_size['value'])
            except:
                pass

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
                if not data[field].replace('.', '').isdigit():
                    data[field] = None

        # Validate beds/baths
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
    Fetch property listings from Zillow using API search and Playwright for details.
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
        
        # Create page for property details
        page = context.new_page()
        page.set_default_navigation_timeout(30000)
        page.set_default_timeout(30000)
        
        # Search API parameters for Newton, MA
        search_payload = {
            "query": "Newton, MA",
            "page": 1,
            "pageSize": 40,
            "filterState": {
                "sortSelection": {"value": "globalrelevanceex"},
                "isAllHomes": {"value": True},
                "isForRent": {"value": False}
            },
            "wants": {
                "cat1": ["listResults"]
            },
            "requestId": 1
        }
        
        try:
            # Get search results from API
            api_url = 'https://www.zillow.com/search/GetSearchPageState.htm'
            api_response = requests.get(
                api_url,
                params={
                    'searchQueryState': json.dumps(search_payload),
                    'wants': json.dumps({"cat1": ["listResults"]}),
                    'requestId': 1
                },
                headers=API_HEADERS
            )
            
            if api_response.status_code == 200:
                api_data = api_response.json()
                results = api_data.get('cat1', {}).get('searchResults', {}).get('listResults', [])
                
                # Process each property from search results
                for result in results[:20]:  # Limit to first 20 results
                    try:
                        # Skip if not in Newton
                        if not result.get('address', '').startswith('Newton'):
                            continue
                            
                        url = result.get('detailUrl')
                        if not url:
                            continue
                            
                        if not url.startswith('http'):
                            url = f"https://www.zillow.com{url}"
                            
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
                        
                        # Short pause between properties
                        page.wait_for_timeout(1000)
                        
                    except Exception as e:
                        print(f"[zillow] Failed to process {url}: {str(e)}")
                        continue
            else:
                print(f"[zillow] API request failed with status {api_response.status_code}")
                
        except Exception as e:
            print(f"[zillow] Error fetching search results: {str(e)}")

        # Clean up
        try:
            page.close()
            context.close()
            browser.close()
        except:
            pass

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