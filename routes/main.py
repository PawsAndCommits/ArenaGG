"""Página principal."""
from flask import Blueprint, render_template

import services as sv
from models import Torneo

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    destacados = (
        Torneo.query.filter(Torneo.destacado.is_(True), Torneo.estado != "finalizado")
        .order_by(Torneo.fecha)
        .limit(3)
        .all()
    )
    abiertos = (
        Torneo.query.filter_by(estado="inscripciones_abiertas").order_by(Torneo.fecha).limit(6).all()
    )
    return render_template(
        "index.html",
        destacados=destacados,
        abiertos=abiertos,
        stats=sv.estadisticas(),
    )
