"""Catálogo de recursos y disponibilidad global."""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas import TipoRecursoSchema
from app.schemas.recursos import (
    DisponibilidadFiltrosSchema,
    DisponibilidadGlobalSchema,
    TipoRecursoFiltrosSchema,
)
from app.services import servicios

bp = Blueprint("Recursos", __name__, url_prefix="/api/v1", description="Recursos")


@bp.route("/tipos")
class TiposRecurso(MethodView):
    @bp.arguments(TipoRecursoFiltrosSchema, location="query")
    @bp.response(200, TipoRecursoSchema(many=True))
    @bp.paginate()
    def get(self, filtros, pagination_parameters):
        """Catálogo nacional de tipos de recurso, con los códigos de RescueSync."""
        items, total = servicios().recursos.tipos(
            pagination_parameters.page,
            pagination_parameters.page_size,
            solo_activos=filtros["solo_activos"],
        )
        pagination_parameters.item_count = total
        return items


@bp.route("/recursos/disponibilidad")
class Disponibilidad(MethodView):
    @bp.arguments(DisponibilidadFiltrosSchema, location="query")
    @bp.response(200, DisponibilidadGlobalSchema(many=True))
    @bp.paginate()
    def get(self, filtros, pagination_parameters):
        """Disponibilidad agregada por tipo de recurso.

        Por defecto suma solo inventarios de ONGs habilitadas. Puede filtrarse por ONG o por
        tipo de recurso sin cambiar el contrato de respuesta.
        """
        items, total = servicios().recursos.disponibilidad_global(
            pagination_parameters.page,
            pagination_parameters.page_size,
            tipo_recurso_id=filtros.get("tipo_recurso_id"),
            ong_id=filtros.get("ong_id"),
            solo_ongs_habilitadas=filtros["solo_ongs_habilitadas"],
        )
        pagination_parameters.item_count = total
        return items
