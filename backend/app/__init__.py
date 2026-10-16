"""Sistema Nacional de Gestión de Recursos y Riesgos.

Application Factory inspirada en la webapp RescueSync. Este incremento implementa I-3.2:
catálogo y consulta de certificaciones, ONGs habilitadas y disponibilidad global de recursos.
"""

from flask import Flask

from app import models  # noqa: F401
from app.cli import registrar_comandos
from app.config import Config, validar
from app.controllers import registrar_blueprints
from app.errors import registrar_manejadores_de_error
from app.extensions import api, db, jwt, migrate
from app.logs import configurar_logging
from app.security import configurar_jwt
from app.services import crear_servicios


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    validar(app.config)
    configurar_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    configurar_jwt(jwt)
    api.init_app(app)
    registrar_blueprints(api)
    registrar_manejadores_de_error(app)
    registrar_comandos(app)

    app.extensions["servicios"] = crear_servicios()
    return app
