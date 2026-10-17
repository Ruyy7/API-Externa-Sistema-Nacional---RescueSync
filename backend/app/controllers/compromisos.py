"""Endpoints de I-3.4: validar restricciones y bloquear o comprometer recursos.

Todos exigen el token de una cuenta de servicio. La webapp reserva, ajusta y cancela; la
confirmación de lo adjudicado la puede enviar la webapp o Bonita.
"""

from flask.views import MethodView
from flask_jwt_extended import get_jwt_identity
from flask_smorest import Blueprint

from app.controllers.errores import documentar_errores
from app.schemas.compromisos import (
    AjusteEntradaSchema,
    CompromisoFiltrosSchema,
    CompromisoSchema,
    ConfirmacionEntradaSchema,
    ReservaEntradaSchema,
    VerificacionEntradaSchema,
    VerificacionSchema,
)
from app.security import SEGURIDAD, RolSistema, roles_required
from app.services import servicios

WEBAPP, BONITA, AUDITOR = RolSistema.WEBAPP, RolSistema.BONITA, RolSistema.AUDITOR

bp = Blueprint(
    "Compromisos",
    __name__,
    url_prefix="/api/v1",
    description="Bloqueo y compromiso de recursos (I-3.4)",
)


def _errores(*codigos: int):
    return documentar_errores(bp, *codigos)


@bp.route("/compromisos/verificacion")
class Verificacion(MethodView):
    @roles_required(WEBAPP, BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(VerificacionEntradaSchema)
    @bp.response(200, VerificacionSchema)
    @_errores(401, 403, 422)
    def post(self, datos):
        """Valida restricciones sin reservar nada

        Comprueba que la ONG esté habilitada y que los tipos de recurso y las cantidades sean
        válidos, y devuelve por ítem cuánto hay disponible: DISPONIBLE, PARCIAL o
        SIN_DISPONIBILIDAD. No bloquea nada: la reserva vuelve a validar con las filas bloqueadas.
        """
        return servicios().compromisos.verificar(datos)


@bp.route("/compromisos")
class Compromisos(MethodView):
    @roles_required(WEBAPP, BONITA, AUDITOR)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(CompromisoFiltrosSchema, location="query")
    @bp.response(200, CompromisoSchema(many=True))
    @bp.paginate()
    @_errores(401, 403)
    def get(self, filtros, pagination_parameters):
        """Lista reservas y compromisos"""
        compromisos, total = servicios().compromisos.listar(
            filtros, pagination_parameters.page, pagination_parameters.page_size
        )
        pagination_parameters.item_count = total
        return compromisos

    @roles_required(WEBAPP)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ReservaEntradaSchema)
    @bp.response(201, CompromisoSchema)
    @bp.alt_response(
        200, schema=CompromisoSchema, description="Reintento: ya existía con el mismo pedido."
    )
    @_errores(401, 403, 409, 422)
    def post(self, datos):
        """Reserva (bloquea) los recursos de una oferta presentada

        La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario
        (SELECT ... FOR UPDATE), valida la disponibilidad y descuenta lo reservado, todo en una
        transacción: dos pedidos simultáneos nunca reservan más de lo que hay. Si no alcanza,
        responde 409 RECURSOS_INSUFICIENTES y no reserva nada.
        """
        compromiso, es_nuevo = servicios().compromisos.reservar(datos, get_jwt_identity())
        return compromiso, 201 if es_nuevo else 200


@bp.route("/compromisos/<int:compromiso_id>")
class CompromisoPorId(MethodView):
    @roles_required(WEBAPP, BONITA, AUDITOR)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, CompromisoSchema)
    @_errores(401, 403, 404)
    def get(self, compromiso_id):
        """Detalle de una reserva o compromiso"""
        return servicios().compromisos.obtener(compromiso_id)

    @roles_required(WEBAPP)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(AjusteEntradaSchema)
    @bp.response(200, CompromisoSchema)
    @_errores(401, 403, 404, 409, 422)
    def put(self, datos, compromiso_id):
        """Ajusta la reserva cuando la ONG modifica la oferta

        Solo dentro de la ventana de ofertas. Lo que aumenta necesita disponibilidad; lo que baja o
        desaparece se libera. Si algo no alcanza, la reserva queda como estaba.
        """
        return servicios().compromisos.ajustar(compromiso_id, datos)


@bp.route("/compromisos/<int:compromiso_id>/cancelacion")
class Cancelacion(MethodView):
    @roles_required(WEBAPP)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, CompromisoSchema)
    @_errores(401, 403, 404, 409)
    def post(self, compromiso_id):
        """Cancela la reserva cuando la ONG retira la oferta y libera los recursos"""
        return servicios().compromisos.cancelar(compromiso_id)


@bp.route("/compromisos/<int:compromiso_id>/confirmacion")
class Confirmacion(MethodView):
    @roles_required(WEBAPP, BONITA)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ConfirmacionEntradaSchema)
    @bp.response(200, CompromisoSchema)
    @_errores(401, 403, 404, 409, 422)
    def post(self, datos, compromiso_id):
        """Compromete lo adjudicado por el municipio

        Lo llama la webapp al registrar la adjudicación, o Bonita desde la tarea *Comprometer
        recursos*. Lo adjudicado pasa de bloqueado a comprometido y la diferencia de una
        adjudicación parcial se libera en ese momento. Si ya terminó la ventana de adjudicación,
        la reserva vence y responde 409 RESERVA_VENCIDA.
        """
        return servicios().compromisos.confirmar(compromiso_id, datos)
