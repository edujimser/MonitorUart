"""
Menú interno para crear, editar, ordenar y borrar terminales.

Cada terminal es una regla (uart/parse.py). El orden de la lista es el orden de
las pestañas y también la prioridad de color en la consola General.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout,
)

from uart.parse import TIPOS_FILTRO, ReglaTerminal, reglas_por_defecto

AYUDA = (
    "<b>Empieza por</b>: la línea empieza por el texto, p. ej. <code>[ERR]</code><br>"
    "<b>Contiene</b>: el texto aparece en cualquier parte de la línea<br>"
    "<b>Expresión regular</b>: patrón de Python, p. ej. <code>^\\[(ERR|WRN)\\]</code> "
    "o <code>Temp=\\d+</code>"
)


class DialogoRegla(QDialog):
    """Crear o editar una terminal."""

    def __init__(self, regla: ReglaTerminal = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar terminal" if regla else "Nueva terminal")
        self.setMinimumWidth(460)

        self._id = regla.id if regla else None
        self._color = regla.color if regla else "#4fc3f7"

        self.inputNombre = QLineEdit(regla.nombre if regla else "")
        self.inputNombre.setPlaceholderText("Ej.: Errores, Sensores, Motor…")

        self.comboTipo = QComboBox()
        for clave, texto in TIPOS_FILTRO.items():
            self.comboTipo.addItem(texto, clave)
        if regla:
            self.comboTipo.setCurrentIndex(max(0, self.comboTipo.findData(regla.tipo)))

        self.inputPatron = QLineEdit(regla.patron if regla else "")
        self.inputPatron.setPlaceholderText("Ej.: [ERR]")

        self.btnColor = QPushButton()
        self.btnColor.clicked.connect(self._elegir_color)
        self._pintar_boton_color()

        self.chkActivo = QCheckBox("Terminal activa (visible como pestaña)")
        self.chkActivo.setChecked(regla.activo if regla else True)

        self.chkMayus = QCheckBox("Distinguir mayúsculas y minúsculas")
        self.chkMayus.setChecked(regla.mayusculas if regla else False)

        self.chkGeneral = QCheckBox("Mostrar también en la consola General")
        self.chkGeneral.setChecked(regla.en_general if regla else True)

        self.chkAlerta = QCheckBox("Avisar al llegar un mensaje (sonido y parpadeo en la barra de tareas)")
        self.chkAlerta.setChecked(regla.alerta if regla else False)

        # Prueba en vivo: escribe una línea de ejemplo y ve si coincide
        self.inputPrueba = QLineEdit()
        self.inputPrueba.setPlaceholderText("Escribe una línea de ejemplo para probar el filtro")
        self.lblResultado = QLabel()

        lblAyuda = QLabel(AYUDA)
        lblAyuda.setWordWrap(True)
        lblAyuda.setObjectName("infoLabel")

        formulario = QFormLayout()
        formulario.addRow("Nombre:", self.inputNombre)
        formulario.addRow("Filtro:", self.comboTipo)
        formulario.addRow("Patrón:", self.inputPatron)
        formulario.addRow("", lblAyuda)
        formulario.addRow("Color:", self.btnColor)
        formulario.addRow("", self.chkActivo)
        formulario.addRow("", self.chkMayus)
        formulario.addRow("", self.chkGeneral)
        formulario.addRow("", self.chkAlerta)
        formulario.addRow("Probar:", self.inputPrueba)
        formulario.addRow("", self.lblResultado)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

        for senal in (self.inputPatron.textChanged, self.inputPrueba.textChanged, self.inputNombre.textChanged):
            senal.connect(self._actualizar_prueba)
        self.comboTipo.currentIndexChanged.connect(self._actualizar_prueba)
        self.chkMayus.toggled.connect(self._actualizar_prueba)
        self._actualizar_prueba()

    # ------------------------------------------------------------------
    def regla(self) -> ReglaTerminal:
        """Construye la regla con lo que hay en el formulario (sin validar)."""
        datos = dict(
            nombre=self.inputNombre.text().strip(),
            patron=self.inputPatron.text(),
            tipo=self.comboTipo.currentData(),
            color=self._color,
            activo=self.chkActivo.isChecked(),
            mayusculas=self.chkMayus.isChecked(),
            en_general=self.chkGeneral.isChecked(),
            alerta=self.chkAlerta.isChecked(),
        )
        if self._id:
            datos["id"] = self._id   # se conserva para no perder el contenido de la pestaña
        return ReglaTerminal(**datos)

    def accept(self):
        try:
            self.regla().validar()
        except ValueError as e:
            QMessageBox.warning(self, "Terminal no válida", str(e))
            return
        super().accept()

    # ------------------------------------------------------------------
    def _elegir_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, "Color de la terminal")
        if color.isValid():
            self._color = color.name()
            self._pintar_boton_color()

    def _pintar_boton_color(self):
        self.btnColor.setText(self._color)
        self.btnColor.setStyleSheet(
            f"background-color: {self._color}; color: #000000; border: 1px solid #888888; "
            f"border-radius: 4px; padding: 4px; min-width: 90px;"
        )

    def _actualizar_prueba(self):
        regla = self.regla()
        regla.activo = True
        try:
            regla.validar()
        except ValueError as e:
            self.lblResultado.setText(f"⚠ {e}")
            self.lblResultado.setStyleSheet("color: #c77700;")
            return

        linea = self.inputPrueba.text()
        if not linea:
            self.lblResultado.setText("")
        elif regla.coincide(linea):
            self.lblResultado.setText("✔ Coincide: esta línea irá a esta terminal")
            self.lblResultado.setStyleSheet("color: #1b8a2e;")
        else:
            self.lblResultado.setText("✘ No coincide")
            self.lblResultado.setStyleSheet("color: #b00020;")


class GestorTerminales(QDialog):
    """Lista de terminales con Añadir / Editar / Eliminar / Subir / Bajar."""

    def __init__(self, reglas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionar terminales")
        self.resize(620, 420)

        # Se trabaja sobre copias: si se pulsa Cancelar no cambia nada
        self._reglas = [r.copia() for r in reglas]

        self.lista = QListWidget()
        self.lista.setObjectName("listaTerminales")
        self.lista.itemDoubleClicked.connect(lambda _item: self._editar())
        self.lista.itemChanged.connect(self._al_cambiar_check)
        self.lista.currentRowChanged.connect(lambda _fila: self._actualizar_botones())

        self.btnAnadir = QPushButton("Añadir…")
        self.btnEditar = QPushButton("Editar…")
        self.btnEliminar = QPushButton("Eliminar")
        self.btnSubir = QPushButton("Subir")
        self.btnBajar = QPushButton("Bajar")
        self.btnRestaurar = QPushButton("Restaurar predeterminadas")

        self.btnAnadir.clicked.connect(self._anadir)
        self.btnEditar.clicked.connect(self._editar)
        self.btnEliminar.clicked.connect(self._eliminar)
        self.btnSubir.clicked.connect(lambda: self._mover(-1))
        self.btnBajar.clicked.connect(lambda: self._mover(+1))
        self.btnRestaurar.clicked.connect(self._restaurar)

        columna = QVBoxLayout()
        for b in (self.btnAnadir, self.btnEditar, self.btnEliminar, self.btnSubir, self.btnBajar):
            columna.addWidget(b)
        columna.addStretch(1)
        columna.addWidget(self.btnRestaurar)

        centro = QHBoxLayout()
        centro.addWidget(self.lista, 1)
        centro.addLayout(columna)

        lblInfo = QLabel(
            "Cada línea recibida se muestra siempre en <b>General</b> y, además, en todas las "
            "terminales cuyo filtro cumpla. Marca o desmarca la casilla para activar o desactivar "
            "una terminal. El orden de la lista es el orden de las pestañas."
        )
        lblInfo.setWordWrap(True)
        lblInfo.setObjectName("infoLabel")

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(lblInfo)
        layout.addLayout(centro, 1)
        layout.addWidget(botones)

        self._refrescar(0)

    # ------------------------------------------------------------------
    def reglas(self) -> list:
        return self._reglas

    # ------------------------------------------------------------------
    def _refrescar(self, seleccion: int = -1):
        self.lista.blockSignals(True)
        self.lista.clear()
        for r in self._reglas:
            aviso = "   🔔" if r.alerta else ""
            item = QListWidgetItem(f"{r.nombre}    —    {TIPOS_FILTRO.get(r.tipo, r.tipo)}:  {r.patron}{aviso}")
            item.setForeground(QColor(r.color))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if r.activo else Qt.CheckState.Unchecked)
            self.lista.addItem(item)
        self.lista.blockSignals(False)

        if self._reglas:
            self.lista.setCurrentRow(min(max(seleccion, 0), len(self._reglas) - 1))
        self._actualizar_botones()

    def _actualizar_botones(self):
        fila = self.lista.currentRow()
        hay = 0 <= fila < len(self._reglas)
        self.btnEditar.setEnabled(hay)
        self.btnEliminar.setEnabled(hay)
        self.btnSubir.setEnabled(hay and fila > 0)
        self.btnBajar.setEnabled(hay and fila < len(self._reglas) - 1)

    def _al_cambiar_check(self, item: QListWidgetItem):
        fila = self.lista.row(item)
        if 0 <= fila < len(self._reglas):
            self._reglas[fila].activo = item.checkState() == Qt.CheckState.Checked

    def _anadir(self):
        dialogo = DialogoRegla(parent=self)
        if dialogo.exec():
            self._reglas.append(dialogo.regla())
            self._refrescar(len(self._reglas) - 1)

    def _editar(self):
        fila = self.lista.currentRow()
        if not (0 <= fila < len(self._reglas)):
            return
        dialogo = DialogoRegla(self._reglas[fila], parent=self)
        if dialogo.exec():
            self._reglas[fila] = dialogo.regla()
            self._refrescar(fila)

    def _eliminar(self):
        fila = self.lista.currentRow()
        if not (0 <= fila < len(self._reglas)):
            return
        nombre = self._reglas[fila].nombre
        respuesta = QMessageBox.question(
            self, "Eliminar terminal",
            f"¿Eliminar la terminal «{nombre}»?\nSe perderá el contenido de su pestaña.",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            del self._reglas[fila]
            self._refrescar(fila)

    def _mover(self, delta: int):
        fila = self.lista.currentRow()
        destino = fila + delta
        if 0 <= fila < len(self._reglas) and 0 <= destino < len(self._reglas):
            self._reglas[fila], self._reglas[destino] = self._reglas[destino], self._reglas[fila]
            self._refrescar(destino)

    def _restaurar(self):
        respuesta = QMessageBox.question(
            self, "Restaurar predeterminadas",
            "¿Sustituir todas las terminales por las predeterminadas (Errores, Test, Flash, Web)?",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self._reglas = reglas_por_defecto()
            self._refrescar(0)
