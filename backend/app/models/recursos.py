"""Inventario nacional de recursos por ONG."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.catalogos import TipoRecurso
from app.models.comun import ConMarcasDeTiempo, IdGrande
from app.models.organizaciones import ONG


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
        # Destino de la FK compuesta de compromiso_item: el recurso es de la ONG del compromiso
        UniqueConstraint("id", "ong_id"),
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

    ong: Mapped[ONG] = relationship(back_populates="inventario")
    tipo_recurso: Mapped[TipoRecurso] = relationship()

    @property
    def cantidad_disponible(self) -> Decimal:
        return self.cantidad_total - self.cantidad_bloqueada - self.cantidad_comprometida

    # Los métodos siguientes cambian contadores que comparten pedidos simultáneos: quien los llama
    # tiene que tener la fila bloqueada (SELECT ... FOR UPDATE, ver repositories/bloqueos.py).

    def bloquear(self, cantidad: Decimal) -> None:
        """Reserva para una oferta presentada."""
        self.cantidad_bloqueada += cantidad

    def desbloquear(self, cantidad: Decimal) -> None:
        """Devuelve una reserva: la oferta se retiró, se redujo o venció."""
        self.cantidad_bloqueada -= cantidad

    def comprometer(self, reservada: Decimal, adjudicada: Decimal) -> None:
        """Adjudicación: lo adjudicado pasa de bloqueado a comprometido y el resto se libera."""
        self.cantidad_bloqueada -= reservada
        self.cantidad_comprometida += adjudicada

    # Los usa la liberación (I-3.5) al informar una actividad cumplida. Cuál de los dos
    # corresponde lo decide tipo_recurso.reutilizable.

    def liberar(self, cantidad: Decimal) -> None:
        """Recurso reutilizable (personal, carpas): vuelve a estar disponible."""
        self.cantidad_comprometida -= cantidad

    def consumir(self, cantidad: Decimal) -> None:
        """Recurso consumible (raciones, agua): se usó, así que también sale del stock."""
        self.cantidad_comprometida -= cantidad
        self.cantidad_total -= cantidad
