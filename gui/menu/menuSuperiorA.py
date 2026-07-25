# gui/menu_superior.py
from PyQt6.QtWidgets import QMenuBar
from PyQt6.QtGui import QAction


class MenuSuperiorA(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        
        menuArchivo = self.addMenu("Archivo")
        
        #Guardar log
        self.accionGuardar = QAction("Guardar Log", self)
        self.accionGuardar.setShortcut("Ctrl+S")
        self.accionGuardar.setStatusTip("Guardar el log actual en un archivo")
        menuArchivo.addAction(self.accionGuardar)
        menuArchivo.addSeparator()
        #Salir
        self.accionSalir = QAction("Salir", self)
        self.accionSalir.setShortcut("Ctrl+X")
        self.accionSalir.setStatusTip("Cerrar la aplicación")
        menuArchivo.addAction(self.accionSalir)
        
   