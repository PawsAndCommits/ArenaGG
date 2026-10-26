"""Errores de negocio con código HTTP."""


class ErrorNegocio(Exception):
    def __init__(self, mensaje: str, codigo: int = 400, errores: dict | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.errores = errores or {}


class ErrorValidacion(ErrorNegocio):
    def __init__(self, errores: dict):
        super().__init__("Los datos enviados no son válidos.", 400, errores)
