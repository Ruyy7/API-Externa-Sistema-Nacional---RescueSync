"""Piezas compartidas del modelo del Sistema Nacional."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, ClassVar

from sqlalchemy import BigInteger, DateTime, Enum, Identity, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.errors import TransicionInvalida

IdGrande = Annotated[int, mapped_column(BigInteger, Identity(always=True), primary_key=True)]
IdCatalogo = Annotated[int, mapped_column(SmallInteger, Identity(always=True), primary_key=True)]


def ahora() -> datetime:
    return datetime.now(UTC)


def columna_enum(enum: type[StrEnum], nombre: str) -> Enum:
    """Enum textual con CHECK para mantener migraciones simples y legibles."""
    return Enum(
        enum,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=30,
        validate_strings=True,
    )


class ConMarcasDeTiempo:
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConCicloDeVida:
    """Patrón State en su variante de tabla de transiciones, igual que en la webapp.

    Cada entidad declara TRANSICIONES = {estado_actual: {estados_permitidos}} y `transicionar`
    rechaza con 409 cualquier cambio que no esté declarado.
    """

    NOMBRE: ClassVar[str]
    TRANSICIONES: ClassVar[dict]

    def transicionar(self, nuevo: StrEnum) -> None:
        if nuevo not in self.TRANSICIONES[self.estado]:
            raise TransicionInvalida(
                f"No se puede pasar {self.NOMBRE} de {self.estado} a {nuevo}.",
                detalles={"estado_actual": str(self.estado), "estado_pedido": str(nuevo)},
            )
        self.estado = nuevo
