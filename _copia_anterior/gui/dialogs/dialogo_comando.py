"""
Diálogo para crear o editar un comando guardado.
"""

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QVBoxLayout,
)

from uart.comandos import Comando, parsear_parametros


class DialogoComando(QDialog):
    def __init__(self, comando: Comando = None, categorias=(), parent=None, comando_sugerido: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Editar comando" if comando else "Nuevo comando")
        self.setMinimumWidth(520)
        self._original = comando

        self.comboCategoria = QComboBox()
        self.comboCategoria.setEditable(True)
        self.comboCategoria.addItems(sorted(set(categorias)) or ["General"])
        self.comboCategoria.setCurrentText(comando.categoria if comando else
                                           (self.comboCategoria.itemText(0) or "General"))

        self.inputComando = QLineEdit(comando.comando if comando else comando_sugerido)
        self.inputComando.setPlaceholderText("Ej.: FLASH_READ_ALL_SECTOR_DIR")

        self.inputParametros = QLineEdit(" ".join(f"[{p}]" for p in comando.parametros) if comando else "")
        self.inputParametros.setPlaceholderText("Ej.: [SecIni] [SecFin]   (vacío = sin parámetros)")
        self.inputParametros.setToolTip("Se envían separados por espacios detrás del comando")

        self.inputEjemplo = QLineEdit(comando.ejemplo if comando else "")
        self.inputEjemplo.setPlaceholderText("Ej.: FLASH_READ_ALL_SECTOR_DIR 1 10 20 4")

        self.inputNombre = QLineEdit(comando.nombre if comando else "")
        self.inputNombre.setPlaceholderText("Opcional: texto que se ve en la lista")

        self.inputDescripcion = QPlainTextEdit(comando.descripcion if comando else "")
        self.inputDescripcion.setPlaceholderText("Qué hace el comando")
        self.inputDescripcion.setFixedHeight(70)

        self.chkConfirmar = QCheckBox("Pedir confirmación antes de enviar (recomendado para borrados)")
        self.chkConfirmar.setChecked(comando.confirmar if comando else False)

        self.lblVista = QLabel()
        self.lblVista.setObjectName("vistaComando")
        self.lblVista.setWordWrap(True)

        formulario = QFormLayout()
        formulario.addRow("Categoría:", self.comboCategoria)
        formulario.addRow("Comando:", self.inputComando)
        formulario.addRow("Parámetros:", self.inputParametros)
        formulario.addRow("Ejemplo:", self.inputEjemplo)
        formulario.addRow("Nombre:", self.inputNombre)
        formulario.addRow("Descripción:", self.inputDescripcion)
        formulario.addRow("", self.chkConfirmar)
        formulario.addRow("Se enviará:", self.lblVista)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

        for campo in (self.inputComando, self.inputParametros, self.inputEjemplo):
            campo.textChanged.connect(self._actualizar_vista)
        self._actualizar_vista()

    # ------------------------------------------------------------------
    def comando(self) -> Comando:
        """Construye el comando con lo que hay en el formulario (conserva id y últimos valores)."""
        c = Comando(
            comando=self.inputComando.text().strip(),
            categoria=self.comboCategoria.currentText().strip() or "General",
            nombre=self.inputNombre.text().strip(),
            parametros=parsear_parametros(self.inputParametros.text()),
            ejemplo=self.inputEjemplo.text().strip(),
            descripcion=self.inputDescripcion.toPlainText().strip(),
            confirmar=self.chkConfirmar.isChecked(),
        )
        if self._original is not None:
            c.id = self._original.id
            if len(self._original.parametros) == len(c.parametros):
                c.ultimos_valores = list(self._original.ultimos_valores)
        return c

    def accept(self):
        try:
            self.comando().validar()
        except ValueError as e:
            QMessageBox.warning(self, "Comando no válido", str(e))
            return
        super().accept()

    def _actualizar_vista(self):
        c = self.comando()
        if not c.comando:
            self.lblVista.setText("—")
            return
        valores = c.valores_ejemplo() or [f"<{p}>" for p in c.parametros]
        self.lblVista.setText(" ".join([c.comando] + valores))
