"""Rutas de equipos, roster e invitaciones."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import equipos as eq
from models import Equipo, EquipoMiembro, Torneo, db
from services import ErrorNegocio

bp = Blueprint("equipos", __name__, url_prefix="/equipos")


def _datos_formulario():
    return {
        "nombre": request.form.get("nombre", ""),
        "tag": request.form.get("tag", ""),
        "descripcion": request.form.get("descripcion", ""),
    }


def _flash_error(error, por_defecto):
    flash(getattr(error, "mensaje", por_defecto), "danger")
    for mensaje in getattr(error, "errores", {}).values():
        flash(mensaje, "danger")


@bp.route("/")
def lista():
    todos = Equipo.query.order_by(Equipo.nombre).all()
    mios = eq.equipos_de(current_user) if current_user.is_authenticated else []
    invitaciones = eq.invitaciones_de(current_user) if current_user.is_authenticated else []
    return render_template(
        "equipos/lista.html", equipos=todos, mis_equipos=mios, invitaciones=invitaciones
    )


@bp.route("/invitaciones")
@login_required
def invitaciones():
    return render_template(
        "equipos/invitaciones.html", invitaciones=eq.invitaciones_de(current_user)
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    datos, errores = {}, {}
    if request.method == "POST":
        datos = _datos_formulario()
        try:
            equipo = eq.crear_equipo(datos, current_user)
        except ErrorNegocio as error:
            db.session.rollback()
            errores = error.errores
            _flash_error(error, "No se pudo crear el equipo.")
        else:
            flash(f"Equipo «{equipo.nombre}» creado.", "success")
            return redirect(url_for("equipos.detalle", equipo_id=equipo.id))
    return render_template("equipos/form.html", equipo=None, datos=datos, errores=errores)


@bp.route("/<int:equipo_id>")
def detalle(equipo_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    torneos = []
    if current_user.is_authenticated and equipo.es_capitan(current_user):
        torneos = [
            torneo
            for torneo in Torneo.query.filter_by(
                modalidad="equipos", estado="inscripciones_abiertas"
            ).order_by(Torneo.fecha)
            if not eq.inscripcion_de(equipo, torneo)
        ]
    membresia = (
        equipo.membresia_de(current_user.id) if current_user.is_authenticated else None
    )
    return render_template(
        "equipos/detalle.html",
        equipo=equipo,
        puede_gestionar=eq.puede_gestionar(equipo, current_user),
        es_capitan=current_user.is_authenticated and equipo.es_capitan(current_user),
        membresia=membresia,
        torneos=torneos,
    )


@bp.route("/<int:equipo_id>/editar", methods=["GET", "POST"])
@login_required
def editar(equipo_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    if not eq.puede_gestionar(equipo, current_user):
        flash("Solo el capitán puede editar el equipo.", "danger")
        return redirect(url_for("equipos.detalle", equipo_id=equipo.id))
    datos = {
        "nombre": equipo.nombre,
        "tag": equipo.tag,
        "descripcion": equipo.descripcion,
    }
    errores = {}
    if request.method == "POST":
        datos = _datos_formulario()
        try:
            eq.actualizar_equipo(equipo, datos, current_user)
        except ErrorNegocio as error:
            db.session.rollback()
            errores = error.errores
            _flash_error(error, "No se pudo actualizar el equipo.")
        else:
            flash("Equipo actualizado.", "success")
            return redirect(url_for("equipos.detalle", equipo_id=equipo.id))
    return render_template("equipos/form.html", equipo=equipo, datos=datos, errores=errores)


@bp.route("/<int:equipo_id>/invitar", methods=["POST"])
@login_required
def invitar(equipo_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    try:
        eq.invitar(equipo, request.form.get("username", ""), current_user)
    except ErrorNegocio as error:
        db.session.rollback()
        _flash_error(error, "No se pudo enviar la invitación.")
    else:
        flash("Invitación enviada.", "success")
    return redirect(url_for("equipos.detalle", equipo_id=equipo.id))


@bp.route("/<int:equipo_id>/invitaciones/<int:membresia_id>/<accion>", methods=["POST"])
@login_required
def responder(equipo_id, membresia_id, accion):
    if accion not in ("aceptar", "rechazar"):
        flash("Acción inválida.", "danger")
        return redirect(url_for("equipos.lista"))
    equipo = db.get_or_404(Equipo, equipo_id)
    membresia = db.session.get(EquipoMiembro, membresia_id)
    if not membresia or membresia.equipo_id != equipo.id:
        flash("Invitación no encontrada.", "danger")
        return redirect(url_for("equipos.lista"))
    try:
        eq.responder_invitacion(membresia, current_user, accion == "aceptar")
    except ErrorNegocio as error:
        db.session.rollback()
        _flash_error(error, "No se pudo responder la invitación.")
    else:
        flash(
            "Invitación aceptada." if accion == "aceptar" else "Invitación rechazada.",
            "success",
        )
    return redirect(request.referrer or url_for("equipos.lista"))


@bp.route("/<int:equipo_id>/expulsar/<int:membresia_id>", methods=["POST"])
@login_required
def expulsar(equipo_id, membresia_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    try:
        eq.expulsar(equipo, membresia_id, current_user)
    except ErrorNegocio as error:
        db.session.rollback()
        _flash_error(error, "No se pudo quitar al jugador.")
    else:
        flash("Jugador quitado del equipo.", "success")
    return redirect(url_for("equipos.detalle", equipo_id=equipo.id))


@bp.route("/<int:equipo_id>/salir", methods=["POST"])
@login_required
def salir(equipo_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    try:
        eq.salir(equipo, current_user)
    except ErrorNegocio as error:
        db.session.rollback()
        _flash_error(error, "No se pudo salir del equipo.")
    else:
        flash("Saliste del equipo.", "success")
    return redirect(url_for("equipos.lista"))


@bp.route("/<int:equipo_id>/capitan/<int:usuario_id>", methods=["POST"])
@login_required
def transferir(equipo_id, usuario_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    try:
        eq.transferir_capitan(equipo, usuario_id, current_user)
    except ErrorNegocio as error:
        db.session.rollback()
        _flash_error(error, "No se pudo transferir la capitanía.")
    else:
        flash("Capitanía transferida.", "success")
    return redirect(url_for("equipos.detalle", equipo_id=equipo.id))


@bp.route("/<int:equipo_id>/eliminar", methods=["POST"])
@login_required
def eliminar(equipo_id):
    equipo = db.get_or_404(Equipo, equipo_id)
    try:
        eq.eliminar_equipo(equipo, current_user)
    except ErrorNegocio as error:
        db.session.rollback()
        _flash_error(error, "No se pudo eliminar el equipo.")
        return redirect(url_for("equipos.detalle", equipo_id=equipo.id))
    flash("Equipo eliminado.", "success")
    return redirect(url_for("equipos.lista"))
