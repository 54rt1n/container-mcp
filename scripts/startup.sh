#!/bin/bash
set -e

echo "Starting Container-MCP..."

# Load AppArmor profiles if AppArmor is available
if [ -d "/sys/kernel/security/apparmor" ]; then
  echo "Loading AppArmor profiles..."
  apparmor_parser -r /etc/apparmor.d/mcp-bash || true
  apparmor_parser -r /etc/apparmor.d/mcp-python || true
else
  echo "AppArmor not available, skipping profile loading"
fi

# Start the main application
echo "Launching MCP application..."
exec /app/.venv/bin/python /app/cmcp/main.py "$@" 