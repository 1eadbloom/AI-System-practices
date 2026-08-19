# FastAPI Dependency Injection

FastAPI's dependency injection ("Depends") system is one of its most distinctive features: it lets you declare shared logic — database connections, authentication checks, pagination parameters, rate limiting — as plain functions that FastAPI automatically calls and injects into any path operation that needs them.

## Basic usage

```python
from fastapi import Depends

def get_query_params(skip: int = 0, limit: int = 100):
    return {"skip": skip, "limit": limit}

@app.get("/items/")
def list_items(params: dict = Depends(get_query_params)):
    return fetch_items(**params)
```

`Depends(get_query_params)` tells FastAPI: before calling `list_items`, first call `get_query_params` (itself treated exactly like a path operation function — it can have its own query parameters, defaults, and even its own dependencies), and pass its return value as the `params` argument. The query parameters `skip` and `limit` are automatically exposed and validated on the *outer* endpoint's documentation too, even though they're declared on the dependency function rather than directly on `list_items`.

## Class-based dependencies

A dependency can also be a class, which is convenient when several related parameters should travel together:

```python
class Pagination:
    def __init__(self, skip: int = 0, limit: int = 100):
        self.skip = skip
        self.limit = limit

@app.get("/items/")
def list_items(pagination: Pagination = Depends()):
    return fetch_items(pagination.skip, pagination.limit)
```

## Dependencies with yield (setup/teardown)

A very common pattern is a dependency that needs cleanup logic — most often, a database session that must be closed after the request finishes regardless of whether the path operation succeeded or raised an exception:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/items/")
def list_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

Code before the `yield` runs before the path operation; code after `yield` (in the `finally` block here) runs after the path operation returns, even if it raised an exception — this is the standard way to guarantee a resource is released exactly once per request.

## Sharing dependencies across many routes

Rather than adding `Depends(get_current_user)` to every single protected endpoint individually, dependencies can be declared once at the router or application level:

```python
from fastapi import APIRouter

router = APIRouter(dependencies=[Depends(verify_api_key)])

@router.get("/admin/stats")
def get_stats():
    ...
```

Every route registered on `router` now automatically requires `verify_api_key` to succeed before the route's own code runs, without each individual function needing to repeat the dependency declaration.

## Caching within a single request

By default, if the same dependency function (with the same parameters) is depended on by multiple other dependencies within a single request, FastAPI calls it only once and reuses the cached result for the rest of that request — useful when, say, both an authentication dependency and a logging dependency both need the current user, without doing the lookup twice. This caching can be disabled per-dependency with `Depends(get_db, use_cache=False)` for cases where you genuinely want a fresh call each time.

## Why dependency injection instead of decorators or middleware

Compared to global middleware, `Depends` lets you scope shared logic precisely — to specific routes, specific routers, or the whole app — and lets a dependency itself declare typed parameters that show up correctly in the auto-generated documentation, which a generic middleware function (which only sees the raw request) cannot do as cleanly. Dependencies are also independently testable as ordinary Python functions, and FastAPI's `app.dependency_overrides` dictionary makes it straightforward to swap in test doubles (e.g., a fake `get_db` returning an in-memory database) during automated tests, without changing any application code.
