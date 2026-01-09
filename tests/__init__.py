"""
Test Suite for Quantitative Trading Platform

Organization:
- unit/: Unit tests for individual modules
- integration/: Integration tests for component interactions
- e2e/: End-to-end tests for full workflows

Run tests:
    pytest                    # Run all tests
    pytest tests/unit         # Run only unit tests
    pytest -m fast            # Run fast tests only
    pytest -m "not slow"      # Skip slow tests
    pytest -n auto            # Parallel execution
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
