#!/bin/bash
set -e

# Container-MCP Container Build Script
# This script builds the Container-MCP container image

echo "=== Container-MCP Container Build ==="

# Check if podman or docker is installed
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    echo "Using Podman to build the container."
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    echo "Using Docker to build the container."
else
    echo "Neither Podman nor Docker found. Please install one of them and try again."
    exit 1
fi

# Set container image name and tag
IMAGE_NAME="container-mcp"
TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

# Build the container image
echo "Building container image: ${FULL_IMAGE_NAME}..."
${CONTAINER_CMD} build -t ${FULL_IMAGE_NAME} -f Containerfile .

# Check build result
if [ $? -eq 0 ]; then
    echo "Container image built successfully."
    
    # Display image information
    echo "Image information:"
    ${CONTAINER_CMD} image inspect ${FULL_IMAGE_NAME} --format "{{.Id}}" | cut -d':' -f2 | cut -c1-12
    
    # Create a tag with date
    DATE_TAG=$(date +"%Y%m%d")
    ${CONTAINER_CMD} tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:${DATE_TAG}
    echo "Created additional tag: ${IMAGE_NAME}:${DATE_TAG}"
    
    echo "=== Build Complete ==="
    echo "To run the container, execute: bin/04-run-container.sh"
    echo "To set up the environment first, execute: bin/03-setup-environment.sh"
else
    echo "Container build failed!"
    exit 1
fi 