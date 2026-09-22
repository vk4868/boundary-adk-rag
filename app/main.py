"""FastAPI surface for the governed document assistant."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.audit import AuditWriteError
from app.config import Settings, get_settings
from app.index import IndexUnavailable
from app.models import ChatRequest, ChatResponse, SourceListResponse
from app.service import (
    ChatService,
    ServiceUnavailable,
    SessionOwnershipError,
    UnknownSession,
)
from app.tools import BudgetExceeded


settings = get_settings()
service = ChatService(settings)
app = FastAPI(
    title="ADK Document Research Assistant",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    if request.url.path == "/health" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class HealthResponse(BaseModel):
    status: str
    auth_configured: bool
    model_ready: bool
    model_provider: str
    model: str
    index: dict[str, object]


def _provided_token(
    x_app_token: str | None,
    authorization: str | None,
) -> str | None:
    if x_app_token:
        return x_app_token
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return None


async def authenticated_principal(
    x_app_token: str | None = Header(default=None, alias="X-App-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    if not settings.auth_ready or settings.app_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="application authentication is not configured",
        )
    supplied = _provided_token(x_app_token, authorization)
    expected = settings.app_token.get_secret_value()
    if supplied is None or not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid application token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return service.principal_for_token(supplied)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    index_status = service.repository.status()
    ready = bool(
        settings.auth_ready and settings.model_ready and index_status.get("ready")
    )
    return HealthResponse(
        status="ready" if ready else "degraded",
        auth_configured=settings.auth_ready,
        model_ready=settings.model_ready,
        model_provider=settings.app_model_provider,
        model=settings.app_model,
        index=index_status,
    )


@app.get("/api/sources", response_model=SourceListResponse)
async def sources(
    _principal: str = Depends(authenticated_principal),
) -> SourceListResponse:
    try:
        return SourceListResponse(
            sources=service.repository.list_sources(settings.app_server_role)
        )
    except IndexUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="corpus index is unavailable",
        ) from exc


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    principal: str = Depends(authenticated_principal),
) -> ChatResponse:
    if request.role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role is server-assigned and must not be supplied by the client",
        )
    try:
        return await service.chat(
            message=request.message,
            requested_session_id=request.session_id,
            principal=principal,
        )
    except UnknownSession as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="unknown or expired session",
        ) from exc
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="session access denied",
        ) from exc
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="request budget exceeded",
        ) from exc
    except (IndexUnavailable, ServiceUnavailable, AuditWriteError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is not ready to complete a governed response",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="request time budget exceeded",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="model workflow failed closed",
        ) from exc


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
