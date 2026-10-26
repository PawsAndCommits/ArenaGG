"""Hash y verificación de contraseñas con Argon2."""
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()


def hashear_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        return False
