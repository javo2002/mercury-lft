#!/bin/bash

# --- MASTER BOT RUNNER SCRIPT ---
# This script correctly sets up the environment for cron jobs.

# Check if the correct number of arguments (strategy type and ticker) were provided
if [ "$#" -ne 2 ]; then
    echo "Usage: ./run_bot.sh <strategy_type> <ticker>"
    echo "Example: ./run_bot.sh sma GOOG"
    exit 1
fi

STRATEGY_TYPE=$1
TICKER=$2
SCRIPT_NAME="live_bot_${STRATEGY_TYPE}.py"

# --- Environment Setup ---
# Navigate to the project directory
cd /home/ubuntu/trading_bot_phase1

# Export the API keys for this script's session
export API_KEY="PKUCSK92T6YBO6GFIST5"
export API_SECRET="VkZ1GC0l1cVEidpc9N6Y0kKDGtUVbUOQKnvVUHrc"

# --- Execution ---
echo "--- [$(date)] ---"
echo "Executing ${SCRIPT_NAME} for ${TICKER}..."

# This is the CRITICAL line. It uses the full path to the Python
# executable INSIDE your virtual environment, ensuring the correct libraries are used.
/home/ubuntu/trading_bot_phase1/venv/bin/python ${SCRIPT_NAME} ${TICKER}
