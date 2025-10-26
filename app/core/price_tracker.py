import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, Optional
from app.utils.config_loader import SETTINGS
from app.utils.logger import logger

class PriceTracker:
    def __init__(self, history_file: str = "data/price_history.json"):
        self.history_file = Path(history_file)
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """Load price history from JSON file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Error loading price history file")
                return {}
        return {}
    
    def _save_history(self) -> None:
        """Save price history to JSON file"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def track_price_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Track price changes for properties"""
        if df is None or df.empty:
            return df
            
        result = df.copy()
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Initialize new columns
        result['price_change'] = 0.0
        result['price_change_pct'] = 0.0
        result['days_since_change'] = 0
        result['price_history'] = None
        
        for idx, row in result.iterrows():
            url = row.get('url')
            current_price = float(row.get('price', 0))
            
            if not url or current_price == 0:
                continue
                
            # Get property history
            prop_history = self.history.get(url, {})
            
            # Update history with current price
            if not prop_history or prop_history.get('latest_price') != current_price:
                if prop_history:
                    # Calculate changes
                    previous_price = float(prop_history.get('latest_price', 0))
                    if previous_price > 0:
                        price_change = current_price - previous_price
                        price_change_pct = (price_change / previous_price) * 100
                        result.at[idx, 'price_change'] = price_change
                        result.at[idx, 'price_change_pct'] = price_change_pct
                
                # Update history
                if not prop_history:
                    prop_history = {
                        'initial_price': current_price,
                        'initial_date': current_date,
                        'price_history': []
                    }
                
                prop_history['price_history'].append({
                    'date': current_date,
                    'price': current_price
                })
                prop_history['latest_price'] = current_price
                prop_history['latest_date'] = current_date
                
                self.history[url] = prop_history
            
            # Add history to DataFrame
            result.at[idx, 'price_history'] = json.dumps(prop_history.get('price_history', []))
            
            # Calculate days since last change
            if prop_history.get('latest_date'):
                latest_date = datetime.strptime(prop_history['latest_date'], "%Y-%m-%d")
                result.at[idx, 'days_since_change'] = (datetime.now() - latest_date).days
        
        # Save updated history
        self._save_history()
        
        return result

# Initialize global price tracker
price_tracker = PriceTracker()