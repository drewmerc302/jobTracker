#!/bin/bash
export PATH="/Users/drewmerc/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd /Users/drewmerc/workspace/jobTracker

# Truncate logs to ~1MB
for logfile in data/logs/stdout.log data/logs/stderr.log; do
    if [ -f "$logfile" ] && [ "$(stat -f%z "$logfile" 2>/dev/null || echo 0)" -gt 1048576 ]; then
        tail -c 1048576 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
    fi
done

mkdir -p data/logs
uv run jobtracker 2>&1
