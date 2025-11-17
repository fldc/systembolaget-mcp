# Testing the Systembolaget MCP Server

## Understanding MCP Servers

MCP (Model Context Protocol) servers communicate via JSON-RPC over stdin/stdout. They are designed to be used by MCP clients like Claude Desktop, not directly from the command line.

## Testing Methods

### 1. Using the Test Script (Recommended for Development)

The `test_server.py` script lets you test the server functions directly:

```bash
# With uv
uv run test_server.py

# With Python
python test_server.py
```

This bypasses the JSON-RPC layer and calls the tool functions directly, making it easy to test during development.

### 2. Using Claude Desktop (Recommended for Integration Testing)

This is the primary way to use the server:

1. Add the server to your Claude Desktop config:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "systembolaget": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/systembolaget-mcp",
        "run",
        "systembolaget_mcp.py"
      ]
    }
  }
}
```

2. Restart Claude Desktop

3. Ask questions like:
   - "Search for Swedish beers under 50 SEK"
   - "Find stores in Stockholm"
   - "What wines are available from Italy?"

### 3. Using the MCP Inspector (Advanced)

The MCP Inspector is a tool for testing MCP servers:

```bash
# Install the MCP Inspector
npx @modelcontextprotocol/inspector uv --directory /path/to/systembolaget-mcp run systembolaget_mcp.py
```

This provides a web UI for testing your MCP server.

### 4. Manual JSON-RPC Testing (Advanced)

If you want to test the JSON-RPC protocol manually, you need to send properly formatted messages:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | uv run systembolaget_mcp.py
```

Example tool call:
```bash
echo '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "systembolaget_search_products",
    "arguments": {
      "query": "öl",
      "country": "Sverige",
      "max_price": 50,
      "limit": 5
    }
  }
}' | uv run systembolaget_mcp.py
```

## Common Issues

### ❌ "validation errors for JSONRPCMessage"

This means you tried to send plain text to the server instead of JSON-RPC messages. Use one of the testing methods above instead.

### ❌ "Could not find API key in app bundle"

The server couldn't extract the API key from Systembolaget's website. This can happen if:
- Systembolaget's website structure changed
- Network connectivity issues
- Website is temporarily down

Solution: Set a manual API key:
```bash
export SYSTEMBOLAGET_API_KEY="your-key"
```

### ❌ "Resource not found" or 404 errors

The API endpoint might have changed or the product/store ID doesn't exist. Check the Systembolaget API documentation for the correct endpoints.

## Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or run with verbose output:
```bash
uv run --verbose systembolaget_mcp.py
```

## Running Unit Tests

Once you add tests:

```bash
# With uv
uv run pytest

# With pytest directly
pytest
```

## API Testing

You can test the API key extraction separately:

```python
import asyncio
from systembolaget_mcp import extract_api_key

async def test():
    key = await extract_api_key()
    print(f"API Key: {key[:20]}...")  # Print first 20 chars

asyncio.run(test())
```
