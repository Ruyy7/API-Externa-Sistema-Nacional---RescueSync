"""Inventario nacional de recursos por ONG."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.comun import ConMarcasDeTiempo, IdGrande


class InventarioRecurso(ConMarcasDeTiempo, db.Model):
    """Stock agregado de una ONG para un tipo de recurso.

    ``cantidad_bloqueada`` representa reservas temporales de ofertas presentadas y todavía no
    adjudicadas. ``cantidad_comprometida`` representa recursos ya adjudicados y en uso/ejecución.
    La separación evita confundir una reserva provisional con un compromiso efectivo.
    """

    __tablename__ = "inventario_recurso"
    __table_args__ = (
        UniqueConstraint("ong_id", "tipo_recurso_id"),
        CheckConstraint("cantidad_total >= 0", name="cantidad_total_no_negativa"),
        CheckConstraint("cantidad_bloqueada >= 0", name="cantidad_bloqueada_no_negativa"),
        CheckConstraint("cantidad_comprometida >= 0", name="cantidad_comprometida_no_negativa"),
        CheckConstraint(
            "cantidad_bloqueada + cantidad_comprometida <= cantidad_total",
            name="reservada_y_comprometida_no_superan_total",
        ),
    )

    id: Mapped[IdGrande]
    ong_id: Mapped[int] = mapped_column(ForeignKey("ong.id", ondelete="CASCADE"), index=True)
    tipo_recurso_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("tipo_recurso.id"), index=True
    )
    cantidad_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cantidad_bloqueada: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    cantidad_comprometida: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )

    ong: Mapped["ONG"] = relationship(back_populates="inventario")
    tipo_recurso: Mapped["TipoRecurso"] = relationship()

    @property
    def cantidad_disponible(self) -> Decimal:
        return self.cantidad_total - self.cantidad_bloqueada - self.cantidad_comprometida
