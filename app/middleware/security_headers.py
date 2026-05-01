"""
Security response headers — applied to every response.

CSP notes:
- 'unsafe-inline' is required: index.html has a large inline <script> block.
  Nonce-based CSP would eliminate this but requires server-side template rendering.
- frame-ancestors allows Telegram origins so the Mini App works in Telegram WebView.
  Admin paths use 'none' (no framing needed).
- HSTS max-age = 2 years (63072000 s) — only set on HTTPS, which Railway guarantees.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_HSTS = "max-age=63072000; includeSubDomains; preload"

# Telegram Mini App requires telegram.org for SDK + Google Fonts for typography
_CSP_APP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://telegram.org; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self'; "
    "frame-ancestors 'self' https://telegram.org https://web.telegram.org; "
    "base-uri 'self'; "
    "form-action 'self';"
)

# Admin panel: deny all framing
_CSP_ADMIN = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        is_admin = request.url.path.startswith("/admin")

        response.headers["Strict-Transport-Security"] = _HSTS
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]        = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"]   = _CSP_ADMIN if is_admin else _CSP_APP

        if is_admin:
            # Belt-and-suspenders for older browsers that don't support CSP frame-ancestors
            response.headers["X-Frame-Options"] = "DENY"

        # Remove server fingerprint injected by uvicorn/starlette
        response.headers.pop("server", None)

        return response
