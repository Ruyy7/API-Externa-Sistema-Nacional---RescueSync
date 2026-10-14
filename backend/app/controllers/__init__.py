"""Registro de blueprints HTTP."""

from flask_smorest import Api

from app.controllers import certificaciones, ongs, recursos, validaciones


def registrar_blueprints(api: Api) -> None:
    for modulo in (ongs, certificaciones, recursos, validaciones):
        api.register_blueprint(modulo.bp)
