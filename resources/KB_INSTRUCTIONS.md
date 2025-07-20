# Knowledge Base Tools - Usage Guide for LLMs

## Overview
This knowledge base system provides semantic search, document management, and relationship modeling. Use these tools to store, retrieve, and explore structured knowledge with automatic indexing and graph-based relationships.

## Core Tool Examples

### 1. Creating and Writing Documents

**Example 1: Creating a technical guide**
```
kb_create_document
{
    "path": "guides/authentication/oauth2-flow",
    "metadata": {
        "type": "technical_guide",
        "difficulty": "intermediate", 
        "author": "system",
        "version": "1.0"
    }
}

kb_write_content
{
    "path": "guides/authentication/oauth2-flow",
    "content": "# OAuth2 Authentication Flow\n\nOAuth2 is a protocol that allows applications to...",
    "force": false
}
```

**Example 2: Creating API documentation**
```
kb_create_document
{
    "path": "api/endpoints/user-management",
    "metadata": {
        "type": "api_docs",
        "endpoint": "/api/v1/users",
        "methods": ["GET", "POST", "PUT", "DELETE"]
    }
}

kb_write_content
{
    "path": "api/endpoints/user-management", 
    "content": "## User Management API\n\n### GET /api/v1/users\nRetrieve user list...",
    "force": false
}
```

### 2. Reading Documents and Collections

**Example 1: Reading a specific document**
```
kb_read
{
    "path": "guides/authentication/oauth2-flow",
    "include_content": true,
    "include_index": true
}
```
Returns: `{status: "success", content: "...", index: {...}, mode: "read"}`

**Example 2: Listing documents in a collection**
```
kb_read
{
    "path": "guides/authentication",
    "recursive": true,
    "include_content": false,
    "include_index": false
}
```
Returns: `{documents: ["guides/authentication/oauth2-flow", ...], count: 5, mode: "list"}`

**Example 3: Bulk reading with content**
```
kb_read
{
    "path": "api",
    "recursive": true,
    "include_content": true,
    "include_index": true
}
```
Returns: `{documents: [{path: "...", content: "...", index: {...}}], mode: "bulk_read"}`

### 3. Semantic Search

**Example 1: Basic semantic search**
```
kb_search
{
    "query": "error handling and exception management patterns",
    "top_k_rerank": 10,
    "include_content": true,
    "include_index": false,
    "use_reranker": true
}
```
Returns: `{results: [{urn: "...", content: "...", rerank_score: 0.95}], count: 10}`

**Example 2: Graph-based exploration**
```
kb_search
{
    "query": "security implementation",
    "seed_uris": ["kb://guides/authentication/oauth2-flow"],
    "expand_hops": 2,
    "relation_predicates": ["references", "implements"],
    "top_k_rerank": 15,
    "include_content": true
}
```

**Example 3: Filtering search results**
```
kb_search
{
    "query": "database connection patterns",
    "filter_urns": ["kb://archive/old-db-guide"],
    "top_k_sparse": 30,
    "top_k_rerank": 8,
    "include_content": true
}
```

### 4. Building Relationships with Triples

**Example 1: Adding document references**
```
kb_update_triples
{
    "action": "add",
    "triple_type": "reference", 
    "path": "guides/authentication/oauth2-flow",
    "predicate": "uses",
    "ref_path": "guides/security/jwt-tokens"
}
```
Returns: `{action: "add", triple_type: "reference", status: "success", added: true}`

```
kb_update_triples
{
    "action": "add",
    "triple_type": "reference",
    "path": "api/endpoints/auth",
    "predicate": "implements", 
    "ref_path": "guides/authentication/oauth2-flow"
}
```

**Example 2: Setting user preferences** 
```
kb_update_triples
{
    "action": "add",
    "triple_type": "preference",
    "path": "guides/authentication/oauth2-flow",
    "predicate": "difficulty",
    "object": "advanced"
}

kb_update_triples
{
    "action": "add", 
    "triple_type": "preference",
    "path": "guides/authentication/oauth2-flow",
    "predicate": "topics",
    "object": "security,authentication,web"
}
```

**Example 3: Adding metadata**
```
kb_update_triples
{
    "action": "add",
    "triple_type": "metadata", 
    "path": "api/endpoints/user-management",
    "predicate": "api_version",
    "object": "v2.1"
}

kb_update_triples
{
    "action": "add",
    "triple_type": "metadata",
    "path": "api/endpoints/user-management", 
    "predicate": "last_updated",
    "object": "2025-01-07"
}
```

### 5. System Management

**Example 1: Rebuilding search indices**
```
kb_manage
{
    "action": "rebuild_search_index",
    "options": {"rebuild_all": true}
}
```
Returns: `{action: "rebuild_search_index", status: "success", result: {...}}`

**Example 2: Moving documents**
```
kb_manage
{
    "action": "move_document", 
    "options": {
        "path": "guides/auth-old",
        "new_path": "guides/authentication/legacy-methods"
    }
}
```
Returns: `{action: "move_document", status: "success", old_path: "...", new_path: "..."}`

**Example 3: Archiving documents**
```
kb_manage
{
    "action": "delete",
    "options": {"path": "guides/deprecated/old-api"}
}
```
Returns: `{action: "delete", status: "archived", archive_path: "archive/..."}`

## Common Workflow Patterns

### Pattern 1: Research and Documentation
```
# 1. Search for existing information
kb_search
{
    "query": "user authentication best practices",
    "include_content": true,
    "top_k_rerank": 5
}

# 2. Read related documents
kb_read
{
    "path": "guides/authentication/oauth2-flow",
    "include_content": true,
    "include_index": true
}

# 3. Create new comprehensive guide
kb_create_document
{
    "path": "guides/security/auth-best-practices",
    "metadata": {"type": "guide", "comprehensiveness": "high"}
}

# 4. Write content incorporating research
kb_write_content
{
    "path": "guides/security/auth-best-practices", 
    "content": "# Authentication Best Practices\n\nBased on analysis of..."
}

# 5. Link to source materials
kb_update_triples
{
    "action": "add",
    "triple_type": "reference",
    "path": "guides/security/auth-best-practices",
    "predicate": "synthesizes",
    "ref_path": "guides/authentication/oauth2-flow"
}
```

### Pattern 2: API Documentation Discovery
```
# Find all API endpoints related to user management
kb_search
{
    "query": "user management API endpoints",
    "seed_uris": ["kb://api/endpoints/user-management"],
    "expand_hops": 1,
    "relation_predicates": ["references", "implements"],
    "include_content": true,
    "include_index": true
}

# Explore implementation details
kb_read
{
    "path": "api/implementation/user-service",
    "include_content": true,
    "include_index": true
}
```

### Pattern 3: Knowledge Graph Exploration
```
# Start with a central concept
kb_search
{
    "query": "database architecture",
    "top_k_rerank": 3,
    "include_index": true
}

# Expand through relationships
kb_search
{
    "seed_uris": ["kb://architecture/database/core"],
    "expand_hops": 2,
    "relation_predicates": ["implements", "uses", "extends"],
    "include_content": true,
    "top_k_rerank": 10
}
```

## Best Practices

1. **Always check tool responses** for error status before proceeding
2. **Use semantic queries** instead of exact keyword matching for better results
3. **Include content when you need to analyze** document text
4. **Build rich relationship networks** using descriptive predicates
5. **Use hierarchical paths** like "domain/category/specific-topic"
6. **Combine text search with graph traversal** for comprehensive discovery
7. **Regular index maintenance** improves search performance
8. **Archive instead of deleting** to preserve knowledge history

## Error Handling Examples

```
# Check for document existence before writing content
kb_read
{
    "path": "guides/new-topic",
    "include_content": false,
    "include_index": false
}

# If document doesn't exist, create it first
kb_create_document
{
    "path": "guides/new-topic", 
    "metadata": {"type": "guide"}
}

# Then write content
kb_write_content
{
    "path": "guides/new-topic",
    "content": "# New Topic Guide\n...",
    "force": false
}

# If content already exists, use force to overwrite
kb_write_content
{
    "path": "guides/new-topic",
    "content": "# New Topic Guide\n...", 
    "force": true
}
```
