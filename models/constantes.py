"""Constantes de dominio compartidas por modelos y servicios."""

ROLES = ("admin", "jugador")

ESTADOS_TORNEO = {
    "proximamente": "Próximamente",
    "inscripciones_abiertas": "Inscripciones abiertas",
    "en_curso": "En curso",
    "finalizado": "Finalizado",
}

MODALIDADES = {
    "individual": "Individual",
    "equipos": "Por equipos",
}

FORMATOS = {
    "BO1": "Mejor de 1",
    "BO3": "Mejor de 3",
    "BO5": "Mejor de 5",
}

ESTADOS_PARTIDA = ("pendiente", "finalizada", "bye")
ESTADOS_RESULTADO = ("pendiente", "confirmado", "disputa")
