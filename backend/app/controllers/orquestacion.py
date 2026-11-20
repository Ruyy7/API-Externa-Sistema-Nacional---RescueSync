"""Operaciones del proceso que invoca Bonita como orquestador (docs/08-orquestacion-bonita.md).

Solo las puede llamar la cuenta de servicio de Bonita: la webapp no invoca la validación, el
bloqueo, el compromiso ni la liberación. Todas se ubican por la emergencia, que es la variable
`emergenciaId` del proceso, y reciben el JSON que Bonita le pide antes a la webapp. La liberación
final y el cierre (*Liberar recursos* y *Cerrar proyecto*) están en liberaciones.py.
"""

from flask.views import MethodView
from flask_jwt_extended import get_jwt_identity
from flask_smorest import Blueprint

from app.controllers.errores import documentar_errores
from app.schemas.orquestacion import (
    ActividadesEntradaSchema,
    ActividadesResultadoSchema,
    AdjudicacionEntradaSchema,
    AdjudicacionResultadoSchema,
    BloqueoPedidoSchema,
    BloqueoResultadoSchema,
    DesbloqueoResultadoSchema,
)
from app.security import ORQUESTADOR, SEGURIDAD, roles_required
from app.services import servicios

BONITA = ORQUESTADOR

bp = Blueprint(
    "Orquestación",
    __name__,
    url_prefix="/api/v1",
    description="Pasos del proceso que invoca Bonita: validación con bloqueo, compromiso de la "
    "adjudicación y liberación por actividad",
)

_DESCRIPCIONES = {
    404: "La emergencia no tiene una convocatoria validada con esa referencia, o la ONG no tiene "
    "un compromiso con esa categoría.",
    409: "Choca con el estado actual: la convocatoria ya se adjudicó, los bloqueos vencieron, el "
    "proyecto está cerrado o el recurso está ocupado (reintentar).",
    422: "Datos inválidos: tipo de recurso desconocido, fechas incoherentes o una adjudicación "
    "que supera lo bloqueado.",
}


def _errores(*codigos: int):
    return documentar_errores(bp, *codigos, descripciones=_DESCRIPCIONES)


@bp.route("/emergencias/<string:referencia>/bloqueo")
class BloqueoDeEmergencia(MethodView):
    @roles_required(BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(BloqueoPedidoSchema)
    @bp.response(200, BloqueoResultadoSchema)
    @_errores(401, 403, 409, 422)
    def post(self, pedido, referencia):
        """Valida las ofertas de la convocatoria y bloquea lo aceptado

        Es la tarea *Validar ofertas*: cuando vence la ventana, Bonita le pide a la webapp el
        listado consolidado de ofertas y lo envía acá. Cada línea se acepta total o parcialmente,
        o queda sin habilitar (sin rechazo binario), y lo aceptado queda bloqueado con
        SELECT ... FOR UPDATE hasta la adjudicación: ninguna otra emergencia puede llevárselo.
        La respuesta tiene el formato de POST /validaciones. Repetirlo reemplaza los bloqueos de
        la convocatoria, así que sirve para un reintento y para validar de nuevo una convocatoria
        reabierta.
        """
        return servicios().orquestacion.validar_y_bloquear(referencia, pedido, get_jwt_identity())


@bp.route("/emergencias/<string:referencia>/desbloqueo")
class DesbloqueoDeEmergencia(MethodView):
    @roles_required(BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, DesbloqueoResultadoSchema)
    @_errores(401, 403, 409)
    def post(self, referencia):
        """Libera los bloqueos sin adjudicar de la emergencia

        Bonita lo llama cuando el coordinador decide *Reabrir convocatoria* o *Reformular
        lotes*: las ofertas pueden cambiar y se validan de nuevo al vencer la nueva ventana. No
        toca lo ya comprometido. Si no queda nada bloqueado, no cambia nada.
        """
        return servicios().orquestacion.desbloquear(referencia)


@bp.route("/emergencias/<string:referencia>/adjudicacion")
class AdjudicacionDeEmergencia(MethodView):
    @roles_required(BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(AdjudicacionEntradaSchema)
    @bp.response(200, AdjudicacionResultadoSchema)
    @_errores(401, 403, 404, 409, 422)
    def post(self, datos, referencia):
        """Compromete lo adjudicado y libera lo que no se adjudicó

        Es la tarea *Comprometer recursos*: Bonita le pide a la webapp qué adjudicó el municipio
        y lo envía acá. En una sola transacción, lo adjudicado pasa de bloqueado a comprometido y
        el resto de los bloqueos de la convocatoria se libera. Todo o nada: si una adjudicación
        no es válida, no se compromete ninguna. Repetir la misma adjudicación no cambia nada.
        """
        return servicios().orquestacion.comprometer_adjudicacion(referencia, datos)


@bp.route("/emergencias/<string:referencia>/actividades")
class ActividadesDeEmergencia(MethodView):
    @roles_required(BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ActividadesEntradaSchema)
    @bp.response(200, ActividadesResultadoSchema)
    @_errores(401, 403, 404, 409, 422)
    def post(self, datos, referencia):
        """Registra las actividades cumplidas y libera sus recursos

        Es la tarea *Marcar actividad como finalizada*: Bonita le pide a la webapp las
        actividades que todavía no informó y las envía acá. Cada una libera su cantidad de lo
        comprometido (lo reutilizable vuelve al stock, lo consumible se da de baja). Es
        idempotente por `actividad_referencia`: las que ya estaban registradas no liberan dos
        veces, y una lista vacía no cambia nada.
        """
        return servicios().orquestacion.registrar_actividades(
            referencia, datos["actividades"], get_jwt_identity()
        )
