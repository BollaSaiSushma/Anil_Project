# app/classifier/llm_classifier.py

import os
import pandas as pd
from openai import OpenAI

# Import your NLP modules
from app.nlp.openai_classifier import classify_properties
from app.nlp.keyword_detector import add_keyword_flags
from app.nlp.nlp_filter import filter_candidates

# Initialize OpenAI client (uses .env or environment variable)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run_classifier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full NLP classification pipeline:
    1) LLM classification using OpenAI API
    2) Keyword-based detection of phrases like
       'tear down', 'builder', 'contractor special', 'development opportunity'
    3) Filtering to keep only relevant development opportunities
    """
    if df is None or df.empty:
        print("Empty DataFrame received — skipping NLP classification.")
        return df

    # Step 1: Run LLM-based classification
    print("Running OpenAI LLM classification...")
    classified = classify_properties(df)

    # Step 2: Add keyword flags
    print("Adding keyword detection flags...")
    with_flags = add_keyword_flags(classified)

    # Step 3: Filter by NLP confidence or keyword relevance
    print("Filtering top candidate properties...")
    final_df = filter_candidates(with_flags)

    print(f"NLP Classification completed. Final rows: {len(final_df)}")
    return final_df
