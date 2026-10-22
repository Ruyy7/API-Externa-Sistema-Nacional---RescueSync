"""Endpoints de ONGs: consulta (I-3.2) y registro con sus categorías (I-3.1).

Las consultas que devuelven datos de contacto (CUIT, email, teléfono) exigen el token de una
cuenta de servicio. Una ONG consulta sus propios datos con /ongs/yo.
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.controllers.errores import documentar_errores
from app.schemas.certificaciones import ONGCertificacionSchema
from app.schemas.cuentas import CategoriasEntradaSchema, ONGRegistradaSchema, RegistroONGSchema
from app.schemas.ongs import ONGFiltrosSchema, ONGSchema
from app.schemas.recursos import InventarioRecursoSchema
from app.security import (
    ROLES_DE_SERVICIO,
    SEGURIDAD,
    RolSistema,
    cuit_del_token,
    roles_required,
)
from app.services import servicios

bp = Blueprint("ONGs", __name__, url_prefix="/api/v1", description="ONGs")


def _errores(*codigos: int):
    return documentar_errores(bp, *codigos)


@bp.route("/ongs")
class ONGs(MethodView):
    @roles_required(*ROLES_DE_SERVICIO)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(ONGFiltrosSchema, location="query")
    @bp.response(200, ONGSchema(many=True))
    @bp.paginate()
    @_errores(401, 403)
    def get(self, filtros, pagination_parameters):
        """Lista ONGs; `habilitada=true` devuelve únicamente ONGs habilitadas."""
        ongs, total = servicios().ongs.listar(
            pagination_parameters.page,
            pagination_parameters.page_size,
            habilitada=filtros.get("habilitada"),
        )
        pagination_parameters.item_count = total
        return ongs

    @bp.arguments(RegistroONGSchema)
    @bp.response(201, ONGRegistradaSchema)
    @bp.alt_response(409, description="CUIT o email ya registrados")
    def post(self, datos):
        """Registro directo de una ONG (I-3.1), sin aprobación posterior.

        La ONG se inscribe en categorías (tipos de recurso del catálogo) y declara el máximo que
        puede aportar en cada una. Queda habilitada y con una cuenta para iniciar sesión con su
        email y su contraseña.
        """
        return servicios().onboarding.registrar(datos)


@bp.route("/ongs/yo")
class MiONG(MethodView):
    @roles_required(RolSistema.ONG)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, ONGRegistradaSchema)
    def get(self):
        """La ONG dueña del token, con sus categorías y lo disponible en cada una."""
        return servicios().onboarding.mi_ong(cuit_del_token())


@bp.route("/ongs/yo/categorias")
class MisCategorias(MethodView):
    @roles_required(RolSistema.ONG)
    @bp.doc(security=SEGURIDAD)
    @bp.arguments(CategoriasEntradaSchema)
    @bp.response(200, ONGRegistradaSchema)
    @bp.alt_response(409, description="Un tope quedaría por debajo de lo reservado o comprometido")
    def put(self, datos):
        """Reemplaza las categorías y los topes de la ONG dueña del token.

        No se puede bajar un tope por debajo de lo ya reservado más lo comprometido, ni quitar una
        categoría que ya se usó en reservas.
        """
        return servicios().onboarding.actualizar_categorias(cuit_del_token(), datos["categorias"])


@bp.route("/ongs/<int:ong_id>")
class ONPorId(MethodView):
    @roles_required(*ROLES_DE_SERVICIO)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, ONGSchema)
    @_errores(401, 403, 404)
    def get(self, ong_id):
        """Detalle de una ONG registrada en el Sistema Nacional."""
        return servicios().ongs.obtener(ong_id)


@bp.route("/ongs/<int:ong_id>/certificaciones")
class CertificacionesDeONG(MethodView):
    @roles_required(*ROLES_DE_SERVICIO)
    @bp.doc(security=SEGURIDAD)
    @bp.response(200, ONGCertificacionSchema(many=True))
    @_errores(401, 403, 404)
    def get(self, ong_id):
        """Certificaciones declaradas para una ONG, con vigencia y fechas."""
        return servicios().certificaciones.de_ong(ong_id)


@bp.route("/ongs/<int:ong_id>/recursos")
class RecursosDeONG(MethodView):
    @bp.response(200, InventarioRecursoSchema(many=True))
    def get(self, ong_id):
        """Inventario y disponibilidad actual de una ONG."""
        return servicios().recursos.inventario_de_ong(ong_id)
