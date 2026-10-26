"""Dependencias de autenticación para FastAPI."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.session import get_db
from models.usuario import Usuario
from security.jwt import decodificar_token, huella_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

CREDENCIALES_INVALIDAS = "No se pudo validar la sesión. Iniciá sesión nuevamente."


def _error_credenciales(detalle: str = CREDENCIALES_INVALIDAS) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def usuario_desde_token(token: str, request: Request, db: Session) -> Usuario | None:
    settings = request.app.state.settings
    try:
        payload = decodificar_token(token, settings)
    except jwt.ExpiredSignatureError:
        raise _error_credenciales("El token expiró. Iniciá sesión nuevamente.")
    except jwt.InvalidTokenError:
        raise _error_credenciales("Token inválido.")

    usuario = db.get(Usuario, int(payload.get("sub", 0)))
    if not usuario or huella_password(usuario) != payload.get("hv"):
        raise _error_credenciales()
    return usuario


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Usuario:
    if not token:
        raise _error_credenciales("Falta el token de acceso. Usá 'Authorization: Bearer <token>'.")
    return usuario_desde_token(token, request, db)


def get_optional_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Usuario | None:
    if not token:
        return None
    try:
        return usuario_desde_token(token, request, db)
    except HTTPException:
        return None


def require_admin(usuario: Annotated[Usuario, Depends(get_current_user)]) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación requiere rol de administrador.",
        )
    return usuario


UsuarioActual = Annotated[Usuario, Depends(get_current_user)]
UsuarioOpcional = Annotated[Usuario | None, Depends(get_optional_user)]
AdminActual = Annotated[Usuario, Depends(require_admin)]
SesionDB = Annotated[Session, Depends(get_db)]
