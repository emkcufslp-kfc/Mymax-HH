"""
Fix BAD_PRICE: drop rows where ALL of Open/High/Low/Close are zero or negative.
These are genuine no-trade days (halted/disposition stocks) from TWSE source.
Also drops duplicate dates.

NOTE: We DROP zero rows (not forward-fill) because forward-filling a halted
stock creates false price continuity and distorts pivot high calculations.
"""
import pandas as pd
from pathlib import Path

RAW_DIR = Path(r"D:\Claude projects\主觀看盤\data\raw")
PRICE_COLS = ["Open", "High", "Low", "Close"]

csv_files = sorted(RAW_DIR.glob("*.csv"))
fixed = 0
skipped = 0
total_dropped = 0

for f in csv_files:
    symbol = f.stem
    try:
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        date_col = df.columns[0]

        before = len(df)

        # Drop rows where ALL available price cols are zero/negative
        cols_present = [c for c in PRICE_COLS if c in df.columns]
        if cols_present:
            all_zero = pd.Series([True] * len(df), index=df.index)
            for col in cols_present:
                all_zero = all_zero & (df[col] <= 0)
            df = df[~all_zero]

        # Drop duplicate dates (keep last)
        df = df.drop_duplicates(subset=[date_col], keep="last")
        df = df.sort_values(date_col).reset_index(drop=True)

        after = len(df)
        dropped = before - after

        if dropped == 0:
            skipped += 1
            continue

        df.to_csv(f, index=False)
        total_dropped += dropped
        print(f"  {symbol}: dropped {dropped} no-trade rows ({after} remain)")
        fixed += 1

    except Exception as e:
        print(f"  {symbol}: ERROR {e}")

print(f"\nDone! Files fixed={fixed}, Skipped (clean)={skipped}, Total rows dropped={total_dropped}")
