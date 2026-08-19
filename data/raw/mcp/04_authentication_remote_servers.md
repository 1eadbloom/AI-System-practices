# MCP Authentication and Remote Servers

Local stdio-based MCP servers run as a subprocess under the same user account as the host, so there is no separate authentication step — the operating system's process permissions are the security boundary. Remote, network-accessible MCP servers are a different story: they need a real authentication and authorization model, since they may be shared across many users or organizations.

## OAuth 2.1 as the standard

Current versions of the MCP specification define an authorization flow for HTTP-based (Streamable HTTP) servers built on OAuth 2.1, with the MCP server acting as an OAuth resource server (and often also as its own authorization server, or delegating to a third-party identity provider). The general flow:

1. The client attempts to connect to the remote server without credentials.
2. The server responds with metadata pointing the client to its OAuth authorization endpoint (discovered via a well-known metadata document, similar to OpenID Connect discovery).
3. The client performs a standard OAuth authorization-code flow (with PKCE) to obtain an access token, typically involving a browser redirect for the user to log in and grant consent.
4. The client includes the resulting access token as a Bearer token on subsequent MCP requests to the server.

## Dynamic client registration

Because MCP clients may connect to servers operated by parties they have no pre-existing relationship with, the spec supports OAuth's dynamic client registration extension, letting a client register itself with a new authorization server programmatically the first time it connects, rather than requiring a developer to manually pre-register every client/server pair in advance.

## Token scoping

A well-implemented remote MCP server should issue access tokens scoped only to the specific capabilities a given client/user actually needs, following the principle of least privilege — for instance, a token that only allows read access to resources, without permission to invoke write-capable tools, for an integration that genuinely only needs read access.

## Why local servers don't need this

It's worth being explicit about why stdio servers are exempt from the OAuth flow: a stdio server is launched directly by the host application as a child process and communicates only over local pipes that no other process or user can intercept. The trust boundary is "whatever already has permission to run code as this user," which is the same trust boundary the host application itself operates under — there is no separate network-reachable surface to protect.

## Practical deployment patterns for remote servers

- **Single-tenant internal server**: a company runs one MCP server instance behind its existing SSO/identity provider, and only employees with valid company credentials can connect. OAuth here is mostly about reusing existing identity infrastructure rather than defending against the open internet.
- **Multi-tenant SaaS-hosted server**: a vendor runs one MCP server that many different customer organizations connect to, where the access token must also carry enough information (or be looked up against enough server-side state) to determine which tenant's data a given request should operate against — this is functionally similar to how a normal multi-tenant REST API authenticates and scopes requests, just expressed through MCP's tool/resource model instead of REST endpoints.
- **Public, low-trust server**: a server exposing a non-sensitive public API (e.g., public weather data) may choose to skip authentication entirely and rely on simple rate limiting instead, since there is no user-specific data to protect.

## Transport security

Beyond OAuth-based authorization, Streamable HTTP servers should be served over TLS (HTTPS) in any non-local deployment, exactly as would be expected of any other HTTP API handling potentially sensitive tool arguments and results.
