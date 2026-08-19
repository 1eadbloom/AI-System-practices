# FastAPI Core Concepts: Path Operations and Pydantic Models

FastAPI is a Python web framework for building APIs, built on top of Starlette (for the actual ASGI web handling) and Pydantic (for data validation and serialization). Its central selling points are automatic request validation, automatic interactive API documentation, and first-class support for Python type hints as the mechanism for declaring both.

## Path operations

A "path operation" is FastAPI's term for a function bound to a specific HTTP method and URL path, declared with a decorator:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

Here `item_id` is a path parameter (extracted from the URL itself, and FastAPI automatically validates it must be convertible to `int`, returning a 422 error if a client sends something non-numeric), while `q` is a query parameter (read from `?q=...` in the URL, optional here since it defaults to `None`).

## Pydantic models for request bodies

For anything beyond simple scalar parameters, request bodies are declared as Pydantic models:

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None

@app.post("/items/")
def create_item(item: Item):
    return item
```

FastAPI reads the function's type hint (`item: Item`), recognizes it as a Pydantic model, parses the incoming JSON request body against that model's schema, and either returns a fully validated and type-coerced `Item` instance to your function, or automatically returns a 422 Unprocessable Entity response with a detailed, field-by-field description of what validation failed — without you writing any explicit validation code.

## Response models

You can similarly declare what shape a path operation's response should take with `response_model`, which both validates the outgoing data and — importantly — filters out any extra fields your function might have included that aren't part of the declared response schema, which is a common technique for avoiding accidentally leaking internal fields (like a hashed password) that exist on an internal database model but shouldn't be exposed over the API.

```python
class ItemOut(BaseModel):
    name: str
    price: float

@app.post("/items/", response_model=ItemOut)
def create_item(item: Item) -> ItemOut:
    ...
```

## Automatic interactive documentation

Because every path operation's parameters, request body schema, and response schema are fully described via type hints, FastAPI generates an OpenAPI schema for the entire application automatically, and serves two interactive documentation UIs out of the box at `/docs` (Swagger UI) and `/redoc` (ReDoc) with zero additional configuration — every endpoint, parameter, and model shows up there automatically and stays in sync with the actual code, since the documentation is generated from the same type hints that drive validation.

## Status codes and error handling

Path operations can declare an explicit success status code (`@app.post("/items/", status_code=201)`), and errors are raised as `HTTPException`:

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
def read_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]
```

Raising `HTTPException` anywhere inside a path operation function immediately short-circuits normal execution and returns the specified status code and JSON body (`{"detail": "Item not found"}` in this example) to the client.

## Why type hints matter so much in FastAPI's design

FastAPI deliberately leans on standard Python type hints (rather than a separate, framework-specific validation DSL) for three things simultaneously: editor autocomplete and type checking during development, runtime request/response validation, and automatic documentation generation. This is the core design insight that differentiates it from earlier Python web frameworks, where these three concerns typically required three separate, manually-kept-in-sync mechanisms.
