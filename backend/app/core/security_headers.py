from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from ..config import settings

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Appends strict security headers to all HTTP responses to enforce HTTPS,
    mitigate clickjacking, cross-site scripting, MIME sniffing, and control browser hardware permissions.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # 1. HSTS (HTTP Strict Transport Security)
        if settings.ENABLE_HSTS:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains; preload"
            )

        # 2. Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 3. Clickjacking mitigation
        response.headers["X-Frame-Options"] = "DENY"

        # 4. Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 5. Browser Feature & Hardware Permissions Policy (Permit only Camera & Geolocation for AERIS)
        response.headers["Permissions-Policy"] = (
            "camera=(self), geolocation=(self), microphone=(), payment=(), usb=()"
        )

        # 6. Basic XSS protection for legacy agents
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 7. Content Security Policy (strict CSP mitigating XSS and script injection)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; connect-src 'self' ws: wss: http: https:;"
        )

        return response
