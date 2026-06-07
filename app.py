"""
mymax21 · SL10_TP50 每日訊號儀表板
Daily signal dashboard for the SL10/TP50 swing-trading strategy (TW stocks).
Data source: Google Sheets (each tab = YYYYMMDD trading date).
Deployed via Streamlit Cloud.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ── Google Sheets 設定 ────────────────────────────────────────────────────────
SHEET_ID = "1X8L7VNfZ5siqGj4KiisuMqv4shy3R1TAKAjdc5bOgbY"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
MAX_DAYS = 120

# ── 頁面設定 ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="mymax21 · SL10_TP50 每日儀表板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 全域樣式（深色主題補強） ──────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-size: 12px !important; }
[data-testid="stMetricValue"] { font-size: 20px !important; }
[data-testid="stMetricLabel"] { font-size: 14px !important; }
[data-testid="stCaptionContainer"] { font-size: 12px !important; }
thead tr th { font-size: 15px !important; color: #8b949e !important; }
tbody tr td { font-size: 16px !important; }
[data-testid="stDataFrame"] * { font-size: 16px !important; }
[data-testid="stDataFrame"] [class*="header"] { font-size: 15px !important; }
h1, h2, h3 { font-size: 16px !important; }
.badge-grn { background: rgba(63,185,80,.15); color: #3fb950;
             border: 1px solid rgba(63,185,80,.35); border-radius: 20px;
             padding: 1px 9px; font-size: 11px; font-weight: 600; }
.badge-blu { background: rgba(88,166,255,.15); color: #58a6ff;
             border: 1px solid rgba(88,166,255,.35); border-radius: 20px;
             padding: 1px 9px; font-size: 11px; font-weight: 600; }
.info-note { background: #1c2128; border-left: 3px solid #d29922;
             padding: 6px 12px; border-radius: 4px;
             font-size: 11px; color: #8b949e; margin: 6px 0; }
hr { border-color: #30363d; }
</style>
""", unsafe_allow_html=True)


# ── Google Sheets 連線 ────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_gsheet_client():
    """建立 gspread client（使用 Streamlit Secrets 的 service account）"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=300, show_spinner=False)
def discover_dates() -> list[str]:
    """
    取得 Google Sheets 所有 worksheet 名稱（YYYYMMDD 格式），
    轉換為 YYYY-MM-DD，排序由新到舊，最多120個交易日。
    """
    client = get_gsheet_client()
    sh = client.open_by_key(SHEET_ID)
    valid = []
    for ws in sh.worksheets():
        t = ws.title
        if len(t) == 8 and t.isdigit():
            valid.append(f"{t[:4]}-{t[4:6]}-{t[6:]}")
    valid.sort(reverse=True)
    return valid[:MAX_DAYS]


@st.cache_data(ttl=300, show_spinner=False)
def load_sheet_date(date_str: str) -> list[dict]:
    """
    載入指定日期的 worksheet，回傳 list of dict（每行一筆訊號）。
    date_str 格式：YYYY-MM-DD
    """
    client = get_gsheet_client()
    sh = client.open_by_key(SHEET_ID)
    ws = sh.worksheet(date_str.replace("-", ""))
    return ws.get_all_records()


# ── 工具函式 ──────────────────────────────────────────────────────────────────
def weekday_zh(date_str: str) -> str:
    days = ["一", "二", "三", "四", "五", "六", "日"]
    return days[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


def next_trading_day(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    delta = 3 if d.weekday() == 4 else (2 if d.weekday() == 5 else 1)
    return (d + timedelta(days=delta)).strftime("%Y-%m-%d")


def fmt_vol(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{v/1000:.0f}K" if v >= 100_000 else f"{int(v):,}"


def fmt_price(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return str(p)
    return f"{p:.2f}" if p < 100 else f"{p:.0f}"


def fmt_pct(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return str(p)
    return f"{'+'if p>0 else ''}{p:.2f}%"


def date_label(d: str) -> str:
    return f"{d}（{weekday_zh(d)}）"


# ── 持倉資料（手動維護） ──────────────────────────────────────────────────────
OPEN_POSITIONS = [
    dict(code="5483", name="中美晶",  entry_date="2026-03-12", entry=115.00, current=152.50, trail_sl=126.50, tp=172.50, shares=869),
    dict(code="6805", name="富世達",  entry_date="2026-03-19", entry=1545.0, current=1950.0, trail_sl=1699.5, tp=2317.5, shares=64),
    dict(code="2382", name="廣達",    entry_date="2026-04-02", entry=313.00, current=390.50, trail_sl=313.00, tp=469.50, shares=319),
    dict(code="2881", name="富邦金",  entry_date="2026-04-09", entry=94.50,  current=118.00, trail_sl=94.50,  tp=141.75, shares=1058),
]
MAX_POSITIONS = 5


# ── 左側欄位 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 mymax21 · SL10_TP50")
    st.caption("台灣股票市場 · 每日訊號儀表板")
    st.divider()

    with st.spinner("載入日期清單…"):
        date_options = discover_dates()

    if not date_options:
        st.error("Google Sheets 尚無資料，請確認 Service Account 權限。")
        st.stop()

    selected_date = st.selectbox(
        "📅 歷史日期（最多120個交易日）",
        options=date_options,
        format_func=date_label,
        index=0,
    )

    st.divider()

    held = len(OPEN_POSITIONS)
    slots_free = MAX_POSITIONS - held
    portfolio_val = 756_000
    total_return = 51.2

    st.markdown("**組合概況**")
    st.metric("市值", f"NT${portfolio_val:,}", f"+{total_return}%")
    st.metric("可用部位", f"{slots_free} / {MAX_POSITIONS}", f"持有 {held} 個")
    st.metric("未實現損益", "+NT$256,000", "4個持倉")

    st.divider()

    with st.expander("📖 策略規則"):
        st.markdown("""
**SL10 / TP50 策略**

| 項目 | 規則 |
|------|------|
| 進場 | T+1 收盤價 |
| 最大部位 | 5 個 |
| 每部位資金 | NT$100,000 |
| 固定停損 | 進場 × 0.90（−10%） |
| 移動停損 | +15% → 損益平衡<br>+25% → 鎖住+10%<br>+35% → 鎖住+20%<br>+45% → 鎖住+30% |
| 止盈 | 進場 × 1.50（+50%） |
| 排序 | 成交量前5名 |
| 濾網 | 收盤 ≥ 前高樞紐（左=4，右=2）|
""", unsafe_allow_html=True)

    st.caption(f"資料來源：Google Sheets · 共 {len(date_options)} 個交易日")


# ── 主區域 ────────────────────────────────────────────────────────────────────
entry_date = next_trading_day(selected_date)

col_title, col_dates = st.columns([2, 1])
with col_title:
    st.markdown("## SL10_TP50 每日儀表板")
with col_dates:
    st.markdown(f"""
<div style='text-align:right;line-height:1.8'>
  <span style='color:#8b949e;font-size:11px'>訊號日期</span><br>
  <strong>{date_label(selected_date)}</strong><br>
  <span style='color:#8b949e;font-size:11px'>進場日期 (T+1)</span><br>
  <strong>{date_label(entry_date)}</strong>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── 載入當日訊號 ──────────────────────────────────────────────────────────────
with st.spinner("載入訊號資料…"):
    rows = load_sheet_date(selected_date)

top5 = sorted(rows, key=lambda r: float(r.get("volume", 0) or 0), reverse=True)[:5]
total_signals = len(rows)

# ── KPI 列 ────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("組合市值", f"NT${portfolio_val:,}", f"+{total_return}%（自2026/01）")
k2.metric("可用部位", f"{slots_free} / {MAX_POSITIONS}", f"持有 {held} 個")
k3.metric("未實現損益", "+NT$256k", "4個持倉合計")
k4.metric("今日訊號數", str(total_signals), "筆符合條件，顯示前5名")
k5.metric("待處理動作", f"{slots_free} 買進" if slots_free > 0 else "無空位",
          f"進場日：{entry_date}")

st.divider()

# ── 買進訊號表 ────────────────────────────────────────────────────────────────
st.markdown(
    f"### ↑ 買進訊號 &nbsp;<span class='badge-grn'>依成交量前5名</span>&nbsp;"
    f"<span class='badge-blu'>{date_label(selected_date)}</span>",
    unsafe_allow_html=True,
)
slot_hint = (
    f"有 {slots_free} 個空位 — 排名第1至{slots_free}進場，其餘列入排隊"
    if slots_free > 0 else "無空位 — 所有訊號列入排隊"
)
st.markdown(f"<div class='info-note'>▲ {slot_hint}</div>", unsafe_allow_html=True)

if top5:
    headers = ["排名","代碼","股票名稱","成交量（張）","收盤價","漲跌幅","得分","前高","止損 (−10%)","止盈 (+50%)","動作"]
    th = "".join(f"<th style='padding:8px 12px;text-align:left;color:#8b949e;border-bottom:1px solid #30363d;white-space:nowrap'>{h}</th>" for h in headers)
    rows_html = ""
    for rank, r in enumerate(top5, 1):
        price = float(r.get("price", 0) or 0)
        has_slot = rank <= slots_free
        action = "↑ 買進" if has_slot else "排隊"
        action_html = f"<span style='color:#3fb950;font-weight:700'>{action}</span>" if has_slot else f"<span style='color:#8b949e'>{action}</span>"
        bg = "background:rgba(63,185,80,0.08)" if has_slot else "opacity:0.7"
        vals = [rank, r.get("symbol",""), r.get("name",""), fmt_vol(r.get("volume",0)),
                fmt_price(price), fmt_pct(r.get("changePct",0)), r.get("points",0),
                fmt_price(r.get("h",0)), fmt_price(price*0.9), fmt_price(price*1.5), action_html]
        tds = "".join(f"<td style='padding:7px 12px;border-bottom:1px solid #21262d'>{v}</td>" for v in vals)
        rows_html += f"<tr style='{bg}'>{tds}</tr>"
    sig_html = f"""
<div style='overflow-x:auto'>
<table style='width:100%;border-collapse:collapse;font-size:16px'>
<thead><tr>{th}</tr></thead>
<tbody>{rows_html}</tbody>
</table></div>"""
    st.markdown(sig_html, unsafe_allow_html=True)
else:
    st.info("此日期無符合條件的訊號。")

st.divider()

# ── 持倉明細 ──────────────────────────────────────────────────────────────────
st.markdown(
    f"### ◉ 持倉明細 &nbsp;<span class='badge-blu'>持有{held}個 · {slots_free}個空位</span>",
    unsafe_allow_html=True,
)

if OPEN_POSITIONS:
    pos_headers = ["代碼","股票名稱","進場日","進場價","最新收盤","移動停損 ▲","止盈目標","報酬率","未實現損益","動作"]
    th2 = "".join(f"<th style='padding:8px 12px;text-align:left;color:#8b949e;border-bottom:1px solid #30363d;white-space:nowrap'>{h}</th>" for h in pos_headers)
    pos_rows_html = ""
    for p in OPEN_POSITIONS:
        ret = (p["current"] / p["entry"] - 1) * 100
        pnl = (p["current"] - p["entry"]) * p["shares"]
        action = ("↑ 接近止盈" if ret >= 45
                  else "■ 持有（移動停損已升）" if ret >= 25
                  else "■ 持有")
        bg = "background:rgba(63,185,80,0.12)" if ret >= 40 else ""
        pnl_str = f"+NT${pnl:,.0f}" if pnl >= 0 else f"NT${pnl:,.0f}"
        vals = [p["code"], p["name"], p["entry_date"], fmt_price(p["entry"]),
                fmt_price(p["current"]), fmt_price(p["trail_sl"]), fmt_price(p["tp"]),
                fmt_pct(ret), pnl_str, action]
        tds = "".join(f"<td style='padding:7px 12px;border-bottom:1px solid #21262d'>{v}</td>" for v in vals)
        pos_rows_html += f"<tr style='{bg}'>{tds}</tr>"
    pos_html = f"""
<div style='overflow-x:auto'>
<table style='width:100%;border-collapse:collapse;font-size:16px'>
<thead><tr>{th2}</tr></thead>
<tbody>{pos_rows_html}</tbody>
</table></div>"""
    st.markdown(pos_html, unsafe_allow_html=True)
else:
    st.info("目前無持倉。")

# ── 頁尾 ──────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"mymax21 · SL10_TP50 · 僅限台股 · "
    f"資料來源：Google Sheets · "
    f"共 {len(date_options)} 個交易日 · "
    "最多保存120個交易日"
)
