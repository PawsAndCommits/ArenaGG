"""Controllers de equipos, roster e invitaciones."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from controllers.helpers import obtener_o_404, serializar_equipo, serializar_torneo
from models import Equipo, EquipoMiembro, Torneo
from schemas import (
    EquipoCreate,
    EquipoMiembroResponse,
    EquipoResponse,
    EquipoUpdate,
    InvitacionCreate,
    InvitacionResponse,
    MensajeResponse,
    TorneoResponse,
)
from security import SesionDB, UsuarioActual, UsuarioOpcional
from services import equipos as eq

router = APIRouter(tags=["Equipos"])


def _equipo(db, equipo_id: int) -> Equipo:
    return obtener_o_404(db, Equipo, equipo_id, "Equipo no encontrado.")


def _membresia(db, equipo_id: int, membresia_id: int) -> EquipoMiembro:
    membresia = obtener_o_404(
        db, EquipoMiembro, membresia_id, "Invitación no encontrada."
    )
    if membresia.equipo_id != equipo_id:
        raise HTTPException(status_code=404, detail="La invitación no pertenece a este equipo.")
    return membresia


@router.get(
    "/equipos",
    response_model=list[EquipoResponse],
    summary="Listar equipos",
)
def listar_equipos(db: SesionDB, usuario: UsuarioOpcional):
    equipos = db.scalars(select(Equipo).order_by(Equipo.nombre)).all()
    return [serializar_equipo(equipo, usuario) for equipo in equipos]


@router.get(
    "/equipos/mios",
    response_model=list[EquipoResponse],
    summary="Equipos del usuario autenticado",
)
def mis_equipos(db: SesionDB, usuario: UsuarioActual):
    equipos = eq.equipos_de(db, usuario)
    return [serializar_equipo(equipo, usuario, detalle=True) for equipo in equipos]


@router.get(
    "/equipos/invitaciones",
    response_model=list[InvitacionResponse],
    summary="Invitaciones pendientes del usuario autenticado",
)
def invitaciones(db: SesionDB, usuario: UsuarioActual):
    return [
        {
            "id": membresia.id,
            "equipo": serializar_equipo(membresia.equipo, usuario),
            "usuario_id": membresia.usuario_id,
            "username": membresia.usuario.username,
            "invitado_por": membresia.invitado_por.username
            if membresia.invitado_por
            else None,
            "creado_en": membresia.creado_en,
        }
        for membresia in eq.invitaciones_de(db, usuario)
    ]


@router.post(
    "/equipos",
    response_model=EquipoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un equipo",
)
def crear_equipo(datos: EquipoCreate, db: SesionDB, usuario: UsuarioActual):
    equipo = eq.crear_equipo(db, datos.model_dump(), usuario)
    return serializar_equipo(equipo, usuario, detalle=True)


@router.get(
    "/equipos/{equipo_id}",
    response_model=EquipoResponse,
    summary="Detalle de un equipo",
)
def obtener_equipo(equipo_id: int, db: SesionDB, usuario: UsuarioOpcional):
    equipo = _equipo(db, equipo_id)
    return serializar_equipo(equipo, usuario, detalle=True)


@router.put(
    "/equipos/{equipo_id}",
    response_model=EquipoResponse,
    summary="Editar un equipo",
)
def actualizar_equipo(
    equipo_id: int, datos: EquipoUpdate, db: SesionDB, usuario: UsuarioActual
):
    equipo = _equipo(db, equipo_id)
    equipo = eq.actualizar_equipo(db, equipo, datos.model_dump(exclude_unset=True), usuario)
    return serializar_equipo(equipo, usuario, detalle=True)


@router.delete(
    "/equipos/{equipo_id}",
    response_model=MensajeResponse,
    summary="Eliminar un equipo",
)
def eliminar_equipo(equipo_id: int, db: SesionDB, usuario: UsuarioActual):
    equipo = _equipo(db, equipo_id)
    eq.eliminar_equipo(db, equipo, usuario)
    return {"mensaje": "Equipo eliminado."}


@router.post(
    "/equipos/{equipo_id}/invitar",
    response_model=EquipoMiembroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invitar a un jugador al equipo",
)
def invitar(
    equipo_id: int, datos: InvitacionCreate, db: SesionDB, usuario: UsuarioActual
):
    equipo = _equipo(db, equipo_id)
    membresia = eq.invitar(db, equipo, datos.username, usuario)
    return membresia.to_dict()


@router.post(
    "/equipos/{equipo_id}/invitaciones/{membresia_id}/aceptar",
    response_model=MensajeResponse,
    summary="Aceptar una invitación",
)
def aceptar_invitacion(
    equipo_id: int, membresia_id: int, db: SesionDB, usuario: UsuarioActual
):
    membresia = _membresia(db, equipo_id, membresia_id)
    eq.responder_invitacion(db, membresia, usuario, True)
    return {"mensaje": "Invitación aceptada."}


@router.post(
    "/equipos/{equipo_id}/invitaciones/{membresia_id}/rechazar",
    response_model=MensajeResponse,
    summary="Rechazar una invitación",
)
def rechazar_invitacion(
    equipo_id: int, membresia_id: int, db: SesionDB, usuario: UsuarioActual
):
    membresia = _membresia(db, equipo_id, membresia_id)
    eq.responder_invitacion(db, membresia, usuario, False)
    return {"mensaje": "Invitación rechazada."}


@router.delete(
    "/equipos/{equipo_id}/miembros/{membresia_id}",
    response_model=MensajeResponse,
    summary="Quitar a un jugador del equipo (capitán)",
)
def expulsar_miembro(
    equipo_id: int, membresia_id: int, db: SesionDB, usuario: UsuarioActual
):
    equipo = _equipo(db, equipo_id)
    eq.expulsar(db, equipo, membresia_id, usuario)
    return {"mensaje": "Jugador quitado del equipo."}


@router.post(
    "/equipos/{equipo_id}/salir",
    response_model=MensajeResponse,
    summary="Salir de un equipo",
)
def salir_equipo(equipo_id: int, db: SesionDB, usuario: UsuarioActual):
    equipo = _equipo(db, equipo_id)
    eq.salir(db, equipo, usuario)
    return {"mensaje": "Saliste del equipo."}


@router.post(
    "/equipos/{equipo_id}/capitan/{usuario_id}",
    response_model=MensajeResponse,
    summary="Transferir la capitanía",
)
def transferir_capitan(
    equipo_id: int, usuario_id: int, db: SesionDB, usuario: UsuarioActual
):
    equipo = _equipo(db, equipo_id)
    eq.transferir_capitan(db, equipo, usuario_id, usuario)
    return {"mensaje": "Capitanía transferida."}


@router.get(
    "/equipos/{equipo_id}/torneos-disponibles",
    response_model=list[TorneoResponse],
    summary="Torneos por equipos donde inscribir al equipo",
)
def torneos_disponibles(
    equipo_id: int, db: SesionDB, usuario: UsuarioActual
):
    equipo = _equipo(db, equipo_id)
    if not equipo.es_capitan(usuario) and not usuario.es_admin:
        raise HTTPException(
            status_code=403, detail="Solo el capitán puede inscribir al equipo."
        )
    torneos = db.scalars(
        select(Torneo)
        .where(
            Torneo.modalidad == "equipos",
            Torneo.estado == "inscripciones_abiertas",
        )
        .order_by(Torneo.fecha)
    ).all()
    return [
        serializar_torneo(torneo)
        for torneo in torneos
        if not eq.inscripcion_de(db, equipo, torneo)
    ]
