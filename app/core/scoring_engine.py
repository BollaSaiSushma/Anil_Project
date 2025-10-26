import pandas as pd

def add_opportunity_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["opportunity_score"] = (
        out.get("development_score", 0).fillna(0) * 0.7
        + out.get("has_keywords", False).astype(int) * 20
    )
    return out
