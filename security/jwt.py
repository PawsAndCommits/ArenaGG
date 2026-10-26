"""Emisión y validación de tokens JWT."""
from datetime import UTC, datetime, timedelta

import jwt

from config import Settings
from models.usuario import Usuario

ALGORITMO = "HS256"


def huella_password(usuario: Usuario) -> str:
    return (usuario.password_hash or "")[-12:]


def crear_token(usuario: Usuario, settings: Settings) -> tuple[str, int]:
    expira_en = settings.token_expiracion_minutos * 60
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "rol": usuario.rol,
        "hv": huella_password(usuario),
        "iat": ahora,
        "exp": ahora + timedelta(seconds=expira_en),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITMO)
    return token, expira_en


def decodificar_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITMO])
