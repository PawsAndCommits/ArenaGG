"""Reglas de negocio de usuarios, torneos, llaves y resultados."""
import random
import re
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import notificaciones as notif
from models import (
    ESTADOS_TORNEO,
    FORMATOS,
    MODALIDADES,
    ROLES,
    Equipo,
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
OBJETIVO_MAPAS = {"BO1": 1, "BO3": 2, "BO5": 3}


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
        if not email and not alta:
            limpio["email"] = None
        elif not EMAIL_RE.match(email) or len(email) > 120:
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
        if usuario.tiene_password and not usuario.check_password(
            str(datos.get("password_actual") or "")
        ):
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

    if "reglas" in datos or alta:
        reglas = _str(datos, "reglas")
        if len(reglas) > 5000:
            errores["reglas"] = "Las reglas pueden tener como máximo 5000 caracteres."
        limpio["reglas"] = reglas

    if "premio" in datos or alta:
        premio = _str(datos, "premio")
        if len(premio) > 200:
            errores["premio"] = "El premio puede tener como máximo 200 caracteres."
        limpio["premio"] = premio

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

    formato = _str(datos, "formato") or (torneo.formato if torneo else "BO1")
    if formato not in FORMATOS:
        errores["formato"] = "El formato debe ser BO1, BO3 o BO5."
    elif torneo and torneo.tiene_partidas and formato != torneo.formato:
        errores["formato"] = "No se puede cambiar el formato cuando ya hay partidas generadas."
    limpio["formato"] = formato

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
            errores["jugadores_por_equipo"] = (
                "En modalidad por equipos indicá entre 2 y 10 jugadores por equipo."
            )
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
                "El torneo ya tiene partidas generadas. Reiniciá la llave para volver a abrir inscripciones."
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


def _validar_equipo_inscripcion(torneo, equipo, usuario):
    if not equipo:
        raise ErrorValidacion({"equipo_id": "Elegí un equipo para inscribirte."})
    if not equipo.es_capitan(usuario):
        raise ErrorNegocio("Solo el capitán puede inscribir al equipo.", 403)
    if not equipo.miembro_activo(usuario.id):
        raise ErrorNegocio("El capitán no pertenece al equipo.", 409)
    if len(equipo.miembros_activos) != torneo.jugadores_por_equipo:
        raise ErrorNegocio(
            f"El equipo necesita {torneo.jugadores_por_equipo} integrantes activos "
            f"(tiene {len(equipo.miembros_activos)}).",
            409,
        )
    ids_equipo = {m.usuario_id for m in equipo.miembros_activos}
    for inscripcion in torneo.inscripciones:
        if inscripcion.equipo_id == equipo.id:
            raise ErrorNegocio("Ese equipo ya está inscripto en el torneo.", 409)
        ids_inscriptos = {jugador.id for jugador in inscripcion.roster}
        repetidos = ids_equipo & ids_inscriptos
        if repetidos:
            nombres = ", ".join(
                m.usuario.username for m in equipo.miembros_activos if m.usuario_id in repetidos
            )
            raise ErrorNegocio(
                f"Estos jugadores ya están inscriptos con otro equipo: {nombres}.", 409
            )


def inscribir(torneo, usuario, datos=None):
    datos = datos or {}
    if torneo.estado != "inscripciones_abiertas":
        raise ErrorNegocio("Las inscripciones para este torneo no están abiertas.", 409)
    if torneo.inscripcion_de(usuario):
        raise ErrorNegocio("Ya estás inscripto en este torneo.", 409)
    if torneo.esta_completo:
        raise ErrorNegocio("El torneo está completo: no quedan cupos disponibles.", 409)

    equipo = None
    nombre_equipo = integrantes = None
    if torneo.es_por_equipos:
        equipo_id = _entero(datos.get("equipo_id"))
        equipo = db.session.get(Equipo, equipo_id) if equipo_id else None
        _validar_equipo_inscripcion(torneo, equipo, usuario)
        nombre_equipo = equipo.nombre
        integrantes = ", ".join(m.usuario.username for m in equipo.miembros_activos)

    inscripcion = Inscripcion(
        torneo=torneo,
        usuario=usuario,
        equipo=equipo,
        nombre_equipo=nombre_equipo,
        integrantes=integrantes,
    )
    db.session.add(inscripcion)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorNegocio("Ya existe una inscripción igual en este torneo.", 409)

    destinatarios = [i.id for i in inscripcion.roster]
    notif.enviar_a(
        destinatarios,
        "inscripcion",
        "Inscripción confirmada",
        f"Quedaste inscripto en «{torneo.nombre}».",
        url=notif.url_torneo(torneo),
        torneo_id=torneo.id,
    )
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
    if inscripcion.equipo and not inscripcion.es_capitan(usuario):
        raise ErrorNegocio("Solo el capitán puede cancelar la inscripción del equipo.", 403)
    _verificar_puede_desinscribir(torneo)
    db.session.delete(inscripcion)
    db.session.commit()


def eliminar_inscripcion(inscripcion):
    _verificar_puede_desinscribir(inscripcion.torneo)
    db.session.delete(inscripcion)
    db.session.commit()


def _siguiente_potencia(cantidad):
    potencia = 1
    rondas = 0
    while potencia < cantidad:
        potencia *= 2
        rondas += 1
    return potencia, rondas


def _indices_byes(cantidad_partidas, cantidad_byes):
    indices = set()
    if not cantidad_byes:
        return indices
    for i in range(cantidad_byes):
        indice = int((i + 0.5) * cantidad_partidas / cantidad_byes)
        while indice in indices:
            indice = (indice + 1) % cantidad_partidas
        indices.add(indice)
    return indices


def iniciar_torneo(torneo):
    if torneo.estado != "inscripciones_abiertas":
        raise ErrorNegocio("El torneo debe estar en inscripciones abiertas para iniciar.", 409)
    if len(torneo.inscripciones) < 2:
        raise ErrorNegocio("Se necesitan al menos 2 inscriptos para iniciar el torneo.", 409)
    if torneo.tiene_partidas:
        raise ErrorNegocio("Las partidas ya fueron generadas para este torneo.", 409)

    inscripciones = list(torneo.inscripciones)
    random.shuffle(inscripciones)
    tamano, total_rondas = _siguiente_potencia(len(inscripciones))
    partidas_ronda_1 = tamano // 2
    byes = tamano - len(inscripciones)
    indices_byes = _indices_byes(partidas_ronda_1, byes)

    torneo.estado = "en_curso"
    torneo.total_rondas = total_rondas
    torneo.iniciado_en = ahora()

    jugador = 0
    byes_creados = []
    for indice in range(partidas_ronda_1):
        if indice in indices_byes:
            participante1 = inscripciones[jugador]
            jugador += 1
            participante2 = None
            estado = "bye"
        else:
            participante1 = inscripciones[jugador]
            participante2 = inscripciones[jugador + 1]
            jugador += 2
            estado = "pendiente"
        partida = Partida(
            ronda=1,
            numero=indice + 1,
            participante1_id=participante1.id,
            participante2_id=participante2.id if participante2 else None,
            estado=estado,
        )
        if participante2 is None:
            partida.ganador_id = participante1.id
            byes_creados.append(partida)
        torneo.partidas.append(partida)

    for ronda in range(2, total_rondas + 1):
        cantidad = tamano // (2 ** ronda)
        for numero in range(1, cantidad + 1):
            torneo.partidas.append(
                Partida(ronda=ronda, numero=numero, estado="pendiente")
            )
    db.session.flush()

    for partida in byes_creados:
        _avanzar_ganador(torneo, partida, partida.ganador_id)
    db.session.commit()

    notif.avisar_torneo(
        torneo,
        "torneo",
        "Torneo iniciado",
        f"«{torneo.nombre}» ya está en marcha.",
        excluir=[],
    )
    for partida in torneo.partidas:
        if partida.ronda != 1:
            continue
        if partida.estado == "bye":
            notif.avisar_partida(
                partida,
                "bye",
                "Pase directo",
                f"Pasaste directo en {torneo.nombre}. Tu próximo rival se define en la ronda siguiente.",
            )
        elif partida.lista_para_jugar:
            notif.avisar_partida(
                partida,
                "partida",
                "Te toca jugar",
                f"{partida.nombre_ronda} · Partida #{partida.numero} en «{torneo.nombre}».",
            )
    return torneo


def _validar_marcador(formato, puntaje1, puntaje2):
    objetivo = OBJETIVO_MAPAS.get(formato, 1)
    if max(puntaje1, puntaje2) != objetivo or min(puntaje1, puntaje2) >= objetivo:
        return (
            f"Para {formato} el ganador debe llegar a {objetivo} mapas y el perdedor "
            f"no puede llegar a {objetivo}."
        )
    return None


def _validar_puntajes(torneo, datos):
    puntaje1 = _entero(datos.get("puntaje1"))
    puntaje2 = _entero(datos.get("puntaje2"))
    errores = {}
    if puntaje1 is None or puntaje1 < 0:
        errores["puntaje1"] = "Ingresá un marcador válido para el primer participante."
    if puntaje2 is None or puntaje2 < 0:
        errores["puntaje2"] = "Ingresá un marcador válido para el segundo participante."
    if puntaje1 is not None and puntaje2 is not None:
        if puntaje1 == puntaje2:
            errores["puntaje"] = "No puede haber empate: tiene que haber un ganador."
        else:
            error_formato = _validar_marcador(torneo.formato, puntaje1, puntaje2)
            if error_formato:
                errores["formato"] = error_formato
    if errores:
        raise ErrorValidacion(errores)
    return puntaje1, puntaje2


def _finalizar_partida(torneo, partida, ganador_id):
    partida.ganador_id = ganador_id
    partida.estado = "finalizada"
    db.session.flush()
    _avanzar_ganador(torneo, partida, ganador_id)
    if partida.ronda == torneo.total_rondas:
        torneo.estado = "finalizado"
    db.session.flush()


def _avanzar_ganador(torneo, partida_actual, ganador_id):
    total = torneo.total_rondas or max((p.ronda for p in torneo.partidas), default=0)
    if partida_actual.ronda >= total:
        return
    siguiente_numero = (partida_actual.numero + 1) // 2
    siguiente = next(
        (
            p
            for p in torneo.partidas
            if p.ronda == partida_actual.ronda + 1 and p.numero == siguiente_numero
        ),
        None,
    )
    if not siguiente:
        siguiente = Partida(
            ronda=partida_actual.ronda + 1,
            numero=siguiente_numero,
            estado="pendiente",
        )
        torneo.partidas.append(siguiente)
        db.session.flush()
    if partida_actual.numero % 2 == 1:
        siguiente.participante1_id = ganador_id
    else:
        siguiente.participante2_id = ganador_id
    if siguiente.participante1_id and siguiente.participante2_id and siguiente.estado != "bye":
        siguiente.estado = "pendiente"


def _notificar_resultado_confirmado(torneo, partida, ganador):
    perdedor = (
        partida.participante2
        if partida.participante1_id == ganador.id
        else partida.participante1
    )
    notif.avisar_partida(
        partida,
        "resultado",
        "Resultado confirmado",
        f"{partida.nombre_ronda}: {ganador.nombre_mostrar} ganó la partida #{partida.numero}.",
    )
    if partida.ronda == torneo.total_rondas:
        notif.enviar_a(
            notif.ids_de_inscripcion(ganador),
            "campeon",
            "¡Campeón!",
            f"Ganaste «{torneo.nombre}».",
            url=notif.url_torneo(torneo),
            torneo_id=torneo.id,
        )
        return
    if perdedor:
        notif.enviar_a(
            notif.ids_de_inscripcion(perdedor),
            "eliminado",
            "Quedaste eliminado",
            f"Tu participación en «{torneo.nombre}» terminó en {partida.nombre_ronda}.",
            url=notif.url_torneo(torneo),
            torneo_id=torneo.id,
        )
    siguiente = next(
        (
            p
            for p in torneo.partidas
            if p.ronda == partida.ronda + 1 and p.numero == (partida.numero + 1) // 2
        ),
        None,
    )
    if siguiente and siguiente.lista_para_jugar and not siguiente.resultado:
        notif.avisar_partida(
            siguiente,
            "partida",
            "Te toca jugar",
            f"Ya está definido tu rival de {siguiente.nombre_ronda} en «{torneo.nombre}».",
        )


def registrar_resultado_partida(torneo, partida_id, datos, registrado_por):
    partida = db.session.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if partida.estado == "finalizada":
        raise ErrorNegocio("Esta partida ya tiene un resultado confirmado.", 409)
    if partida.estado == "bye":
        raise ErrorNegocio("Las partidas de pase directo no requieren resultado.", 409)
    if partida.resultado:
        raise ErrorNegocio("Ya hay un resultado cargado para esta partida.", 409)
    if not partida.lista_para_jugar:
        raise ErrorNegocio("La partida todavía no está completa.", 409)
    if registrado_por is not None and not partida.puede_reportar(registrado_por):
        raise ErrorNegocio("No podés cargar el resultado de esta partida.", 403)

    puntaje1, puntaje2 = _validar_puntajes(torneo, datos)
    ganador_id = partida.participante1_id if puntaje1 > puntaje2 else partida.participante2_id
    es_admin = bool(registrado_por and registrado_por.es_admin)
    confirmado = registrado_por is None or es_admin

    resultado = Resultado(
        partida_id=partida.id,
        puntaje1=puntaje1,
        puntaje2=puntaje2,
        ganador_id=ganador_id,
        estado="confirmado" if confirmado else "pendiente",
        registrado_por_id=registrado_por.id if registrado_por else None,
        confirmado_por_id=registrado_por.id if confirmado and registrado_por else None,
        confirmado_en=ahora() if confirmado else None,
    )
    db.session.add(resultado)
    if confirmado:
        _finalizar_partida(torneo, partida, ganador_id)
    db.session.commit()

    if confirmado:
        _notificar_resultado_confirmado(torneo, partida, partida.ganador)
    else:
        notif.avisar_partida(
            partida,
            "resultado_pendiente",
            "Resultado cargado",
            f"{registrado_por.username} cargó {puntaje1}-{puntaje2}. Falta la confirmación del rival.",
        )
    return partida


def confirmar_resultado(torneo, partida_id, usuario):
    partida = db.session.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_confirmar(usuario):
        raise ErrorNegocio("No podés confirmar este resultado.", 403)
    resultado = partida.resultado
    resultado.estado = "confirmado"
    resultado.confirmado_por_id = usuario.id
    resultado.confirmado_en = ahora()
    resultado.actualizado_en = ahora()
    _finalizar_partida(torneo, partida, resultado.ganador_id)
    db.session.commit()
    _notificar_resultado_confirmado(torneo, partida, partida.ganador)
    return partida


def disputar_resultado(torneo, partida_id, datos, usuario):
    partida = db.session.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_disputar(usuario):
        raise ErrorNegocio("No podés disputar este resultado.", 403)
    motivo = _str(datos, "motivo")
    if not 3 <= len(motivo) <= 255:
        raise ErrorValidacion({"motivo": "Contá el motivo de la disputa (entre 3 y 255 caracteres)."})
    partida.resultado.estado = "disputa"
    partida.resultado.disputa_motivo = motivo
    partida.resultado.actualizado_en = ahora()
    db.session.commit()
    notif.avisar_partida(
        partida,
        "disputa",
        "Resultado en disputa",
        f"{usuario.username} disputó la partida #{partida.numero}: {motivo}",
    )
    notif.enviar_a(
        notif.ids_admins(),
        "disputa",
        "Disputa para resolver",
        f"Partida #{partida.numero} de «{torneo.nombre}»: {motivo}",
        url=notif.url_partida(partida),
        torneo_id=torneo.id,
    )
    return partida


def resolver_disputa(torneo, partida_id, datos, admin):
    partida = db.session.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_resolver(admin):
        raise ErrorNegocio("Solo un administrador puede resolver este resultado.", 403)
    puntaje1, puntaje2 = _validar_puntajes(torneo, datos)
    ganador_id = partida.participante1_id if puntaje1 > puntaje2 else partida.participante2_id
    resultado = partida.resultado
    resultado.puntaje1 = puntaje1
    resultado.puntaje2 = puntaje2
    resultado.ganador_id = ganador_id
    resultado.estado = "confirmado"
    resultado.confirmado_por_id = admin.id
    resultado.resuelto_por_id = admin.id
    resultado.confirmado_en = ahora()
    resultado.actualizado_en = ahora()
    _finalizar_partida(torneo, partida, ganador_id)
    db.session.commit()
    _notificar_resultado_confirmado(torneo, partida, partida.ganador)
    return partida


def rechazar_resultado(torneo, partida_id, admin):
    partida = db.session.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not partida.puede_rechazar(admin):
        raise ErrorNegocio("Solo un administrador puede rechazar este resultado.", 403)
    partida.resultado = None
    partida.ganador_id = None
    partida.estado = "pendiente"
    db.session.commit()
    notif.avisar_partida(
        partida,
        "resultado_rechazado",
        "Resultado rechazado",
        f"El administrador rechazó el marcador de la partida #{partida.numero}. Carguen uno nuevo.",
    )
    return partida


def programar_partida(torneo, partida_id, fecha, admin):
    partida = db.session.get(Partida, partida_id)
    if not partida or partida.torneo_id != torneo.id:
        raise ErrorNegocio("Partida no encontrada.", 404)
    if not admin.es_admin:
        raise ErrorNegocio("Solo un administrador puede programar la partida.", 403)
    fecha_dt = _fecha(fecha)
    if not fecha_dt:
        raise ErrorValidacion({"fecha_programada": "Ingresá una fecha válida."})
    partida.fecha_programada = fecha_dt
    db.session.commit()
    if partida.lista_para_jugar:
        notif.avisar_partida(
            partida,
            "horario",
            "Horario definido",
            f"Partida #{partida.numero}: {fecha_dt.strftime('%d/%m/%Y %H:%M')}.",
        )
    return partida


def reiniciar_llave(torneo, admin):
    if not admin.es_admin:
        raise ErrorNegocio("Solo un administrador puede reiniciar la llave.", 403)
    for partida in list(torneo.partidas):
        db.session.delete(partida)
    torneo.estado = "inscripciones_abiertas"
    torneo.total_rondas = None
    torneo.iniciado_en = None
    db.session.commit()
    notif.avisar_torneo(
        torneo,
        "torneo",
        "Llave reiniciada",
        f"El administrador reinició «{torneo.nombre}». Las inscripciones vuelven a estar abiertas.",
    )
    return torneo


def tabla_posiciones(torneo):
    filas = {}
    for inscripcion in torneo.inscripciones:
        filas[inscripcion.id] = {
            "inscripcion_id": inscripcion.id,
            "nombre": inscripcion.nombre_mostrar,
            "equipo": inscripcion.nombre_equipo,
            "usuario_id": inscripcion.usuario_id,
            "victorias": 0,
            "derrotas": 0,
            "partidas_jugadas": 0,
            "mapas_favor": 0,
            "mapas_contra": 0,
            "diferencia": 0,
            "winrate": 0,
            "racha": [],
            "estado": "En juego" if torneo.estado == "en_curso" else "Inscripto",
        }

    for partida in sorted(torneo.partidas, key=lambda p: (p.ronda, p.numero)):
        if partida.estado != "finalizada" or not partida.resultado:
            continue
        if partida.resultado.estado != "confirmado":
            continue
        for inscripcion, favor, contra in (
            (partida.participante1, partida.resultado.puntaje1, partida.resultado.puntaje2),
            (partida.participante2, partida.resultado.puntaje2, partida.resultado.puntaje1),
        ):
            if not inscripcion or inscripcion.id not in filas:
                continue
            fila = filas[inscripcion.id]
            fila["partidas_jugadas"] += 1
            fila["mapas_favor"] += favor
            fila["mapas_contra"] += contra
            if partida.ganador_id == inscripcion.id:
                fila["victorias"] += 1
                fila["racha"].append("G")
            else:
                fila["derrotas"] += 1
                fila["racha"].append("P")
                fila["estado"] = "Eliminado"

    campeon = torneo.campeon
    tabla = list(filas.values())
    for fila in tabla:
        fila["diferencia"] = fila["mapas_favor"] - fila["mapas_contra"]
        fila["winrate"] = (
            round(fila["victorias"] * 100 / fila["partidas_jugadas"])
            if fila["partidas_jugadas"]
            else 0
        )
        fila["ultimos"] = "".join(fila["racha"][-5:])
        if campeon and campeon.id == fila["inscripcion_id"]:
            fila["estado"] = "Campeón"
    tabla.sort(
        key=lambda f: (
            -f["victorias"],
            -f["diferencia"],
            f["derrotas"],
            -f["winrate"],
            f["nombre"].lower(),
        )
    )
    for posicion, fila in enumerate(tabla, 1):
        fila["posicion"] = posicion
    return tabla


def mi_partida(torneo, usuario):
    inscripcion = torneo.inscripcion_de(usuario)
    if not inscripcion:
        return None
    candidatas = [
        partida
        for partida in torneo.partidas
        if partida.estado == "pendiente"
        and inscripcion.id in (partida.participante1_id, partida.participante2_id)
    ]
    candidatas.sort(key=lambda p: (not p.lista_para_jugar, p.ronda, p.numero))
    return candidatas[0] if candidatas else None


def historial_usuario(usuario):
    ids = {inscripcion.id for inscripcion in usuario.inscripciones}
    for membresia in usuario.membresias:
        if membresia.estado == "activo" and membresia.equipo:
            ids.update(inscripcion.id for inscripcion in membresia.equipo.inscripciones)
    if not ids:
        return []
    inscripciones = Inscripcion.query.filter(Inscripcion.id.in_(ids)).all()
    return sorted(inscripciones, key=lambda i: i.torneo.fecha, reverse=True)


def historial_a_json(inscripciones):
    return [
        {
            "torneo": {
                "id": i.torneo.id,
                "nombre": i.torneo.nombre,
                "videojuego": i.torneo.videojuego,
                "fecha": i.torneo.fecha.isoformat(timespec="minutes"),
                "estado": i.torneo.estado,
            },
            "inscripcion_id": i.id,
            "nombre": i.nombre_mostrar,
            "inscripto_en": i.creado_en.isoformat(timespec="minutes"),
        }
        for i in inscripciones
    ]


def estadisticas():
    por_estado = dict(
        db.session.query(Torneo.estado, func.count(Torneo.id)).group_by(Torneo.estado).all()
    )
    return {
        "usuarios": Usuario.query.count(),
        "torneos": Torneo.query.count(),
        "torneos_por_estado": {clave: por_estado.get(clave, 0) for clave in ESTADOS_TORNEO},
        "inscripciones": Inscripcion.query.count(),
    }
