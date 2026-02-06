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
  - `ListManager`: Organized list and collection management
  - `MarketManager`: Stock and cryptocurrency data via Yahoo Finance
  - `RssManager`: RSS and Atom feed fetching

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

#### `health_check`
Gets server health status and system information.

- **Parameters**: None
- **Returns**:
  - `status` (string): Server health status
  - `timestamp` (string): Current ISO timestamp
  - `server` (object): Server details (name, host, port, platform, python_version)
  - `system` (object): System metrics (cpu_percent, memory_percent, disk_percent)
  - `managers` (object): Status of each manager (enabled/disabled)

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "server": {
    "name": "Container-MCP",
    "host": "127.0.0.1",
    "port": 9001,
    "platform": "linux",
    "python_version": "3.12.0"
  },
  "system": {
    "cpu_percent": 12.5,
    "memory_percent": 45.2,
    "disk_percent": 67.8
  },
  "managers": {
    "bash": "enabled",
    "python": "enabled",
    "file": "enabled",
    "web": "enabled",
    "kb": "enabled",
    "list": "enabled",
    "market": "enabled",
    "rss": "enabled"
  }
}
```

### File Operations

#### `fs_read`
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

#### `fs_write`
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

#### `fs_list`
Lists contents of a directory safely.

- **Parameters**:
  - `path` (string, optional): Path to the directory (default: "/")
  - `pattern` (string, optional): Glob pattern to filter files
  - `recursive` (boolean, optional): Whether to list recursively (default: true)
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

#### `fs_delete`
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

#### `fs_move`
Moves or renames a file safely.

- **Parameters**:
  - `source_path` (string, required): Source file path
  - `destination_path` (string, required): Destination file path
- **Returns**:
  - `success` (boolean): Whether the move was successful
  - `source_path` (string): Original file path
  - `destination_path` (string): New file path

```json
{
  "success": true,
  "source_path": "data/old_name.txt",
  "destination_path": "data/new_name.txt"
}
```

#### `fs_apply_diff`
Applies a unified diff patch to a file in the sandbox filesystem.

- **Parameters**:
  - `path` (string, required): Path to the file to patch (relative to sandbox root)
  - `diff` (string, required): Unified diff content to apply
- **Returns**:
  - `success` (boolean): Whether the patch was applied successfully
  - `path` (string): Path to the patched file
  - `lines_applied` (integer): Number of lines changed
  - `new_size` (integer): New file size in bytes
  - `error` (string): Error message if patch failed

```json
{
  "success": true,
  "path": "src/main.py",
  "lines_applied": 5,
  "new_size": 1248,
  "error": null
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

#### Document URI Format

Knowledge base documents use a structured URI format: `kb://namespace/collection[/subcollection]*/name`

- **namespace**: Top-level organizational unit (e.g., "projects", "research")
- **collection**: Main category within namespace (e.g., "documentation", "notes")
- **subcollection**: Optional nested categories (e.g., "api", "tutorials")
- **name**: Document identifier (e.g., "getting-started", "user-guide")

Examples:
- `kb://projects/docs/api-reference`
- `kb://research/papers/machine-learning/transformers`
- `kb://personal/notes/meeting-2024-01-15`

#### `kb_create_document`
Creates a new document in the knowledge base with optional metadata and content.

- **Parameters**:
  - `uri` (string, required): Document URI in format "kb://namespace/collection[/subcollection]*/name"
  - `metadata` (object, optional): Document metadata (default: {})
  - `content` (string, optional): Document content (allows single-step create and write)
- **Returns**:
  - Complete document index object with creation details
- **Notes**: You can create a document with content in a single step by providing the `content` parameter, or use a two-step process by creating first and then adding content with `kb_write_content`.

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
  - `uri` (string, required): Document URI
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
Reads document data from the knowledge base. When called without a `uri`, lists all documents (replacing the need for a separate list operation).

- **Parameters**:
  - `uri` (string, optional): Document URI. If omitted, lists all documents.
  - `recursive` (boolean, optional): Whether to list recursively (default: true)
  - `include_content` (boolean, optional): Whether to include document content (default: false)
  - `include_index` (boolean, optional): Whether to include document metadata (default: false)
- **Returns**:
  - Document data based on requested components. Operates in three modes:
    - **list mode**: When `uri` is omitted, returns a list of document URIs
    - **bulk_read mode**: When `uri` is a partial path (namespace or collection), returns multiple documents
    - **read mode**: When `uri` is a full document path, returns a single document

**Reading a single document:**
```json
{
  "status": "success",
  "uri": "kb://projects/docs/api-reference",
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

**Listing all documents (no uri):**
```json
{
  "mode": "list",
  "documents": [
    "kb://projects/docs/api-reference",
    "kb://projects/docs/user-guide",
    "kb://research/papers/transformers"
  ],
  "count": 3
}
```

#### `kb_update_triples`
Manages RDF triples (preferences, references, and metadata) for documents. This tool also handles metadata updates via `triple_type="metadata"`, replacing the need for a separate metadata update operation.

- **Parameters**:
  - `action` (string, required): Action to perform ("add" or "remove")
  - `triple_type` (string, required): Type of triple ("preference", "reference", or "metadata")
  - `uri` (string, required): Source document URI
  - `predicate` (string, required): Predicate of the triple
  - `object` (string, optional): Object of the triple (for preferences and metadata)
  - `ref_uri` (string, optional): Referenced document URI (for references only)
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

**Updating metadata:**
```json
{
  "status": "updated",
  "action": "add",
  "triple_type": "metadata"
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
  - `seed_uris` (array, optional): Starting full URIs (kb://namespace/collection/name) for graph expansion
  - `root_uri` (string, optional): Partial URI (kb://namespace or kb://namespace/collection) to scope search
  - `expand_hops` (integer, optional): Number of relationship hops to expand (default: 0)
  - `filter_uris` (array, optional): URIs to exclude from results
  - `relation_predicates` (array, optional): Predicates to follow during graph traversal (default: ["references"])
  - `top_k_sparse` (integer, optional): Number of sparse search results to retrieve (default: 50)
  - `top_k_rerank` (integer, optional): Number of final results after reranking (default: 10)
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

#### `kb_manage`
Manages knowledge base operations like moving documents and rebuilding search indices.

- **Parameters**:
  - `action` (string, required): Management action to perform
    - `"move_document"`: Move a document
    - `"delete"`: Archive a document
    - `"rebuild_search_index"`: Rebuild search indices
  - `options` (object, required): Action-specific options
    - For `"move_document"`: `{"uri": "...", "new_uri": "..."}`
    - For `"delete"`: `{"uri": "..."}`
    - For `"rebuild_search_index"`: `{"rebuild_all": true}` (optional)
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

### List Operations

The list system provides org-mode based list management for tasks, notes, shopping, and general collections. Lists support various item statuses and can be tagged for organization.

#### Item Statuses

Items in lists can have the following statuses: `TODO`, `DONE`, `WAITING`, `CANCELLED`, `NEXT`, `SOMEDAY`

#### List Types

Lists can be one of: `todo`, `shopping`, `notes`, `checklist`, `project`, `reading`, `ideas`

#### `list_create`
Creates a new organized list for tasks, notes, shopping, or any collection.

- **Parameters**:
  - `name` (string, required): Internal name for the list (used for filename)
  - `title` (string, optional): Display title for the list
  - `list_type` (string, optional): Type of list (default: "todo")
  - `description` (string, optional): Optional description
  - `tags` (array, optional): Tags for organization
  - `properties` (object, optional): Custom user-defined properties
- **Returns**:
  - `success` (boolean): Whether creation succeeded
  - `name` (string): List name
  - `metadata` (object): Title, type, created timestamp, properties
  - `path` (string): File path

```json
{
  "success": true,
  "name": "grocery-list",
  "metadata": {
    "title": "Weekly Groceries",
    "type": "shopping",
    "created": "2024-01-15T10:30:00.000Z",
    "properties": {}
  },
  "path": "/app/lists/grocery-list.org"
}
```

#### `list_get`
Retrieves and browses lists with flexible filtering options.

- **Parameters**:
  - `name` (string, optional): Name of specific list to retrieve. If omitted, lists all available lists.
  - `include_items` (boolean, optional): Whether to include items in response (default: true)
  - `summary_only` (boolean, optional): Return only summary statistics without items (default: false)
  - `status_filter` (string, optional): Filter items by status (TODO, DONE, WAITING, CANCELLED, NEXT, SOMEDAY)
  - `tag_filter` (array, optional): Filter items by tags (items must have ALL specified tags)
- **Returns**:
  - When `name` is omitted: `lists` (array of summaries), `count`
  - When `name` is provided: `name`, `metadata`, `items`, `statistics`

**Listing all lists:**
```json
{
  "success": true,
  "lists": [
    {"name": "grocery-list", "title": "Weekly Groceries", "type": "shopping"},
    {"name": "project-tasks", "title": "Q1 Tasks", "type": "todo"}
  ],
  "count": 2
}
```

**Getting a specific list:**
```json
{
  "success": true,
  "name": "project-tasks",
  "metadata": {"title": "Q1 Tasks", "type": "todo"},
  "items": [
    {
      "text": "Complete API integration",
      "status": "TODO",
      "index": 0,
      "tags": ["backend"],
      "created": "2024-01-15T10:30:00.000Z",
      "completed": null,
      "properties": {}
    }
  ],
  "statistics": {
    "total_items": 5,
    "status_counts": {"TODO": 3, "DONE": 2},
    "completion_percentage": 40.0
  }
}
```

#### `list_modify`
Modifies list items by adding, updating, or removing them.

- **Parameters**:
  - `list_name` (string, required): Name of the list
  - `action` (string, required): Operation to perform ("add", "update", or "remove")
  - `item_text` (string, optional): Text of item (required for "add", optional for "update")
  - `item_index` (integer, optional): Index of item (required for "update" and "remove")
  - `status` (string, optional): Item status (TODO, DONE, WAITING, CANCELLED, NEXT, SOMEDAY)
  - `tags` (array, optional): Tags for the item
  - `properties` (object, optional): Custom properties
- **Returns**:
  - `success` (boolean): Whether the operation succeeded
  - `action` (string): The action performed
  - `item` (object): The affected item details

**Adding an item:**
```json
{
  "success": true,
  "action": "add",
  "item": {
    "text": "Buy milk",
    "status": "TODO",
    "index": 3,
    "tags": ["dairy"]
  },
  "total_items": 4
}
```

**Updating an item:**
```json
{
  "success": true,
  "action": "update",
  "item_index": 0,
  "item": {"text": "Buy milk", "status": "DONE"},
  "old_item": {"text": "Buy milk", "status": "TODO"}
}
```

**Removing an item:**
```json
{
  "success": true,
  "action": "remove",
  "removed_item": {"text": "Buy milk", "status": "DONE", "index": 0},
  "remaining_items": 3
}
```

#### `list_update`
Updates list properties and metadata. Properties use merge semantics — only provided keys are updated, existing keys are preserved.

- **Parameters**:
  - `name` (string, required): Name of the list
  - `title` (string, optional): New title
  - `list_type` (string, optional): New list type
  - `description` (string, optional): New description
  - `tags` (array, optional): New tags (replaces existing)
  - `author` (string, optional): New author
  - `properties` (object, optional): Custom properties (merged with existing)
- **Returns**:
  - `success` (boolean): Whether the update succeeded
  - `name` (string): List name
  - `metadata` (object): Updated metadata

```json
{
  "success": true,
  "name": "project-tasks",
  "metadata": {
    "title": "Q1 Tasks - Updated",
    "type": "project",
    "tags": ["work", "q1"],
    "description": "Updated project task list"
  }
}
```

#### `list_delete`
Permanently deletes an entire list and all its items. The list file will be archived for safety but the list will no longer be accessible through normal operations.

- **Parameters**:
  - `name` (string, required): Name of the list to delete
- **Returns**:
  - `success` (boolean): Whether the deletion succeeded
  - `name` (string): Deleted list name
  - `items_count` (integer): Number of items that were in the list
  - `archived_to` (string): Archive file path

```json
{
  "success": true,
  "name": "old-grocery-list",
  "items_count": 12,
  "archived_to": "/app/lists/.archive/old-grocery-list.org"
}
```

#### `list_search`
Searches for items across multiple lists by text or tags.

- **Parameters**:
  - `query` (string, required): Search query string
  - `list_names` (array, optional): Specific lists to search in (searches all if omitted)
  - `search_in` (array, optional): Where to search: "text", "tags", or both (default: ["text"])
  - `case_sensitive` (boolean, optional): Whether search is case-sensitive (default: false)
- **Returns**:
  - `matches` (array): List of matching items with list context
  - `total_matches` (integer): Total number of matches
  - `lists_searched` (integer): Number of lists searched
  - `search_options` (object): Applied search parameters

```json
{
  "success": true,
  "query": "milk",
  "matches": [
    {
      "list_name": "grocery-list",
      "list_title": "Weekly Groceries",
      "item_index": 2,
      "item_text": "Buy milk",
      "item_status": "TODO",
      "item_tags": ["dairy"],
      "match_type": "text"
    }
  ],
  "total_matches": 1,
  "lists_searched": 3,
  "search_options": {
    "search_in": ["text"],
    "case_sensitive": false
  }
}
```

### Market Operations

The market system provides financial data queries using Yahoo Finance for stocks and cryptocurrencies.

#### `market_query`
Queries stock or cryptocurrency prices with fundamentals, news, and trend analysis.

- **Parameters**:
  - `symbol` (string, required): Stock/crypto symbol (e.g., "AAPL", "BTC-USD", "TSLA")
  - `period` (string, optional): Historical period for trend metrics (default: "1y")
  - `interval` (string, optional): Historical data interval (default: "1d")
  - `news_count` (integer, optional): Number of recent news items to return (default: 5)
- **Returns**:
  - `symbol` (string): Queried symbol
  - `name` (string): Company/asset name
  - `price` (float): Current price
  - `change` (float): Price change
  - `change_percent` (float): Percentage change
  - `volume` (integer): Trading volume
  - `market_cap` (integer): Market capitalization
  - `currency` (string): Currency code
  - `timestamp` (string): ISO format timestamp
  - `fundamentals` (object): Earnings, PE ratios, dividends, margins
  - `news` (array): Recent news items
  - `trend` (object): Moving averages, RSI, volatility, historical returns
  - `success` (boolean): Whether the query succeeded
  - `error` (string): Error message if query failed

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "price": 185.92,
  "change": 2.35,
  "change_percent": 1.28,
  "volume": 54321000,
  "market_cap": 2890000000000,
  "currency": "USD",
  "timestamp": "2024-01-15T16:00:00Z",
  "fundamentals": {
    "trailing_pe": 29.5,
    "forward_pe": 27.8,
    "dividend_yield": 0.0054,
    "profit_margin": 0.256,
    "earnings_quarterly_growth": 0.13
  },
  "news": [
    {
      "title": "Apple Reports Strong Q4 Earnings",
      "link": "https://example.com/article",
      "publisher": "Reuters",
      "published": "2024-01-15T12:00:00Z",
      "type": "STORY"
    }
  ],
  "trend": {
    "as_of": "2024-01-15T16:00:00Z",
    "close": 185.92,
    "return_1w": 0.023,
    "return_1m": 0.045,
    "return_3m": 0.12,
    "ma20": 183.50,
    "ma50": 180.25,
    "ma200": 175.80,
    "rsi14": 58.3,
    "volatility_20d": 0.18,
    "range_52w_low": 164.08,
    "range_52w_high": 199.62,
    "data_points": 252
  },
  "success": true,
  "error": null
}
```

### RSS Operations

The RSS system fetches and parses RSS and Atom feeds.

#### `rss_fetch`
Fetches and parses an RSS or Atom feed, returning structured items.

- **Parameters**:
  - `url` (string, required): RSS feed URL
  - `limit` (integer, optional): Maximum number of items to return (default: 10)
- **Returns**:
  - `feed_title` (string): Title of the feed
  - `feed_link` (string): Link to the feed's website
  - `items` (array): Feed items, each with:
    - `title` (string): Item title
    - `link` (string): Item URL
    - `published` (string): Publication date
    - `summary` (string): Item summary/description
  - `item_count` (integer): Number of items returned
  - `success` (boolean): Whether the fetch succeeded
  - `error` (string): Error message if fetch failed

```json
{
  "feed_title": "Hacker News",
  "feed_link": "https://news.ycombinator.com",
  "items": [
    {
      "title": "Show HN: A new open-source project",
      "link": "https://example.com/project",
      "published": "2024-01-15T14:30:00Z",
      "summary": "An innovative approach to solving..."
    }
  ],
  "item_count": 10,
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

### List Environment

The list environment provides organized collection management:

- **Org-mode Format**: Lists stored as org-mode files for portability
- **Status Tracking**: Items support multiple statuses (TODO, DONE, WAITING, CANCELLED, NEXT, SOMEDAY)
- **Tagging**: Items and lists support tags for flexible organization
- **Archival**: Deleted lists are archived for safety
- **Search**: Cross-list search by text and tags
- **Isolation**: List operations restricted to configured storage path

### Market Environment

The market environment provides controlled access to financial data:

- **Data Source**: Yahoo Finance for stocks and cryptocurrencies
- **Timeout Control**: Configurable timeouts (default: 30s, max: 60s)
- **Data Types**: Price quotes, fundamentals, news, and trend analysis

### RSS Environment

The RSS environment provides feed fetching capabilities:

- **Feed Types**: Supports both RSS and Atom feeds
- **Timeout Control**: Configurable timeouts (default: 15s, max: 30s)
- **User Agent**: Configurable user agent string
- **Item Limiting**: Configurable maximum items per fetch

## Architecture

The project follows a modular architecture:

```bash
container-mcp/
├── cmcp/                     # Main application code
│   ├── managers/             # Domain-specific managers
│   │   ├── bash_manager.py   # Secure bash execution
│   │   ├── file_manager.py   # Secure file operations
│   │   ├── knowledge_base_manager.py # Knowledge base operations
│   │   ├── list_manager.py   # List/collection operations
│   │   ├── market_manager.py # Market data operations
│   │   ├── python_manager.py # Secure python execution
│   │   ├── rss_manager.py    # RSS feed operations
│   │   └── web_manager.py    # Secure web operations
│   ├── kb/                   # Knowledge base components
│   │   ├── document_store.py # Document storage and retrieval
│   │   ├── models.py         # Data models and schemas
│   │   ├── path.py           # Path parsing and validation
│   │   └── search.py         # Search indices and ranking
│   ├── tools/                # MCP tool implementations
│   │   ├── file.py           # File operation tools
│   │   ├── kb.py             # Knowledge base tools
│   │   ├── list.py           # List operation tools
│   │   ├── market.py         # Market data tools
│   │   ├── rss.py            # RSS feed tools
│   │   ├── system.py         # System operation tools
│   │   └── web.py            # Web operation tools
│   ├── utils/                # Utility functions
│   │   ├── diff.py           # Diff/patch utilities
│   │   ├── io.py             # I/O helpers
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

### List Manager Configuration

```
# List Manager Configuration
CMCP_LIST_STORAGE_PATH=/app/lists
TOOLS_ENABLE_LIST=true
```

### Market Manager Configuration

```
# Market Manager Configuration
MARKET_TIMEOUT_DEFAULT=30
MARKET_TIMEOUT_MAX=60
TOOLS_ENABLE_MARKET=true
```

### RSS Manager Configuration

```
# RSS Manager Configuration
RSS_TIMEOUT_DEFAULT=15
RSS_TIMEOUT_MAX=30
RSS_USER_AGENT=container-mcp/1.0
TOOLS_ENABLE_RSS=true
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
