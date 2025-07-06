# cmcp/tools/list.py
"""List tools module.

This module contains tools for managing org-mode based lists and todo items.
"""

from typing import Dict, Any, Optional, List, Literal
import logging
from mcp.server.fastmcp import FastMCP
from cmcp.managers.list_manager import ListManager

logger = logging.getLogger(__name__)

def create_list_tools(mcp: FastMCP, list_manager: ListManager) -> None:
    """Create and register list tools.
    
    Args:
        mcp: The MCP instance
        list_manager: The list manager instance
    """
    
    @mcp.tool()
    async def list_create(
        name: str, 
        title: Optional[str] = None, 
        list_type: str = "todo", 
        description: str = "", 
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new list for organizing tasks, notes, shopping items, or any other collection.
        
        Lists are org-mode based and support various item statuses (TODO, DONE, WAITING, etc.) 
        and can be tagged for easy categorization.
        
        Args:
            name: Unique identifier for the list (used as filename, alphanumeric/dash/underscore only)
            title: Human-readable display title (defaults to name if not provided)
            list_type: Category of list - "todo", "shopping", "notes", "checklist", or custom type
            description: Brief description of the list's purpose or contents
            tags: Tags for categorizing and filtering lists (e.g., ["work", "urgent", "project-x"])
            
        Returns:
            Dictionary containing:
            - success: Whether the list was created successfully
            - name: The list identifier
            - metadata: Complete list metadata including creation timestamp
            - error: Error message if creation failed
            
        Examples:
            Create a work todo list:
            >>> list_create("work-tasks", "Work Tasks Q1 2025", "todo", "Quarterly objectives", ["work", "q1-2025"])
            
            Create a shopping list:
            >>> list_create("groceries", "Grocery Shopping", "shopping", tags=["weekly", "essentials"])
        """
        return await list_manager.create_list(
            name=name,
            title=title,
            list_type=list_type,
            description=description,
            tags=tags
        )
    
    @mcp.tool()
    async def list_get(
        name: Optional[str] = None,
        include_items: bool = True,
        summary_only: bool = False,
        status_filter: Optional[str] = None,
        tag_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Retrieve list(s) with flexible filtering and display options.
        
        This tool can:
        - Get all lists (when name is None)
        - Get a specific list with all its items
        - Get just list metadata/summary without items
        - Filter items by status or tags
        - Provide statistics about list completion
        
        Args:
            name: List identifier to retrieve. If None, returns all lists (summary only)
            include_items: Whether to include list items in response (ignored if name is None)
            summary_only: Return only metadata and statistics, not individual items
            status_filter: Filter items by status ("TODO", "DONE", "WAITING", "CANCELLED", "NEXT", "SOMEDAY")
            tag_filter: Filter items that have ALL specified tags
            
        Returns:
            When retrieving all lists (name is None):
                - success: Operation status
                - lists: Array of list summaries with metadata
                - count: Total number of lists
                
            When retrieving specific list:
                - success: Operation status
                - name: List identifier
                - metadata: List metadata (title, type, description, dates, tags)
                - items: Array of items (if include_items=True and summary_only=False)
                - statistics: Item counts by status and completion percentage
                - error: Error message if retrieval failed
                
        Examples:
            Get all lists:
            >>> list_get()
            
            Get specific list with all items:
            >>> list_get("work-tasks")
            
            Get only TODO items from a list:
            >>> list_get("work-tasks", status_filter="TODO")
            
            Get summary statistics only:
            >>> list_get("work-tasks", summary_only=True)
        """
        # Get all lists
        if name is None:
            return await list_manager.list_all_lists()
        
        # Get specific list
        try:
            list_info = await list_manager.get_list(name)
            if not list_info["success"]:
                return list_info
            
            # Calculate statistics
            items = list_info["items"]
            status_counts = {}
            for item in items:
                status = item["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
            
            done_items = status_counts.get("DONE", 0)
            total_items = len(items)
            completion_percentage = (done_items / total_items * 100) if total_items > 0 else 0
            
            result = {
                "success": True,
                "name": name,
                "metadata": list_info["metadata"],
                "statistics": {
                    "total_items": total_items,
                    "status_counts": status_counts,
                    "completion_percentage": round(completion_percentage, 1)
                }
            }
            
            # Apply filters and include items if requested
            if not summary_only and include_items:
                filtered_items = items
                
                # Apply status filter
                if status_filter:
                    filtered_items = [item for item in filtered_items if item["status"] == status_filter]
                
                # Apply tag filter (items must have ALL specified tags)
                if tag_filter:
                    filtered_items = [
                        item for item in filtered_items 
                        if all(tag in item.get("tags", []) for tag in tag_filter)
                    ]
                
                result["items"] = filtered_items
                if status_filter or tag_filter:
                    result["filters_applied"] = {
                        "status": status_filter,
                        "tags": tag_filter,
                        "filtered_count": len(filtered_items)
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting list '{name}': {e}")
            return {"success": False, "error": str(e)}
    
    @mcp.tool()
    async def list_modify(
        list_name: str,
        action: Literal["add", "update", "remove"],
        item_text: Optional[str] = None,
        item_index: Optional[int] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add, update, or remove items in a list with a single flexible tool.
        
        This unified tool handles all item-level modifications:
        - Add new items with initial status and tags
        - Update existing items (text, status, or tags)
        - Remove items from the list
        - Quickly toggle item status between TODO/DONE
        
        Args:
            list_name: Identifier of the list to modify
            action: Operation to perform - "add", "update", or "remove"
            item_text: 
                - For "add": Text content of the new item (required)
                - For "update": New text for the item (optional, unchanged if None)
                - For "remove": Not used
            item_index: 
                - For "add": Not used
                - For "update"/"remove": 0-based index of item to modify (required)
            status: Item status - "TODO", "DONE", "WAITING", "CANCELLED", "NEXT", "SOMEDAY"
                - For "add": Initial status (defaults to "TODO")
                - For "update": New status (optional, unchanged if None)
                - For "remove": Not used
            tags: Tags for categorizing items
                - For "add": Initial tags for new item
                - For "update": Replace all tags (None keeps existing tags)
                - For "remove": Not used
                
        Returns:
            Dictionary containing:
            - success: Whether the operation succeeded
            - action: The action performed
            - item: Details of the affected item
            - list_name: The list that was modified
            - error: Error message if operation failed
            
        Examples:
            Add a new task:
            >>> list_modify("work-tasks", "add", "Review Q1 report", status="TODO", tags=["urgent", "reports"])
            
            Mark item as done:
            >>> list_modify("work-tasks", "update", item_index=2, status="DONE")
            
            Update item text and add tags:
            >>> list_modify("shopping", "update", item_index=0, item_text="Buy organic milk", tags=["dairy", "organic"])
            
            Remove completed item:
            >>> list_modify("work-tasks", "remove", item_index=5)
        """
        try:
            if action == "add":
                if not item_text:
                    return {"success": False, "error": "item_text is required for add action"}
                
                return await list_manager.add_item(
                    list_name=list_name,
                    item_text=item_text,
                    status=status or "TODO",
                    tags=tags
                )
            
            elif action == "update":
                if item_index is None:
                    return {"success": False, "error": "item_index is required for update action"}
                
                return await list_manager.update_item(
                    list_name=list_name,
                    item_index=item_index,
                    new_text=item_text,
                    new_status=status,
                    new_tags=tags
                )
            
            elif action == "remove":
                if item_index is None:
                    return {"success": False, "error": "item_index is required for remove action"}
                
                return await list_manager.remove_item(
                    list_name=list_name,
                    item_index=item_index
                )
            
            else:
                return {"success": False, "error": f"Invalid action: {action}. Use 'add', 'update', or 'remove'"}
                
        except Exception as e:
            logger.error(f"Error in list_modify: {e}")
            return {"success": False, "error": str(e)}
    
    @mcp.tool()
    async def list_delete(name: str) -> Dict[str, Any]:
        """Permanently delete an entire list and all its items.
        
        WARNING: This action cannot be undone. The list file will be archived
        but not immediately deleted from the filesystem.
        
        Args:
            name: Identifier of the list to delete
            
        Returns:
            Dictionary containing:
            - success: Whether the list was deleted successfully
            - name: The deleted list identifier
            - items_count: Number of items that were in the list
            - error: Error message if deletion failed
            
        Example:
            >>> list_delete("old-shopping-list")
        """
        return await list_manager.delete_list(name)
    
    @mcp.tool()
    async def list_search(
        query: str,
        list_names: Optional[List[str]] = None,
        search_in: List[Literal["text", "tags"]] = ["text"],
        case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Search for items across one or more lists with flexible search options.
        
        Powerful search tool that can find items by text content or tags across
        multiple lists simultaneously. Results include full context about where
        each item was found.
        
        Args:
            query: Search term or phrase to look for
            list_names: Specific lists to search in. If None, searches all lists
            search_in: Where to search - ["text"] for item content, ["tags"] for tags, or both
            case_sensitive: Whether search should be case-sensitive (default: False)
            
        Returns:
            Dictionary containing:
            - success: Whether search completed successfully
            - query: The search query used
            - matches: Array of matching items with:
                - list_name: Which list contains the item
                - list_title: Human-readable list title
                - item_index: Position in the list
                - item_text: Full item text
                - item_status: Current status
                - item_tags: Associated tags
                - match_type: Where match was found ("text" or "tag")
            - total_matches: Total number of matching items
            - lists_searched: Number of lists searched
            - error: Error message if search failed
            
        Examples:
            Search all lists for a term:
            >>> list_search("meeting")
            
            Search specific lists:
            >>> list_search("budget", list_names=["work-tasks", "projects"])
            
            Search only in tags:
            >>> list_search("urgent", search_in=["tags"])
            
            Search both text and tags with case sensitivity:
            >>> list_search("ASAP", search_in=["text", "tags"], case_sensitive=True)
        """
        try:
            matching_items = []
            lists_searched = 0
            
            # Determine which lists to search
            if list_names:
                lists_to_search = []
                for name in list_names:
                    list_info = await list_manager.get_list(name)
                    if list_info["success"]:
                        lists_to_search.append((name, list_info))
            else:
                all_lists = await list_manager.list_all_lists()
                if not all_lists["success"]:
                    return all_lists
                
                lists_to_search = []
                for list_summary in all_lists["lists"]:
                    list_info = await list_manager.get_list(list_summary["name"])
                    if list_info["success"]:
                        lists_to_search.append((list_summary["name"], list_info))
            
            lists_searched = len(lists_to_search)
            
            # Prepare search query
            search_query = query if case_sensitive else query.lower()
            
            # Search through items
            for search_list_name, list_info in lists_to_search:
                for item in list_info["items"]:
                    match_found = False
                    match_type = None
                    
                    # Search in text
                    if "text" in search_in:
                        item_text = item["text"] if case_sensitive else item["text"].lower()
                        if search_query in item_text:
                            match_found = True
                            match_type = "text"
                    
                    # Search in tags
                    if "tags" in search_in and not match_found:
                        item_tags = item.get("tags", [])
                        if not case_sensitive:
                            item_tags = [tag.lower() for tag in item_tags]
                        if search_query in item_tags:
                            match_found = True
                            match_type = "tag"
                    
                    if match_found:
                        matching_items.append({
                            "list_name": search_list_name,
                            "list_title": list_info["metadata"]["title"],
                            "item_index": item["index"],
                            "item_text": item["text"],
                            "item_status": item["status"],
                            "item_tags": item.get("tags", []),
                            "match_type": match_type
                        })
            
            return {
                "success": True,
                "query": query,
                "matches": matching_items,
                "total_matches": len(matching_items),
                "lists_searched": lists_searched,
                "search_options": {
                    "list_names": list_names,
                    "search_in": search_in,
                    "case_sensitive": case_sensitive
                }
            }
            
        except Exception as e:
            logger.error(f"Error searching with query '{query}': {e}")
            return {"success": False, "error": str(e)}
    
    # Register list resource handler
    @mcp.resource("list://{name}")
    async def get_list_resource(name: str) -> str:
        """Get list contents as a resource.
        
        Args:
            name: Name of the list
            
        Returns:
            List contents as formatted text
        """
        try:
            list_info = await list_manager.get_list(name)
            if not list_info["success"]:
                return f"Error: {list_info['error']}"
            
            # Format list as readable text
            lines = []
            metadata = list_info["metadata"]
            lines.append(f"# {metadata['title']}")
            lines.append(f"Type: {metadata['type']}")
            lines.append(f"Created: {metadata['created']}")
            lines.append(f"Modified: {metadata['modified']}")
            
            if metadata['description']:
                lines.append(f"Description: {metadata['description']}")
            
            if metadata['tags']:
                lines.append(f"Tags: {', '.join(metadata['tags'])}")
            
            lines.append("")  # Empty line
            lines.append("## Items")
            
            if list_info["items"]:
                for i, item in enumerate(list_info["items"]):
                    status_symbol = "✓" if item["status"] == "DONE" else "○"
                    item_line = f"{i}. {status_symbol} {item['text']}"
                    if item.get("tags"):
                        item_line += f" ({', '.join(item['tags'])})"
                    lines.append(item_line)
            else:
                lines.append("No items")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error accessing list resource {name}: {str(e)}")
            return f"Error: {str(e)}"