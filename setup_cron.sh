#!/bin/bash

# Setup cron job for daily 6 AM blog generation

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCHEDULER_SCRIPT="$SCRIPT_DIR/blog_scheduler.py"

# Create cron job to run at 6 AM daily
# 0 6 * * * = 6:00 AM every day
CRON_JOB="0 6 * * * cd $SCRIPT_DIR && /usr/bin/python3 $SCHEDULER_SCRIPT >> $SCRIPT_DIR/blog_scheduler.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$SCHEDULER_SCRIPT"; then
    echo "Cron job already exists for blog_scheduler.py"
    echo "Current cron jobs:"
    crontab -l | grep "$SCHEDULER_SCRIPT"
else
    # Add new cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✓ Cron job added successfully!"
    echo "Blog scheduler will run daily at 6:00 AM"
    echo ""
    echo "To view cron jobs, run: crontab -l"
    echo "To remove cron job, run: crontab -e and delete the blog_scheduler line"
fi

# Test the scheduler immediately (optional)
echo ""
echo "Would you like to test the blog scheduler now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Running blog scheduler test..."
    python3 "$SCHEDULER_SCRIPT"
fi
