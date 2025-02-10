#!/bin/bash

set -euo pipefail
IFS=$'\n\t'

# Define variables
PROJECT_DIR=$(realpath "$(dirname "$BASH_SOURCE[0]")/..")
SERVICE_NAME="net-server"

# Change to project directory
cd "$PROJECT_DIR"

# Stop services
sudo systemctl stop cron
sudo systemctl stop "$SERVICE_NAME"

# Print package versions
uv pip list

# Update the project
git fetch -p && git reset --hard origin/main

# Sync the project dependencies
uv sync --group prod

# Start services
sudo systemctl start cron
sudo systemctl start "$SERVICE_NAME"

# Log success message
echo "Server update completed successfully."
