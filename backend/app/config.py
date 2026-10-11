"""Configuración 12-factor del Sistema Nacional."""

import os
from urllib.parse import quote_plus


def _database_url() -> str | None:
    """Obtiene DATABASE_URL o la deriva para ejecución local fuera de Docker.

    Docker Compose sigue inyectando DATABASE_URL con host ``db:5432``. El fallback evita duplicar
    la URL en ``.env`` cuando se ejecuta Flask manualmente desde la máquina anfitriona.
    """

    explicita = os.environ.get("DATABASE_URL")
    if explicita:
        return explicita

    usuario = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    base = os.environ.get("POSTGRES_DB")
    if not all((usuario, password, base)):
        return None

    host = os.environ.get("DATABASE_HOST", "localhost")
    puerto = os.environ.get("DB_PORT", "5433")
    return (
        f"postgresql+psycopg://{quote_plus(usuario)}:{quote_plus(password)}"
        f"@{host}:{puerto}/{quote_plus(base)}"
    )


class Config:
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # El punto 1 de la E3 agregará login y protección de endpoints. Se deja preparada la extensión.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    API_TITLE = "Sistema Nacional de Gestión de Recursos y Riesgos"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api/v1"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


_OBLIGATORIAS = {"SQLALCHEMY_DATABASE_URI": "DATABASE_URL o POSTGRES_*"}


def validar(config) -> None:
    """Falla al arrancar si falta configuración imprescindible para este incremento."""
    faltantes = [variable for clave, variable in _OBLIGATORIAS.items() if not config.get(clave)]
    if faltantes:
        raise RuntimeError(f"Faltan variables de entorno: {', '.join(faltantes)}")
