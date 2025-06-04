#!/bin/bash
set -e

# Container-MCP Container Status Check Script
# This script checks if the container is running and displays logs if it's not

echo "=== Container-MCP Status Check ==="

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
    echo "Container details:"
    ${CONTAINER_CMD} inspect ${CONTAINER_NAME} --format "ID: {{.Id}}\nCreated: {{.Created}}\nStatus: {{.State.Status}}"
    
    # Check if container has health check before trying to display it
    HEALTH_CHECK=$(${CONTAINER_CMD} inspect ${CONTAINER_NAME} --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}No health check configured{{end}}" 2>/dev/null || echo "Health check information not available")
    echo "Health: ${HEALTH_CHECK}"
    
    # Get port mapping
    PORT_INFO=$(${CONTAINER_CMD} port ${CONTAINER_NAME} 2>/dev/null || echo "")
    if [ -n "$PORT_INFO" ]; then
        echo "Container is accessible at: ${PORT_INFO}"
    else
        # Try to get port from config
        if [ -f "volume/config/app.env" ]; then
            MCP_PORT=$(grep "^MCP_PORT=" volume/config/custom.env | cut -d'=' -f2)
            echo "Container should be accessible at: http://localhost:${MCP_PORT}"
        else
            echo "Port information not available."
        fi
    fi
    
    # Show last 10 lines of logs
    echo ""
    echo "Last 10 log lines:"
    ${CONTAINER_CMD} logs --tail 10 ${CONTAINER_NAME}

    echo ""
    echo "To view full logs, run: ${CONTAINER_CMD} logs -f ${CONTAINER_NAME}"
else
    echo "❌ Container ${CONTAINER_NAME} is not running."
    CONTAINER_STATUS=$(${CONTAINER_CMD} inspect ${CONTAINER_NAME} --format "{{.State.Status}}" 2>/dev/null || echo "unknown")
    echo "Container status: ${CONTAINER_STATUS}"
    
    # Check if container has exited with an error
    EXIT_CODE=$(${CONTAINER_CMD} inspect ${CONTAINER_NAME} --format "{{.State.ExitCode}}" 2>/dev/null || echo "unknown")
    if [ "$EXIT_CODE" != "0" ] && [ "$EXIT_CODE" != "unknown" ]; then
        echo "Container exited with code: ${EXIT_CODE}"
    fi
    
    echo ""
    echo "Container logs:"
    ${CONTAINER_CMD} logs ${CONTAINER_NAME}
    
    echo ""
    echo "Would you like to restart the container? (y/n)"
    read -r restart_container
    
    if [[ $restart_container == "y" || $restart_container == "Y" ]]; then
        echo "Restarting container..."
        ${CONTAINER_CMD} restart ${CONTAINER_NAME}
        
        # Verify restart
        sleep 3
        CONTAINER_RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")
        if [ -n "$CONTAINER_RUNNING" ]; then
            echo "✅ Container ${CONTAINER_NAME} is now running."
        else
            echo "❌ Failed to restart container ${CONTAINER_NAME}."
            echo "Please check logs and try running bin/04-run-container.sh again."
        fi
    fi
fi

echo "=== Status Check Complete ===" 
