"""Contrato de POST /validaciones (I-3.3). Las cantidades viajan como texto decimal."""

from marshmallow import EXCLUDE, Schema, fields, validate

from app.models import MotivoNivel, NivelCompetencia, RolSugerido

_REFERENCIA = validate.Length(min=1, max=100)
_POSITIVA = validate.Range(min=0, min_inclusive=False)


class _Tolerante(Schema):
    # Bonita reenvía el JSON de la webapp: los campos que no usamos se ignoran en vez de fallar.
    class Meta:
        unknown = EXCLUDE


class ItemPedidoSchema(_Tolerante):
    lote_referencia = fields.Str(required=True, validate=_REFERENCIA)
    ong_cuit = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=13),
        metadata={"description": "ONG que aporta la línea (en un consorcio, cada una la suya)."},
    )
    tipo_recurso = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=40),
        metadata={"description": "Código del catálogo compartido con la webapp."},
    )
    cantidad_requerida = fields.Decimal(
        required=True,
        places=2,
        as_string=True,
        validate=_POSITIVA,
        metadata={"description": "Lo que pide el lote; define si la línea es PRINCIPAL o APOYO."},
    )
    cantidad_ofrecida = fields.Decimal(required=True, places=2, as_string=True, validate=_POSITIVA)


class OfertaPedidoSchema(_Tolerante):
    oferta_referencia = fields.Str(required=True, validate=_REFERENCIA)
    items = fields.List(
        fields.Nested(ItemPedidoSchema), required=True, validate=validate.Length(min=1)
    )


class ValidacionPedidoSchema(_Tolerante):
    convocatoria_referencia = fields.Str(required=True, validate=_REFERENCIA)
    ofertas = fields.List(
        fields.Nested(OfertaPedidoSchema), required=True, validate=validate.Length(min=1)
    )


class ItemResultadoSchema(Schema):
    lote_referencia = fields.Str()
    ong_cuit = fields.Str()
    tipo_recurso = fields.Str()
    cantidad_requerida = fields.Decimal(places=2, as_string=True)
    cantidad_ofrecida = fields.Decimal(places=2, as_string=True)
    cantidad_habilitada = fields.Decimal(
        places=2,
        as_string=True,
        metadata={"description": "Lo que la ONG todavía puede aportar en esa categoría."},
    )
    cantidad_aceptada = fields.Decimal(places=2, as_string=True)
    nivel = fields.Enum(NivelCompetencia)
    motivo = fields.Enum(MotivoNivel, allow_none=True)
    rol_sugerido = fields.Enum(RolSugerido, allow_none=True)


class OfertaResultadoSchema(Schema):
    oferta_referencia = fields.Str()
    nivel = fields.Enum(NivelCompetencia)
    items = fields.List(fields.Nested(ItemResultadoSchema))


class ValidacionResultadoSchema(Schema):
    convocatoria_referencia = fields.Str()
    ofertas = fields.List(fields.Nested(OfertaResultadoSchema))
