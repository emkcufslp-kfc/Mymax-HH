import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

RAW_DIR = Path("D:\\Claude projects\\") / "主觀看盤" / "data" / "raw"
TODAY = datetime.today().strftime("%Y-%m-%d")
EXPECTED_END = "2026-05-13"  # known last update before yfinance run

issues = []

csv_files = sorted(RAW_DIR.glob("*.csv"))
print(f"Checking {len(csv_files)} tickers...\n")

for f in csv_files:
    symbol = f.stem
    try:
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).reset_index(drop=True)

        last_date = df[date_col].max().strftime("%Y-%m-%d")
        row_count = len(df)

        # Check 1: stale data
        if last_date < "2026-05-01":
            issues.append((symbol, "STALE", f"last={last_date}"))
            continue

        # Check 2: missing recent data (should be >= 2026-05-13)
        if last_date < EXPECTED_END:
            issues.append((symbol, "OUTDATED", f"last={last_date}, expected>={EXPECTED_END}"))
            continue

        # Check 3: duplicate dates
        dupes = df[date_col].duplicated().sum()
        if dupes > 0:
            issues.append((symbol, "DUPLICATES", f"{dupes} duplicate dates"))

        # Check 4: large gaps (>10 calendar days between rows, excluding known holidays)
        df["next"] = df[date_col].shift(-1)
        df["gap"] = (df["next"] - df[date_col]).dt.days
        big_gaps = df[df["gap"] > 10].dropna()
        if not big_gaps.empty:
            for _, row in big_gaps.iterrows():
                issues.append((symbol, "GAP", f"{row[date_col].date()} -> {row['next'].date()} ({int(row['gap'])} days)"))

        # Check 5: NaN in OHLCV
        ohlcv = ["Open", "High", "Low", "Close", "Volume"]
        for col in ohlcv:
            if col in df.columns:
                nan_count = df[col].isna().sum()
                if nan_count > 0:
                    issues.append((symbol, "NAN", f"{nan_count} NaN in {col}"))

        # Check 6: zero/negative prices
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                bad = (df[col] <= 0).sum()
                if bad > 0:
                    issues.append((symbol, "BAD_PRICE", f"{bad} zero/neg in {col}"))

    except Exception as e:
        issues.append((symbol, "READ_ERROR", str(e)))

# Report
if not issues:
    print("All tickers OK!")
else:
    print(f"Found {len(issues)} issues:\n")
    print(f"{'Ticker':<10} {'Type':<15} {'Detail'}")
    print("-" * 60)
    for sym, itype, detail in issues:
        print(f"{sym:<10} {itype:<15} {detail}")

# Summary by type
from collections import Counter
type_counts = Counter(t for _, t, _ in issues)
print(f"\nSummary: {dict(type_counts)}")
