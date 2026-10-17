"""Inicio de sesión (I-3.1)."""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.cuentas import LoginSchema, TokenSchema
from app.services import servicios

bp = Blueprint(
    "Autenticación", __name__, url_prefix="/api/v1", description="Inicio de sesión (I-3.1)"
)


@bp.route("/login")
class Login(MethodView):
    @bp.arguments(LoginSchema)
    @bp.response(200, TokenSchema)
    @bp.alt_response(401, description="Usuario o contraseña incorrectos")
    def post(self, datos):
        """Inicia sesión y devuelve un JWT para usar en `Authorization: Bearer <token>`.

        Sirve para las cuentas de servicio (webapp, Bonita y auditor) y para las ONGs
        registradas, que entran con su email. El token vale 8 horas y lleva el rol de la cuenta.
        """
        return servicios().auth.login(datos["usuario"], datos["password"])
