# app/nlp/openai_classifier.py
import os
import openai
import pandas as pd
from app.utils.config_loader import SETTINGS

openai.api_key = SETTINGS.openai_key

KEYWORDS = ["tear down", "builder", "contractor special", "development opportunity"]

def classify_properties(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        print("⚠️ No data to classify.")
        return df

    df["has_keywords"] = df["url"].astype(str).str.lower().apply(
        lambda x: any(k in x for k in KEYWORDS)
    )

    results = []
    for _, row in df.iterrows():
        try:
            prompt = (
                f"Analyze this property listing text: {row.get('address','')} in "
                f"{row.get('city','')}.\n"
                "Does this appear to be a redevelopment opportunity (tear down, builder, contractor special, "
                "development opportunity)? Respond with JSON like "
                '{"label": "HIGH/MEDIUM/LOW", "reason": "..."}'
            )
            completion = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = completion.choices[0].message["content"]
            label = "LOW"
            reason = ""
            if "HIGH" in content.upper():
                label = "HIGH"
            elif "MEDIUM" in content.upper():
                label = "MEDIUM"
            elif "LOW" in content.upper():
                label = "LOW"
            reason = content.strip()
        except Exception as e:
            label = "LOW"
            reason = f"Error: {e}"

        results.append({"label": label, "explanation": reason})

    res_df = pd.DataFrame(results)
    merged = pd.concat([df.reset_index(drop=True), res_df], axis=1)
    return merged
