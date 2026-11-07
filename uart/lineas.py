"""
Ensamblado de líneas a partir de los bytes que llegan por el puerto serie.

El puerto entrega los datos en trozos arbitrarios (media línea, tres líneas y
un trozo...). Para poder clasificar cada mensaje por su prefijo ([ERR], [GEN]...)
hay que reconstruir primero las líneas completas. Este módulo no depende de Qt,
así que se puede probar de forma aislada.
"""


def decodificar(crudo: bytes) -> str:
    """Convierte los bytes de una línea en texto imprimible.

    - Quita los '\\0' (el firmware antiguo enviaba el terminador de C).
    - Quita el '\\r' final de los finales de línea "\\r\\n".
    - Intenta UTF-8 y, si falla, Latin-1 (nunca lanza excepción).
    - Sustituye otros caracteres de control por '·' para que no rompan la consola.
    """
    crudo = crudo.replace(b"\x00", b"").rstrip(b"\r")
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        texto = crudo.decode("latin-1")
    return "".join(c if (c >= " " or c == "\t") else "·" for c in texto)


class EnsambladorLineas:
    """Acumula bytes y devuelve líneas completas (terminadas en '\\n')."""

    def __init__(self, max_longitud: int = 4096):
        self._buffer = bytearray()
        self.max_longitud = max_longitud

    @property
    def pendiente(self) -> bool:
        """True si hay una línea a medias esperando su '\\n'."""
        return len(self._buffer) > 0

    def alimentar(self, datos: bytes) -> list:
        """Añade bytes y devuelve la lista de líneas que se han completado."""
        self._buffer.extend(datos)
        lineas = []

        while True:
            idx = self._buffer.find(b"\n")
            if idx < 0:
                break
            crudo = bytes(self._buffer[:idx])
            del self._buffer[:idx + 1]
            lineas.append(decodificar(crudo))

        # Protección: una "línea" enorme sin '\n' (basura, baudios mal puestos...)
        # no puede hacer crecer el buffer sin límite.
        if len(self._buffer) > self.max_longitud:
            lineas.append(decodificar(bytes(self._buffer)))
            self._buffer.clear()

        return lineas

    def vaciar(self):
        """Devuelve la línea incompleta pendiente (o None) y limpia el buffer.

        Se usa cuando pasa un tiempo sin datos: así se muestran también los
        mensajes que no terminan en '\\n' (por ejemplo un prompt "> ").
        """
        if not self._buffer:
            return None
        texto = decodificar(bytes(self._buffer))
        self._buffer.clear()
        return texto
