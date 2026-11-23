"""Test-only ASGI app for test_proxy_headers_uvicorn.py: echoes what uvicorn
put into the scope. Never imported by the real app.

`app` routes like main.py without backend/static (redirect_slashes=False, no
SPA catch-all), so it works whether or not the frontend was built. Under
/default-slashes, the same route with FastAPI's default redirect_slashes, to
show where its redirect would point."""
from __future__ import annotations

from fastapi import FastAPI, Request


def _echo(request: Request) -> dict:
    client = request.scope.get("client")
    return {"client": list(client) if client else None, "scheme": request.scope.get("scheme")}


app = FastAPI(redirect_slashes=False)
default_slashes = FastAPI()


@app.get("/api/echo")
async def echo(request: Request):
    return _echo(request)


@default_slashes.get("/api/echo")
async def echo_default(request: Request):
    return _echo(request)


app.mount("/default-slashes", default_slashes)
