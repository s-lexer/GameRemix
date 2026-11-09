@echo off
chcp 65001 >nul
rem Full PageHeap for div.exe: any use of freed memory crashes at once (dump -> scratch\crashdumps). Slower game, more memory. Off: pageheap_off.cmd
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'" & exit /b)
"C:\Program Files (x86)\Windows Kits\10\Debuggers\x86\gflags.exe" /p /enable div.exe /full
echo.
echo Проверка памяти для div.exe ВКЛЮЧЕНА. Игра будет медленнее. Выключить: pageheap_off.cmd
pause
