import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any
from app.utils.config_loader import SETTINGS

def calculate_days_on_market(list_date: str) -> int:
    """Calculate days on market from listing date"""
    try:
        list_date = pd.to_datetime(list_date)
        return (datetime.now() - list_date).days
    except:
        return None

def calculate_price_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate price-related metrics"""
    metrics = {}
    try:
        # Price per square foot
        if row.get('living_area') and row.get('price'):
            metrics['price_per_sf'] = float(row['price']) / float(row['living_area'])
        
        # Price relative to assessed value
        if row.get('assessed_value') and row.get('price'):
            metrics['price_to_assessed_ratio'] = float(row['price']) / float(row['assessed_value'])
            
    except (ValueError, TypeError):
        pass
    return metrics

def extract_condition_keywords(description: str) -> list:
    """Extract condition-related keywords from description"""
    CONDITION_KEYWORDS = [
        'needs work', 'as is', 'fixer', 'handyman', 'TLC',
        'potential', 'opportunity', 'renovate', 'update',
        'remodel', 'original condition', 'dated'
    ]
    
    found_keywords = []
    if description:
        description = description.lower()
        for keyword in CONDITION_KEYWORDS:
            if keyword in description:
                found_keywords.append(keyword)
    return found_keywords

def enrich_property_data(df: pd.DataFrame) -> pd.DataFrame:
    """Main function to enrich property data with additional fields"""
    if df is None or df.empty:
        return df
        
    enriched = df.copy()
    
    # Add market indicators
    enriched['days_on_market'] = enriched['list_date'].apply(calculate_days_on_market)
    
    # Calculate price metrics
    price_metrics = enriched.apply(calculate_price_metrics, axis=1)
    enriched['price_per_sf'] = price_metrics.apply(lambda x: x.get('price_per_sf'))
    enriched['price_to_assessed_ratio'] = price_metrics.apply(lambda x: x.get('price_to_assessed_ratio'))
    
    # Extract condition keywords
    enriched['condition_keywords'] = enriched['description'].apply(extract_condition_keywords)
    
    # Calculate property age if year_built exists
    enriched['property_age'] = None
    if 'year_built' in enriched.columns:
        current_year = datetime.now().year
        enriched['property_age'] = enriched['year_built'].apply(
            lambda x: current_year - int(x) if pd.notnull(x) else None
        )
    
    # Add buildable area calculation based on FAR
    if 'lot_sqft' in enriched.columns and 'far_ratio' in enriched.columns:
        enriched['max_buildable_sf'] = enriched.apply(
            lambda row: float(row['lot_sqft']) * float(row['far_ratio'])
            if pd.notnull(row['lot_sqft']) and pd.notnull(row['far_ratio'])
            else None,
            axis=1
        )
    
    return enriched