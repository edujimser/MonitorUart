from PyQt6.QtWidgets import QTextEdit
import os

class Consola(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Solo lectura
        self.setReadOnly(True)

        # Aplicar estilo
        self.aplicarEstilo()

    def aplicarEstilo(self):
        # Ruta absoluta del QSS
        ruta_qss = os.path.join(os.path.dirname(__file__), "ConsolaStyle.qss")

        try:
            with open(ruta_qss, "r", encoding="utf-8") as f:
                estilo = f.read()
            self.setStyleSheet(estilo)
        except Exception as e:
            print(f"[ERROR] No se pudo aplicar el estilo: {e}")