"""Bandeja de notificaciones del jugador."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Notificacion, db
from seguridad import destino_seguro

bp = Blueprint("notificaciones", __name__, url_prefix="/notificaciones")


@bp.route("/")
@login_required
def lista():
    filtro = request.args.get("filtro", "todas")
    consulta = Notificacion.query.filter_by(usuario_id=current_user.id)
    if filtro == "sin_leer":
        consulta = consulta.filter_by(leida=False)
    pagina = consulta.order_by(Notificacion.creada_en.desc()).paginate(
        page=request.args.get("pagina", 1, type=int), per_page=20, error_out=False
    )
    return render_template(
        "notificaciones/lista.html",
        pagina=pagina,
        filtro=filtro,
        sin_leer=Notificacion.query.filter_by(usuario_id=current_user.id, leida=False).count(),
    )


@bp.route("/<int:notificacion_id>/leer", methods=["POST"])
@login_required
def leer(notificacion_id):
    notificacion = db.get_or_404(Notificacion, notificacion_id)
    if notificacion.usuario_id != current_user.id:
        return jsonify({"error": "No autorizado."}), 403
    notificacion.leida = True
    db.session.commit()
    if request.headers.get("Accept") == "application/json":
        return jsonify({"ok": True, "sin_leer": _sin_leer()})
    return redirect(destino_seguro(notificacion.url, url_for("notificaciones.lista")))


@bp.route("/<int:notificacion_id>/abrir", methods=["POST"])
@login_required
def abrir(notificacion_id):
    notificacion = db.get_or_404(Notificacion, notificacion_id)
    if notificacion.usuario_id != current_user.id:
        return jsonify({"error": "No autorizado."}), 403
    notificacion.leida = True
    db.session.commit()
    destino = notificacion.url or url_for("notificaciones.lista")
    return redirect(destino_seguro(destino, url_for("notificaciones.lista")))


@bp.route("/leer-todas", methods=["POST"])
@login_required
def leer_todas():
    Notificacion.query.filter_by(usuario_id=current_user.id, leida=False).update({"leida": True})
    db.session.commit()
    if request.headers.get("Accept") == "application/json":
        return jsonify({"ok": True, "sin_leer": 0})
    return redirect(request.referrer or url_for("notificaciones.lista"))


def _sin_leer():
    return Notificacion.query.filter_by(usuario_id=current_user.id, leida=False).count()
