import sys

from PyQt6.QtWidgets import QApplication

from gui.ventana_principal import VentanaPrincipal
from utils.logger import instalar_manejador_excepciones


def main():
    # Si salta una excepción en un slot, se registra en el log en vez de cerrar la app
    instalar_manejador_excepciones()

    app = QApplication(sys.argv)
    # Necesarios para que QSettings recuerde puerto, baudios, tamaño de ventana...
    app.setOrganizationName("edujimser")
    app.setApplicationName("MonitorUART")

    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
