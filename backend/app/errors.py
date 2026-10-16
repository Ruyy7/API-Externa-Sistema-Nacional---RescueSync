"""Errores de dominio y respuesta JSON uniforme."""

import logging
from http import HTTPStatus

from flask import Flask, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.extensions import db

log = logging.getLogger(__name__)


class ErrorDeDominio(Exception):
    http_status = HTTPStatus.CONFLICT
    codigo = "ERROR_DE_DOMINIO"

    def __init__(self, mensaje: str, *, codigo: str | None = None, detalles: dict | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or {}
        if codigo:
            self.codigo = codigo


class NoEncontrado(ErrorDeDominio):
    http_status = HTTPStatus.NOT_FOUND
    codigo = "NO_ENCONTRADO"


class ReglaDeNegocio(ErrorDeDominio):
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    codigo = "VALIDACION"


class Conflicto(ErrorDeDominio):
    http_status = HTTPStatus.CONFLICT
    codigo = "CONFLICTO"


class Prohibido(ErrorDeDominio):
    http_status = HTTPStatus.FORBIDDEN
    codigo = "PROHIBIDO"


_POR_ESTADO = {
    400: ("SOLICITUD_INVALIDA", "La solicitud no es válida."),
    401: ("NO_AUTENTICADO", "Se requiere iniciar sesión."),
    403: ("PROHIBIDO", "Permiso insuficiente para esta operación."),
    404: ("NO_ENCONTRADO", "El recurso no existe."),
    405: ("METODO_NO_PERMITIDO", "Método no permitido."),
    422: ("VALIDACION", "Hay campos con errores."),
}


def _respuesta(status: int, codigo: str, mensaje: str, detalles: dict | None = None):
    # SQLAlchemy Session funciona como Unit of Work: un error no deja cambios parciales.
    db.session.rollback()
    return jsonify(codigo=codigo, mensaje=mensaje, detalles=detalles or {}), status


def registrar_manejadores_de_error(app: Flask) -> None:
    @app.errorhandler(ErrorDeDominio)
    def _de_dominio(error: ErrorDeDominio):
        return _respuesta(error.http_status, error.codigo, error.mensaje, error.detalles)

    @app.errorhandler(HTTPException)
    def _http(error: HTTPException):
        codigo, mensaje = _POR_ESTADO.get(error.code, ("ERROR_HTTP", error.description))
        detalles = getattr(error, "data", {}).get("messages", {})
        return _respuesta(error.code, codigo, mensaje, detalles)

    @app.errorhandler(IntegrityError)
    def _integridad(error: IntegrityError):
        log.warning(
            "Restricción de la base violada", extra={"contexto": {"error": str(error.orig)}}
        )
        return _respuesta(409, "CONFLICTO", "La operación choca con datos existentes.")

    @app.errorhandler(Exception)
    def _inesperado(error: Exception):
        log.exception("Error no controlado")
        return _respuesta(500, "ERROR_INTERNO", "Ocurrió un error inesperado.")
