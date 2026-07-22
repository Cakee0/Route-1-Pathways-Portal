"""
utils/ratelimit.py — minimal in-memory, per-IP rate limiting (audit S3).

Pure ASGI middleware, no external dependencies. Only the abuse-prone
endpoints are limited: credential stuffing / bot signups on /auth/*, spam on
POST /messages. Everything else passes through untouched.

State lives in process memory, which is correct for the single-process
uvicorn deployment; if the app ever runs multiple workers the effective
limit becomes (limit × workers) — still a hard ceiling per IP.
"""

import json
import time

# (method, path) → (max requests, window in seconds) per client IP
DEFAULT_RULES = {
    ("POST", "/auth/login"):           (10, 300),   # brute force / stuffing
    ("POST", "/auth/register"):        (10, 3600),  # mass bot signups
    ("POST", "/auth/google"):          (20, 300),
    ("POST", "/auth/google/complete"): (10, 3600),
    ("POST", "/messages"):             (20, 60),    # messaging spam
    ("POST", "/profiles/me/avatar"):   (10, 3600),  # image processing + S3 cost
}

_SWEEP_INTERVAL = 600   # seconds between purges of idle IPs
_MAX_WINDOW     = 3600  # longest window above; sweep keeps nothing older


class RateLimitMiddleware:
    def __init__(self, app, rules=None):
        self.app = app
        self.rules = rules if rules is not None else DEFAULT_RULES
        self._hits: dict = {}   # (path, ip) → [monotonic timestamps]
        self._last_sweep = time.monotonic()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if len(path) > 1:
            path = path.rstrip("/")
        rule = self.rules.get((scope["method"], path))
        if rule is None:
            await self.app(scope, receive, send)
            return

        limit, window = rule
        now = time.monotonic()
        key = (path, self._client_ip(scope))
        hits = [t for t in self._hits.get(key, ()) if t > now - window]

        if len(hits) >= limit:
            self._hits[key] = hits
            retry_after = max(1, int(hits[0] + window - now) + 1)
            await self._reject(send, retry_after)
            return

        hits.append(now)
        self._hits[key] = hits
        self._maybe_sweep(now)
        await self.app(scope, receive, send)

    @staticmethod
    def _client_ip(scope) -> str:
        # Behind Caddy the peer address is 127.0.0.1; the real client is the
        # LAST entry of X-Forwarded-For — the one our proxy appended. (Caddy
        # strips client-supplied XFF unless trusted_proxies is configured, so
        # the last entry cannot be spoofed. The first entry can be.)
        for name, value in scope.get("headers", ()):
            if name == b"x-forwarded-for":
                return value.decode("latin-1").split(",")[-1].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    def _maybe_sweep(self, now: float) -> None:
        if now - self._last_sweep < _SWEEP_INTERVAL:
            return
        self._last_sweep = now
        cutoff = now - _MAX_WINDOW
        for key in list(self._hits):
            kept = [t for t in self._hits[key] if t > cutoff]
            if kept:
                self._hits[key] = kept
            else:
                del self._hits[key]

    @staticmethod
    async def _reject(send, retry_after: int) -> None:
        body = json.dumps(
            {"detail": f"Too many requests. Please wait {retry_after} seconds and try again."}
        ).encode()
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"retry-after", str(retry_after).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
