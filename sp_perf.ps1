# PowerShell version of sp_perf.sh
$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "HHmmss"
$filename = "sp_${timestamp}.csv"

# Remove old data file from device
hdc shell rm /data/local/tmp/data.csv

# Wake up the device
hdc shell power-shell wakeup

# Start SP_daemon in background
$process = Start-Process -FilePath hdc -ArgumentList 'shell "SP_daemon -N 3 -g -gc -ci"' -PassThru
$p1 = $process.Id

# Wait a bit for daemon to start
Start-Sleep -Seconds 2

# Start the app
hdc shell aa start -b com.example.glass -a EntryAbility

# Wait for the daemon process to complete
Wait-Process -Id $p1

# Create data directory if it doesn't exist
if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

# Pull the data file from device
hdc file recv /data/local/tmp/data.csv "data/$filename"

# Stop the app
hdc shell aa force-stop com.example.glass

Write-Host "Performance data saved to: data/$filename"
