from sqlalchemy import select

from app.extensions import db
from app.models import EstadoONG, ONG
from app.repositories import paginar_entidades


class ONGRepository:
    def obtener(self, ong_id: int) -> ONG | None:
        return db.session.get(ONG, ong_id)

    def listar(
        self, pagina: int, tamano: int, *, habilitada: bool | None = None
    ) -> tuple[list[ONG], int]:
        consulta = select(ONG).order_by(ONG.razon_social)
        if habilitada is True:
            consulta = consulta.where(ONG.estado == EstadoONG.HABILITADA)
        elif habilitada is False:
            consulta = consulta.where(ONG.estado != EstadoONG.HABILITADA)
        return paginar_entidades(consulta, pagina, tamano)
