"""Autenticación y autorización.

- Páginas web: sesión de Flask-Login + decorador admin_requerido.
- API REST: token "Bearer" firmado (se obtiene en POST /api/auth/login).
"""
import secrets
from functools import wraps

from flask import abort, current_app, g, jsonify, request, session
from flask_login import current_user, login_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import Usuario, db


def admin_requerido(vista):
    @wraps(vista)
    @login_required
    def envoltura(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return vista(*args, **kwargs)

    return envoltura


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def verificar_csrf():
    """Se ejecuta antes de cada petición web que modifica datos."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.path.startswith("/api/"):
        enviado = request.form.get("csrf_token", "")
        if not enviado or not secrets.compare_digest(enviado, session.get("_csrf", "")):
            abort(400, description="El formulario expiró. Recargá la página e intentá de nuevo.")


def destino_seguro(url, por_defecto):
    """Evita redirecciones a otros sitios (solo rutas internas)."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return por_defecto


def _serializador():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="api-token")


def generar_token(usuario):
    # La huella del hash invalida los tokens anteriores si cambia la contraseña.
    return _serializador().dumps({"id": usuario.id, "h": usuario.password_hash[-12:]})


def _usuario_desde_token():
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        return None, "Falta el token de acceso. Enviá 'Authorization: Bearer <token>'."
    token = cabecera[7:].strip()
    try:
        datos = _serializador().loads(token, max_age=current_app.config["TOKEN_EXPIRACION_SEGUNDOS"])
    except SignatureExpired:
        return None, "El token expiró. Iniciá sesión nuevamente."
    except BadSignature:
        return None, "Token inválido."
    usuario = db.session.get(Usuario, datos.get("id"))
    if not usuario or usuario.password_hash[-12:] != datos.get("h"):
        return None, "Token inválido."
    return usuario, None


def token_requerido(admin=False):
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            usuario, error = _usuario_desde_token()
            if not usuario:
                return jsonify({"error": error}), 401
            if admin and not usuario.es_admin:
                return jsonify({"error": "Esta operación requiere rol de administrador."}), 403
            g.usuario = usuario
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def usuario_api_opcional():
    """Devuelve el usuario del token si se envió uno válido; si no, None."""
    usuario, _ = _usuario_desde_token()
    return usuario


def obtener_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, description="El cuerpo debe ser un objeto JSON (Content-Type: application/json).")
    return datos
