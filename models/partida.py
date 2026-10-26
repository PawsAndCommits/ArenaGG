"""Modelo de partidas de eliminación directa."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, fecha_iso

if TYPE_CHECKING:
    from models.inscripcion import Inscripcion
    from models.resultado import Resultado
    from models.torneo import Torneo


class Partida(Base):
    __tablename__ = "partidas"
    __table_args__ = (
        UniqueConstraint("torneo_id", "ronda", "numero", name="torneo_ronda_numero"),
        CheckConstraint("ronda >= 1 AND numero >= 1", name="ronda_numero"),
        CheckConstraint("estado IN ('pendiente', 'finalizada', 'bye')", name="estado"),
        CheckConstraint(
            "participante1_id IS NULL OR participante2_id IS NULL "
            "OR participante1_id <> participante2_id",
            name="participantes_distintos",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    torneo_id: Mapped[int] = mapped_column(
        ForeignKey("torneos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ronda: Mapped[int] = mapped_column(Integer, nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    participante1_id: Mapped[int | None] = mapped_column(
        ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=True
    )
    participante2_id: Mapped[int | None] = mapped_column(
        ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=True
    )
    ganador_id: Mapped[int | None] = mapped_column(
        ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=True
    )
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="pendiente")
    fecha_programada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    torneo: Mapped[Torneo] = relationship("Torneo", back_populates="partidas")
    participante1: Mapped[Inscripcion | None] = relationship(
        "Inscripcion", foreign_keys=[participante1_id]
    )
    participante2: Mapped[Inscripcion | None] = relationship(
        "Inscripcion", foreign_keys=[participante2_id]
    )
    ganador: Mapped[Inscripcion | None] = relationship(
        "Inscripcion", foreign_keys=[ganador_id]
    )
    resultado: Mapped[Resultado | None] = relationship(
        "Resultado", back_populates="partida", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def lista_para_jugar(self) -> bool:
        return (
            self.estado != "bye"
            and self.participante1_id is not None
            and self.participante2_id is not None
        )

    @property
    def nombre_ronda(self) -> str:
        total = self.torneo.total_rondas or max(
            (p.ronda for p in self.torneo.partidas), default=0
        )
        faltan = total - self.ronda
        nombres = {
            0: "Final",
            1: "Semifinal",
            2: "Cuartos de final",
            3: "Octavos de final",
            4: "Ronda de 32",
            5: "Ronda de 64",
        }
        return nombres.get(faltan, f"Ronda {self.ronda}")

    @property
    def estado_texto(self) -> str:
        if self.estado == "bye":
            return "Pase directo"
        if self.estado == "finalizada":
            return "Finalizada"
        if self.resultado:
            if self.resultado.estado == "pendiente":
                return "Esperando confirmación"
            if self.resultado.estado == "disputa":
                return "En disputa"
        if self.lista_para_jugar:
            return "Por jugar"
        if self.participante1_id or self.participante2_id:
            return "Esperando rival"
        return "Por definir"

    @property
    def estado_clase(self) -> str:
        if self.estado == "bye":
            return "bye"
        if self.estado == "finalizada":
            return "finalizada"
        if self.resultado and self.resultado.estado == "disputa":
            return "disputa"
        if self.resultado and self.resultado.estado == "pendiente":
            return "esperando"
        if self.lista_para_jugar:
            return "por-jugar"
        return "por-definir"

    def incluye_usuario(self, usuario) -> bool:
        return bool(
            usuario
            and getattr(usuario, "id", None)
            and (
                (self.participante1 and self.participante1.incluye_usuario(usuario))
                or (self.participante2 and self.participante2.incluye_usuario(usuario))
            )
        )

    def es_capitan(self, usuario) -> bool:
        return bool(
            usuario
            and getattr(usuario, "id", None)
            and (
                (self.participante1 and self.participante1.es_capitan(usuario))
                or (self.participante2 and self.participante2.es_capitan(usuario))
            )
        )

    def puede_reportar(self, usuario) -> bool:
        if not usuario:
            return False
        if getattr(usuario, "es_admin", False):
            return self.lista_para_jugar and self.estado == "pendiente" and not self.resultado
        return (
            self.lista_para_jugar
            and self.estado == "pendiente"
            and not self.resultado
            and self.es_capitan(usuario)
        )

    def puede_confirmar(self, usuario) -> bool:
        return bool(
            usuario
            and self.resultado
            and self.resultado.estado == "pendiente"
            and self.es_capitan(usuario)
            and self.resultado.registrado_por_id != usuario.id
        )

    def puede_disputar(self, usuario) -> bool:
        return self.puede_confirmar(usuario)

    def puede_resolver(self, usuario) -> bool:
        return bool(
            usuario
            and getattr(usuario, "es_admin", False)
            and self.resultado
            and self.resultado.estado in ("pendiente", "disputa")
        )

    def puede_rechazar(self, usuario) -> bool:
        return self.puede_resolver(usuario)

    def to_dict(self) -> dict:
        def participante(inscripcion):
            return inscripcion.to_dict_corto() if inscripcion else None

        resultado = self.resultado
        return {
            "id": self.id,
            "torneo_id": self.torneo_id,
            "ronda": self.ronda,
            "nombre_ronda": self.nombre_ronda,
            "numero": self.numero,
            "estado": self.estado,
            "estado_texto": self.estado_texto,
            "estado_clase": self.estado_clase,
            "lista_para_jugar": self.lista_para_jugar,
            "fecha_programada": fecha_iso(self.fecha_programada),
            "participante1": participante(self.participante1),
            "participante2": participante(self.participante2),
            "ganador": participante(self.ganador),
            "resultado": resultado.to_dict() if resultado else None,
        }
