"""Consulta de tipos de recurso e inventario disponible."""

from app.models import InventarioRecurso, TipoRecurso
from app.repositories.recursos import DisponibilidadGlobal, RecursoRepository
from app.services.ongs import ONGService


class RecursoService:
    def __init__(self, recursos: RecursoRepository, ongs: ONGService):
        self.recursos = recursos
        self.ongs = ongs

    def tipos(
        self, pagina: int, tamano: int, *, solo_activos: bool = True
    ) -> tuple[list[TipoRecurso], int]:
        return self.recursos.tipos(pagina, tamano, solo_activos=solo_activos)

    def inventario_de_ong(self, ong_id: int) -> list[InventarioRecurso]:
        self.ongs.obtener(ong_id)
        return self.recursos.inventario_de_ong(ong_id)

    def disponibilidad_global(
        self,
        pagina: int,
        tamano: int,
        *,
        tipo_recurso_id: int | None = None,
        ong_id: int | None = None,
        solo_ongs_habilitadas: bool = True,
    ) -> tuple[list[DisponibilidadGlobal], int]:
        if ong_id is not None:
            self.ongs.obtener(ong_id)
        return self.recursos.disponibilidad_global(
            pagina,
            tamano,
            tipo_recurso_id=tipo_recurso_id,
            ong_id=ong_id,
            solo_ongs_habilitadas=solo_ongs_habilitadas,
        )
