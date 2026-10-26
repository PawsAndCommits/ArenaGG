"""Schemas de equipos."""
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import ModeloRespuesta


class EquipoCreate(BaseModel):
    nombre: str = ""
    tag: str = ""
    descripcion: str = ""


class EquipoUpdate(BaseModel):
    nombre: str | None = None
    tag: str | None = None
    descripcion: str | None = None


class EquipoMiembroResponse(ModeloRespuesta):
    id: int
    equipo_id: int
    usuario_id: int
    username: str | None = None
    rol: str
    estado: str
    invitado_por: str | None = None
    creado_en: datetime | None = None


class EquipoResponse(ModeloRespuesta):
    id: int
    nombre: str
    tag: str
    descripcion: str
    capitan_id: int | None = None
    capitan: str | None = None
    miembros: int
    creado_en: datetime | None = None
    roster: list[EquipoMiembroResponse] = Field(default_factory=list)
    invitaciones: list[EquipoMiembroResponse] = Field(default_factory=list)
    inscripciones: list[dict] = Field(default_factory=list)
    mi_rol: str | None = None
    miembro_id: int | None = None
    iniciales: str | None = None


class InvitacionCreate(BaseModel):
    username: str = ""


class EquipoInscripcionCreate(BaseModel):
    torneo_id: int


class InvitacionResponse(BaseModel):
    id: int
    equipo: EquipoResponse
    usuario_id: int
    username: str | None = None
    invitado_por: str | None = None
    creado_en: datetime | None = None
