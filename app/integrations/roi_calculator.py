# app/integrations/roi_calculator.py
import pandas as pd
import numpy as np

def _to_num(s):
    # handles "$1,234,000", "1,234,000", None, ""
    if s is None:
        return np.nan
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(",", "").replace("$", "")
    try:
        return float(s)
    except Exception:
        return np.nan

def enrich_with_roi(
    df: pd.DataFrame,
    *,
    default_buildable_sf: float = 2000.0,
    hard_cost_per_sf: float = 275.0,
    soft_cost_pct: float = 0.15,
    resale_price_per_sf: float = 550.0
) -> pd.DataFrame:
    """
    Computes:
      dev_cost       = land_cost + hard_cost + soft_cost
      resale_value   = buildable_sf * resale_price_per_sf
      profit         = resale_value - dev_cost
      roi_percentage = profit / dev_cost * 100
      roi_score      = clamp(roi_percentage/2, 0..100)

    Inputs expected:
      price (land acquisition), buildable_sf (optional)
    """

    if df is None or df.empty:
        return df

    out = df.copy()

    # 1) Numeric price
    out["price_num"] = out.get("price").apply(_to_num) if "price" in out.columns else np.nan

    # 2) Buildable SF
    if "buildable_sf" not in out.columns:
        out["buildable_sf"] = default_buildable_sf
    else:
        out["buildable_sf"] = pd.to_numeric(out["buildable_sf"], errors="coerce").fillna(default_buildable_sf)

    # 3) Costs
    land_cost = out["price_num"].fillna(0.0)
    hard_cost = out["buildable_sf"] * float(hard_cost_per_sf)
    soft_cost = (land_cost + hard_cost) * float(soft_cost_pct)
    dev_cost  = land_cost + hard_cost + soft_cost

    # 4) Resale value
    resale_value = out["buildable_sf"] * float(resale_price_per_sf)

    # 5) Profit and ROI
    profit = resale_value - dev_cost
    with np.errstate(divide="ignore", invalid="ignore"):
        roi_percentage = (profit / dev_cost) * 100.0
    roi_percentage = roi_percentage.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    roi_score = (roi_percentage / 2.0).clip(0, 100).round(0).astype(int)

    # 6) Assign outputs
    out["dev_cost"] = dev_cost.round(2)
    out["resale_value"] = resale_value.round(2)
    out["profit"] = profit.round(2)
    out["roi_percentage"] = roi_percentage.round(2)
    out["roi_score"] = roi_score

    # Optional: drop helper
    out.drop(columns=[c for c in ["price_num"] if c in out.columns], inplace=True)

    return out
