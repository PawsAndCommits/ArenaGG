"""Creación y envío de notificaciones persistentes."""
from flask import current_app, has_request_context, url_for

from extensiones import socketio
from models import Notificacion, Usuario, db


def _url(endpoint, **valores):
    if has_request_context():
        return url_for(endpoint, **valores)
    return current_app.url_map.bind("").build(endpoint, valores)


def _ids_unicos(ids):
    vistos = []
    for valor in ids:
        if valor and valor not in vistos:
            vistos.append(valor)
    return vistos


def crear(usuario_id, tipo, titulo, mensaje="", url=None, torneo_id=None):
    notificacion = Notificacion(
        usuario_id=usuario_id,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        torneo_id=torneo_id,
    )
    db.session.add(notificacion)
    return notificacion


def enviar_a(ids, tipo, titulo, mensaje="", url=None, torneo_id=None, excluir=None):
    excluidos = set(excluir or [])
    notificaciones = [
        crear(usuario_id, tipo, titulo, mensaje, url, torneo_id)
        for usuario_id in _ids_unicos(ids)
        if usuario_id not in excluidos
    ]
    db.session.commit()
    publicar(notificaciones)
    return notificaciones


def publicar(notificaciones):
    for notificacion in notificaciones:
        socketio.emit(
            "notificacion",
            notificacion.to_dict(),
            to=f"user:{notificacion.usuario_id}",
        )


def ids_de_inscripcion(inscripcion):
    if not inscripcion:
        return []
    return _ids_unicos(usuario.id for usuario in inscripcion.roster if usuario)


def ids_de_partida(partida):
    return _ids_unicos(
        ids_de_inscripcion(partida.participante1) + ids_de_inscripcion(partida.participante2)
    )


def ids_admins():
    return [usuario.id for usuario in Usuario.query.filter_by(rol="admin").all()]


def url_torneo(torneo):
    return _url("torneos.detalle", torneo_id=torneo.id)


def url_partida(partida):
    return _url("torneos.sala", torneo_id=partida.torneo_id, partida_id=partida.id)


def url_equipo(equipo):
    return _url("equipos.detalle", equipo_id=equipo.id)


def url_equipos():
    return _url("equipos.lista")


def avisar_partida(partida, tipo, titulo, mensaje, excluir=None):
    return enviar_a(
        ids_de_partida(partida),
        tipo,
        titulo,
        mensaje,
        url=url_partida(partida),
        torneo_id=partida.torneo_id,
        excluir=excluir,
    )


def avisar_torneo(torneo, tipo, titulo, mensaje, excluir=None):
    ids = []
    for inscripcion in torneo.inscripciones:
        ids.extend(ids_de_inscripcion(inscripcion))
    return enviar_a(
        ids,
        tipo,
        titulo,
        mensaje,
        url=url_torneo(torneo),
        torneo_id=torneo.id,
        excluir=excluir,
    )
