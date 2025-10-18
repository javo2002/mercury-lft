#!/bin/bash

# --- Master Bot Runner Script ---
# Sets up the environment for the master_bot.py cron job.

cd /home/ubuntu/trading_bot_phase1

# Export the API keys for this script's session
export API_KEY="PKUCSK92T6YBO6GFIST5"
export API_SECRET="VkZ1GC0l1cVEidpc9N6Y0kKDGtUVbUOQKnvVUHrc"

echo "--- [$(date)] ---"
echo "Executing master_bot.py..."

# Activate the venv and run the master bot script
/home/ubuntu/trading_bot_phase1/venv/bin/python master_bot.py
