"""Modelo de inscripciones a torneos."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, ahora, fecha_iso

if TYPE_CHECKING:
    from models.equipo import Equipo
    from models.torneo import Torneo
    from models.usuario import Usuario


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (
        UniqueConstraint("torneo_id", "usuario_id", name="torneo_usuario"),
        UniqueConstraint("torneo_id", "nombre_equipo", name="torneo_equipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    torneo_id: Mapped[int] = mapped_column(
        ForeignKey("torneos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipo_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nombre_equipo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    integrantes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora)

    torneo: Mapped[Torneo] = relationship("Torneo", back_populates="inscripciones")
    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="inscripciones")
    equipo: Mapped[Equipo | None] = relationship("Equipo", back_populates="inscripciones")

    @property
    def nombre_mostrar(self) -> str:
        if self.equipo:
            return self.equipo.nombre
        return self.nombre_equipo or self.usuario.username

    @property
    def capitan(self):
        if self.equipo and self.equipo.capitan:
            return self.equipo.capitan
        return self.usuario

    @property
    def capitan_id(self) -> int:
        return self.equipo.capitan_id if self.equipo else self.usuario_id

    @property
    def roster(self) -> list[Usuario]:
        if self.equipo:
            return [m.usuario for m in self.equipo.miembros_activos]
        return [self.usuario]

    def es_capitan(self, usuario) -> bool:
        return bool(usuario and getattr(usuario, "id", None) == self.capitan_id)

    def incluye_usuario(self, usuario) -> bool:
        if not usuario or not getattr(usuario, "id", None):
            return False
        if self.usuario_id == usuario.id:
            return True
        return bool(self.equipo and self.equipo.miembro_activo(usuario.id))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "torneo_id": self.torneo_id,
            "usuario": {"id": self.usuario.id, "username": self.usuario.username},
            "equipo_id": self.equipo_id,
            "equipo": self.equipo.to_dict() if self.equipo else None,
            "nombre": self.nombre_mostrar,
            "nombre_equipo": self.nombre_equipo,
            "integrantes": self.integrantes,
            "inscripto_en": fecha_iso(self.creado_en),
            "roster": [
                {"id": jugador.id, "username": jugador.username}
                for jugador in self.roster
                if jugador
            ],
        }

    def to_dict_corto(self) -> dict:
        return {
            "inscripcion_id": self.id,
            "usuario_id": self.usuario_id,
            "equipo_id": self.equipo_id,
            "nombre": self.nombre_mostrar,
            "capitan_id": self.capitan_id,
            "roster": [
                {"id": jugador.id, "username": jugador.username}
                for jugador in self.roster
                if jugador
            ],
        }
