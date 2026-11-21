"""Tests integrados contra PostgreSQL, siguiendo la estrategia de RescueSync."""

import os

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text

from app import create_app
from app.cli import cargar_datos_demo
from app.config import Config
from app.extensions import db

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.exit(
        "Falta TEST_DATABASE_URL: corré `docker compose run --rm api pytest` desde la raíz."
    )


# Inventario de los tests: a diferencia del seed de la demo, arranca con reservas y compromisos
# ajenos, para probar que las operaciones descuentan lo que ya está tomado.
# (cuit, recurso, total, bloqueado, comprometido)
INVENTARIO_DE_TEST = [
    ("30-11111111-1", "PARAMEDICO", "12", "2", "0"),
    ("30-11111111-1", "RESCATISTA", "20", "3", "2"),
    ("30-11111111-1", "FRAZADA", "300", "20", "30"),
    ("30-22222222-2", "RACION_ALIMENTO", "5000", "700", "300"),
    ("30-22222222-2", "AGUA_POTABLE", "2500", "300", "200"),
    ("30-22222222-2", "ALIMENTO_SECO", "1200", "100", "100"),
    ("30-33333333-3", "PARAMEDICO", "100", "0", "0"),
]


class ConfigDeTest(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ["TEST_DATABASE_URL"]
    JWT_SECRET_KEY = "clave-solo-tests"
    LOG_LEVEL = "WARNING"


@pytest.fixture(scope="session")
def app():
    app = create_app(ConfigDeTest)
    with app.app_context():
        downgrade(revision="base")
        upgrade()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def datos_limpios(app):
    with app.app_context():
        cargar_datos_demo(INVENTARIO_DE_TEST)
        yield
        db.session.remove()
        db.session.execute(
            text(
                "TRUNCATE actividad, cierre_proyecto, cuenta, compromiso_item, compromiso, "
                "convocatoria, inventario_recurso, ong_certificacion, tipo_recurso, unidad_medida, "
                "certificacion, ong RESTART IDENTITY CASCADE"
            )
        )
        db.session.commit()
