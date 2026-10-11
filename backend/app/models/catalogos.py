"""Certificaciones y catálogo compartido de tipos de recurso."""

from datetime import date

from sqlalchemy import Date, ForeignKey, SmallInteger, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.comun import IdCatalogo, columna_enum
from app.models.enums import CategoriaRecurso


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

    ong: Mapped["ONG"] = relationship(back_populates="certificaciones")
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
