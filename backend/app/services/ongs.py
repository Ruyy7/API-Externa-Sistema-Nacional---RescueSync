"""Casos de uso de consulta de ONGs."""

from app.errors import NoEncontrado
from app.models import ONG
from app.repositories.ongs import ONGRepository


class ONGService:
    def __init__(self, ongs: ONGRepository):
        self.ongs = ongs

    def listar(
        self, pagina: int, tamano: int, *, habilitada: bool | None = None
    ) -> tuple[list[ONG], int]:
        return self.ongs.listar(pagina, tamano, habilitada=habilitada)

    def obtener(self, ong_id: int) -> ONG:
        ong = self.ongs.obtener(ong_id)
        if ong is None:
            raise NoEncontrado("La ONG no existe.")
        return ong
