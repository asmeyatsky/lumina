"""
Authentication & Authorisation REST API Routes

Architectural Intent:
- Thin HTTP adapter for the AuthService application-layer use cases
- Public endpoints (register, login, refresh) do not require auth
- Protected endpoints use JWT bearer authentication
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from lumina.infrastructure.auth.dependencies import get_current_user, require_role
from lumina.infrastructure.auth.rbac import Role
from lumina.infrastructure.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class InviteMemberRequest(BaseModel):
    email: str
    role: str = Field(..., pattern="^(owner|admin|member|viewer)$")


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    permissions: list[str] = Field(default_factory=list)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan_tier: str
    is_active: bool


class InvitationResponse(BaseModel):
    tenant_id: str
    email: str
    role: str


class APIKeyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    raw_key: str
    permissions: list[str]


class MeResponse(BaseModel):
    user_id: str
    email: str
    name: str
    tenants: list[dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_auth_service(request: Request) -> AuthService:
    """Retrieve the ``AuthService`` from application state."""
    service = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service not available",
        )
    return service


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, request: Request) -> UserResponse:
    """Register a new user account."""
    service = _get_auth_service(request)
    try:
        user = service.register_user(body.email, body.password, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate and receive access + refresh tokens."""
    service = _get_auth_service(request)
    try:
        tokens = service.login(body.email, body.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request) -> TokenResponse:
    """Exchange a refresh token for a new token pair."""
    service = _get_auth_service(request)
    try:
        tokens = service.refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


# ---------------------------------------------------------------------------
# Protected endpoints
# ---------------------------------------------------------------------------

@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: CreateTenantRequest,
    request: Request,
    user: Annotated[dict, Depends(get_current_user)],
) -> TenantResponse:
    """Create a new tenant (organisation).  The authenticated user becomes the owner."""
    service = _get_auth_service(request)
    try:
        tenant = service.create_tenant(body.name, user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan_tier=tenant.plan_tier,
        is_active=tenant.is_active,
    )


@router.post(
    "/tenants/{tenant_id}/members",
    response_model=InvitationResponse,
    status_code=201,
)
async def invite_member(
    tenant_id: str,
    body: InviteMemberRequest,
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.ADMIN))],
) -> InvitationResponse:
    """Invite a new member to the tenant.  Requires at least ADMIN role."""
    service = _get_auth_service(request)
    try:
        invitation = service.invite_member(tenant_id, body.email, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return InvitationResponse(
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
    )


@router.post(
    "/tenants/{tenant_id}/api-keys",
    response_model=APIKeyResponse,
    status_code=201,
)
async def create_api_key(
    tenant_id: str,
    body: CreateAPIKeyRequest,
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.ADMIN))],
) -> APIKeyResponse:
    """Generate an API key for the tenant.  Requires at least ADMIN role."""
    service = _get_auth_service(request)
    try:
        key = service.create_api_key(tenant_id, body.name, body.permissions)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return APIKeyResponse(
        id=key.id,
        tenant_id=key.tenant_id,
        name=key.name,
        raw_key=key.raw_key,
        permissions=key.permissions,
    )


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    user: Annotated[dict, Depends(get_current_user)],
) -> MeResponse:
    """Return profile information for the authenticated user."""
    service = _get_auth_service(request)
    user_dto = service.get_user(user["user_id"])
    if user_dto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    tenants = service.get_memberships_for_user(user["user_id"])
    return MeResponse(
        user_id=user_dto.id,
        email=user_dto.email,
        name=user_dto.name,
        tenants=tenants,
    )
