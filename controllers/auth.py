"""Autenticación: registro, login y usuario autenticado."""
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from models import Usuario
from schemas import TokenResponse, UsuarioCreate, UsuarioResponse
from security import SesionDB, UsuarioActual, crear_token
from services import usuarios as sv

router = APIRouter(tags=["Autenticación"])


def _respuesta_token(usuario: Usuario, request: Request, mensaje: str) -> dict:
    token, expira_en = crear_token(usuario, request.app.state.settings)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expira_en,
        "usuario": usuario.to_dict(privado=True),
        "mensaje": mensaje,
    }


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Iniciar sesión y obtener el token JWT",
)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SesionDB,
):
    usuario = sv.autenticar(db, form.username, form.password)
    return _respuesta_token(usuario, request, "Inicio de sesión correcto.")


@router.post(
    "/auth/registro",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una cuenta de jugador",
)
def registro(request: Request, datos: UsuarioCreate, db: SesionDB):
    usuario = sv.registrar_usuario(db, datos.model_dump())
    return _respuesta_token(usuario, request, "Usuario registrado.")


@router.get(
    "/auth/me",
    response_model=UsuarioResponse,
    summary="Datos del usuario autenticado",
)
def yo(usuario: UsuarioActual):
    return usuario.to_dict(privado=True)
