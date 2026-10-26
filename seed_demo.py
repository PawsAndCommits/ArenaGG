"""Carga datos de prueba para ver la aplicación con contenido.

Uso: python seed_demo.py

    admin / Admin1234
    ShadowFox, NeoBlaze, PixelQueen, Ragnar, LunaByte, Kairo / Jugador1234
"""
from datetime import timedelta

from app import app
from models import Usuario, ahora
import services as sv

NICKS = ["ShadowFox", "NeoBlaze", "PixelQueen", "Ragnar", "LunaByte", "Kairo"]


def main():
    with app.app_context():
        if Usuario.query.first():
            print("La base ya tiene datos. Borrá la carpeta instance/ para regenerar la demo.")
            return
        admin = sv.registrar_usuario({"username": "admin", "email": "admin@demo.com", "password": "Admin1234",
                                      "juegos_favoritos": "Valorant, Tekken 8"}, rol="admin")
        jugadores = [
            sv.registrar_usuario({"username": nick, "email": f"jugador{i}@demo.com", "password": "Jugador1234",
                                  "juegos_favoritos": "Valorant, Rocket League"})
            for i, nick in enumerate(NICKS, start=1)
        ]

        def torneo(nombre, juego, dias, cupo, estado="inscripciones_abiertas", destacado=False, **extra):
            return sv.crear_torneo({"nombre": nombre, "videojuego": juego, "cupo_maximo": cupo,
                                    "fecha": (ahora() + timedelta(days=dias)).isoformat(),
                                    "estado": estado, "destacado": destacado,
                                    "descripcion": f"Torneo de {juego}. ¡Inscribite y demostrá tu nivel!",
                                    **extra}, admin)

        t1 = torneo("Rocket League Showdown", "Rocket League", 5, 8, destacado=True)
        for j in jugadores[:4]:
            sv.inscribir(t1, j)

        t2 = torneo("Duelo EA FC 25", "EA FC 25", 7, 4, destacado=True)
        for j in jugadores[:4]:
            sv.inscribir(t2, j)  # queda con el cupo completo

        t3 = torneo("Valorant 5v5 Cup", "Valorant", 14, 8, destacado=True, modalidad="equipos", jugadores_por_equipo=5)
        sv.inscribir(t3, jugadores[0], {"nombre_equipo": "Night Owls", "integrantes": "Tito, Mara, Juli, Fede"})
        sv.inscribir(t3, jugadores[3], {"nombre_equipo": "Red Dragons", "integrantes": "Sol, Nico, Pau, Leo"})

        torneo("Street Fighter 6 Masters", "Street Fighter 6", 30, 32, estado="proximamente")
        print("Datos de prueba cargados.")


if __name__ == "__main__":
    main()
