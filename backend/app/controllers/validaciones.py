"""Validación por niveles de competencia (I-3.3)."""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.validaciones import ValidacionPedidoSchema, ValidacionResultadoSchema
from app.security import ORQUESTADOR, SEGURIDAD, roles_required
from app.services import servicios

bp = Blueprint(
    "Validaciones",
    __name__,
    url_prefix="/api/v1",
    description="Validación por niveles de competencia",
)


@bp.route("/validaciones")
class Validaciones(MethodView):
    @roles_required(ORQUESTADOR)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ValidacionPedidoSchema)
    @bp.response(200, ValidacionResultadoSchema)
    def post(self, pedido):
        """Evalúa las ofertas de una convocatoria sin rechazarlas en bloque.

        Cada línea se compara con la categoría en que se inscribió la ONG y con lo que le queda
        disponible (máximo menos reservas y compromisos de otras ofertas). Puede quedar aceptada
        total o parcialmente, o sin habilitar, y trae el rol sugerido en su lote. No bloquea
        recursos: el proceso usa `POST /emergencias/{ref}/bloqueo`, que valida y bloquea a la vez.
        """
        return servicios().validaciones.validar(pedido)
