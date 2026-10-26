from routes import cs2_webhook, equipos, main, notificaciones, torneos, usuarios


def registrar_blueprints(app):
    for modulo in (main, usuarios, torneos, equipos, notificaciones, cs2_webhook):
        app.register_blueprint(modulo.bp)
        if hasattr(modulo, "api"):
            app.register_blueprint(modulo.api)
