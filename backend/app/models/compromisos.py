"""Modelo preparado para reserva, adjudicación y liberación de recursos.

Este incremento no expone todavía endpoints de bloqueo/compromiso. Las tablas se incorporan para
que el punto I-3.4 pueda implementar el flujo sin remodelar inventario ni perder trazabilidad.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.comun import ConMarcasDeTiempo, IdGrande, columna_enum
from app.models.enums import EstadoCompromiso


class Convocatoria(ConMarcasDeTiempo, db.Model):
    """Referencia local a una convocatoria originada en la webapp RescueSync."""

    __tablename__ = "convocatoria"
    __table_args__ = (
        CheckConstraint(
            "fecha_limite_adjudicacion >= fecha_cierre",
            name="limite_adjudicacion_no_antes_del_cierre",
        ),
    )

    id: Mapped[IdGrande]
    referencia: Mapped[str] = mapped_column(String(100), unique=True)
    fecha_cierre: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_limite_adjudicacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    compromisos: Mapped[list["Compromiso"]] = relationship(
        back_populates="convocatoria", cascade="all, delete-orphan"
    )


class Compromiso(ConMarcasDeTiempo, db.Model):
    """Reserva/compromiso de una ONG dentro de una oferta de RescueSync."""

    __tablename__ = "compromiso"
    __table_args__ = (UniqueConstraint("oferta_referencia", "ong_id"),)

    id: Mapped[IdGrande]
    convocatoria_id: Mapped[int] = mapped_column(
        ForeignKey("convocatoria.id", ondelete="CASCADE"), index=True
    )
    ong_id: Mapped[int] = mapped_column(ForeignKey("ong.id"), index=True)
    oferta_referencia: Mapped[str] = mapped_column(String(100))
    estado: Mapped[EstadoCompromiso] = mapped_column(
        columna_enum(EstadoCompromiso, "estado_compromiso"),
        default=EstadoCompromiso.RESERVADO,
        server_default=EstadoCompromiso.RESERVADO.value,
    )

    convocatoria: Mapped[Convocatoria] = relationship(back_populates="compromisos")
    ong: Mapped["ONG"] = relationship()
    items: Mapped[list["CompromisoItem"]] = relationship(
        back_populates="compromiso", cascade="all, delete-orphan"
    )


class CompromisoItem(ConMarcasDeTiempo, db.Model):
    """Cantidades reservadas y comprometidas para un recurso concreto."""

    __tablename__ = "compromiso_item"
    __table_args__ = (
        UniqueConstraint("compromiso_id", "inventario_recurso_id"),
        CheckConstraint("cantidad_reservada >= 0", name="cantidad_reservada_no_negativa"),
        CheckConstraint("cantidad_comprometida >= 0", name="cantidad_comprometida_no_negativa"),
        CheckConstraint(
            "cantidad_reservada + cantidad_comprometida > 0",
            name="item_con_cantidad_positiva",
        ),
    )

    id: Mapped[IdGrande]
    compromiso_id: Mapped[int] = mapped_column(
        ForeignKey("compromiso.id", ondelete="CASCADE"), index=True
    )
    inventario_recurso_id: Mapped[int] = mapped_column(
        ForeignKey("inventario_recurso.id"), index=True
    )
    cantidad_reservada: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    cantidad_comprometida: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )

    compromiso: Mapped[Compromiso] = relationship(back_populates="items")
    inventario_recurso: Mapped["InventarioRecurso"] = relationship()
