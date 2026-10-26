"""Reglas de negocio de la aplicación."""
import random
import re
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import (
    ESTADOS_TORNEO,
    MODALIDADES,
    ROLES,
    Inscripcion,
    Partida,
    Resultado,
    Torneo,
    Usuario,
    ahora,
    db,
)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class ErrorNegocio(Exception):
    """Error con mensaje para el usuario y código HTTP asociado."""

    def __init__(self, mensaje, codigo=400, errores=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.errores = errores or {}


class ErrorValidacion(ErrorNegocio):
    def __init__(self, errores):
        super().__init__("Los datos enviados no son válidos.", 400, errores)


def _str(datos, campo):
    valor = datos.get(campo)
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return ", ".join(str(v).strip() for v in valor)
    return str(valor).strip()


def _entero(valor):
    if isinstance(valor, bool):
        return None
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _booleano(valor):
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("1", "true", "on", "si", "sí", "yes")


def _fecha(valor):
    if isinstance(valor, datetime):
        return valor
    texto = str(valor or "").strip().replace(" ", "T")
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _lista_separada(texto, maximo_items, largo_item):
    items = []
    for parte in texto.split(","):
        parte = parte.strip()
        if parte and parte.lower() not in (i.lower() for i in items):
            items.append(parte)
    if len(items) > maximo_items:
        return None, f"Ingresá como máximo {maximo_items} elementos."
    if any(len(i) > largo_item for i in items):
        return None, f"Cada elemento puede tener como máximo {largo_item} caracteres."
    return items, None


def _validar_password(password, errores, campo="password"):
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errores[campo] = "La contraseña debe tener al menos 8 caracteres e incluir letras y números."


def validar_datos_usuario(datos, usuario=None):
    """Valida datos de alta (usuario=None) o de edición (solo los campos enviados)."""
    alta = usuario is None
    errores, limpio = {}, {}

    if alta or "username" in datos:
        username = _str(datos, "username")
        if not USERNAME_RE.match(username):
            errores["username"] = (
                "El nombre de usuario debe tener entre 3 y 30 caracteres "
                "(letras, números, punto, guion o guion bajo)."
            )
        else:
            q = Usuario.query.filter(func.lower(Usuario.username) == username.lower())
            if usuario:
                q = q.filter(Usuario.id != usuario.id)
            if q.first():
                errores["username"] = "Ese nombre de usuario ya está en uso."
            limpio["username"] = username

    if alta or "email" in datos:
        email = _str(datos, "email").lower()
        if not EMAIL_RE.match(email) or len(email) > 120:
            errores["email"] = "Ingresá un correo electrónico válido."
        else:
            q = Usuario.query.filter(Usuario.email == email)
            if usuario:
                q = q.filter(Usuario.id != usuario.id)
            if q.first():
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


def registrar_usuario(datos, rol="jugador"):
    limpio = validar_datos_usuario(datos)
    usuario = Usuario(
        username=limpio["username"],
        email=limpio["email"],
        rol=rol,
        juegos_favoritos=limpio.get("juegos_favoritos", ""),
    )
    if "password" in limpio:
        usuario.set_password(limpio["password"])
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorNegocio("El usuario o el correo ya están registrados.", 409)
    return usuario


def autenticar(identificador, password):
    identificador = (identificador or "").strip()
    usuario = Usuario.query.filter(
        (func.lower(Usuario.username) == identificador.lower())
        | (Usuario.email == identificador.lower())
    ).first()
    if not usuario or not usuario.check_password(password or ""):
        raise ErrorNegocio("Usuario o contraseña incorrectos.", 401)
    return usuario


def actualizar_usuario(usuario, datos, editor):
    limpio = validar_datos_usuario(datos, usuario)

    if "password" in limpio and editor.id == usuario.id:
        if not usuario.check_password(str(datos.get("password_actual") or "")):
            raise ErrorValidacion({"password_actual": "La contraseña actual es incorrecta."})

    if "rol" in datos and datos.get("rol") != usuario.rol:
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
        usuario.set_password(limpio["password"])
    db.session.commit()
    return usuario


def eliminar_usuario(usuario, editor):
    if usuario.id == editor.id:
        raise ErrorNegocio("No podés eliminar tu propia cuenta de administrador.", 400)
    if any(i.torneo.tiene_partidas for i in usuario.inscripciones):
        raise ErrorNegocio(
            "No se puede eliminar: el usuario participa en torneos con partidas generadas "
            "y se perdería el historial.",
            409,
        )
    db.session.delete(usuario)
    db.session.commit()


def validar_datos_torneo(datos, torneo=None):
    alta = torneo is None
    errores, limpio = {}, {}

    def enviado(campo):
        return alta or campo in datos

    if enviado("nombre"):
        nombre = _str(datos, "nombre")
        if not 3 <= len(nombre) <= 100:
            errores["nombre"] = "El nombre debe tener entre 3 y 100 caracteres."
        limpio["nombre"] = nombre

    if "descripcion" in datos or alta:
        descripcion = _str(datos, "descripcion")
        if len(descripcion) > 2000:
            errores["descripcion"] = "La descripción puede tener como máximo 2000 caracteres."
        limpio["descripcion"] = descripcion

    if enviado("videojuego"):
        videojuego = _str(datos, "videojuego")
        if not 2 <= len(videojuego) <= 80:
            errores["videojuego"] = "Indicá el videojuego (entre 2 y 80 caracteres)."
        limpio["videojuego"] = videojuego

    if enviado("fecha"):
        fecha = _fecha(datos.get("fecha"))
        if not fecha:
            errores["fecha"] = "Ingresá una fecha válida con formato AAAA-MM-DDTHH:MM."
        elif alta and fecha < ahora():
            errores["fecha"] = "La fecha del torneo no puede estar en el pasado."
        limpio["fecha"] = fecha

    if enviado("cupo_maximo"):
        cupo = _entero(datos.get("cupo_maximo"))
        if cupo is None or not 2 <= cupo <= 128:
            errores["cupo_maximo"] = "El cupo máximo debe ser un número entre 2 y 128."
        elif torneo and cupo < torneo.inscriptos:
            errores["cupo_maximo"] = (
                f"El cupo no puede ser menor a la cantidad de inscriptos ({torneo.inscriptos})."
            )
        limpio["cupo_maximo"] = cupo

    modalidad = torneo.modalidad if torneo else "individual"
    if "modalidad" in datos:
        modalidad = _str(datos, "modalidad")
        if modalidad not in MODALIDADES:
            errores["modalidad"] = "La modalidad debe ser 'individual' o 'equipos'."
        elif torneo and torneo.inscripciones and modalidad != torneo.modalidad:
            errores["modalidad"] = "No se puede cambiar la modalidad cuando ya hay inscriptos."
        limpio["modalidad"] = modalidad

    if modalidad == "equipos":
        valor = datos.get("jugadores_por_equipo", torneo.jugadores_por_equipo if torneo else None)
        cantidad = _entero(valor)
        if cantidad is None or not 2 <= cantidad <= 10:
            errores["jugadores_por_equipo"] = "En modalidad por equipos indicá entre 2 y 10 jugadores por equipo."
        limpio["jugadores_por_equipo"] = cantidad
    else:
        limpio["jugadores_por_equipo"] = None

    if "estado" in datos:
        estado = _str(datos, "estado")
        estado_actual = torneo.estado if torneo else None
        if estado not in ESTADOS_TORNEO:
            errores["estado"] = "Estado inválido."
        elif estado != estado_actual and estado in ("en_curso", "finalizado"):
            errores["estado"] = (
                "Los estados 'En curso' y 'Finalizado' los asigna el sistema al iniciar "
                "el torneo y al cargar los resultados."
            )
        elif torneo and torneo.tiene_partidas and estado != estado_actual:
            errores["estado"] = (
                "El torneo ya tiene partidas generadas. Reinicialas para volver a abrir inscripciones."
            )
        limpio["estado"] = estado

    if "destacado" in datos:
        limpio["destacado"] = _booleano(datos.get("destacado"))

    if errores:
        raise ErrorValidacion(errores)
    return limpio


def crear_torneo(datos, creador):
    limpio = validar_datos_torneo(datos)
    torneo = Torneo(creado_por=creador, **limpio)
    db.session.add(torneo)
    db.session.commit()
    return torneo


def actualizar_torneo(torneo, datos):
    limpio = validar_datos_torneo(datos, torneo)
    for campo, valor in limpio.items():
        setattr(torneo, campo, valor)
    db.session.commit()
    return torneo


def eliminar_torneo(torneo):
    db.session.delete(torneo)
    db.session.commit()


def buscar_torneos(estado=None, videojuego=None, modalidad=None, texto=None):
    q = Torneo.query
    if estado:
        if estado not in ESTADOS_TORNEO:
            raise ErrorValidacion({"estado": "Estado inválido."})
        q = q.filter(Torneo.estado == estado)
    if modalidad:
        if modalidad not in MODALIDADES:
            raise ErrorValidacion({"modalidad": "Modalidad inválida."})
        q = q.filter(Torneo.modalidad == modalidad)
    if videojuego:
        q = q.filter(Torneo.videojuego.ilike(f"%{videojuego}%"))
    if texto:
        q = q.filter(Torneo.nombre.ilike(f"%{texto}%") | Torneo.descripcion.ilike(f"%{texto}%"))
    return q.order_by(Torneo.fecha.asc()).all()


def videojuegos_disponibles():
    filas = db.session.query(Torneo.videojuego).distinct().order_by(Torneo.videojuego).all()
    return [f[0] for f in filas]


def inscribir(torneo, usuario, datos=None):
    datos = datos or {}
    if torneo.estado != "inscripciones_abiertas":
        raise ErrorNegocio("Las inscripciones para este torneo no están abiertas.", 409)
    if torneo.inscripcion_de(usuario):
        raise ErrorNegocio("Ya estás inscripto en este torneo.", 409)
    if torneo.esta_completo:
        raise ErrorNegocio("El torneo está completo: no quedan cupos disponibles.", 409)

    nombre_equipo = integrantes = None
    if torneo.es_por_equipos:
        errores = {}
        nombre_equipo = _str(datos, "nombre_equipo")
        if not 2 <= len(nombre_equipo) <= 60:
            errores["nombre_equipo"] = "El nombre del equipo debe tener entre 2 y 60 caracteres."
        elif any((i.nombre_equipo or "").lower() == nombre_equipo.lower() for i in torneo.inscripciones):
            errores["nombre_equipo"] = "Ya hay un equipo inscripto con ese nombre."
        necesarios = torneo.jugadores_por_equipo - 1
        lista, error = _lista_separada(_str(datos, "integrantes"), necesarios, 30)
        if error or lista is None or len(lista) != necesarios:
            errores["integrantes"] = (
                f"Indicá los {necesarios} compañeros de equipo separados por comas "
                f"(el capitán es quien inscribe)."
            )
        else:
            integrantes = ", ".join(lista)
        if errores:
            raise ErrorValidacion(errores)

    inscripcion = Inscripcion(
        torneo=torneo, usuario=usuario, nombre_equipo=nombre_equipo, integrantes=integrantes
    )
    db.session.add(inscripcion)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorNegocio("Ya existe una inscripción igual en este torneo.", 409)
    return inscripcion


def _verificar_puede_desinscribir(torneo):
    if torneo.tiene_partidas or torneo.estado not in ("proximamente", "inscripciones_abiertas"):
        raise ErrorNegocio(
            "No se puede cancelar la inscripción porque el torneo ya comenzó.", 409
        )


def cancelar_inscripcion(torneo, usuario):
    inscripcion = torneo.inscripcion_de(usuario)
    if not inscripcion:
        raise ErrorNegocio("No estás inscripto en este torneo.", 404)
    _verificar_puede_desinscribir(torneo)
    db.session.delete(inscripcion)
    db.session.commit()


def eliminar_inscripcion(inscripcion):
    _verificar_puede_desinscribir(inscripcion.torneo)
    db.session.delete(inscripcion)
    db.session.commit()


def iniciar_torneo(torneo):
    if torneo.estado != "inscripciones_abiertas":
        raise ErrorNegocio("El torneo debe estar en inscripciones abiertas para iniciar.", 409)
    if len(torneo.inscripciones) < 2:
        raise ErrorNegocio("Se necesitan al menos 2 inscriptos para iniciar el torneo.", 409)
    if torneo.tiene_partidas:
        raise ErrorNegocio("Las partidas ya fueron generadas para este torneo.", 409)

    inscripciones = list(torneo.inscripciones)
    random.shuffle(inscripciones)

    torneo.estado = "en_curso"
    db.session.flush()

    ronda = 1
    numero = 1
    i = 0
    while i < len(inscripciones):
        participante1 = inscripciones[i]
        i += 1
        participante2 = inscripciones[i] if i < len(inscripciones) else None
        i += 1
        partida = Partida(
            torneo_id=torneo.id,
            ronda=ronda,
            numero=numero,
            participante1_id=participante1.id,
            participante2_id=participante2.id if participante2 else None,
            estado="bye" if participante2 is None else "pendiente",
        )
        if participante2 is None:
            partida.ganador_id = participante1.id
        db.session.add(partida)
        numero += 1

    db.session.commit()
    return torneo


def registrar_resultado_partida(torneo, partida_id, datos, registrado_por):
    partida = Partida.query.filter_by(id=partida_id, torneo_id=torneo.id).first()
    if not partida:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if partida.estado == "finalizada":
        raise ErrorNegocio("Esta partida ya tiene un resultado registrado.", 409)
    if partida.estado == "bye":
        raise ErrorNegocio("Las partidas bye no requieren resultado.", 409)
    if not partida.participante1_id or not partida.participante2_id:
        raise ErrorNegocio("La partida no está completa para cargar un resultado.", 409)

    puntaje1 = _entero(datos.get("puntaje1"))
    puntaje2 = _entero(datos.get("puntaje2"))
    errores = {}
    if puntaje1 is None or puntaje1 < 0:
        errores["puntaje1"] = "Ingresá un puntaje válido para el participante 1."
    if puntaje2 is None or puntaje2 < 0:
        errores["puntaje2"] = "Ingresá un puntaje válido para el participante 2."
    if puntaje1 == puntaje2 and puntaje1 is not None:
        errores["puntaje"] = "No puede haber empate, debe haber un ganador."
    if errores:
        raise ErrorValidacion(errores)

    if puntaje1 > puntaje2:
        ganador_id = partida.participante1_id
    else:
        ganador_id = partida.participante2_id

    resultado = Resultado(
        partida_id=partida.id,
        puntaje1=puntaje1,
        puntaje2=puntaje2,
        ganador_id=ganador_id,
        registrado_por_id=registrado_por.id if registrado_por else None,
    )
    db.session.add(resultado)
    partida.ganador_id = ganador_id
    partida.estado = "finalizada"
    db.session.flush()

    _avanzar_ganador(torneo, partida, ganador_id)
    db.session.commit()
    return partida


def _avanzar_ganador(torneo, partida_actual, ganador_id):
    total_partidas_ronda = Partida.query.filter_by(torneo_id=torneo.id, ronda=partida_actual.ronda).count()
    numero = partida_actual.numero
    siguiente_ronda = partida_actual.ronda + 1

    if total_partidas_ronda == 1:
        torneo.estado = "finalizado"
        return

    if numero % 2 == 1:
        siguiente_numero = (numero + 1) // 2
        siguiente_partida = Partida.query.filter_by(
            torneo_id=torneo.id, ronda=siguiente_ronda, numero=siguiente_numero
        ).first()
        if not siguiente_partida:
            siguiente_partida = Partida(
                torneo_id=torneo.id, ronda=siguiente_ronda, numero=siguiente_numero, estado="pendiente"
            )
            db.session.add(siguiente_partida)
            db.session.flush()
        if siguiente_partida.participante1_id is None:
            siguiente_partida.participante1_id = ganador_id
        elif siguiente_partida.participante2_id is None:
            siguiente_partida.participante2_id = ganador_id
    else:
        siguiente_numero = numero // 2
        siguiente_partida = Partida.query.filter_by(
            torneo_id=torneo.id, ronda=siguiente_ronda, numero=siguiente_numero
        ).first()
        if not siguiente_partida:
            siguiente_partida = Partida(
                torneo_id=torneo.id, ronda=siguiente_ronda, numero=siguiente_numero, estado="pendiente"
            )
            db.session.add(siguiente_partida)
            db.session.flush()
        if siguiente_partida.participante1_id is None:
            siguiente_partida.participante1_id = ganador_id
        elif siguiente_partida.participante2_id is None:
            siguiente_partida.participante2_id = ganador_id

    if siguiente_partida.participante1_id and siguiente_partida.participante2_id and siguiente_partida.estado != "bye":
        siguiente_partida.estado = "pendiente"


def tabla_posiciones(torneo):
    """Victorias, derrotas y partidas jugadas de cada inscripto."""
    filas = {}

    def base(inscripcion):
        return {
            "inscripcion_id": inscripcion.id,
            "nombre": inscripcion.nombre_mostrar,
            "equipo": inscripcion.nombre_equipo,
            "usuario_id": inscripcion.usuario_id,
            "victorias": 0,
            "derrotas": 0,
            "partidas_jugadas": 0,
        }

    for inscripcion in torneo.inscripciones:
        filas[inscripcion.id] = base(inscripcion)

    for partida in torneo.partidas:
        for inscripcion in (partida.participante1, partida.participante2):
            if inscripcion is None:
                continue
            fila = filas.setdefault(inscripcion.id, base(inscripcion))
            fila["partidas_jugadas"] += 1
            if partida.estado == "finalizada" and partida.ganador_id:
                if partida.ganador_id == inscripcion.id:
                    fila["victorias"] += 1
                else:
                    fila["derrotas"] += 1

    tabla = list(filas.values())
    tabla.sort(key=lambda f: (-f["victorias"], f["derrotas"], -f["partidas_jugadas"], f["nombre"].lower()))
    for posicion, fila in enumerate(tabla, 1):
        fila["posicion"] = posicion
    return tabla



def historial_usuario(usuario):
    return sorted(usuario.inscripciones, key=lambda i: i.torneo.fecha, reverse=True)


def historial_a_json(inscripciones):
    return [
        {
            "torneo": {"id": i.torneo.id, "nombre": i.torneo.nombre, "videojuego": i.torneo.videojuego,
                       "fecha": i.torneo.fecha.isoformat(timespec="minutes"), "estado": i.torneo.estado},
            "inscripcion_id": i.id,
            "nombre": i.nombre_mostrar,
            "inscripto_en": i.creado_en.isoformat(timespec="minutes"),
        }
        for i in inscripciones
    ]


def estadisticas():
    por_estado = dict(db.session.query(Torneo.estado, func.count(Torneo.id)).group_by(Torneo.estado).all())
    return {
        "usuarios": Usuario.query.count(),
        "torneos": Torneo.query.count(),
        "torneos_por_estado": {clave: por_estado.get(clave, 0) for clave in ESTADOS_TORNEO},
        "inscripciones": Inscripcion.query.count(),
    }
