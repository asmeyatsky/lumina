"""
LUMINA FastAPI Application

Architectural Intent:
- Composition root for the REST API layer
- CORS, error handling, middleware, and router registration
- Lifespan handler for startup/shutdown of shared resources
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lumina.shared.domain.errors import (
    AuthorizationError,
    DomainError,
    EntityNotFoundError,
    ValidationError,
)

from lumina.presentation.api.middleware import RequestLoggingMiddleware, TenantMiddleware
from lumina.presentation.api import (
    auth_routes,
    beam_routes,
    graph_routes,
    intelligence_routes,
    pulse_routes,
    signal_routes,
)
from lumina.presentation.api.schemas import HealthResponse
from lumina.infrastructure.auth.service import AuthService
from lumina.presentation.config.dependency_injection import Container

logger = logging.getLogger("lumina.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    - On startup: initialise the DI container and attach to app state.
    - On shutdown: clean up resources held by the container.
    """
    container = Container()
    app.state.container = container
    app.state.auth_service = AuthService()
    logger.info("LUMINA API started — container initialised")
    yield
    await container.shutdown()
    logger.info("LUMINA API shutdown — resources released")


def create_app() -> FastAPI:
    """Create and configure the LUMINA FastAPI application."""

    app = FastAPI(
        title="LUMINA - AI Visibility Platform",
        description="Be the answer. Unified API for AI Visibility management.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Custom middleware (order matters: outermost first) ---
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantMiddleware)

    # --- Error handlers ---

    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(
        request: Request, exc: EntityNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.message, "error_type": "entity_not_found"},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": exc.message, "error_type": "authorization_error"},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "error_type": "validation_error"},
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        request: Request, exc: DomainError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message, "error_type": "domain_error"},
        )

    # --- Health check ---

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health_check() -> HealthResponse:
        return HealthResponse(status="healthy", version="1.0.0", service="lumina")

    # --- Module routers ---
    app.include_router(auth_routes.router)
    app.include_router(pulse_routes.router)
    app.include_router(graph_routes.router)
    app.include_router(beam_routes.router)
    app.include_router(signal_routes.router)
    app.include_router(intelligence_routes.router)

    return app
