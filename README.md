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
  - `KnowledgeBaseManager`: Structured document storage with semantic search

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

### Knowledge Base Operations

The knowledge base system provides structured document storage with semantic search capabilities, RDF-style relationships, and metadata management. Documents are organized in a hierarchical namespace structure and support preferences (arbitrary RDF triples) and references (links between documents).

#### Document Path Format

Knowledge base documents use a structured path format: `namespace/collection[/subcollection]*/name`

- **namespace**: Top-level organizational unit (e.g., "projects", "research")
- **collection**: Main category within namespace (e.g., "documentation", "notes")
- **subcollection**: Optional nested categories (e.g., "api", "tutorials")
- **name**: Document identifier (e.g., "getting-started", "user-guide")

Examples:
- `projects/docs/api-reference`
- `research/papers/machine-learning/transformers`
- `personal/notes/meeting-2024-01-15`

#### `kb_create_document`
Creates a new document in the knowledge base with metadata but no content.

- **Parameters**:
  - `path` (string, required): Document path in format "namespace/collection[/subcollection]*/name"
  - `metadata` (object, optional): Document metadata (default: {})
- **Returns**:
  - Complete document index object with creation details
- **Notes**: This is part of a two-step process. Create the document first, then add content with `kb_write_content`.

```json
{
  "namespace": "projects",
  "collection": "docs",
  "name": "api-reference",
  "type": "document",
  "subtype": "text",
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-15T10:30:00.000Z",
  "content_type": "text/plain",
  "chunked": false,
  "fragments": {},
  "preferences": [],
  "references": [],
  "referenced_by": [],
  "indices": [],
  "metadata": {"author": "John Doe", "version": "1.0"}
}
```

#### `kb_write_content`
Writes content to an existing document in the knowledge base.

- **Parameters**:
  - `path` (string, required): Document path
  - `content` (string, required): Document content
  - `force` (boolean, optional): Whether to overwrite existing content (default: false)
- **Returns**:
  - Complete updated document index object
- **Notes**: Document must be created first using `kb_create_document`.

```json
{
  "namespace": "projects",
  "collection": "docs", 
  "name": "api-reference",
  "type": "document",
  "subtype": "text",
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-15T10:35:00.000Z",
  "content_type": "text/plain",
  "chunked": false,
  "fragments": {},
  "preferences": [],
  "references": [],
  "referenced_by": [],
  "indices": [],
  "metadata": {"author": "John Doe", "version": "1.0"}
}
```

#### `kb_read`
Reads document data from the knowledge base.

- **Parameters**:
  - `path` (string, required): Document path
  - `include_content` (boolean, optional): Whether to include document content (default: true)
  - `include_index` (boolean, optional): Whether to include document metadata (default: true)
- **Returns**:
  - Document data based on requested components

```json
{
  "status": "success",
  "path": "projects/docs/api-reference",
  "content": "This is the API reference content...",
  "index": {
    "namespace": "projects",
    "collection": "docs",
    "name": "api-reference",
    "created_at": "2024-01-15T10:30:00Z",
    "metadata": {"author": "John Doe"}
  }
}
```

#### `kb_update_metadata`
Updates metadata for a document in the knowledge base.

- **Parameters**:
  - `path` (string, required): Document path
  - `metadata` (object, required): Metadata to update
- **Returns**:
  - Complete updated document index object

```json
{
  "namespace": "projects",
  "collection": "docs",
  "name": "api-reference",
  "type": "document",
  "subtype": "text", 
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-15T10:40:00.000Z",
  "content_type": "text/plain",
  "chunked": false,
  "fragments": {},
  "preferences": [],
  "references": [],
  "referenced_by": [],
  "indices": [],
  "metadata": {"author": "John Doe", "version": "1.1", "reviewed": true}
}
```

#### `kb_manage_triples`
Manages RDF triples (preferences and references) for documents.

- **Parameters**:
  - `action` (string, required): Action to perform ("add" or "remove")
  - `triple_type` (string, required): Type of triple ("preference" or "reference")
  - `path` (string, required): Source document path
  - `predicate` (string, required): Predicate of the triple
  - `object` (string, optional): Object of the triple (for preferences) or relation name (for references)
  - `ref_path` (string, optional): Referenced document path (for references only)
- **Returns**:
  - Operation status and updated counts

**Adding a preference (arbitrary RDF triple):**
```json
{
  "status": "updated",
  "preference_count": 3,
  "action": "add",
  "triple_type": "preference"
}
```

**Adding a reference (link to another document):**
```json
{
  "status": "success",
  "message": "Reference added",
  "added": true,
  "action": "add",
  "triple_type": "reference"
}
```

**Removing a reference:**
```json
{
  "status": "updated",
  "reference_count": 2,
  "action": "remove",
  "triple_type": "reference"
}
```

#### `kb_search`
Searches the knowledge base using text queries and/or graph expansion.

- **Parameters**:
  - `query` (string, optional): Text query for semantic search and reranking
  - `seed_uris` (array, optional): Starting URIs for graph expansion
  - `expand_hops` (integer, optional): Number of relationship hops to expand (default: 0)
  - `filter_urns` (array, optional): URNs to exclude from results
  - `relation_predicates` (array, optional): Predicates to follow during graph traversal (default: ["references"])
  - `top_k` (integer, optional): Number of results to return (default: 10)
  - `include_content` (boolean, optional): Whether to include document content (default: false)
  - `include_index` (boolean, optional): Whether to include document metadata (default: false)
  - `use_reranker` (boolean, optional): Whether to use semantic reranking (default: true)
- **Returns**:
  - Ranked list of search results

```json
{
  "results": [
    {
      "urn": "kb://projects/docs/api-reference",
      "sparse_score": 1.95,
      "content": "API reference content...",
      "index": {
        "namespace": "projects",
        "collection": "docs",
        "name": "api-reference",
        "type": "document",
        "subtype": "text",
        "created_at": "2025-07-02T23:13:17.362283Z",
        "updated_at": "2025-07-02T23:18:23.396660Z",
        "content_type": "text/plain",
        "chunked": false,
        "fragments": {},
        "preferences": [],
        "references": [
          [
            "references",
            "kb://project/docs/api-dto"
          ]
        ],
        "referenced_by": [],
        "indices": [],
        "metadata": {
          "purpose": "testing_collection_organization",
          "created_for": "kb_exercise",
          "type": "test_document",
          "created_date": "2025-07-02",
          "topic": "search_performance",
          "related_to": "rebuild_test"
        }
      },
      "rerank_score": 0.84,
    }
  ],
  "count": 1
}
```

#### `kb_list_documents`
Lists documents in the knowledge base.

- **Parameters**:
  - `path` (string, optional): Path prefix to filter by
  - `recursive` (boolean, optional): Whether to list recursively (default: true)
- **Returns**:
  - List of document paths

```json
{
  "documents": [
    "projects/docs/api-reference",
    "projects/docs/user-guide",
    "research/papers/transformers"
  ],
  "count": 3
}
```

#### `kb_manage`
Manages knowledge base operations like moving documents and rebuilding search indices.

- **Parameters**:
  - `action` (string, required): Management action to perform
    - `"move_document"`: Move a document (requires `path` and `new_path`)
    - `"delete"`: Archive a document (requires `path`)
    - `"rebuild_search_index"`: Rebuild search indices (optional `rebuild_all`)
  - Additional parameters depend on the action
- **Returns**:
  - Operation status and results

**Moving a document:**
```json
{
  "action": "move_document",
  "status": "success",
  "old_path": "projects/docs/old-name",
  "new_path": "projects/docs/new-name",
  "result": {
    "namespace": "projects",
    "collection": "docs",
    "name": "new-name",
    "type": "document",
    "subtype": "text",
    "created_at": "2024-01-15T10:30:00.000Z",
    "updated_at": "2024-01-15T10:50:00.000Z",
    "content_type": "text/plain",
    "chunked": false,
    "fragments": {},
    "preferences": [],
    "references": [],
    "referenced_by": [],
    "indices": [],
    "metadata": {}
  }
}
```

**Archiving a document:**
```json
{
  "action": "delete",
  "status": "success", 
  "path": "projects/docs/obsolete",
  "result": {
    "status": "archived",
    "message": "Document archived: kb://projects/docs/obsolete",
    "original_path": "projects/docs/obsolete",
    "archive_path": "archive/projects/docs/obsolete",
    "archive_urn": "kb://archive/projects/docs/obsolete"
  }
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

### Knowledge Base Environment

The knowledge base environment provides structured document storage and semantic search:

- **Hierarchical Organization**: Documents organized in namespace/collection/name structure
- **Metadata Management**: Rich metadata support with RDF-style triples
- **Semantic Search**: Full-text search with sparse indexing and semantic reranking
- **Graph Relationships**: Document references with relationship traversal
- **Path Validation**: Strict path validation and normalization
- **Search Indices**: Separate sparse and graph indices for optimal performance
- **Timeout Control**: Configurable timeouts for operations (default: 30s, max: 120s)
- **Isolation**: Knowledge base operations restricted to configured storage path

## Architecture

The project follows a modular architecture:

```bash
container-mcp/
├── cmcp/                     # Main application code
│   ├── managers/             # Domain-specific managers
│   │   ├── bash_manager.py   # Secure bash execution
│   │   ├── file_manager.py   # Secure file operations
│   │   ├── knowledge_base_manager.py # Knowledge base operations
│   │   ├── python_manager.py # Secure python execution
│   │   └── web_manager.py    # Secure web operations
│   ├── kb/                   # Knowledge base components
│   │   ├── document_store.py # Document storage and retrieval
│   │   ├── models.py         # Data models and schemas
│   │   ├── path.py           # Path parsing and validation
│   │   └── search.py         # Search indices and ranking
│   ├── tools/                # MCP tool implementations
│   │   ├── file.py           # File operation tools
│   │   ├── kb.py             # Knowledge base tools
│   │   ├── system.py         # System operation tools
│   │   └── web.py            # Web operation tools
│   ├── utils/                # Utility functions
│   │   └── logging.py        # Logging utilities
│   ├── __init__.py
│   ├── config.py             # Configuration system
│   └── main.py               # MCP server setup
├── apparmor/                 # AppArmor profiles
│   ├── mcp-bash              # Bash execution profile
│   └── mcp-python            # Python execution profile
├── bin/                      # Build/run scripts
│   ├── 00-all-in-one.sh      # Complete setup script
│   ├── 01-init.sh            # Project initialization
│   ├── 02-build-container.sh # Container build script
│   ├── 03-setup-environment.sh # Environment setup
│   ├── 04-run-container.sh   # Container run script
│   ├── 05-check-container.sh # Container health check
│   ├── 06-run-tests.sh       # Test execution
│   ├── 07-attach-container.sh # Container shell access
│   ├── 08-testnetwork.sh     # Network testing
│   ├── 09-view-logs.sh       # Log viewing
│   ├── zy-shutdown.sh        # Container shutdown
│   └── zz-teardown.sh        # Complete teardown
├── tests/                    # Test suites
│   ├── integration/          # Integration tests
│   ├── unit/                 # Unit tests
│   └── conftest.py           # Test configuration
├── volume/                   # Persistent storage
│   ├── config/               # Configuration files
│   ├── data/                 # Data directory
│   ├── kb/                   # Knowledge base storage
│   │   ├── search/           # Search indices
│   │   │   ├── sparse_idx/   # Sparse search index
│   │   │   └── graph_idx/    # Graph search index
│   │   ├── archive/          # Archived documents
│   ├── logs/                 # Log files
│   ├── sandbox/              # Sandboxed execution space
│   │   ├── bash/             # Bash sandbox
│   │   ├── browser/          # Web browser sandbox
│   │   ├── files/            # File operation sandbox
│   │   └── python/           # Python sandbox
│   └── temp/                 # Temporary storage
├── Containerfile            # Container definition
├── podman-compose.yml       # Container orchestration
├── pyproject.toml           # Python project configuration
├── uv.lock                  # Dependency lock file
├── pytest.ini               # Test configuration
└── README.md                # Project documentation
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
git clone https://github.com/54rt1n/container-mcp.git
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

**Important:** When configuring your MCP client, you must set the endpoint URL to `http://127.0.0.1:<port>/sse` (where `<port>` is 8000 by default or the port you've configured). The `/sse` path is required for proper server-sent events communication.

### Example Python Client

```python
from mcp.client.sse import sse_client
from mcp import ClientSession
import asyncio

async def main():
    # Connect to the Container-MCP server
    # Note the /sse endpoint suffix required for SSE communication
    sse_url = "http://127.0.0.1:8000/sse"  # Or your configured port
    
    # Connect to the SSE endpoint
    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Discover available tools
            result = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in result.tools]}")
            
            # Execute a Python script
            python_result = await session.execute_tool(
                "system_run_python",
                {"code": "print('Hello, world!')\nresult = 42\n_ = result"}
            )
            print(f"Python result: {python_result}")
            
            # Execute a bash command
            bash_result = await session.execute_tool(
                "system_run_command",
                {"command": "ls -la"}
            )
            print(f"Command output: {bash_result['stdout']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

Container-MCP can be configured through environment variables, which can be set in `volume/config/custom.env`:

### Server Configuration

```
# MCP Server Configuration
MCP_HOST=127.0.0.1
MCP_PORT=9001
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

### Knowledge Base Manager Configuration

```
# Knowledge Base Manager Configuration
CMCP_KB_STORAGE_PATH=/app/kb
KB_TIMEOUT_DEFAULT=30
KB_TIMEOUT_MAX=120

# Search Configuration
CMCP_KB_SEARCH_ENABLED=true
CMCP_KB_SPARSE_INDEX_PATH=/app/kb/search/sparse_idx
CMCP_KB_GRAPH_INDEX_PATH=/app/kb/search/graph_idx
CMCP_KB_RERANKER_MODEL=mixedbread-ai/mxbai-rerank-base-v1
CMCP_KB_SEARCH_RELATION_PREDICATES=references
CMCP_KB_SEARCH_GRAPH_NEIGHBOR_LIMIT=1000

# Tool Enable/Disable
TOOLS_ENABLE_KB=true
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
