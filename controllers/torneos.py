"""Controllers de torneos, inscripciones, partidas y resultados."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from controllers.helpers import (
    obtener_o_404,
    serializar_equipo,
    serializar_partida,
    serializar_torneo,
    verificar_gestion_torneo,
)
from models import Equipo, Inscripcion, Partida, Torneo
from schemas import (
    DisputaCreate,
    EquipoResponse,
    InscripcionCreate,
    InscripcionResponse,
    MiPartidaResponse,
    ParticipantesResponse,
    PartidaProgramar,
    PartidaResponse,
    PartidasResponse,
    PosicionesResponse,
    ResultadoCreate,
    ResultadoUpdate,
    TorneoCreate,
    TorneoResponse,
    TorneoUpdate,
)
from security import AdminActual, SesionDB, UsuarioActual, UsuarioOpcional
from services import equipos as eq
from services import torneos as sv

router = APIRouter(tags=["Torneos"])


def _torneo(db, torneo_id: int) -> Torneo:
    return obtener_o_404(db, Torneo, torneo_id, "Torneo no encontrado.")


def _partida_del_torneo(db, torneo: Torneo, partida_id: int) -> Partida:
    partida = obtener_o_404(db, Partida, partida_id, "Partida no encontrada.")
    if partida.torneo_id != torneo.id:
        raise HTTPException(status_code=404, detail="La partida no pertenece a este torneo.")
    return partida


@router.get(
    "/torneos",
    response_model=list[TorneoResponse],
    summary="Listar y filtrar torneos",
)
def listar_torneos(
    db: SesionDB,
    usuario: UsuarioOpcional,
    estado: str | None = None,
    videojuego: str | None = None,
    modalidad: str | None = None,
    q: str | None = None,
):
    torneos = sv.buscar_torneos(db, estado, videojuego, modalidad, q)
    return [serializar_torneo(torneo, usuario) for torneo in torneos]


@router.get(
    "/videojuegos",
    response_model=list[str],
    summary="Videojuegos con torneos cargados",
)
def videojuegos(db: SesionDB):
    return sv.videojuegos_disponibles(db)


@router.post(
    "/torneos",
    response_model=TorneoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un torneo (cualquier usuario autenticado)",
)
def crear_torneo(datos: TorneoCreate, db: SesionDB, usuario: UsuarioActual):
    torneo = sv.crear_torneo(db, datos.model_dump(), usuario)
    return serializar_torneo(torneo, usuario, detalle=True, db=db)


@router.get(
    "/torneos/mios",
    response_model=list[TorneoResponse],
    summary="Torneos organizados por el usuario autenticado",
)
def mis_torneos(db: SesionDB, usuario: UsuarioActual):
    torneos = sv.buscar_torneos(db, creado_por_id=usuario.id)
    return [
        serializar_torneo(torneo, usuario, detalle=True, db=db)
        for torneo in torneos
    ]


@router.get(
    "/torneos/{torneo_id}",
    response_model=TorneoResponse,
    summary="Detalle de un torneo",
)
def obtener_torneo(torneo_id: int, db: SesionDB, usuario: UsuarioOpcional):
    torneo = _torneo(db, torneo_id)
    return serializar_torneo(torneo, usuario, detalle=True, db=db)


@router.put(
    "/torneos/{torneo_id}",
    response_model=TorneoResponse,
    summary="Actualizar un torneo (organizador o administrador)",
)
def actualizar_torneo(
    torneo_id: int, datos: TorneoUpdate, db: SesionDB, usuario: UsuarioActual
):
    torneo = _torneo(db, torneo_id)
    verificar_gestion_torneo(torneo, usuario)
    torneo = sv.actualizar_torneo(
        db, torneo, datos.model_dump(exclude_unset=True), usuario
    )
    return serializar_torneo(torneo, usuario, detalle=True, db=db)


@router.delete(
    "/torneos/{torneo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un torneo (organizador o administrador)",
)
def eliminar_torneo(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    verificar_gestion_torneo(torneo, usuario)
    sv.eliminar_torneo(db, torneo)


@router.patch(
    "/torneos/{torneo_id}/iniciar",
    response_model=TorneoResponse,
    summary="Generar la llave y comenzar el torneo (organizador o administrador)",
)
def iniciar_torneo(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    verificar_gestion_torneo(torneo, usuario)
    torneo = sv.iniciar_torneo(db, torneo)
    return serializar_torneo(torneo, usuario, detalle=True, db=db)


@router.post(
    "/torneos/{torneo_id}/reiniciar",
    response_model=TorneoResponse,
    summary="Reiniciar la llave y reabrir inscripciones (organizador o administrador)",
)
def reiniciar_torneo(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    torneo = sv.reiniciar_llave(db, torneo, usuario)
    return serializar_torneo(torneo, usuario, detalle=True, db=db)


@router.post(
    "/torneos/{torneo_id}/finalizar",
    response_model=TorneoResponse,
    summary="Finalizar un torneo en curso (organizador o administrador)",
)
def finalizar_torneo(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    torneo = sv.finalizar_torneo(db, torneo, usuario)
    return serializar_torneo(torneo, usuario, detalle=True, db=db)


@router.get(
    "/torneos/{torneo_id}/participantes",
    response_model=ParticipantesResponse,
    summary="Participantes e inscripciones de un torneo",
)
def participantes(torneo_id: int, db: SesionDB):
    torneo = _torneo(db, torneo_id)
    return {
        "torneo_id": torneo.id,
        "cupo_maximo": torneo.cupo_maximo,
        "inscriptos": torneo.inscriptos,
        "cupos_disponibles": torneo.cupos_disponibles,
        "participantes": [inscripcion.to_dict() for inscripcion in torneo.inscripciones],
    }


@router.get(
    "/torneos/{torneo_id}/posiciones",
    response_model=PosicionesResponse,
    summary="Tabla de posiciones de un torneo",
)
def posiciones(torneo_id: int, db: SesionDB):
    torneo = _torneo(db, torneo_id)
    return {"torneo_id": torneo.id, "posiciones": sv.tabla_posiciones(torneo)}


@router.get(
    "/torneos/{torneo_id}/partidas",
    response_model=PartidasResponse,
    summary="Llave completa de un torneo",
)
def partidas(torneo_id: int, db: SesionDB, usuario: UsuarioOpcional):
    torneo = _torneo(db, torneo_id)
    lista = sorted(torneo.partidas, key=lambda partida: (partida.ronda, partida.numero))
    return {
        "torneo_id": torneo.id,
        "partidas": [serializar_partida(partida, usuario) for partida in lista],
    }


@router.get(
    "/torneos/{torneo_id}/mi-partida",
    response_model=MiPartidaResponse,
    summary="Próxima partida del usuario autenticado en el torneo",
)
def mi_partida(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    partida = sv.mi_partida(torneo, usuario)
    return {
        "torneo_id": torneo.id,
        "partida": serializar_partida(partida, usuario) if partida else None,
    }


@router.get(
    "/torneos/{torneo_id}/equipos-disponibles",
    response_model=list[EquipoResponse],
    summary="Equipos del usuario que pueden inscribirse",
)
def equipos_disponibles(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    equipos = eq.equipos_para_torneo(db, torneo, usuario)
    return [
        serializar_equipo(equipo, usuario)
        for equipo in equipos
        if not eq.inscripcion_de(db, equipo, torneo)
    ]


@router.post(
    "/torneos/{torneo_id}/inscribirse",
    response_model=InscripcionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscribirse en un torneo",
)
def inscribirse(
    torneo_id: int,
    db: SesionDB,
    usuario: UsuarioActual,
    datos: InscripcionCreate | None = None,
):
    torneo = _torneo(db, torneo_id)
    inscripcion = sv.inscribir(
        db, torneo, usuario, datos.model_dump() if datos else {}
    )
    return inscripcion.to_dict()


@router.delete(
    "/torneos/{torneo_id}/inscribirse",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar la propia inscripción",
)
def cancelar_inscripcion(torneo_id: int, db: SesionDB, usuario: UsuarioActual):
    torneo = _torneo(db, torneo_id)
    sv.cancelar_inscripcion(db, torneo, usuario)


@router.get(
    "/torneos/{torneo_id}/partidas/{partida_id}",
    response_model=PartidaResponse,
    summary="Detalle de una partida",
)
def obtener_partida_torneo(
    torneo_id: int, partida_id: int, db: SesionDB, usuario: UsuarioOpcional
):
    torneo = _torneo(db, torneo_id)
    partida = _partida_del_torneo(db, torneo, partida_id)
    return serializar_partida(partida, usuario)


@router.get(
    "/partidas/{partida_id}",
    response_model=PartidaResponse,
    summary="Detalle de una partida por ID",
)
def obtener_partida(partida_id: int, db: SesionDB, usuario: UsuarioOpcional):
    partida = obtener_o_404(db, Partida, partida_id, "Partida no encontrada.")
    return serializar_partida(partida, usuario)


@router.post(
    "/torneos/{torneo_id}/partidas/{partida_id}/resultado",
    response_model=PartidaResponse,
    summary="Cargar el marcador de una partida",
)
def cargar_resultado(
    torneo_id: int,
    partida_id: int,
    datos: ResultadoCreate,
    db: SesionDB,
    usuario: UsuarioActual,
):
    torneo = _torneo(db, torneo_id)
    partida = sv.registrar_resultado_partida(
        db, torneo, partida_id, datos.model_dump(), usuario
    )
    return serializar_partida(partida, usuario)


@router.post(
    "/torneos/{torneo_id}/partidas/{partida_id}/confirmar",
    response_model=PartidaResponse,
    summary="Confirmar el resultado cargado por el rival",
)
def confirmar_resultado(
    torneo_id: int, partida_id: int, db: SesionDB, usuario: UsuarioActual
):
    torneo = _torneo(db, torneo_id)
    partida = sv.confirmar_resultado(db, torneo, partida_id, usuario)
    return serializar_partida(partida, usuario)


@router.post(
    "/torneos/{torneo_id}/partidas/{partida_id}/disputar",
    response_model=PartidaResponse,
    summary="Disputar un resultado cargado",
)
def disputar_resultado(
    torneo_id: int,
    partida_id: int,
    datos: DisputaCreate,
    db: SesionDB,
    usuario: UsuarioActual,
):
    torneo = _torneo(db, torneo_id)
    partida = sv.disputar_resultado(db, torneo, partida_id, datos.model_dump(), usuario)
    return serializar_partida(partida, usuario)


@router.post(
    "/torneos/{torneo_id}/partidas/{partida_id}/resolver",
    response_model=PartidaResponse,
    summary="Resolver una disputa (organizador o administrador)",
)
def resolver_resultado(
    torneo_id: int,
    partida_id: int,
    datos: ResultadoUpdate,
    db: SesionDB,
    usuario: UsuarioActual,
):
    torneo = _torneo(db, torneo_id)
    partida = sv.resolver_disputa(db, torneo, partida_id, datos.model_dump(), usuario)
    return serializar_partida(partida, usuario)


@router.post(
    "/torneos/{torneo_id}/partidas/{partida_id}/rechazar",
    response_model=PartidaResponse,
    summary="Rechazar un resultado (organizador o administrador)",
)
def rechazar_resultado(
    torneo_id: int, partida_id: int, db: SesionDB, usuario: UsuarioActual
):
    torneo = _torneo(db, torneo_id)
    partida = sv.rechazar_resultado(db, torneo, partida_id, usuario)
    return serializar_partida(partida, usuario)


@router.post(
    "/torneos/{torneo_id}/partidas/{partida_id}/programar",
    response_model=PartidaResponse,
    summary="Programar fecha y hora de una partida (organizador o administrador)",
)
def programar_partida(
    torneo_id: int,
    partida_id: int,
    datos: PartidaProgramar,
    db: SesionDB,
    usuario: UsuarioActual,
):
    torneo = _torneo(db, torneo_id)
    partida = sv.programar_partida(
        db, torneo, partida_id, datos.fecha_programada, usuario
    )
    return serializar_partida(partida, usuario)


@router.get(
    "/inscripciones",
    response_model=list[InscripcionResponse],
    summary="Listar inscripciones (solo administradores)",
)
def listar_inscripciones(
    db: SesionDB,
    _admin: AdminActual,
    torneo_id: int | None = Query(default=None),
):
    consulta = select(Inscripcion).order_by(Inscripcion.creado_en.desc())
    if torneo_id:
        consulta = consulta.where(Inscripcion.torneo_id == torneo_id)
    return [inscripcion.to_dict() for inscripcion in db.scalars(consulta).all()]


@router.delete(
    "/inscripciones/{inscripcion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una inscripción (organizador o administrador)",
)
def eliminar_inscripcion(
    inscripcion_id: int, db: SesionDB, usuario: UsuarioActual
):
    inscripcion = obtener_o_404(
        db, Inscripcion, inscripcion_id, "Inscripción no encontrada."
    )
    verificar_gestion_torneo(inscripcion.torneo, usuario)
    sv.eliminar_inscripcion(db, inscripcion)
