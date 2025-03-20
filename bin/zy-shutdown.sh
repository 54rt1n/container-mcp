#!/bin/bash
set -e

# Container-MCP Shutdown Script
# This script safely shuts down the Container-MCP environment

echo "=== Container-MCP Shutdown ==="

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

# Check if the container is running
RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$RUNNING" ]; then
    echo "Container ${CONTAINER_NAME} is running. Stopping it..."
    ${CONTAINER_CMD} stop ${CONTAINER_NAME}
    echo "Container stopped."
else
    echo "Container ${CONTAINER_NAME} is not running."
fi

echo "=== Container-MCP Shutdown Complete ==="
echo "You can restart the container with: ${CONTAINER_CMD} start ${CONTAINER_NAME}"
echo "For complete teardown, use: bin/zz-teardown.sh" 