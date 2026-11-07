# gui/menu/menuSuperiorA.py
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMenuBar


class MenuSuperiorA(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ---------------- Archivo ----------------
        menuArchivo = self.addMenu("Archivo")

        self.accionGuardar = QAction("Guardar consola actual…", self)
        self.accionGuardar.setShortcut(QKeySequence("Ctrl+S"))
        self.accionGuardar.setStatusTip("Guardar el contenido de la pestaña visible")
        menuArchivo.addAction(self.accionGuardar)

        self.accionGuardarTodas = QAction("Guardar todas las consolas…", self)
        self.accionGuardarTodas.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.accionGuardarTodas.setStatusTip("Guardar cada consola en un archivo dentro de una carpeta")
        menuArchivo.addAction(self.accionGuardarTodas)

        menuArchivo.addSeparator()

        self.accionSalir = QAction("Salir", self)
        # Antes era Ctrl+X, que choca con "Cortar"
        self.accionSalir.setShortcut(QKeySequence("Ctrl+Q"))
        self.accionSalir.setStatusTip("Cerrar la aplicación")
        menuArchivo.addAction(self.accionSalir)

        # ---------------- Ver ----------------
        menuVer = self.addMenu("Ver")

        self.accionLimpiarActual = QAction("Limpiar consola actual", self)
        self.accionLimpiarActual.setShortcut(QKeySequence("Ctrl+L"))
        menuVer.addAction(self.accionLimpiarActual)

        self.accionLimpiarTodas = QAction("Limpiar todas las consolas", self)
        self.accionLimpiarTodas.setShortcut(QKeySequence("Ctrl+Shift+L"))
        menuVer.addAction(self.accionLimpiarTodas)

        menuVer.addSeparator()

        self.accionMarcasTiempo = QAction("Mostrar marcas de tiempo", self)
        self.accionMarcasTiempo.setCheckable(True)
        self.accionMarcasTiempo.setShortcut(QKeySequence("Ctrl+T"))
        menuVer.addAction(self.accionMarcasTiempo)

        self.accionPausa = QAction("Pausar visualización", self)
        self.accionPausa.setCheckable(True)
        self.accionPausa.setShortcut(QKeySequence("Ctrl+P"))
        menuVer.addAction(self.accionPausa)

        # ---------------- Terminales ----------------
        menuTerminales = self.addMenu("Terminales")

        self.accionGestionar = QAction("Gestionar terminales…", self)
        self.accionGestionar.setShortcut(QKeySequence("Ctrl+M"))
        self.accionGestionar.setStatusTip("Crear, editar o borrar terminales por tipo de mensaje")
        menuTerminales.addAction(self.accionGestionar)

        # ---------------- Ayuda ----------------
        menuAyuda = self.addMenu("Ayuda")
        self.accionAcercaDe = QAction("Acerca de MonitorUART", self)
        menuAyuda.addAction(self.accionAcercaDe)
