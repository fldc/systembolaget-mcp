# MCP Best Practices

Best practices för att bygga Model Context Protocol (MCP) servrar baserat på Anthropic's riktlinjer och lärdomar från Systembolaget MCP-projektet.

## Design-principer

### 1. Agent-centrerad design

**Gör INTE:**
- Bara wrappa API-endpoints direkt
- Skapa ett verktyg per API-endpoint
- Returnera råa API-svar utan bearbetning

**Gör ISTÄLLET:**
- Designa verktyg för kompletta arbetsflöden
- Kombinera flera API-anrop när det är meningsfullt
- Bearbeta och formatera data för optimal användning
- Tänk på vad en AI-agent verkligen behöver för att lösa uppgifter

**Exempel:**
```python
# Dåligt: Bara en API wrapper
@mcp.tool()
async def get_product_raw(product_id: str):
    return await api.get(f"/products/{product_id}")

# Bra: Workflow-orienterat verktyg
@mcp.tool()
async def search_products(params: SearchInput) -> str:
    """Search products with filters and return formatted results."""
    # Hämta data
    data = await api.search(params)

    # Bearbeta och formatera
    formatted = format_results(data)

    # Lägg till pagination-info och nästa steg
    if has_more:
        formatted += "\nUse offset: X to see more"

    return formatted
```

### 2. Namngivning

**Server-namn:**
- Python: `{service}_mcp` (t.ex. `systembolaget_mcp`)
- Node/TypeScript: `{service}-mcp-server`
- Använd snake_case för Python, kebab-case för TypeScript
- Ingen versionsinformation i namnet

**Verktygsnamn:**
- Format: `{service}_{action}_{resource}`
- Exempel: `systembolaget_search_products`, `github_create_issue`
- Börja med verb: get, list, search, create, update, delete
- Använd snake_case
- Inkludera service-prefix för att undvika konflikter

**Beskrivningar:**
- Var specifik och tydlig
- Matcha exakt vad verktyget gör
- Ingen generisk text som "handles everything"

### 3. Input-validering

**Använd Pydantic v2:**
```python
from pydantic import BaseModel, Field, field_validator, ConfigDict

class SearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Optional[str] = Field(
        None,
        description="Search query for product name"
    )
    min_price: Optional[float] = Field(
        None,
        ge=0,
        description="Minimum price in SEK"
    )

    @field_validator('max_price')
    @classmethod
    def validate_max_price(cls, v, info):
        if v is not None and info.data.get('min_price') is not None:
            if v < info.data['min_price']:
                raise ValueError("max_price must be >= min_price")
        return v
```

**Nyckelpunkter:**
- Använd `model_config = ConfigDict(...)` istället för `class Config`
- Använd `field_validator` istället för deprecated `validator`
- Använd `model_dump()` istället för `dict()`
- Lägg till beskrivningar på alla fält
- Validera constraints (min/max värden, regex patterns)

### 4. Response-formatering

**Stöd både Markdown och JSON:**
```python
format: Literal["markdown", "json"] = Field(
    "markdown",
    description="Response format: 'markdown' for human-readable or 'json' for structured data"
)
```

**Markdown (för människor):**
- Använd headers (###) för struktur
- Använd listor för enkel läsning
- Visa namn OCH ID:n (t.ex. "Nybrogatan 47 (0104)")
- Formatera timestamps till läsbart format
- Skippa onödig metadata

**JSON (för programmatisk användning):**
- Returnera komplett, strukturerad data
- Inkludera all metadata
- Behåll original-strukturen från API:et
- Inkludera pagination-info

### 5. Pagination

**Implementera alltid pagination för listor:**
```python
limit: int = Field(
    DEFAULT_PAGE_SIZE,  # 20
    ge=1,
    le=MAX_PAGE_SIZE,   # 100
    description="Number of results to return"
)
offset: int = Field(
    0,
    ge=0,
    description="Number of results to skip"
)
```

**Returnera pagination-metadata:**
```python
{
    'results': [...],
    'pagination': {
        'limit': 20,
        'offset': 0,
        'total_count': 85,
        'has_more': True,
        'next_offset': 20
    }
}
```

**I Markdown:**
```markdown
Found 85 results (showing 20)

...results...

---
**More results available.** Use `offset: 20` to see the next page.
```

### 6. Character Limits

**Förhindra context overflow:**
```python
CHARACTER_LIMIT = 25000

def truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    if len(content) <= limit:
        return content

    truncated = content[:limit]
    return f"{truncated}\n\n... [Response truncated. Try filtering results to see more details]"
```

**Använd alltid truncation:**
- På alla responses som kan bli stora
- Ge tydlig indikation om trunkering
- Ge råd om hur man filtrerar/begränsar resultat

### 7. Tool Annotations

**Använd korrekt annotations:**
```python
@mcp.tool(
    name="systembolaget_search_products",
    annotations={
        "readOnlyHint": True,      # Endast läsning
        "destructiveHint": False,  # Ändrar inte data
        "idempotentHint": True,    # Samma resultat varje gång
        "openWorldHint": False     # Kräver specifika inputs
    }
)
```

**Guideline:**
- `readOnlyHint`: True för alla GET/search operations
- `destructiveHint`: True för DELETE operations
- `idempotentHint`: True om samma anrop ger samma resultat
- `openWorldHint`: True om verktyget kan hantera öppna queries

## Tekniska Best Practices

### 8. API-nyckel hantering

**Automatisk extraktion (när möjligt):**
```python
_cached_api_key: Optional[str] = None

async def extract_api_key() -> str:
    global _cached_api_key

    # Cacha nyckel
    if _cached_api_key:
        return _cached_api_key

    # Miljövariabel som override
    env_key = os.getenv('SYSTEMBOLAGET_API_KEY')
    if env_key:
        _cached_api_key = env_key
        return env_key

    # Extrahera automatiskt
    key = await auto_extract_key()
    _cached_api_key = key
    return key
```

**Fördelar:**
- Ingen manuell konfiguration krävs
- Fallback till miljövariabel
- Cachad för performance
- Automatiska uppdateringar om nyckel ändras

### 9. Felhantering

**Centraliserad error handler:**
```python
async def make_api_request(url: str, params: dict, headers: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                raise APIError("Resource not found")
            elif response.status_code == 403:
                raise APIError("Access forbidden. Check API key")
            elif response.status_code == 429:
                raise APIError("Rate limit exceeded. Try again later")
            elif response.status_code >= 500:
                raise APIError("API is currently unavailable")
            elif response.status_code != 200:
                raise APIError(f"Request failed with status {response.status_code}")

            return response.json()
    except httpx.TimeoutException:
        raise APIError("Request timed out. Please try again")
    except httpx.RequestError as e:
        raise APIError(f"Network error: {str(e)}")
```

**I verktyg:**
```python
try:
    result = await do_work()
    return result
except APIError as e:
    return f"Error: {str(e)}"
except Exception as e:
    return f"Unexpected error: {str(e)}"
```

**Viktigt:**
- Använd tydliga, handlingsbara felmeddelanden
- Avslöja INTE interna detaljer eller stack traces
- Ge nästa steg ("Check API key", "Try again later")
- Logga detaljerade fel till stderr, inte till användaren

### 10. Async/Await

**Alla I/O-operationer ska vara async:**
```python
# Korrekt
@mcp.tool()
async def search_products(params: SearchInput) -> str:
    api_key = await extract_api_key()
    data = await make_api_request(url, params, headers)
    return format_results(data)

# Fel - blockerar event loop
@mcp.tool()
async def search_products(params: SearchInput) -> str:
    api_key = extract_api_key()  # BLOCKING!
    return format_results(api_key)
```

### 11. Code Composability

**Dela upp i återanvändbara funktioner:**
```python
# Formaterings-helpers
def format_product_markdown(product: dict) -> str:
    ...

def format_store_markdown(store: dict) -> str:
    ...

# API-helpers
async def make_api_request(...) -> dict:
    ...

async def extract_api_key() -> str:
    ...

# Använd i verktyg
@mcp.tool()
async def search_products(params: SearchInput) -> str:
    api_key = await extract_api_key()
    data = await make_api_request(...)

    results = ""
    for product in data['products']:
        results += format_product_markdown(product)

    return results
```

**Fördelar:**
- DRY (Don't Repeat Yourself)
- Enklare testning
- Bättre underhåll
- Konsistent formatering

### 12. Dependencies

**pyproject.toml struktur:**
```toml
[project]
name = "service-mcp"
version = "0.1.0"
description = "MCP server for Service API"
requires-python = ">=3.10"
dependencies = [
    "mcp>=0.9.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]
```

**Använd uv för pakethantering:**
```bash
# Installation
uv sync

# Lägg till dependencies
uv add httpx

# Dev dependencies
uv add --dev pytest
```

## Testing

### 13. Test-strategi

**Skapa direkt test-script:**
```python
#!/usr/bin/env python3
"""Test script for MCP server."""

import asyncio
from your_mcp import search_products, SearchInput

async def test_search():
    params = SearchInput(
        query="test",
        limit=5
    )
    result = await search_products(params)
    print(result)

if __name__ == "__main__":
    asyncio.run(test_search())
```

**Fördelar:**
- Snabbare än JSON-RPC testing
- Lättare att debugga
- Kan köras direkt: `uv run test_server.py`

### 14. Testing Documentation

**Skapa TESTING.md:**
```markdown
# Testing

## Quick Test
uv run test_server.py

## With Claude Desktop
Add to config:
{
  "mcpServers": {
    "service": {
      "command": "uv",
      "args": ["--directory", "/path", "run", "server.py"]
    }
  }
}

## Common Issues
- JSON-RPC errors: Use test_server.py instead
- API key errors: Check TESTING.md for solutions
```

### 15. Dokumentation

**README struktur:**
1. Kort beskrivning
2. Features (verktyg-lista)
3. Installation (uv först, sedan pip)
4. Usage (Claude Desktop config)
5. Tool Reference (alla verktyg dokumenterade)
6. API Key handling (om relevant)
7. Development
8. Contributing

**Varje verktyg ska ha:**
- Beskrivning av vad det gör
- Lista över parametrar med typer
- Exempel på användning
- Eventuella begränsningar

## Säkerhet

### 16. Credential Handling

**Aldrig:**
- Hårdkoda API-nycklar
- Committa `.env` filer
- Logga känslig information
- Exponera nycklar i felmeddelanden

**Alltid:**
- Använd miljövariabler
- Lägg till `.env` i `.gitignore`
- Tillhandahåll `.env.example`
- Cacha credentials säkert

### 17. Input Sanitization

**Validera all input:**
```python
# File paths
import os.path

def validate_path(path: str) -> str:
    # Förhindra path traversal
    if ".." in path:
        raise ValueError("Invalid path")
    return os.path.normpath(path)

# SQL/Commands
# Använd parametriserade queries
# Använd subprocess med shell=False
```

## Performance

### 18. Caching

**Cacha dyra operationer:**
```python
# API keys
_cached_api_key: Optional[str] = None

# Data som ändras sällan
_cached_metadata: Optional[dict] = None
_cache_timestamp: Optional[float] = None
CACHE_TTL = 3600  # 1 timme

async def get_metadata() -> dict:
    global _cached_metadata, _cache_timestamp

    now = time.time()
    if _cached_metadata and _cache_timestamp:
        if now - _cache_timestamp < CACHE_TTL:
            return _cached_metadata

    _cached_metadata = await fetch_metadata()
    _cache_timestamp = now
    return _cached_metadata
```

### 19. Timeouts

**Sätt rimliga timeouts:**
```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

**Guideline:**
- Normal API-anrop: 10-30s
- File uploads: 60-120s
- Long-running: Överväg background tasks

## Projektstruktur

### 20. Filstruktur

**Enkel server (single file):**
```
service-mcp/
├── .python-version
├── pyproject.toml
├── uv.lock
├── service_mcp.py          # Main server
├── test_server.py          # Test script
├── README.md
├── TESTING.md
├── evaluations.xml
├── .env.example
└── .gitignore
```

**Komplex server (multi-file):**
```
service-mcp/
├── src/
│   └── service_mcp/
│       ├── __init__.py
│       ├── server.py       # MCP tools
│       ├── api.py          # API client
│       ├── models.py       # Pydantic models
│       └── formatters.py   # Response formatters
├── tests/
│   ├── test_server.py
│   └── test_api.py
├── .python-version
├── pyproject.toml
├── uv.lock
├── README.md
└── TESTING.md
```

## Deployment

### 21. Claude Desktop Integration

**Optimal config:**
```json
{
  "mcpServers": {
    "service": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/service-mcp",
        "run",
        "service_mcp.py"
      ],
      "env": {
        "API_KEY": "optional-override"
      }
    }
  }
}
```

**Fördelar med uv:**
- Automatisk virtual environment
- Snabb installation
- Reproducerbara builds
- Ingen separat venv-setup

### 22. Error Reporting

**Logga till stderr, inte stdout:**
```python
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # VIKTIGT: stderr, inte stdout
)

logger = logging.getLogger(__name__)

# I kod
logger.info("API key extracted successfully")
logger.error(f"Failed to fetch data: {error}")
```

**Varför stderr?**
- MCP använder stdout för JSON-RPC
- Logging till stdout förstör protokollet
- stderr syns i Claude Desktop logs

## Evaluations

### 23. Skapa bra evaluations

**10 komplexa, realistiska frågor:**
```xml
<evaluations>
    <evaluation>
        <question>Find all Swedish craft beers under 40 SEK. How many results and what are the top 3 based on taste profiles?</question>
        <answer>Tests:
        1. Use search_products with filters
        2. Parse results to count
        3. Analyze taste profiles
        4. Provide recommendations
        Expected: search_products with filters</answer>
    </evaluation>
</evaluations>
```

**Krav:**
- Kräver flera tool calls
- Realistiska use cases
- Verifierbara svar
- Stabila resultat
- Read-only operations

## Sammanfattning

### De 5 viktigaste principerna:

1. **Agent-first design** - Bygg för AI-agents, inte bara API wrappers
2. **Robust error handling** - Tydliga, handlingsbara felmeddelanden
3. **Proper pagination** - Hantera stora dataset korrekt
4. **Input validation** - Använd Pydantic v2 för all validation
5. **Testing infrastructure** - Gör det lätt att testa och debugga

### Vanliga misstag att undvika:

1. Skapa ett verktyg per API endpoint
2. Returnera råa API-svar utan formatering
3. Glömma pagination och character limits
4. Hårdkoda credentials
5. Logga till stdout istället för stderr
6. Sakna proper error handling
7. Ingen test-infrastructure
8. Blockande I/O operationer
9. Dåliga felmeddelanden
10. Saknad dokumentation

## Referenser

- [MCP Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Anthropic MCP Builder Guide](https://github.com/anthropics/skills/tree/main/mcp-builder)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/)
- [uv Package Manager](https://github.com/astral-sh/uv)
