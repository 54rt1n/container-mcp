# tests/unit/test_list_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for ListManager."""

import os
import pytest
import asyncio
from datetime import datetime

from cmcp.managers.list_manager import ListManager, ListMetadata, ListItem


@pytest.mark.asyncio
async def test_create_list_basic(list_manager):
    """Test basic list creation."""
    # Create a simple list
    result = await list_manager.create_list(
        name="test-list",
        title="Test List",
        list_type="todo",
        description="A test list",
        tags=["test", "example"]
    )
    
    assert result["success"] is True
    assert result["name"] == "test-list"
    assert result["metadata"]["title"] == "Test List"
    assert result["metadata"]["type"] == "todo"
    assert result["metadata"]["description"] == "A test list"
    assert result["metadata"]["tags"] == ["test", "example"]
    assert "created" in result["metadata"]
    assert "modified" in result["metadata"]


@pytest.mark.asyncio
async def test_create_list_duplicate(list_manager):
    """Test creating a list with duplicate name."""
    # Create first list
    result1 = await list_manager.create_list("duplicate-test", "First List")
    assert result1["success"] is True
    
    # Try to create duplicate
    result2 = await list_manager.create_list("duplicate-test", "Second List")
    assert result2["success"] is False
    assert "already exists" in result2["error"]


@pytest.mark.asyncio
async def test_create_list_minimal(list_manager):
    """Test creating a list with minimal parameters."""
    result = await list_manager.create_list("minimal")
    
    assert result["success"] is True
    assert result["name"] == "minimal"
    assert result["metadata"]["title"] == "minimal"  # Should default to name
    assert result["metadata"]["type"] == "todo"  # Should default to todo


@pytest.mark.asyncio
async def test_get_list_basic(list_manager):
    """Test getting a list's contents."""
    # Create a list first
    await list_manager.create_list("get-test", "Get Test List")
    
    # Get the list
    result = await list_manager.get_list("get-test")
    
    assert result["success"] is True
    assert result["name"] == "get-test"
    assert result["metadata"]["title"] == "Get Test List"
    assert result["items"] == []  # Should be empty initially
    assert "statistics" in result
    assert result["statistics"]["total_items"] == 0


@pytest.mark.asyncio
async def test_get_list_not_found(list_manager):
    """Test getting a non-existent list."""
    result = await list_manager.get_list("non-existent")
    
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_list_all_lists_empty(list_manager):
    """Test listing all lists when none exist."""
    result = await list_manager.list_all_lists()
    
    assert result["success"] is True
    assert result["lists"] == []
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_list_all_lists_with_data(list_manager):
    """Test listing all lists with data."""
    # Create some test lists
    await list_manager.create_list("list1", "First List", "todo", tags=["work"])
    await list_manager.create_list("list2", "Second List", "shopping", tags=["personal"])
    
    result = await list_manager.list_all_lists()
    
    assert result["success"] is True
    assert result["count"] == 2
    assert len(result["lists"]) == 2
    
    # Check that both lists are present
    list_names = [lst["name"] for lst in result["lists"]]
    assert "list1" in list_names
    assert "list2" in list_names


@pytest.mark.asyncio
async def test_add_item_basic(list_manager):
    """Test adding an item to a list."""
    # Create a list
    await list_manager.create_list("add-test", "Add Test List")
    
    # Add an item
    result = await list_manager.add_item(
        list_name="add-test",
        item_text="Test task",
        status="TODO",
        tags=["important"]
    )
    
    assert result["success"] is True
    assert result["action"] == "add"
    assert result["list_name"] == "add-test"
    assert result["item"]["text"] == "Test task"
    assert result["item"]["status"] == "TODO"
    assert result["item"]["tags"] == ["important"]
    assert result["item"]["index"] == 0
    assert result["total_items"] == 1


@pytest.mark.asyncio
async def test_add_item_invalid_status(list_manager):
    """Test adding an item with invalid status."""
    await list_manager.create_list("status-test", "Status Test List")
    
    result = await list_manager.add_item(
        list_name="status-test",
        item_text="Test task",
        status="INVALID"
    )
    
    assert result["success"] is False
    assert "Invalid status" in result["error"]


@pytest.mark.asyncio
async def test_add_item_nonexistent_list(list_manager):
    """Test adding an item to a non-existent list."""
    result = await list_manager.add_item(
        list_name="nonexistent",
        item_text="Test task"
    )
    
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_update_item_basic(list_manager):
    """Test updating an item in a list."""
    # Create list and add item
    await list_manager.create_list("update-test", "Update Test List")
    await list_manager.add_item("update-test", "Original text", "TODO", ["tag1"])
    
    # Update the item
    result = await list_manager.update_item(
        list_name="update-test",
        item_index=0,
        new_text="Updated text",
        new_status="DONE",
        new_tags=["tag2", "tag3"]
    )
    
    assert result["success"] is True
    assert result["action"] == "update"
    assert result["item_index"] == 0
    assert result["item"]["text"] == "Updated text"
    assert result["item"]["status"] == "DONE"
    assert result["item"]["tags"] == ["tag2", "tag3"]
    assert result["old_item"]["text"] == "Original text"
    assert result["old_item"]["status"] == "TODO"


@pytest.mark.asyncio
async def test_update_item_partial(list_manager):
    """Test updating only some fields of an item."""
    # Create list and add item
    await list_manager.create_list("partial-update", "Partial Update Test")
    await list_manager.add_item("partial-update", "Original text", "TODO", ["original"])
    
    # Update only status
    result = await list_manager.update_item(
        list_name="partial-update",
        item_index=0,
        new_status="DONE"
    )
    
    assert result["success"] is True
    assert result["item"]["text"] == "Original text"  # Should remain unchanged
    assert result["item"]["status"] == "DONE"  # Should be updated
    assert result["item"]["tags"] == ["original"]  # Should remain unchanged


@pytest.mark.asyncio
async def test_update_item_invalid_index(list_manager):
    """Test updating an item with invalid index."""
    await list_manager.create_list("index-test", "Index Test List")
    
    result = await list_manager.update_item(
        list_name="index-test",
        item_index=999,
        new_text="Updated text"
    )
    
    assert result["success"] is False
    assert "out of range" in result["error"]


@pytest.mark.asyncio
async def test_remove_item_basic(list_manager):
    """Test removing an item from a list."""
    # Create list and add items
    await list_manager.create_list("remove-test", "Remove Test List")
    await list_manager.add_item("remove-test", "First item")
    await list_manager.add_item("remove-test", "Second item")
    
    # Remove the first item
    result = await list_manager.remove_item("remove-test", 0)
    
    assert result["success"] is True
    assert result["action"] == "remove"
    assert result["removed_item"]["text"] == "First item"
    assert result["remaining_items"] == 1
    
    # Verify the remaining item has correct index
    list_result = await list_manager.get_list("remove-test")
    assert len(list_result["items"]) == 1
    assert list_result["items"][0]["text"] == "Second item"
    assert list_result["items"][0]["index"] == 0  # Should be re-indexed


@pytest.mark.asyncio
async def test_remove_item_invalid_index(list_manager):
    """Test removing an item with invalid index."""
    await list_manager.create_list("remove-index-test", "Remove Index Test")
    
    result = await list_manager.remove_item("remove-index-test", 999)
    
    assert result["success"] is False
    assert "out of range" in result["error"]


@pytest.mark.asyncio
async def test_delete_list_basic(list_manager):
    """Test deleting a list."""
    # Create list and add some items
    await list_manager.create_list("delete-test", "Delete Test List")
    await list_manager.add_item("delete-test", "Item 1")
    await list_manager.add_item("delete-test", "Item 2")
    
    # Delete the list
    result = await list_manager.delete_list("delete-test")
    
    assert result["success"] is True
    assert result["name"] == "delete-test"
    assert result["items_count"] == 2
    assert "archived_to" in result
    
    # Verify the list is no longer accessible
    get_result = await list_manager.get_list("delete-test")
    assert get_result["success"] is False


@pytest.mark.asyncio
async def test_delete_list_nonexistent(list_manager):
    """Test deleting a non-existent list."""
    result = await list_manager.delete_list("nonexistent")
    
    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_search_items_basic(list_manager):
    """Test searching for items across lists."""
    # Create lists with items
    await list_manager.create_list("search-list1", "Search List 1")
    await list_manager.add_item("search-list1", "Important meeting", "TODO", ["work"])
    await list_manager.add_item("search-list1", "Buy groceries", "TODO", ["personal"])
    
    await list_manager.create_list("search-list2", "Search List 2")
    await list_manager.add_item("search-list2", "Schedule important call", "TODO", ["work"])
    
    # Search for "important"
    result = await list_manager.search_items("important")
    
    assert result["success"] is True
    assert result["query"] == "important"
    assert result["total_matches"] == 2
    assert result["lists_searched"] == 2
    
    # Check matches
    matches = result["matches"]
    assert len(matches) == 2
    assert any("Important meeting" in match["item_text"] for match in matches)
    assert any("important call" in match["item_text"] for match in matches)


@pytest.mark.asyncio
async def test_search_items_specific_lists(list_manager):
    """Test searching in specific lists only."""
    # Create lists with items
    await list_manager.create_list("search-specific1", "Search Specific 1")
    await list_manager.add_item("search-specific1", "Find this item", "TODO")
    
    await list_manager.create_list("search-specific2", "Search Specific 2")
    await list_manager.add_item("search-specific2", "Find this too", "TODO")
    
    # Search only in the first list
    result = await list_manager.search_items("Find", list_names=["search-specific1"])
    
    assert result["success"] is True
    assert result["total_matches"] == 1
    assert result["lists_searched"] == 1
    assert result["matches"][0]["item_text"] == "Find this item"


@pytest.mark.asyncio
async def test_search_items_in_tags(list_manager):
    """Test searching in item tags."""
    # Create list with tagged items
    await list_manager.create_list("tag-search", "Tag Search List")
    await list_manager.add_item("tag-search", "Task 1", "TODO", ["urgent", "work"])
    await list_manager.add_item("tag-search", "Task 2", "TODO", ["personal", "urgent"])
    await list_manager.add_item("tag-search", "Task 3", "TODO", ["work"])
    
    # Search for "urgent" in tags
    result = await list_manager.search_items("urgent", search_in=["tags"])
    
    assert result["success"] is True
    assert result["total_matches"] == 2
    
    # Both matches should be tag matches
    for match in result["matches"]:
        assert match["match_type"] == "tag"
        assert "urgent" in match["item_tags"]


@pytest.mark.asyncio
async def test_search_items_case_sensitive(list_manager):
    """Test case-sensitive search."""
    # Create list with items
    await list_manager.create_list("case-test", "Case Test List")
    await list_manager.add_item("case-test", "Important Task", "TODO")
    await list_manager.add_item("case-test", "important task", "TODO")
    
    # Case-insensitive search (default)
    result1 = await list_manager.search_items("IMPORTANT", case_sensitive=False)
    assert result1["total_matches"] == 2
    
    # Case-sensitive search
    result2 = await list_manager.search_items("Important", case_sensitive=True)
    assert result2["total_matches"] == 1
    assert result2["matches"][0]["item_text"] == "Important Task"


@pytest.mark.asyncio
async def test_get_list_types(list_manager):
    """Test getting list types."""
    # Create lists of different types
    await list_manager.create_list("todo-list", "Todo List", "todo")
    await list_manager.create_list("shopping-list", "Shopping List", "shopping")
    await list_manager.create_list("notes-list", "Notes List", "notes")
    await list_manager.create_list("another-todo", "Another Todo", "todo")
    
    result = await list_manager.get_list_types()
    
    assert result["success"] is True
    assert result["types"]["todo"] == 2
    assert result["types"]["shopping"] == 1
    assert result["types"]["notes"] == 1
    assert "default_types" in result


@pytest.mark.asyncio
async def test_org_content_parsing(list_manager):
    """Test parsing of org-mode content."""
    # Create a list and add items
    await list_manager.create_list("org-test", "Org Test List", "todo", "Test description")
    await list_manager.add_item("org-test", "First task", "TODO", ["tag1", "tag2"])
    await list_manager.add_item("org-test", "Second task", "DONE", ["tag3"])
    
    # Get the list to verify parsing
    result = await list_manager.get_list("org-test")
    
    assert result["success"] is True
    assert len(result["items"]) == 2
    
    # Check first item
    first_item = result["items"][0]
    assert first_item["text"] == "First task"
    assert first_item["status"] == "TODO"
    assert first_item["tags"] == ["tag1", "tag2"]
    
    # Check second item
    second_item = result["items"][1]
    assert second_item["text"] == "Second task"
    assert second_item["status"] == "DONE"
    assert second_item["tags"] == ["tag3"]


@pytest.mark.asyncio
async def test_list_statistics(list_manager):
    """Test list statistics calculation."""
    # Create a list with mixed status items
    await list_manager.create_list("stats-test", "Statistics Test List")
    await list_manager.add_item("stats-test", "Task 1", "TODO")
    await list_manager.add_item("stats-test", "Task 2", "DONE")
    await list_manager.add_item("stats-test", "Task 3", "TODO")
    await list_manager.add_item("stats-test", "Task 4", "DONE")
    await list_manager.add_item("stats-test", "Task 5", "WAITING")
    
    result = await list_manager.get_list("stats-test")
    
    assert result["success"] is True
    stats = result["statistics"]
    
    assert stats["total_items"] == 5
    assert stats["status_counts"]["TODO"] == 2
    assert stats["status_counts"]["DONE"] == 2
    assert stats["status_counts"]["WAITING"] == 1
    assert stats["completion_percentage"] == 40.0  # 2/5 * 100


@pytest.mark.asyncio
async def test_from_env_initialization(test_config):
    """Test .from_env() initialization."""
    # Mock the config loader to return our test config
    import cmcp.config
    original_load_config = cmcp.config.load_config
    cmcp.config.load_config = lambda: test_config

    try:
        # Initialize from environment
        manager = ListManager.from_env()
        
        # Verify the manager was initialized correctly
        assert manager.storage_path == test_config.list_config.storage_path
        
        # Test that the manager works
        result = await manager.create_list("env-test", "Environment Test List")
        assert result["success"] is True
        
    finally:
        # Restore the original function
        cmcp.config.load_config = original_load_config


@pytest.mark.asyncio
async def test_item_completion_tracking(list_manager):
    """Test that item completion is tracked correctly."""
    # Create list and add item
    await list_manager.create_list("completion-test", "Completion Test List")
    await list_manager.add_item("completion-test", "Test task", "TODO")
    
    # Update item to DONE
    result = await list_manager.update_item(
        list_name="completion-test",
        item_index=0,
        new_status="DONE"
    )
    
    assert result["success"] is True
    assert result["item"]["completed"] is not None
    assert result["old_item"]["completed"] is None
    
    # Update back to TODO
    result2 = await list_manager.update_item(
        list_name="completion-test",
        item_index=0,
        new_status="TODO"
    )
    
    assert result2["success"] is True
    assert result2["item"]["completed"] is None


@pytest.mark.asyncio
async def test_filename_sanitization(list_manager):
    """Test that list names are properly sanitized for filenames."""
    # Create list with characters that need sanitization
    result = await list_manager.create_list("test/list with spaces & special chars!")
    
    assert result["success"] is True
    
    # Should be able to retrieve the list
    get_result = await list_manager.get_list("test/list with spaces & special chars!")
    assert get_result["success"] is True
    
    # Check that the file was created (filename should be sanitized)
    assert os.path.exists(list_manager._get_list_path("test/list with spaces & special chars!"))


@pytest.mark.asyncio
async def test_multiple_item_operations(list_manager):
    """Test multiple operations on the same list."""
    # Create list
    await list_manager.create_list("multi-op", "Multi Operation List")
    
    # Add multiple items
    await list_manager.add_item("multi-op", "Task 1", "TODO", ["work"])
    await list_manager.add_item("multi-op", "Task 2", "TODO", ["personal"])
    await list_manager.add_item("multi-op", "Task 3", "TODO", ["work"])
    
    # Update one item
    await list_manager.update_item("multi-op", 1, new_status="DONE")
    
    # Remove one item
    await list_manager.remove_item("multi-op", 0)
    
    # Check final state
    result = await list_manager.get_list("multi-op")
    assert result["success"] is True
    assert len(result["items"]) == 2
    
    # Check that indices are correct after removal
    assert result["items"][0]["index"] == 0
    assert result["items"][1]["index"] == 1
    
    # Check that the right items remain
    assert result["items"][0]["text"] == "Task 2"
    assert result["items"][0]["status"] == "DONE"
    assert result["items"][1]["text"] == "Task 3"
    assert result["items"][1]["status"] == "TODO" 