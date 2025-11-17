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
- A Systembolaget API key from [api-portal.systembolaget.se](https://api-portal.systembolaget.se/)

### Setup

1. Clone this repository:
```bash
git clone https://github.com/yourusername/systembolaget-mcp.git
cd systembolaget-mcp
```

2. Install dependencies:
```bash
pip install -e .
```

Or install development dependencies:
```bash
pip install -e ".[dev]"
```

3. Configure your API key:
```bash
export SYSTEMBOLAGET_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```bash
SYSTEMBOLAGET_API_KEY=your-api-key-here
```

## Usage

### Running the Server

#### With Claude Desktop

Add this configuration to your Claude Desktop config file:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "systembolaget": {
      "command": "python",
      "args": ["/absolute/path/to/systembolaget-mcp/systembolaget_mcp.py"],
      "env": {
        "SYSTEMBOLAGET_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Standalone Testing

Run the server directly:
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

```bash
pytest
```

### Code Formatting

```bash
black systembolaget_mcp.py
```

### Type Checking

```bash
mypy systembolaget_mcp.py
```

### Linting

```bash
ruff systembolaget_mcp.py
```

## API Configuration

This MCP server requires a Systembolaget API key. To obtain one:

1. Visit [api-portal.systembolaget.se](https://api-portal.systembolaget.se/)
2. Create an account or sign in
3. Subscribe to the necessary APIs
4. Copy your API key
5. Set it as an environment variable: `SYSTEMBOLAGET_API_KEY`

## Architecture

The server is built using:
- **FastMCP**: Anthropic's Python SDK for building MCP servers
- **Pydantic v2**: For input validation and schema generation
- **httpx**: For async HTTP requests
- **Type hints**: Full type safety throughout

### Design Principles

- **Agent-centric design**: Tools are designed for complete workflows, not just API wrappers
- **Error handling**: Comprehensive error handling with actionable messages
- **Pagination**: All list operations support pagination to manage large result sets
- **Format flexibility**: Both human-readable (Markdown) and machine-readable (JSON) outputs
- **Character limits**: Responses are truncated to prevent overwhelming context windows

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
