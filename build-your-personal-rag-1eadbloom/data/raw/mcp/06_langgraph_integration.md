# Using MCP Servers from Agent Frameworks (LangGraph and Others)

MCP is framework-agnostic by design, but in practice a large fraction of MCP's value shows up when it's plugged into an agent orchestration framework like LangGraph, since the framework can then treat MCP-exposed tools exactly like any other tool it knows how to call.

## langchain-mcp-adapters

The `langchain-mcp-adapters` package bridges MCP servers into LangChain's standard tool interface, so that tools exposed by any MCP server can be passed directly into a LangGraph agent (such as one built with `create_react_agent`) alongside regular LangChain tools, with no special-casing required in the agent's own code.

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient({
    "weather": {"command": "python", "args": ["weather_server.py"], "transport": "stdio"},
    "github": {"url": "https://mcp.example.com/github", "transport": "streamable_http"},
})

tools = await client.get_tools()
agent = create_react_agent(model, tools=tools)
```

`MultiServerMCPClient` manages connections to multiple MCP servers at once (mixing local stdio servers and remote HTTP servers in the same client), performs tool discovery against all of them, and converts every discovered MCP tool into a LangChain `Tool` object — meaning the rest of your LangGraph code (the `agent` node, the `ToolNode`, conditional routing) doesn't need to know or care that some of its tools originated from MCP rather than being defined natively in Python.

## Why this combination is powerful

LangGraph provides the orchestration logic — state, control flow, persistence, human-in-the-loop, multi-agent coordination — while MCP provides a standardized, reusable way to plug in *capabilities* without writing custom integration code for each one. A LangGraph supervisor agent, for instance, can dynamically gain access to an entire ecosystem of community-built MCP servers (filesystem access, GitHub, Slack, databases, search APIs) simply by configuring `MultiServerMCPClient` with the relevant server connections, rather than the LangGraph application author writing and maintaining bespoke tool wrappers for each one.

## Resource and prompt support in adapters

Most agent-framework adapters for MCP focus primarily on tools, since tools map most directly onto the "function calling" abstraction frameworks already support. Resources and prompts, being application/user-controlled rather than model-controlled, typically require separate, framework-specific glue code if you want a LangGraph application to let a user pick an MCP resource to attach to a thread's state, or to trigger an MCP prompt template as a starting message — this is a deliberate consequence of MCP's three-way control split (described in the protocol overview), since "let the model autonomously call this" and "let the user explicitly select this" are genuinely different UX flows that can't be collapsed into one adapter function.

## Per-thread vs. global tool configuration

Because LangGraph applications are often multi-tenant or multi-user (different threads representing different users or sessions), a common pattern is to construct a fresh `MultiServerMCPClient` (and therefore fresh tool list) per request or per thread, particularly when different users should have access to different MCP servers — for example, a user-specific GitHub MCP server connection authenticated with that particular user's OAuth token, as opposed to sharing one global set of MCP connections across every user of the application.

## Error propagation

When an MCP tool call fails (the underlying MCP server returns a tool error, or the connection itself fails), the adapter surfaces this as a normal LangChain tool execution error, which flows back into the graph's message state as a `ToolMessage` indicating failure — the same `agent` node that handles successful tool results also sees failures, and can decide (via the LLM's own reasoning, since it now sees the error message) whether to retry, try a different tool, or give up and explain the failure to the user, without any MCP-specific error-handling code needed in the graph itself.
