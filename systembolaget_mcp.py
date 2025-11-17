"""Systembolaget MCP Server

A Model Context Protocol server for interacting with Systembolaget's APIs.
Provides tools for searching products, stores, and retrieving detailed information.
"""

import os
from typing import Optional, Literal
from urllib.parse import urlencode
import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("systembolaget_mcp")

# Constants
CHARACTER_LIMIT = 25000
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# API Configuration
SYSTEMBOLAGET_API_BASE = "https://api-extern.systembolaget.se/sb-api-ecommerce/v1"
SYSTEMBOLAGET_STORE_API = "https://api-portal.systembolaget.se/api/v1"


class APIError(Exception):
    """Custom exception for API errors"""
    pass


async def make_api_request(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None
) -> dict:
    """Make an async HTTP request to Systembolaget API with error handling.

    Args:
        url: The API endpoint URL
        params: Query parameters
        headers: Request headers

    Returns:
        dict: JSON response from API

    Raises:
        APIError: If the request fails
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                raise APIError("Resource not found")
            elif response.status_code == 403:
                raise APIError("Access forbidden. Check API key configuration")
            elif response.status_code == 429:
                raise APIError("Rate limit exceeded. Please try again later")
            elif response.status_code >= 500:
                raise APIError("Systembolaget API is currently unavailable")
            elif response.status_code != 200:
                raise APIError(f"API request failed with status {response.status_code}")

            return response.json()
    except httpx.TimeoutException:
        raise APIError("Request timed out. Please try again")
    except httpx.RequestError as e:
        raise APIError(f"Network error: {str(e)}")


def format_product_markdown(product: dict) -> str:
    """Format a product as markdown for human readability.

    Args:
        product: Product data dictionary

    Returns:
        str: Formatted markdown string
    """
    name = product.get('productNameBold', 'Unknown')
    subtitle = product.get('productNameThin', '')
    price = product.get('price', 'N/A')
    volume = product.get('volume', 'N/A')
    alcohol = product.get('alcoholPercentage', 'N/A')
    product_number = product.get('productNumber', 'N/A')
    category = product.get('categoryLevel1', 'N/A')

    md = f"### {name}"
    if subtitle:
        md += f" - {subtitle}"
    md += f"\n\n"
    md += f"- **Product Number:** {product_number}\n"
    md += f"- **Price:** {price} SEK\n"
    md += f"- **Volume:** {volume} ml\n"
    md += f"- **Alcohol:** {alcohol}%\n"
    md += f"- **Category:** {category}\n"

    # Add additional details if available
    if 'country' in product:
        md += f"- **Country:** {product['country']}\n"
    if 'assortmentText' in product:
        md += f"- **Assortment:** {product['assortmentText']}\n"

    # Taste profile if available
    if any(key in product for key in ['tasteClockBitter', 'tasteClockSweetness', 'tasteClockBody']):
        md += "\n**Taste Profile:**\n"
        if 'tasteClockBitter' in product:
            md += f"- Bitterness: {product['tasteClockBitter']}/12\n"
        if 'tasteClockSweetness' in product:
            md += f"- Sweetness: {product['tasteClockSweetness']}/12\n"
        if 'tasteClockBody' in product:
            md += f"- Body: {product['tasteClockBody']}/12\n"

    return md


def format_store_markdown(store: dict) -> str:
    """Format a store as markdown for human readability.

    Args:
        store: Store data dictionary

    Returns:
        str: Formatted markdown string
    """
    name = store.get('name', 'Unknown')
    store_id = store.get('siteId', 'N/A')
    address = store.get('address', {})

    md = f"### {name}\n\n"
    md += f"- **Store ID:** {store_id}\n"

    if address:
        street = address.get('street', '')
        city = address.get('city', '')
        postal_code = address.get('postalCode', '')
        if street:
            md += f"- **Address:** {street}, {postal_code} {city}\n"

    if 'phone' in store:
        md += f"- **Phone:** {store['phone']}\n"

    # Opening hours if available
    if 'openingHours' in store:
        md += "\n**Opening Hours:**\n"
        for day, hours in store['openingHours'].items():
            md += f"- {day}: {hours}\n"

    return md


def truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    """Truncate content if it exceeds character limit.

    Args:
        content: Content to truncate
        limit: Character limit

    Returns:
        str: Truncated content with indicator if truncated
    """
    if len(content) <= limit:
        return content

    truncated = content[:limit]
    return f"{truncated}\n\n... [Response truncated. Try filtering results to see more details]"


# Input Models

class SearchProductsInput(BaseModel):
    """Input model for searching products."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Optional[str] = Field(
        None,
        description="Search query for product name or description"
    )
    category: Optional[str] = Field(
        None,
        description="Filter by category (e.g., 'Öl', 'Vin', 'Sprit')"
    )
    min_price: Optional[float] = Field(
        None,
        ge=0,
        description="Minimum price in SEK"
    )
    max_price: Optional[float] = Field(
        None,
        ge=0,
        description="Maximum price in SEK"
    )
    min_alcohol: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Minimum alcohol percentage (0-100)"
    )
    max_alcohol: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Maximum alcohol percentage (0-100)"
    )
    country: Optional[str] = Field(
        None,
        description="Filter by country of origin"
    )
    limit: int = Field(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Number of results to return (1-{MAX_PAGE_SIZE})"
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of results to skip for pagination"
    )
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data"
    )

    @field_validator('max_price')
    @classmethod
    def validate_max_price(cls, v, info):
        if v is not None and info.data.get('min_price') is not None:
            if v < info.data['min_price']:
                raise ValueError("max_price must be greater than or equal to min_price")
        return v

    @field_validator('max_alcohol')
    @classmethod
    def validate_max_alcohol(cls, v, info):
        if v is not None and info.data.get('min_alcohol') is not None:
            if v < info.data['min_alcohol']:
                raise ValueError("max_alcohol must be greater than or equal to min_alcohol")
        return v


class GetProductInput(BaseModel):
    """Input model for getting product details."""
    model_config = ConfigDict(str_strip_whitespace=True)

    product_number: str = Field(
        ...,
        description="The product number (artikelnummer) to retrieve"
    )
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data"
    )


class SearchStoresInput(BaseModel):
    """Input model for searching stores."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Optional[str] = Field(
        None,
        description="Search query for store name or location"
    )
    city: Optional[str] = Field(
        None,
        description="Filter by city"
    )
    limit: int = Field(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Number of results to return (1-{MAX_PAGE_SIZE})"
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of results to skip for pagination"
    )
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data"
    )


class GetStoreInput(BaseModel):
    """Input model for getting store details."""
    model_config = ConfigDict(str_strip_whitespace=True)

    store_id: str = Field(
        ...,
        description="The store ID (site ID) to retrieve"
    )
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data"
    )


# MCP Tools

@mcp.tool(
    name="systembolaget_search_products",
    annotations={"readOnlyHint": True}
)
async def search_products(params: SearchProductsInput) -> str:
    """Search for products in Systembolaget's catalog.

    This tool searches Systembolaget's product database with various filters like
    category, price range, alcohol content, and country of origin. Returns detailed
    product information including prices, volumes, and taste profiles.

    Args:
        params: Search parameters including query, filters, and pagination options

    Returns:
        str: Formatted list of matching products with details
    """
    try:
        # Build query parameters
        query_params = {}

        if params.query:
            query_params['searchQuery'] = params.query
        if params.category:
            query_params['category'] = params.category
        if params.min_price is not None:
            query_params['minPrice'] = params.min_price
        if params.max_price is not None:
            query_params['maxPrice'] = params.max_price
        if params.min_alcohol is not None:
            query_params['minAlcohol'] = params.min_alcohol
        if params.max_alcohol is not None:
            query_params['maxAlcohol'] = params.max_alcohol
        if params.country:
            query_params['country'] = params.country

        query_params['page'] = params.offset // params.limit
        query_params['pageSize'] = params.limit

        # Note: This is a simplified implementation. The actual Systembolaget API
        # may require authentication and have different endpoint structure.
        # This serves as a template that can be adapted once API access is configured.

        # For now, return a helpful message about API configuration
        api_key = os.getenv('SYSTEMBOLAGET_API_KEY')
        if not api_key:
            return """⚠️  **API Configuration Required**

To use this tool, you need to configure a Systembolaget API key:

1. Obtain an API key from https://api-portal.systembolaget.se/
2. Set the environment variable: `SYSTEMBOLAGET_API_KEY=your_key_here`

Once configured, this tool will search products with the following parameters:
""" + "\n".join(f"- {k}: {v}" for k, v in query_params.items())

        # Make API request (this is a template - adjust URL and headers as needed)
        headers = {
            'Ocp-Apim-Subscription-Key': api_key
        }

        url = f"{SYSTEMBOLAGET_API_BASE}/productsearch/search"
        data = await make_api_request(url, params=query_params, headers=headers)

        products = data.get('products', [])
        total_count = data.get('metadata', {}).get('totalCount', len(products))

        if params.format == "json":
            import json
            result = {
                'products': products[:params.limit],
                'pagination': {
                    'limit': params.limit,
                    'offset': params.offset,
                    'total_count': total_count,
                    'has_more': params.offset + len(products) < total_count
                }
            }
            return truncate_response(json.dumps(result, indent=2, ensure_ascii=False))

        # Markdown format
        if not products:
            return "No products found matching your criteria."

        result = f"# Product Search Results\n\n"
        result += f"Found {total_count} products (showing {len(products[:params.limit])})\n\n"

        for product in products[:params.limit]:
            result += format_product_markdown(product) + "\n\n"

        # Pagination info
        if params.offset + len(products) < total_count:
            next_offset = params.offset + params.limit
            result += f"\n---\n**More results available.** Use `offset: {next_offset}` to see the next page.\n"

        return truncate_response(result)

    except APIError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool(
    name="systembolaget_get_product",
    annotations={"readOnlyHint": True}
)
async def get_product(params: GetProductInput) -> str:
    """Get detailed information about a specific product.

    Retrieves comprehensive details about a product including price, volume,
    alcohol content, taste profile, food pairings, and availability.

    Args:
        params: Product parameters including product number and format

    Returns:
        str: Detailed product information
    """
    try:
        api_key = os.getenv('SYSTEMBOLAGET_API_KEY')
        if not api_key:
            return """⚠️  **API Configuration Required**

To use this tool, you need to configure a Systembolaget API key:

1. Obtain an API key from https://api-portal.systembolaget.se/
2. Set the environment variable: `SYSTEMBOLAGET_API_KEY=your_key_here`

This tool will retrieve detailed information for product: """ + params.product_number

        headers = {
            'Ocp-Apim-Subscription-Key': api_key
        }

        url = f"{SYSTEMBOLAGET_API_BASE}/product/{params.product_number}"
        product = await make_api_request(url, headers=headers)

        if params.format == "json":
            import json
            return truncate_response(json.dumps(product, indent=2, ensure_ascii=False))

        # Markdown format with full details
        result = format_product_markdown(product)

        # Add extended information
        if 'description' in product:
            result += f"\n**Description:**\n{product['description']}\n"

        if 'taste' in product:
            result += f"\n**Taste:**\n{product['taste']}\n"

        if 'usage' in product:
            result += f"\n**Serving Suggestions:**\n{product['usage']}\n"

        if 'tasteSymbols' in product and product['tasteSymbols']:
            result += f"\n**Food Pairings:**\n"
            for symbol in product['tasteSymbols']:
                result += f"- {symbol}\n"

        return truncate_response(result)

    except APIError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool(
    name="systembolaget_search_stores",
    annotations={"readOnlyHint": True}
)
async def search_stores(params: SearchStoresInput) -> str:
    """Search for Systembolaget stores.

    Find stores by name, location, or city. Returns store information including
    addresses, phone numbers, and opening hours.

    Args:
        params: Search parameters including query, city filter, and pagination

    Returns:
        str: List of matching stores with details
    """
    try:
        api_key = os.getenv('SYSTEMBOLAGET_API_KEY')
        if not api_key:
            return """⚠️  **API Configuration Required**

To use this tool, you need to configure a Systembolaget API key:

1. Obtain an API key from https://api-portal.systembolaget.se/
2. Set the environment variable: `SYSTEMBOLAGET_API_KEY=your_key_here`

This tool will search stores with your specified criteria."""

        headers = {
            'Ocp-Apim-Subscription-Key': api_key
        }

        query_params = {
            'page': params.offset // params.limit,
            'pageSize': params.limit
        }

        if params.query:
            query_params['searchQuery'] = params.query
        if params.city:
            query_params['city'] = params.city

        url = f"{SYSTEMBOLAGET_API_BASE}/site/search"
        data = await make_api_request(url, params=query_params, headers=headers)

        stores = data.get('sites', [])
        total_count = data.get('metadata', {}).get('totalCount', len(stores))

        if params.format == "json":
            import json
            result = {
                'stores': stores[:params.limit],
                'pagination': {
                    'limit': params.limit,
                    'offset': params.offset,
                    'total_count': total_count,
                    'has_more': params.offset + len(stores) < total_count
                }
            }
            return truncate_response(json.dumps(result, indent=2, ensure_ascii=False))

        # Markdown format
        if not stores:
            return "No stores found matching your criteria."

        result = f"# Store Search Results\n\n"
        result += f"Found {total_count} stores (showing {len(stores[:params.limit])})\n\n"

        for store in stores[:params.limit]:
            result += format_store_markdown(store) + "\n\n"

        # Pagination info
        if params.offset + len(stores) < total_count:
            next_offset = params.offset + params.limit
            result += f"\n---\n**More results available.** Use `offset: {next_offset}` to see the next page.\n"

        return truncate_response(result)

    except APIError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


@mcp.tool(
    name="systembolaget_get_store",
    annotations={"readOnlyHint": True}
)
async def get_store(params: GetStoreInput) -> str:
    """Get detailed information about a specific store.

    Retrieves comprehensive details about a store including address, contact
    information, opening hours, and available services.

    Args:
        params: Store parameters including store ID and format

    Returns:
        str: Detailed store information
    """
    try:
        api_key = os.getenv('SYSTEMBOLAGET_API_KEY')
        if not api_key:
            return """⚠️  **API Configuration Required**

To use this tool, you need to configure a Systembolaget API key:

1. Obtain an API key from https://api-portal.systembolaget.se/
2. Set the environment variable: `SYSTEMBOLAGET_API_KEY=your_key_here`

This tool will retrieve detailed information for store: """ + params.store_id

        headers = {
            'Ocp-Apim-Subscription-Key': api_key
        }

        url = f"{SYSTEMBOLAGET_API_BASE}/site/{params.store_id}"
        store = await make_api_request(url, headers=headers)

        if params.format == "json":
            import json
            return truncate_response(json.dumps(store, indent=2, ensure_ascii=False))

        # Markdown format with full details
        result = format_store_markdown(store)

        # Add extended information
        if 'services' in store and store['services']:
            result += f"\n**Services:**\n"
            for service in store['services']:
                result += f"- {service}\n"

        if 'parkingInfo' in store:
            result += f"\n**Parking:** {store['parkingInfo']}\n"

        if 'publicTransport' in store:
            result += f"\n**Public Transport:** {store['publicTransport']}\n"

        return truncate_response(result)

    except APIError as e:
        return f"❌ Error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
