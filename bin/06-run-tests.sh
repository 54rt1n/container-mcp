#!/bin/bash
set -e

# Container-MCP Test Runner Script
# This script runs tests for the Container-MCP project

echo "=== Container-MCP Test Runner ==="

# Determine test mode
TEST_MODE=${1:-"all"}  # Default to "all" if not specified

valid_modes=("unit" "integration" "all")
if [[ ! " ${valid_modes[*]} " =~ " ${TEST_MODE} " ]]; then
    echo "Invalid test mode: ${TEST_MODE}"
    echo "Valid modes: ${valid_modes[*]}"
    exit 1
fi

# Check if we're in a virtual environment, and activate if not
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        echo "Activating virtual environment..."
        source .venv/bin/activate
    else
        echo "No virtual environment found. Creating one..."
        python3.12 -m venv .venv
        source .venv/bin/activate
        uv pip install -e ".[dev]"
    fi
fi

# Ensure test dependencies are installed
echo "Ensuring test dependencies are installed..."
uv pip install -e ".[dev]"

# Create necessary test directories
echo "Setting up test directories..."
mkdir -p /tmp/cmcp-test-sandbox/bash
mkdir -p /tmp/cmcp-test-sandbox/python
mkdir -p /tmp/cmcp-test-sandbox/files
mkdir -p /tmp/cmcp-test-temp

# Run tests based on mode
case ${TEST_MODE} in
    "unit")
        echo "Running unit tests..."
        python -m pytest tests/unit -v
        ;;
    "integration")
        echo "Running integration tests..."
        python -m pytest tests/integration -v
        ;;
    "all")
        echo "Running all tests..."
        python -m pytest
        ;;
esac

# Check test result
if [ $? -eq 0 ]; then
    echo "=== Tests Passed ==="
else
    echo "=== Tests Failed ==="
    exit 1
fi

# Offer to generate a coverage report
echo "Would you like to generate a test coverage report? (y/n)"
read -r generate_coverage

if [[ $generate_coverage == "y" || $generate_coverage == "Y" ]]; then
    echo "Generating coverage report..."
    python -m pytest --cov=cmcp --cov-report=term --cov-report=html
    echo "HTML coverage report generated in htmlcov/"
    echo "Open htmlcov/index.html in your browser to view the report."
fi

echo "=== Test Run Complete ===" 