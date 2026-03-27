import pytest
from unittest.mock import AsyncMock, MagicMock

from cmcp.tools.kb import create_kb_tools


class MockMCP:
    def __init__(self):
        self.tool_registry = {}
        self.resource_registry = {}

    def tool(self):
        def register(func):
            self.tool_registry[func.__name__] = func
            return func

        return register

    def resource(self, pattern):
        def register(func):
            self.resource_registry[pattern] = func
            return func

        return register


@pytest.mark.asyncio
async def test_kb_read_bulk_read_handles_document_dicts():
    mcp = MockMCP()
    kb_manager = MagicMock()
    kb_manager.list_documents = AsyncMock(
        return_value=[
            {
                "uri": "kb://research/project/intro",
                "index": {"title": "Intro"},
            }
        ]
    )

    create_kb_tools(mcp, kb_manager)

    kb_read = mcp.tool_registry["kb_read"]
    result = await kb_read(uri="kb://research/project", include_index=True)

    assert result["mode"] == "bulk_read"
    assert result["count"] == 1
    assert result["documents"] == [
        {
            "uri": "kb://research/project/intro",
            "index": {"title": "Intro"},
        }
    ]
