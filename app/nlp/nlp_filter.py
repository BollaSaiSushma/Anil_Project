import pandas as pd
def filter_candidates(df: pd.DataFrame) -> pd.DataFrame:
    return df.reset_index(drop=True)  # TEMP: no downstream filtering
