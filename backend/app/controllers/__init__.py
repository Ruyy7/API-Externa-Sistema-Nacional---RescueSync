"""Registro de blueprints HTTP."""

from flask_smorest import Api

from app.controllers import certificaciones, ongs, recursos


def registrar_blueprints(api: Api) -> None:
    for modulo in (ongs, certificaciones, recursos):
        api.register_blueprint(modulo.bp)
