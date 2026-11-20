@echo off
title KHOI DONG COC AUTO MASTER
cd /d "%~dp0"

:: Kiem tra neu co pythonw thi chay ngam khong bat man hinh den CMD
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start pythonw main.py
) else (
    start python main.py
)
exit
