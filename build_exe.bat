@echo off
title DONG GOI APP COC AUTO MASTER (EXE)
cd /d "%~dp0"

echo ========================================================
echo   BAT DAU DONG GOI COC AUTO MASTER RA FILE .EXE DUY NHAT
echo   (Nguoi dung khong can cai Python, chi can nhap dup chuot)
echo ========================================================
echo.

pyinstaller coc_auto.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [LOI] Dong goi that bai!
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [THANH CONG] File exe da duoc tao tai: dist\COC_AutoMaster.exe
echo ========================================================
echo.
pause
