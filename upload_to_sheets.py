"""
一次性腳本：把 data/downloads/ 的 JSON 訊號檔上傳到 Google Sheets。
每個日期建立一個 tab（YYYYMMDD），欄位對應 JSON rows 的欄位。
執行：python upload_to_sheets.py
"""
import json
import re
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ── 設定 ──────────────────────────────────────────────────────────────────────
SHEET_ID = "1X8L7VNfZ5siqGj4KiisuMqv4shy3R1TAKAjdc5bOgbY"
KEY_FILE = Path(__file__).parent / "mymax21-dashboard-2c3cce9caad1.json"
DOWNLOAD_DIR = Path(__file__).parent / "data" / "downloads"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 連線 ──────────────────────────────────────────────────────────────────────
creds = Credentials.from_service_account_file(str(KEY_FILE), scopes=SCOPES)
client = gspread.authorize(creds)
sh = client.open_by_key(SHEET_ID)

existing_tabs = {ws.title for ws in sh.worksheets()}
print(f"現有 tabs: {existing_tabs}")

# ── 掃描 JSON 檔 ──────────────────────────────────────────────────────────────
pat = re.compile(r"^(\d{8})_tw_daily_21_small_ext120_up")
date_files: dict[str, list[Path]] = {}
for f in DOWNLOAD_DIR.iterdir():
    m = pat.match(f.name)
    if m and f.suffix == ".json" and "daily_top10" not in f.name:
        date_files.setdefault(m.group(1), []).append(f)

# 每個日期取最新版本
for raw_date, files in sorted(date_files.items()):
    def ver(p):
        vm = re.search(r"_v(\d+)\.json$", p.name)
        return int(vm.group(1)) if vm else 0
    best = sorted(files, key=ver)[-1]

    with open(best, encoding="utf-8") as f:
        data = json.load(f)

    rows = data.get("rows", [])
    if not rows:
        print(f"  {raw_date}: 無資料，跳過")
        continue

    # 欄位順序
    columns = ["symbol", "name", "price", "diff", "changePct", "volume", "points", "h", "a1"]
    header = columns

    values = [header]
    for r in rows:
        values.append([r.get(c, "") for c in columns])

    # 建立或清空 tab
    if raw_date in existing_tabs:
        ws = sh.worksheet(raw_date)
        ws.clear()
        print(f"  {raw_date}: 已存在，清空重寫")
    else:
        ws = sh.add_worksheet(title=raw_date, rows=max(len(values)+5, 50), cols=len(columns)+2)
        print(f"  {raw_date}: 新建 tab")

    ws.update("A1", values)
    print(f"  {raw_date}: 寫入 {len(rows)} 筆 ✓")

print("\n完成！")
