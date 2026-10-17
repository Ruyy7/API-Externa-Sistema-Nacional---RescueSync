"""Endpoints de I-3.5: actividades cumplidas, liberación de recursos y cierre del proyecto.

La webapp informa las actividades que las ONGs marcan como finalizadas [E-7]; Bonita libera lo
que quede y cierra el proyecto (*Liberar recursos* y *Cerrar proyecto*). El auditor consulta.
"""

from flask.views import MethodView
from flask_jwt_extended import get_jwt_identity
from flask_smorest import Blueprint

from app.controllers.errores import documentar_errores
from app.schemas.liberaciones import (
    ActividadEntradaSchema,
    ActividadFiltrosSchema,
    ActividadSchema,
)
from app.security import SEGURIDAD, RolSistema, roles_required
from app.services import servicios

WEBAPP, BONITA, AUDITOR = RolSistema.WEBAPP, RolSistema.BONITA, RolSistema.AUDITOR

bp = Blueprint(
    "Liberaciones",
    __name__,
    url_prefix="/api/v1",
    description="Liberación de recursos y cierre del proyecto (I-3.5)",
)

_DESCRIPCIONES = {
    404: "La ONG no tiene un compromiso con esa categoría en la emergencia, o la emergencia no "
    "existe.",
    409: "Choca con el estado actual: la cantidad supera lo pendiente, el compromiso no está "
    "COMPROMETIDO, la referencia ya se usó con otros datos, el proyecto está cerrado, quedan "
    "recursos sin liberar, o el recurso está ocupado (reintentar).",
    422: "Datos inválidos: ONG inexistente, tipo de recurso desconocido, cantidad no entera, "
    "fecha futura o compromiso ambiguo (indicar oferta_referencia).",
}


def _errores(*codigos: int):
    return documentar_errores(bp, *codigos, descripciones=_DESCRIPCIONES)


@bp.route("/actividades")
class Actividades(MethodView):
    @roles_required(WEBAPP, BONITA, AUDITOR)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ActividadFiltrosSchema, location="query")
    @bp.response(200, ActividadSchema(many=True))
    @bp.paginate()
    @_errores(401, 403)
    def get(self, filtros, pagination_parameters):
        """Historial de actividades cumplidas y liberaciones"""
        actividades, total = servicios().liberaciones.listar_actividades(
            filtros, pagination_parameters.page, pagination_parameters.page_size
        )
        pagination_parameters.item_count = total
        return actividades

    @roles_required(WEBAPP, BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ActividadEntradaSchema)
    @bp.response(201, ActividadSchema)
    @bp.alt_response(
        200,
        schema=ActividadSchema,
        description="Reintento: la actividad ya estaba registrada y no se libera de nuevo.",
    )
    @_errores(401, 403, 404, 409, 422)
    def post(self, datos):
        """Registra una actividad cumplida y libera sus recursos

        La webapp lo llama cuando la ONG marca una actividad como finalizada: para esta
        emergencia, esta ONG y esta categoría, tantos recursos terminaron su tarea en tal fecha.
        Con el compromiso y la fila de inventario bloqueados (SELECT ... FOR UPDATE), descuenta
        esa cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible
        sale del stock. Cuando no queda nada pendiente, el compromiso pasa a FINALIZADO.
        """
        actividad, es_nueva = servicios().liberaciones.registrar_actividad(
            datos, get_jwt_identity()
        )
        return actividad, 201 if es_nueva else 200


@bp.route("/actividades/<int:actividad_id>")
class ActividadPorId(MethodView):
    @roles_required(WEBAPP, BONITA, AUDITOR)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, ActividadSchema)
    @_errores(401, 403, 404)
    def get(self, actividad_id):
        """Detalle de una actividad"""
        return servicios().liberaciones.obtener_actividad(actividad_id)
