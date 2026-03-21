"""
LUMINA API Middleware

Architectural Intent:
- Cross-cutting concerns handled before/after request processing
- TenantMiddleware enforces multi-tenancy via JWT token (with X-Tenant-ID fallback)
- RequestLoggingMiddleware provides structured request/response logging
"""

from __future__ import annotations

import logging
import time
from typing import Callable

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("lumina.api")


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant_id from JWT token or X-Tenant-ID header and attach to request state.

    Public endpoints (health check, docs, auth endpoints) bypass tenant
    validation.  For all other endpoints the middleware first attempts to read
    the tenant from the JWT ``Authorization: Bearer`` token.  If no JWT is
    present it falls back to the ``X-Tenant-ID`` header for backwards
    compatibility.
    """

    EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})
    EXEMPT_PREFIXES = ("/api/v1/auth/",)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip auth for exempt exact paths
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip auth for exempt prefixes (auth endpoints)
        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Attempt to extract tenant_id from JWT bearer token
        tenant_id = self._extract_tenant_from_jwt(request)

        # Fall back to X-Tenant-ID header
        if not tenant_id:
            tenant_id_header = request.headers.get("X-Tenant-ID")
            if tenant_id_header and tenant_id_header.strip():
                tenant_id = tenant_id_header.strip()

        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "X-Tenant-ID header is required",
                    "error_type": "validation_error",
                },
            )

        request.state.tenant_id = tenant_id
        return await call_next(request)

    @staticmethod
    def _extract_tenant_from_jwt(request: Request) -> str | None:
        """Try to decode the bearer token and return the tenant_id claim."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        try:
            import os
            secret = os.environ.get("JWT_SECRET", "lumina-dev-secret-change-me")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload.get("tenant_id") or None
        except Exception:
            return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request method, path, response status, and latency for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path

        response = await call_next(request)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "request_completed method=%s path=%s status=%d latency_ms=%.1f",
            method,
            path,
            response.status_code,
            latency_ms,
        )

        return response
