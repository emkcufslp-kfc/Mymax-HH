@echo off
setlocal

set "ROOT=D:\Backtest\mymax21"
set "PYTHON=C:\Program Files\Python314\python.exe"
set "OUT_DIR=%ROOT%\data\downloads\daily_top10_volume_gt1000"

echo [STEP 1] Updating price database...
"%PYTHON%" "%ROOT%\scripts\update_price_db_v2.py"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Price DB update failed
    exit /b 1
)

echo [STEP 2] Downloading daily signals...
"%PYTHON%" "%ROOT%\scripts\mymax21_portable_downloader.py" --type 21_small,ext120_up --category tw_daily --sort-field volume --sort-order desc --min-volume 1000 --limit 10 --out-dir "%OUT_DIR%" --json
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Signal download failed
    exit /b 1
)

echo [STEP 3] Uploading to Google Sheets...
"%PYTHON%" "%ROOT%\scripts\push_to_sheets.py"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Google Sheets upload failed
    exit /b 1
)

echo [INFO] All done!

endlocal
