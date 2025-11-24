#!/bin/bash
set -e

# Generate time-only filename (HHMMSS) and zero-padded hour
timestamp=$(date +%H%M%S)
filename="photo_${timestamp}.jpeg"

echo "Using filename: $filename"

hdc shell power-shell wakeup
hdc shell aa start -b com.example.glass -a EntryAbility
sleep 1
hdc shell snapshot_display -f /data/local/tmp/0.jpeg

hdc file recv /data/local/tmp/0.jpeg "$filename"
hdc shell aa force-stop com.example.glass

exit 0
