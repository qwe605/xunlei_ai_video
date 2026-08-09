from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.config import Settings
from app.dependencies import get_app_settings, get_auth_service, get_current_user
from app.schemas import AuthCredentials, RegisterRequest, UserRead
from app.services.auth import AuthError, AuthService


AUTH_COOKIE_NAME = "xunlei_session"
router = APIRouter(prefix="/auth", tags=["账号"])


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> UserRead:
    try:
        result = service.register(payload)
    except AuthError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    _set_session_cookie(response, result.token, settings)
    return result.user


@router.post("/login", response_model=UserRead)
def login(
    payload: AuthCredentials,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> UserRead:
    try:
        result = service.login(payload)
    except AuthError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    _set_session_cookie(response, result.token, settings)
    return result.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    token: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> None:
    service.logout(token)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserRead)
def me(user: Annotated[UserRead, Depends(get_current_user)]) -> UserRead:
    return user
