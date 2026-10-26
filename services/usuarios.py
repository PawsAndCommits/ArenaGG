"""Reglas de negocio de usuarios."""
import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Inscripcion, Usuario
from security.passwords import hashear_password, verificar_password
from services.errors import ErrorNegocio, ErrorValidacion

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
ROLES = ("admin", "jugador")


def _str(datos, campo) -> str:
    valor = datos.get(campo)
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return ", ".join(str(item).strip() for item in valor)
    return str(valor).strip()


def _lista_separada(texto: str, maximo_items: int, largo_item: int):
    items: list[str] = []
    for parte in texto.split(","):
        parte = parte.strip()
        if parte and parte.lower() not in (item.lower() for item in items):
            items.append(parte)
    if len(items) > maximo_items:
        return None, f"Ingresá como máximo {maximo_items} elementos."
    if any(len(item) > largo_item for item in items):
        return None, f"Cada elemento puede tener como máximo {largo_item} caracteres."
    return items, None


def _validar_password(password: str, errores: dict, campo: str = "password") -> None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errores[campo] = (
            "La contraseña debe tener al menos 8 caracteres e incluir letras y números."
        )


def validar_datos_usuario(db: Session, datos: dict, usuario: Usuario | None = None) -> dict:
    alta = usuario is None
    errores: dict = {}
    limpio: dict = {}

    if alta or "username" in datos:
        username = _str(datos, "username")
        if not USERNAME_RE.match(username):
            errores["username"] = (
                "El nombre de usuario debe tener entre 3 y 30 caracteres "
                "(letras, números, punto, guion o guion bajo)."
            )
        else:
            consulta = select(Usuario.id).where(
                func.lower(Usuario.username) == username.lower()
            )
            if usuario:
                consulta = consulta.where(Usuario.id != usuario.id)
            if db.scalar(consulta):
                errores["username"] = "Ese nombre de usuario ya está en uso."
            limpio["username"] = username

    if alta or "email" in datos:
        email = _str(datos, "email").lower()
        if not email and not alta:
            limpio["email"] = None
        elif not EMAIL_RE.match(email) or len(email) > 120:
            errores["email"] = "Ingresá un correo electrónico válido."
        else:
            consulta = select(Usuario.id).where(Usuario.email == email)
            if usuario:
                consulta = consulta.where(Usuario.id != usuario.id)
            if db.scalar(consulta):
                errores["email"] = "Ese correo electrónico ya está registrado."
            limpio["email"] = email

    password = datos.get("password") or ""
    if alta or password:
        password = str(password)
        _validar_password(password, errores)
        confirmacion = datos.get("password_confirmacion")
        if confirmacion is not None and confirmacion != password:
            errores["password_confirmacion"] = "Las contraseñas no coinciden."
        limpio["password"] = password

    if "juegos_favoritos" in datos:
        juegos, error = _lista_separada(_str(datos, "juegos_favoritos"), 10, 40)
        if error:
            errores["juegos_favoritos"] = error
        else:
            limpio["juegos_favoritos"] = ", ".join(juegos)

    if errores:
        raise ErrorValidacion(errores)
    return limpio


def registrar_usuario(db: Session, datos: dict, rol: str = "jugador") -> Usuario:
    limpio = validar_datos_usuario(db, datos)
    usuario = Usuario(
        username=limpio["username"],
        email=limpio["email"],
        rol=rol,
        juegos_favoritos=limpio.get("juegos_favoritos", ""),
    )
    if "password" in limpio:
        usuario.password_hash = hashear_password(limpio["password"])
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErrorNegocio("El usuario o el correo ya están registrados.", 409)
    return usuario


def autenticar(db: Session, identificador: str, password: str) -> Usuario:
    identificador = (identificador or "").strip()
    usuario = db.scalar(
        select(Usuario).where(
            (func.lower(Usuario.username) == identificador.lower())
            | (func.lower(Usuario.email) == identificador.lower())
        )
    )
    if not usuario or not verificar_password(password or "", usuario.password_hash):
        raise ErrorNegocio("Usuario o contraseña incorrectos.", 401)
    return usuario


def actualizar_usuario(db: Session, usuario: Usuario, datos: dict, editor: Usuario) -> Usuario:
    limpio = validar_datos_usuario(db, datos, usuario)

    if "password" in limpio and editor.id == usuario.id:
        if usuario.tiene_password and not verificar_password(
            str(datos.get("password_actual") or ""), usuario.password_hash
        ):
            raise ErrorValidacion(
                {"password_actual": "La contraseña actual es incorrecta."}
            )

    if "rol" in datos and datos.get("rol") is not None and datos.get("rol") != usuario.rol:
        if not editor.es_admin:
            raise ErrorNegocio("Solo un administrador puede cambiar roles.", 403)
        rol = _str(datos, "rol")
        if rol not in ROLES:
            raise ErrorValidacion({"rol": "El rol debe ser 'admin' o 'jugador'."})
        if editor.id == usuario.id:
            raise ErrorNegocio("No podés quitarte tu propio rol de administrador.", 400)
        usuario.rol = rol

    for campo in ("username", "email", "juegos_favoritos"):
        if campo in limpio:
            setattr(usuario, campo, limpio[campo])
    if "password" in limpio:
        usuario.password_hash = hashear_password(limpio["password"])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErrorNegocio("El usuario o el correo ya están registrados.", 409)
    return usuario


def eliminar_usuario(db: Session, usuario: Usuario, editor: Usuario) -> None:
    if usuario.id == editor.id:
        raise ErrorNegocio("No podés eliminar tu propia cuenta de administrador.", 400)
    if any(inscripcion.torneo.tiene_partidas for inscripcion in usuario.inscripciones):
        raise ErrorNegocio(
            "No se puede eliminar: el usuario participa en torneos con partidas generadas "
            "y se perdería el historial.",
            409,
        )
    db.delete(usuario)
    db.commit()


def historial_usuario(db: Session, usuario: Usuario) -> list[Inscripcion]:
    ids = {inscripcion.id for inscripcion in usuario.inscripciones}
    for membresia in usuario.membresias:
        if membresia.estado == "activo" and membresia.equipo:
            ids.update(
                inscripcion.id for inscripcion in membresia.equipo.inscripciones
            )
    if not ids:
        return []
    inscripciones = list(db.scalars(select(Inscripcion).where(Inscripcion.id.in_(ids))).all())
    return sorted(inscripciones, key=lambda inscripcion: inscripcion.torneo.fecha, reverse=True)


def historial_a_json(inscripciones: list[Inscripcion]) -> list[dict]:
    return [
        {
            "torneo": {
                "id": inscripcion.torneo.id,
                "nombre": inscripcion.torneo.nombre,
                "videojuego": inscripcion.torneo.videojuego,
                "fecha": inscripcion.torneo.fecha.isoformat(timespec="minutes"),
                "estado": inscripcion.torneo.estado,
            },
            "inscripcion_id": inscripcion.id,
            "nombre": inscripcion.nombre_mostrar,
            "inscripto_en": inscripcion.creado_en.isoformat(timespec="minutes"),
        }
        for inscripcion in inscripciones
    ]
