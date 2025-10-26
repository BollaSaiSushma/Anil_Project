import pandas as pd

KEYWORDS = ["tear-down", "zoned multi", "corner lot", "subdivide"]

def add_keyword_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["has_keywords"] = False

    for kw in KEYWORDS:
        df["has_keywords"] = df["has_keywords"] | df.fillna(" ").apply(
            lambda r: kw in str(r.values).lower(), axis=1
        )

    return df
