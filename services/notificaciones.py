"""Creación y envío de notificaciones persistentes."""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from models import Inscripcion, Notificacion, Partida, Torneo, Usuario
from services.errors import ErrorNegocio


def contar_sin_leer(db: Session, usuario_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.leida.is_(False),
            )
        )
        or 0
    )


def bandeja(
    db: Session, usuario: Usuario, solo_sin_leer: bool, pagina: int, por_pagina: int
) -> tuple[list[Notificacion], int]:
    condiciones = [Notificacion.usuario_id == usuario.id]
    if solo_sin_leer:
        condiciones.append(Notificacion.leida.is_(False))
    total = db.scalar(select(func.count(Notificacion.id)).where(*condiciones)) or 0
    items = db.scalars(
        select(Notificacion)
        .where(*condiciones)
        .order_by(Notificacion.creada_en.desc(), Notificacion.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return list(items), total


def recientes_sin_leer(db: Session, usuario: Usuario, limite: int = 5) -> list[Notificacion]:
    return list(
        db.scalars(
            select(Notificacion)
            .where(
                Notificacion.usuario_id == usuario.id,
                Notificacion.leida.is_(False),
            )
            .order_by(Notificacion.creada_en.desc(), Notificacion.id.desc())
            .limit(limite)
        ).all()
    )


def marcar_leida(db: Session, notificacion: Notificacion, usuario: Usuario) -> Notificacion:
    if notificacion.usuario_id != usuario.id:
        raise ErrorNegocio("No autorizado.", 403)
    notificacion.leida = True
    db.commit()
    return notificacion


def marcar_todas_leidas(db: Session, usuario: Usuario) -> None:
    db.execute(
        update(Notificacion)
        .where(
            Notificacion.usuario_id == usuario.id,
            Notificacion.leida.is_(False),
        )
        .values(leida=True)
    )
    db.commit()


def _ids_unicos(ids) -> list[int]:
    vistos: list[int] = []
    for valor in ids:
        if valor and valor not in vistos:
            vistos.append(valor)
    return vistos


def crear(
    db: Session,
    usuario_id: int,
    tipo: str,
    titulo: str,
    mensaje: str = "",
    url: str | None = None,
    torneo_id: int | None = None,
) -> Notificacion:
    notificacion = Notificacion(
        usuario_id=usuario_id,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        torneo_id=torneo_id,
    )
    db.add(notificacion)
    return notificacion


def enviar_a(
    db: Session,
    ids,
    tipo: str,
    titulo: str,
    mensaje: str = "",
    url: str | None = None,
    torneo_id: int | None = None,
    excluir=None,
) -> list[Notificacion]:
    excluidos = set(excluir or [])
    notificaciones = [
        crear(db, usuario_id, tipo, titulo, mensaje, url, torneo_id)
        for usuario_id in _ids_unicos(ids)
        if usuario_id not in excluidos
    ]
    db.commit()
    return notificaciones


def ids_de_inscripcion(inscripcion: Inscripcion | None) -> list[int]:
    if not inscripcion:
        return []
    return _ids_unicos(usuario.id for usuario in inscripcion.roster if usuario)


def ids_de_partida(partida: Partida) -> list[int]:
    return _ids_unicos(
        ids_de_inscripcion(partida.participante1)
        + ids_de_inscripcion(partida.participante2)
    )


def ids_admins(db: Session) -> list[int]:
    return list(db.scalars(select(Usuario.id).where(Usuario.rol == "admin")).all())


def ids_gestion(db: Session, torneo: Torneo) -> list[int]:
    """Administradores globales más el organizador del torneo."""
    return _ids_unicos(ids_admins(db) + [torneo.creado_por_id])


def url_torneo(torneo: Torneo) -> str:
    return f"#/torneos/{torneo.id}"


def url_partida(partida: Partida) -> str:
    return f"#/torneos/{partida.torneo_id}/partidas/{partida.id}"


def url_equipo(equipo) -> str:
    return f"#/equipos/{equipo.id}"


def url_equipos() -> str:
    return "#/equipos"


def avisar_partida(
    db: Session,
    partida: Partida,
    tipo: str,
    titulo: str,
    mensaje: str,
    excluir=None,
) -> list[Notificacion]:
    return enviar_a(
        db,
        ids_de_partida(partida),
        tipo,
        titulo,
        mensaje,
        url=url_partida(partida),
        torneo_id=partida.torneo_id,
        excluir=excluir,
    )


def avisar_torneo(
    db: Session,
    torneo: Torneo,
    tipo: str,
    titulo: str,
    mensaje: str,
    excluir=None,
) -> list[Notificacion]:
    ids: list[int] = []
    for inscripcion in torneo.inscripciones:
        ids.extend(ids_de_inscripcion(inscripcion))
    return enviar_a(
        db,
        ids,
        tipo,
        titulo,
        mensaje,
        url=url_torneo(torneo),
        torneo_id=torneo.id,
        excluir=excluir,
    )
