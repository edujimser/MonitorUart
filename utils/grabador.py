"""
Grabación en tiempo real de todo lo que se recibe a un archivo de texto.
"""


class Grabador:
    def __init__(self):
        self._archivo = None
        self.ruta = None

    @property
    def activo(self) -> bool:
        return self._archivo is not None

    def iniciar(self, ruta: str) -> None:
        """Abre el archivo (lo sobrescribe). Lanza OSError si no se puede."""
        self.detener()
        self._archivo = open(ruta, "w", encoding="utf-8", errors="replace")
        self.ruta = ruta

    def escribir(self, lineas) -> None:
        if self._archivo is None or not lineas:
            return
        try:
            self._archivo.write("\n".join(lineas) + "\n")
            self._archivo.flush()   # que no se pierda nada si la app se cierra de golpe
        except OSError:
            self.detener()
            raise

    def detener(self) -> None:
        if self._archivo is not None:
            try:
                self._archivo.close()
            except OSError:
                pass
        self._archivo = None
        self.ruta = None
