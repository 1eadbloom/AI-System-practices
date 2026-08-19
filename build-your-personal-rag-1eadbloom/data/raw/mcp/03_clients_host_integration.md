# MCP Clients and Host Integration

While servers expose capabilities, the client side of MCP is responsible for connecting to one or more servers, performing capability discovery, and making those capabilities available to whatever AI application (the "host") embeds it.

## Connecting with the Python SDK

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="python", args=["weather_server.py"])

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_forecast", {"city": "Taipei"})
```

The `initialize()` call performs the protocol handshake described in the architecture overview: the client and server exchange supported protocol versions and declared capabilities before any further requests are made.

## Discovery calls

After initialization, a client typically calls:

- `list_tools()` — returns every tool the server exposes, with its name, description, and JSON Schema for arguments.
- `list_resources()` — returns static resources and resource templates the server exposes.
- `list_prompts()` — returns available prompt templates.

Hosts generally re-run discovery whenever a new server connects, and well-behaved servers send a `notifications/tools/list_changed` (or the resource/prompt equivalent) message if their available capabilities change at runtime, so a long-lived client connection doesn't serve a stale capability list.

## Converting MCP tools into a model's native tool-calling format

Because different model providers expose slightly different function-calling schemas, a host typically has an adapter layer that converts the JSON Schema from `list_tools()` into whatever shape the underlying LLM API expects (for example, Anthropic's `tools` parameter or OpenAI's `tools`/`functions` parameter). When the model returns a tool call, the host's adapter routes it back to `session.call_tool(name, arguments)` against the correct MCP client connection, then formats the MCP tool result back into the message format the model expects for a tool result turn.

## Multiple servers, one host

A realistic AI application connects to several MCP servers at once — e.g., a filesystem server, a GitHub server, and a custom internal-tools server — each via its own `ClientSession`. The host is responsible for namespacing tool names if two servers happen to expose tools with the same name, aggregating the combined tool list for the model, and routing each tool call to the correct underlying client session based on which server originally advertised that tool.

## Sampling: servers calling back into the model

A more advanced MCP capability, called "sampling," lets a server request that the *client's* LLM generate a completion on the server's behalf, rather than the server needing its own separate model access or API key. This is useful for servers that want to do some lightweight reasoning (e.g., summarizing a large result before returning it) without bundling their own model integration. Because this gives a server influence over what gets sent to the user's LLM, clients are expected to support a human-in-the-loop review step before forwarding a sampling request, rather than honoring it silently.

## Roots: scoping a server's view of the filesystem

For filesystem-oriented servers, the client can declare "roots" — a set of directories the server is allowed to operate within — during initialization. This lets a host scope a generic filesystem server down to just the user's current project directory, for instance, rather than the server assuming it has access to the entire machine.

## Security considerations for client implementers

Because tool calls and resource reads can return arbitrary content from a server, and that content becomes part of the model's context, host implementations need to treat server output as untrusted input — content from a resource or tool result should not be treated as instructions to silently execute additional tool calls, since a compromised or malicious server could otherwise attempt prompt-injection style attacks through tool outputs. Many hosts surface a confirmation step for higher-risk tool categories (such as ones that can write files or send network requests) instead of auto-approving every tool call the model proposes.
