#!/bin/bash
# run.sh - Entry script for Smart Street Lighting Edge Device

echo "Starting Edge Device Pipeline..."

# Change to script directory
cd "$(dirname "$0")" || exit 1

# Optional: Activate virtual environment if you have one
# e.g., source ../venv/bin/activate
# Currently your screenshot shows (venv) active

# Execute the main program safely
echo "Launching main Python process..."
python3 edge_main.py
