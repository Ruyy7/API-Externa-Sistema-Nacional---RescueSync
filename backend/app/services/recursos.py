"""Consulta de tipos de recurso e inventario disponible."""

from app.errors import NoEncontrado, ReglaDeNegocio
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
        # Un filtro que no puede coincidir con nada se informa, en vez de responder una lista vacía
        if ong_id is not None:
            ong = self.ongs.obtener(ong_id)
            if solo_ongs_habilitadas and not ong.habilitada:
                raise ReglaDeNegocio(
                    "La ONG no está habilitada. Para consultarla, enviar "
                    "solo_ongs_habilitadas=false."
                )
        if tipo_recurso_id is not None:
            tipo = self.recursos.tipo(tipo_recurso_id)
            if tipo is None or not tipo.activo:
                raise NoEncontrado("El tipo de recurso no existe o no está activo.")
        return self.recursos.disponibilidad_global(
            pagina,
            tamano,
            tipo_recurso_id=tipo_recurso_id,
            ong_id=ong_id,
            solo_ongs_habilitadas=solo_ongs_habilitadas,
        )
