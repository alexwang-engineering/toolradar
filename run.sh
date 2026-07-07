#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Install dependencies if needed
if ! python3 -c "import requests, bs4, webview" 2>/dev/null; then
  echo "📦 Installing dependencies..."
  pip3 install -r requirements.txt -q --break-system-packages
fi

python3 app.py
