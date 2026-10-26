"""Rutas de torneos, inscripciones, partidas y resultados (web + API)."""
import secrets

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

import equipos as eq
import notificaciones as notif
import services as sv
from extensiones import socketio
from models import AsignacionPartida, Inscripcion, Partida, ServidorCS2, Torneo, ahora, db
from seguridad import admin_requerido, destino_seguro, obtener_json, token_requerido

bp = Blueprint("torneos", __name__)
api = Blueprint("api_torneos", __name__, url_prefix="/api")


def _datos_formulario_torneo():
    datos = request.form.to_dict()
    datos.pop("csrf_token", None)
    datos["destacado"] = "destacado" in request.form
    return datos


def _emitir_actualizacion(torneo):
    socketio.emit(
        "torneo_actualizado", {"torneo_id": torneo.id}, to=f"torneo:{torneo.id}"
    )


def _url_sala(partida):
    return url_for("torneos.sala", torneo_id=partida.torneo_id, partida_id=partida.id)


def _redirigir_sala(partida):
    destino = request.form.get("siguiente") or _url_sala(partida)
    return redirect(destino_seguro(destino, _url_sala(partida)))


@bp.route("/torneos")
def lista():
    filtros = {
        "estado": request.args.get("estado", ""),
        "videojuego": request.args.get("videojuego", ""),
        "modalidad": request.args.get("modalidad", ""),
        "q": request.args.get("q", "").strip(),
    }
    try:
        torneos = sv.buscar_torneos(
            filtros["estado"], filtros["videojuego"], filtros["modalidad"], filtros["q"]
        )
    except sv.ErrorNegocio:
        flash("Filtro inválido.", "warning")
        torneos = sv.buscar_torneos()
    return render_template(
        "torneos/lista.html",
        torneos=torneos,
        filtros=filtros,
        videojuegos=sv.videojuegos_disponibles(),
    )


@bp.route("/torneos/<int:torneo_id>")
def detalle(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partidas = sorted(torneo.partidas, key=lambda p: (p.ronda, p.numero))
    mi_inscripcion = (
        torneo.inscripcion_de(current_user) if current_user.is_authenticated else None
    )
    mis_equipos = []
    if current_user.is_authenticated and torneo.es_por_equipos:
        mis_equipos = eq.equipos_para_torneo(torneo, current_user)
    servidores = []
    if current_app.config["MODO_SERVIDORES"] and current_user.is_authenticated and current_user.es_admin:
        servidores = ServidorCS2.query.filter_by(activo=True).order_by(ServidorCS2.nombre).all()
    return render_template(
        "torneos/detalle.html",
        torneo=torneo,
        mi_inscripcion=mi_inscripcion,
        mi_partida=sv.mi_partida(torneo, current_user) if current_user.is_authenticated else None,
        partidas=partidas,
        posiciones=sv.tabla_posiciones(torneo),
        servidores_disponibles=servidores,
        mis_equipos=mis_equipos,
    )


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>")
def sala(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    servidores = []
    if current_app.config["MODO_SERVIDORES"] and current_user.is_authenticated and current_user.es_admin:
        servidores = ServidorCS2.query.filter_by(activo=True).order_by(ServidorCS2.nombre).all()
    return render_template(
        "torneos/sala.html",
        torneo=torneo,
        partida=partida,
        es_participante=current_user.is_authenticated and partida.incluye_usuario(current_user),
        puede_reportar=partida.puede_reportar(current_user),
        puede_confirmar=partida.puede_confirmar(current_user),
        puede_disputar=partida.puede_disputar(current_user),
        puede_resolver=partida.puede_resolver(current_user),
        puede_rechazar=partida.puede_rechazar(current_user),
        asignacion=partida.asignacion_partida,
        servidores_disponibles=servidores,
    )


@bp.route("/torneos/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    datos, errores = {"modalidad": "individual", "estado": "inscripciones_abiertas", "formato": "BO1"}, {}
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
        "reglas": torneo.reglas,
        "premio": torneo.premio,
        "videojuego": torneo.videojuego,
        "fecha": torneo.fecha.strftime("%Y-%m-%dT%H:%M"),
        "cupo_maximo": torneo.cupo_maximo,
        "estado": torneo.estado,
        "modalidad": torneo.modalidad,
        "formato": torneo.formato,
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
    try:
        sv.inscribir(torneo, current_user, request.form.to_dict())
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        for mensaje in error.errores.values():
            flash(mensaje, "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    flash(f"¡Listo! Quedaste inscripto en «{torneo.nombre}».", "success")
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/cancelar", methods=["POST"])
@login_required
def cancelar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    try:
        sv.cancelar_inscripcion(torneo, current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
    else:
        flash("Cancelaste tu inscripción.", "info")
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/iniciar", methods=["POST"])
@admin_requerido
def iniciar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    try:
        sv.iniciar_torneo(torneo)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        return redirect(url_for("torneos.detalle", torneo_id=torneo.id))
    flash("¡Torneo iniciado! La llave ya está completa.", "success")
    _emitir_actualizacion(torneo)
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/reiniciar", methods=["POST"])
@admin_requerido
def reiniciar(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    try:
        sv.reiniciar_llave(torneo, current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
    else:
        flash("Llave reiniciada. El torneo volvió a inscripciones abiertas.", "success")
        _emitir_actualizacion(torneo)
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/resultado", methods=["POST"])
@login_required
def cargar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    if not partida.puede_reportar(current_user):
        flash("No podés cargar el resultado de esta partida.", "danger")
        return redirect(_url_sala(partida))
    try:
        partida = sv.registrar_resultado_partida(
            torneo, partida_id, request.form.to_dict(), current_user
        )
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        for mensaje in error.errores.values():
            flash(mensaje, "danger")
        return redirect(_url_sala(partida))
    if partida.resultado and partida.resultado.estado == "pendiente":
        flash("Resultado cargado. Ahora tiene que confirmarlo el rival.", "success")
    else:
        flash("Resultado confirmado. El ganador avanzó automáticamente.", "success")
    _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/confirmar", methods=["POST"])
@login_required
def confirmar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    try:
        partida = sv.confirmar_resultado(torneo, partida_id, current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        return redirect(_url_sala(partida))
    flash("Resultado confirmado. ¡Gracias!", "success")
    _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/disputar", methods=["POST"])
@login_required
def disputar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    try:
        partida = sv.disputar_resultado(torneo, partida_id, request.form.to_dict(), current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        for mensaje in error.errores.values():
            flash(mensaje, "danger")
        return redirect(_url_sala(partida))
    flash("Disputa enviada. El administrador va a revisar el resultado.", "warning")
    _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/resolver", methods=["POST"])
@admin_requerido
def resolver_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    try:
        partida = sv.resolver_disputa(torneo, partida_id, request.form.to_dict(), current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        for mensaje in error.errores.values():
            flash(mensaje, "danger")
        return redirect(_url_sala(partida))
    flash("Resultado resuelto y confirmado.", "success")
    _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/rechazar", methods=["POST"])
@admin_requerido
def rechazar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    try:
        partida = sv.rechazar_resultado(torneo, partida_id, current_user)
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
        return redirect(_url_sala(partida))
    flash("Resultado rechazado. Los jugadores pueden cargar uno nuevo.", "info")
    _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/programar", methods=["POST"])
@admin_requerido
def programar_partida(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    try:
        partida = sv.programar_partida(
            torneo, partida_id, request.form.get("fecha_programada"), current_user
        )
    except sv.ErrorNegocio as error:
        db.session.rollback()
        flash(error.mensaje, "danger")
    else:
        flash("Horario de la partida actualizado.", "success")
        _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/servidor", methods=["POST"])
@admin_requerido
def asignar_servidor(torneo_id, partida_id):
    if not current_app.config["MODO_SERVIDORES"]:
        abort(404)
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        abort(404)
    if partida.estado != "pendiente" or not partida.lista_para_jugar:
        flash("Solo se puede asignar servidor a partidas pendientes con ambos participantes.", "warning")
        return redirect(_url_sala(partida))

    servidor = db.session.get(ServidorCS2, request.form.get("servidor_id", type=int) or 0)
    if not servidor or not servidor.activo:
        flash("Elegí un servidor activo.", "danger")
        return redirect(_url_sala(partida))

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
        asignacion.actualizado_en = ahora()
    db.session.commit()

    from integraciones import cs2

    try:
        cs2.preparar_partida(servidor, partida)
    except Exception as error:
        flash(f"Servidor asignado, pero falló el envío por RCON: {error}", "warning")
    else:
        flash(f"Servidor «{servidor.nombre}» asignado y partida preparada por RCON.", "success")

    notif.avisar_partida(
        partida,
        "servidor",
        "Servidor asignado",
        f"Conectate a {servidor.ip}:{servidor.puerto}.",
    )
    _emitir_actualizacion(torneo)
    return _redirigir_sala(partida)


@bp.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/servidor/quitar", methods=["POST"])
@admin_requerido
def quitar_servidor(torneo_id, partida_id):
    if not current_app.config["MODO_SERVIDORES"]:
        abort(404)
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.session.get(Partida, partida_id)
    asignacion = AsignacionPartida.query.filter_by(partida_id=partida_id).first()
    if asignacion:
        db.session.delete(asignacion)
        db.session.commit()
        flash("Servidor liberado de la partida.", "info")
    if partida and partida.torneo_id == torneo.id:
        return redirect(_url_sala(partida))
    return redirect(url_for("torneos.detalle", torneo_id=torneo.id))


@api.route("/torneos", methods=["GET"])
def api_listar():
    torneos = sv.buscar_torneos(
        request.args.get("estado"),
        request.args.get("videojuego"),
        request.args.get("modalidad"),
        request.args.get("q"),
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
    return (
        jsonify(
            {
                "mensaje": "Inscripción realizada.",
                "inscripcion": inscripcion.to_dict(),
                "cupos_disponibles": torneo.cupos_disponibles,
            }
        ),
        201,
    )


@api.route("/torneos/<int:torneo_id>/inscribirse", methods=["DELETE"])
@token_requerido()
def api_cancelar_inscripcion(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    sv.cancelar_inscripcion(torneo, g.usuario)
    return jsonify(
        {"mensaje": "Inscripción cancelada.", "cupos_disponibles": torneo.cupos_disponibles}
    )


@api.route("/torneos/<int:torneo_id>/participantes", methods=["GET"])
def api_participantes(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    return jsonify(
        {
            "torneo_id": torneo.id,
            "cupo_maximo": torneo.cupo_maximo,
            "inscriptos": torneo.inscriptos,
            "cupos_disponibles": torneo.cupos_disponibles,
            "participantes": [i.to_dict() for i in torneo.inscripciones],
        }
    )


@api.route("/torneos/<int:torneo_id>/posiciones", methods=["GET"])
def api_posiciones(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    return jsonify({"torneo_id": torneo.id, "posiciones": sv.tabla_posiciones(torneo)})


@api.route("/torneos/<int:torneo_id>/partidas", methods=["GET"])
def api_partidas(torneo_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partidas = sorted(torneo.partidas, key=lambda p: (p.ronda, p.numero))
    return jsonify({"torneo_id": torneo.id, "partidas": [p.to_dict() for p in partidas]})


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
    _emitir_actualizacion(torneo)
    return jsonify({"mensaje": "Torneo iniciado.", "torneo": torneo.to_dict(detalle=True)})


@api.route("/torneos/<int:torneo_id>/partidas/<int:partida_id>/resultado", methods=["POST"])
@token_requerido()
def api_cargar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = db.get_or_404(Partida, partida_id)
    if partida.torneo_id != torneo.id:
        return jsonify({"error": "La partida no pertenece a este torneo."}), 400
    if not partida.puede_reportar(g.usuario):
        return jsonify({"error": "No podés cargar el resultado de esta partida."}), 403
    partida = sv.registrar_resultado_partida(torneo, partida_id, obtener_json(), g.usuario)
    _emitir_actualizacion(torneo)
    return jsonify({"mensaje": "Resultado registrado.", "partida": partida.to_dict()})


@api.route(
    "/torneos/<int:torneo_id>/partidas/<int:partida_id>/confirmar", methods=["POST"]
)
@token_requerido()
def api_confirmar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = sv.confirmar_resultado(torneo, partida_id, g.usuario)
    _emitir_actualizacion(torneo)
    return jsonify({"mensaje": "Resultado confirmado.", "partida": partida.to_dict()})


@api.route(
    "/torneos/<int:torneo_id>/partidas/<int:partida_id>/disputar", methods=["POST"]
)
@token_requerido()
def api_disputar_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = sv.disputar_resultado(torneo, partida_id, obtener_json(), g.usuario)
    _emitir_actualizacion(torneo)
    return jsonify({"mensaje": "Disputa registrada.", "partida": partida.to_dict()})


@api.route(
    "/torneos/<int:torneo_id>/partidas/<int:partida_id>/resolver", methods=["POST"]
)
@token_requerido(admin=True)
def api_resolver_resultado(torneo_id, partida_id):
    torneo = db.get_or_404(Torneo, torneo_id)
    partida = sv.resolver_disputa(torneo, partida_id, obtener_json(), g.usuario)
    _emitir_actualizacion(torneo)
    return jsonify({"mensaje": "Resultado resuelto.", "partida": partida.to_dict()})
