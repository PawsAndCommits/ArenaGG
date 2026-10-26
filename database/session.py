"""Engine, sesiones y dependencia de FastAPI para la base de datos."""
from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config import Settings
from database.base import Base


def crear_engine(settings: Settings) -> Engine:
    opciones: dict = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        opciones["connect_args"] = {"check_same_thread": False}

    engine = create_engine(settings.database_url, **opciones)

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def activar_claves_foraneas(conexion, _registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def crear_fabrica_sesiones(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def inicializar_base(engine: Engine) -> None:
    import models  # noqa: F401  (registra todas las tablas en la metadata)

    Base.metadata.create_all(bind=engine)


def get_db(request: Request) -> Generator[Session, None, None]:
    fabrica: sessionmaker[Session] = request.app.state.session_factory
    sesion = fabrica()
    try:
        yield sesion
    finally:
        sesion.close()
