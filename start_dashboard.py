#!/usr/bin/env python3
"""
ShopGuard Trading Platform - Web Dashboard Starter
===================================================

Starts the web dashboard on localhost:5000 with proper configuration.

Usage:
    python start_dashboard.py              # Start on default port 5000
    python start_dashboard.py --port 8080  # Start on custom port
    python start_dashboard.py --no-debug   # Production mode (no auto-reload)
    python start_dashboard.py --open       # Auto-open browser
"""

import sys
import os
import argparse
import webbrowser
import time
from threading import Timer

# Add src to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, 'src')
WEBAPP_DIR = os.path.join(SCRIPT_DIR, 'webapp')

sys.path.insert(0, SRC_DIR)
sys.path.insert(0, WEBAPP_DIR)


class Colors:
    """Terminal colors for pretty output"""
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def color(text: str, c: str) -> str:
    """Apply color to text"""
    return f"{c}{text}{Colors.END}"


def print_banner(port: int):
    """Print startup banner"""
    print(color("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🛡️  SHOPGUARD TRADING DASHBOARD                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """, Colors.CYAN))

    print(f"  {color('Starting web dashboard...', Colors.BOLD)}\n")
    print(f"  {color('URL:', Colors.CYAN)}      http://localhost:{port}")
    print(f"  {color('Username:', Colors.CYAN)} admin")
    print(f"  {color('Password:', Colors.CYAN)} quanttrader2024")
    print()
    print(color("  ⚠  Change credentials in webapp/app.py for production!", Colors.YELLOW))
    print()
    print(color("═" * 64, Colors.CYAN))
    print()


def check_dependencies() -> bool:
    """Check that required dependencies are installed"""
    missing = []

    try:
        import flask
    except ImportError:
        missing.append('flask')

    try:
        import numpy
    except ImportError:
        missing.append('numpy')

    if missing:
        print(color(f"  ✗ Missing dependencies: {', '.join(missing)}", Colors.RED))
        print(color("  Run: pip install " + " ".join(missing), Colors.YELLOW))
        return False

    return True


def open_browser(port: int):
    """Open browser after a short delay"""
    time.sleep(1.5)
    webbrowser.open(f'http://localhost:{port}')


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='ShopGuard Trading Dashboard Starter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_dashboard.py              # Default settings
  python start_dashboard.py --port 8080  # Custom port
  python start_dashboard.py --open       # Auto-open browser
  python start_dashboard.py --no-debug   # Production mode
        """
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5000,
        help='Port to run the dashboard on (default: 5000)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--no-debug',
        action='store_true',
        help='Run in production mode (no auto-reload)'
    )
    parser.add_argument(
        '--open', '-o',
        action='store_true',
        help='Automatically open browser'
    )

    args = parser.parse_args()

    # Print banner
    print_banner(args.port)

    # Check dependencies
    if not check_dependencies():
        print(color("\n  ✗ Please install missing dependencies first.", Colors.RED))
        sys.exit(1)

    print(color("  ✓ Dependencies verified", Colors.GREEN))

    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(color("  ✓ Environment loaded from .env", Colors.GREEN))
    except ImportError:
        print(color("  ⚠ python-dotenv not installed, using system env", Colors.YELLOW))

    # Import Flask app
    try:
        # Change to webapp directory for correct template paths
        os.chdir(WEBAPP_DIR)
        from app import app
        print(color("  ✓ Flask app loaded", Colors.GREEN))
    except ImportError as e:
        print(color(f"  ✗ Failed to import Flask app: {e}", Colors.RED))
        print(color("  Make sure webapp/app.py exists and Flask is installed", Colors.YELLOW))
        sys.exit(1)
    except Exception as e:
        print(color(f"  ✗ Error loading app: {e}", Colors.RED))
        sys.exit(1)

    # Open browser if requested
    if args.open:
        print(color("  ➤ Opening browser...", Colors.CYAN))
        Timer(1.5, lambda: webbrowser.open(f'http://localhost:{args.port}')).start()

    print()
    print(color("  Press Ctrl+C to stop the server", Colors.YELLOW))
    print()

    # Start the server
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=not args.no_debug
        )
    except KeyboardInterrupt:
        print(color("\n\n  ✓ Dashboard stopped gracefully", Colors.GREEN))
    except OSError as e:
        if "Address already in use" in str(e):
            print(color(f"\n  ✗ Port {args.port} is already in use!", Colors.RED))
            print(color(f"  Try: python start_dashboard.py --port {args.port + 1}", Colors.YELLOW))
            print(color(f"  Or kill the process: lsof -ti:{args.port} | xargs kill -9", Colors.YELLOW))
        else:
            raise


if __name__ == '__main__':
    main()
