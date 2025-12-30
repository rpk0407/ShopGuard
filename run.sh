#!/bin/bash
# ShopGuard Quick Start Script

echo "============================================"
echo "  SHOPGUARD AI TRADING PLATFORM"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.9+"
    exit 1
fi

echo "✓ Python3 found: $(python3 --version)"

# Navigate to project
cd "$(dirname "$0")/shopguard_platform"

# Check/Install dependencies
echo ""
echo "Checking dependencies..."

python3 -c "import flask" 2>/dev/null || {
    echo "Installing Flask..."
    pip3 install flask
}

python3 -c "import numpy" 2>/dev/null || {
    echo "Installing NumPy..."
    pip3 install numpy
}

python3 -c "import requests" 2>/dev/null || {
    echo "Installing Requests..."
    pip3 install requests
}

# Optional: Numba for acceleration
python3 -c "import numba" 2>/dev/null || {
    echo ""
    echo "⚡ TIP: Install Numba for 100x faster calculations:"
    echo "   pip3 install numba"
    echo ""
}

echo ""
echo "============================================"
echo "  Starting ShopGuard..."
echo "============================================"
echo ""

# Run the app
python3 -m shopguard_platform.app
