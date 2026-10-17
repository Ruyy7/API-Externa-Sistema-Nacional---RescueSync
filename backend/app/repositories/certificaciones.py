from sqlalchemy import select

from app.extensions import db
from app.models import Certificacion, ONGCertificacion
from app.repositories import paginar_entidades


class CertificacionRepository:
    def listar(
        self, pagina: int, tamano: int, *, solo_activas: bool = True
    ) -> tuple[list[Certificacion], int]:
        consulta = select(Certificacion).order_by(Certificacion.nombre)
        if solo_activas:
            consulta = consulta.where(Certificacion.activa)
        return paginar_entidades(consulta, pagina, tamano)

    def de_ong(self, ong_id: int) -> list[ONGCertificacion]:
        consulta = (
            select(ONGCertificacion)
            .where(ONGCertificacion.ong_id == ong_id)
            .join(ONGCertificacion.certificacion)
            .order_by(Certificacion.nombre)
        )
        return list(db.session.scalars(consulta))
