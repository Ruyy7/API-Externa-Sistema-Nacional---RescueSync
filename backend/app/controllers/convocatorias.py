"""Endpoints de las convocatorias a las que pertenecen las reservas (I-3.4).

La convocatoria se registra sola con la primera reserva. Estos endpoints cubren reabrirla (fechas
nuevas) y reformularla (convocatoria nueva), que cambian cuándo vencen sus reservas.
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.controllers.errores import documentar_errores
from app.schemas.convocatorias import (
    ConvocatoriaSchema,
    FechasConvocatoriaSchema,
    ReformulacionEntradaSchema,
    ReformulacionSchema,
)
from app.security import SEGURIDAD, RolSistema, roles_required
from app.services import servicios

WEBAPP, BONITA, AUDITOR = RolSistema.WEBAPP, RolSistema.BONITA, RolSistema.AUDITOR

bp = Blueprint(
    "Convocatorias",
    __name__,
    url_prefix="/api/v1",
    description="Convocatorias y vencimiento de las reservas (I-3.4)",
)


def _errores(*codigos: int):
    return documentar_errores(bp, *codigos)


@bp.route("/convocatorias/<string:referencia>")
class ConvocatoriaPorReferencia(MethodView):
    @roles_required(WEBAPP, BONITA, AUDITOR)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, ConvocatoriaSchema)
    @_errores(401, 403, 404)
    def get(self, referencia):
        """Fechas de una convocatoria"""
        return servicios().convocatorias.obtener(referencia)

    @roles_required(WEBAPP, BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(FechasConvocatoriaSchema)
    @bp.response(200, ConvocatoriaSchema)
    @_errores(401, 403, 404, 422)
    def put(self, datos, referencia):
        """Reabre la convocatoria con fechas nuevas

        Las reservas vigentes pasan a vencer con la nueva fecha límite de adjudicación. Las que ya
        vencieron siguen vencidas.
        """
        return servicios().convocatorias.actualizar_fechas(referencia, datos)


@bp.route("/convocatorias/<string:referencia>/reformulacion")
class Reformulacion(MethodView):
    @roles_required(WEBAPP, BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ReformulacionEntradaSchema)
    @bp.response(200, ReformulacionSchema)
    @_errores(401, 403, 404, 409, 422)
    def post(self, datos, referencia):
        """Reformula la convocatoria: sus reservas vigentes pasan a la nueva"""
        convocatoria, movidos = servicios().convocatorias.reformular(referencia, datos["nueva"])
        return {"convocatoria": convocatoria, "compromisos_movidos": movidos}
