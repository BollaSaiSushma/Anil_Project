# app/nlp/openai_classifier.py  (NEW SDK STYLE)
import json
import pandas as pd
from openai import OpenAI
from app.utils.config_loader import SETTINGS

client = OpenAI(api_key=SETTINGS.openai_key)

KEYWORDS = ["tear down", "teardown", "builder", "contractor special", "development opportunity"]

def _keyword_list(text: str):
    t = (text or "").lower()
    return [k for k in KEYWORDS if k in t]

def classify_properties(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    rows = []
    for _, r in df.fillna("").iterrows():
        text = r.get("snippet") or " ".join([
            str(r.get("address") or ""), str(r.get("city") or ""), str(r.get("state") or "")
        ])

        if not SETTINGS.openai_key:
            kws = _keyword_list(text)
            rows.append({
                **r.to_dict(),
                "label": "HIGH" if kws else "LOW",
                "explanation": "No OPENAI_API_KEY loaded; keyword-only fallback.",
            })
            continue

        try:
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": (
                        "Classify redevelopment potential. Detect phrases like "
                        "'tear down', 'builder', 'contractor special', 'development opportunity'. "
                        "Return STRICT JSON: {\"label\":\"HIGH|MEDIUM|LOW\",\"reason\":\"...\"}.\n\n"
                        f"TEXT:\n{text[:6000]}"
                    ),
                }],
            )
            content = resp.choices[0].message.content
            data = json.loads(content)
            label = str(data.get("label", "LOW")).upper()
            reason = str(data.get("reason", ""))[:300]
        except Exception as e:
            label = "LOW"
            reason = f"LLM error: {e}"

        rows.append({
            **r.to_dict(),
            "label": label,
            "explanation": reason,
        })

    return pd.DataFrame(rows)
