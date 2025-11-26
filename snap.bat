@echo off
setlocal enabledelayedexpansion


:: Generate time-only filename (HHMMSS)
set "timestamp=%time:~0,2%%time:~3,2%%time:~6,2%"
set "timestamp=%timestamp: =0%"
set "filename=photo_%timestamp%.jpeg"

echo Using filename: !filename!

hdc shell power-shell wakeup
hdc shell aa start -b com.example.glass -a EntryAbility
timeout /t 1 /nobreak
hdc shell snapshot_display -f /data/local/tmp/0.jpeg

if not exist data (
    mkdir data
)
hdc file recv /data/local/tmp/0.jpeg "data/!filename!"
hdc shell aa force-stop com.example.glass
:done