"""
Registro de errores internos de la aplicación.

El .exe se genera con --windowed, así que los print() no se ven en ningún sitio.
Los errores se guardan en %APPDATA%\\MonitorUART\\monitoruart.log.
"""

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from utils.rutas import carpeta_usuario

_logger = None


def obtener_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("MonitorUART")
    logger.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    try:
        manejador = RotatingFileHandler(
            os.path.join(carpeta_usuario(), "monitoruart.log"),
            maxBytes=1_000_000, backupCount=2, encoding="utf-8",
        )
        manejador.setFormatter(formato)
        logger.addHandler(manejador)
    except OSError:
        pass

    if sys.stderr is not None:   # en el .exe sin consola stderr es None
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        logger.addHandler(consola)

    _logger = logger
    return logger


def instalar_manejador_excepciones() -> None:
    """Evita que una excepción no controlada en un slot de Qt cierre la aplicación de golpe.

    PyQt6 aborta el programa si una excepción escapa de un slot y no hay sys.excepthook propio.
    """
    def manejador(tipo, valor, tb):
        obtener_logger().error("Excepción no controlada:\n%s",
                               "".join(traceback.format_exception(tipo, valor, tb)))

    sys.excepthook = manejador
