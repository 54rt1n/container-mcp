#!/bin/bash
set -e

# Container-MCP Container Run Script
# This script runs the Container-MCP container

echo "=== Container-MCP Container Run ==="

# Check if podman or docker is installed
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    COMPOSE_CMD="podman-compose"
    COMPOSE_FILE="podman-compose.yml"
    echo "Using Podman for container operations."
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    COMPOSE_CMD="docker compose"
    COMPOSE_FILE="docker-compose.yml"
    echo "Using Docker for container operations."
else
    echo "Neither Podman nor Docker found. Please install one of them and try again."
    exit 1
fi

# Check if the container is already running
CONTAINER_NAME="container-mcp"
RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$RUNNING" ]; then
    echo "Container ${CONTAINER_NAME} is already running. Stopping it..."
    ${CONTAINER_CMD} stop ${CONTAINER_NAME}
    echo "Container stopped."
fi

# Check if container exists but is not running (Created, Exited, etc.)
EXISTS=$(${CONTAINER_CMD} ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$EXISTS" ]; then
    echo "Container ${CONTAINER_NAME} exists but is not running. Removing it..."
    ${CONTAINER_CMD} rm ${CONTAINER_NAME}
    echo "Container removed."
fi

# Check if compose file exists
if [ -f "${COMPOSE_FILE}" ]; then
    # Check if compose command is available
    if command -v ${COMPOSE_CMD} &> /dev/null || [ "${COMPOSE_CMD}" = "docker compose" ]; then
        echo "Starting container using ${COMPOSE_FILE}..."
        
        # If using docker compose (with space), handle it differently
        if [ "${COMPOSE_CMD}" = "docker compose" ]; then
            docker compose -f ${COMPOSE_FILE} up -d
        else
            ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d
        fi
        
        echo "Container started using compose."
    else
        echo "Compose command not found. Falling back to direct container run."
        # Fall back to direct container run
        RUN_CONTAINER=true
    fi
else
    echo "Compose file not found. Using direct container run."
    RUN_CONTAINER=true
fi

# Run container directly if needed
if [ "${RUN_CONTAINER}" = "true" ]; then
    echo "Running container directly..."
    
    # Get configuration from env file
    if [ -f "volume/config/app.env" ]; then
        echo "Using app.env file"
        ENV_FILE="volume/config/app.env"
    elif [ -f "volume/config/default.env" ]; then
        echo "Using default.env file"
        ENV_FILE="volume/config/default.env"
    else
        echo "No configuration file found!"
        exit 1
    fi
    
    # Get MCP port from env file
    MCP_PORT=$(grep "^MCP_PORT=" ${ENV_FILE} | cut -d'=' -f2)
    MCP_PORT=${MCP_PORT:-8000}  # Default to 8000 if not found
    LISTENER_HOST=$(grep "^LISTENER_HOST=" ${ENV_FILE} | cut -d'=' -f2)
    LISTENER_HOST=${LISTENER_HOST:-127.0.0.1}
    
    echo "Starting container on ${LISTENER_HOST}:${MCP_PORT}..."
    
    # Run the container with the --replace flag to handle existing containers
    ${CONTAINER_CMD} run -d \
        --name ${CONTAINER_NAME} \
        --user $(id -u):$(id -g) \
        -p ${LISTENER_HOST}:${MCP_PORT}:8000 \
        -v "$(pwd)/volume/config:/app/config:Z" \
        -v "$(pwd)/volume/logs:/app/logs:Z" \
        -v "$(pwd)/volume/data:/app/data:Z" \
        -v "$(pwd)/volume/sandbox:/app/sandbox:Z" \
        -v "$(pwd)/volume/temp:/app/temp:Z" \
        -v "$(pwd)/volume/kb:/app/kb:Z" \
        --security-opt apparmor:unconfined \
        --restart unless-stopped \
        --env-file ${ENV_FILE} \
        container-mcp:latest
        
    echo "Container started directly."
fi

# Check if container is running
sleep 2
RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$RUNNING" ]; then
    echo "Container is now running."
    echo "To view logs, run: ${CONTAINER_CMD} logs -f ${CONTAINER_NAME}"
    echo "To stop it, run: ${CONTAINER_CMD} stop ${CONTAINER_NAME}"
    
    # Show host and port information
    PORT_INFO=$(${CONTAINER_CMD} port ${CONTAINER_NAME} 2>/dev/null || echo "")
    if [ -n "$PORT_INFO" ]; then
        echo "Container is accessible at: ${PORT_INFO}"
    else
        echo "Container is accessible at: http://localhost:${MCP_PORT}"
    fi
else
    echo "Failed to start the container. Check logs for more information."
    ${CONTAINER_CMD} logs ${CONTAINER_NAME} 2>/dev/null || echo "No logs available."
    exit 1
fi

echo "=== Container Run Complete ==="
echo "To check the container status, run: bin/05-check-container.sh" 
echo "To run tests against the container, execute: bin/06-run-tests.sh"
echo "To view container logs, execute: bin/09-view-logs.sh" 
