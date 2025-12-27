#!/bin/bash
# =============================================================================
# ShopGuard Trading Platform - Setup and Run Script
# =============================================================================
# Usage:
#   ./setup_and_run.sh           # Full setup
#   ./setup_and_run.sh --check   # Check dependencies only
#   ./setup_and_run.sh --skip-venv # Skip virtual environment creation
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
CHECK_ONLY=false
SKIP_VENV=false
for arg in "$@"; do
    case $arg in
        --check)
            CHECK_ONLY=true
            ;;
        --skip-venv)
            SKIP_VENV=true
            ;;
    esac
done

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   🛡️  SHOPGUARD TRADING PLATFORM                             ║"
    echo "║                                                              ║"
    echo "║   Automated Setup Script                                     ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${BOLD}${CYAN}[$1/$2] $3${NC}"
}

print_success() {
    echo -e "  ${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "  ${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "  ${RED}✗ $1${NC}"
}

# Step 1: Check Python version
check_python() {
    print_step 1 6 "Checking Python version..."

    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python not found. Please install Python 3.10+"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        print_error "Python 3.10+ required (found $PYTHON_VERSION)"
        exit 1
    fi

    print_success "Python $PYTHON_VERSION detected"
}

# Step 2: Create virtual environment
create_venv() {
    print_step 2 6 "Setting up virtual environment..."

    if [ "$SKIP_VENV" = true ]; then
        print_warning "Skipping virtual environment (--skip-venv)"
        return
    fi

    if [ -d "venv" ]; then
        print_success "Virtual environment already exists"
    else
        $PYTHON_CMD -m venv venv
        print_success "Created virtual environment"
    fi

    # Activate virtual environment
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        print_success "Activated virtual environment"
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
        print_success "Activated virtual environment (Windows)"
    fi
}

# Step 3: Upgrade pip
upgrade_pip() {
    print_step 3 6 "Upgrading pip..."
    pip install --upgrade pip -q
    print_success "pip upgraded to $(pip --version | awk '{print $2}')"
}

# Step 4: Install dependencies
install_dependencies() {
    print_step 4 6 "Installing dependencies..."

    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt -q
        print_success "Installed all dependencies from requirements.txt"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi

    # Ensure Flask is installed (required for web dashboard)
    pip install flask -q 2>/dev/null || true
    print_success "Flask web framework ready"
}

# Step 5: Configure environment
configure_environment() {
    print_step 5 6 "Configuring environment..."

    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_success "Created .env from template"
            print_warning "Edit .env to add your API keys for live trading"
        else
            # Create minimal .env file
            cat > .env << 'EOF'
# ShopGuard Trading Platform Configuration
# =========================================

# Trading Mode: 'paper' for simulation, 'live' for real trading
TRADING_MODE=paper

# Default broker for paper trading
DEFAULT_BROKER=paper

# Initial capital for paper trading (USD)
INITIAL_CAPITAL=100000

# API Keys (required for live trading only)
# Uncomment and fill in when ready for live trading:
# ALPACA_API_KEY=your_alpaca_api_key_here
# ALPACA_SECRET_KEY=your_alpaca_secret_key_here
# BINANCE_API_KEY=your_binance_api_key_here
# BINANCE_SECRET_KEY=your_binance_secret_key_here
EOF
            print_success "Created default .env configuration"
        fi
    else
        print_success ".env configuration exists"
    fi

    # Set PYTHONPATH
    export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}/src"
    print_success "PYTHONPATH configured"
}

# Step 6: Verify installation
verify_installation() {
    print_step 6 6 "Verifying installation..."

    # Test core imports
    $PYTHON_CMD -c "import numpy; print(f'  ✓ NumPy {numpy.__version__}')" 2>/dev/null || print_error "NumPy import failed"
    $PYTHON_CMD -c "import scipy; print(f'  ✓ SciPy {scipy.__version__}')" 2>/dev/null || print_error "SciPy import failed"
    $PYTHON_CMD -c "import pandas; print(f'  ✓ Pandas {pandas.__version__}')" 2>/dev/null || print_error "Pandas import failed"
    $PYTHON_CMD -c "import flask; print(f'  ✓ Flask {flask.__version__}')" 2>/dev/null || print_error "Flask import failed"

    # Test project modules
    export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}/src"
    $PYTHON_CMD -c "import sys; sys.path.insert(0, 'src'); from ai_models import TradingEnsemble; print('  ✓ AI Models loaded')" 2>/dev/null || print_warning "AI Models not fully available"
    $PYTHON_CMD -c "import sys; sys.path.insert(0, 'src'); from trading import BrokerFactory; print('  ✓ Trading modules loaded')" 2>/dev/null || print_warning "Trading modules not fully available"
}

# Print final instructions
print_final_instructions() {
    echo -e "\n${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  ✓ SETUP COMPLETE!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Next Steps:${NC}"
    echo ""
    echo -e "  ${CYAN}1. Activate the virtual environment:${NC}"
    echo "     source venv/bin/activate"
    echo ""
    echo -e "  ${CYAN}2. Start the web dashboard:${NC}"
    echo "     python start_dashboard.py"
    echo "     # Or: python webapp/app.py"
    echo ""
    echo -e "  ${CYAN}3. Access the dashboard:${NC}"
    echo "     URL: http://localhost:5000"
    echo "     Username: admin"
    echo "     Password: quanttrader2024"
    echo ""
    echo -e "  ${CYAN}4. Other commands:${NC}"
    echo "     python assistant.py          # Interactive assistant"
    echo "     python run_demo.py           # Run demos"
    echo "     python quick_start.py --test # Run tests"
    echo ""
    echo -e "  ${YELLOW}Note: Trading is in PAPER mode by default (no real money).${NC}"
    echo -e "  ${YELLOW}Edit .env to configure API keys for live trading.${NC}"
    echo ""
}

# Main execution
main() {
    print_banner

    check_python

    if [ "$CHECK_ONLY" = true ]; then
        echo -e "\n${GREEN}✓ Python check passed!${NC}"
        exit 0
    fi

    create_venv
    upgrade_pip
    install_dependencies
    configure_environment
    verify_installation
    print_final_instructions
}

main
