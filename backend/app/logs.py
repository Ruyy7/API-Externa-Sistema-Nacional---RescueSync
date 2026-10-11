"""Logging estructurado JSON, igual al usado por la webapp RescueSync."""

import json
import logging
import sys
import time

from flask import Flask, g, request


class FormatoJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
            **getattr(record, "contexto", {}),
        }
        if record.exc_info:
            evento["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(evento, ensure_ascii=False, default=str)


def configurar_logging(app: Flask) -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJSON())
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(app.config["LOG_LEVEL"])
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    @app.before_request
    def _marcar_inicio():
        g.inicio = time.perf_counter()

    @app.after_request
    def _registrar_pedido(respuesta):
        duracion_ms = round((time.perf_counter() - g.get("inicio", time.perf_counter())) * 1000, 1)
        logging.getLogger("http").info(
            "%s %s",
            request.method,
            request.path,
            extra={"contexto": {"estado": respuesta.status_code, "duracion_ms": duracion_ms}},
        )
        return respuesta
