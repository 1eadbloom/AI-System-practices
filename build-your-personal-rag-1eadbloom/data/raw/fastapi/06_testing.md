# Testing FastAPI Applications

FastAPI applications are tested with `TestClient` (built on `httpx`), which lets you call path operations directly in a test process without actually starting a network server, while still exercising the full request/response cycle including middleware, dependency injection, and validation.

## Basic test setup

```python
from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)

def test_read_item():
    response = client.get("/items/42")
    assert response.status_code == 200
    assert response.json() == {"item_id": 42, "q": None}
```

`TestClient` exposes the same interface as a typical `requests`/`httpx`-style HTTP client (`.get`, `.post`, `.put`, etc.), but routes calls directly into the ASGI application in-process, which makes tests fast and avoids needing a running server or open network port.

## Overriding dependencies for tests

Rather than hitting a real database or calling a real authentication provider during tests, `app.dependency_overrides` lets you substitute any dependency with a test double:

```python
def fake_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = fake_get_db

def test_create_item():
    response = client.post("/items/", json={"name": "Widget", "price": 9.99})
    assert response.status_code == 200
```

This works because `app.dependency_overrides` is a dictionary keyed by the *original* dependency function; FastAPI checks this dictionary before calling the real dependency, and if a matching override exists, calls the override instead — transparently, with no changes needed to the path operation code under test. It's standard practice to clear or reset `app.dependency_overrides` between test modules (or use a pytest fixture for this) so that overrides from one test file don't leak into another.

## Testing authenticated endpoints

The most common pattern is overriding the `get_current_user` dependency directly, rather than going through a real login flow in every test:

```python
def fake_current_user():
    return User(id=1, username="testuser")

app.dependency_overrides[get_current_user] = fake_current_user

def test_protected_route():
    response = client.get("/users/me")
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
```

For tests that specifically want to verify the *real* authentication flow end-to-end (not just downstream behavior assuming a valid user), you instead call the actual `/token` login endpoint, extract the returned access token, and pass it as a real `Authorization: Bearer ...` header on subsequent requests, without overriding `get_current_user`.

## Testing async path operations

`TestClient` handles both `async def` and plain `def` path operations transparently — your test functions themselves can remain ordinary synchronous `def test_...` functions even when testing fully async endpoints, since `TestClient` manages running the underlying event loop internally. For projects that prefer writing async test functions directly (e.g., using `pytest-asyncio`), `httpx.AsyncClient` configured with an ASGI transport pointed at the app provides an equivalent async-native testing interface.

## Testing validation errors

Because validation is automatic, testing it mostly means asserting on the 422 response shape for intentionally bad input:

```python
def test_invalid_item():
    response = client.post("/items/", json={"name": "Widget"})  # missing required "price"
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "price"]
```

## Test database isolation

For tests that touch a database, a common pattern is pointing `get_db`'s override at a separate test database (often SQLite in-memory, or a dedicated test schema in the same database engine used in production), and wrapping each test in a transaction that's rolled back afterward, or recreating tables between test runs — keeping test data isolated from both production data and from other tests running in the same suite.
