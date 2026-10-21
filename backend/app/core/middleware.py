"""
Security headers and request body limit middlewares.
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from app.core.config import settings

MAX_BODY_BYTES = 1024 * 1024  # 1 MB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard HTTP security headers into every response.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self)"

        if settings.ENV.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces a strict 1 MB body size limit on incoming requests to prevent DoS/memory exhaustion.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "detail": f"Request body exceeds 1 MB limit (size: {length} bytes)",
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)
