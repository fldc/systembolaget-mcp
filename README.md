# Systembolaget MCP Server

A Model Context Protocol (MCP) server for interacting with Systembolaget's APIs. This server provides tools for searching products, retrieving product details, finding stores, and getting store information.

## Features

### Available Tools

1. **systembolaget_search_products** - Search for products in Systembolaget's catalog
   - Filter by category, price range, alcohol content, country
   - Support for pagination
   - Returns detailed product information including taste profiles

2. **systembolaget_get_product** - Get detailed information about a specific product
   - Comprehensive product details
   - Taste profiles and food pairings
   - Serving suggestions

3. **systembolaget_search_stores** - Search for Systembolaget stores
   - Find stores by name or city
   - Pagination support
   - Returns addresses and contact information

4. **systembolaget_get_store** - Get detailed information about a specific store
   - Complete store details
   - Opening hours
   - Available services and parking information

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer

**Note:** No API key required! The server automatically extracts the API key from Systembolaget's website.

### Setup with uv (Recommended)

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repository:
```bash
git clone https://github.com/fldc/systembolaget-mcp.git
cd systembolaget-mcp
```

3. Install dependencies:
```bash
uv sync
```

Or install with development dependencies:
```bash
uv sync --all-extras
```

4. (Optional) Configure a custom API key:
```bash
export SYSTEMBOLAGET_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```bash
SYSTEMBOLAGET_API_KEY=your-api-key-here
```

**The API key is optional.** If not provided, the server will automatically extract it from Systembolaget's website.

### Alternative: Setup with pip

If you prefer using pip:

```bash
pip install -e .
# Or with dev dependencies:
pip install -e ".[dev]"
```

## Usage

### Running the Server

#### With Claude Desktop

Add this configuration to your Claude Desktop config file:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

**Using uv (Recommended):**
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

**Using Python directly:**
```json
{
  "mcpServers": {
    "systembolaget": {
      "command": "python",
      "args": ["/absolute/path/to/systembolaget-mcp/systembolaget_mcp.py"]
    }
  }
}
```

**Note:** The `env` section with `SYSTEMBOLAGET_API_KEY` is optional. The server will automatically extract the API key if not provided.

#### Standalone Testing

Run the server directly:

**With uv:**
```bash
uv run systembolaget_mcp.py
```

**With Python:**
```bash
python systembolaget_mcp.py
```

### Example Queries

Once connected through Claude Desktop, you can ask questions like:

- "Search for Swedish beers under 50 SEK"
- "Find wines from Italy with alcohol content between 12-14%"
- "Show me stores in Stockholm"
- "Get details for product number 12345"
- "What are the opening hours for the store in Uppsala?"

## Tool Reference

### systembolaget_search_products

Search for products with various filters.

**Parameters:**
- `query` (optional): Search query for product name
- `category` (optional): Filter by category (e.g., 'Öl', 'Vin', 'Sprit')
- `min_price` (optional): Minimum price in SEK
- `max_price` (optional): Maximum price in SEK
- `min_alcohol` (optional): Minimum alcohol percentage (0-100)
- `max_alcohol` (optional): Maximum alcohol percentage (0-100)
- `country` (optional): Filter by country of origin
- `limit` (optional): Number of results (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `format` (optional): Response format - 'markdown' or 'json' (default: 'markdown')

**Example:**
```json
{
  "category": "Öl",
  "country": "Sverige",
  "max_price": 50,
  "limit": 10
}
```

### systembolaget_get_product

Get detailed information about a specific product.

**Parameters:**
- `product_number` (required): The product number (artikelnummer)
- `format` (optional): Response format - 'markdown' or 'json' (default: 'markdown')

**Example:**
```json
{
  "product_number": "12345"
}
```

### systembolaget_search_stores

Search for stores by name or location.

**Parameters:**
- `query` (optional): Search query for store name or location
- `city` (optional): Filter by city
- `limit` (optional): Number of results (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `format` (optional): Response format - 'markdown' or 'json' (default: 'markdown')

**Example:**
```json
{
  "city": "Stockholm",
  "limit": 5
}
```

### systembolaget_get_store

Get detailed information about a specific store.

**Parameters:**
- `store_id` (required): The store ID (site ID)
- `format` (optional): Response format - 'markdown' or 'json' (default: 'markdown')

**Example:**
```json
{
  "store_id": "0123"
}
```

## Development

### Running Tests

**With uv:**
```bash
uv run pytest
```

**With pip/venv:**
```bash
pytest
```

### Code Formatting

**With uv:**
```bash
uv run black systembolaget_mcp.py
```

**With pip/venv:**
```bash
black systembolaget_mcp.py
```

### Type Checking

**With uv:**
```bash
uv run mypy systembolaget_mcp.py
```

**With pip/venv:**
```bash
mypy systembolaget_mcp.py
```

### Linting

**With uv:**
```bash
uv run ruff check systembolaget_mcp.py
```

**With pip/venv:**
```bash
ruff check systembolaget_mcp.py
```

### Adding Dependencies

**With uv:**
```bash
uv add <package-name>
# For dev dependencies:
uv add --dev <package-name>
```

**With pip:**
```bash
# Edit pyproject.toml manually, then:
pip install -e ".[dev]"
```

## API Key Extraction

This MCP server **automatically extracts the API key** from Systembolaget's website - no manual configuration needed!

### How it works

The server uses the same technique as [AlexGustafsson/systembolaget-api](https://github.com/AlexGustafsson/systembolaget-api):

1. Fetches Systembolaget's main website
2. Extracts the Next.js app bundle path from the HTML
3. Downloads the app bundle JavaScript file
4. Extracts the `NEXT_PUBLIC_API_KEY_APIM` value
5. Caches the key for subsequent requests

This approach works because Systembolaget's public website uses the same API key in their frontend code.

### Manual Configuration (Optional)

If you prefer to use a custom API key or if automatic extraction fails:

1. Visit [api-portal.systembolaget.se](https://api-portal.systembolaget.se/)
2. Create an account and subscribe to the APIs
3. Copy your API key
4. Set it as an environment variable: `SYSTEMBOLAGET_API_KEY=your-key`

The server will use your custom key instead of extracting one automatically.

## Architecture

The server is built using:
- **FastMCP**: Anthropic's Python SDK for building MCP servers
- **Pydantic v2**: For input validation and schema generation
- **httpx**: For async HTTP requests
- **Type hints**: Full type safety throughout

### Design Principles

- **Agent-centric design**: Tools are designed for complete workflows, not just API wrappers
- **Automatic API key extraction**: No manual configuration required - keys are extracted automatically
- **Error handling**: Comprehensive error handling with actionable messages
- **Pagination**: All list operations support pagination to manage large result sets
- **Format flexibility**: Both human-readable (Markdown) and machine-readable (JSON) outputs
- **Character limits**: Responses are truncated to prevent overwhelming context windows
- **Caching**: API keys are cached to minimize overhead

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [Anthropic](https://www.anthropic.com/) for the MCP SDK
- [Systembolaget](https://www.systembolaget.se/) for their API
- [AlexGustafsson/systembolaget-api](https://github.com/AlexGustafsson/systembolaget-api) for API reference

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [MCP documentation](https://modelcontextprotocol.io/)
- Review the [Systembolaget API documentation](https://api-portal.systembolaget.se/)
