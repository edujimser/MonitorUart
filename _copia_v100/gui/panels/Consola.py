"""
Consola de texto con barra de herramientas propia.

- QPlainTextEdit en vez de QTextEdit: mucho más rápido con miles de líneas.
- Límite de líneas: las más antiguas se descartan solas (la memoria no crece sin fin).
- Cada línea puede tener su color.
- Botones: Limpiar, Guardar, Auto-scroll y búsqueda (Enter = siguiente coincidencia).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


class Consola(QWidget):
    def __init__(self, titulo: str, color: str = "#e0e0e0", max_lineas: int = 20000, parent=None):
        super().__init__(parent)
        self._titulo = titulo
        self._hay_lineas = False
        self._formatos = {}

        # ---------------- Barra superior ----------------
        self.punto = QLabel()
        self.punto.setObjectName("consolaPunto")
        self.punto.setFixedSize(12, 12)

        self.lblTitulo = QLabel(titulo)
        self.lblTitulo.setObjectName("consolaTitulo")

        self.lblContador = QLabel("0 líneas")
        self.lblContador.setObjectName("consolaContador")

        self.inputBuscar = QLineEdit()
        self.inputBuscar.setPlaceholderText("Buscar… (Enter)")
        self.inputBuscar.setClearButtonEnabled(True)
        self.inputBuscar.setFixedWidth(180)
        self.inputBuscar.returnPressed.connect(self.buscar)

        self.chkAutoScroll = QCheckBox("Auto-scroll")
        self.chkAutoScroll.setChecked(True)
        self.chkAutoScroll.toggled.connect(self._al_cambiar_autoscroll)

        self.btnGuardar = QPushButton("Guardar")
        self.btnGuardar.setToolTip("Guardar el contenido de esta consola en un archivo")
        self.btnGuardar.clicked.connect(lambda: self.guardar())

        self.btnLimpiar = QPushButton("Limpiar")
        self.btnLimpiar.setObjectName("btnLimpiarConsola")
        self.btnLimpiar.setToolTip("Borrar el contenido de esta consola")
        self.btnLimpiar.clicked.connect(self.limpiar)

        barra = QHBoxLayout()
        barra.setContentsMargins(2, 0, 2, 0)
        barra.addWidget(self.punto)
        barra.addWidget(self.lblTitulo)
        barra.addSpacing(8)
        barra.addWidget(self.lblContador)
        barra.addStretch(1)
        barra.addWidget(self.inputBuscar)
        barra.addWidget(self.chkAutoScroll)
        barra.addWidget(self.btnGuardar)
        barra.addWidget(self.btnLimpiar)

        # ---------------- Texto ----------------
        self.texto = QPlainTextEdit()
        self.texto.setObjectName("consolaTexto")
        self.texto.setReadOnly(True)
        self.texto.setUndoRedoEnabled(False)
        self.texto.setMaximumBlockCount(max_lineas)
        self.texto.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.texto.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(barra)
        layout.addWidget(self.texto, 1)

        self.set_titulo(titulo, color)

    # ------------------------------------------------------------------
    @property
    def titulo(self) -> str:
        return self._titulo

    def set_titulo(self, titulo: str, color: str) -> None:
        self._titulo = titulo
        self.lblTitulo.setText(titulo)
        self.punto.setStyleSheet(f"background-color: {color}; border-radius: 6px;")

    # ------------------------------------------------------------------
    def agregar_lineas(self, items) -> None:
        """Añade varias líneas de golpe. items = lista de (texto, color)."""
        if not items:
            return

        cursor = QTextCursor(self.texto.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        for texto, color in items:
            if self._hay_lineas:
                cursor.insertBlock()
            cursor.insertText(texto, self._formato(color))
            self._hay_lineas = True
        cursor.endEditBlock()

        if self.chkAutoScroll.isChecked():
            barra = self.texto.verticalScrollBar()
            barra.setValue(barra.maximum())

        self._actualizar_contador()

    def limpiar(self) -> None:
        self.texto.clear()
        self._hay_lineas = False
        self._actualizar_contador()

    def texto_plano(self) -> str:
        return self.texto.toPlainText()

    # ------------------------------------------------------------------
    def buscar(self) -> None:
        patron = self.inputBuscar.text()
        if not patron:
            return

        # Al buscar, el auto-scroll movería la vista: se desactiva
        self.chkAutoScroll.setChecked(False)

        if not self.texto.find(patron):
            # Si no hay más coincidencias hacia abajo, se vuelve a empezar desde arriba
            self.texto.moveCursor(QTextCursor.MoveOperation.Start)
            if not self.texto.find(patron):
                self.inputBuscar.setStyleSheet("background-color: #ffd6d6;")
                return
        self.inputBuscar.setStyleSheet("")

    def guardar(self, ruta: str = None) -> bool:
        if ruta is None:
            ruta, _ = QFileDialog.getSaveFileName(
                self, f"Guardar consola '{self._titulo}'", f"{self._titulo}.txt",
                "Archivo de texto (*.txt);;Todos los archivos (*)",
            )
            if not ruta:
                return False
        try:
            with open(ruta, "w", encoding="utf-8", errors="replace") as f:
                f.write(self.texto_plano())
            return True
        except OSError as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{e}")
            return False

    # ------------------------------------------------------------------
    def _formato(self, color: str) -> QTextCharFormat:
        fmt = self._formatos.get(color)
        if fmt is None:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self._formatos[color] = fmt
        return fmt

    def _actualizar_contador(self) -> None:
        n = self.texto.blockCount() if self._hay_lineas else 0
        self.lblContador.setText(f"{n} línea" if n == 1 else f"{n} líneas")

    def _al_cambiar_autoscroll(self, activo: bool) -> None:
        if activo:
            barra = self.texto.verticalScrollBar()
            barra.setValue(barra.maximum())
