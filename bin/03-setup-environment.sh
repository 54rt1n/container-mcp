#!/bin/bash
set -e

# Container-MCP Environment Setup Script
# This script sets up the environment for running the Container-MCP container

echo "=== Container-MCP Environment Setup ==="

# Check if podman or docker is installed
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    echo "Using Podman for container operations."
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    echo "Using Docker for container operations."
else
    echo "Neither Podman nor Docker found. Please install one of them and try again."
    exit 1
fi

# Set up directories with appropriate permissions
echo "Setting up directories for container volumes..."

# Create directories if they don't exist
mkdir -p volume/{data,logs,config,sandbox,temp,kb}

# Copy the available commands list to sandbox
if [ -f "resources/AVAILABLE_COMMANDS.txt" ]; then
    echo "Copying available commands list to sandbox..."
    cp resources/AVAILABLE_COMMANDS.txt volume/sandbox/
fi

# Ensure permissions are set correctly
# All directories under volume need to be writable by the container
chmod -R 777 volume

echo "Directories set up successfully."

# Check if SELinux is enabled
if command -v getenforce &> /dev/null && [ "$(getenforce)" != "Disabled" ]; then
    echo "SELinux is enabled, setting appropriate context for volume mounts..."
    # Set SELinux context for container volumes
    if command -v chcon &> /dev/null; then
        chcon -Rt container_file_t volume
        echo "SELinux context set for container volumes."
    else
        echo "Warning: chcon command not found, SELinux context not set."
    fi
fi

# Create a network for the container if it doesn't exist
NETWORK_NAME="container-mcp-network"
if ! ${CONTAINER_CMD} network ls | grep -q ${NETWORK_NAME}; then
    echo "Creating container network: ${NETWORK_NAME}..."
    ${CONTAINER_CMD} network create ${NETWORK_NAME}
    echo "Network created."
else
    echo "Network ${NETWORK_NAME} already exists."
fi

# Copy default configuration if app.env doesn't exist
if [ ! -f "volume/config/app.env" ] && [ -f "volume/config/default.env" ]; then
    echo "Creating app configuration from default..."
    cp volume/config/default.env volume/config/app.env
    echo "You can modify the app configuration in volume/config/app.env"
fi

# Ensure port comments are correct in app.env
if [ -f "volume/config/app.env" ]; then
    # Check if port comment exists, add if not
    if ! grep -q "Note: The port value below defines the external port mapping" volume/config/app.env; then
        # Create temporary file with updated content
        sed -i '2i# Note: The port value below defines the external port mapping.\n# Inside the container, the application always listens on port 8000.' volume/config/app.env
        echo "Updated port configuration comments in app.env"
    fi
fi

# Set up container-compose file if using Docker
if [ "${CONTAINER_CMD}" = "docker" ] && [ -f "podman-compose.yml" ]; then
    echo "Creating docker-compose.yml from podman-compose.yml..."
    cp podman-compose.yml docker-compose.yml
    echo "docker-compose.yml created."
fi

# Install required host system packages
echo "Checking for required system packages..."

required_packages=("firejail" "apparmor" "apparmor-utils")
missing_packages=()

for pkg in "${required_packages[@]}"; do
    if ! command -v ${pkg} &> /dev/null && ! dpkg -l | grep -q ${pkg}; then
        missing_packages+=("${pkg}")
    fi
done

if [ ${#missing_packages[@]} -gt 0 ]; then
    echo "The following required packages are missing: ${missing_packages[*]}"
    echo "Please install them using your system's package manager."
    echo "For Ubuntu/Debian: sudo apt install ${missing_packages[*]}"
    echo "For RHEL/Fedora: sudo dnf install ${missing_packages[*]}"
fi

echo "=== Environment Setup Complete ==="
echo "The environment is ready for running the Container-MCP container."
echo "To run the container, execute: bin/04-run-container.sh" 
