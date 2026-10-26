"""Modelo de notificaciones persistentes."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, ahora, fecha_iso

if TYPE_CHECKING:
    from models.torneo import Torneo
    from models.usuario import Usuario


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    torneo_id: Mapped[int | None] = mapped_column(
        ForeignKey("torneos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=ahora, index=True
    )

    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="notificaciones")
    torneo: Mapped[Torneo | None] = relationship("Torneo")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "mensaje": self.mensaje,
            "url": self.url,
            "leida": self.leida,
            "torneo_id": self.torneo_id,
            "creada_en": fecha_iso(self.creada_en),
        }
