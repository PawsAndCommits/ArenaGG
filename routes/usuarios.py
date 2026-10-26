"""Rutas de usuarios: registro, login, perfil e inscripciones del jugador (web + API)."""
import secrets

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

import services as sv
from models import Usuario, db
from seguridad import destino_seguro, generar_token, obtener_json, token_requerido
from integraciones import steam

bp = Blueprint("usuarios", __name__)
api = Blueprint("api_usuarios", __name__, url_prefix="/api")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    datos, errores = {}, {}
    if request.method == "POST":
        datos = request.form.to_dict()
        try:
            usuario = sv.registrar_usuario(datos)
        except sv.ErrorNegocio as error:
            errores = error.errores
            flash(error.mensaje, "danger")
        else:
            login_user(usuario)
            flash(f"¡Bienvenido/a, {usuario.username}! Tu cuenta fue creada.", "success")
            return redirect(url_for("main.index"))
    return render_template("usuarios/registro.html", datos=datos, errores=errores)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    identificador = ""
    if request.method == "POST":
        identificador = request.form.get("identificador", "")
        try:
            usuario = sv.autenticar(identificador, request.form.get("password", ""))
        except sv.ErrorNegocio as error:
            flash(error.mensaje, "danger")
        else:
            login_user(usuario, remember="recordar" in request.form)
            flash(f"Hola de nuevo, {usuario.username}.", "success")
            return redirect(destino_seguro(request.args.get("next"), url_for("main.index")))
    return render_template("usuarios/login.html", identificador=identificador)


@bp.route("/login/steam")
def steam_login():
    if current_user.is_authenticated:
        session["steam_vincular"] = True
    else:
        session.pop("steam_vincular", None)
    return redirect(steam.url_login())


@bp.route("/login/steam/callback")
def steam_callback():
    if not steam.validar_openid():
        flash("No se pudo validar la autenticación con Steam.", "danger")
        return redirect(url_for("usuarios.login"))

    steam_id = steam.extraer_steam_id()
    if not steam_id:
        flash("No se pudo obtener el SteamID.", "danger")
        return redirect(url_for("usuarios.login"))

    resumen = steam.resumen_jugador(steam_id) or {}

    if current_user.is_authenticated or session.get("steam_vincular"):
        usuario = current_user if current_user.is_authenticated else None
        if not usuario:
            flash("Iniciá sesión para vincular tu cuenta de Steam.", "warning")
            return redirect(url_for("usuarios.login"))
        existente = Usuario.query.filter_by(steam_id=steam_id).first()
        if existente and existente.id != usuario.id:
            flash("Ese perfil de Steam ya está vinculado a otra cuenta.", "danger")
            return redirect(url_for("usuarios.perfil"))
        usuario.steam_id = steam_id
        usuario.steam_persona_name = resumen.get("personaname")
        usuario.steam_avatar = resumen.get("avatar")
        usuario.steam_avatar_full = resumen.get("avatarfull") or resumen.get("avatarmedium")
        usuario.steam_profile_url = resumen.get("profileurl")
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Error al vincular Steam.", "danger")
            return redirect(url_for("usuarios.perfil"))
        session.pop("steam_vincular", None)
        flash("Cuenta de Steam vinculada correctamente.", "success")
        return redirect(url_for("usuarios.perfil"))

    usuario = Usuario.query.filter_by(steam_id=steam_id).first()
    if usuario:
        login_user(usuario)
        flash(f"Hola de nuevo, {usuario.username}.", "success")
        return redirect(url_for("main.index"))

    username_base = resumen.get("personaname") or f"steam_{steam_id[-6:]}"
    username = username_base.replace(" ", "_")
    base = username
    sufijo = 1
    while Usuario.query.filter_by(username=username).first():
        username = f"{base}_{sufijo}"
        sufijo += 1

    usuario = Usuario(
        username=username,
        email=None,
        rol="jugador",
        password_hash=None,
        steam_id=steam_id,
        steam_persona_name=resumen.get("personaname"),
        steam_avatar=resumen.get("avatar"),
        steam_avatar_full=resumen.get("avatarfull") or resumen.get("avatarmedium"),
        steam_profile_url=resumen.get("profileurl"),
    )
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("No se pudo crear la cuenta con Steam.", "danger")
        return redirect(url_for("usuarios.login"))
    login_user(usuario)
    flash(f"¡Bienvenido/a, {usuario.username}! Cuenta creada con Steam.", "success")
    return redirect(url_for("usuarios.perfil"))


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Cerraste sesión correctamente.", "info")
    return redirect(url_for("main.index"))


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    errores = {}
    if request.method == "POST":
        datos = {
            "username": request.form.get("username", ""),
            "email": request.form.get("email", ""),
            "juegos_favoritos": request.form.get("juegos_favoritos", ""),
        }
        try:
            sv.actualizar_usuario(current_user, datos, current_user)
        except sv.ErrorNegocio as error:
            db.session.rollback()
            errores = error.errores
            flash(error.mensaje, "danger")
        else:
            flash("Tus datos se actualizaron correctamente.", "success")
            return redirect(url_for("usuarios.perfil"))
    return _render_perfil(current_user, errores)


@bp.route("/perfil/password", methods=["POST"])
@login_required
def cambiar_password():
    datos = {
        "password_actual": request.form.get("password_actual", ""),
        "password": request.form.get("password", ""),
        "password_confirmacion": request.form.get("password_confirmacion", ""),
    }
    if not datos["password"]:
        flash("Ingresá la nueva contraseña.", "danger")
        return redirect(url_for("usuarios.perfil"))
    try:
        sv.actualizar_usuario(current_user, datos, current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        return _render_perfil(current_user, error.errores, error.mensaje)
    flash("Contraseña actualizada.", "success")
    return redirect(url_for("usuarios.perfil"))


@bp.route("/jugadores/<int:usuario_id>")
def jugador(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if current_user.is_authenticated and current_user.id == usuario.id:
        return redirect(url_for("usuarios.perfil"))
    return _render_perfil(usuario, {})


def _render_perfil(usuario, errores, mensaje_error=None):
    if mensaje_error:
        flash(mensaje_error, "danger")
    cs2_stats = cs2_playtime = None
    if usuario.steam_id:
        cs2_stats = steam.estadisticas_cs2(usuario.steam_id)
        cs2_playtime = steam.horas_cs2(usuario.steam_id)
    return render_template(
        "usuarios/perfil.html",
        usuario=usuario,
        historial=sv.historial_usuario(usuario),
        errores=errores,
        cs2_stats=cs2_stats,
        cs2_playtime=cs2_playtime,
    )


@api.route("/auth/registro", methods=["POST"])
@api.route("/usuarios", methods=["POST"])
def api_registro():
    usuario = sv.registrar_usuario(obtener_json())
    return jsonify({"mensaje": "Usuario registrado.", "usuario": usuario.to_dict(privado=True),
                    "token": generar_token(usuario)}), 201


@api.route("/auth/login", methods=["POST"])
def api_login():
    datos = obtener_json()
    usuario = sv.autenticar(datos.get("username") or datos.get("email"), datos.get("password"))
    return jsonify({
        "mensaje": "Inicio de sesión correcto.",
        "token": generar_token(usuario),
        "tipo": "Bearer",
        "expira_en_segundos": current_app.config["TOKEN_EXPIRACION_SEGUNDOS"],
        "usuario": usuario.to_dict(privado=True),
    })


@api.route("/auth/me", methods=["GET"])
@token_requerido()
def api_yo():
    return jsonify(g.usuario.to_dict(privado=True))


@api.route("/usuarios", methods=["GET"])
@token_requerido(admin=True)
def api_listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.id).all()
    return jsonify([u.to_dict(privado=True) for u in usuarios])


@api.route("/usuarios/<int:usuario_id>", methods=["GET"])
@token_requerido()
def api_obtener_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    privado = g.usuario.es_admin or g.usuario.id == usuario.id
    return jsonify(usuario.to_dict(privado=privado))


@api.route("/usuarios/<int:usuario_id>", methods=["PUT"])
@token_requerido()
def api_actualizar_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if not (g.usuario.es_admin or g.usuario.id == usuario.id):
        abort(403)
    try:
        sv.actualizar_usuario(usuario, obtener_json(), g.usuario)
    except sv.ErrorNegocio:
        db.session.rollback()
        raise
    return jsonify({"mensaje": "Usuario actualizado.", "usuario": usuario.to_dict(privado=True)})


@api.route("/usuarios/<int:usuario_id>", methods=["DELETE"])
@token_requerido(admin=True)
def api_eliminar_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    sv.eliminar_usuario(usuario, g.usuario)
    return jsonify({"mensaje": "Usuario eliminado."})


@api.route("/usuarios/<int:usuario_id>/historial", methods=["GET"])
def api_historial(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    return jsonify({"usuario": usuario.to_dict(), "historial": sv.historial_a_json(sv.historial_usuario(usuario))})
