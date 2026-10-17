"""Autenticación con JWT y control de acceso por rol.

A la API del Sistema Nacional la llaman sistemas: la webapp RescueSync y Bonita, cada uno con una
cuenta de servicio. Las ONGs también tienen cuenta, que crean al registrarse (I-3.1), para
consultar y actualizar sus categorías. El token lleva el rol en el claim `rol` y, si es de una ONG,
su CUIT en `ong_cuit`. Los tokens los emite `POST /login`; `flask token-servicio` sigue
disponible para probar en desarrollo.
"""

from datetime import timedelta
from enum import StrEnum
from functools import wraps

from flask import jsonify
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, verify_jwt_in_request

from app.errors import Prohibido

CLAIM_ROL = "rol"
CLAIM_ONG = "ong_cuit"
# Para que Swagger muestre el candado en los endpoints protegidos: @bp.doc(security=SEGURIDAD)
SEGURIDAD = [{"bearerAuth": []}]


class RolSistema(StrEnum):
    WEBAPP = "SISTEMA_WEBAPP"
    BONITA = "SISTEMA_BONITA"
    AUDITOR = "AUDITOR"
    # Cuenta de una ONG registrada (I-3.1): solo gestiona sus propias categorías
    ONG = "ONG"


ROLES_DE_SERVICIO = (RolSistema.WEBAPP, RolSistema.BONITA, RolSistema.AUDITOR)


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


def emitir_token(
    identidad: str, rol: RolSistema, horas: int = 8, claims: dict | None = None
) -> str:
    """Token de una cuenta. Lo usan `POST /login`, `flask token-servicio` y los tests."""
    return create_access_token(
        identity=identidad,
        additional_claims={CLAIM_ROL: rol.value, **(claims or {})},
        expires_delta=timedelta(hours=horas),
    )


def cuit_del_token() -> str:
    """CUIT de la ONG dueña del token. Solo tiene sentido detrás de roles_required(ONG)."""
    return get_jwt()[CLAIM_ONG]
