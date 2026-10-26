"""Modelo de usuarios."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, ahora, fecha_iso

if TYPE_CHECKING:
    from models.equipo import Equipo, EquipoMiembro
    from models.inscripcion import Inscripcion
    from models.notificacion import Notificacion


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'jugador')", name="rol"),
        CheckConstraint("length(username) >= 3", name="username_largo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rol: Mapped[str] = mapped_column(String(10), nullable=False, default="jugador")
    juegos_favoritos: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora)

    inscripciones: Mapped[list[Inscripcion]] = relationship(
        "Inscripcion",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )
    notificaciones: Mapped[list[Notificacion]] = relationship(
        "Notificacion",
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Notificacion.creada_en.desc()",
    )
    equipos_capitan: Mapped[list[Equipo]] = relationship(
        "Equipo",
        back_populates="capitan",
        foreign_keys="Equipo.capitan_id",
    )
    membresias: Mapped[list[EquipoMiembro]] = relationship(
        "EquipoMiembro",
        back_populates="usuario",
        cascade="all, delete-orphan",
        foreign_keys="EquipoMiembro.usuario_id",
    )

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"

    @property
    def tiene_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def lista_juegos(self) -> list[str]:
        return [juego.strip() for juego in self.juegos_favoritos.split(",") if juego.strip()]

    def to_dict(self, privado: bool = False) -> dict:
        datos = {
            "id": self.id,
            "username": self.username,
            "rol": self.rol,
            "juegos_favoritos": self.lista_juegos,
            "creado_en": fecha_iso(self.creado_en),
        }
        if privado:
            datos["email"] = self.email
            datos["tiene_password"] = self.tiene_password
        return datos
