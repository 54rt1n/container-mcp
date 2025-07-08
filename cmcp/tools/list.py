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
        """Create a new organized list for tasks, notes, shopping, or any collection.
        
        This tool creates org-mode based lists that support various item statuses 
        (TODO, DONE, WAITING, etc.) and can be tagged for organization. Perfect for 
        project management, shopping lists, or general note-taking.
        
        Examples:
        
        Request: {"name": "list_create", "parameters": {"name": "work-tasks", "title": "Q1 Work Tasks", "list_type": "todo", "description": "Quarterly objectives and tasks", "tags": ["work", "q1-2025"]}}
        Response: {"success": true, "name": "work-tasks", "metadata": {"title": "Q1 Work Tasks", "type": "todo", "created": "2024-01-01T10:00:00Z"}}
        
        Request: {"name": "list_create", "parameters": {"name": "groceries", "title": "Weekly Groceries", "list_type": "shopping", "tags": ["weekly", "essentials"]}}
        Response: {"success": true, "name": "groceries", "metadata": {"title": "Weekly Groceries", "type": "shopping", "created": "2024-01-01T10:30:00Z"}}
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
        """Retrieve and browse lists with flexible filtering options.
        
        This tool can browse all your lists, get details of specific lists, 
        filter items by status or tags, and provide completion statistics.
        Perfect for checking progress or finding specific items.
        
        Examples:
        
        Request: {"name": "list_get", "parameters": {}}
        Response: {"success": true, "lists": [{"name": "work-tasks", "title": "Q1 Work Tasks", "type": "todo"}], "count": 3}
        
        Request: {"name": "list_get", "parameters": {"name": "work-tasks", "status_filter": "TODO"}}
        Response: {"success": true, "name": "work-tasks", "items": [{"index": 0, "text": "Review code", "status": "TODO"}], "statistics": {"total_items": 5, "completion_percentage": 60.0}}
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
        """Modify list items by adding, updating, or removing them.
        
        This flexible tool handles all item operations within a list. Add new tasks,
        update existing items (change text, status, or tags), mark items as done,
        or remove completed items. Perfect for managing dynamic lists.
        
        Examples:
        
        Request: {"name": "list_modify", "parameters": {"list_name": "work-tasks", "action": "add", "item_text": "Review Q1 report", "status": "TODO", "tags": ["urgent", "reports"]}}
        Response: {"success": true, "action": "add", "item": {"index": 3, "text": "Review Q1 report", "status": "TODO", "tags": ["urgent", "reports"]}}
        
        Request: {"name": "list_modify", "parameters": {"list_name": "work-tasks", "action": "update", "item_index": 2, "status": "DONE"}}
        Response: {"success": true, "action": "update", "item": {"index": 2, "text": "Complete project setup", "status": "DONE"}}
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
        
        This tool completely removes a list from the system. Use with caution as 
        this action cannot be undone. The list file will be archived for safety
        but the list will no longer be accessible through normal operations.
        
        Examples:
        
        Request: {"name": "list_delete", "parameters": {"name": "old-shopping-list"}}
        Response: {"success": true, "name": "old-shopping-list", "items_count": 5, "archived": true}
        
        Request: {"name": "list_delete", "parameters": {"name": "completed-project-tasks"}}
        Response: {"success": true, "name": "completed-project-tasks", "items_count": 12, "archived": true}
        """
        return await list_manager.delete_list(name)
    
    @mcp.tool()
    async def list_search(
        query: str,
        list_names: Optional[List[str]] = None,
        search_in: List[Literal["text", "tags"]] = ["text"],
        case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Search for items across multiple lists by text or tags.
        
        This powerful search tool finds items by content or tags across all your lists
        or specific ones. Get comprehensive results showing exactly where each match
        was found, perfect for locating tasks or items across your organization system.
        
        Examples:
        
        Request: {"name": "list_search", "parameters": {"query": "meeting", "search_in": ["text"]}}
        Response: {"success": true, "query": "meeting", "matches": [{"list_name": "work-tasks", "item_text": "Prepare for team meeting", "item_status": "TODO", "match_type": "text"}], "total_matches": 3}
        
        Request: {"name": "list_search", "parameters": {"query": "urgent", "list_names": ["work-tasks", "projects"], "search_in": ["tags"], "case_sensitive": false}}
        Response: {"success": true, "query": "urgent", "matches": [{"list_name": "work-tasks", "item_text": "Fix critical bug", "item_tags": ["urgent", "bug"], "match_type": "tag"}], "total_matches": 2}
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