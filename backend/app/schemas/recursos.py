from marshmallow import Schema, fields

from app.schemas import FiltrosSchema, TipoRecursoSchema


class TipoRecursoFiltrosSchema(FiltrosSchema):
    solo_activos = fields.Bool(load_default=True)


class DisponibilidadFiltrosSchema(FiltrosSchema):
    tipo_recurso_id = fields.Int(load_default=None, allow_none=True)
    ong_id = fields.Int(load_default=None, allow_none=True)
    solo_ongs_habilitadas = fields.Bool(load_default=True)


class InventarioRecursoSchema(Schema):
    tipo_recurso = fields.Nested(TipoRecursoSchema)
    cantidad_total = fields.Decimal(as_string=True)
    cantidad_bloqueada = fields.Decimal(as_string=True)
    cantidad_comprometida = fields.Decimal(as_string=True)
    cantidad_disponible = fields.Decimal(as_string=True)


class DisponibilidadGlobalSchema(Schema):
    tipo_recurso = fields.Nested(TipoRecursoSchema)
    cantidad_total = fields.Decimal(as_string=True)
    cantidad_bloqueada = fields.Decimal(as_string=True)
    cantidad_comprometida = fields.Decimal(as_string=True)
    cantidad_disponible = fields.Decimal(as_string=True)
