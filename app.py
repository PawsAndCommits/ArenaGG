"""Aplicación Flask de ArenaGG."""
import os
import secrets
import sqlite3

import click
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, render_template, request
from flask_login import LoginManager, current_user
from flask_socketio import join_room, leave_room
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException

import migraciones
from extensiones import socketio
from models import (
    ESTADOS_TORNEO,
    FORMATOS,
    MODALIDADES,
    Notificacion,
    Torneo,
    Usuario,
    db,
)
from routes import registrar_blueprints
from seguridad import csrf_token, verificar_csrf
from services import ErrorNegocio, registrar_usuario

login_manager = LoginManager()
login_manager.login_view = "usuarios.login"
login_manager.login_message = "Iniciá sesión para continuar."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def cargar_usuario(usuario_id):
    return db.session.get(Usuario, int(usuario_id))


@event.listens_for(Engine, "connect")
def activar_claves_foraneas(conexion, _registro):
    if isinstance(conexion, sqlite3.Connection):
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def _clave_secreta(carpeta):
    ruta = os.path.join(carpeta, "secret_key.txt")
    if not os.path.exists(ruta):
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(secrets.token_hex(32))
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read().strip()


def _entorno_booleano(nombre, por_defecto=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


CARPETA_PROYECTO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CARPETA_PROYECTO, ".env"))


def create_app(config=None):
    app = Flask(__name__, instance_path=os.path.join(CARPETA_PROYECTO, "instance"))
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _clave_secreta(app.instance_path),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL")
        or "sqlite:///" + os.path.join(app.instance_path, "torneos.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TOKEN_EXPIRACION_SEGUNDOS=8 * 60 * 60,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        STEAM_API_KEY=os.environ.get("STEAM_API_KEY", ""),
        CS2_WEBHOOK_SECRET=os.environ.get("CS2_WEBHOOK_SECRET", ""),
        MODO_SERVIDORES=_entorno_booleano("MODO_SERVIDORES"),
        CSRF_ENABLED=True,
    )
    if config:
        app.config.update(config)
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    db.init_app(app)
    login_manager.init_app(app)
    opciones_socket = {}
    if os.environ.get("SOCKETIO_ORIGINS"):
        opciones_socket["cors_allowed_origins"] = os.environ["SOCKETIO_ORIGINS"]
    socketio.init_app(app, **opciones_socket)
    registrar_blueprints(app)

    with app.app_context():
        db.create_all()
        migraciones.aplicar()

    app.before_request(verificar_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.context_processor
    def variables_globales():
        datos = {
            "ESTADOS_TORNEO": ESTADOS_TORNEO,
            "MODALIDADES": MODALIDADES,
            "FORMATOS": FORMATOS,
            "modo_servidores": app.config["MODO_SERVIDORES"],
            "notificaciones_sin_leer": 0,
            "notificaciones_recientes": [],
        }
        if current_user.is_authenticated:
            datos["notificaciones_sin_leer"] = Notificacion.query.filter_by(
                usuario_id=current_user.id, leida=False
            ).count()
            datos["notificaciones_recientes"] = (
                Notificacion.query.filter_by(usuario_id=current_user.id)
                .order_by(Notificacion.creada_en.desc())
                .limit(5)
                .all()
            )
        return datos

    @app.template_filter("fecha")
    def formato_fecha(valor, formato="%d/%m/%Y %H:%M"):
        return valor.strftime(formato) if valor else "Por definir"

    @app.template_filter("fecha_input")
    def formato_fecha_input(valor):
        return valor.strftime("%Y-%m-%dT%H:%M") if valor else ""

    _registrar_errores(app)
    _registrar_comandos(app)
    return app


@socketio.on("connect")
def socket_conectar():
    if current_user.is_authenticated:
        join_room(f"user:{current_user.id}")
    join_room("publico")


@socketio.on("unirse_torneo")
def socket_unirse_torneo(datos):
    torneo_id = None
    if isinstance(datos, dict):
        torneo_id = datos.get("torneo_id")
    try:
        torneo_id = int(torneo_id)
    except (TypeError, ValueError):
        return
    if db.session.get(Torneo, torneo_id):
        join_room(f"torneo:{torneo_id}")


@socketio.on("salir_torneo")
def socket_salir_torneo(datos):
    torneo_id = None
    if isinstance(datos, dict):
        torneo_id = datos.get("torneo_id")
    try:
        leave_room(f"torneo:{int(torneo_id)}")
    except (TypeError, ValueError):
        return


def _registrar_errores(app):
    @app.errorhandler(ErrorNegocio)
    def error_negocio(error):
        db.session.rollback()
        if request.path.startswith("/api/"):
            cuerpo = {"error": error.mensaje}
            if error.errores:
                cuerpo["detalles"] = error.errores
            return jsonify(cuerpo), error.codigo
        detalle = error.mensaje
        if error.errores:
            detalle = " ".join(error.errores.values())
        return render_template("error.html", codigo=error.codigo, mensaje=detalle), error.codigo

    @app.errorhandler(HTTPException)
    def error_http(error):
        mensajes = {
            400: "La solicitud no es válida.",
            401: "No autenticado.",
            403: "No tenés permisos para esta operación.",
            404: "Recurso no encontrado.",
            405: "Método HTTP no permitido para esta ruta.",
        }
        mensaje = error.description if error.code == 400 else mensajes.get(
            error.code, error.description
        )
        if request.path.startswith("/api/"):
            return jsonify({"error": mensaje}), error.code
        return render_template("error.html", codigo=error.code, mensaje=mensaje), error.code

    @app.errorhandler(Exception)
    def error_inesperado(error):
        db.session.rollback()
        app.logger.exception(error)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno del servidor."}), 500
        return render_template(
            "error.html",
            codigo=500,
            mensaje="Ocurrió un error inesperado. Intentá de nuevo en unos minutos.",
        ), 500


def _registrar_comandos(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        migraciones.aplicar()
        click.echo(f"Base de datos lista en {app.config['SQLALCHEMY_DATABASE_URI']}")

    @app.cli.command("migrar")
    def migrar():
        migraciones.aplicar()
        click.echo("Migración aplicada.")

    @app.cli.command("crear-admin")
    @click.option("--username", prompt="Nombre de usuario")
    @click.option("--email", prompt="Correo electrónico")
    @click.option("--password", prompt="Contraseña", hide_input=True, confirmation_prompt=True)
    def crear_admin(username, email, password):
        existente = Usuario.query.filter_by(username=username).first()
        if existente:
            existente.rol = "admin"
            db.session.commit()
            click.echo(f"El usuario '{username}' ahora es administrador.")
            return
        try:
            registrar_usuario(
                {"username": username, "email": email, "password": password}, rol="admin"
            )
        except ErrorNegocio as error:
            for mensaje in error.errores.values() or [error.mensaje]:
                click.echo(f"Error: {mensaje}", err=True)
            raise SystemExit(1)
        click.echo(f"Administrador '{username}' creado correctamente.")

    @app.cli.command("crear-servidor")
    @click.option("--nombre", prompt="Nombre del servidor")
    @click.option("--ip", prompt="IP del servidor")
    @click.option("--puerto", prompt="Puerto RCON", default=27015, type=int)
    @click.option("--rcon-password", prompt="Contraseña RCON", hide_input=True)
    def crear_servidor(nombre, ip, puerto, rcon_password):
        from models import ServidorCS2

        servidor = ServidorCS2(
            nombre=nombre, ip=ip, puerto=puerto, rcon_password=rcon_password, activo=True
        )
        db.session.add(servidor)
        db.session.commit()
        click.echo(f"Servidor '{nombre}' creado con ID {servidor.id}.")


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=_entorno_booleano("FLASK_DEBUG"))
