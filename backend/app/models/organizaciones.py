"""ONGs registradas en el Sistema Nacional."""

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.comun import ConMarcasDeTiempo, IdGrande, columna_enum
from app.models.enums import EstadoONG


class ONG(ConMarcasDeTiempo, db.Model):
    __tablename__ = "ong"
    __table_args__ = (Index("ix_ong_estado", "estado"),)

    id: Mapped[IdGrande]
    razon_social: Mapped[str] = mapped_column(String(160))
    cuit: Mapped[str] = mapped_column(String(13), unique=True)
    email_contacto: Mapped[str | None] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(40))
    estado: Mapped[EstadoONG] = mapped_column(
        columna_enum(EstadoONG, "estado_ong"),
        default=EstadoONG.PENDIENTE,
        server_default=EstadoONG.PENDIENTE.value,
    )

    certificaciones: Mapped[list["ONGCertificacion"]] = relationship(
        back_populates="ong", cascade="all, delete-orphan"
    )
    inventario: Mapped[list["InventarioRecurso"]] = relationship(
        back_populates="ong", cascade="all, delete-orphan"
    )

    @property
    def habilitada(self) -> bool:
        return self.estado == EstadoONG.HABILITADA


# Evita imports circulares solo para los type hints de SQLAlchemy.
