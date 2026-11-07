from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit


class LineaEnvio(QLineEdit):
    """Campo de envío con historial: flechas Arriba/Abajo recuperan comandos anteriores."""

    def __init__(self, parent=None, max_historial: int = 50):
        super().__init__(parent)
        self._historial = []
        self._posicion = 0
        self._max = max_historial

    def agregar_historial(self, texto: str) -> None:
        if texto and (not self._historial or self._historial[-1] != texto):
            self._historial.append(texto)
            del self._historial[:-self._max]
        self._posicion = len(self._historial)

    def keyPressEvent(self, evento):
        if self._historial and evento.key() == Qt.Key.Key_Up:
            self._posicion = max(0, self._posicion - 1)
            self.setText(self._historial[self._posicion])
            return
        if self._historial and evento.key() == Qt.Key.Key_Down:
            self._posicion = min(len(self._historial), self._posicion + 1)
            self.setText(self._historial[self._posicion] if self._posicion < len(self._historial) else "")
            return
        super().keyPressEvent(evento)
