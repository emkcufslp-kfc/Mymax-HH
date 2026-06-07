"""
update_price_db_v2.py

Dual-source TW price database updater:
  - Primary:  FinMind TaiwanStockPrice (raw, direct from TWSE) -- for date coverage
  - Adjusted: yfinance with auto_adjust=True (for correct pivot high / strategy signals)

Zero-OHLCV rows (Trading_Volume=0 and close=0) are genuine no-trade days
(disposition stocks / halted trading) and are DROPPED from the database.

Workflow:
  Step 1: Scan signal JSONs for new tickers not in DB -> full download (2015-01-05 to today)
  Step 2: Update all existing tickers from last_date+1 to today
  Step 3: Drop zero-price rows in any file that was touched
  Step 4: Remove duplicate dates

Source selection per ticker:
  - Try yfinance first (adjusted)
  - If yfinance returns insufficient data, fall back to FinMind (raw)
"""

import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# ============================================================
RAW_DIR = Path(r"D:\Claude projects\主觀看盤\data\raw")
SIGNAL_DIR = Path(r"D:\Backtest\mymax21\data\downloads\daily_top10_volume_gt1000")
DB_START = "2015-01-05"
TODAY = datetime.today().strftime("%Y-%m-%d")
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
SLEEP_YF = 0.3
SLEEP_FM = 0.25
# ============================================================


def find_raw_dir() -> Path:
    if RAW_DIR.exists():
        return RAW_DIR
    raise FileNotFoundError(f"Cannot find raw data directory: {RAW_DIR}")


# ─────────────────────────────────────────────────────────────
# FinMind helpers
# ─────────────────────────────────────────────────────────────
def finmind_download(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Download from FinMind TaiwanStockPrice. Returns DataFrame or empty."""
    try:
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": symbol,
            "start_date": start,
            "end_date": end,
        }
        r = requests.get(FINMIND_URL, params=params, timeout=20)
        data = r.json()
        rows = data.get("data", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        # Rename columns to match our schema
        df = df.rename(columns={
            "date": "Date",
            "max": "High",
            "min": "Low",
            "open": "Open",
            "close": "Close",
            "Trading_Volume": "Volume",
        })
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        # Drop no-trade rows (halted stocks): all OHLC = 0
        df = df[~((df["Open"] <= 0) & (df["High"] <= 0) &
                  (df["Low"] <= 0) & (df["Close"] <= 0))]
        df = df.sort_values("Date").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# yfinance helpers
# ─────────────────────────────────────────────────────────────
def yf_download(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Download from yfinance (adjusted). Returns DataFrame or empty."""
    try:
        yf_symbol = f"{symbol}.TW"
        df = yf.download(yf_symbol, start=start, end=end,
                         auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        # Drop rows where all OHLC = 0 (yfinance artifact)
        df = df[~((df["Open"] <= 0) & (df["High"] <= 0) &
                  (df["Low"] <= 0) & (df["Close"] <= 0))]
        df = df.sort_values("Date").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# Core operations
# ─────────────────────────────────────────────────────────────
def clean_existing(df: pd.DataFrame) -> pd.DataFrame:
    """Drop zero-price rows and duplicate dates from an existing DataFrame."""
    date_col = df.columns[0]
    # Drop rows where all OHLC are zero/negative
    price_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
    if price_cols:
        mask = pd.Series([True] * len(df), index=df.index)
        for col in price_cols:
            mask = mask & (df[col] <= 0)
        df = df[~mask]
    # Drop duplicate dates
    df = df.drop_duplicates(subset=[date_col], keep="last")
    df = df.sort_values(date_col).reset_index(drop=True)
    return df


def download_full(symbol: str, csv_path: Path) -> str:
    """Full download from DB_START to TODAY. Try yfinance first, then FinMind."""
    # Try yfinance
    time.sleep(SLEEP_YF)
    df = yf_download(symbol, DB_START, TODAY)
    source = "yfinance"

    # Fall back to FinMind if yfinance gave fewer than 100 rows
    if len(df) < 100:
        time.sleep(SLEEP_FM)
        df_fm = finmind_download(symbol, DB_START, TODAY)
        if len(df_fm) > len(df):
            df = df_fm
            source = "FinMind"

    if df.empty:
        return f"  {symbol}: no data from either source"

    df.to_csv(csv_path, index=False)
    return (f"  {symbol}: NEW {source} {len(df)} rows "
            f"{df.iloc[0]['Date']} -> {df.iloc[-1]['Date']} OK")


def update_existing(csv_path: Path) -> str:
    """Append new rows since last date. Also clean any existing zero rows."""
    symbol = csv_path.stem
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

        # Clean existing zeros/dupes
        before_rows = len(df)
        df = clean_existing(df)
        cleaned = before_rows - len(df)

        last_date = df[date_col].max()
        start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")

        if start_date >= TODAY:
            suffix = f" (cleaned {cleaned} bad rows)" if cleaned else ""
            return f"  {symbol}: up to date ({last_date.date()}){suffix}"

        # Try yfinance first
        time.sleep(SLEEP_YF)
        new = yf_download(symbol, start_date, TODAY)
        source = "yf"

        # Fall back to FinMind if yfinance has nothing
        if new.empty:
            time.sleep(SLEEP_FM)
            new = finmind_download(symbol, start_date, TODAY)
            source = "FinMind"

        if new.empty:
            suffix = f" (cleaned {cleaned})" if cleaned else ""
            df[date_col] = df[date_col].dt.strftime("%Y-%m-%d")
            df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
            df.to_csv(csv_path, index=False)
            return f"  {symbol}: no new data (last={last_date.date()}){suffix}"

        # Merge
        df[date_col] = df[date_col].dt.strftime("%Y-%m-%d")
        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        combined = pd.concat([df, new], ignore_index=True)
        combined = combined.drop_duplicates("Date").sort_values("Date")
        combined.to_csv(csv_path, index=False)

        extra = f", cleaned {cleaned}" if cleaned else ""
        return (f"  {symbol}: +{len(new)} rows [{source}] -> "
                f"{combined.iloc[-1]['Date']} OK{extra}")

    except Exception as e:
        return f"  {symbol}: ERROR {e}"


def get_signal_symbols() -> set:
    symbols = set()
    if not SIGNAL_DIR.exists():
        return symbols
    for f in SIGNAL_DIR.glob("*.json"):
        try:
            with open(f, encoding="utf-8") as jf:
                data = json.load(jf)
            for row in data.get("rows", []):
                s = str(row.get("symbol", "")).strip()
                if s:
                    symbols.add(s)
        except Exception:
            pass
    return symbols


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    raw_dir = find_raw_dir()
    csv_files = sorted(raw_dir.glob("*.csv"))
    existing_symbols = {f.stem for f in csv_files}

    # Step 1: new tickers from recent signals
    print("Checking for new tickers in signal files...")
    signal_symbols = get_signal_symbols()
    new_symbols = signal_symbols - existing_symbols
    if new_symbols:
        print(f"Found {len(new_symbols)} new tickers: {sorted(new_symbols)}")
        for sym in sorted(new_symbols):
            result = download_full(sym, raw_dir / f"{sym}.csv")
            print(f"[NEW] {result}")
        csv_files = sorted(raw_dir.glob("*.csv"))
    else:
        print("No new tickers found.")

    # Step 2: update all existing tickers
    print(f"\nUpdating {len(csv_files)} tickers to {TODAY}...\n")
    ok = skip = err = 0
    for i, f in enumerate(csv_files, 1):
        result = update_existing(f)
        print(f"[{i}/{len(csv_files)}] {result}")
        if "OK" in result:
            ok += 1
        elif "ERROR" in result:
            err += 1
        else:
            skip += 1

    print(f"\nDone! Updated={ok}, Already up-to-date={skip}, Errors={err}")
    print(f"Run date: {TODAY}")


if __name__ == "__main__":
    main()
