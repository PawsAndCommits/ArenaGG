"""Fábrica de la aplicación FastAPI."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import IntegrityError

from config import Settings, get_settings
from controllers import ROUTERS
from database.session import (
    crear_engine,
    crear_fabrica_sesiones,
    inicializar_base,
)
from services.errors import ErrorNegocio

RAIZ = Path(__file__).resolve().parent
FRONTEND = RAIZ / "frontend"
INDEX = FRONTEND / "index.html"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = crear_engine(settings)
    inicializar_base(engine)
    fabrica_sesiones = crear_fabrica_sesiones(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        inicializar_base(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "API de torneos de ArenaGG. Autenticá con el botón **Authorize** "
            "usando usuario y contraseña para probar los endpoints protegidos."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Autenticación", "description": "Registro, login y token JWT."},
            {"name": "Usuarios", "description": "Perfiles, historial y estadísticas."},
            {"name": "Torneos", "description": "Llaves, inscripciones, partidas y resultados."},
            {"name": "Equipos", "description": "Roster, invitaciones y capitanía."},
            {"name": "Notificaciones", "description": "Bandeja y polling de avisos."},
        ],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = fabrica_sesiones

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    @app.exception_handler(ErrorNegocio)
    async def error_negocio(_request: Request, exc: ErrorNegocio):
        return JSONResponse(
            status_code=exc.codigo,
            content={"detail": exc.mensaje, "errores": exc.errores},
        )

    @app.exception_handler(RequestValidationError)
    async def error_validacion(_request: Request, exc: RequestValidationError):
        errores = {}
        for error in exc.errors():
            ubicacion = ".".join(
                str(parte)
                for parte in error.get("loc", ())
                if parte not in ("body", "query", "path")
            )
            errores[ubicacion or "general"] = error.get("msg", "Dato inválido.")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": "Los datos enviados no son válidos.",
                "errores": errores,
            },
        )

    @app.exception_handler(IntegrityError)
    async def error_integridad(_request: Request, _exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "La operación entra en conflicto con datos existentes.",
                "errores": {},
            },
        )

    for router in ROUTERS:
        app.include_router(router)

    if (FRONTEND / "assets").exists():
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND / "assets"),
            name="assets",
        )

    @app.get("/", include_in_schema=False)
    def spa():
        if not INDEX.exists():
            raise HTTPException(status_code=404, detail="La interfaz no está disponible.")
        return FileResponse(INDEX)

    @app.get("/index.html", include_in_schema=False)
    def spa_index():
        return spa()

    @app.get("/health", tags=["Sistema"], summary="Estado del servicio")
    def health():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    return app
