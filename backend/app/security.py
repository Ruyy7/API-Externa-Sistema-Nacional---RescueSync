"""Autenticación con JWT y control de acceso por rol.

A la API del Sistema Nacional la llaman sistemas, no personas: la webapp RescueSync y Bonita. Cada
uno usa una cuenta de servicio, y su token lleva el rol en el claim `rol`. El login que emite esos
tokens es parte del punto I-3.1; mientras no exista, `flask token-servicio` emite tokens para
probar los endpoints desde Swagger.
"""

from datetime import timedelta
from enum import StrEnum
from functools import wraps

from flask import jsonify
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, verify_jwt_in_request

from app.errors import Prohibido

CLAIM_ROL = "rol"
# Para que Swagger muestre el candado en los endpoints protegidos: @bp.doc(security=SEGURIDAD)
SEGURIDAD = [{"bearerAuth": []}]


class RolSistema(StrEnum):
    WEBAPP = "SISTEMA_WEBAPP"
    BONITA = "SISTEMA_BONITA"
    AUDITOR = "AUDITOR"


def configurar_jwt(jwt: JWTManager) -> None:
    """Lleva los errores de JWT al formato uniforme de la API."""

    def _no_autenticado(mensaje: str):
        return jsonify(codigo="NO_AUTENTICADO", mensaje=mensaje, detalles={}), 401

    @jwt.unauthorized_loader
    def _sin_token(_motivo):
        return _no_autenticado("Falta el token de acceso (Authorization: Bearer ...).")

    @jwt.invalid_token_loader
    def _token_invalido(_motivo):
        return _no_autenticado("El token de acceso no es válido.")

    @jwt.expired_token_loader
    def _token_vencido(_encabezado, _datos):
        return _no_autenticado("El token de acceso venció.")


def roles_required(*roles: RolSistema):
    """Patrón Decorator: el endpoint solo se ejecuta si el token trae alguno de los roles."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            verify_jwt_in_request()
            if get_jwt().get(CLAIM_ROL) not in roles:
                raise Prohibido("El rol del token no permite esta operación.")
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def emitir_token(identidad: str, rol: RolSistema, horas: int = 8) -> str:
    """Token de una cuenta de servicio. Lo usan `flask token-servicio` y los tests."""
    return create_access_token(
        identity=identidad,
        additional_claims={CLAIM_ROL: rol.value},
        expires_delta=timedelta(hours=horas),
    )
