"""
LUMINA API Middleware

Architectural Intent:
- Cross-cutting concerns handled before/after request processing
- TenantMiddleware enforces multi-tenancy via X-Tenant-ID header
- RequestLoggingMiddleware provides structured request/response logging
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("lumina.api")


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant_id from X-Tenant-ID header and attach to request state.

    Public endpoints (health check, docs) bypass tenant validation.
    All other endpoints require a valid X-Tenant-ID header.
    """

    EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id or not tenant_id.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "X-Tenant-ID header is required",
                    "error_type": "validation_error",
                },
            )

        request.state.tenant_id = tenant_id.strip()
        return await call_next(request)


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
