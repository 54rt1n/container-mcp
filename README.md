# Container-MCP

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A secure, container-based implementation of the Model Context Protocol (MCP) for executing tools on behalf of large language models.

## Overview

Container-MCP provides a sandboxed environment for safely executing code, running commands, accessing files, and performing web operations requested by large language models. It implements the MCP protocol to expose these capabilities as tools that can be discovered and called by AI systems in a secure manner.

The architecture uses a domain-specific manager pattern with multi-layered security to ensure tools execute in isolated environments with appropriate restrictions, protecting the host system from potentially harmful operations.

## Key Features

- **Multi-layered Security**
  - Container isolation using Podman/Docker
  - AppArmor profiles for restricting access
  - Firejail sandboxing for additional isolation
  - Resource limits (CPU, memory, execution time)
  - Path traversal prevention
  - Allowed extension restrictions

- **MCP Protocol Implementation**
  - Standardized tool discovery and execution
  - Resource management
  - Async execution support

- **Domain-Specific Managers**
  - `BashManager`: Secure command execution
  - `PythonManager`: Sandboxed Python code execution
  - `FileManager`: Safe file operations
  - `WebManager`: Secure web browsing and scraping

- **Configurable Environment**
  - Extensive configuration via environment variables
  - Custom environment support
  - Development and production modes

## Available Tools

### System Operations

#### `system_run_command`
Executes bash commands in a secure sandbox environment.

- **Parameters**:
  - `command` (string, required): The bash command to execute
  - `working_dir` (string, optional): Working directory (ignored in sandbox)
- **Returns**:
  - `stdout` (string): Command standard output
  - `stderr` (string): Command standard error
  - `exit_code` (integer): Command exit code
  - `success` (boolean): Whether command completed successfully

```json
{
  "stdout": "file1.txt\nfile2.txt\n",
  "stderr": "",
  "exit_code": 0,
  "success": true
}
```

#### `system_run_python`
Executes Python code in a secure sandbox environment.

- **Parameters**:
  - `code` (string, required): Python code to execute
  - `working_dir` (string, optional): Working directory (ignored in sandbox)
- **Returns**:
  - `output` (string): Print output from the code
  - `error` (string): Error output from the code
  - `result` (any): Optional return value (available if code sets `_` variable)
  - `success` (boolean): Whether code executed successfully

```json
{
  "output": "Hello, world!\n",
  "error": "",
  "result": 42,
  "success": true
}
```

#### `system_env_var`
Gets environment variable values.

- **Parameters**:
  - `var_name` (string, optional): Specific variable to retrieve
- **Returns**:
  - `variables` (object): Dictionary of environment variables
  - `requested_var` (string): Value of the requested variable (if var_name provided)

```json
{
  "variables": {
    "MCP_PORT": "8000",
    "SANDBOX_ROOT": "/app/sandbox"
  },
  "requested_var": "8000"
}
```

### File Operations

#### `file_read`
Reads file contents safely.

- **Parameters**:
  - `path` (string, required): Path to the file (relative to sandbox root)
  - `encoding` (string, optional): File encoding (default: "utf-8")
- **Returns**:
  - `content` (string): File content
  - `size` (integer): File size in bytes
  - `modified` (float): Last modified timestamp
  - `success` (boolean): Whether the read was successful

```json
{
  "content": "This is the content of the file.",
  "size": 31,
  "modified": 1673452800.0,
  "success": true
}
```

#### `file_write`
Writes content to a file safely.

- **Parameters**:
  - `path` (string, required): Path to the file (relative to sandbox root)
  - `content` (string, required): Content to write
  - `encoding` (string, optional): File encoding (default: "utf-8")
- **Returns**:
  - `success` (boolean): Whether the write was successful
  - `path` (string): Path to the written file

```json
{
  "success": true,
  "path": "data/myfile.txt"
}
```

#### `file_list`
Lists contents of a directory safely.

- **Parameters**:
  - `path` (string, optional): Path to the directory (default: "/")
  - `pattern` (string, optional): Glob pattern to filter files
- **Returns**:
  - `entries` (array): List of directory entries with metadata
  - `path` (string): The listed directory path
  - `success` (boolean): Whether the listing was successful

```json
{
  "entries": [
    {
      "name": "file1.txt",
      "path": "file1.txt",
      "is_directory": false,
      "size": 1024,
      "modified": 1673452800.0
    },
    {
      "name": "data",
      "path": "data",
      "is_directory": true,
      "size": null,
      "modified": 1673452500.0
    }
  ],
  "path": "/",
  "success": true
}
```

#### `file_delete`
Deletes a file safely.

- **Parameters**:
  - `path` (string, required): Path of the file to delete
- **Returns**:
  - `success` (boolean): Whether the deletion was successful
  - `path` (string): Path to the deleted file

```json
{
  "success": true,
  "path": "temp/old_file.txt"
}
```

#### `file_move`
Moves or renames a file safely.

- **Parameters**:
  - `source` (string, required): Source file path
  - `destination` (string, required): Destination file path
- **Returns**:
  - `success` (boolean): Whether the move was successful
  - `source` (string): Original file path
  - `destination` (string): New file path

```json
{
  "success": true,
  "source": "data/old_name.txt",
  "destination": "data/new_name.txt"
}
```

### Web Operations

#### `web_search`
Uses a search engine to find information on the web.

- **Parameters**:
  - `query` (string, required): The query to search for
- **Returns**:
  - `results` (array): List of search results
  - `query` (string): The original query

```json
{
  "results": [
    {
      "title": "Search Result Title",
      "url": "https://example.com/page1",
      "snippet": "Text snippet from the search result..."
    }
  ],
  "query": "example search query"
}
```

#### `web_scrape`
Scrapes a specific URL and returns the content.

- **Parameters**:
  - `url` (string, required): The URL to scrape
  - `selector` (string, optional): CSS selector to target specific content
- **Returns**:
  - `content` (string): Scraped content
  - `url` (string): The URL that was scraped
  - `title` (string): Page title
  - `success` (boolean): Whether the scrape was successful
  - `error` (string): Error message if scrape failed

```json
{
  "content": "This is the content of the web page...",
  "url": "https://example.com/page",
  "title": "Example Page",
  "success": true,
  "error": null
}
```

#### `web_browse`
Interactively browses a website using Playwright.

- **Parameters**:
  - `url` (string, required): Starting URL for browsing session
- **Returns**:
  - `content` (string): Page HTML content
  - `url` (string): The final URL after any redirects
  - `title` (string): Page title
  - `success` (boolean): Whether the browsing was successful
  - `error` (string): Error message if browsing failed

```json
{
  "content": "<!DOCTYPE html><html>...</html>",
  "url": "https://example.com/after_redirect",
  "title": "Example Page",
  "success": true,
  "error": null
}
```

## Execution Environment

Container-MCP provides isolated execution environments for different types of operations, each with its own security measures and resource constraints.

### Container Environment

The main Container-MCP service runs inside a container (using Podman or Docker) providing the first layer of isolation:

- **Base Image**: Ubuntu 24.04
- **User**: Non-root ubuntu user
- **Python**: 3.12
- **Network**: Limited to localhost binding only
- **Filesystem**: Volume mounts for configuration, data, and logs
- **Security**: AppArmor, Seccomp, and capability restrictions

### Bash Execution Environment

The Bash execution environment is configured with multiple isolation layers:

- **Allowed Commands**: Restricted to safe commands configured in `BASH_ALLOWED_COMMANDS`
- **Firejail Sandbox**: Process isolation with restricted filesystem access
- **AppArmor Profile**: Fine-grained access control
- **Resource Limits**:
  - Execution timeout (default: 30s, max: 120s)
  - Limited directory access to sandbox only
- **Network**: No network access
- **File System**: Read-only access to data, read-write to sandbox

Example allowed commands:
```
ls, cat, grep, find, echo, pwd, mkdir, touch
```

### Python Execution Environment

The Python execution environment is designed for secure code execution:

- **Python Version**: 3.12
- **Memory Limit**: Configurable memory ceiling (default: 256MB)
- **Execution Timeout**: Configurable time limit (default: 30s, max: 120s)
- **AppArmor Profile**: Restricts access to system resources
- **Firejail Sandbox**: Process isolation
- **Capabilities**: All capabilities dropped
- **Network**: No network access
- **Available Libraries**: Only standard library
- **Output Capturing**: stdout/stderr redirected and sanitized
- **Resource Controls**: CPU and memory limits enforced

### File System Environment

The file system environment controls access to files within the sandbox:

- **Base Directory**: All operations restricted to sandbox root
- **Path Validation**: All paths normalized and checked for traversal attempts
- **Size Limits**: Maximum file size enforced (default: 10MB)
- **Extension Control**: Only allowed extensions permitted (default: txt, md, csv, json, py)
- **Permission Control**: Appropriate read/write permissions enforced
- **Isolation**: No access to host file system

### Web Environment

The web environment provides controlled access to external resources:

- **Domain Control**: Optional whitelisting of allowed domains
- **Timeout Control**: Configurable timeouts for operations
- **Browser Control**: Headless browser via Playwright for full rendering
- **Scraping Control**: Simple scraping via requests/BeautifulSoup
- **Content Sanitization**: All content parsed and sanitized
- **Network Isolation**: Separate network namespace via container

## Architecture

The project follows a modular architecture:

```
container-mcp/
├── cmcp/                     # Main application code
│   ├── managers/             # Domain-specific managers
│   │   ├── bash_manager.py   # Secure bash execution
│   │   ├── python_manager.py # Secure python execution
│   │   ├── file_manager.py   # Secure file operations
│   │   └── web_manager.py    # Secure web operations
│   ├── utils/                # Utility functions
│   ├── config.py             # Configuration system
│   └── main.py               # MCP server setup
├── apparmor/                 # AppArmor profiles
├── config/                   # Configuration files
├── bin/                      # Build/run scripts
├── data/                     # Data directory
├── logs/                     # Log directory
├── sandbox/                  # Sandboxed execution space
│   ├── bash/                 # Bash sandbox
│   ├── python/               # Python sandbox
│   ├── files/                # File operation sandbox
│   └── browser/              # Web browser sandbox
├── temp/                     # Temporary storage
└── tests/                    # Test suites
```

Each manager follows consistent design patterns:
- `.from_env()` class method for environment-based initialization
- Async execution methods for non-blocking operations
- Strong input validation and error handling
- Security-first approach to all operations

## Security Measures

Container-MCP implements multiple layers of security:

1. **Container Isolation**: Uses Podman/Docker for container isolation
2. **AppArmor Profiles**: Fine-grained access control for bash and Python execution
3. **Firejail Sandboxing**: Additional process isolation
4. **Resource Limits**: Memory, CPU, and execution time limits
5. **Path Traversal Prevention**: Validates and normalizes all file paths
6. **Allowed Extension Restrictions**: Controls what file types can be accessed
7. **Network Restrictions**: Controls what domains can be accessed
8. **Least Privilege**: Components run with minimal necessary permissions

## Installation

### Prerequisites

- Linux system with Podman or Docker
- Python 3.12+
- Firejail (`apt install firejail` or `dnf install firejail`)
- AppArmor (`apt install apparmor apparmor-utils` or `dnf install apparmor apparmor-utils`)

### Quick Start

The quickest way to get started is to use the all-in-one script:

```bash
git clone https://github.com/container-mcp/container-mcp.git
cd container-mcp
chmod +x bin/00-all-in-one.sh
./bin/00-all-in-one.sh
```

### Step-by-Step Installation

You can also perform the installation steps individually:

1. **Initialize the project**:
   ```bash
   ./bin/01-init.sh
   ```

2. **Build the container**:
   ```bash
   ./bin/02-build-container.sh
   ```

3. **Set up the environment**:
   ```bash
   ./bin/03-setup-environment.sh
   ```

4. **Run the container**:
   ```bash
   ./bin/04-run-container.sh
   ```

5. **Run tests** (optional):
   ```bash
   ./bin/05-run-tests.sh
   ```

## Usage

Once the container is running, you can connect to it using any MCP client implementation. The server will be available at `http://localhost:8000` or the port specified in your configuration.

### Example Python Client

```python
from mcp.client import MCPClient

async def main():
    # Connect to the Container-MCP server
    client = await MCPClient.connect("http://localhost:8000")
    
    # Discover available tools
    tools = await client.get_tools()
    print(f"Available tools: {[t.name for t in tools]}")
    
    # Execute a Python script
    result = await client.execute_tool("system_run_python", {
        "code": "print('Hello, world!')\nresult = 42\n_ = result"
    })
    print(f"Python result: {result}")
    
    # Execute a bash command
    result = await client.execute_tool("system_run_command", {
        "command": "ls -la"
    })
    print(f"Command output: {result['stdout']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Configuration

Container-MCP can be configured through environment variables, which can be set in `config/custom.env`:

### Server Configuration

```
# MCP Server Configuration
MCP_HOST=127.0.0.1
MCP_PORT=9000
DEBUG=true
LOG_LEVEL=INFO
```

### Bash Manager Configuration

```
# Bash Manager Configuration
BASH_ALLOWED_COMMANDS=ls,cat,grep,find,echo,pwd,mkdir,touch
BASH_TIMEOUT_DEFAULT=30
BASH_TIMEOUT_MAX=120
```

### Python Manager Configuration

```
# Python Manager Configuration
PYTHON_MEMORY_LIMIT=256
PYTHON_TIMEOUT_DEFAULT=30
PYTHON_TIMEOUT_MAX=120
```

### File Manager Configuration

```
# File Manager Configuration 
FILE_MAX_SIZE_MB=10
FILE_ALLOWED_EXTENSIONS=txt,md,csv,json,py
```

### Web Manager Configuration

```
# Web Manager Configuration
WEB_TIMEOUT_DEFAULT=30
WEB_ALLOWED_DOMAINS=*
```

## Development

### Setting Up a Development Environment

1. Create a Python virtual environment:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit

# Run only integration tests
pytest tests/integration

# Run with coverage report
pytest --cov=cmcp --cov-report=term --cov-report=html
```

### Development Server

To run the MCP server in development mode:

```bash
python -m cmcp.main --test-mode
```

## License

This project is licensed under the Apache License 2.0.

## Author

Martin Bukowski
