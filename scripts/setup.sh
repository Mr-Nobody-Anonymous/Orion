#!/usr/bin/env bash
set -euo pipefail

echo "=== Setting up ORION Environment ==="

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'"

# Create venv if not existing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Upgrade pip and install build tools
python -m pip install --upgrade pip setuptools wheel build

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run initial system check
echo "Running Orion health check..."
python start.py --check

echo "=== Orion setup complete ==="
