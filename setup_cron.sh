#!/bin/bash

# Setup cron job for daily 6 AM blog generation (America/Chicago)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCHEDULER_SCRIPT="$SCRIPT_DIR/blog_scheduler.py"
VENV_PYTHON="$(dirname "$SCRIPT_DIR")/.venv/bin/python"

# Create cron job to run at 6 AM America/Chicago daily
# CRON_TZ ensures DST-safe scheduling in Central time.
CRON_TZ_LINE="CRON_TZ=America/Chicago"
CRON_JOB="0 6 * * * cd $SCRIPT_DIR && $VENV_PYTHON $SCHEDULER_SCRIPT --run-once >> $SCRIPT_DIR/blog_scheduler.log 2>&1"

# Check if cron job already exists
CURRENT_CRONTAB="$(crontab -l 2>/dev/null)"
if echo "$CURRENT_CRONTAB" | grep -q "$SCHEDULER_SCRIPT"; then
    echo "Existing blog scheduler cron entry found. Replacing with updated entry..."
fi

# Remove previous scheduler entries and previous CRON_TZ setting, then append updated entries.
FILTERED_CRONTAB="$(echo "$CURRENT_CRONTAB" | grep -v "$SCHEDULER_SCRIPT" | grep -v "^CRON_TZ=America/Chicago$")"
printf "%s\n%s\n%s\n" "$FILTERED_CRONTAB" "$CRON_TZ_LINE" "$CRON_JOB" | crontab -

echo "✓ Cron job configured successfully!"
echo "Blog scheduler will run daily at 6:00 AM America/Chicago"
echo ""
echo "Installed entries:"
crontab -l | grep -E "CRON_TZ=America/Chicago|$SCHEDULER_SCRIPT"
echo ""
echo "To view cron jobs, run: crontab -l"
echo "To remove cron job, run: crontab -e and delete the blog_scheduler lines"

# Test the scheduler immediately (optional)
echo ""
echo "Would you like to test the blog scheduler now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Running blog scheduler test..."
    "$VENV_PYTHON" "$SCHEDULER_SCRIPT" --run-once
fi
