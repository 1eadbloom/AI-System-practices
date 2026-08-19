# FastAPI Authentication and Security

FastAPI provides a `fastapi.security` module with building blocks for common authentication schemes, designed to integrate naturally with the dependency injection system rather than as separate middleware.

## OAuth2 with Password flow and JWT bearer tokens

The most common pattern for a typical API with username/password login is OAuth2's "password" flow combined with JSON Web Tokens (JWT) for subsequent authenticated requests:

```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_jwt_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_jwt_token(token)  # raises if invalid/expired
    user = get_user(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user

@app.get("/users/me")
def read_current_user(current_user=Depends(get_current_user)):
    return current_user
```

`OAuth2PasswordBearer` is itself a dependency that knows how to extract a Bearer token from the `Authorization` header and will automatically raise a 401 if the header is missing — it does *not* validate the token's contents itself, that's the job of `get_current_user`, which decodes and verifies the JWT (checking signature and expiry) and looks up the corresponding user. Because `get_current_user` is just a normal dependency, it can be reused with `Depends(get_current_user)` on every protected route, and `app.dependency_overrides` makes it trivial to substitute a fake authenticated user during tests.

## Password hashing

Passwords should never be stored in plaintext. The standard pattern uses `passlib` (commonly with the `bcrypt` scheme) to hash passwords at signup and verify them at login:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

## API key authentication

For simpler service-to-service authentication (no per-user login flow), FastAPI supports API key extraction from a header, query parameter, or cookie via `APIKeyHeader`, `APIKeyQuery`, or `APIKeyCookie`, used as a dependency the same way as the bearer-token pattern above.

## CORS

Browser-based frontends calling a FastAPI backend from a different origin need Cross-Origin Resource Sharing configured, typically via Starlette's `CORSMiddleware`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myfrontend.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Using `allow_origins=["*"]` in combination with `allow_credentials=True` is invalid per the CORS specification and most browsers will reject it — if credentials (cookies, auth headers) need to flow cross-origin, the allowed origins list must be an explicit, finite set rather than a wildcard.

## Scopes and fine-grained permissions

`OAuth2PasswordBearer` and related security classes support declaring OAuth2 "scopes," letting different endpoints require different permission levels from the same authenticated user (e.g., a `read:items` scope versus an `admin` scope), with FastAPI automatically documenting which scopes each endpoint requires in the generated OpenAPI schema, and raising a 403 if a presented token's scopes don't satisfy what the endpoint declares as required.

## Why this all flows through Depends

The unifying design choice is that every authentication mechanism in FastAPI is ultimately just another dependency — there's no separate "auth middleware" concept layered on top of the rest of the framework. This means authentication requirements compose naturally with everything else dependencies can do: caching within a request, easy overriding in tests, and automatic appearance in the interactive `/docs` UI (which even includes an "Authorize" button wired up to whichever security scheme the app declares).
