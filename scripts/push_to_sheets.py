"""
每日排程腳本：把最新下載的訊號 JSON 上傳到 Google Sheets。
由 run_daily_top10_volume_gt1000.cmd 在下載完成後呼叫。

用法：python push_to_sheets.py [--date YYYYMMDD]
若不指定 --date，自動找 data/downloads/daily_top10_volume_gt1000/ 最新檔案。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ── 設定 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
SHEET_ID = "1X8L7VNfZ5siqGj4KiisuMqv4shy3R1TAKAjdc5bOgbY"
KEY_FILE = ROOT / "mymax21-dashboard-2c3cce9caad1.json"
DOWNLOAD_DIR = ROOT / "data" / "downloads" / "daily_top10_volume_gt1000"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUMNS = ["symbol", "name", "price", "diff", "changePct", "volume",
           "points", "h", "a1"]


def find_latest_json(date_str: str | None) -> Path:
    if date_str:
        matches = list(DOWNLOAD_DIR.glob(f"{date_str}_tw_daily_21_small_ext120_up*.json"))
        if not matches:
            sys.exit(f"找不到日期 {date_str} 的 JSON 檔案")
        return sorted(matches)[-1]

    # 找最新檔案
    files = [f for f in DOWNLOAD_DIR.glob("*.json")]
    if not files:
        sys.exit(f"找不到任何 JSON 檔案：{DOWNLOAD_DIR}")
    return sorted(files)[-1]


def upload(json_path: Path) -> None:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    rows = data.get("rows", [])
    trade_date = data.get("metadata", {}).get("trade_date", "")
    if not trade_date:
        m = re.match(r"(\d{8})", json_path.name)
        trade_date = m.group(1) if m else ""
    if not trade_date:
        sys.exit("無法取得交易日期")

    tab_name = trade_date  # YYYYMMDD

    # 連線
    creds = Credentials.from_service_account_file(str(KEY_FILE), scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    existing = {ws.title for ws in sh.worksheets()}

    header = COLUMNS
    values = [header] + [[r.get(c, "") for c in COLUMNS] for r in rows]

    if tab_name in existing:
        ws = sh.worksheet(tab_name)
        ws.clear()
        print(f"[push_to_sheets] {tab_name}: 已存在，清空重寫")
    else:
        ws = sh.add_worksheet(title=tab_name,
                              rows=max(len(values) + 5, 50),
                              cols=len(COLUMNS) + 2)
        print(f"[push_to_sheets] {tab_name}: 新建 tab")

    ws.update(range_name="A1", values=values)
    print(f"[push_to_sheets] {tab_name}: 寫入 {len(rows)} 筆 ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="指定日期 YYYYMMDD，不填則取最新")
    args = parser.parse_args()

    json_path = find_latest_json(args.date)
    print(f"[push_to_sheets] 讀取：{json_path.name}")
    upload(json_path)
