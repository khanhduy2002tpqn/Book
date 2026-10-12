@echo off
chcp 65001 >nul
echo ========================================================
echo       AI PDF Reader - Khoi dong cuc bo (Khong dung Docker)
echo ========================================================
echo.

:: 1. Kiem tra thu muc backend va venv
if not exist "backend\venv\Scripts\uvicorn.exe" (
    echo [LOI] Chua tim thay moi truong Python venv!
    echo Vui long cai dat backend truoc bang cach:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b
)

:: 2. Giai phong port 8000 va 5173 neu dang bi chiem dung boi tien trinh cu
echo Dang kiem tra va giai phong cac port 8000 va 5173 neu co...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /t /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do taskkill /f /t /pid %%a >nul 2>&1

:: 3. Khoi dong Backend FastAPI tai port 8000 (bind 0.0.0.0 cho phep ESP32 / LAN ket noi)
echo [1/2] Dang khoi dong Backend FastAPI tai http://0.0.0.0:8000 ...
start "AI PDF Reader - Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 4. Khoi dong Frontend Vite tai port 5173
echo [2/2] Dang khoi dong Frontend Vite tai http://localhost:5173 ...
start "AI PDF Reader - Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================================
echo   He thong da khoi dong xong!
echo   - Backend API: http://localhost:8000/docs
echo   - Frontend:    http://localhost:5173
echo.
echo   Trinh duyet se tu dong mo trong vai giay...
echo ========================================================

ping 127.0.0.1 -n 3 >nul
start http://localhost:5173
