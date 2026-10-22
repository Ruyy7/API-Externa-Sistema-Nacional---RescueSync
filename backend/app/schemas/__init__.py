"""DTO/Schemas: contrato HTTP y fuente de OpenAPI."""

from marshmallow import EXCLUDE, Schema, ValidationError, fields, pre_load


class FiltrosSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class FiltrosEstrictosSchema(FiltrosSchema):
    """Filtros del catálogo (I-3.2): un parámetro mal escrito (`habilitadas=true`) responde 422 en
    lugar de ignorarse y devolver el listado sin filtrar. `page` y `page_size` los lee
    @bp.paginate(), así que se aceptan aunque el schema no los declare."""

    PARAMETROS_DE_PAGINACION = {"page", "page_size"}

    @pre_load
    def _rechazar_desconocidos(self, datos, **_kwargs):
        desconocidos = set(datos) - set(self.fields) - self.PARAMETROS_DE_PAGINACION
        if desconocidos:
            raise ValidationError(
                {nombre: ["Parámetro desconocido."] for nombre in sorted(desconocidos)}
            )
        return datos


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
