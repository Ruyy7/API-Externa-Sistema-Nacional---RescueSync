"""Casos de uso de consulta de certificaciones."""

from app.models import Certificacion, ONGCertificacion
from app.repositories.certificaciones import CertificacionRepository
from app.services.ongs import ONGService


class CertificacionService:
    def __init__(self, certificaciones: CertificacionRepository, ongs: ONGService):
        self.certificaciones = certificaciones
        self.ongs = ongs

    def listar(
        self, pagina: int, tamano: int, *, solo_activas: bool = True
    ) -> tuple[list[Certificacion], int]:
        return self.certificaciones.listar(pagina, tamano, solo_activas=solo_activas)

    def de_ong(self, ong_id: int) -> list[ONGCertificacion]:
        self.ongs.obtener(ong_id)
        return self.certificaciones.de_ong(ong_id)
