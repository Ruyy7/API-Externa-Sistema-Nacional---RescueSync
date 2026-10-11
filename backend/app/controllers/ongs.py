"""Endpoints de consulta de ONGs."""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.certificaciones import ONGCertificacionSchema
from app.schemas.ongs import ONGFiltrosSchema, ONGSchema
from app.schemas.recursos import InventarioRecursoSchema
from app.services import servicios

bp = Blueprint("ONGs", __name__, url_prefix="/api/v1", description="ONGs")


@bp.route("/ongs")
class ONGs(MethodView):
    @bp.arguments(ONGFiltrosSchema, location="query")
    @bp.response(200, ONGSchema(many=True))
    @bp.paginate()
    def get(self, filtros, pagination_parameters):
        """Lista ONGs; `habilitada=true` devuelve únicamente ONGs habilitadas."""
        ongs, total = servicios().ongs.listar(
            pagination_parameters.page,
            pagination_parameters.page_size,
            habilitada=filtros.get("habilitada"),
        )
        pagination_parameters.item_count = total
        return ongs


@bp.route("/ongs/<int:ong_id>")
class ONPorId(MethodView):
    @bp.response(200, ONGSchema)
    def get(self, ong_id):
        """Detalle de una ONG registrada en el Sistema Nacional."""
        return servicios().ongs.obtener(ong_id)


@bp.route("/ongs/<int:ong_id>/certificaciones")
class CertificacionesDeONG(MethodView):
    @bp.response(200, ONGCertificacionSchema(many=True))
    def get(self, ong_id):
        """Certificaciones declaradas para una ONG, con vigencia y fechas."""
        return servicios().certificaciones.de_ong(ong_id)


@bp.route("/ongs/<int:ong_id>/recursos")
class RecursosDeONG(MethodView):
    @bp.response(200, InventarioRecursoSchema(many=True))
    def get(self, ong_id):
        """Inventario y disponibilidad actual de una ONG."""
        return servicios().recursos.inventario_de_ong(ong_id)
