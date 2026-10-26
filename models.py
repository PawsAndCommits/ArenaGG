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

FORMATOS = {
    "BO1": "Mejor de 1",
    "BO3": "Mejor de 3",
    "BO5": "Mejor de 5",
}

ESTADOS_PARTIDA = ("pendiente", "finalizada", "bye")
ESTADOS_RESULTADO = ("pendiente", "confirmado", "disputa")


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
    notificaciones = db.relationship(
        "Notificacion",
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Notificacion.creada_en.desc()",
    )
    equipos_capitan = db.relationship(
        "Equipo", back_populates="capitan", foreign_keys="Equipo.capitan_id"
    )
    membresias = db.relationship(
        "EquipoMiembro",
        back_populates="usuario",
        cascade="all, delete-orphan",
        foreign_keys="EquipoMiembro.usuario_id",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"

    @property
    def tiene_password(self):
        return bool(self.password_hash)

    @property
    def lista_juegos(self):
        return [j.strip() for j in self.juegos_favoritos.split(",") if j.strip()]

    @property
    def tiene_steam(self):
        return bool(self.steam_id)

    @property
    def nombre_visible(self):
        return self.steam_persona_name or self.username

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
            datos["tiene_password"] = self.tiene_password
        return datos


class Notificacion(db.Model):
    __tablename__ = "notificaciones"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    torneo_id = db.Column(
        db.Integer, db.ForeignKey("torneos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo = db.Column(db.String(40), nullable=False, default="general")
    titulo = db.Column(db.String(120), nullable=False)
    mensaje = db.Column(db.String(255), nullable=False, default="")
    url = db.Column(db.String(255), nullable=True)
    leida = db.Column(db.Boolean, nullable=False, default=False, index=True)
    creada_en = db.Column(db.DateTime, nullable=False, default=ahora, index=True)

    usuario = db.relationship("Usuario", back_populates="notificaciones")
    torneo = db.relationship("Torneo")

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "mensaje": self.mensaje,
            "url": self.url,
            "leida": self.leida,
            "torneo_id": self.torneo_id,
            "creada_en": fecha_iso(self.creada_en),
        }


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
    formato = db.Column(db.String(10), nullable=False, default="BO1")
    reglas = db.Column(db.Text, nullable=False, default="")
    premio = db.Column(db.String(200), nullable=False, default="")
    total_rondas = db.Column(db.Integer, nullable=True)
    iniciado_en = db.Column(db.DateTime, nullable=True)
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
    def formato_texto(self):
        return FORMATOS.get(self.formato, self.formato)

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
    def final(self):
        total = self.total_rondas or max((p.ronda for p in self.partidas), default=0)
        if not total:
            return None
        return next((p for p in self.partidas if p.ronda == total), None)

    @property
    def campeon(self):
        final = self.final
        if final and final.estado == "finalizada":
            return final.ganador
        return None

    @property
    def partidas_pendientes(self):
        return [p for p in self.partidas if p.estado == "pendiente"]

    def inscripcion_de(self, usuario):
        if not usuario or not getattr(usuario, "id", None):
            return None
        for inscripcion in self.inscripciones:
            if inscripcion.usuario_id == usuario.id:
                return inscripcion
            if inscripcion.equipo and inscripcion.equipo.miembro_activo(usuario.id):
                return inscripcion
        return None

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
            "formato": self.formato,
            "formato_texto": self.formato_texto,
            "premio": self.premio,
            "destacado": self.destacado,
            "acepta_inscripciones": self.acepta_inscripciones,
            "campeon": campeon.to_dict() if campeon else None,
        }
        if detalle:
            datos["creado_por"] = self.creado_por.username if self.creado_por else None
            datos["creado_en"] = fecha_iso(self.creado_en)
            datos["total_rondas"] = self.total_rondas
            datos["reglas"] = self.reglas
        return datos


class Equipo(db.Model):
    __tablename__ = "equipos"
    __table_args__ = (
        UniqueConstraint("nombre", name="uq_equipos_nombre"),
        CheckConstraint("length(nombre) >= 2", name="ck_equipos_nombre_largo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(60), nullable=False, index=True)
    tag = db.Column(db.String(10), nullable=False, default="")
    descripcion = db.Column(db.Text, nullable=False, default="")
    capitan_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    capitan = db.relationship("Usuario", back_populates="equipos_capitan", foreign_keys=[capitan_id])
    miembros = db.relationship(
        "EquipoMiembro",
        back_populates="equipo",
        cascade="all, delete-orphan",
        order_by="EquipoMiembro.creado_en",
    )
    inscripciones = db.relationship("Inscripcion", back_populates="equipo")

    @property
    def miembros_activos(self):
        return [m for m in self.miembros if m.estado == "activo"]

    @property
    def invitaciones_pendientes(self):
        return [m for m in self.miembros if m.estado == "invitado"]

    @property
    def iniciales(self):
        partes = [p for p in self.nombre.replace("-", " ").split() if p]
        if not partes:
            return "GG"
        return "".join(p[0] for p in partes[:2]).upper()

    def miembro_activo(self, usuario_id):
        return any(m.usuario_id == usuario_id and m.estado == "activo" for m in self.miembros)

    def membresia_de(self, usuario_id):
        return next((m for m in self.miembros if m.usuario_id == usuario_id), None)

    def es_capitan(self, usuario):
        return bool(usuario and getattr(usuario, "id", None) == self.capitan_id)

    def to_dict(self, detalle=False):
        datos = {
            "id": self.id,
            "nombre": self.nombre,
            "tag": self.tag,
            "descripcion": self.descripcion,
            "capitan_id": self.capitan_id,
            "capitan": self.capitan.username if self.capitan else None,
            "miembros": len(self.miembros_activos),
            "creado_en": fecha_iso(self.creado_en),
        }
        if detalle:
            datos["roster"] = [m.to_dict() for m in self.miembros_activos]
            datos["invitaciones"] = [m.to_dict() for m in self.invitaciones_pendientes]
        return datos


class EquipoMiembro(db.Model):
    __tablename__ = "equipo_miembros"
    __table_args__ = (
        UniqueConstraint("equipo_id", "usuario_id", name="uq_equipo_miembro"),
        CheckConstraint("rol IN ('capitan', 'jugador')", name="ck_equipo_miembro_rol"),
        CheckConstraint("estado IN ('activo', 'invitado', 'rechazado')", name="ck_equipo_miembro_estado"),
    )

    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(
        db.Integer, db.ForeignKey("equipos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rol = db.Column(db.String(10), nullable=False, default="jugador")
    estado = db.Column(db.String(10), nullable=False, default="activo", index=True)
    invitado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)
    respondido_en = db.Column(db.DateTime, nullable=True)

    equipo = db.relationship("Equipo", back_populates="miembros")
    usuario = db.relationship("Usuario", back_populates="membresias", foreign_keys=[usuario_id])
    invitado_por = db.relationship("Usuario", foreign_keys=[invitado_por_id])

    @property
    def es_capitan(self):
        return self.rol == "capitan"

    @property
    def activo(self):
        return self.estado == "activo"

    def to_dict(self):
        return {
            "id": self.id,
            "equipo_id": self.equipo_id,
            "usuario_id": self.usuario_id,
            "username": self.usuario.username if self.usuario else None,
            "rol": self.rol,
            "estado": self.estado,
            "invitado_por": self.invitado_por.username if self.invitado_por else None,
            "creado_en": fecha_iso(self.creado_en),
        }


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
    equipo_id = db.Column(
        db.Integer, db.ForeignKey("equipos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nombre_equipo = db.Column(db.String(60), nullable=True)
    integrantes = db.Column(db.String(255), nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    torneo = db.relationship("Torneo", back_populates="inscripciones")
    usuario = db.relationship("Usuario", back_populates="inscripciones")
    equipo = db.relationship("Equipo", back_populates="inscripciones")

    @property
    def nombre_mostrar(self):
        if self.equipo:
            return self.equipo.nombre
        return self.nombre_equipo or self.usuario.username

    @property
    def capitan(self):
        if self.equipo and self.equipo.capitan:
            return self.equipo.capitan
        return self.usuario

    @property
    def capitan_id(self):
        return self.equipo.capitan_id if self.equipo else self.usuario_id

    @property
    def roster(self):
        if self.equipo:
            return [m.usuario for m in self.equipo.miembros_activos]
        return [self.usuario]

    def es_capitan(self, usuario):
        return bool(usuario and getattr(usuario, "id", None) == self.capitan_id)

    def incluye_usuario(self, usuario):
        if not usuario or not getattr(usuario, "id", None):
            return False
        if self.usuario_id == usuario.id:
            return True
        return bool(self.equipo and self.equipo.miembro_activo(usuario.id))

    def to_dict(self):
        return {
            "id": self.id,
            "torneo_id": self.torneo_id,
            "usuario": {"id": self.usuario.id, "username": self.usuario.username},
            "equipo_id": self.equipo_id,
            "equipo": self.equipo.to_dict() if self.equipo else None,
            "nombre": self.nombre_mostrar,
            "nombre_equipo": self.nombre_equipo,
            "integrantes": self.integrantes,
            "inscripto_en": fecha_iso(self.creado_en),
        }

    def to_dict_corto(self):
        return {
            "inscripcion_id": self.id,
            "usuario_id": self.usuario_id,
            "equipo_id": self.equipo_id,
            "nombre": self.nombre_mostrar,
        }


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
        return (
            self.estado != "bye"
            and self.participante1_id is not None
            and self.participante2_id is not None
        )

    @property
    def nombre_ronda(self):
        total = self.torneo.total_rondas or max((p.ronda for p in self.torneo.partidas), default=0)
        faltan = total - self.ronda
        nombres = {
            0: "Final",
            1: "Semifinal",
            2: "Cuartos de final",
            3: "Octavos de final",
            4: "Ronda de 32",
            5: "Ronda de 64",
        }
        return nombres.get(faltan, f"Ronda {self.ronda}")

    @property
    def estado_texto(self):
        if self.estado == "bye":
            return "Pase directo"
        if self.estado == "finalizada":
            return "Finalizada"
        if self.resultado:
            if self.resultado.estado == "pendiente":
                return "Esperando confirmación"
            if self.resultado.estado == "disputa":
                return "En disputa"
        if self.lista_para_jugar:
            return "Por jugar"
        if self.participante1_id or self.participante2_id:
            return "Esperando rival"
        return "Por definir"

    @property
    def estado_clase(self):
        if self.estado == "bye":
            return "bye"
        if self.estado == "finalizada":
            return "finalizada"
        if self.resultado and self.resultado.estado == "disputa":
            return "disputa"
        if self.resultado and self.resultado.estado == "pendiente":
            return "esperando"
        if self.lista_para_jugar:
            return "por-jugar"
        return "por-definir"

    def incluye_usuario(self, usuario):
        return bool(
            usuario
            and getattr(usuario, "id", None)
            and (
                (self.participante1 and self.participante1.incluye_usuario(usuario))
                or (self.participante2 and self.participante2.incluye_usuario(usuario))
            )
        )

    def es_capitan(self, usuario):
        return bool(
            usuario
            and getattr(usuario, "id", None)
            and (
                (self.participante1 and self.participante1.es_capitan(usuario))
                or (self.participante2 and self.participante2.es_capitan(usuario))
            )
        )

    def puede_reportar(self, usuario):
        if not usuario or not getattr(usuario, "is_authenticated", False):
            return False
        if getattr(usuario, "es_admin", False):
            return self.lista_para_jugar and self.estado == "pendiente" and not self.resultado
        return (
            self.lista_para_jugar
            and self.estado == "pendiente"
            and not self.resultado
            and self.es_capitan(usuario)
        )

    def puede_confirmar(self, usuario):
        return bool(
            usuario
            and getattr(usuario, "is_authenticated", False)
            and self.resultado
            and self.resultado.estado == "pendiente"
            and self.es_capitan(usuario)
            and self.resultado.registrado_por_id != usuario.id
        )

    def puede_disputar(self, usuario):
        return self.puede_confirmar(usuario)

    def puede_resolver(self, usuario):
        return bool(
            usuario
            and getattr(usuario, "is_authenticated", False)
            and getattr(usuario, "es_admin", False)
            and self.resultado
            and self.resultado.estado in ("pendiente", "disputa")
        )

    def puede_rechazar(self, usuario):
        return self.puede_resolver(usuario)

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
            "estado_texto": self.estado_texto,
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
    estado = db.Column(db.String(20), nullable=False, default="confirmado", index=True)
    registrado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    confirmado_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    resuelto_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    disputa_motivo = db.Column(db.String(255), nullable=True)
    registrado_en = db.Column(db.DateTime, nullable=False, default=ahora)
    confirmado_en = db.Column(db.DateTime, nullable=True)
    actualizado_en = db.Column(db.DateTime, nullable=True)

    partida = db.relationship("Partida", back_populates="resultado")
    ganador = db.relationship("Inscripcion", foreign_keys=[ganador_id])
    registrado_por = db.relationship("Usuario", foreign_keys=[registrado_por_id])
    confirmado_por = db.relationship("Usuario", foreign_keys=[confirmado_por_id])
    resuelto_por = db.relationship("Usuario", foreign_keys=[resuelto_por_id])

    @property
    def confirmado(self):
        return self.estado == "confirmado"

    def to_dict(self):
        return {
            "id": self.id,
            "partida_id": self.partida_id,
            "puntaje1": self.puntaje1,
            "puntaje2": self.puntaje2,
            "ganador_inscripcion_id": self.ganador_id,
            "estado": self.estado,
            "registrado_por": self.registrado_por.username if self.registrado_por else None,
            "confirmado_por": self.confirmado_por.username if self.confirmado_por else None,
            "resuelto_por": self.resuelto_por.username if self.resuelto_por else None,
            "disputa_motivo": self.disputa_motivo,
            "registrado_en": fecha_iso(self.registrado_en),
            "confirmado_en": fecha_iso(self.confirmado_en),
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

    asignaciones = db.relationship(
        "AsignacionPartida", back_populates="servidor", cascade="all, delete-orphan"
    )


class AsignacionPartida(db.Model):
    __tablename__ = "asignaciones_partida"
    __table_args__ = (UniqueConstraint("partida_id", name="uq_asignacion_partida"),)

    id = db.Column(db.Integer, primary_key=True)
    partida_id = db.Column(
        db.Integer, db.ForeignKey("partidas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    servidor_id = db.Column(
        db.Integer,
        db.ForeignKey("servidores_cs2.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    estado = db.Column(db.String(20), nullable=False, default="asignado")
    clave_conexion = db.Column(db.String(64), nullable=True)
    enviado_a_jugadores = db.Column(db.Boolean, nullable=False, default=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)
    actualizado_en = db.Column(db.DateTime, nullable=True)

    partida = db.relationship(
        "Partida",
        backref=db.backref("asignacion_partida", uselist=False, cascade="all, delete-orphan"),
    )
    servidor = db.relationship("ServidorCS2", back_populates="asignaciones")

    @property
    def connect_command(self):
        if not self.servidor:
            return None
        return f"connect {self.servidor.ip}:{self.servidor.puerto}"
