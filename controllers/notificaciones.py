"""Controllers de notificaciones persistentes."""
import math

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, update

from controllers.helpers import obtener_o_404
from models import Notificacion
from schemas import (
    AccionNotificacionResponse,
    MensajeResponse,
    NotificacionesPagina,
    NotificacionesResumen,
)
from security import SesionDB, UsuarioActual

router = APIRouter(tags=["Notificaciones"])


def _sin_leer(db, usuario_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.leida.is_(False),
            )
        )
        or 0
    )


@router.get(
    "/notificaciones",
    response_model=NotificacionesPagina,
    summary="Bandeja de notificaciones del usuario",
)
def listar_notificaciones(
    db: SesionDB,
    usuario: UsuarioActual,
    filtro: str = Query(default="todas", pattern="^(todas|sin_leer)$"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
):
    condiciones = [Notificacion.usuario_id == usuario.id]
    if filtro == "sin_leer":
        condiciones.append(Notificacion.leida.is_(False))
    total = db.scalar(select(func.count(Notificacion.id)).where(*condiciones)) or 0
    items = db.scalars(
        select(Notificacion)
        .where(*condiciones)
        .order_by(Notificacion.creada_en.desc(), Notificacion.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return {
        "items": [notificacion.to_dict() for notificacion in items],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": math.ceil(total / por_pagina) if total else 0,
        "sin_leer": _sin_leer(db, usuario.id),
    }


@router.get(
    "/notificaciones/resumen",
    response_model=NotificacionesResumen,
    summary="Resumen para el polling de la campanita",
)
def resumen_notificaciones(db: SesionDB, usuario: UsuarioActual):
    recientes = db.scalars(
        select(Notificacion)
        .where(
            Notificacion.usuario_id == usuario.id,
            Notificacion.leida.is_(False),
        )
        .order_by(Notificacion.creada_en.desc(), Notificacion.id.desc())
        .limit(5)
    ).all()
    return {
        "sin_leer": _sin_leer(db, usuario.id),
        "recientes": [notificacion.to_dict() for notificacion in recientes],
    }


@router.post(
    "/notificaciones/{notificacion_id}/leer",
    response_model=AccionNotificacionResponse,
    summary="Marcar una notificación como leída",
)
def leer_notificacion(
    notificacion_id: int, db: SesionDB, usuario: UsuarioActual
):
    notificacion = obtener_o_404(
        db, Notificacion, notificacion_id, "Notificación no encontrada."
    )
    if notificacion.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="No autorizado.")
    notificacion.leida = True
    db.commit()
    return {
        "mensaje": "Notificación leída.",
        "sin_leer": _sin_leer(db, usuario.id),
        "notificacion": notificacion.to_dict(),
    }


@router.post(
    "/notificaciones/leer-todas",
    response_model=MensajeResponse,
    summary="Marcar todas las notificaciones como leídas",
)
def leer_todas(db: SesionDB, usuario: UsuarioActual):
    db.execute(
        update(Notificacion)
        .where(
            Notificacion.usuario_id == usuario.id,
            Notificacion.leida.is_(False),
        )
        .values(leida=True)
    )
    db.commit()
    return {"mensaje": "Notificaciones marcadas como leídas."}
