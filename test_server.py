#!/usr/bin/env python3
"""Test script for Systembolaget MCP server.

This script demonstrates how to call the MCP server tools directly
without going through the JSON-RPC protocol.
"""

import asyncio
from systembolaget_mcp import (
    search_products,
    get_product,
    search_stores,
    get_store,
    SearchProductsInput,
    GetProductInput,
    SearchStoresInput,
    GetStoreInput,
)


async def test_search_products():
    """Test searching for Swedish beers under 50 SEK."""
    print("=" * 80)
    print("Test 1: Search for Swedish beers under 50 SEK")
    print("=" * 80)

    params = SearchProductsInput(
        query="öl",
        country="Sverige",
        max_price=50.0,
        limit=5
    )

    result = await search_products(params)
    print(result)
    print("\n")


async def test_search_stores():
    """Test searching for stores in Stockholm."""
    print("=" * 80)
    print("Test 2: Search for stores in Stockholm")
    print("=" * 80)

    params = SearchStoresInput(
        city="Stockholm",
        limit=3
    )

    result = await search_stores(params)
    print(result)
    print("\n")


async def test_get_product():
    """Test getting a specific product (example product number)."""
    print("=" * 80)
    print("Test 3: Get product details (example)")
    print("=" * 80)

    params = GetProductInput(
        product_number="1"  # You'd need a real product number
    )

    result = await get_product(params)
    print(result)
    print("\n")


async def main():
    """Run all tests."""
    print("\n🧪 Testing Systembolaget MCP Server\n")

    try:
        await test_search_products()
    except Exception as e:
        print(f"❌ Test 1 failed: {e}\n")

    try:
        await test_search_stores()
    except Exception as e:
        print(f"❌ Test 2 failed: {e}\n")

    # Uncomment to test specific product lookup
    # try:
    #     await test_get_product()
    # except Exception as e:
    #     print(f"❌ Test 3 failed: {e}\n")

    print("✅ Testing complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
