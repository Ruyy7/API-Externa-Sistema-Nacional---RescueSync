"""DTO/Schemas: contrato HTTP y fuente de OpenAPI."""

from marshmallow import EXCLUDE, Schema, fields


class FiltrosSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class UnidadMedidaSchema(Schema):
    id = fields.Int()
    codigo = fields.Str()
    nombre = fields.Str()
    admite_decimales = fields.Bool()


class TipoRecursoSchema(Schema):
    id = fields.Int()
    codigo = fields.Str()
    nombre = fields.Str()
    categoria = fields.Str()
    reutilizable = fields.Bool()
    unidad_medida = fields.Nested(UnidadMedidaSchema)
