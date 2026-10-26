"""Base declarativa y utilidades compartidas de la base de datos."""
from datetime import datetime

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def ahora() -> datetime:
    """Fecha y hora local sin microsegundos."""
    return datetime.now().replace(microsecond=0)


def fecha_iso(valor: datetime | None) -> str | None:
    return valor.isoformat(timespec="minutes") if valor else None
