"""Schemas de torneos, inscripciones, partidas y resultados."""
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import ModeloRespuesta
from schemas.equipo import EquipoResponse


class TorneoCreate(BaseModel):
    nombre: str = ""
    descripcion: str = ""
    videojuego: str = ""
    fecha: datetime | None = None
    cupo_maximo: int = 2
    estado: str = "inscripciones_abiertas"
    modalidad: str = "individual"
    jugadores_por_equipo: int | None = None
    destacado: bool = False
    formato: str = "BO1"
    reglas: str = ""
    premio: str = ""


class TorneoUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    videojuego: str | None = None
    fecha: datetime | None = None
    cupo_maximo: int | None = None
    estado: str | None = None
    modalidad: str | None = None
    jugadores_por_equipo: int | None = None
    destacado: bool | None = None
    formato: str | None = None
    reglas: str | None = None
    premio: str | None = None


class InscripcionCreate(BaseModel):
    equipo_id: int | None = None


class InscripcionUpdate(BaseModel):
    equipo_id: int | None = None


class InscripcionEquipo(BaseModel):
    id: int
    nombre: str
    tag: str
    capitan_id: int | None = None


class InscripcionResponse(ModeloRespuesta):
    id: int
    torneo_id: int
    usuario: dict
    equipo_id: int | None = None
    equipo: EquipoResponse | None = None
    nombre: str
    nombre_equipo: str | None = None
    integrantes: str | None = None
    inscripto_en: datetime | None = None
    roster: list[dict] = Field(default_factory=list)


class ParticipanteResponse(BaseModel):
    inscripcion_id: int
    usuario_id: int
    equipo_id: int | None = None
    nombre: str
    capitan_id: int | None = None
    roster: list[dict] = Field(default_factory=list)


class ResultadoCreate(BaseModel):
    puntaje1: int
    puntaje2: int


class ResultadoUpdate(BaseModel):
    puntaje1: int
    puntaje2: int


class DisputaCreate(BaseModel):
    motivo: str = ""


class PartidaProgramar(BaseModel):
    fecha_programada: datetime | None = None


class PartidaUpdate(BaseModel):
    fecha_programada: datetime | None = None


class ResultadoResponse(ModeloRespuesta):
    id: int
    partida_id: int
    puntaje1: int
    puntaje2: int
    ganador_inscripcion_id: int
    estado: str
    registrado_por: str | None = None
    confirmado_por: str | None = None
    resuelto_por: str | None = None
    disputa_motivo: str | None = None
    registrado_en: datetime | None = None
    confirmado_en: datetime | None = None
    actualizado_en: datetime | None = None


class PartidaResponse(ModeloRespuesta):
    id: int
    torneo_id: int
    ronda: int
    nombre_ronda: str
    numero: int
    estado: str
    estado_texto: str
    estado_clase: str
    lista_para_jugar: bool = False
    fecha_programada: datetime | None = None
    participante1: ParticipanteResponse | None = None
    participante2: ParticipanteResponse | None = None
    ganador: ParticipanteResponse | None = None
    resultado: ResultadoResponse | None = None
    puede_reportar: bool = False
    puede_confirmar: bool = False
    puede_disputar: bool = False
    puede_resolver: bool = False
    puede_rechazar: bool = False


class TorneoResponse(ModeloRespuesta):
    id: int
    nombre: str
    descripcion: str
    videojuego: str
    fecha: datetime | None = None
    cupo_maximo: int
    inscriptos: int
    cupos_disponibles: int
    esta_completo: bool = False
    porcentaje_ocupado: int = 0
    estado: str
    estado_texto: str
    modalidad: str
    modalidad_texto: str
    jugadores_por_equipo: int | None = None
    formato: str
    formato_texto: str
    premio: str
    destacado: bool
    acepta_inscripciones: bool
    tiene_partidas: bool = False
    campeon: InscripcionResponse | None = None
    creado_por_id: int | None = None
    puede_gestionar: bool = False
    es_organizador: bool = False
    creado_por: str | None = None
    creado_en: datetime | None = None
    iniciado_en: datetime | None = None
    total_rondas: int | None = None
    reglas: str | None = None
    mi_inscripcion: InscripcionResponse | None = None
    mis_equipos: list["EquipoResponse"] = Field(default_factory=list)
    mi_partida: PartidaResponse | None = None


class ParticipantesResponse(BaseModel):
    torneo_id: int
    cupo_maximo: int
    inscriptos: int
    cupos_disponibles: int
    participantes: list[InscripcionResponse]


class PosicionResponse(BaseModel):
    posicion: int
    inscripcion_id: int
    nombre: str
    equipo: str | None = None
    usuario_id: int
    victorias: int
    derrotas: int
    partidas_jugadas: int
    mapas_favor: int
    mapas_contra: int
    diferencia: int
    winrate: int
    ultimos: str
    estado: str


class PosicionesResponse(BaseModel):
    torneo_id: int
    posiciones: list[PosicionResponse]


class PartidasResponse(BaseModel):
    torneo_id: int
    partidas: list[PartidaResponse]


class MiPartidaResponse(BaseModel):
    torneo_id: int
    partida: PartidaResponse | None = None
