from mcp.client.sse import sse_client
from mcp import ClientSession
import asyncio
import json
import argparse

async def run_sse_client(protocol, host, port):
    # Construct SSE URL from protocol, host and port
    sse_url = f"{protocol}://{host}:{port}/sse"
    print(f"Connecting to: {sse_url}")

    # Connect to the SSE endpoint
    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # Perform an operation (e.g., list tools)
            result = await session.list_tools()
            
            print("\n==== Available Tools ====\n")
            for tool in result.tools:
                print(f"📌 {tool.name}")
                
                # Get the first line of description for conciseness
                first_desc_line = tool.description.split('\n')[0].strip()
                print(f"   Description: {first_desc_line}")
                
                # Add required parameters
                if hasattr(tool, "inputSchema") and isinstance(tool.inputSchema, dict):
                    required_params = tool.inputSchema.get('required', [])
                    if required_params:
                        print(f"   Required parameters: {', '.join(required_params)}")
                
                    # Add parameter details with their types
                    properties = tool.inputSchema.get('properties', {})
                    if properties:
                        print("   Parameters:")
                        for param_name, param_info in properties.items():
                            param_type = param_info.get('type', 'unknown')
                            default = f", default: {param_info['default']}" if 'default' in param_info else ""
                            required = " (required)" if param_name in required_params else ""
                            print(f"     - {param_name}: {param_type}{default}{required}")
                
                print()  # Empty line between tools

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List MCP tools from a server")
    parser.add_argument("--protocol", default="http", choices=["http", "https"], help="Protocol to use (default: http)")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    
    args = parser.parse_args()
    
    asyncio.run(run_sse_client(args.protocol, args.host, args.port))
