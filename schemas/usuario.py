"""Schemas de usuarios, historial y estadísticas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import ModeloRespuesta


class UsuarioCreate(BaseModel):
    username: str = ""
    email: str = ""
    password: str = ""
    password_confirmacion: str | None = None
    juegos_favoritos: str | list[str] | None = None


class UsuarioUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None
    password_actual: str | None = None
    password_confirmacion: str | None = None
    juegos_favoritos: str | list[str] | None = None
    rol: str | None = None


class UsuarioResponse(ModeloRespuesta):
    id: int
    username: str
    email: str | None = None
    rol: str
    juegos_favoritos: list[str] = Field(default_factory=list)
    creado_en: datetime | None = None
    tiene_password: bool | None = None


class UsuarioResumen(ModeloRespuesta):
    id: int
    username: str


class HistorialTorneo(BaseModel):
    id: int
    nombre: str
    videojuego: str
    fecha: datetime
    estado: str


class HistorialItem(BaseModel):
    torneo: HistorialTorneo
    inscripcion_id: int
    nombre: str
    inscripto_en: datetime


class HistorialResponse(BaseModel):
    usuario: UsuarioResponse
    historial: list[HistorialItem]


class EstadisticasResponse(BaseModel):
    usuarios: int
    torneos: int
    torneos_por_estado: dict[str, int]
    inscripciones: int
