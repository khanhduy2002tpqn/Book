@echo off
chcp 65001 >nul
echo ========================================================
echo       AI PDF Reader - Tool Tải Lên & OCR Hàng Loạt
echo ========================================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
    echo [LỖI] Chưa tìm thấy môi trường Python venv!
    pause
    exit /b
)

backend\venv\Scripts\python.exe bulk_upload_ocr.py %*

echo.
pause
