#!/usr/bin/env bash
# Create the venv (nmrfinesse/) and install NMRFinesse (Linux development environment)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv nmrfinesse
nmrfinesse/bin/python -m pip install --upgrade pip
nmrfinesse/bin/python -m pip install -e .
echo "environment ready: nmrfinesse/bin/python main.py"
