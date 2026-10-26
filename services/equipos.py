"""Reglas de negocio de equipos, roster e invitaciones."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.base import ahora
from models import Equipo, EquipoMiembro, Inscripcion, Torneo, Usuario
from services import notificaciones as notif
from services.errors import ErrorNegocio, ErrorValidacion


def _texto(datos: dict, campo: str, por_defecto: str = "") -> str:
    valor = datos.get(campo, por_defecto)
    return str(valor if valor is not None else "").strip()


def _validar(db: Session, datos: dict, equipo: Equipo | None = None) -> dict:
    errores: dict = {}
    nombre = _texto(datos, "nombre", equipo.nombre if equipo else "")
    tag = _texto(datos, "tag", equipo.tag if equipo else "").upper()
    descripcion = _texto(datos, "descripcion", equipo.descripcion if equipo else "")

    if not 2 <= len(nombre) <= 60:
        errores["nombre"] = "El nombre del equipo debe tener entre 2 y 60 caracteres."
    else:
        objetivo = nombre.casefold()
        for otro_id, otro_nombre in db.execute(select(Equipo.id, Equipo.nombre)).all():
            if equipo and otro_id == equipo.id:
                continue
            if otro_nombre.casefold() == objetivo:
                errores["nombre"] = "Ya existe un equipo con ese nombre."
                break
    if len(tag) > 10:
        errores["tag"] = "El tag puede tener como máximo 10 caracteres."
    if len(descripcion) > 500:
        errores["descripcion"] = "La descripción puede tener como máximo 500 caracteres."
    if errores:
        raise ErrorValidacion(errores)
    return {"nombre": nombre, "tag": tag, "descripcion": descripcion}


def _equipo_con_torneo_activo(equipo: Equipo):
    return next(
        (
            inscripcion.torneo
            for inscripcion in equipo.inscripciones
            if inscripcion.torneo and inscripcion.torneo.estado != "finalizado"
        ),
        None,
    )


def _bloquear_cambios_de_roster(equipo: Equipo) -> None:
    torneo = _equipo_con_torneo_activo(equipo)
    if torneo:
        raise ErrorNegocio(
            f"No se puede cambiar el roster mientras el equipo participa en «{torneo.nombre}». "
            "Primero cancelá la inscripción o esperá a que termine el torneo.",
            409,
        )


def crear_equipo(db: Session, datos: dict, capitan: Usuario) -> Equipo:
    limpio = _validar(db, datos)
    equipo = Equipo(**limpio, capitan_id=capitan.id)
    equipo.miembros.append(
        EquipoMiembro(usuario_id=capitan.id, rol="capitan", estado="activo")
    )
    db.add(equipo)
    db.commit()
    return equipo


def actualizar_equipo(
    db: Session, equipo: Equipo, datos: dict, usuario: Usuario
) -> Equipo:
    if not puede_gestionar(equipo, usuario):
        raise ErrorNegocio("Solo el capitán puede editar el equipo.", 403)
    limpio = _validar(db, datos, equipo)
    for campo, valor in limpio.items():
        setattr(equipo, campo, valor)
    db.commit()
    return equipo


def puede_gestionar(equipo: Equipo, usuario: Usuario | None) -> bool:
    return bool(
        usuario and (usuario.es_admin or equipo.es_capitan(usuario))
    )


def invitar(
    db: Session, equipo: Equipo, username: str, invitador: Usuario
) -> EquipoMiembro:
    if not equipo.es_capitan(invitador):
        raise ErrorNegocio("Solo el capitán puede invitar jugadores.", 403)
    _bloquear_cambios_de_roster(equipo)
    usuario = db.scalar(
        select(Usuario).where(func.lower(Usuario.username) == (username or "").strip().lower())
    )
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
            usuario_id=usuario.id,
            rol="jugador",
            estado="invitado",
            invitado_por_id=invitador.id,
        )
        equipo.miembros.append(membresia)
    db.commit()
    notif.enviar_a(
        db,
        [usuario.id],
        "equipo",
        "Invitación a equipo",
        f"{invitador.username} te invitó a {equipo.nombre}.",
        url=notif.url_equipo(equipo),
    )
    return membresia


def responder_invitacion(
    db: Session, membresia: EquipoMiembro | None, usuario: Usuario, aceptar: bool
) -> EquipoMiembro:
    if not membresia or membresia.usuario_id != usuario.id:
        raise ErrorNegocio("Invitación no encontrada.", 404)
    if membresia.estado != "invitado":
        raise ErrorNegocio("Esta invitación ya fue respondida.", 409)
    equipo = membresia.equipo
    if aceptar:
        _bloquear_cambios_de_roster(equipo)
    membresia.estado = "activo" if aceptar else "rechazado"
    membresia.respondido_en = ahora()
    db.commit()
    if equipo.capitan_id and equipo.capitan_id != usuario.id:
        notif.enviar_a(
            db,
            [equipo.capitan_id],
            "equipo",
            "Respuesta a la invitación",
            f"{usuario.username} {'aceptó' if aceptar else 'rechazó'} la invitación a {equipo.nombre}.",
            url=notif.url_equipo(equipo),
        )
    return membresia


def expulsar(
    db: Session, equipo: Equipo, membresia_id: int, usuario: Usuario
) -> None:
    if not equipo.es_capitan(usuario):
        raise ErrorNegocio("Solo el capitán puede quitar jugadores.", 403)
    _bloquear_cambios_de_roster(equipo)
    membresia = db.get(EquipoMiembro, membresia_id)
    if not membresia or membresia.equipo_id != equipo.id:
        raise ErrorNegocio("Ese jugador no pertenece al equipo.", 404)
    if membresia.usuario_id == equipo.capitan_id:
        raise ErrorNegocio("No podés quitar al capitán del equipo.", 409)
    usuario_id = membresia.usuario_id
    db.delete(membresia)
    db.commit()
    notif.enviar_a(
        db,
        [usuario_id],
        "equipo",
        "Saliste del equipo",
        f"El capitán te quitó de {equipo.nombre}.",
        url=notif.url_equipos(),
    )


def salir(db: Session, equipo: Equipo, usuario: Usuario) -> None:
    membresia = equipo.membresia_de(usuario.id)
    if not membresia:
        raise ErrorNegocio("No pertenecés a este equipo.", 404)
    if equipo.capitan_id == usuario.id:
        raise ErrorNegocio(
            "El capitán no puede salir: primero eliminá el equipo o transferí la capitanía.",
            409,
        )
    _bloquear_cambios_de_roster(equipo)
    db.delete(membresia)
    db.commit()
    if equipo.capitan_id:
        notif.enviar_a(
            db,
            [equipo.capitan_id],
            "equipo",
            "Un jugador salió del equipo",
            f"{usuario.username} dejó {equipo.nombre}.",
            url=notif.url_equipo(equipo),
        )


def transferir_capitan(
    db: Session, equipo: Equipo, usuario_id: int, capitan: Usuario
) -> None:
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
    db.commit()
    notif.enviar_a(
        db,
        [nuevo.usuario_id],
        "equipo",
        "Sos el nuevo capitán",
        f"Ahora administrás {equipo.nombre}.",
        url=notif.url_equipo(equipo),
    )


def eliminar_equipo(db: Session, equipo: Equipo, usuario: Usuario) -> None:
    if not equipo.es_capitan(usuario) and not usuario.es_admin:
        raise ErrorNegocio("Solo el capitán puede eliminar el equipo.", 403)
    if equipo.inscripciones:
        raise ErrorNegocio("No se puede eliminar un equipo que ya jugó un torneo.", 409)
    db.delete(equipo)
    db.commit()


def validar_para_torneo(equipo: Equipo, torneo, usuario: Usuario) -> Equipo:
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
                m.usuario.username
                for m in equipo.miembros_activos
                if m.usuario_id in repetidos
            )
            raise ErrorNegocio(
                f"Estos jugadores ya están inscriptos con otro equipo: {nombres}.", 409
            )
    return equipo


def listar_equipos(db: Session) -> list[Equipo]:
    return list(db.scalars(select(Equipo).order_by(Equipo.nombre)).all())


def torneos_disponibles(db: Session, equipo: Equipo, usuario: Usuario) -> list[Torneo]:
    if not equipo.es_capitan(usuario) and not usuario.es_admin:
        raise ErrorNegocio("Solo el capitán puede inscribir al equipo.", 403)
    torneos = db.scalars(
        select(Torneo)
        .where(
            Torneo.modalidad == "equipos",
            Torneo.estado == "inscripciones_abiertas",
        )
        .order_by(Torneo.fecha)
    ).all()
    return [torneo for torneo in torneos if not inscripcion_de(db, equipo, torneo)]


def invitaciones_de(db: Session, usuario: Usuario) -> list[EquipoMiembro]:
    return list(
        db.scalars(
            select(EquipoMiembro)
            .where(
                EquipoMiembro.usuario_id == usuario.id,
                EquipoMiembro.estado == "invitado",
            )
            .order_by(EquipoMiembro.creado_en.desc())
        ).all()
    )


def equipos_de(db: Session, usuario: Usuario) -> list[Equipo]:
    return list(
        db.scalars(
            select(Equipo)
            .join(EquipoMiembro)
            .where(
                EquipoMiembro.usuario_id == usuario.id,
                EquipoMiembro.estado == "activo",
            )
            .order_by(Equipo.nombre)
        ).all()
    )


def equipos_para_torneo(db: Session, torneo, usuario: Usuario) -> list[Equipo]:
    return [
        equipo
        for equipo in equipos_de(db, usuario)
        if len(equipo.miembros_activos) == torneo.jugadores_por_equipo
    ]


def inscripcion_de(db: Session, equipo: Equipo, torneo):
    return db.scalar(
        select(Inscripcion).where(
            Inscripcion.torneo_id == torneo.id,
            Inscripcion.equipo_id == equipo.id,
        )
    )


def mi_rol(equipo: Equipo, usuario: Usuario | None) -> str | None:
    if not usuario:
        return None
    membresia = equipo.membresia_de(usuario.id)
    if not membresia:
        return None
    if membresia.estado == "activo":
        return membresia.rol
    return membresia.estado
