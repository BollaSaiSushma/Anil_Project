import pandas as pd
from app.classifier.llm_classifier import run_classifier
from app.integrations.roi_calculator import enrich_with_roi
from app.utils.config_loader import SETTINGS

def test_property_classification():
    print("=== Testing Property Classification System ===\n")
    
    # Create a sample property dataset
    test_properties = pd.DataFrame([
        {
            "address": "123 Development St",
            "city": "Newton",
            "state": "MA",
            "price": "750000",
            "beds": 2,
            "baths": 1,
            "lot_sqft": 8000,
            "url": "https://example.com/property1",
            "source": "test",
            "snippet": "ATTENTION DEVELOPERS! Prime tear-down opportunity in desirable Newton location. Existing structure on oversized 8,000 sq ft lot. Zoned for multi-family development. Perfect for builders or contractors looking to maximize potential. Property sold as-is. Great opportunity for new construction.",
        },
        {
            "address": "456 Builder Way",
            "city": "Newton",
            "state": "MA",
            "price": "850000",
            "beds": 3,
            "baths": 2,
            "lot_sqft": 6500,
            "url": "https://example.com/property2",
            "source": "test",
            "snippet": "Contractor special! This property needs complete renovation or potential teardown. Large 6,500 sq ft corner lot offers excellent development opportunity. Current zoning allows for duplex construction. Selling as-is, perfect for experienced builders.",
        },
        {
            "address": "789 Regular Ave",
            "city": "Newton",
            "state": "MA",
            "price": "950000",
            "beds": 4,
            "baths": 3,
            "lot_sqft": 3500,
            "url": "https://example.com/property3",
            "source": "test",
            "snippet": "Beautiful well-maintained colonial home with modern updates. Move-in ready with new kitchen and bathrooms. Hardwood floors throughout, central AC, and professionally landscaped yard. Perfect for families!",
        }
    ])
    
    print("Test Properties:")
    print(test_properties[["address", "price", "lot_sqft"]].to_string())
    print("\n1. Running NLP Classification...")
    
    try:
        # Run classification
        classified = run_classifier(test_properties)
        print("\nClassification Results:")
        print(classified[["address", "label", "explanation"]].to_string())
        
        # Run ROI calculations
        print("\n2. Calculating ROI Metrics...")
        with_roi = enrich_with_roi(classified)
        
        print("\nFinal Results (with ROI):")
        display_cols = ["address", "label", "dev_cost", "resale_value", "profit", "roi_percentage", "roi_score"]
        print(with_roi[display_cols].to_string())
        
        return True
        
    except Exception as e:
        print("\n❌ Classification Test Failed!")
        print("Error:", str(e))
        return False

if __name__ == "__main__":
    test_property_classification()