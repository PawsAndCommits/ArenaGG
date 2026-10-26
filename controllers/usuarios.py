"""Controllers de usuarios, historial y estadísticas."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from controllers.helpers import obtener_o_404
from models import Usuario
from schemas import (
    EstadisticasResponse,
    HistorialResponse,
    MensajeResponse,
    UsuarioResponse,
    UsuarioUpdate,
)
from security import AdminActual, SesionDB, UsuarioActual, UsuarioOpcional
from services import torneos as torneos_sv
from services import usuarios as sv

router = APIRouter(tags=["Usuarios"])


@router.get(
    "/usuarios/me",
    response_model=UsuarioResponse,
    summary="Perfil del usuario autenticado",
)
def mi_perfil(usuario: UsuarioActual):
    return usuario.to_dict(privado=True)


@router.get(
    "/usuarios",
    response_model=list[UsuarioResponse],
    summary="Listar usuarios (solo administradores)",
)
def listar_usuarios(db: SesionDB, _admin: AdminActual):
    usuarios = db.scalars(select(Usuario).order_by(Usuario.id)).all()
    return [usuario.to_dict(privado=True) for usuario in usuarios]


@router.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
    response_model_exclude_none=True,
    summary="Obtener el perfil de un usuario",
)
def obtener_usuario(
    usuario_id: int,
    db: SesionDB,
    actual: UsuarioOpcional,
):
    usuario = obtener_o_404(db, Usuario, usuario_id, "Usuario no encontrado.")
    privado = bool(actual and (actual.es_admin or actual.id == usuario.id))
    return usuario.to_dict(privado=privado)


@router.put(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Actualizar un usuario",
)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: SesionDB,
    actual: UsuarioActual,
):
    usuario = obtener_o_404(db, Usuario, usuario_id, "Usuario no encontrado.")
    if not (actual.es_admin or actual.id == usuario.id):
        raise HTTPException(status_code=403, detail="No podés editar este perfil.")
    usuario = sv.actualizar_usuario(db, usuario, datos.model_dump(exclude_unset=True), actual)
    return usuario.to_dict(privado=True)


@router.delete(
    "/usuarios/{usuario_id}",
    response_model=MensajeResponse,
    summary="Eliminar un usuario (solo administradores)",
)
def eliminar_usuario(usuario_id: int, db: SesionDB, admin: AdminActual):
    usuario = obtener_o_404(db, Usuario, usuario_id, "Usuario no encontrado.")
    sv.eliminar_usuario(db, usuario, admin)
    return {"mensaje": "Usuario eliminado."}


@router.get(
    "/usuarios/{usuario_id}/historial",
    response_model=HistorialResponse,
    summary="Historial de torneos de un jugador",
)
def historial_usuario(usuario_id: int, db: SesionDB):
    usuario = obtener_o_404(db, Usuario, usuario_id, "Usuario no encontrado.")
    return {
        "usuario": usuario.to_dict(),
        "historial": sv.historial_a_json(sv.historial_usuario(db, usuario)),
    }


@router.get(
    "/estadisticas",
    response_model=EstadisticasResponse,
    summary="Totales públicos de la plataforma",
)
def estadisticas(db: SesionDB):
    return torneos_sv.estadisticas(db)
