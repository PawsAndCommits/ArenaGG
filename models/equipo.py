"""Modelos de equipos y sus integrantes."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, ahora, fecha_iso

if TYPE_CHECKING:
    from models.inscripcion import Inscripcion
    from models.usuario import Usuario


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (
        UniqueConstraint("nombre", name="nombre"),
        CheckConstraint("length(nombre) >= 2", name="nombre_largo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    capitan_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora)

    capitan: Mapped[Usuario | None] = relationship(
        "Usuario", back_populates="equipos_capitan", foreign_keys=[capitan_id]
    )
    miembros: Mapped[list[EquipoMiembro]] = relationship(
        "EquipoMiembro",
        back_populates="equipo",
        cascade="all, delete-orphan",
        order_by="EquipoMiembro.creado_en",
    )
    inscripciones: Mapped[list[Inscripcion]] = relationship(
        "Inscripcion", back_populates="equipo"
    )

    @property
    def miembros_activos(self) -> list[EquipoMiembro]:
        return [m for m in self.miembros if m.estado == "activo"]

    @property
    def invitaciones_pendientes(self) -> list[EquipoMiembro]:
        return [m for m in self.miembros if m.estado == "invitado"]

    @property
    def iniciales(self) -> str:
        partes = [p for p in self.nombre.replace("-", " ").split() if p]
        if not partes:
            return "GG"
        return "".join(p[0] for p in partes[:2]).upper()

    def miembro_activo(self, usuario_id: int) -> bool:
        return any(
            m.usuario_id == usuario_id and m.estado == "activo" for m in self.miembros
        )

    def membresia_de(self, usuario_id: int) -> EquipoMiembro | None:
        return next((m for m in self.miembros if m.usuario_id == usuario_id), None)

    def es_capitan(self, usuario) -> bool:
        return bool(usuario and getattr(usuario, "id", None) == self.capitan_id)

    def to_dict(self, detalle: bool = False) -> dict:
        datos = {
            "id": self.id,
            "nombre": self.nombre,
            "tag": self.tag,
            "descripcion": self.descripcion,
            "capitan_id": self.capitan_id,
            "capitan": self.capitan.username if self.capitan else None,
            "miembros": len(self.miembros_activos),
            "creado_en": fecha_iso(self.creado_en),
        }
        if detalle:
            datos["roster"] = [m.to_dict() for m in self.miembros_activos]
            datos["invitaciones"] = [m.to_dict() for m in self.invitaciones_pendientes]
            datos["inscripciones"] = [
                {
                    "id": inscripcion.id,
                    "torneo": {
                        "id": inscripcion.torneo.id,
                        "nombre": inscripcion.torneo.nombre,
                        "videojuego": inscripcion.torneo.videojuego,
                        "fecha": fecha_iso(inscripcion.torneo.fecha),
                        "estado": inscripcion.torneo.estado,
                        "estado_texto": inscripcion.torneo.estado_texto,
                    },
                }
                for inscripcion in self.inscripciones
            ]
        return datos


class EquipoMiembro(Base):
    __tablename__ = "equipo_miembros"
    __table_args__ = (
        UniqueConstraint("equipo_id", "usuario_id", name="equipo_usuario"),
        CheckConstraint("rol IN ('capitan', 'jugador')", name="rol"),
        CheckConstraint(
            "estado IN ('activo', 'invitado', 'rechazado')", name="estado"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rol: Mapped[str] = mapped_column(String(10), nullable=False, default="jugador")
    estado: Mapped[str] = mapped_column(
        String(10), nullable=False, default="activo", index=True
    )
    invitado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora)
    respondido_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    equipo: Mapped[Equipo] = relationship("Equipo", back_populates="miembros")
    usuario: Mapped[Usuario] = relationship(
        "Usuario", back_populates="membresias", foreign_keys=[usuario_id]
    )
    invitado_por: Mapped[Usuario | None] = relationship(
        "Usuario", foreign_keys=[invitado_por_id]
    )

    @property
    def es_capitan(self) -> bool:
        return self.rol == "capitan"

    @property
    def activo(self) -> bool:
        return self.estado == "activo"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "equipo_id": self.equipo_id,
            "usuario_id": self.usuario_id,
            "username": self.usuario.username if self.usuario else None,
            "rol": self.rol,
            "estado": self.estado,
            "invitado_por": self.invitado_por.username if self.invitado_por else None,
            "creado_en": fecha_iso(self.creado_en),
        }
