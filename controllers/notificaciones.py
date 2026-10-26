"""Controllers de notificaciones persistentes."""
import math

from fastapi import APIRouter, Query

from controllers.helpers import obtener_o_404
from models import Notificacion
from schemas import (
    AccionNotificacionResponse,
    MensajeResponse,
    NotificacionesPagina,
    NotificacionesResumen,
)
from security import SesionDB, UsuarioActual
from services import notificaciones as sv

router = APIRouter(tags=["Notificaciones"])


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
    items, total = sv.bandeja(db, usuario, filtro == "sin_leer", pagina, por_pagina)
    return {
        "items": [notificacion.to_dict() for notificacion in items],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": math.ceil(total / por_pagina) if total else 0,
        "sin_leer": sv.contar_sin_leer(db, usuario.id),
    }


@router.get(
    "/notificaciones/resumen",
    response_model=NotificacionesResumen,
    summary="Resumen para el polling de la campanita",
)
def resumen_notificaciones(db: SesionDB, usuario: UsuarioActual):
    return {
        "sin_leer": sv.contar_sin_leer(db, usuario.id),
        "recientes": [
            notificacion.to_dict() for notificacion in sv.recientes_sin_leer(db, usuario)
        ],
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
    notificacion = sv.marcar_leida(db, notificacion, usuario)
    return {
        "mensaje": "Notificación leída.",
        "sin_leer": sv.contar_sin_leer(db, usuario.id),
        "notificacion": notificacion.to_dict(),
    }


@router.post(
    "/notificaciones/leer-todas",
    response_model=MensajeResponse,
    summary="Marcar todas las notificaciones como leídas",
)
def leer_todas(db: SesionDB, usuario: UsuarioActual):
    sv.marcar_todas_leidas(db, usuario)
    return {"mensaje": "Notificaciones marcadas como leídas."}
