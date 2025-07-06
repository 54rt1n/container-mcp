# cmcp/managers/list_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""List Manager for managing org-mode based lists."""

import os
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path

from cmcp.utils.logging import get_logger
from cmcp.managers.file_manager import FileManager
from cmcp.utils.io import read_file, write_file, list_directory, delete_file

logger = get_logger(__name__)


@dataclass
class ListItem:
    """Represents a single item in a list."""
    
    text: str
    status: str = "TODO"  # TODO, DONE, WAITING, CANCELLED, NEXT, SOMEDAY
    index: int = 0
    tags: List[str] = field(default_factory=list)
    created: Optional[str] = None  # Track when item was added
    completed: Optional[str] = None  # Track when item was marked DONE


@dataclass
class ListMetadata:
    """Metadata for a list."""
    
    title: str
    type: str = "todo"
    created: str = ""
    modified: str = ""
    tags: List[str] = field(default_factory=list)
    description: str = ""
    author: str = ""  # Who created the list
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "title": self.title,
            "type": self.type,
            "created": self.created,
            "modified": self.modified,
            "tags": self.tags,
            "description": self.description,
            "author": self.author
        }


@dataclass
class ListInfo:
    """Complete information about a list."""
    
    name: str
    metadata: ListMetadata
    items: List[ListItem]
    file_path: str
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate statistics for the list."""
        status_counts = {}
        tag_counts = {}
        
        for item in self.items:
            # Count by status
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            
            # Count by tags
            for tag in item.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        total_items = len(self.items)
        done_items = status_counts.get("DONE", 0)
        completion_percentage = (done_items / total_items * 100) if total_items > 0 else 0
        
        return {
            "total_items": total_items,
            "status_counts": status_counts,
            "tag_counts": tag_counts,
            "completion_percentage": round(completion_percentage, 1),
            "done_items": done_items,
            "pending_items": total_items - done_items
        }


class ListManager:
    """Manager for org-mode based list operations."""
    
    VALID_STATUSES = ["TODO", "DONE", "WAITING", "CANCELLED", "NEXT", "SOMEDAY"]
    DEFAULT_LIST_TYPES = ["todo", "shopping", "notes", "checklist", "project", "reading", "ideas"]
    
    def __init__(self, storage_path: str):
        """Initialize the ListManager.
        
        Args:
            storage_path: The path to the storage directory
        """
        self.storage_path = storage_path
        self._ensure_storage_directory()
        
        logger.debug(f"ListManager initialized with lists dir: {self.storage_path}")
    
    def _ensure_storage_directory(self):
        """Ensure the storage directory exists."""
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls, config=None):
        """Create a ListManager from environment configuration.
        
        Args:
            config: Optional configuration object, loads from environment if not provided
            
        Returns:
            Configured ListManager instance
        """
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
        logger.debug("Creating ListManager from environment configuration")
        
        # Use environment variable for lists directory if available
        return cls(storage_path=config.list_config.storage_path)
    
    def _get_list_path(self, list_name: str) -> str:
        """Get the file path for a list.
        
        Args:
            list_name: Name of the list
            
        Returns:
            Relative path to the list file
        """
        # Sanitize list name for filename
        safe_name = re.sub(r'[^\w\-_\.]', '_', list_name)
        if not safe_name.endswith('.org'):
            safe_name += '.org'
        
        return f"{self.storage_path}/{safe_name}"
    
    def _parse_org_content(self, content: str) -> Tuple[ListMetadata, List[ListItem]]:
        """Parse org-mode content to extract metadata and items.
        
        Args:
            content: Org-mode file content
            
        Returns:
            Tuple of (metadata, items)
        """
        lines = content.split('\n')
        metadata = ListMetadata(title="Untitled List")
        items = []
        
        # Parse metadata from org headers
        for line in lines:
            line = line.strip()
            if line.startswith('#+TITLE:'):
                metadata.title = line[8:].strip()
            elif line.startswith('#+TYPE:'):
                metadata.type = line[7:].strip()
            elif line.startswith('#+CREATED:'):
                metadata.created = line[10:].strip()
            elif line.startswith('#+MODIFIED:'):
                metadata.modified = line[11:].strip()
            elif line.startswith('#+TAGS:'):
                tags_str = line[7:].strip()
                metadata.tags = [tag.strip() for tag in tags_str.split()] if tags_str else []
            elif line.startswith('#+DESCRIPTION:'):
                metadata.description = line[14:].strip()
            elif line.startswith('#+AUTHOR:'):
                metadata.author = line[9:].strip()
        
        # Parse items (look for * TODO, * DONE, etc.)
        item_index = 0
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Match org-mode todo items: * STATUS text
            match = re.match(r'^\*+\s+(TODO|DONE|WAITING|CANCELLED|NEXT|SOMEDAY)\s+(.+)', line_stripped)
            if match:
                status = match.group(1)
                item_text = match.group(2)
                
                # Extract tags from item text (tags at end like :tag1:tag2:)
                tags = []
                tag_match = re.search(r'\s+:([\w:]+):$', item_text)
                if tag_match:
                    tag_string = tag_match.group(1)
                    tags = [tag for tag in tag_string.split(':') if tag]
                    item_text = re.sub(r'\s+:[\w:]+:$', '', item_text)
                
                # Look for metadata in following lines
                created = None
                completed = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('CREATED:'):
                        created = next_line[8:].strip()
                    elif next_line.startswith('COMPLETED:'):
                        completed = next_line[10:].strip()
                
                items.append(ListItem(
                    text=item_text,
                    status=status,
                    index=item_index,
                    tags=tags,
                    created=created,
                    completed=completed
                ))
                item_index += 1
        
        return metadata, items
    
    def _generate_org_content(self, metadata: ListMetadata, items: List[ListItem]) -> str:
        """Generate org-mode content from metadata and items.
        
        Args:
            metadata: List metadata
            items: List items
            
        Returns:
            Org-mode formatted content
        """
        content_lines = []
        
        # Add metadata headers
        content_lines.append(f"#+TITLE: {metadata.title}")
        content_lines.append(f"#+TYPE: {metadata.type}")
        content_lines.append(f"#+CREATED: {metadata.created}")
        content_lines.append(f"#+MODIFIED: {metadata.modified}")
        
        if metadata.tags:
            content_lines.append(f"#+TAGS: {' '.join(metadata.tags)}")
        
        if metadata.description:
            content_lines.append(f"#+DESCRIPTION: {metadata.description}")
            
        if metadata.author:
            content_lines.append(f"#+AUTHOR: {metadata.author}")
        
        content_lines.append("")  # Empty line before items
        
        # Add items
        if items:
            for item in items:
                item_line = f"* {item.status} {item.text}"
                if item.tags:
                    item_line += f" :{':'.join(item.tags)}:"
                content_lines.append(item_line)
                
                # Add item metadata
                if item.created:
                    content_lines.append(f"  CREATED: {item.created}")
                if item.completed:
                    content_lines.append(f"  COMPLETED: {item.completed}")
        else:
            content_lines.append("* No items yet")
        
        return '\n'.join(content_lines)
    
    async def create_list(self, name: str, title: Optional[str] = None, 
                         list_type: str = "todo", description: str = "", 
                         tags: Optional[List[str]] = None,
                         author: str = "") -> Dict[str, Any]:
        """Create a new list.
        
        Args:
            name: Internal name for the list (used for filename)
            title: Display title for the list
            list_type: Type of list (todo, shopping, etc.)
            description: Optional description
            tags: Optional list of tags
            author: Optional author name
            
        Returns:
            Dictionary with creation result
        """
        try:
            list_path = self._get_list_path(name)
            
            # Check if list already exists
            try:
                await read_file(list_path)
                return {
                    "success": False,
                    "error": f"List '{name}' already exists"
                }
            except FileNotFoundError:
                pass  # List doesn't exist, we can create it
            
            # Validate list type
            if list_type not in self.DEFAULT_LIST_TYPES:
                logger.warning(f"Non-standard list type '{list_type}' used")
            
            # Create metadata
            now = datetime.now().isoformat()
            metadata = ListMetadata(
                title=title or name,
                type=list_type,
                created=now,
                modified=now,
                description=description,
                tags=tags or [],
                author=author
            )
            
            # Generate org content
            content = self._generate_org_content(metadata, [])
            
            # Write the file
            await write_file(list_path, content)
            
            logger.info(f"Created list '{name}' at {list_path}")
            return {
                "success": True,
                "name": name,
                "metadata": metadata.to_dict(),
                "path": list_path
            }
            
        except Exception as e:
            logger.error(f"Error creating list '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_list(self, name: str) -> Dict[str, Any]:
        """Get a list's contents.
        
        Args:
            name: Name of the list
            
        Returns:
            Dictionary with list information
        """
        try:
            list_path = self._get_list_path(name)
            content, file_metadata = await read_file(list_path)
            
            metadata, items = self._parse_org_content(content)
            
            # Create ListInfo for statistics
            list_info = ListInfo(
                name=name,
                metadata=metadata,
                items=items,
                file_path=list_path
            )
            
            return {
                "success": True,
                "name": name,
                "metadata": metadata.to_dict(),
                "items": [self._item_to_dict(item) for item in items],
                "statistics": list_info.get_statistics(),
                "file_size": file_metadata.size,
                "file_modified": file_metadata.modified_time
            }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"List '{name}' not found"
            }
        except Exception as e:
            logger.error(f"Error reading list '{name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _item_to_dict(self, item: ListItem) -> Dict[str, Any]:
        """Convert ListItem to dictionary."""
        return {
            "text": item.text,
            "status": item.status,
            "index": item.index,
            "tags": item.tags,
            "created": item.created,
            "completed": item.completed
        }
    
    async def list_all_lists(self, include_statistics: bool = False) -> Dict[str, Any]:
        """List all available lists.
        
        Args:
            include_statistics: Whether to include detailed statistics for each list
        
        Returns:
            Dictionary with all list information
        """
        try:
            # List files in the lists directory
            entries = await list_directory(self.storage_path, recursive=False)
            
            lists = []
            for entry in entries:
                if entry.name.endswith(".org") and not entry.metadata.is_directory:
                    list_name = entry.name[:-4]  # Remove .org extension
                    
                    # Try to read metadata for each list
                    try:
                        list_info = await self.get_list(list_name)
                        if list_info["success"]:
                            list_summary = {
                                "name": list_name,
                                "title": list_info["metadata"]["title"],
                                "type": list_info["metadata"]["type"],
                                "created": list_info["metadata"]["created"],
                                "modified": list_info["metadata"]["modified"],
                                "tags": list_info["metadata"]["tags"],
                                "description": list_info["metadata"]["description"]
                            }
                            
                            if include_statistics:
                                list_summary.update(list_info["statistics"])
                            else:
                                list_summary["item_count"] = list_info["statistics"]["total_items"]
                            
                            lists.append(list_summary)
                    except Exception as e:
                        logger.warning(f"Could not read list {list_name}: {e}")
                        lists.append({
                            "name": list_name,
                            "title": list_name,
                            "type": "unknown",
                            "item_count": 0,
                            "error": str(e)
                        })
            
            # Sort lists by modified date (newest first)
            lists.sort(key=lambda x: x.get("modified", ""), reverse=True)
            
            return {
                "success": True,
                "lists": lists,
                "count": len(lists)
            }
            
        except Exception as e:
            logger.error(f"Error listing all lists: {e}")
            return {
                "success": False,
                "error": str(e),
                "lists": [],
                "count": 0
            }
    
    async def add_item(self, list_name: str, item_text: str, 
                      status: str = "TODO", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Add an item to a list.
        
        Args:
            list_name: Name of the list
            item_text: Text of the item
            status: Status of the item (TODO, DONE, etc.)
            tags: Optional tags for the item
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Validate status
            if status not in self.VALID_STATUSES:
                return {
                    "success": False,
                    "error": f"Invalid status '{status}'. Valid statuses: {', '.join(self.VALID_STATUSES)}"
                }
            
            # Get current list
            list_info = await self.get_list(list_name)
            if not list_info["success"]:
                return list_info
            
            # Parse current content
            list_path = self._get_list_path(list_name)
            content, _ = await read_file(list_path)
            metadata, items = self._parse_org_content(content)
            
            # Add new item with creation timestamp
            now = datetime.now().isoformat()
            new_item = ListItem(
                text=item_text,
                status=status,
                index=len(items),
                tags=tags or [],
                created=now,
                completed=now if status == "DONE" else None
            )
            items.append(new_item)
            
            # Update modification time
            metadata.modified = now
            
            # Generate updated content
            updated_content = self._generate_org_content(metadata, items)
            
            # Write back to file
            await write_file(list_path, updated_content)
            
            logger.info(f"Added item to list '{list_name}': {item_text}")
            return {
                "success": True,
                "action": "add",
                "list_name": list_name,
                "item": self._item_to_dict(new_item),
                "total_items": len(items)
            }
            
        except Exception as e:
            logger.error(f"Error adding item to list '{list_name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_item(self, list_name: str, item_index: int, 
                         new_text: Optional[str] = None, 
                         new_status: Optional[str] = None,
                         new_tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Update an item in a list.
        
        Args:
            list_name: Name of the list
            item_index: Index of the item to update
            new_text: New text for the item
            new_status: New status for the item
            new_tags: New tags for the item
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Validate status if provided
            if new_status and new_status not in self.VALID_STATUSES:
                return {
                    "success": False,
                    "error": f"Invalid status '{new_status}'. Valid statuses: {', '.join(self.VALID_STATUSES)}"
                }
            
            # Get current list
            list_path = self._get_list_path(list_name)
            content, _ = await read_file(list_path)
            metadata, items = self._parse_org_content(content)
            
            # Validate item index
            if item_index < 0 or item_index >= len(items):
                return {
                    "success": False,
                    "error": f"Item index {item_index} out of range (0-{len(items)-1})"
                }
            
            # Update item
            item = items[item_index]
            old_item = self._item_to_dict(item)
            
            now = datetime.now().isoformat()
            
            if new_text is not None:
                item.text = new_text
            if new_status is not None:
                item.status = new_status
                # Track completion time
                if new_status == "DONE" and old_item["status"] != "DONE":
                    item.completed = now
                elif new_status != "DONE":
                    item.completed = None
            if new_tags is not None:
                item.tags = new_tags
            
            # Update modification time
            metadata.modified = now
            
            # Generate updated content
            updated_content = self._generate_org_content(metadata, items)
            
            # Write back to file
            await write_file(list_path, updated_content)
            
            logger.info(f"Updated item {item_index} in list '{list_name}'")
            return {
                "success": True,
                "action": "update",
                "list_name": list_name,
                "item_index": item_index,
                "old_item": old_item,
                "item": self._item_to_dict(item)
            }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"List '{list_name}' not found"
            }
        except Exception as e:
            logger.error(f"Error updating item in list '{list_name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def remove_item(self, list_name: str, item_index: int) -> Dict[str, Any]:
        """Remove an item from a list.
        
        Args:
            list_name: Name of the list
            item_index: Index of the item to remove
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Get current list
            list_path = self._get_list_path(list_name)
            content, _ = await read_file(list_path)
            metadata, items = self._parse_org_content(content)
            
            # Validate item index
            if item_index < 0 or item_index >= len(items):
                return {
                    "success": False,
                    "error": f"Item index {item_index} out of range (0-{len(items)-1})"
                }
            
            # Remove item
            removed_item = items.pop(item_index)
            
            # Update indices for remaining items
            for i, item in enumerate(items):
                item.index = i
            
            # Update modification time
            metadata.modified = datetime.now().isoformat()
            
            # Generate updated content
            updated_content = self._generate_org_content(metadata, items)
            
            # Write back to file
            await write_file(list_path, updated_content)
            
            logger.info(f"Removed item {item_index} from list '{list_name}'")
            return {
                "success": True,
                "action": "remove",
                "list_name": list_name,
                "removed_item": self._item_to_dict(removed_item),
                "remaining_items": len(items)
            }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"List '{list_name}' not found"
            }
        except Exception as e:
            logger.error(f"Error removing item from list '{list_name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_list(self, list_name: str) -> Dict[str, Any]:
        """Delete a list.
        
        Args:
            list_name: Name of the list to delete
            
        Returns:
            Dictionary with operation result
        """
        try:
            list_path = self._get_list_path(list_name)
            
            # Get list info before deletion
            list_info = await self.get_list(list_name)
            if not list_info["success"]:
                return list_info
            
            # Archive the file instead of immediate deletion
            archive_dir = f"{self.storage_path}/.archive"
            Path(archive_dir).mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{list_name}_{timestamp}.org"
            archive_path = f"{archive_dir}/{archive_name}"
            
            # Move to archive
            content, _ = await read_file(list_path)
            await write_file(archive_path, content)
            await delete_file(list_path)
            
            logger.info(f"Deleted list '{list_name}' (archived to {archive_path})")
            return {
                "success": True,
                "name": list_name,
                "items_count": list_info["statistics"]["total_items"],
                "archived_to": archive_path
            }
            
        except Exception as e:
            logger.error(f"Error deleting list '{list_name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_items(self, query: str, list_names: Optional[List[str]] = None,
                          search_in: List[str] = ["text"], 
                          case_sensitive: bool = False) -> Dict[str, Any]:
        """Search for items across lists.
        
        Args:
            query: Search query
            list_names: Optional list of specific lists to search in
            search_in: Where to search - "text", "tags", or both
            case_sensitive: Whether search is case-sensitive
            
        Returns:
            Dictionary with search results
        """
        try:
            matching_items = []
            lists_searched = 0
            
            # Determine which lists to search
            if list_names:
                lists_to_search = []
                for name in list_names:
                    list_info = await self.get_list(name)
                    if list_info["success"]:
                        lists_to_search.append((name, list_info))
            else:
                all_lists = await self.list_all_lists()
                if not all_lists["success"]:
                    return all_lists
                
                lists_to_search = []
                for list_summary in all_lists["lists"]:
                    if "error" not in list_summary:  # Skip lists with errors
                        list_info = await self.get_list(list_summary["name"])
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
                    match_details = []
                    
                    # Search in text
                    if "text" in search_in:
                        item_text = item["text"] if case_sensitive else item["text"].lower()
                        if search_query in item_text:
                            match_found = True
                            match_type = "text"
                            # Find position of match
                            pos = item_text.find(search_query)
                            match_details.append({
                                "type": "text",
                                "position": pos,
                                "context": item["text"][max(0, pos-20):pos+len(search_query)+20]
                            })
                    
                    # Search in tags
                    if "tags" in search_in:
                        item_tags = item.get("tags", [])
                        if not case_sensitive:
                            item_tags_lower = [tag.lower() for tag in item_tags]
                            for i, tag in enumerate(item_tags_lower):
                                if search_query in tag:
                                    match_found = True
                                    if match_type != "text":
                                        match_type = "tag"
                                    match_details.append({
                                        "type": "tag",
                                        "tag": item["tags"][i]
                                    })
                        else:
                            for tag in item_tags:
                                if search_query in tag:
                                    match_found = True
                                    if match_type != "text":
                                        match_type = "tag"
                                    match_details.append({
                                        "type": "tag",
                                        "tag": tag
                                    })
                    
                    if match_found:
                        matching_items.append({
                            "list_name": search_list_name,
                            "list_title": list_info["metadata"]["title"],
                            "item_index": item["index"],
                            "item_text": item["text"],
                            "item_status": item["status"],
                            "item_tags": item.get("tags", []),
                            "match_type": match_type,
                            "match_details": match_details
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
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_list_types(self) -> Dict[str, Any]:
        """Get all list types currently in use.
        
        Returns:
            Dictionary with list types and their counts
        """
        try:
            all_lists = await self.list_all_lists()
            if not all_lists["success"]:
                return all_lists
            
            type_counts = {}
            for list_info in all_lists["lists"]:
                list_type = list_info.get("type", "unknown")
                type_counts[list_type] = type_counts.get(list_type, 0) + 1
            
            return {
                "success": True,
                "types": type_counts,
                "default_types": self.DEFAULT_LIST_TYPES
            }
            
        except Exception as e:
            logger.error(f"Error getting list types: {e}")
            return {
                "success": False,
                "error": str(e)
            }