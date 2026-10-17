from marshmallow import Schema, fields

from app.schemas import FiltrosSchema


class CertificacionFiltrosSchema(FiltrosSchema):
    solo_activas = fields.Bool(load_default=True)


class CertificacionSchema(Schema):
    id = fields.Int()
    codigo = fields.Str()
    nombre = fields.Str()
    descripcion = fields.Str(allow_none=True)
    activa = fields.Bool()


class ONGCertificacionSchema(Schema):
    certificacion = fields.Nested(CertificacionSchema)
    fecha_emision = fields.Date()
    fecha_vencimiento = fields.Date(allow_none=True)
    vigente = fields.Bool()
