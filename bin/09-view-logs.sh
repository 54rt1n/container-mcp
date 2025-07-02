#!/bin/bash
set -e

# Container-MCP Log Viewer Script
# This script provides various options for viewing Container-MCP logs

echo "=== Container-MCP Log Viewer ==="

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

# Parse command line arguments
FOLLOW=false
LINES=""
SINCE=""
TIMESTAMPS=false

# Display usage information
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -f, --follow         Follow log output (live tail)"
    echo "  -n, --lines NUM      Show last NUM lines (default: all)"
    echo "  -s, --since TIME     Show logs since timestamp (e.g., '2h', '2023-01-01T00:00:00')"
    echo "  -t, --timestamps     Show timestamps"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                   Show all logs"
    echo "  $0 -f                Follow logs in real-time"
    echo "  $0 -n 50             Show last 50 lines"
    echo "  $0 -f -t             Follow logs with timestamps"
    echo "  $0 -s 1h             Show logs from last hour"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -s|--since)
            SINCE="$2"
            shift 2
            ;;
        -t|--timestamps)
            TIMESTAMPS=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Build the logs command
LOGS_CMD="${CONTAINER_CMD} logs"

if [ "$FOLLOW" = true ]; then
    LOGS_CMD="$LOGS_CMD --follow"
fi

if [ -n "$LINES" ]; then
    LOGS_CMD="$LOGS_CMD --tail $LINES"
fi

if [ -n "$SINCE" ]; then
    LOGS_CMD="$LOGS_CMD --since $SINCE"
fi

if [ "$TIMESTAMPS" = true ]; then
    LOGS_CMD="$LOGS_CMD --timestamps"
fi

LOGS_CMD="$LOGS_CMD $CONTAINER_NAME"

# Check if container is running for live logs
if [ "$FOLLOW" = true ]; then
    CONTAINER_RUNNING=$(${CONTAINER_CMD} ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" 2>/dev/null || echo "")
    if [ -z "$CONTAINER_RUNNING" ]; then
        echo "Warning: Container ${CONTAINER_NAME} is not running. Showing existing logs only."
        echo "To follow live logs, start the container first with bin/04-run-container.sh"
        echo ""
    fi
fi

# Display log information
echo "Container: ${CONTAINER_NAME}"
if [ -n "$LINES" ]; then
    echo "Showing: Last $LINES lines"
elif [ -n "$SINCE" ]; then
    echo "Showing: Logs since $SINCE"
elif [ "$FOLLOW" = true ]; then
    echo "Mode: Following logs (Press CTRL+C to exit)"
else
    echo "Showing: All available logs"
fi

if [ "$TIMESTAMPS" = true ]; then
    echo "Timestamps: Enabled"
fi

echo "Command: $LOGS_CMD"
echo ""
echo "=== Container Logs ==="

# Execute the logs command
exec $LOGS_CMD 