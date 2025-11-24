#!/bin/bash
set -exv

timestamp=$(date +%H%M%S)
filename="sp_${timestamp}.csv"

hdc shell rm /data/local/tmp/data.csv
hdc shell "SP_daemon -N 4 -g -ci -r" &
p1=$!
hdc shell aa start -b com.example.glass -a EntryAbility
wait $p1

hdc file recv /data/local/tmp/data.csv "$filename"
hdc shell aa force-stop com.example.glass