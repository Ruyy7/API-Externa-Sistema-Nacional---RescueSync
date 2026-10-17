"""Cuentas que pueden iniciar sesión en el Sistema Nacional (I-3.1)."""

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.comun import ConMarcasDeTiempo, IdGrande
from app.models.organizaciones import ONG
from app.security import RolSistema


class Cuenta(ConMarcasDeTiempo, db.Model):
    """Cuenta de servicio (webapp, Bonita, auditor) o cuenta de una ONG registrada.

    Solo se guarda el hash de la contraseña. Cada ONG tiene una sola cuenta.
    """

    __tablename__ = "cuenta"
    __table_args__ = (
        # Solo las cuentas de ONG pertenecen a una ONG, y todas ellas pertenecen a una
        CheckConstraint("(rol = 'ONG') = (ong_id IS NOT NULL)", name="ong_solo_en_cuentas_de_ong"),
    )

    id: Mapped[IdGrande]
    usuario: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Guarda el valor del rol (SISTEMA_WEBAPP), igual que el claim del token. columna_enum guarda
    # el nombre del miembro, que en los demás enumerados coincide con el valor y acá no.
    rol: Mapped[RolSistema] = mapped_column(
        Enum(
            RolSistema,
            name="rol",
            native_enum=False,
            create_constraint=True,
            length=30,
            validate_strings=True,
            values_callable=lambda enum: [miembro.value for miembro in enum],
        )
    )
    ong_id: Mapped[int | None] = mapped_column(
        ForeignKey("ong.id", ondelete="CASCADE"), unique=True
    )
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())

    ong: Mapped[ONG | None] = relationship()

    def definir_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def verificar_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
