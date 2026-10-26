"""Aplicación Flask de ArenaGG."""
import os
import secrets
import sqlite3

import click
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request
from flask_login import LoginManager
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException

from extensiones import socketio
from models import ESTADOS_TORNEO, MODALIDADES, Usuario, db
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
    """SQLite necesita activar las claves foráneas en cada conexión."""
    if isinstance(conexion, sqlite3.Connection):
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def _clave_secreta(carpeta):
    """Guarda la clave secreta en instance/ para no regenerarla en cada arranque."""
    ruta = os.path.join(carpeta, "secret_key.txt")
    if not os.path.exists(ruta):
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(secrets.token_hex(32))
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read().strip()


CARPETA_PROYECTO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CARPETA_PROYECTO, ".env"))


def create_app(config=None):
    app = Flask(__name__, instance_path=os.path.join(CARPETA_PROYECTO, "instance"))
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _clave_secreta(app.instance_path),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(app.instance_path, "torneos.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TOKEN_EXPIRACION_SEGUNDOS=8 * 60 * 60,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        STEAM_API_KEY=os.environ.get("STEAM_API_KEY", ""),
        CS2_WEBHOOK_SECRET=os.environ.get("CS2_WEBHOOK_SECRET", ""),
    )
    if config:
        app.config.update(config)
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    registrar_blueprints(app)

    with app.app_context():
        db.create_all()

    app.before_request(verificar_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.context_processor
    def variables_globales():
        return {"ESTADOS_TORNEO": ESTADOS_TORNEO, "MODALIDADES": MODALIDADES}

    @app.template_filter("fecha")
    def formato_fecha(valor, formato="%d/%m/%Y %H:%M"):
        return valor.strftime(formato) if valor else "Por definir"

    @app.template_filter("fecha_input")
    def formato_fecha_input(valor):
        return valor.strftime("%Y-%m-%dT%H:%M") if valor else ""

    _registrar_errores(app)
    _registrar_comandos(app)
    return app


def _registrar_errores(app):
    @app.errorhandler(ErrorNegocio)
    def error_negocio(error):
        db.session.rollback()
        if request.path.startswith("/api/"):
            cuerpo = {"error": error.mensaje}
            if error.errores:
                cuerpo["detalles"] = error.errores
            return jsonify(cuerpo), error.codigo
        flash(error.mensaje, "danger")
        for mensaje in error.errores.values():
            flash(mensaje, "danger")
        return redirect(request.referrer or "/")

    @app.errorhandler(HTTPException)
    def error_http(error):
        if request.path.startswith("/api/"):
            mensajes = {
                401: "No autenticado.",
                403: "No tenés permisos para esta operación.",
                404: "Recurso no encontrado.",
                405: "Método HTTP no permitido para esta ruta.",
            }
            mensaje = error.description if error.code == 400 else mensajes.get(error.code, error.description)
            return jsonify({"error": mensaje}), error.code
        return render_template("error.html", error=error), error.code

    @app.errorhandler(Exception)
    def error_inesperado(error):
        db.session.rollback()
        app.logger.exception(error)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno del servidor."}), 500
        return render_template("error.html", error=None), 500


def _registrar_comandos(app):
    @app.cli.command("init-db")
    def init_db():
        """Crea (si no existen) las tablas de instance/torneos.db."""
        db.create_all()
        click.echo(f"Base de datos lista en {app.config['SQLALCHEMY_DATABASE_URI']}")

    @app.cli.command("crear-admin")
    @click.option("--username", prompt="Nombre de usuario")
    @click.option("--email", prompt="Correo electrónico")
    @click.option("--password", prompt="Contraseña", hide_input=True, confirmation_prompt=True)
    def crear_admin(username, email, password):
        """Crea un usuario administrador (o asciende uno existente)."""
        existente = Usuario.query.filter_by(username=username).first()
        if existente:
            existente.rol = "admin"
            db.session.commit()
            click.echo(f"El usuario '{username}' ahora es administrador.")
            return
        try:
            registrar_usuario({"username": username, "email": email, "password": password}, rol="admin")
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
        """Registra un servidor dedicado de CS2 para asignar a las partidas."""
        from models import ServidorCS2

        servidor = ServidorCS2(
            nombre=nombre, ip=ip, puerto=puerto, rcon_password=rcon_password, activo=True
        )
        db.session.add(servidor)
        db.session.commit()
        click.echo(f"Servidor '{nombre}' creado con ID {servidor.id}.")


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True)
