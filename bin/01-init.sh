#!/bin/bash
set -e

# Container-MCP Initialization Script
# This script sets up the project directory structure and dependencies

echo "=== Initializing Container-MCP Project ==="

# Make the script executable
chmod +x bin/*.sh

# Create necessary directories if they don't exist
echo "Creating directory structure..."
mkdir -p volume/{data,logs,config,sandbox,temp}
mkdir -p volume/sandbox/{bash,python,files,browser}
mkdir -p build

# Set permissions for container directories
# All directories under volume need to be writable by the container
chmod -R 777 volume

# Create app.env as a copy of default.env if it doesn't exist
if [ ! -f volume/config/app.env ] && [ -f resources/default.env ]; then
    cp resources/default.env volume/config/app.env
    echo "App configuration created at volume/config/app.env"
fi

# Check for uv installation
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "uv installed successfully"
fi

# Install dependencies using uv
echo "Installing dependencies..."
# Install in development mode with build directory
uv pip install -e ".[dev]"
echo "Dependencies installed"

# Check for required system packages
echo "Checking for required system packages..."

packages=("firejail" "apparmor" "apparmor-utils")
missing_packages=()

for pkg in "${packages[@]}"; do
    if ! command -v "$pkg" &> /dev/null && ! dpkg -l | grep -q "$pkg" && ! rpm -q "$pkg" &> /dev/null; then
        missing_packages+=("$pkg")
    fi
done

if [ ${#missing_packages[@]} -ne 0 ]; then
    echo "Warning: The following packages may be missing from your system:"
    for pkg in "${missing_packages[@]}"; do
        echo "  - $pkg"
    done
    echo ""
    echo "You may need to install them for full functionality:"
    echo "  For Ubuntu/Debian: sudo apt install ${missing_packages[*]}"
    echo "  For RHEL/Fedora: sudo dnf install ${missing_packages[*]}"
    echo ""
else
    echo "All required system packages are installed."
fi

# Check for Docker or Podman
if command -v podman &> /dev/null; then
    echo "Podman found, will use for container operations."
    CONTAINER_CMD="podman"
elif command -v docker &> /dev/null; then
    echo "Docker found, will use for container operations."
    CONTAINER_CMD="docker"
else
    echo "Warning: Neither Podman nor Docker found. You need to install one of them:"
    echo "  For Ubuntu/Debian: sudo apt install podman"
    echo "  For RHEL/Fedora: sudo dnf install podman"
    echo ""
fi

echo "=== Container-MCP Project Initialized ==="
echo "You can now proceed to build the container with bin/02-build-container.sh" 