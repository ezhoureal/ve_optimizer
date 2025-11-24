@echo off
rem Windows BAT equivalent of sp_perf.sh
rem - runs SP_daemon on device, starts the app, waits for the daemon to finish,
rem   copies /data/local/tmp/data.csv to local data\sp_<HHMMSS>.csv and stops the app.

setlocal enabledelayedexpansion

rem timestamp in HHMMSS using PowerShell for reliable formatting
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "Get-Date -Format HHmmss"`) do set TIMESTAMP=%%t
set "FILENAME=sp_%TIMESTAMP%.csv"

echo [sp_perf.bat] filename=%FILENAME%

echo [sp_perf.bat] removing remote file if present...
hdc shell rm /data/local/tmp/data.csv

echo [sp_perf.bat] waking device power-shell...
hdc shell power-shell wakeup

echo [sp_perf.bat] launching SP_daemon and app (daemon runs until finished)...
powershell -NoProfile -Command "\
$p = Start-Process -FilePath 'hdc' -ArgumentList 'shell','SP_daemon -N 5 -g -gc -ci' -NoNewWindow -PassThru; \
Start-Sleep -Seconds 2; \
Start-Process -FilePath 'hdc' -ArgumentList 'shell','aa start -b com.example.glass -a EntryAbility' -NoNewWindow; \
$p.WaitForExit();"

if ERRORLEVEL 1 (
  echo [sp_perf.bat] ERROR: running daemon or starting app failed (exit %ERRORLEVEL%)
  endlocal
  exit /b %ERRORLEVEL%
)

rem ensure local data directory exists
if not exist data mkdir data

echo [sp_perf.bat] receiving data to data\%FILENAME% ...
hdc file recv /data/local/tmp/data.csv "data/%FILENAME%"

echo [sp_perf.bat] stopping app...
hdc shell aa force-stop com.example.glass

echo [sp_perf.bat] done, received data/%FILENAME%
endlocal
exit /b 0
