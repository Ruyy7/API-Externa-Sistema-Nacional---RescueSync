"""Actividades cumplidas y cierre del proyecto (I-3.5).

Una actividad libera una parte de un ítem comprometido: lo reutilizable vuelve al stock y lo
consumible se da de baja. El acumulado vive en `compromiso_item.cantidad_liberada`; esta tabla es
el historial que pidió el docente ("para esta emergencia, para esta ONG, para esta categoría y
estos recursos, se cumplió la tarea en tal fecha y con tales observaciones").
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.compromisos import CompromisoItem
from app.models.comun import ConMarcasDeTiempo, IdGrande, columna_enum
from app.models.enums import AccionLiberacion, OrigenActividad


class Actividad(ConMarcasDeTiempo, db.Model):
    """Liberación de una parte de un ítem comprometido. Solo se inserta: es historial."""

    __tablename__ = "actividad"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        # La referencia es el id de la actividad en la webapp: la traen las informadas por la ONG
        # (y hace de clave de idempotencia); las que genera el cierre no tienen.
        CheckConstraint(
            "(origen = 'INFORMADA') = (referencia IS NOT NULL)",
            name="referencia_solo_si_informada",
        ),
    )

    id: Mapped[IdGrande]
    referencia: Mapped[str | None] = mapped_column(String(100), unique=True)
    # Sin ondelete a propósito: un ítem con historial no se puede borrar
    compromiso_item_id: Mapped[int] = mapped_column(ForeignKey("compromiso_item.id"), index=True)
    origen: Mapped[OrigenActividad] = mapped_column(
        columna_enum(OrigenActividad, "origen_actividad")
    )
    accion: Mapped[AccionLiberacion] = mapped_column(
        columna_enum(AccionLiberacion, "accion_liberacion")
    )
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # La fecha en que la ONG cumplió la tarea, informada por el cliente (no la del registro)
    fecha_cumplimiento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observaciones: Mapped[str | None] = mapped_column(Text)
    # Identidad del token que la registró, como `creado_por` en compromiso
    registrada_por: Mapped[str] = mapped_column(String(100))

    item: Mapped[CompromisoItem] = relationship(back_populates="actividades")


class CierreProyecto(ConMarcasDeTiempo, db.Model):
    """Cierre del proyecto de una emergencia (tarea *Cerrar proyecto* del BPMN).

    La emergencia vive en la webapp y acá solo se la conoce por su referencia; el cierre es su
    único dato propio en el Sistema Nacional. El UNIQUE hace al cierre idempotente: cerrar dos veces
    devuelve el mismo cierre.
    """

    __tablename__ = "cierre_proyecto"

    id: Mapped[IdGrande]
    emergencia_referencia: Mapped[str] = mapped_column(String(100), unique=True)
    fecha_cierre: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observaciones: Mapped[str | None] = mapped_column(Text)
    cerrado_por: Mapped[str] = mapped_column(String(100))
