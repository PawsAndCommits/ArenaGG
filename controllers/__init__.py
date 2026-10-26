"""Routers de la API."""
from controllers import auth, equipos, notificaciones, torneos, usuarios

ROUTERS = [
    auth.router,
    usuarios.router,
    torneos.router,
    equipos.router,
    notificaciones.router,
]
