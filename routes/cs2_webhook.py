"""Resultados enviados por el servidor de CS2."""

import hashlib
import hmac

from flask import Blueprint, current_app, jsonify, request

import services as sv
from extensiones import socketio
from models import AsignacionPartida, Partida, db

bp = Blueprint("cs2_webhook", __name__, url_prefix="/api/cs2")


def _firma_valida(cuerpo):
    secreto = current_app.config.get("CS2_WEBHOOK_SECRET") or ""
    if not secreto:
        return True  # sin secreto configurado no se pide firma
    recibida = request.headers.get("X-CS2-Signature", "")
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return bool(recibida) and hmac.compare_digest(esperada, recibida)


@bp.route("/webhook/match-result", methods=["POST"])
def match_result():
    cuerpo = request.get_data() or b""
    if not _firma_valida(cuerpo):
        return jsonify({"error": "Firma inválida."}), 401

    datos = request.get_json(silent=True) or {}
    partida_id = datos.get("partida_id")
    puntaje1 = datos.get("puntaje1")
    puntaje2 = datos.get("puntaje2")

    if not partida_id or puntaje1 is None or puntaje2 is None:
        return jsonify({"error": "Se requieren partida_id, puntaje1 y puntaje2."}), 400

    partida = db.session.get(Partida, int(partida_id))
    if not partida:
        return jsonify({"error": "Partida no encontrada."}), 404

    torneo = partida.torneo
    try:
        partida = sv.registrar_resultado_partida(
            torneo, partida.id, {"puntaje1": puntaje1, "puntaje2": puntaje2}, None
        )
    except sv.ErrorNegocio as error:
        db.session.rollback()
        return jsonify({"error": error.mensaje, "detalles": error.errores or None}), error.codigo
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error procesando el webhook de CS2")
        return jsonify({"error": "Error interno procesando el resultado."}), 500

    asignacion = AsignacionPartida.query.filter_by(partida_id=partida.id).first()
    if asignacion:
        asignacion.estado = "finalizado"
        asignacion.actualizado_en = sv.ahora()
        db.session.commit()

    socketio.emit("match_ready", {
        "torneo_id": torneo.id,
        "torneo": torneo.nombre,
        "partida_id": partida.id,
        "partida_numero": partida.numero,
        "mensaje": "RESULTADO AUTOMÁTICO RECIBIDO - GANADOR AVANZADO",
    })

    return jsonify({
        "mensaje": "Resultado procesado correctamente.",
        "partida_id": partida.id,
        "ganador": partida.ganador.nombre_mostrar if partida.ganador else None,
        "torneo_estado": torneo.estado,
    }), 200
