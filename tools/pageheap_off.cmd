@echo off
chcp 65001 >nul
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'" & exit /b)
"C:\Program Files (x86)\Windows Kits\10\Debuggers\x86\gflags.exe" /p /disable div.exe
echo.
echo Проверка памяти для div.exe ВЫКЛЮЧЕНА.
pause
