"""
Panel de comandos guardados: elegir, rellenar parámetros y enviar con un clic.

- Árbol agrupado por categorías con buscador.
- Al elegir un comando aparecen sus parámetros (se recuerdan los últimos valores usados).
- Vista previa exacta de lo que se va a enviar.
- Confirmación para comandos peligrosos (borrados).
- Añadir, editar, duplicar, eliminar, ordenar, importar/exportar y restaurar.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from gui.dialogs.dialogo_comando import DialogoComando
from uart.comandos import cargar_comandos, comandos_por_defecto, guardar_comandos

COLOR_PELIGRO = QColor("#b00020")


class PanelComandos(QWidget):
    # Texto final que hay que enviar por la UART
    enviar = pyqtSignal(str)
    # Se emite cuando cambia la lista (para guardarla)
    cambiado = pyqtSignal()

    def __init__(self, comandos, parent=None):
        super().__init__(parent)
        self.comandos = comandos
        self._campos = []                 # QLineEdit de los parámetros del comando elegido
        self._actual = None               # Comando seleccionado

        # ---------------- Buscador y botones ----------------
        self.inputBuscar = QLineEdit()
        self.inputBuscar.setPlaceholderText("Buscar comando…")
        self.inputBuscar.setClearButtonEnabled(True)
        self.inputBuscar.textChanged.connect(self._rellenar_arbol)

        self.btnAnadir = QPushButton("Añadir")
        self.btnEditar = QPushButton("Editar")
        self.btnEliminar = QPushButton("Eliminar")
        self.btnMas = QToolButton()
        self.btnMas.setText("Más ▾")
        self.btnMas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(self)
        self.accionDuplicar = QAction("Duplicar", self)
        self.accionSubir = QAction("Subir", self)
        self.accionBajar = QAction("Bajar", self)
        self.accionImportar = QAction("Importar comandos…", self)
        self.accionExportar = QAction("Exportar comandos…", self)
        self.accionRestaurar = QAction("Restaurar predeterminados", self)
        for a in (self.accionDuplicar, self.accionSubir, self.accionBajar):
            menu.addAction(a)
        menu.addSeparator()
        for a in (self.accionImportar, self.accionExportar):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self.accionRestaurar)
        self.btnMas.setMenu(menu)

        self.btnAnadir.clicked.connect(lambda: self.anadir())
        self.btnEditar.clicked.connect(self._editar)
        self.btnEliminar.clicked.connect(self._eliminar)
        self.accionDuplicar.triggered.connect(self._duplicar)
        self.accionSubir.triggered.connect(lambda: self._mover(-1))
        self.accionBajar.triggered.connect(lambda: self._mover(+1))
        self.accionImportar.triggered.connect(self._importar)
        self.accionExportar.triggered.connect(self._exportar)
        self.accionRestaurar.triggered.connect(self._restaurar)

        botones = QHBoxLayout()
        for b in (self.btnAnadir, self.btnEditar, self.btnEliminar, self.btnMas):
            botones.addWidget(b)

        # ---------------- Árbol ----------------
        self.arbol = QTreeWidget()
        self.arbol.setObjectName("arbolComandos")
        self.arbol.setHeaderLabels(["Comando", "Descripción"])
        self.arbol.setColumnWidth(0, 230)
        self.arbol.setRootIsDecorated(True)
        self.arbol.setUniformRowHeights(True)
        self.arbol.currentItemChanged.connect(self._al_seleccionar)
        self.arbol.itemDoubleClicked.connect(self._al_doble_clic)

        # ---------------- Detalle ----------------
        self.lblTitulo = QLabel("Elige un comando")
        self.lblTitulo.setObjectName("tituloComando")
        self.lblTitulo.setWordWrap(True)

        self.lblDescripcion = QLabel("")
        self.lblDescripcion.setObjectName("infoLabel")
        self.lblDescripcion.setWordWrap(True)

        self.formParametros = QFormLayout()

        self.lblVista = QLabel("")
        self.lblVista.setObjectName("vistaComando")
        self.lblVista.setWordWrap(True)
        self.lblVista.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.btnEjemplo = QPushButton("Usar ejemplo")
        self.btnEjemplo.setToolTip("Rellenar los parámetros con los valores del ejemplo")
        self.btnEjemplo.clicked.connect(self._usar_ejemplo)

        self.btnEnviar = QPushButton("Enviar  ▶")
        self.btnEnviar.setObjectName("btnEnviarComando")
        self.btnEnviar.setMinimumHeight(34)
        self.btnEnviar.clicked.connect(self.enviar_actual)

        filaEnviar = QHBoxLayout()
        filaEnviar.addWidget(self.btnEjemplo)
        filaEnviar.addWidget(self.btnEnviar, 1)

        detalle = QFrame()
        detalle.setObjectName("detalleComando")
        layoutDetalle = QVBoxLayout(detalle)
        layoutDetalle.addWidget(self.lblTitulo)
        layoutDetalle.addWidget(self.lblDescripcion)
        layoutDetalle.addLayout(self.formParametros)
        layoutDetalle.addWidget(self.lblVista)
        layoutDetalle.addLayout(filaEnviar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.inputBuscar)
        layout.addLayout(botones)
        layout.addWidget(self.arbol, 1)
        layout.addWidget(detalle)

        self._rellenar_arbol()
        self._mostrar_detalle(None)

    # ==================================================================
    # Árbol
    # ==================================================================
    def _rellenar_arbol(self, *_):
        filtro = self.inputBuscar.text().strip().lower()
        id_seleccionado = self._actual.id if self._actual else None

        self.arbol.blockSignals(True)
        self.arbol.clear()
        categorias = {}
        fuente_cat = QFont()
        fuente_cat.setBold(True)
        a_seleccionar = None

        for c in self.comandos:
            texto_busqueda = f"{c.categoria} {c.titulo} {c.comando} {c.descripcion}".lower()
            if filtro and filtro not in texto_busqueda:
                continue

            padre = categorias.get(c.categoria)
            if padre is None:
                padre = QTreeWidgetItem([c.categoria, ""])
                padre.setFont(0, fuente_cat)
                padre.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.arbol.addTopLevelItem(padre)
                categorias[c.categoria] = padre

            titulo = c.titulo + ("  " + " ".join(f"[{p}]" for p in c.parametros) if c.parametros else "")
            item = QTreeWidgetItem([titulo, c.descripcion])
            item.setData(0, Qt.ItemDataRole.UserRole, c.id)
            item.setToolTip(0, c.ejemplo or c.comando)
            item.setToolTip(1, c.descripcion)
            if c.confirmar:
                item.setForeground(0, COLOR_PELIGRO)
            padre.addChild(item)
            if c.id == id_seleccionado:
                a_seleccionar = item

        self.arbol.expandAll()
        self.arbol.blockSignals(False)

        if a_seleccionar is not None:
            self.arbol.setCurrentItem(a_seleccionar)
        else:
            self._mostrar_detalle(None)
        self._actualizar_botones()

    def _comando_de(self, item):
        if item is None:
            return None
        id_ = item.data(0, Qt.ItemDataRole.UserRole)
        return next((c for c in self.comandos if c.id == id_), None) if id_ else None

    def _al_seleccionar(self, actual, _anterior=None):
        self._mostrar_detalle(self._comando_de(actual))
        self._actualizar_botones()

    def _al_doble_clic(self, item, _columna):
        c = self._comando_de(item)
        if c is None:
            return
        if c.parametros and self._campos:
            self._campos[0].setFocus()
            self._campos[0].selectAll()
        else:
            self.enviar_actual()

    def _actualizar_botones(self):
        hay = self._actual is not None
        self.btnEditar.setEnabled(hay)
        self.btnEliminar.setEnabled(hay)
        self.btnEnviar.setEnabled(hay)
        self.btnEjemplo.setEnabled(hay and bool(self._actual.valores_ejemplo()) if hay else False)
        for a in (self.accionDuplicar, self.accionSubir, self.accionBajar):
            a.setEnabled(hay)

    # ==================================================================
    # Detalle y parámetros
    # ==================================================================
    def _mostrar_detalle(self, comando):
        self._actual = comando

        while self.formParametros.rowCount():
            self.formParametros.removeRow(0)
        self._campos = []

        if comando is None:
            self.lblTitulo.setText("Elige un comando")
            self.lblDescripcion.setText("Doble clic en un comando sin parámetros para enviarlo directamente.")
            self.lblVista.setText("")
            return

        aviso = "  ⚠" if comando.confirmar else ""
        self.lblTitulo.setText(comando.titulo + aviso)
        self.lblDescripcion.setText(comando.descripcion or "")

        ejemplo = comando.valores_ejemplo()
        for i, nombre in enumerate(comando.parametros):
            campo = QLineEdit()
            if i < len(ejemplo):
                campo.setPlaceholderText(f"p. ej. {ejemplo[i]}")
            if i < len(comando.ultimos_valores):
                campo.setText(str(comando.ultimos_valores[i]))
            campo.textChanged.connect(self._actualizar_vista)
            campo.returnPressed.connect(self.enviar_actual)
            self.formParametros.addRow(f"{nombre}:", campo)
            self._campos.append(campo)

        self._actualizar_vista()

    def _valores(self):
        return [c.text().strip() for c in self._campos]

    def _actualizar_vista(self, *_):
        c = self._actual
        if c is None:
            self.lblVista.setText("")
            return
        partes = [c.comando] + [v or f"<{n}>" for v, n in zip(self._valores(), c.parametros)]
        self.lblVista.setText("→ " + " ".join(partes))

    def _usar_ejemplo(self):
        if self._actual is None:
            return
        for campo, valor in zip(self._campos, self._actual.valores_ejemplo()):
            campo.setText(valor)

    def enviar_actual(self):
        c = self._actual
        if c is None:
            return
        try:
            texto = c.construir(self._valores())
        except ValueError as e:
            QMessageBox.warning(self, "Faltan datos", str(e))
            for campo in self._campos:
                if not campo.text().strip():
                    campo.setFocus()
                    break
            return

        if c.confirmar:
            respuesta = QMessageBox.question(
                self, "Confirmar envío",
                f"¿Enviar este comando?\n\n{texto}\n\n{c.descripcion}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return

        if c.parametros and c.ultimos_valores != self._valores():
            c.ultimos_valores = self._valores()
            self.cambiado.emit()
        self.enviar.emit(texto)

    # ==================================================================
    # Gestión de la lista
    # ==================================================================
    def _categorias(self):
        return [c.categoria for c in self.comandos]

    def anadir(self, comando_sugerido: str = ""):
        dialogo = DialogoComando(categorias=self._categorias(), parent=self, comando_sugerido=comando_sugerido)
        if self._actual is not None:
            dialogo.comboCategoria.setCurrentText(self._actual.categoria)
        if not dialogo.exec():
            return
        nuevo = dialogo.comando()
        # Se coloca detrás del último de su categoría (o al final)
        posicion = len(self.comandos)
        for i, c in enumerate(self.comandos):
            if c.categoria == nuevo.categoria:
                posicion = i + 1
        self.comandos.insert(posicion, nuevo)
        self._actual = nuevo
        self._tras_cambio()

    def _editar(self):
        if self._actual is None:
            return
        dialogo = DialogoComando(self._actual, self._categorias(), self)
        if not dialogo.exec():
            return
        editado = dialogo.comando()
        i = self.comandos.index(self._actual)
        self.comandos[i] = editado
        self._actual = editado
        self._tras_cambio()

    def _duplicar(self):
        if self._actual is None:
            return
        copia = self._actual.copia(nuevo_id=True)
        copia.nombre = (self._actual.titulo + " (copia)")
        self.comandos.insert(self.comandos.index(self._actual) + 1, copia)
        self._actual = copia
        self._tras_cambio()

    def _eliminar(self):
        c = self._actual
        if c is None:
            return
        respuesta = QMessageBox.question(self, "Eliminar comando", f"¿Eliminar el comando «{c.titulo}»?")
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        self.comandos.remove(c)
        self._actual = None
        self._tras_cambio()

    def _mover(self, delta: int):
        """Sube o baja el comando dentro de su categoría."""
        c = self._actual
        if c is None:
            return
        i = self.comandos.index(c)
        j = i + delta
        while 0 <= j < len(self.comandos) and self.comandos[j].categoria != c.categoria:
            j += delta
        if 0 <= j < len(self.comandos):
            self.comandos[i], self.comandos[j] = self.comandos[j], self.comandos[i]
            self._tras_cambio()

    def _importar(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Importar comandos", "", "JSON (*.json);;Todos (*)")
        if not ruta:
            return
        importados = cargar_comandos(ruta)
        existentes = {(c.comando, tuple(c.parametros)) for c in self.comandos}
        nuevos = [c.copia(nuevo_id=True) for c in importados
                  if (c.comando, tuple(c.parametros)) not in existentes]
        self.comandos.extend(nuevos)
        self._tras_cambio()
        QMessageBox.information(self, "Importar comandos",
                                f"Se han añadido {len(nuevos)} comandos "
                                f"({len(importados) - len(nuevos)} ya existían).")

    def _exportar(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar comandos", "comandos.json", "JSON (*.json)")
        if not ruta:
            return
        try:
            guardar_comandos(ruta, self.comandos)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    def _restaurar(self):
        respuesta = QMessageBox.question(
            self, "Restaurar predeterminados",
            "¿Sustituir todos los comandos por los predeterminados del firmware?\n"
            "Se perderán los comandos que hayas añadido.",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self.comandos[:] = comandos_por_defecto()
            self._actual = None
            self._tras_cambio()

    def _tras_cambio(self):
        self._rellenar_arbol()
        self.cambiado.emit()
