"""Modelos de la base de datos."""
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

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

ESTADOS_PARTIDA = ("pendiente", "finalizada", "bye")


def ahora():
    return datetime.now().replace(microsecond=0)


def fecha_iso(valor):
    return valor.isoformat(timespec="minutes") if valor else None


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'jugador')", name="ck_usuarios_rol"),
        CheckConstraint("length(username) >= 3", name="ck_usuarios_username_largo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    rol = db.Column(db.String(10), nullable=False, default="jugador")
    juegos_favoritos = db.Column(db.String(255), nullable=False, default="")
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)
    steam_id = db.Column(db.String(32), unique=True, nullable=True, index=True)
    steam_persona_name = db.Column(db.String(100), nullable=True)
    steam_avatar = db.Column(db.String(255), nullable=True)
    steam_avatar_full = db.Column(db.String(255), nullable=True)
    steam_profile_url = db.Column(db.String(255), nullable=True)

    inscripciones = db.relationship(
        "Inscripcion", back_populates="usuario", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"

    @property
    def lista_juegos(self):
        return [j.strip() for j in self.juegos_favoritos.split(",") if j.strip()]

    @property
    def tiene_steam(self):
        return bool(self.steam_id)

    def to_dict(self, privado=False):
        datos = {
            "id": self.id,
            "username": self.username,
            "rol": self.rol,
            "juegos_favoritos": self.lista_juegos,
            "creado_en": fecha_iso(self.creado_en),
            "steam_id": self.steam_id,
            "steam_avatar": self.steam_avatar,
            "steam_profile_url": self.steam_profile_url,
        }
        if privado:
            datos["email"] = self.email
        return datos


class Torneo(db.Model):
    __tablename__ = "torneos"
    __table_args__ = (
        CheckConstraint("cupo_maximo BETWEEN 2 AND 128", name="ck_torneos_cupo"),
        CheckConstraint(
            "estado IN ('proximamente', 'inscripciones_abiertas', 'en_curso', 'finalizado')",
            name="ck_torneos_estado",
        ),
        CheckConstraint("modalidad IN ('individual', 'equipos')", name="ck_torneos_modalidad"),
        CheckConstraint(
            "jugadores_por_equipo IS NULL OR jugadores_por_equipo BETWEEN 2 AND 10",
            name="ck_torneos_jugadores_equipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False, default="")
    videojuego = db.Column(db.String(80), nullable=False, index=True)
    fecha = db.Column(db.DateTime, nullable=False)
    cupo_maximo = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="proximamente", index=True)
    modalidad = db.Column(db.String(15), nullable=False, default="individual")
    jugadores_por_equipo = db.Column(db.Integer, nullable=True)
    destacado = db.Column(db.Boolean, nullable=False, default=False)
    creado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    creado_por = db.relationship("Usuario")
    inscripciones = db.relationship(
        "Inscripcion",
        back_populates="torneo",
        cascade="all, delete-orphan",
        order_by="Inscripcion.creado_en",
    )
    partidas = db.relationship(
        "Partida",
        back_populates="torneo",
        cascade="all, delete-orphan",
        order_by="[Partida.ronda, Partida.numero]",
    )

    @property
    def estado_texto(self):
        return ESTADOS_TORNEO.get(self.estado, self.estado)

    @property
    def modalidad_texto(self):
        return MODALIDADES.get(self.modalidad, self.modalidad)

    @property
    def es_por_equipos(self):
        return self.modalidad == "equipos"

    @property
    def inscriptos(self):
        return len(self.inscripciones)

    @property
    def cupos_disponibles(self):
        return max(self.cupo_maximo - self.inscriptos, 0)

    @property
    def esta_completo(self):
        return self.inscriptos >= self.cupo_maximo

    @property
    def porcentaje_ocupado(self):
        return round(self.inscriptos * 100 / self.cupo_maximo) if self.cupo_maximo else 0

    @property
    def acepta_inscripciones(self):
        return self.estado == "inscripciones_abiertas" and not self.esta_completo

    @property
    def tiene_partidas(self):
        return len(self.partidas) > 0

    @property
    def total_rondas(self):
        return max((p.ronda for p in self.partidas), default=0)

    @property
    def final(self):
        total = self.total_rondas
        return next((p for p in self.partidas if p.ronda == total), None) if total else None

    @property
    def campeon(self):
        final = self.final
        if final and final.estado == "finalizada":
            return final.ganador
        return None

    def inscripcion_de(self, usuario):
        if not usuario or not getattr(usuario, "id", None):
            return None
        return next((i for i in self.inscripciones if i.usuario_id == usuario.id), None)

    def to_dict(self, detalle=False):
        campeon = self.campeon
        datos = {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "videojuego": self.videojuego,
            "fecha": fecha_iso(self.fecha),
            "cupo_maximo": self.cupo_maximo,
            "inscriptos": self.inscriptos,
            "cupos_disponibles": self.cupos_disponibles,
            "estado": self.estado,
            "estado_texto": self.estado_texto,
            "modalidad": self.modalidad,
            "jugadores_por_equipo": self.jugadores_por_equipo,
            "destacado": self.destacado,
            "acepta_inscripciones": self.acepta_inscripciones,
            "campeon": campeon.to_dict() if campeon else None,
        }
        if detalle:
            datos["creado_por"] = self.creado_por.username if self.creado_por else None
            datos["creado_en"] = fecha_iso(self.creado_en)
            datos["total_rondas"] = self.total_rondas
        return datos


class Inscripcion(db.Model):
    __tablename__ = "inscripciones"
    __table_args__ = (
        UniqueConstraint("torneo_id", "usuario_id", name="uq_inscripciones_torneo_usuario"),
        UniqueConstraint("torneo_id", "nombre_equipo", name="uq_inscripciones_torneo_equipo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    torneo_id = db.Column(
        db.Integer, db.ForeignKey("torneos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre_equipo = db.Column(db.String(60), nullable=True)
    integrantes = db.Column(db.String(255), nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    torneo = db.relationship("Torneo", back_populates="inscripciones")
    usuario = db.relationship("Usuario", back_populates="inscripciones")

    @property
    def nombre_mostrar(self):
        return self.nombre_equipo or self.usuario.username

    def to_dict(self):
        return {
            "id": self.id,
            "torneo_id": self.torneo_id,
            "usuario": {"id": self.usuario.id, "username": self.usuario.username},
            "nombre": self.nombre_mostrar,
            "nombre_equipo": self.nombre_equipo,
            "integrantes": self.integrantes,
            "inscripto_en": fecha_iso(self.creado_en),
        }

    def to_dict_corto(self):
        return {"inscripcion_id": self.id, "usuario_id": self.usuario_id, "nombre": self.nombre_mostrar}


class Partida(db.Model):
    __tablename__ = "partidas"
    __table_args__ = (
        UniqueConstraint("torneo_id", "ronda", "numero", name="uq_partidas_torneo_ronda_numero"),
        CheckConstraint("ronda >= 1 AND numero >= 1", name="ck_partidas_ronda_numero"),
        CheckConstraint("estado IN ('pendiente', 'finalizada', 'bye')", name="ck_partidas_estado"),
        CheckConstraint(
            "participante1_id IS NULL OR participante2_id IS NULL "
            "OR participante1_id <> participante2_id",
            name="ck_partidas_participantes_distintos",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    torneo_id = db.Column(
        db.Integer, db.ForeignKey("torneos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ronda = db.Column(db.Integer, nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    participante1_id = db.Column(
        db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=True
    )
    participante2_id = db.Column(
        db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=True
    )
    ganador_id = db.Column(
        db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=True
    )
    estado = db.Column(db.String(12), nullable=False, default="pendiente")
    fecha_programada = db.Column(db.DateTime, nullable=True)

    torneo = db.relationship("Torneo", back_populates="partidas")
    participante1 = db.relationship("Inscripcion", foreign_keys=[participante1_id])
    participante2 = db.relationship("Inscripcion", foreign_keys=[participante2_id])
    ganador = db.relationship("Inscripcion", foreign_keys=[ganador_id])
    resultado = db.relationship(
        "Resultado", back_populates="partida", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def lista_para_jugar(self):
        return self.participante1_id is not None and self.participante2_id is not None

    @property
    def nombre_ronda(self):
        faltan = self.torneo.total_rondas - self.ronda
        nombres = {0: "Final", 1: "Semifinal", 2: "Cuartos de final", 3: "Octavos de final"}
        return nombres.get(faltan, f"Ronda {self.ronda}")

    def to_dict(self):
        def participante(insc):
            return insc.to_dict_corto() if insc else None

        res = self.resultado
        return {
            "id": self.id,
            "torneo_id": self.torneo_id,
            "ronda": self.ronda,
            "nombre_ronda": self.nombre_ronda,
            "numero": self.numero,
            "estado": self.estado,
            "fecha_programada": fecha_iso(self.fecha_programada),
            "participante1": participante(self.participante1),
            "participante2": participante(self.participante2),
            "ganador": participante(self.ganador),
            "resultado": res.to_dict() if res else None,
        }


class Resultado(db.Model):
    __tablename__ = "resultados"
    __table_args__ = (
        CheckConstraint("puntaje1 >= 0 AND puntaje2 >= 0", name="ck_resultados_puntajes"),
        CheckConstraint("puntaje1 <> puntaje2", name="ck_resultados_sin_empate"),
    )

    id = db.Column(db.Integer, primary_key=True)
    partida_id = db.Column(
        db.Integer, db.ForeignKey("partidas.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    puntaje1 = db.Column(db.Integer, nullable=False)
    puntaje2 = db.Column(db.Integer, nullable=False)
    ganador_id = db.Column(
        db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=False
    )
    registrado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    registrado_en = db.Column(db.DateTime, nullable=False, default=ahora)
    actualizado_en = db.Column(db.DateTime, nullable=True)

    partida = db.relationship("Partida", back_populates="resultado")
    ganador = db.relationship("Inscripcion")
    registrado_por = db.relationship("Usuario")

    def to_dict(self):
        return {
            "id": self.id,
            "partida_id": self.partida_id,
            "puntaje1": self.puntaje1,
            "puntaje2": self.puntaje2,
            "ganador_inscripcion_id": self.ganador_id,
            "registrado_por": self.registrado_por.username if self.registrado_por else None,
            "registrado_en": fecha_iso(self.registrado_en),
            "actualizado_en": fecha_iso(self.actualizado_en),
        }



class ServidorCS2(db.Model):
    __tablename__ = "servidores_cs2"
    __table_args__ = (
        CheckConstraint("puerto BETWEEN 1 AND 65535", name="ck_servidores_puerto"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    ip = db.Column(db.String(120), nullable=False)
    puerto = db.Column(db.Integer, nullable=False)
    rcon_password = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    asignaciones = db.relationship("AsignacionPartida", back_populates="servidor", cascade="all, delete-orphan")


class AsignacionPartida(db.Model):
    __tablename__ = "asignaciones_partida"
    __table_args__ = (
        UniqueConstraint("partida_id", name="uq_asignacion_partida"),
    )

    id = db.Column(db.Integer, primary_key=True)
    partida_id = db.Column(db.Integer, db.ForeignKey("partidas.id", ondelete="CASCADE"), nullable=False, index=True)
    servidor_id = db.Column(db.Integer, db.ForeignKey("servidores_cs2.id", ondelete="SET NULL"), nullable=True, index=True)
    estado = db.Column(db.String(20), nullable=False, default="asignado")
    clave_conexion = db.Column(db.String(64), nullable=True)
    enviado_a_jugadores = db.Column(db.Boolean, nullable=False, default=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)
    actualizado_en = db.Column(db.DateTime, nullable=True)

    partida = db.relationship("Partida", backref=db.backref("asignacion_partida", uselist=False, cascade="all, delete-orphan"))
    servidor = db.relationship("ServidorCS2", back_populates="asignaciones")

    @property
    def connect_command(self):
        if not self.servidor:
            return None
        return f"connect {self.servidor.ip}:{self.servidor.puerto}"

