#!/bin/bash
# One-time setup for MyHeritage automation agent

set -e

echo "=== MyHeritage Agent Setup ==="

# Check Python version
python3 --version

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
fi

# Activate
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Create .env from example if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env created from .env.example — edit it if needed"
fi

# Create data directory
mkdir -p data logs recon

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "1. Export cookies from Chrome (EditThisCookie → JSON format)"
echo "   Save to: data/myheritage_cookies.json"
echo ""
echo "2. Run auth check:"
echo "   source venv/bin/activate"
echo "   python auth/browser_auth.py"
echo ""
echo "3. Run recon:"
echo "   python recon.py"
echo ""
