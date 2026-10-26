"""Schemas de autenticación."""
from pydantic import BaseModel, ConfigDict

from schemas.usuario import UsuarioResponse


class TokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: UsuarioResponse
    mensaje: str = "Inicio de sesión correcto."
