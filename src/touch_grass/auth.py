"""Optional bearer-token auth for the MCP HTTP endpoint, plus the run helper.

These endpoints drive a real keyboard and mouse — effectively "remote control
this machine" — so we refuse to bind to a non-loopback host without either a
token or an explicit unsafe opt-in.
"""

from __future__ import annotations

import hmac

from .config import Config


class BearerAuthMiddleware:
    """ASGI middleware enforcing ``Authorization: Bearer <token>`` on every request."""

    def __init__(self, app, token: str):
        self.app = app
        self._expected = f"Bearer {token}"

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"authorization", b"").decode("latin-1")
        if not hmac.compare_digest(provided, self._expected):
            await _send_401(send)
            return
        await self.app(scope, receive, send)


async def _send_401(send) -> None:
    body = b'{"error":"unauthorized"}'
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", b"application/json"),
            (b"www-authenticate", b"Bearer"),
        ],
    })
    await send({"type": "http.response.body", "body": body})


def auth_policy_error(cfg: Config) -> str | None:
    """Return an error message if the server must NOT start, else None."""
    if cfg.auth_token or cfg.host_is_loopback or cfg.unsafe_no_auth:
        return None
    return (
        f"Refusing to bind to non-loopback host '{cfg.host}' with no auth — these "
        "endpoints control a real keyboard/mouse. Set TOUCH_GRASS_AUTH_TOKEN=<secret> "
        "(clients send 'Authorization: Bearer <secret>'), or set "
        "TOUCH_GRASS_UNSAFE_NO_AUTH=1 for a trusted private network."
    )


def run_server(mcp, cfg: Config) -> None:
    """Start the FastMCP server, adding bearer auth when a token is configured."""
    err = auth_policy_error(cfg)
    if err:
        raise SystemExit(err)

    mcp.settings.host = cfg.host
    mcp.settings.port = cfg.port

    if cfg.auth_token:
        import uvicorn

        app = mcp.streamable_http_app()
        app.add_middleware(BearerAuthMiddleware, token=cfg.auth_token)
        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    else:
        mcp.run(transport="streamable-http")
