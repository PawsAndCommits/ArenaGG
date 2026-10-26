"""Utilidades compartidas por los controllers."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Partida, Torneo, Usuario
from services import equipos as eq
from services import torneos as sv


def obtener_o_404(db: Session, modelo, identificador: int, mensaje: str = "Recurso no encontrado."):
    objeto = db.get(modelo, identificador)
    if not objeto:
        raise HTTPException(status_code=404, detail=mensaje)
    return objeto


def serializar_partida(partida: Partida, usuario: Usuario | None = None) -> dict:
    datos = partida.to_dict()
    if usuario:
        datos.update(
            {
                "puede_reportar": partida.puede_reportar(usuario),
                "puede_confirmar": partida.puede_confirmar(usuario),
                "puede_disputar": partida.puede_disputar(usuario),
                "puede_resolver": partida.puede_resolver(usuario),
                "puede_rechazar": partida.puede_rechazar(usuario),
            }
        )
    return datos


def serializar_equipo(
    equipo, usuario: Usuario | None = None, detalle: bool = False
) -> dict:
    datos = equipo.to_dict(detalle=detalle)
    membresia = equipo.membresia_de(usuario.id) if usuario else None
    datos["mi_rol"] = eq.mi_rol(equipo, usuario)
    datos["miembro_id"] = membresia.id if membresia else None
    datos["iniciales"] = equipo.iniciales
    if detalle and not eq.puede_gestionar(equipo, usuario):
        datos["invitaciones"] = []
    return datos


def serializar_torneo(
    torneo: Torneo,
    usuario: Usuario | None = None,
    detalle: bool = False,
    db: Session | None = None,
) -> dict:
    datos = torneo.to_dict(detalle=detalle)
    if not detalle:
        return datos
    mi_inscripcion = torneo.inscripcion_de(usuario) if usuario else None
    datos["mi_inscripcion"] = mi_inscripcion.to_dict() if mi_inscripcion else None
    datos["mis_equipos"] = []
    if usuario and torneo.es_por_equipos and db is not None:
        datos["mis_equipos"] = [
            serializar_equipo(equipo, usuario)
            for equipo in eq.equipos_para_torneo(db, torneo, usuario)
        ]
    partida = sv.mi_partida(torneo, usuario)
    datos["mi_partida"] = serializar_partida(partida, usuario) if partida else None
    return datos
