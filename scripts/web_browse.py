#!/usr/bin/env python3
# scripts/web_browse.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Browse a webpage via the MCP server."""

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.sse import sse_client


async def main(url: str, host: str, port: int) -> None:
    """Connect to MCP server and browse a webpage."""
    server_url = f"http://{host}:{port}/sse"
    async with sse_client(server_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "web_browse",
                arguments={"url": url}
            )

            for content in result.content:
                if hasattr(content, "text"):
                    data = json.loads(content.text)
                    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Browse a webpage via MCP server")
    parser.add_argument("url", help="URL to browse (e.g., https://example.com)")
    parser.add_argument("--host", default="localhost", help="MCP server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="MCP server port (default: 8000)")

    args = parser.parse_args()
    asyncio.run(main(args.url, args.host, args.port))
