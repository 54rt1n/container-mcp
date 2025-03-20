#!/bin/bash
set -e

# Container-MCP Complete Teardown Script
# This script completely removes the container, network, and images without prompting

echo "=== Container-MCP Complete Teardown ==="
echo "This script will:"
echo "1. Stop the running container"
echo "2. Remove the container"
echo "3. Remove the container network"
echo "4. Remove all container images"
echo ""
echo "Press ENTER to continue or CTRL+C to cancel..."
read -r

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

CONTAINER_NAME="container-mcp"
NETWORK_NAME="container-mcp-network"
IMAGE_NAME="container-mcp"

# Step 1: Stop the container if running
RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")
if [ -n "$RUNNING" ]; then
    echo "Stopping container ${CONTAINER_NAME}..."
    ${CONTAINER_CMD} stop ${CONTAINER_NAME}
    echo "Container stopped."
else
    echo "Container ${CONTAINER_NAME} is not running."
fi

# Step 2: Remove the container if it exists
EXISTS=$(${CONTAINER_CMD} ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")
if [ -n "$EXISTS" ]; then
    echo "Removing container ${CONTAINER_NAME}..."
    ${CONTAINER_CMD} rm ${CONTAINER_NAME}
    echo "Container removed."
else
    echo "Container ${CONTAINER_NAME} does not exist."
fi

# Step 3: Remove the network if it exists
if ${CONTAINER_CMD} network ls | grep -q ${NETWORK_NAME}; then
    echo "Removing container network: ${NETWORK_NAME}..."
    ${CONTAINER_CMD} network rm ${NETWORK_NAME}
    echo "Network removed."
else
    echo "Network ${NETWORK_NAME} does not exist."
fi

# Step 4: Remove all container images matching the name
IMAGE_EXISTS=$(${CONTAINER_CMD} images ${IMAGE_NAME} -q 2>/dev/null || echo "")
if [ -n "$IMAGE_EXISTS" ]; then
    echo "Removing container image ${IMAGE_NAME}:latest..."
    ${CONTAINER_CMD} rmi ${IMAGE_NAME}:latest 2>/dev/null || echo "Latest image not found or could not be removed."
    
    # Also remove any dated tags
    DATED_IMAGES=$(${CONTAINER_CMD} images | grep ${IMAGE_NAME} | awk '{print $1":"$2}')
    if [ -n "$DATED_IMAGES" ]; then
        echo "Removing all dated container images..."
        for img in $DATED_IMAGES; do
            ${CONTAINER_CMD} rmi $img 2>/dev/null || echo "Could not remove $img."
        done
    fi
    
    echo "Container image(s) removed."
else
    echo "No container images found for ${IMAGE_NAME}."
fi

# Ask if user wants to clean data directories
echo ""
echo "Would you like to also clean up ALL data directories? (sandbox, logs, temp) (y/N)"
read -r clean_data

if [[ $clean_data == "y" || $clean_data == "Y" ]]; then
    echo "Cleaning up data directories..."
    # Remove contents but not the directories themselves
    rm -rf sandbox/* 2>/dev/null || true
    rm -rf logs/* 2>/dev/null || true
    rm -rf temp/* 2>/dev/null || true
    rm -rf data/* 2>/dev/null || true
    rm -rf volume/sandbox/* 2>/dev/null || true
    rm -rf volume/logs/* 2>/dev/null || true
    rm -rf volume/temp/* 2>/dev/null || true
    rm -rf volume/data/* 2>/dev/null || true
    echo "Data directories cleaned."
fi

echo "=== Container-MCP Teardown Complete ==="
echo "All container resources have been removed."
echo "You can rebuild the environment with: bin/00-all-in-one.sh" 