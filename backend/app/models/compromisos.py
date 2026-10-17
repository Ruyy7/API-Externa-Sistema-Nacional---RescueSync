"""Reserva, adjudicación y liberación de recursos de las ONGs (I-3.4).

Los contadores vivos están en `inventario_recurso` (bloqueado y comprometido). Estas tablas guardan
qué oferta reservó o comprometió cada cantidad, y en qué estado está.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.catalogos import TipoRecurso
from app.models.comun import ConCicloDeVida, ConMarcasDeTiempo, IdGrande, ahora, columna_enum
from app.models.enums import EstadoCompromiso
from app.models.organizaciones import ONG
from app.models.recursos import InventarioRecurso


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
    # Id de la emergencia en la webapp: la liberación (I-3.5) y Bonita buscan por emergencia
    emergencia_referencia: Mapped[str] = mapped_column(String(100), index=True)
    fecha_cierre: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_limite_adjudicacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    compromisos: Mapped[list[Compromiso]] = relationship(
        back_populates="convocatoria", cascade="all, delete-orphan"
    )


class Compromiso(ConMarcasDeTiempo, ConCicloDeVida, db.Model):
    """Reserva/compromiso de una ONG dentro de una oferta de RescueSync.

    Ciclo de vida (patrón State): RESERVADO cuando la ONG presenta la oferta; COMPROMETIDO cuando
    el municipio la adjudica; CANCELADO si la ONG la retira; VENCIDO si termina la ventana de
    adjudicación sin adjudicarla. FINALIZADO lo usa la liberación (I-3.5).
    """

    __tablename__ = "compromiso"
    __table_args__ = (
        UniqueConstraint("oferta_referencia", "ong_id"),
        # Destino de la FK compuesta de compromiso_item: el ítem es de la misma ONG
        UniqueConstraint("id", "ong_id"),
        CheckConstraint(
            "estado NOT IN ('COMPROMETIDO', 'FINALIZADO') OR confirmado_en IS NOT NULL",
            name="confirmado_con_fecha",
        ),
        CheckConstraint(
            "estado <> 'CANCELADO' OR cancelado_en IS NOT NULL", name="cancelado_con_fecha"
        ),
        CheckConstraint("estado <> 'VENCIDO' OR vencido_en IS NOT NULL", name="vencido_con_fecha"),
        CheckConstraint(
            "estado <> 'FINALIZADO' OR finalizado_en IS NOT NULL", name="finalizado_con_fecha"
        ),
        # Lo recorre el vencimiento automático de las reservas
        Index(
            "ix_compromiso_reservados",
            "convocatoria_id",
            postgresql_where=text("estado = 'RESERVADO'"),
        ),
    )

    NOMBRE = "el compromiso"
    TRANSICIONES = {
        EstadoCompromiso.RESERVADO: {
            EstadoCompromiso.COMPROMETIDO,
            EstadoCompromiso.CANCELADO,
            EstadoCompromiso.VENCIDO,
        },
        EstadoCompromiso.COMPROMETIDO: {EstadoCompromiso.FINALIZADO},
        EstadoCompromiso.CANCELADO: set(),
        EstadoCompromiso.VENCIDO: set(),
        EstadoCompromiso.FINALIZADO: set(),
    }
    # Columna que registra cuándo ocurrió cada transición (la exigen los CHECK de la tabla)
    FECHA_DE_TRANSICION = {
        EstadoCompromiso.COMPROMETIDO: "confirmado_en",
        EstadoCompromiso.CANCELADO: "cancelado_en",
        EstadoCompromiso.VENCIDO: "vencido_en",
        EstadoCompromiso.FINALIZADO: "finalizado_en",
    }

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
    # Identidad del token que hizo la reserva (la cuenta de servicio), para trazabilidad
    creado_por: Mapped[str] = mapped_column(String(100))
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vencido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # La completa la liberación (I-3.5) al pasar a FINALIZADO
    finalizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    convocatoria: Mapped[Convocatoria] = relationship(back_populates="compromisos")
    ong: Mapped[ONG] = relationship()
    items: Mapped[list[CompromisoItem]] = relationship(
        back_populates="compromiso",
        cascade="all, delete-orphan",
        order_by="CompromisoItem.id",
        primaryjoin="Compromiso.id == CompromisoItem.compromiso_id",
        foreign_keys="CompromisoItem.compromiso_id",
    )

    def transicionar(self, nuevo: EstadoCompromiso) -> None:
        """Cambia el estado y registra cuándo, en el mismo paso: si la sesión hace flush en el
        medio de la operación, la fila nunca queda en un estado sin su fecha."""
        super().transicionar(nuevo)
        if (columna := self.FECHA_DE_TRANSICION.get(nuevo)) is not None:
            setattr(self, columna, ahora())

    def vencio(self, momento: datetime) -> bool:
        """Una reserva vence cuando termina la ventana de adjudicación de su convocatoria."""
        return (
            self.estado == EstadoCompromiso.RESERVADO
            and self.convocatoria.fecha_limite_adjudicacion <= momento
        )

    def cantidades_reservadas(self) -> dict[str, Decimal]:
        return {item.tipo_recurso.codigo: item.cantidad_reservada for item in self.items}

    def cantidades_comprometidas(self) -> dict[str, Decimal]:
        return {item.tipo_recurso.codigo: item.cantidad_comprometida for item in self.items}


class CompromisoItem(ConMarcasDeTiempo, db.Model):
    """Cantidades reservadas y comprometidas para un recurso concreto.

    Los ítems quedan como historial: al cancelar o vencer no se ponen en cero, porque el estado vive
    en el compromiso. La columna ong_id está repetida a propósito: con las dos FK compuestas, la
    base garantiza que el inventario reservado sea de la misma ONG del compromiso.
    """

    __tablename__ = "compromiso_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["compromiso_id", "ong_id"],
            ["compromiso.id", "compromiso.ong_id"],
            name="fk_compromiso_item_compromiso_ong",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["inventario_recurso_id", "ong_id"],
            ["inventario_recurso.id", "inventario_recurso.ong_id"],
            name="fk_compromiso_item_inventario_ong",
        ),
        UniqueConstraint("compromiso_id", "inventario_recurso_id"),
        CheckConstraint("cantidad_reservada >= 0", name="cantidad_reservada_no_negativa"),
        CheckConstraint("cantidad_comprometida >= 0", name="cantidad_comprometida_no_negativa"),
        CheckConstraint(
            "cantidad_reservada + cantidad_comprometida > 0",
            name="item_con_cantidad_positiva",
        ),
        CheckConstraint(
            "cantidad_comprometida <= cantidad_reservada",
            name="comprometida_no_supera_reservada",
        ),
    )

    id: Mapped[IdGrande]
    compromiso_id: Mapped[int] = mapped_column(index=True)
    ong_id: Mapped[int]
    inventario_recurso_id: Mapped[int] = mapped_column(index=True)
    cantidad_reservada: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    cantidad_comprometida: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )

    compromiso: Mapped[Compromiso] = relationship(
        back_populates="items",
        primaryjoin="CompromisoItem.compromiso_id == Compromiso.id",
        foreign_keys="CompromisoItem.compromiso_id",
    )
    inventario_recurso: Mapped[InventarioRecurso] = relationship(
        primaryjoin="CompromisoItem.inventario_recurso_id == InventarioRecurso.id",
        foreign_keys="CompromisoItem.inventario_recurso_id",
    )

    @property
    def tipo_recurso(self) -> TipoRecurso:
        return self.inventario_recurso.tipo_recurso
