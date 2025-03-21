#!/bin/bash
set -e

# Container-MCP Container Attach Script
# This script attaches a shell to the running container-mcp container

echo "=== Container-MCP Shell Attach ==="

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

# Container name
CONTAINER_NAME="container-mcp"

# Check if container exists
CONTAINER_EXISTS=$(${CONTAINER_CMD} ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -z "$CONTAINER_EXISTS" ]; then
    echo "Container ${CONTAINER_NAME} does not exist. Please run bin/04-run-container.sh first."
    exit 1
fi

# Check if container is running
CONTAINER_RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$CONTAINER_RUNNING" ]; then
    echo "✅ Container ${CONTAINER_NAME} is running."
    echo "Attaching a shell to the container..."
    
    # Default shell to use
    SHELL_TO_USE=${1:-"/bin/bash"}
    
    # Attach shell to the container
    ${CONTAINER_CMD} exec -it ${CONTAINER_NAME} ${SHELL_TO_USE}
else
    echo "❌ Container ${CONTAINER_NAME} is not running."
    echo "Please start the container first using bin/04-run-container.sh or restart it using bin/05-check-container.sh"
    exit 1
fi

echo "=== Shell session ended ===" 