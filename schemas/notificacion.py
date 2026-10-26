"""Schemas de notificaciones."""
from datetime import datetime

from pydantic import BaseModel

from schemas.common import ModeloRespuesta


class NotificacionResponse(ModeloRespuesta):
    id: int
    tipo: str
    titulo: str
    mensaje: str
    url: str | None = None
    leida: bool
    torneo_id: int | None = None
    creada_en: datetime | None = None


class NotificacionUpdate(BaseModel):
    leida: bool = True


class NotificacionesPagina(BaseModel):
    items: list[NotificacionResponse]
    total: int
    pagina: int
    por_pagina: int
    paginas: int
    sin_leer: int


class NotificacionesResumen(BaseModel):
    sin_leer: int
    recientes: list[NotificacionResponse]


class AccionNotificacionResponse(BaseModel):
    mensaje: str
    sin_leer: int
    notificacion: NotificacionResponse | None = None
