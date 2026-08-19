# FastAPI Middleware, Error Handling, and Application Lifespan

## Middleware

Middleware in FastAPI (inherited from Starlette) wraps every request and response passing through the application, useful for cross-cutting concerns that apply uniformly regardless of which specific route handled the request — logging, timing, adding security headers, or request ID tagging.

```python
import time
from fastapi import Request

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start_time)
    return response
```

A middleware function receives the incoming request and a `call_next` callable representing "the rest of the application" (the next middleware in the stack, eventually reaching the actual path operation). It can inspect or modify the request before calling `call_next`, and inspect or modify the response after. Multiple middleware functions stack, executing in the reverse order they were added for the "before" portion and in registration order for the "after" portion — similar to how nested context managers unwind.

## Exception handlers

Rather than handling every possible error inline in every path operation, FastAPI lets you register a single handler for a given exception type, applied across the whole application:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

class ItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id

@app.exception_handler(ItemNotFoundError)
def item_not_found_handler(request: Request, exc: ItemNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Item {exc.item_id} not found"},
    )
```

Any path operation can now simply `raise ItemNotFoundError(item_id=42)` and the handler above produces a consistent, well-formatted response — this centralizes error-response formatting instead of repeating `HTTPException` calls with identical shapes throughout the codebase, and is particularly useful for translating domain-specific exceptions raised deep inside business logic (which may have no direct knowledge of HTTP at all) into proper HTTP responses at the API boundary.

## Overriding the default validation error handler

FastAPI's default response for a Pydantic validation failure is a structured 422 response listing every failing field. This default can be overridden globally via `@app.exception_handler(RequestValidationError)` if an application wants a different error response shape (for example, to match an existing company-wide API error format).

## Application lifespan (startup and shutdown)

Resources that should be initialized once when the application starts (a database connection pool, a loaded ML model, a cache client) and cleanly released when it shuts down are managed with the `lifespan` context manager, which replaced the older separate `@app.on_event("startup")` / `@app.on_event("shutdown")` decorators:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.db_pool = await create_db_pool()
    yield
    # shutdown
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)
```

Code before `yield` runs once at startup, before the application begins accepting requests; code after `yield` runs once at shutdown. Storing the resulting resources on `app.state` makes them accessible from path operations and dependencies via the `Request` object (`request.app.state.db_pool`) without relying on global module-level variables.

## Why centralize this instead of handling it per-route

The common thread across middleware, exception handlers, and lifespan management is the same architectural idea as dependency injection: concerns that apply broadly across an application should be declared once, in one place, rather than copy-pasted into every individual path operation. This keeps individual route functions focused on their specific business logic, while cross-cutting behavior (timing, error formatting, resource lifecycle) lives in dedicated, independently testable application-level constructs.
