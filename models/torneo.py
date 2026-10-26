"""Modelo de torneos."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, ahora, fecha_iso
from models.constantes import ESTADOS_TORNEO, FORMATOS, MODALIDADES

if TYPE_CHECKING:
    from models.inscripcion import Inscripcion
    from models.partida import Partida
    from models.usuario import Usuario


class Torneo(Base):
    __tablename__ = "torneos"
    __table_args__ = (
        CheckConstraint("cupo_maximo BETWEEN 2 AND 128", name="cupo"),
        CheckConstraint(
            "estado IN ('proximamente', 'inscripciones_abiertas', 'en_curso', 'finalizado')",
            name="estado",
        ),
        CheckConstraint("modalidad IN ('individual', 'equipos')", name="modalidad"),
        CheckConstraint(
            "jugadores_por_equipo IS NULL OR jugadores_por_equipo BETWEEN 2 AND 10",
            name="jugadores_equipo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    videojuego: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cupo_maximo: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, default="proximamente", index=True
    )
    modalidad: Mapped[str] = mapped_column(String(15), nullable=False, default="individual")
    jugadores_por_equipo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    destacado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False, default="BO1")
    reglas: Mapped[str] = mapped_column(Text, nullable=False, default="")
    premio: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    total_rondas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iniciado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora)

    creado_por: Mapped[Usuario | None] = relationship("Usuario")
    inscripciones: Mapped[list[Inscripcion]] = relationship(
        "Inscripcion",
        back_populates="torneo",
        cascade="all, delete-orphan",
        order_by="Inscripcion.creado_en",
    )
    partidas: Mapped[list[Partida]] = relationship(
        "Partida",
        back_populates="torneo",
        cascade="all, delete-orphan",
        order_by="[Partida.ronda, Partida.numero]",
    )

    @property
    def estado_texto(self) -> str:
        return ESTADOS_TORNEO.get(self.estado, self.estado)

    @property
    def modalidad_texto(self) -> str:
        return MODALIDADES.get(self.modalidad, self.modalidad)

    @property
    def formato_texto(self) -> str:
        return FORMATOS.get(self.formato, self.formato)

    @property
    def es_por_equipos(self) -> bool:
        return self.modalidad == "equipos"

    @property
    def inscriptos(self) -> int:
        return len(self.inscripciones)

    @property
    def cupos_disponibles(self) -> int:
        return max(self.cupo_maximo - self.inscriptos, 0)

    @property
    def esta_completo(self) -> bool:
        return self.inscriptos >= self.cupo_maximo

    @property
    def porcentaje_ocupado(self) -> int:
        return round(self.inscriptos * 100 / self.cupo_maximo) if self.cupo_maximo else 0

    @property
    def acepta_inscripciones(self) -> bool:
        return self.estado == "inscripciones_abiertas" and not self.esta_completo

    @property
    def tiene_partidas(self) -> bool:
        return len(self.partidas) > 0

    @property
    def final(self):
        total = self.total_rondas or max((p.ronda for p in self.partidas), default=0)
        if not total:
            return None
        return next((p for p in self.partidas if p.ronda == total), None)

    @property
    def campeon(self):
        final = self.final
        if final and final.estado == "finalizada":
            return final.ganador
        return None

    @property
    def partidas_pendientes(self):
        return [p for p in self.partidas if p.estado == "pendiente"]

    def puede_gestionar(self, usuario) -> bool:
        if not usuario or not getattr(usuario, "id", None):
            return False
        return bool(getattr(usuario, "es_admin", False)) or self.creado_por_id == usuario.id

    def inscripcion_de(self, usuario):
        if not usuario or not getattr(usuario, "id", None):
            return None
        for inscripcion in self.inscripciones:
            if inscripcion.usuario_id == usuario.id:
                return inscripcion
            if inscripcion.equipo and inscripcion.equipo.miembro_activo(usuario.id):
                return inscripcion
        return None

    def to_dict(self, detalle: bool = False) -> dict:
        campeon = self.campeon
        datos = {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "videojuego": self.videojuego,
            "fecha": fecha_iso(self.fecha),
            "cupo_maximo": self.cupo_maximo,
            "inscriptos": self.inscriptos,
            "cupos_disponibles": self.cupos_disponibles,
            "esta_completo": self.esta_completo,
            "porcentaje_ocupado": self.porcentaje_ocupado,
            "estado": self.estado,
            "estado_texto": self.estado_texto,
            "modalidad": self.modalidad,
            "modalidad_texto": self.modalidad_texto,
            "jugadores_por_equipo": self.jugadores_por_equipo,
            "formato": self.formato,
            "formato_texto": self.formato_texto,
            "premio": self.premio,
            "destacado": self.destacado,
            "acepta_inscripciones": self.acepta_inscripciones,
            "tiene_partidas": self.tiene_partidas,
            "campeon": campeon.to_dict() if campeon else None,
            "creado_por_id": self.creado_por_id,
        }
        if detalle:
            datos["creado_por"] = self.creado_por.username if self.creado_por else None
            datos["creado_en"] = fecha_iso(self.creado_en)
            datos["iniciado_en"] = fecha_iso(self.iniciado_en)
            datos["total_rondas"] = self.total_rondas
            datos["reglas"] = self.reglas
        return datos
