#!/bin/bash

# --- Screener Runner Script ---
# Sets up the environment for the screener.py cron job.

cd /home/ubuntu/trading_bot_phase1

# Export the Alpaca API keys needed for the screener
export API_KEY="PKUCSK92T6YBO6GFIST5"
export API_SECRET="VkZ1GC0l1cVEidpc9N6Y0kKDGtUVbUOQKnvVUHrc"

echo "--- [$(date)] ---"
echo "Executing screener.py..."

# Activate the venv and run the screener script
/home/ubuntu/trading_bot_phase1/venv/bin/python screener.py
