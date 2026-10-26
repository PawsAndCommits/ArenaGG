"""Modelo de resultados de partidas."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, ahora, fecha_iso

if TYPE_CHECKING:
    from models.inscripcion import Inscripcion
    from models.partida import Partida
    from models.usuario import Usuario


class Resultado(Base):
    __tablename__ = "resultados"
    __table_args__ = (
        CheckConstraint("puntaje1 >= 0 AND puntaje2 >= 0", name="puntajes"),
        CheckConstraint("puntaje1 <> puntaje2", name="sin_empate"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partida_id: Mapped[int] = mapped_column(
        ForeignKey("partidas.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    puntaje1: Mapped[int] = mapped_column(Integer, nullable=False)
    puntaje2: Mapped[int] = mapped_column(Integer, nullable=False)
    ganador_id: Mapped[int] = mapped_column(
        ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="confirmado", index=True
    )
    registrado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    confirmado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    resuelto_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    disputa_motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registrado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora)
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    partida: Mapped[Partida] = relationship("Partida", back_populates="resultado")
    ganador: Mapped[Inscripcion] = relationship(
        "Inscripcion", foreign_keys=[ganador_id]
    )
    registrado_por: Mapped[Usuario | None] = relationship(
        "Usuario", foreign_keys=[registrado_por_id]
    )
    confirmado_por: Mapped[Usuario | None] = relationship(
        "Usuario", foreign_keys=[confirmado_por_id]
    )
    resuelto_por: Mapped[Usuario | None] = relationship(
        "Usuario", foreign_keys=[resuelto_por_id]
    )

    @property
    def confirmado(self) -> bool:
        return self.estado == "confirmado"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "partida_id": self.partida_id,
            "puntaje1": self.puntaje1,
            "puntaje2": self.puntaje2,
            "ganador_inscripcion_id": self.ganador_id,
            "estado": self.estado,
            "registrado_por": self.registrado_por.username if self.registrado_por else None,
            "confirmado_por": self.confirmado_por.username if self.confirmado_por else None,
            "resuelto_por": self.resuelto_por.username if self.resuelto_por else None,
            "disputa_motivo": self.disputa_motivo,
            "registrado_en": fecha_iso(self.registrado_en),
            "confirmado_en": fecha_iso(self.confirmado_en),
            "actualizado_en": fecha_iso(self.actualizado_en),
        }
