"""Registro de blueprints HTTP."""

from flask_smorest import Api

from app.controllers import (
    auth,
    certificaciones,
    compromisos,
    convocatorias,
    liberaciones,
    ongs,
    recursos,
    validaciones,
)


def registrar_blueprints(api: Api) -> None:
    for modulo in (
        auth,
        ongs,
        certificaciones,
        recursos,
        validaciones,
        compromisos,
        convocatorias,
        liberaciones,
    ):
        api.register_blueprint(modulo.bp)
