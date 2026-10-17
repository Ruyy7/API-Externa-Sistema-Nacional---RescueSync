"""Contrato del login y del registro de ONGs (I-3.1)."""

import re
from decimal import Decimal

from marshmallow import Schema, ValidationError, fields, validate

from app.schemas.ongs import ONGSchema
from app.schemas.recursos import InventarioRecursoSchema

_FORMATO_CUIT = re.compile(r"^\d{2}-\d{8}-\d$")
_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def cuit_valido(cuit: str) -> bool:
    """Formato XX-XXXXXXXX-X y dígito verificador (módulo 11, como lo calcula AFIP/ARCA)."""
    if not _FORMATO_CUIT.match(cuit):
        return False
    digitos = [int(c) for c in cuit if c.isdigit()]
    resto = sum(d * p for d, p in zip(digitos[:10], _PESOS_CUIT, strict=True)) % 11
    verificador = {0: 0, 1: None}.get(resto, 11 - resto)
    return verificador == digitos[10]


def _validar_cuit(cuit: str) -> None:
    if not cuit_valido(cuit):
        raise ValidationError(
            "CUIT inválido: tiene que tener el formato XX-XXXXXXXX-X y un "
            "dígito verificador correcto."
        )


class LoginSchema(Schema):
    usuario = fields.Str(required=True, validate=validate.Length(min=1, max=254))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=1, max=128))


class TokenSchema(Schema):
    access_token = fields.Str()
    token_type = fields.Str()
    expira_en_segundos = fields.Int()
    rol = fields.Str()


class CategoriaEntradaSchema(Schema):
    """Categoría en la que se inscribe la ONG y el máximo que puede aportar en ella."""

    tipo_recurso = fields.Str(required=True, validate=validate.Length(min=1, max=40))
    cantidad_maxima = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=Decimal("0.01"), max=Decimal("9999999999.99")),
    )


_CATEGORIAS = fields.List(
    fields.Nested(CategoriaEntradaSchema),
    required=True,
    validate=validate.Length(min=1, max=100),
)


class RegistroONGSchema(Schema):
    razon_social = fields.Str(required=True, validate=validate.Length(min=3, max=160))
    cuit = fields.Str(required=True, validate=_validar_cuit)
    email_contacto = fields.Email(required=True, validate=validate.Length(max=254))
    telefono = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=40))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8, max=128))
    categorias = _CATEGORIAS


class CategoriasEntradaSchema(Schema):
    categorias = _CATEGORIAS


class ONGRegistradaSchema(ONGSchema):
    """La ONG con sus categorías: el máximo es `cantidad_total`."""

    categorias = fields.List(fields.Nested(InventarioRecursoSchema), attribute="inventario")
