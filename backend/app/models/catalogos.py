"""Certificaciones y catálogo compartido de tipos de recurso."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, SmallInteger, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.comun import IdCatalogo, columna_enum
from app.models.enums import CategoriaRecurso

# Solo para el type hint de ONGCertificacion.ong: importarlo de verdad generaría un import circular
if TYPE_CHECKING:
    from app.models.organizaciones import ONG


class Certificacion(db.Model):
    __tablename__ = "certificacion"

    id: Mapped[IdCatalogo]
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    activa: Mapped[bool] = mapped_column(default=True, server_default=true())


class ONGCertificacion(db.Model):
    """Certificación concreta que posee una ONG."""

    __tablename__ = "ong_certificacion"

    ong_id: Mapped[int] = mapped_column(ForeignKey("ong.id", ondelete="CASCADE"), primary_key=True)
    certificacion_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("certificacion.id"), primary_key=True
    )
    fecha_emision: Mapped[date] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)

    ong: Mapped[ONG] = relationship(back_populates="certificaciones")
    certificacion: Mapped[Certificacion] = relationship()

    @property
    def vigente(self) -> bool:
        return self.fecha_vencimiento is None or self.fecha_vencimiento >= date.today()


class UnidadMedida(db.Model):
    __tablename__ = "unidad_medida"

    id: Mapped[IdCatalogo]
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    admite_decimales: Mapped[bool] = mapped_column(default=False, server_default=false())

    def admite(self, cantidad: Decimal) -> bool:
        """Una unidad que no admite decimales (personas, raciones, kits) solo acepta enteros.
        Es la misma regla que `unidad_medida.admite()` en la webapp."""
        return self.admite_decimales or cantidad == cantidad.to_integral_value()


class TipoRecurso(db.Model):
    """Códigos iguales a los usados por la webapp RescueSync."""

    __tablename__ = "tipo_recurso"

    id: Mapped[IdCatalogo]
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    categoria: Mapped[CategoriaRecurso] = mapped_column(columna_enum(CategoriaRecurso, "categoria"))
    unidad_medida_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("unidad_medida.id"))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    reutilizable: Mapped[bool] = mapped_column(
        default=True,
        server_default=true(),
        comment="Indica si el recurso vuelve al stock al finalizar la actividad",
    )

    unidad_medida: Mapped[UnidadMedida] = relationship()
