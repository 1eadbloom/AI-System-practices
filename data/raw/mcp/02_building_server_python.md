# Building an MCP Server with the Python SDK

The official MCP Python SDK provides a high-level framework, `FastMCP`, that lets you expose tools, resources, and prompts with plain Python functions and decorators, without manually handling JSON-RPC framing or transport details.

## Minimal server

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-server")

@mcp.tool()
def get_forecast(city: str, days: int = 3) -> str:
    """Get a multi-day weather forecast for a city."""
    return f"Forecast for {city}: sunny for the next {days} days."

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

`FastMCP` introspects the function's type hints and docstring to automatically generate the JSON Schema describing the tool's parameters, and uses the docstring as the tool's description shown to the model. As with LangGraph tool definitions, writing a clear, specific docstring directly affects how reliably a model chooses to call the tool with correct arguments.

## Exposing resources

Resources are registered with `@mcp.resource(uri_template)`:

```python
@mcp.resource("config://app/settings")
def get_settings() -> str:
    """Return the current application settings as JSON."""
    return json.dumps(load_settings())

@mcp.resource("notes://{note_id}")
def get_note(note_id: str) -> str:
    """Fetch a single note by its ID."""
    return notes_db[note_id]
```

URI templates support path parameters (like `{note_id}` above), which FastMCP automatically parses out and passes as function arguments when a client requests a matching URI. Static resources (no template parameters) can be listed in full by the client; templated resources are typically discovered dynamically based on application context.

## Exposing prompts

```python
@mcp.prompt()
def code_review_prompt(language: str, code: str) -> str:
    """Generate a code review prompt for the given snippet."""
    return f"Please review this {language} code for bugs and style issues:\n\n{code}"
```

Prompts registered this way typically appear in a host application's UI as a selectable template (for example, a slash command), letting users explicitly invoke a server-defined prompt rather than relying on the model to decide to do so.

## Async tools and long-running work

Tool functions can be defined as `async def` for I/O-bound work (database queries, outbound HTTP calls), and FastMCP awaits them transparently:

```python
@mcp.tool()
async def fetch_url(url: str) -> str:
    """Fetch the contents of a URL."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        return resp.text
```

## Returning structured content

Tools are not limited to plain strings. A tool can return text, images, or embedded resource content, and as of more recent SDK versions, can also declare a structured output schema so that responses are validated and returned as typed JSON rather than free text, which downstream code in the host application can parse reliably instead of needing to re-parse natural-language output.

## Error handling

Raising a Python exception inside a tool function is automatically converted by FastMCP into an MCP-level tool error response, which the host surfaces back to the model as a failed tool call rather than crashing the server process. This lets the model see the error message and potentially retry with corrected arguments, which is generally more useful than the server going silent or the host losing the whole connection over one bad call.

## Running the server

For local development and for hosts that spawn the server as a subprocess, `mcp.run(transport="stdio")` is the standard choice. For a server meant to be reached over a network, `mcp.run(transport="streamable-http")` runs an HTTP server (FastMCP builds on Starlette/Uvicorn under the hood for this transport) that remote clients can connect to.

## Testing locally with the MCP Inspector

The MCP Inspector is a standalone developer tool (run via `npx @modelcontextprotocol/inspector`) that connects to a server the same way a real host would, but provides a manual UI for listing and invoking tools, browsing resources, and trying prompts — letting you validate a server's behavior interactively before wiring it into an actual AI application.
