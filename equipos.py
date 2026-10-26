"""Altas, roster e invitaciones de equipos."""
from sqlalchemy import func

import notificaciones as notif
from models import Equipo, EquipoMiembro, Inscripcion, Usuario, ahora, db
from services import ErrorNegocio, ErrorValidacion


def _texto(datos, campo):
    return str(datos.get(campo) or "").strip()


def _validar(datos, equipo=None):
    errores = {}
    nombre = _texto(datos, "nombre")
    tag = _texto(datos, "tag").upper()
    descripcion = _texto(datos, "descripcion")

    if not 2 <= len(nombre) <= 60:
        errores["nombre"] = "El nombre del equipo debe tener entre 2 y 60 caracteres."
    else:
        consulta = Equipo.query.filter(func.lower(Equipo.nombre) == nombre.lower())
        if equipo:
            consulta = consulta.filter(Equipo.id != equipo.id)
        if consulta.first():
            errores["nombre"] = "Ya existe un equipo con ese nombre."
    if len(tag) > 10:
        errores["tag"] = "El tag puede tener como máximo 10 caracteres."
    if len(descripcion) > 500:
        errores["descripcion"] = "La descripción puede tener como máximo 500 caracteres."
    if errores:
        raise ErrorValidacion(errores)
    return {"nombre": nombre, "tag": tag, "descripcion": descripcion}


def _equipo_con_torneo_activo(equipo):
    return next(
        (
            inscripcion.torneo
            for inscripcion in equipo.inscripciones
            if inscripcion.torneo and inscripcion.torneo.estado != "finalizado"
        ),
        None,
    )


def _bloquear_cambios_de_roster(equipo):
    torneo = _equipo_con_torneo_activo(equipo)
    if torneo:
        raise ErrorNegocio(
            f"No se puede cambiar el roster mientras el equipo participa en «{torneo.nombre}». "
            "Primero cancelá la inscripción o esperá a que termine el torneo.",
            409,
        )


def crear_equipo(datos, capitan):
    limpio = _validar(datos)
    equipo = Equipo(**limpio, capitan_id=capitan.id)
    db.session.add(equipo)
    db.session.flush()
    db.session.add(
        EquipoMiembro(equipo_id=equipo.id, usuario_id=capitan.id, rol="capitan", estado="activo")
    )
    db.session.commit()
    return equipo


def actualizar_equipo(equipo, datos, usuario):
    if not puede_gestionar(equipo, usuario):
        raise ErrorNegocio("Solo el capitán puede editar el equipo.", 403)
    limpio = _validar(datos, equipo)
    for campo, valor in limpio.items():
        setattr(equipo, campo, valor)
    db.session.commit()
    return equipo


def puede_gestionar(equipo, usuario):
    return bool(
        usuario
        and getattr(usuario, "is_authenticated", False)
        and (getattr(usuario, "es_admin", False) or equipo.es_capitan(usuario))
    )


def invitar(equipo, username, invitador):
    if not equipo.es_capitan(invitador):
        raise ErrorNegocio("Solo el capitán puede invitar jugadores.", 403)
    _bloquear_cambios_de_roster(equipo)
    usuario = Usuario.query.filter(func.lower(Usuario.username) == username.lower()).first()
    if not usuario:
        raise ErrorNegocio("No existe un jugador con ese nombre de usuario.", 404)
    if usuario.id == equipo.capitan_id:
        raise ErrorNegocio("Ya sos el capitán del equipo.", 409)
    membresia = equipo.membresia_de(usuario.id)
    if membresia and membresia.estado == "activo":
        raise ErrorNegocio("Ese jugador ya está en el equipo.", 409)
    if membresia and membresia.estado == "invitado":
        raise ErrorNegocio("Ese jugador ya tiene una invitación pendiente.", 409)
    if membresia:
        membresia.estado = "invitado"
        membresia.rol = "jugador"
        membresia.invitado_por_id = invitador.id
        membresia.respondido_en = None
    else:
        membresia = EquipoMiembro(
            equipo_id=equipo.id,
            usuario_id=usuario.id,
            rol="jugador",
            estado="invitado",
            invitado_por_id=invitador.id,
        )
        db.session.add(membresia)
    db.session.commit()
    notif.enviar_a(
        [usuario.id],
        "equipo",
        "Invitación a equipo",
        f"{invitador.username} te invitó a {equipo.nombre}.",
        url=notif.url_equipo(equipo),
    )
    return membresia


def responder_invitacion(membresia, usuario, aceptar):
    if not membresia or membresia.usuario_id != usuario.id:
        raise ErrorNegocio("Invitación no encontrada.", 404)
    if membresia.estado != "invitado":
        raise ErrorNegocio("Esta invitación ya fue respondida.", 409)
    equipo = membresia.equipo
    if aceptar:
        _bloquear_cambios_de_roster(equipo)
    membresia.estado = "activo" if aceptar else "rechazado"
    membresia.respondido_en = ahora()
    db.session.commit()
    if equipo.capitan_id and equipo.capitan_id != usuario.id:
        notif.enviar_a(
            [equipo.capitan_id],
            "equipo",
            "Respuesta a la invitación",
            f"{usuario.username} {'aceptó' if aceptar else 'rechazó'} la invitación a {equipo.nombre}.",
            url=notif.url_equipo(equipo),
        )
    return membresia


def expulsar(equipo, membresia_id, usuario):
    if not equipo.es_capitan(usuario):
        raise ErrorNegocio("Solo el capitán puede quitar jugadores.", 403)
    _bloquear_cambios_de_roster(equipo)
    membresia = db.session.get(EquipoMiembro, membresia_id)
    if not membresia or membresia.equipo_id != equipo.id:
        raise ErrorNegocio("Ese jugador no pertenece al equipo.", 404)
    if membresia.usuario_id == equipo.capitan_id:
        raise ErrorNegocio("No podés quitar al capitán del equipo.", 409)
    usuario_id = membresia.usuario_id
    db.session.delete(membresia)
    db.session.commit()
    notif.enviar_a(
        [usuario_id],
        "equipo",
        "Saliste del equipo",
        f"El capitán te quitó de {equipo.nombre}.",
        url=notif.url_equipos(),
    )


def salir(equipo, usuario):
    membresia = equipo.membresia_de(usuario.id)
    if not membresia:
        raise ErrorNegocio("No pertenecés a este equipo.", 404)
    if equipo.capitan_id == usuario.id:
        raise ErrorNegocio(
            "El capitán no puede salir: primero eliminá el equipo o transferí la capitanía.", 409
        )
    _bloquear_cambios_de_roster(equipo)
    db.session.delete(membresia)
    db.session.commit()
    notif.enviar_a(
        [equipo.capitan_id],
        "equipo",
        "Un jugador salió del equipo",
        f"{usuario.username} dejó {equipo.nombre}.",
        url=notif.url_equipo(equipo),
    )


def transferir_capitan(equipo, usuario_id, capitan):
    if not equipo.es_capitan(capitan):
        raise ErrorNegocio("Solo el capitán puede transferir la capitanía.", 403)
    nuevo = equipo.membresia_de(usuario_id)
    if not nuevo or nuevo.estado != "activo":
        raise ErrorNegocio("El nuevo capitán debe ser un integrante activo.", 409)
    if nuevo.usuario_id == capitan.id:
        raise ErrorNegocio("Ya sos el capitán.", 409)
    anterior = equipo.membresia_de(capitan.id)
    if anterior:
        anterior.rol = "jugador"
    nuevo.rol = "capitan"
    equipo.capitan_id = nuevo.usuario_id
    db.session.commit()
    notif.enviar_a(
        [nuevo.usuario_id],
        "equipo",
        "Sos el nuevo capitán",
        f"Ahora administrás {equipo.nombre}.",
        url=notif.url_equipo(equipo),
    )


def eliminar_equipo(equipo, usuario):
    if not equipo.es_capitan(usuario) and not getattr(usuario, "es_admin", False):
        raise ErrorNegocio("Solo el capitán puede eliminar el equipo.", 403)
    if equipo.inscripciones:
        raise ErrorNegocio("No se puede eliminar un equipo que ya jugó un torneo.", 409)
    db.session.delete(equipo)
    db.session.commit()


def validar_para_torneo(equipo, torneo, usuario):
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
    return equipo


def invitaciones_de(usuario):
    return (
        EquipoMiembro.query.filter_by(usuario_id=usuario.id, estado="invitado")
        .order_by(EquipoMiembro.creado_en.desc())
        .all()
    )


def equipos_de(usuario):
    return (
        Equipo.query.join(EquipoMiembro)
        .filter(EquipoMiembro.usuario_id == usuario.id, EquipoMiembro.estado == "activo")
        .order_by(Equipo.nombre)
        .all()
    )


def equipos_para_torneo(torneo, usuario):
    equipos = equipos_de(usuario)
    return [e for e in equipos if len(e.miembros_activos) == torneo.jugadores_por_equipo]


def inscripcion_de(equipo, torneo):
    return Inscripcion.query.filter_by(torneo_id=torneo.id, equipo_id=equipo.id).first()
