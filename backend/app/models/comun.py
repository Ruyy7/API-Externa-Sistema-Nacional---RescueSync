"""Piezas compartidas del modelo del Sistema Nacional."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, Enum, Identity, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

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
