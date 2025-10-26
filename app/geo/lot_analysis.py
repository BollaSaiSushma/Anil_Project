import pandas as pd

def estimate_buildable_sf(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["buildable_sf"] = (out.get("lot_sqft", 0) * 0.35).fillna(0)  # 35% rule of thumb
    return out
