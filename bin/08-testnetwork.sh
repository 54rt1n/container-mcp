#!/bin/bash

# Test Network Connectivity to Container-MCP SSE Endpoint
# Tests if the 8080/sse endpoint is responding properly

set -e

# Configuration
HOST="${HOST:-localhost}"
PORT="${PORT:-8000}"
HEALTH_ENDPOINT="/health"
TIMEOUT="${TIMEOUT:-10}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Testing Container-MCP Network Connectivity"
echo "==========================================="
echo "Host: $HOST"
echo "Port: $PORT"
echo "Health Endpoint: $HEALTH_ENDPOINT"
echo "Timeout: ${TIMEOUT}s"
echo ""

# Function to test basic connectivity
test_basic_connectivity() {
    echo -n "Testing basic connectivity to $HOST:$PORT... "
    if timeout $TIMEOUT bash -c "</dev/tcp/$HOST/$PORT" 2>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        return 1
    fi
}

# Function to test HTTP response
test_http_response() {
    echo -n "Testing HTTP response on $HOST:$PORT... "
    
    # Try to get HTTP response using curl
    if command -v curl >/dev/null 2>&1; then
        response=$(curl -s -w "%{http_code}" -o /dev/null --connect-timeout $TIMEOUT "http://$HOST:$PORT/" 2>/dev/null || echo "000")
        if [[ "$response" =~ ^[2-5][0-9][0-9]$ ]]; then
            echo -e "${GREEN}✓ PASS${NC} (HTTP $response)"
            return 0
        else
            echo -e "${RED}✗ FAIL${NC} (HTTP $response)"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ SKIP${NC} (curl not available)"
        return 0
    fi
}

# Function to test health endpoint specifically
test_health_endpoint() {
    echo -n "Testing health endpoint $HOST:$PORT$HEALTH_ENDPOINT... "
    
    if command -v curl >/dev/null 2>&1; then
        # Test health endpoint and get detailed response
        response=$(curl -s -w "%{http_code}" \
            --connect-timeout $TIMEOUT \
            -H "Accept: application/json" \
            "http://$HOST:$PORT$HEALTH_ENDPOINT" 2>/dev/null || echo "000")
        
        # Extract status code from response
        status_code="${response: -3}"
        response_body="${response%???}"
        
        if [[ "$status_code" =~ ^[2][0-9][0-9]$ ]]; then
            echo -e "${GREEN}✓ PASS${NC} (HTTP $status_code)"
            # Try to extract server status from JSON response
            if command -v jq >/dev/null 2>&1 && echo "$response_body" | jq -e '.status' >/dev/null 2>&1; then
                server_status=$(echo "$response_body" | jq -r '.status')
                server_name=$(echo "$response_body" | jq -r '.server.name // "Unknown"')
                echo "    Server: $server_name, Status: $server_status"
            fi
            return 0
        else
            echo -e "${RED}✗ FAIL${NC} (HTTP $status_code)"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ SKIP${NC} (curl not available)"
        return 0
    fi
}

# Function to test container status
test_container_status() {
    echo -n "Checking container status... "
    
    if command -v podman >/dev/null 2>&1; then
        if podman ps --filter "name=container-mcp" --format "{{.Status}}" | grep -q "Up"; then
            echo -e "${GREEN}✓ RUNNING${NC}"
            return 0
        else
            echo -e "${RED}✗ NOT RUNNING${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ SKIP${NC} (podman not available)"
        return 0
    fi
}

# Function to show container logs if there's an issue
show_container_logs() {
    echo ""
    echo "Container logs (last 10 lines):"
    echo "================================"
    if command -v podman >/dev/null 2>&1; then
        podman logs --tail 10 container-mcp 2>/dev/null || echo "Could not retrieve logs"
    else
        echo "Podman not available - cannot show logs"
    fi
}

# Run all tests
test_passed=0
test_total=0

echo "Running connectivity tests..."
echo ""

# Test 1: Container Status
test_total=$((test_total + 1))
if test_container_status; then
    test_passed=$((test_passed + 1))
fi

# Test 2: Basic Connectivity
test_total=$((test_total + 1))
if test_basic_connectivity; then
    test_passed=$((test_passed + 1))
fi

# Test 3: HTTP Response
test_total=$((test_total + 1))
if test_http_response; then
    test_passed=$((test_passed + 1))
fi

# Test 4: Health Endpoint
test_total=$((test_total + 1))
if test_health_endpoint; then
    test_passed=$((test_passed + 1))
fi

# Summary
echo ""
echo "Test Results:"
echo "============="
echo "Passed: $test_passed/$test_total"

python scripts/list_tools.py

if [ $test_passed -eq $test_total ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo "The Container-MCP service appears to be working correctly!"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo "There may be connectivity issues with the Container-MCP service."
    
    # Show troubleshooting info
    echo ""
    echo "Troubleshooting:"
    echo "================"
    echo "• Check if the container is running: podman ps"
    echo "• Check container logs: podman logs container-mcp"
    echo "• Verify port mapping: podman port container-mcp"
    echo "• Test different host: HOST=<ip> ./bin/08-testnetwork.sh"
    
    show_container_logs
    exit 1
fi 