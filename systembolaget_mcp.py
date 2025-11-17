"""Systembolaget MCP Server

A Model Context Protocol server for interacting with Systembolaget's APIs.
Provides tools for searching products, stores, and retrieving detailed information.
"""

import json
import logging
import os
import re
from functools import wraps
from typing import Optional, Literal, Callable, Any
import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("systembolaget_mcp")

# Constants
CHARACTER_LIMIT = 25000
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
API_TIMEOUT = 30.0
API_KEY_CACHE_DURATION = 3600  # 1 hour in seconds

# API Configuration
SYSTEMBOLAGET_API_BASE = "https://api-extern.systembolaget.se/sb-api-ecommerce/v1"
SYSTEMBOLAGET_WEBSITE = "https://www.systembolaget.se"

# Cached API key
_cached_api_key: Optional[str] = None
_api_key_timestamp: Optional[float] = None


class APIError(Exception):
    """Custom exception for API errors"""

    pass


def invalidate_api_key() -> None:
    """Invalidate the cached API key to force re-extraction."""
    global _cached_api_key, _api_key_timestamp
    _cached_api_key = None
    _api_key_timestamp = None
    logger.info("API key cache invalidated")


async def get_app_bundle_path() -> str:
    """Extract the app bundle path from Systembolaget's main website.

    Returns:
        str: Path to the app bundle JavaScript file

    Raises:
        APIError: If unable to fetch or parse the website
    """
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            logger.debug(f"Fetching main website: {SYSTEMBOLAGET_WEBSITE}")
            response = await client.get(SYSTEMBOLAGET_WEBSITE)

            if response.status_code != 200:
                raise APIError(f"Failed to fetch Systembolaget website: {response.status_code}")

            # Extract app bundle path using regex
            # Pattern matches: <script src="/_next/static/chunks/pages/_app-HASH.js">
            pattern = r'<script src="([^"]+_app-[^"]+\.js)"'
            match = re.search(pattern, response.text)

            if not match:
                raise APIError("Could not find app bundle path in website")

            bundle_path = match.group(1)
            logger.debug(f"Found app bundle path: {bundle_path}")
            return bundle_path

    except httpx.RequestError as e:
        raise APIError(f"Network error fetching website: {str(e)}")


async def extract_api_key() -> str:
    """Extract the API key from Systembolaget's app bundle.

    This function fetches the main website, finds the app bundle script,
    and extracts the NEXT_PUBLIC_API_KEY_APIM value. Keys are cached for
    API_KEY_CACHE_DURATION seconds to minimize overhead.

    Returns:
        str: The API key

    Raises:
        APIError: If unable to extract the API key
    """
    import time

    global _cached_api_key, _api_key_timestamp

    # Return cached key if available and not expired
    if _cached_api_key and _api_key_timestamp:
        age = time.time() - _api_key_timestamp
        if age < API_KEY_CACHE_DURATION:
            logger.debug(f"Using cached API key (age: {age:.0f}s)")
            return _cached_api_key
        else:
            logger.info(f"API key cache expired (age: {age:.0f}s), refreshing")

    # Check environment variable first (optional override)
    env_key = os.getenv("SYSTEMBOLAGET_API_KEY")
    if env_key:
        logger.info("Using API key from environment variable")
        _cached_api_key = env_key
        _api_key_timestamp = time.time()
        return env_key

    try:
        logger.info("Extracting API key from website")
        # Get app bundle path
        bundle_path = await get_app_bundle_path()

        # Construct full URL
        if bundle_path.startswith("http"):
            bundle_url = bundle_path
        else:
            bundle_url = f"{SYSTEMBOLAGET_WEBSITE}{bundle_path}"

        # Fetch the app bundle
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            logger.debug(f"Fetching app bundle: {bundle_url}")
            response = await client.get(bundle_url)

            if response.status_code != 200:
                raise APIError(f"Failed to fetch app bundle: {response.status_code}")

            # Extract API key using regex
            # Pattern matches: NEXT_PUBLIC_API_KEY_APIM:"key-value"
            pattern = r'NEXT_PUBLIC_API_KEY_APIM:"([^"]+)"'
            match = re.search(pattern, response.text)

            if not match:
                raise APIError("Could not find API key in app bundle")

            api_key = match.group(1)
            _cached_api_key = api_key
            _api_key_timestamp = time.time()
            logger.info("API key extracted and cached successfully")
            return api_key

    except httpx.RequestError as e:
        raise APIError(f"Network error extracting API key: {str(e)}")


async def make_api_request(
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    retry_on_403: bool = True,
) -> dict[str, Any]:
    """Make an async HTTP request to Systembolaget API with error handling.

    Args:
        url: The API endpoint URL
        params: Query parameters
        headers: Request headers
        retry_on_403: If True, retry once with refreshed API key on 403 error

    Returns:
        dict: JSON response from API

    Raises:
        APIError: If the request fails
    """
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            logger.debug(f"API request: {url}")
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                raise APIError("Resource not found")
            elif response.status_code == 403:
                # API key might be invalid, try refreshing once
                if retry_on_403:
                    logger.warning("Got 403 response, invalidating API key and retrying")
                    invalidate_api_key()
                    # Retry with fresh key - caller needs to provide new headers
                    raise APIError("Access forbidden. API key may be invalid - please retry")
                else:
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


def format_product_markdown(product: dict[str, Any]) -> str:
    """Format a product as markdown for human readability.

    Args:
        product: Product data dictionary

    Returns:
        str: Formatted markdown string
    """
    name = product.get("productNameBold", "Unknown")
    subtitle = product.get("productNameThin", "")
    price = product.get("price", "N/A")
    volume = product.get("volume", "N/A")
    alcohol = product.get("alcoholPercentage", "N/A")
    product_number = product.get("productNumber", "N/A")
    category = product.get("categoryLevel1", "N/A")

    md = f"### {name}"
    if subtitle:
        md += f" - {subtitle}"
    md += "\n\n"
    md += f"- **Product Number:** {product_number}\n"
    md += f"- **Price:** {price} SEK\n"
    md += f"- **Volume:** {volume} ml\n"
    md += f"- **Alcohol:** {alcohol}%\n"
    md += f"- **Category:** {category}\n"

    # Add additional details if available
    if "country" in product:
        md += f"- **Country:** {product['country']}\n"
    if "assortmentText" in product:
        md += f"- **Assortment:** {product['assortmentText']}\n"

    # Taste profile if available
    if any(key in product for key in ["tasteClockBitter", "tasteClockSweetness", "tasteClockBody"]):
        md += "\n**Taste Profile:**\n"
        if "tasteClockBitter" in product:
            md += f"- Bitterness: {product['tasteClockBitter']}/12\n"
        if "tasteClockSweetness" in product:
            md += f"- Sweetness: {product['tasteClockSweetness']}/12\n"
        if "tasteClockBody" in product:
            md += f"- Body: {product['tasteClockBody']}/12\n"

    return md


def format_store_markdown(store: dict[str, Any]) -> str:
    """Format a store as markdown for human readability.

    Args:
        store: Store data dictionary

    Returns:
        str: Formatted markdown string
    """
    name = store.get("displayName", store.get("alias", "Unknown"))
    store_id = store.get("siteId", "N/A")
    street = store.get("streetAddress", "")
    city = store.get("city", "")
    postal_code = store.get("postalCode", "")

    md = f"### {name}\n\n"
    md += f"- **Store ID:** {store_id}\n"

    if street:
        address_parts = [street]
        if postal_code:
            address_parts.append(postal_code)
        if city:
            address_parts.append(city)
        md += f"- **Address:** {' '.join(address_parts)}\n"

    if store.get("isAgent"):
        md += "- **Type:** Agent\n"
    if store.get("isTastingStore"):
        md += "- **Features:** Tasting Store\n"

    # Opening hours - show today's hours
    if "openingHours" in store and len(store["openingHours"]) > 0:
        # Find today's hours (usually second entry is today)
        for day_info in store["openingHours"][:3]:  # Check first few days
            if day_info.get("openFrom") != "00:00:00":
                open_from = day_info.get("openFrom", "")[:5]  # HH:MM
                open_to = day_info.get("openTo", "")[:5]
                md += f"- **Hours:** {open_from} - {open_to}\n"
                break

    if "position" in store:
        lat = store["position"].get("latitude")
        lon = store["position"].get("longitude")
        if lat and lon:
            md += f"- **Location:** {lat:.4f}, {lon:.4f}\n"

    return md


def truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    """Truncate content if it exceeds character limit.

    Truncates at the last complete line before the limit to preserve formatting.

    Args:
        content: Content to truncate
        limit: Character limit

    Returns:
        str: Truncated content with indicator if truncated
    """
    if len(content) <= limit:
        return content

    # Try to truncate at last complete line to preserve formatting
    truncate_point = content.rfind("\n", 0, limit)
    if truncate_point > limit * 0.8:  # If we're within 80% of limit
        truncated = content[:truncate_point]
    else:
        # Fall back to simple truncation if no good line break found
        truncated = content[:limit]

    return f"{truncated}\n\n... [Response truncated. Try filtering results to see more details]"


# Input Models


class SearchProductsInput(BaseModel):
    """Input model for searching products."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: Optional[str] = Field(None, description="Search query for product name or description")
    category: Optional[str] = Field(
        None, description="Filter by category (e.g., 'Öl', 'Vin', 'Sprit')"
    )
    min_price: Optional[float] = Field(None, ge=0, description="Minimum price in SEK")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price in SEK")
    min_alcohol: Optional[float] = Field(
        None, ge=0, le=100, description="Minimum alcohol percentage (0-100)"
    )
    max_alcohol: Optional[float] = Field(
        None, ge=0, le=100, description="Maximum alcohol percentage (0-100)"
    )
    country: Optional[str] = Field(None, description="Filter by country of origin")
    limit: int = Field(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Number of results to return (1-{MAX_PAGE_SIZE})",
    )
    offset: int = Field(0, ge=0, description="Number of results to skip for pagination")
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data",
    )

    @field_validator("max_price")
    @classmethod
    def validate_max_price(cls, v, info):
        if v is not None and info.data.get("min_price") is not None:
            if v < info.data["min_price"]:
                raise ValueError("max_price must be greater than or equal to min_price")
        return v

    @field_validator("max_alcohol")
    @classmethod
    def validate_max_alcohol(cls, v, info):
        if v is not None and info.data.get("min_alcohol") is not None:
            if v < info.data["min_alcohol"]:
                raise ValueError("max_alcohol must be greater than or equal to min_alcohol")
        return v


class GetProductInput(BaseModel):
    """Input model for getting product details."""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_number: str = Field(..., description="The product number (artikelnummer) to retrieve")
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data",
    )


class SearchStoresInput(BaseModel):
    """Input model for searching stores."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: Optional[str] = Field(None, description="Search query for store name or location")
    city: Optional[str] = Field(None, description="Filter by city")
    limit: int = Field(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Number of results to return (1-{MAX_PAGE_SIZE})",
    )
    offset: int = Field(0, ge=0, description="Number of results to skip for pagination")
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data",
    )


class GetStoreInput(BaseModel):
    """Input model for getting store details."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_id: str = Field(..., description="The store ID (site ID) to retrieve")
    format: Literal["markdown", "json"] = Field(
        "markdown",
        description="Response format: 'markdown' for human-readable or 'json' for structured data",
    )


# Error handling decorator


def handle_tool_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle errors consistently across all tool functions.

    Args:
        func: The async tool function to wrap

    Returns:
        Wrapped function with error handling
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await func(*args, **kwargs)  # type: ignore[no-any-return]
        except APIError as e:
            logger.error(f"API error in {func.__name__}: {str(e)}")
            return f"Error: {str(e)}"
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}")
            return f"Unexpected error: {str(e)}"

    return wrapper  # type: ignore[return-value]


# MCP Tools


@mcp.tool(name="systembolaget_search_products", annotations={"readOnlyHint": True})
@handle_tool_errors
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
    logger.info(f"Searching products: query={params.query}, category={params.category}")

    # Get API key (automatically extracted from website)
    api_key = await extract_api_key()

    # Build query parameters
    query_params: dict[str, Any] = {}

    if params.query:
        query_params["searchQuery"] = params.query
    if params.category:
        query_params["category"] = params.category
    if params.min_price is not None:
        query_params["minPrice"] = params.min_price
    if params.max_price is not None:
        query_params["maxPrice"] = params.max_price
    if params.min_alcohol is not None:
        query_params["minAlcohol"] = params.min_alcohol
    if params.max_alcohol is not None:
        query_params["maxAlcohol"] = params.max_alcohol
    if params.country:
        query_params["country"] = params.country

    # Note: API uses page-based pagination. We convert offset to page number.
    # For best results, use offset values that are multiples of limit.
    page = params.offset // params.limit
    query_params["page"] = page
    query_params["pageSize"] = params.limit

    # Make API request
    headers = {"Ocp-Apim-Subscription-Key": api_key}

    url = f"{SYSTEMBOLAGET_API_BASE}/productsearch/search"
    data = await make_api_request(url, params=query_params, headers=headers)

    products = data.get("products", [])
    total_count = data.get("metadata", {}).get("totalCount", len(products))

    logger.info(f"Found {total_count} products, returning {len(products)}")

    if params.format == "json":
        result = {
            "products": products,
            "pagination": {
                "limit": params.limit,
                "offset": params.offset,
                "total_count": total_count,
                "returned_count": len(products),
                "has_more": params.offset + len(products) < total_count,
            },
        }
        return truncate_response(json.dumps(result, indent=2, ensure_ascii=False))

    # Markdown format
    if not products:
        return "No products found matching your criteria."

    result = "# Product Search Results\n\n"
    result += f"Found {total_count} products (showing {len(products)})\n\n"

    for product in products:
        result += format_product_markdown(product) + "\n\n"

    # Pagination info
    if params.offset + len(products) < total_count:
        next_offset = params.offset + params.limit
        result += f"\n---\n**More results available.** Use `offset: {next_offset}` to see the next page.\n"

    return truncate_response(result)


@mcp.tool(name="systembolaget_get_product", annotations={"readOnlyHint": True})
@handle_tool_errors
async def get_product(params: GetProductInput) -> str:
    """Get detailed information about a specific product.

    Retrieves comprehensive details about a product including price, volume,
    alcohol content, taste profile, food pairings, and availability.

    Args:
        params: Product parameters including product number and format

    Returns:
        str: Detailed product information
    """
    logger.info(f"Getting product: {params.product_number}")

    # Get API key (automatically extracted from website)
    api_key = await extract_api_key()

    headers = {"Ocp-Apim-Subscription-Key": api_key}

    url = f"{SYSTEMBOLAGET_API_BASE}/product/{params.product_number}"
    product = await make_api_request(url, headers=headers)

    if params.format == "json":
        return truncate_response(json.dumps(product, indent=2, ensure_ascii=False))

    # Markdown format with full details
    result = format_product_markdown(product)

    # Add extended information
    if "description" in product:
        result += f"\n**Description:**\n{product['description']}\n"

    if "taste" in product:
        result += f"\n**Taste:**\n{product['taste']}\n"

    if "usage" in product:
        result += f"\n**Serving Suggestions:**\n{product['usage']}\n"

    if "tasteSymbols" in product and product["tasteSymbols"]:
        result += "\n**Food Pairings:**\n"
        for symbol in product["tasteSymbols"]:
            result += f"- {symbol}\n"

    return truncate_response(result)


@mcp.tool(name="systembolaget_search_stores", annotations={"readOnlyHint": True})
@handle_tool_errors
async def search_stores(params: SearchStoresInput) -> str:
    """Search for Systembolaget stores.

    Find stores by name, location, or city. Returns store information including
    addresses, phone numbers, and opening hours.

    Note: The API returns all matching stores, so pagination is applied client-side.
    This means all results are fetched from the API even when using pagination.

    Args:
        params: Search parameters including query, city filter, and pagination

    Returns:
        str: List of matching stores with details
    """
    logger.info(f"Searching stores: query={params.query}, city={params.city}")

    # Get API key (automatically extracted from website)
    api_key = await extract_api_key()

    headers = {"Ocp-Apim-Subscription-Key": api_key, "Origin": "https://www.systembolaget.se"}

    query_params: dict[str, Any] = {"includePredictions": "true"}

    # Combine query and city into single search term
    search_terms = []
    if params.query:
        search_terms.append(params.query)
    if params.city:
        search_terms.append(params.city)

    if search_terms:
        query_params["q"] = " ".join(search_terms)

    url = f"{SYSTEMBOLAGET_API_BASE}/sitesearch/site"
    data = await make_api_request(url, params=query_params, headers=headers)

    stores = data.get("siteSearchResults", [])

    # Note: API doesn't support pagination parameters, so we fetch all results
    # and paginate client-side. For large result sets, consider using more specific queries.
    total_count = len(stores)
    paginated_stores = stores[params.offset : params.offset + params.limit]

    logger.info(f"Found {total_count} stores, returning {len(paginated_stores)}")

    if params.format == "json":
        result = {
            "stores": paginated_stores,
            "pagination": {
                "limit": params.limit,
                "offset": params.offset,
                "total_count": total_count,
                "returned_count": len(paginated_stores),
                "has_more": params.offset + params.limit < total_count,
            },
        }
        return truncate_response(json.dumps(result, indent=2, ensure_ascii=False))

    # Markdown format
    if not paginated_stores:
        return "No stores found matching your criteria."

    result = "# Store Search Results\n\n"
    result += f"Found {total_count} stores (showing {len(paginated_stores)})\n\n"

    for store in paginated_stores:
        result += format_store_markdown(store) + "\n\n"

    # Pagination info
    if params.offset + params.limit < total_count:
        next_offset = params.offset + params.limit
        result += f"\n---\n**More results available.** Use `offset: {next_offset}` to see the next page.\n"

    return truncate_response(result)


# Note: Individual store lookup endpoint not available in current API.
# The endpoint /site/{store_id} returns 404 errors.
# Keeping function for potential future use if endpoint becomes available.
# To enable, uncomment the @mcp.tool decorator below.
#
# @mcp.tool(
#     name="systembolaget_get_store",
#     annotations={"readOnlyHint": True}
# )
@handle_tool_errors
async def get_store(params: GetStoreInput) -> str:
    """Get detailed information about a specific store.

    Retrieves comprehensive details about a store including address, contact
    information, opening hours, and available services.

    Note: This endpoint is currently not available in the API and will return
    a 404 error. Use search_stores instead.

    Args:
        params: Store parameters including store ID and format

    Returns:
        str: Detailed store information
    """
    logger.info(f"Getting store: {params.store_id}")

    # Get API key (automatically extracted from website)
    api_key = await extract_api_key()

    headers = {"Ocp-Apim-Subscription-Key": api_key}

    url = f"{SYSTEMBOLAGET_API_BASE}/site/{params.store_id}"
    store = await make_api_request(url, headers=headers)

    if params.format == "json":
        return truncate_response(json.dumps(store, indent=2, ensure_ascii=False))

    # Markdown format with full details
    result = format_store_markdown(store)

    # Add extended information
    if "services" in store and store["services"]:
        result += "\n**Services:**\n"
        for service in store["services"]:
            result += f"- {service}\n"

    if "parkingInfo" in store:
        result += f"\n**Parking:** {store['parkingInfo']}\n"

    if "publicTransport" in store:
        result += f"\n**Public Transport:** {store['publicTransport']}\n"

    return truncate_response(result)


def main() -> None:
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
