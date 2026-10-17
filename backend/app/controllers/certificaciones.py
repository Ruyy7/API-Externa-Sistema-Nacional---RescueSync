"""Catálogo nacional de certificaciones."""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.certificaciones import CertificacionFiltrosSchema, CertificacionSchema
from app.services import servicios

bp = Blueprint("Certificaciones", __name__, url_prefix="/api/v1", description="Certificaciones")


@bp.route("/certificaciones")
class Certificaciones(MethodView):
    @bp.arguments(CertificacionFiltrosSchema, location="query")
    @bp.response(200, CertificacionSchema(many=True))
    @bp.paginate()
    def get(self, filtros, pagination_parameters):
        """Catálogo de certificaciones conocidas por el Sistema Nacional."""
        items, total = servicios().certificaciones.listar(
            pagination_parameters.page,
            pagination_parameters.page_size,
            solo_activas=filtros["solo_activas"],
        )
        pagination_parameters.item_count = total
        return items
