"""Request body size limit: 413 for any body over MAX_BODY_BYTES.

Checked up front from Content-Length, then while the body is read, for
chunked requests that send no Content-Length (or a false one). The body is
read here, at most MAX_BODY_BYTES of it, and handed to the app in one piece.
The 413 is answered directly, without relying on how the framework handles
errors raised while a route reads its body. The largest real body (a rule
with its conditions) is well under 2 KB.
"""
from __future__ import annotations
import json

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 64 * 1024
_BODY_413 = json.dumps({"detail": "Request body too large"}).encode()


async def _send_413(send: Send) -> None:
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-type", b"application/json"),
                    (b"content-length", str(len(_BODY_413)).encode())],
    })
    await send({"type": "http.response.body", "body": _BODY_413})


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        length = Headers(scope=scope).get("content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            await _send_413(send)
            return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return  # the client left: nobody to answer
            body = message.get("body", b"")
            size += len(body)
            if size > self.max_bytes:
                await _send_413(send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()  # later calls wait for the disconnect, as usual

        await self.app(scope, replay, send)
