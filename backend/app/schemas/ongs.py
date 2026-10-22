from marshmallow import Schema, fields

from app.schemas import FiltrosEstrictosSchema


class ONGFiltrosSchema(FiltrosEstrictosSchema):
    habilitada = fields.Bool(load_default=None, allow_none=True)


class ONGSchema(Schema):
    id = fields.Int()
    razon_social = fields.Str()
    cuit = fields.Str()
    email_contacto = fields.Str(allow_none=True)
    telefono = fields.Str(allow_none=True)
    estado = fields.Str()
    habilitada = fields.Bool()
    creado_en = fields.DateTime()
    actualizado_en = fields.DateTime()
