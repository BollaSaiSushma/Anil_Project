import re
import requests
import pandas as pd
from app.scraper.browser_fetch import harvest_many
from app.scraper.url_filters import filter_newton_urls

class RedfinScraper:
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self.headers = {"User-Agent": self.DEFAULT_UA}

    def _match_first(self, html: str, patterns: list[str]):
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                return m
        return None

    def parse_property_page(self, html: str) -> dict:
        """Parse a single Redfin property page HTML and extract property details."""
        # address
        addr_patterns = [
                r'"streetLine":"([^"]+)"',
                r'"streetAddress":"([^"]+)"',
                r'"fullAddress":"([^"]+)"',
                r'<h1[^>]*>([^<]+?(?=\s*\$|\s*\||\s*$))',
                r'<title>([^|]+?)(?=\s*\$|\s*\|)',
                r'<span[^>]*>Address:\s*([^<]+)',
                r'<div[^>]*>([^<]+?(?:Street|Road|Avenue|Lane|Drive|Place|Circle|Court|Terrace|Way)[^<]*)</div>'
            ]
        addr_m = None
        for pattern in addr_patterns:
            addr_m = re.search(pattern, html, re.IGNORECASE)
            if addr_m:
                break
        address_value = addr_m.group(1).strip() if addr_m else None

        # price (normalized as string like "1,250,000")
        price_m = self._match_first(html, [
            r'"price":\s*"?\$?([\d,]+)"?',
            r'"homePrice":\s*"?\$?([\d,]+)"?',
            r'<div[^>]*>Price:\s*\$?([\d,]+)',
            r'\$([0-9,]+)',
            r'([0-9,]+)\s*dollars'
        ])
        price_value = price_m.group(1).replace(',', '') if price_m else None

        # optional details
        beds_patterns = [
            r'"beds":\s*"?(\d+)"?',
            r'"bedrooms":\s*"?(\d+)"?',
            r'<span[^>]*>(\d+)\s*(?:Beds|Bedrooms)',
            r'(\d+)\s*(?:Beds|Bedrooms)',
            r'(\d+)\s*(?:BR|bed)',
            r'Beds:\s*(\d+)'
        ]
        baths_patterns = [
            r'"baths":\s*"?(\d+(?:\.\d+)?)"?',
            r'"bathrooms":\s*"?(\d+(?:\.\d+)?)"?',
            r'<span[^>]*>(\d+(?:\.\d+)?)\s*(?:Baths|Bathrooms)',
            r'(\d+(?:\.\d+)?)\s*(?:Baths|Bathrooms)',
            r'(\d+(?:\.\d+)?)\s*(?:BA|bath)',
            r'Baths:\s*(\d+(?:\.\d+)?)'
        ]
        lot_patterns = [
            r'"lotSize":\s*"?(\d+(?:,\d+)?)"?',
            r'"lotSqft":\s*"?(\d+(?:,\d+)?)"?',
            r'Lot Size:\s*([\d,]+)',
            r'(\d+(?:,\d+)?)\s*sq\s*ft\s*lot',
            r'Lot:\s*([\d,]+)\s*sq\s*ft',
            r'Lot Size \(sq ft\):\s*([\d,]+)',
            r'(\d+(?:,\d+)?)\s*Square Feet'
        ]
        
        beds_m = None
        baths_m = None
        lot_m = None
        
        for pattern in beds_patterns:
            beds_m = re.search(pattern, html)
            if beds_m:
                break
                
        for pattern in baths_patterns:
            baths_m = re.search(pattern, html)
            if baths_m:
                break
                
        for pattern in lot_patterns:
            lot_m = re.search(pattern, html)
            if lot_m:
                break

        return {
            "address": address_value,
            "price": price_value,  # string like "1,250,000" is OK
            "beds": int(beds_m.group(1)) if beds_m else None,
            "baths": float(baths_m.group(1)) if baths_m else None,
            "lot_sqft": int(lot_m.group(1).replace(',', '')) if lot_m else None
        }
