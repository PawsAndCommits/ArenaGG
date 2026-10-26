"""Rutas de torneos e inscripciones (web + API)."""
import secrets

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import services as sv
from extensiones import socketio
from models import AsignacionPartida, Inscripcion, Partida, ServidorCS2, Torneo, db
from seguridad import admin_requerido, obtener_json, token_requerido

bp = Blueprint("torneos", __name__)
api = Blueprint("api_torneos", __name__, url_prefix="/api")


def _puede_operar_partida(partida, usuario):
    """Admin, o capitán dueño de alguna de las dos inscripciones de la partida."""
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False
    if getattr(usuario, "es_admin", False):
        return True
    for inscripcion in (partida.participante1, partida.participante2):
        if inscripcion and inscripcion.usuario_id == usuario.id:
            return True
    return False


def _datos_formulario_torneo():
    datos = request.form.to_dict()
    datos.pop("csrf_token", None)
    datos["destacado"] = "destacado" in request.form
    return datos


@bp.route("/torneos")
def lista():
    filtros = {
        "estado": request.args.get("estado", ""),
        "videojuego": request.args.get("videojuego", ""),
        "modalidad": request.args.get("modalidad", ""),
        "q": request.args.get("q", "").strip(),
    }
    try:
        torneos = sv.buscar_torneos(filtros["estado"], filtros["videojuego"], filtros["modalidad"], filtros["q"])
    except sv.ErrorNegocio:
        flash("Filtro inválido.", "warning")
        torneos = sv.buscar_torneos()
    return render_template(
        "torneos/lista.html", torneos=torneos, filtros=filtros, videojuegos=sv.videojuegos_disponibles()
    )


@bp.route("/torneos/<int:torneo_id>")
def detalle(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partidas = sorted(torneo.partidas, key=lambda p: (p.ronda, p.numero))
    try:
        posiciones = sv.tabla_posiciones(torneo)
    except Exception:
        posiciones = []
    servidores = []
    if current_user.is_authenticated and current_user.es_admin:
        servidores = ServidorCS2.query.filter_by(activo=True).order_by(ServidorCS2.nombre).all()
    return render_template(
        "torneos/detalle.html",
        torneo=torneo,
        mi_inscripcion=torneo.inscripcion_de(current_user) if current_user.is_authenticated else None,
        partidas=partidas,
        posiciones=posiciones,
        servidores_disponibles=servidores,
    )


@bp.route("/torneos/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    datos, errores = {"modalidad": "individual", "estado": "inscripciones_abiertas"}, {}
    if request.method == "POST":
        datos = _datos_formulario_torneo()
        try:
            torneo = sv.crear_torneo(datos, current_user)
        except sv.ErrorNegocio as error:
            errores = error.errores
            flash(error.mensaje, "danger")
        else:
            flash(f"Torneo «{torneo.nombre}» creado.", "success")
            return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    return render_template("torneos/form.html", torneo=None, datos=datos, errores=errores)


@bp.route("/torneos/<int:torneo_id>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    errores = {}
    datos = {
        "nombre": torneo.nombre,
        "descripcion": torneo.descripcion,
        "videojuego": torneo.videojuego,
        "fecha": torneo.fecha.strftime("%Y-%m-%dT%H:%M"),
        "cupo_maximo": torneo.cupo_maximo,
        "estado": torneo.estado,
        "modalidad": torneo.modalidad,
        "jugadores_por_equipo": torneo.jugadores_por_equipo or "",
        "destacado": torneo.destacado,
    }
    if request.method == "POST":
        datos = _datos_formulario_torneo()
        try:
            sv.actualizar_torneo(torneo, datos)
        except sv.ErrorNegocio as error:
            db.session.rollback()
            errores = error.errores
            flash(error.mensaje, "danger")
        else:
            flash("Torneo actualizado.", "success")
            return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    return render_template("torneos/form.html", torneo=torneo, datos=datos, errores=errores)


@bp.route("/torneos/<int:torneo_id>/eliminar", methods=["POST"])
@admin_requerido
def eliminar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    nombre = torneo.nombre
    sv.eliminar_torneo(torneo)
    flash(f"Torneo «{nombre}» eliminado.", "success")
    return redirect(url_for("torneos.lista"))


@bp.route("/torneos/<int:torneo_id>/inscribirse", methods=["POST"])
@login_required
def inscribirse(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    sv.inscribir(torneo, current_user, request.form.to_dict())
    flash(f"¡Listo! Quedaste inscripto en «{torneo.nombre}».", "success")
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/cancelar", methods=["POST"])
@login_required
def cancelar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    sv.cancelar_inscripcion(torneo, current_user)
    flash("Cancelaste tu inscripción.", "info")
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/iniciar", methods=["POST"])
@admin_requerido
def iniciar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    try:
        sv.iniciar_torneo(torneo)
    except sv.ErrorNegocio as error:
        flash(error.mensaje, "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    flash("¡Torneo iniciado! Se generaron los cruces de la primera ronda.", "success")
    socketio.emit("torneo_iniciado", {"torneo_id": torneo.id, "nombre": torneo.nombre})
    socketio.emit("match_ready", {
        "torneo_id": torneo.id,
        "torneo": torneo.nombre,
        "mensaje": "TORNEO INICIADO - CONÉCTATE AL SERVIDOR",
    })
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/resultado", methods=["POST"])
@login_required
def cargar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        flash("La partida no pertenece a este torneo.", "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    if not _puede_operar_partida(partida, current_user):
        flash("Solo el administrador o los capitanes de la partida pueden cargar el resultado.", "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    try:
        partida = sv.registrar_resultado_partida(torneo, partida_id, request.form.to_dict(), current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        for mensaje in error.errores.values():
            flash(mensaje, "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    flash("Resultado registrado. El ganador avanzó automáticamente.", "success")
    socketio.emit("match_ready", {
        "torneo_id": torneo.id,
        "torneo": torneo.nombre,
        "partida_id": partida.id,
        "partida_numero": partida.numero,
        "ronda": partida.ronda,
    })
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/servidor", methods=["POST"])
@admin_requerido
def asignar_servidor(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        flash("La partida no pertenece a este torneo.", "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    if partida.estado != "pendiente" or not partida.lista_para_jugar:
        flash("Solo se puede asignar servidor a partidas pendientes con ambos participantes.", "warning")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))

    servidor = db.session.get(ServidorCS2, request.form.get("servidor_id", type=int) or 0)
    if not servidor or not servidor.activo:
        flash("Elegí un servidor activo.", "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))

    asignacion = AsignacionPartida.query.filter_by(partida_id=partida.id).first()
    if asignacion is None:
        asignacion = AsignacionPartida(
            partida_id=partida.id,
            servidor_id=servidor.id,
            estado="asignado",
            clave_conexion=secrets.token_urlsafe(16),
        )
        db.session.add(asignacion)
    else:
        asignacion.servidor_id = servidor.id
        asignacion.estado = "asignado"
        asignacion.actualizado_en = sv.ahora()
    db.session.commit()

    from integraciones import cs2

    try:
        cs2.preparar_partida(servidor, partida)
    except Exception as error:
        flash(f"Servidor asignado, pero falló el envío por RCON: {error}", "warning")
    else:
        flash(f"Servidor «{servidor.nombre}» asignado y partida preparada por RCON.", "success")

    socketio.emit("match_ready", {
        "torneo_id": torneo.id,
        "torneo": torneo.nombre,
        "partida_id": partida.id,
        "partida_numero": partida.numero,
        "servidor_ip": servidor.ip,
        "servidor_puerto": servidor.puerto,
        "connect": f"connect {servidor.ip}:{servidor.puerto}",
    })
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/servidor/quitar", methods=["POST"])
@admin_requerido
def quitar_servidor(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    asignacion = AsignacionPartida.query.filter_by(partida_id=partida_id).first()
    if asignacion:
        db.session.delete(asignacion)
        db.session.commit()
        flash("Servidor liberado de la partida.", "info")
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@api.route("/torneos", methods=["GET"])
def api_listar():
    torneos = sv.buscar_torneos(
        request.args.get("estado"), request.args.get("videojuego"),
        request.args.get("modalidad"), request.args.get("q"),
    )
    return jsonify([t.to_dict() for t in torneos])


@api.route("/torneos/<int:torneo_id>", methods=["GET"])
def api_obtener(torneo_id):
    return jsonify(db.get_or_404(Torneo, torneo_id).to_dict(detalle=True))


@api.route("/torneos", methods=["POST"])
@token_requerido(admin=True)
def api_crear():
    torneo = sv.crear_torneo(obtener_json(), g.usuario)
    return jsonify({"mensaje": "Torneo creado.", "torneo": torneo.to_dict(detalle=True)}), 201


@api.route("/torneos/<int:torneo_id>", methods=["PUT"])
@token_requerido(admin=True)
def api_actualizar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    sv.actualizar_torneo(torneo, obtener_json())
    return jsonify({"mensaje": "Torneo actualizado.", "torneo": torneo.to_dict(detalle=True)})


@api.route("/torneos/<int:torneo_id>", methods=["DELETE"])
@token_requerido(admin=True)
def api_eliminar(torneo_id):
    sv.eliminar_torneo(db.get_or_404(Torneo, torneo_id))
    return jsonify({"mensaje": "Torneo eliminado."})


@api.route("/torneos/<int:torneo_id>/inscribirse", methods=["POST"])
@token_requerido()
def api_inscribirse(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    datos = request.get_json(silent=True) or {}
    inscripcion = sv.inscribir(torneo, g.usuario, datos if isinstance(datos, dict) else {})
    return jsonify({"mensaje": "Inscripción realizada.", "inscripcion": inscripcion.to_dict(),
                    "cupos_disponibles": torneo.cupos_disponibles}), 201


@api.route("/torneos/<int:torneo_id>/inscribirse", methods=["DELETE"])
@token_requerido()
def api_cancelar_inscripcion(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    sv.cancelar_inscripcion(torneo, g.usuario)
    return jsonify({"mensaje": "Inscripción cancelada.", "cupos_disponibles": torneo.cupos_disponibles})


@api.route("/torneos/<int:torneo_id>/participantes", methods=["GET"])
def api_participantes(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    return jsonify({
        "torneo_id": torneo.id,
        "cupo_maximo": torneo.cupo_maximo,
        "inscriptos": torneo.inscriptos,
        "cupos_disponibles": torneo.cupos_disponibles,
        "participantes": [i.to_dict() for i in torneo.inscripciones],
    })


@api.route("/inscripciones", methods=["GET"])
@token_requerido(admin=True)
def api_listar_inscripciones():
    q = Inscripcion.query
    torneo_id = request.args.get("torneo_id", type=int)
    if torneo_id:
        q = q.filter_by(torneo_id=torneo_id)
    return jsonify([i.to_dict() for i in q.order_by(Inscripcion.creado_en.desc()).all()])


@api.route("/inscripciones/<int:inscripcion_id>", methods=["DELETE"])
@token_requerido(admin=True)
def api_eliminar_inscripcion(inscripcion_id):
    sv.eliminar_inscripcion(db.get_or_404(Inscripcion, inscripcion_id))
    return jsonify({"mensaje": "Inscripción eliminada."})


@api.route("/torneos/<int:torneo_id>/iniciar", methods=["POST"])
@token_requerido(admin=True)
def api_iniciar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    sv.iniciar_torneo(torneo)
    socketio.emit("torneo_iniciado", {"torneo_id": torneo.id, "nombre": torneo.nombre})
    socketio.emit("match_ready", {
        "torneo_id": torneo.id,
        "torneo": torneo.nombre,
        "mensaje": "TORNEO INICIADO - CONÉCTATE AL SERVIDOR",
    })
    return jsonify({"mensaje": "Torneo iniciado.", "torneo": torneo.to_dict(detalle=True)})


@api.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/resultado", methods=["POST"])
@token_requerido()
def api_cargar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        return jsonify({"error": "La partida no pertenece a este torneo."}), 400
    if not _puede_operar_partida(partida, g.usuario):
        return jsonify({"error": "Solo el administrador o los capitanes pueden cargar el resultado."}), 403
    partida = sv.registrar_resultado_partida(torneo, partida_id, obtener_json(), g.usuario)
    socketio.emit("match_ready", {
        "torneo_id": torneo.id,
        "torneo": torneo.nombre,
        "partida_id": partida.id,
        "partida_numero": partida.numero,
        "ronda": partida.ronda,
    })
    return jsonify({"mensaje": "Resultado registrado.", "partida": partida.to_dict()})
