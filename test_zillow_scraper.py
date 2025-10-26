import unittest
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError
from app.scraper.zillow_scraper_simple import _extract_data, fetch_zillow

class TestZillowScraper(unittest.TestCase):
    def test_data_extraction(self):
        """Test the data extraction function with sample HTML."""
        test_html = '''
        {
            "streetAddress": "123 Test St",
            "price": "$599,000",
            "bedrooms": "4",
            "bathrooms": "2.5",
            "lotSize": {
                "value": "7500"
            }
        }
        <h1>123 Test St, Newton</h1>
        '''
        
        data = _extract_data(test_html)
        
        # Test data presence and format
        self.assertEqual(data['address'], "123 Test St")
        self.assertEqual(data['price'], "599000")
        self.assertEqual(data['beds'], 4)
        self.assertEqual(data['baths'], 2.5)
        self.assertEqual(data['lot_size'], "7500")
        
    def test_edge_cases(self):
        """Test edge cases in data extraction."""
        # Test missing data
        incomplete_html = '''
        {
            "streetAddress": "456 Test St",
            "price": "$699,000"
        }
        '''
        data = _extract_data(incomplete_html)
        self.assertEqual(data['address'], "456 Test St")
        self.assertEqual(data['price'], "699000")
        self.assertIsNone(data.get('beds'))
        self.assertIsNone(data.get('baths'))
        self.assertIsNone(data.get('lot_size'))
        
        # Test alternative formats
        alt_format_html = '''
        <h1>789 Test St, Newton, MA</h1>
        <span>$799,000</span>
        4 bed 3 bath
        Lot: 8,500 sqft
        '''
        data = _extract_data(alt_format_html)
        self.assertEqual(data['address'], "789 Test St")
        self.assertEqual(data['price'], "799000")
        self.assertEqual(data['beds'], 4)
        self.assertEqual(data['baths'], 3)
        self.assertEqual(data['lot_size'], "8500")
        
    def test_fetch_zillow_integration(self):
        """Test the complete fetch_zillow function."""
        df = fetch_zillow("Newton")
        
        # Test DataFrame structure
        self.assertIsInstance(df, pd.DataFrame, "Result should be a DataFrame")
        self.assertFalse(df.empty, "DataFrame should not be empty")
        
        # Test required columns
        required_cols = ['address', 'city', 'state', 'price', 'beds', 'baths', 'lot_sqft', 'url']
        for col in required_cols:
            self.assertIn(col, df.columns, f"Missing required column: {col}")
        
        # Test data validity
        self.assertTrue(df['city'].eq('Newton').all(), "All properties should be in Newton")
        self.assertTrue(df['state'].eq('MA').all(), "All properties should be in MA")
        self.assertTrue(df['url'].str.contains('zillow.com').all(), 
                       "All URLs should be from Zillow")
        
        # Test numeric columns
        numeric_cols = ['price', 'beds', 'baths', 'lot_sqft']
        for col in numeric_cols:
            self.assertTrue(pd.to_numeric(df[col], errors='coerce').notna().any(),
                          f"{col} should contain valid numeric values")

if __name__ == '__main__':
    unittest.main(verbose=True)