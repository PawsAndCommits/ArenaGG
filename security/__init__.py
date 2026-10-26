"""Seguridad de ArenaGG: contraseñas, JWT y dependencias."""
from security.dependencies import (
    AdminActual,
    SesionDB,
    UsuarioActual,
    UsuarioOpcional,
    get_current_user,
    get_optional_user,
    oauth2_scheme,
    require_admin,
)
from security.jwt import crear_token, decodificar_token
from security.passwords import hashear_password, verificar_password

__all__ = [
    "AdminActual",
    "SesionDB",
    "UsuarioActual",
    "UsuarioOpcional",
    "crear_token",
    "decodificar_token",
    "get_current_user",
    "get_optional_user",
    "hashear_password",
    "oauth2_scheme",
    "require_admin",
    "verificar_password",
]
