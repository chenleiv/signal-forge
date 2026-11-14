"""Security headers on every HTTP response: API, SPA, static files and error
responses (401, 403, 404, 413, 429), since this runs outside every other
middleware and exception handler.

The SPA gets a Content-Security-Policy that allows no inline scripts. Its
external origins are exactly what the frontend uses: Google Fonts
(styles.scss) and the world map data on cdn.jsdelivr.net (threat-map.ts).
Styles need 'unsafe-inline' because Angular injects component styles at
runtime. JSON routes get a policy that allows nothing at all.
"""
from __future__ import annotations

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SPA_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    # 'self' also covers the same-origin wss:// live stream (CSP Level 3).
    "connect-src 'self' https://cdn.jsdelivr.net",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
API_CSP = "default-src 'none'; frame-ancestors 'none'"
HSTS = "max-age=31536000; includeSubDomains"

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

API_PREFIXES = ("/api/", "/auth/", "/health")
# Swagger UI and ReDoc load scripts from a CDN and run inline code. They are
# served only when ENABLE_API_DOCS is on (local development), without a CSP.
DOCS_PATHS = ("/docs", "/redoc")


def is_https(scope: Scope) -> bool:
    """HTTPS directly, or as reported by the proxy in front of the app (Render
    terminates TLS). The proxy's value is the last one in the header. A client
    that fakes it only changes the headers of its own response."""
    if scope.get("scheme") == "https":
        return True
    proto = Headers(scope=scope).get("x-forwarded-proto", "")
    return proto.split(",")[-1].strip().lower() == "https"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        api = path.startswith(API_PREFIXES)
        docs = path.startswith(DOCS_PATHS)
        https = is_https(scope)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in COMMON_HEADERS.items():
                    headers[name] = value
                if not docs:
                    headers["Content-Security-Policy"] = API_CSP if api else SPA_CSP
                if api:
                    # Alert, incident and user data stays out of every cache.
                    headers["Cache-Control"] = "no-store"
                if https:
                    headers["Strict-Transport-Security"] = HSTS
            await send(message)

        await self.app(scope, receive, send_with_headers)
