"""Inicio de sesión (I-3.1): emite el JWT de una cuenta de servicio o de una ONG."""

from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import NoAutenticado
from app.models import Cuenta
from app.repositories.cuentas import CuentaRepository
from app.security import CLAIM_ONG, RolSistema, emitir_token

HORAS_DE_VALIDEZ = 8
# Si el usuario no existe se verifica igual contra este hash, así la respuesta tarda lo mismo y no
# revela qué usuarios existen.
_HASH_DE_RELLENO = generate_password_hash("relleno-para-usuarios-inexistentes")


def normalizar_usuario(usuario: str) -> str:
    """Los usuarios son emails o nombres de cuenta: sin espacios ni mayúsculas."""
    return usuario.strip().lower()


class AuthService:
    def __init__(self, cuentas: CuentaRepository):
        self.cuentas = cuentas

    def login(self, usuario: str, password: str) -> dict:
        cuenta = self.cuentas.por_usuario(normalizar_usuario(usuario))
        if cuenta is None:
            check_password_hash(_HASH_DE_RELLENO, password)
        elif cuenta.activa and cuenta.verificar_password(password):
            return self._token(cuenta)
        # Mismo error para usuario inexistente, contraseña incorrecta o cuenta inactiva
        raise NoAutenticado("Usuario o contraseña incorrectos.", codigo="CREDENCIALES_INVALIDAS")

    @staticmethod
    def _token(cuenta: Cuenta) -> dict:
        claims = {CLAIM_ONG: cuenta.ong.cuit} if cuenta.rol == RolSistema.ONG else {}
        return {
            "access_token": emitir_token(str(cuenta.id), cuenta.rol, HORAS_DE_VALIDEZ, claims),
            "token_type": "Bearer",
            "expira_en_segundos": HORAS_DE_VALIDEZ * 3600,
            "rol": cuenta.rol,
        }
