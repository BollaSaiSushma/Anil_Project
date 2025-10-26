import pandas as pd
REQUIRED = ["address","city","state","price","beds","baths","lot_sqft","url"]

def merge_sources(sources: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [s for s in sources if s is not None and not s.empty]
    if not frames:
        return pd.DataFrame(columns=REQUIRED)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    for c in REQUIRED:
        if c not in df.columns: df[c] = None
    for nc in ("price","beds","baths","lot_sqft"):
        df[nc] = pd.to_numeric(df[nc], errors="coerce")
    return df[REQUIRED]
