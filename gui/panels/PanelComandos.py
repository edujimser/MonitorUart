"""
Panel de comandos guardados: elegir, rellenar parámetros y enviar con un clic.

- Árbol por categorías (en el orden que elijas) con buscador y grupo "★ Favoritos".
- Gestión de categorías: añadir, renombrar, eliminar, ordenar (también con clic derecho).
- Parámetros con los últimos valores usados y vista previa exacta de lo que se envía.
- Confirmación para comandos peligrosos (borrados).
- Envío repetido cada X ms (útil para consultar un estado periódicamente).
- Menú contextual: enviar, editar, duplicar, favorito, copiar, mover a categoría, eliminar.
- Importar/exportar y restaurar predeterminados.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QSpinBox, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from gui.dialogs.dialogo_comando import DialogoComando
from gui.dialogs.gestor_categorias import GestorCategorias, pedir_nombre_categoria
from uart.comandos import (
    cargar_comandos, comandos_por_defecto, guardar_comandos, normalizar_categorias,
)

COLOR_PELIGRO = QColor("#b00020")
COLOR_VACIA = QColor("#999999")
ROL_ID = Qt.ItemDataRole.UserRole          # id del comando o nombre de la categoría
ROL_TIPO = Qt.ItemDataRole.UserRole + 1    # "cmd", "cat" o "fav"
FAVORITOS = "★ Favoritos"


def _accion(menu, texto, funcion):
    """Añade una opción al menú. La señal triggered pasa un bool que aquí se descarta."""
    accion = menu.addAction(texto)
    accion.triggered.connect(lambda _checked=False: funcion())
    return accion


class PanelComandos(QWidget):
    # Se emite cuando cambia la lista o las categorías (para guardarlas)
    cambiado = pyqtSignal()

    def __init__(self, comandos, categorias=None, parent=None):
        super().__init__(parent)
        self.comandos = comandos
        self.categorias = normalizar_categorias(categorias, comandos)
        # La ventana principal la sustituye por su función de envío (devuelve True si se envió)
        self.enviar_func = lambda texto: False

        self._campos = []
        self._actual = None
        self._texto_repetido = None

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
        self.accionCategorias = QAction("Gestionar categorías…", self)
        self.accionNuevaCategoria = QAction("Nueva categoría…", self)
        self.accionDuplicar = QAction("Duplicar comando", self)
        self.accionSubir = QAction("Subir comando", self)
        self.accionBajar = QAction("Bajar comando", self)
        self.accionImportar = QAction("Importar comandos…", self)
        self.accionExportar = QAction("Exportar comandos…", self)
        self.accionRestaurar = QAction("Restaurar predeterminados", self)
        menu.addAction(self.accionCategorias)
        menu.addAction(self.accionNuevaCategoria)
        menu.addSeparator()
        for a in (self.accionDuplicar, self.accionSubir, self.accionBajar):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self.accionImportar)
        menu.addAction(self.accionExportar)
        menu.addSeparator()
        menu.addAction(self.accionRestaurar)
        self.btnMas.setMenu(menu)

        self.btnAnadir.clicked.connect(lambda: self.anadir())
        self.btnEditar.clicked.connect(self._editar)
        self.btnEliminar.clicked.connect(self._eliminar)
        self.accionCategorias.triggered.connect(self.gestionar_categorias)
        self.accionNuevaCategoria.triggered.connect(self._nueva_categoria)
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
        self.arbol.setUniformRowHeights(True)
        self.arbol.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.arbol.customContextMenuRequested.connect(self._menu_contextual)
        self.arbol.currentItemChanged.connect(self._al_seleccionar)
        self.arbol.itemDoubleClicked.connect(self._al_doble_clic)

        # ---------------- Detalle ----------------
        self.lblTitulo = QLabel("Elige un comando")
        self.lblTitulo.setObjectName("tituloComando")
        self.lblTitulo.setWordWrap(True)

        self.btnFavorito = QToolButton()
        self.btnFavorito.setObjectName("btnFavorito")
        self.btnFavorito.setText("☆")
        self.btnFavorito.setToolTip("Añadir o quitar de Favoritos")
        self.btnFavorito.clicked.connect(self._alternar_favorito)

        filaTitulo = QHBoxLayout()
        filaTitulo.addWidget(self.lblTitulo, 1)
        filaTitulo.addWidget(self.btnFavorito)

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

        # Repetición periódica
        self.btnRepetir = QPushButton("⟳ Repetir cada")
        self.btnRepetir.setObjectName("btnRepetir")
        self.btnRepetir.setCheckable(True)
        self.btnRepetir.setToolTip("Enviar el comando una y otra vez con el intervalo indicado")
        self.btnRepetir.toggled.connect(self._al_repetir)
        self.spinIntervalo = QSpinBox()
        self.spinIntervalo.setRange(50, 600_000)
        self.spinIntervalo.setSingleStep(100)
        self.spinIntervalo.setValue(1000)
        self.spinIntervalo.setSuffix(" ms")
        self.spinIntervalo.valueChanged.connect(lambda v: self.timerRepetir.setInterval(v))
        self.lblRepitiendo = QLabel("")
        self.lblRepitiendo.setObjectName("infoLabel")

        filaRepetir = QHBoxLayout()
        filaRepetir.addWidget(self.btnRepetir)
        filaRepetir.addWidget(self.spinIntervalo)
        filaRepetir.addWidget(self.lblRepitiendo, 1)

        self.timerRepetir = QTimer(self)
        self.timerRepetir.timeout.connect(self._tick_repetir)

        detalle = QFrame()
        detalle.setObjectName("detalleComando")
        layoutDetalle = QVBoxLayout(detalle)
        layoutDetalle.addLayout(filaTitulo)
        layoutDetalle.addWidget(self.lblDescripcion)
        layoutDetalle.addLayout(self.formParametros)
        layoutDetalle.addWidget(self.lblVista)
        layoutDetalle.addLayout(filaEnviar)
        layoutDetalle.addLayout(filaRepetir)

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
        self.categorias[:] = normalizar_categorias(self.categorias, self.comandos)

        self.arbol.blockSignals(True)
        self.arbol.clear()
        negrita = QFont()
        negrita.setBold(True)
        a_seleccionar = None

        def nodo(texto, tipo, clave):
            item = QTreeWidgetItem([texto, ""])
            item.setFont(0, negrita)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(0, ROL_TIPO, tipo)
            item.setData(0, ROL_ID, clave)
            self.arbol.addTopLevelItem(item)
            return item

        def hoja(padre, c):
            titulo = c.titulo + ("  " + " ".join(f"[{p}]" for p in c.parametros) if c.parametros else "")
            item = QTreeWidgetItem([titulo, c.descripcion])
            item.setData(0, ROL_ID, c.id)
            item.setData(0, ROL_TIPO, "cmd")
            item.setToolTip(0, c.ejemplo or c.comando)
            item.setToolTip(1, c.descripcion)
            if c.confirmar:
                item.setForeground(0, COLOR_PELIGRO)
            padre.addChild(item)
            return item

        def coincide(c):
            return not filtro or filtro in f"{c.categoria} {c.titulo} {c.comando} {c.descripcion}".lower()

        favoritos = [c for c in self.comandos if c.favorito and coincide(c)]
        if favoritos:
            padre = nodo(FAVORITOS, "fav", "")
            for c in favoritos:
                item = hoja(padre, c)
                if c.id == id_seleccionado and a_seleccionar is None:
                    a_seleccionar = item

        for cat in self.categorias:
            propios = [c for c in self.comandos if c.categoria == cat and coincide(c)]
            if filtro and not propios:
                continue
            padre = nodo(cat, "cat", cat)
            if not propios:
                padre.setText(1, "(vacía: clic derecho → Nuevo comando aquí)")
                padre.setForeground(1, COLOR_VACIA)
            for c in propios:
                item = hoja(padre, c)
                if c.id == id_seleccionado and a_seleccionar is None:
                    a_seleccionar = item

        self.arbol.expandAll()
        self.arbol.blockSignals(False)

        if a_seleccionar is not None:
            self.arbol.setCurrentItem(a_seleccionar)
        else:
            self._mostrar_detalle(None)
        self._actualizar_botones()

    def _comando_de(self, item):
        if item is None or item.data(0, ROL_TIPO) != "cmd":
            return None
        id_ = item.data(0, ROL_ID)
        return next((c for c in self.comandos if c.id == id_), None)

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
        c = self._actual
        hay = c is not None
        self.btnEditar.setEnabled(hay)
        self.btnEliminar.setEnabled(hay)
        self.btnEnviar.setEnabled(hay)
        self.btnFavorito.setEnabled(hay)
        self.btnEjemplo.setEnabled(hay and bool(c.valores_ejemplo()))
        # No se repiten comandos peligrosos (borrados)
        self.btnRepetir.setEnabled(self.btnRepetir.isChecked() or (hay and not c.confirmar))
        for a in (self.accionDuplicar, self.accionSubir, self.accionBajar):
            a.setEnabled(hay)

    # ==================================================================
    # Menú contextual (clic derecho)
    # ==================================================================
    def _menu_contextual(self, posicion):
        item = self.arbol.itemAt(posicion)
        menu = QMenu(self)
        tipo = item.data(0, ROL_TIPO) if item is not None else None

        if tipo == "cmd":
            c = self._comando_de(item)
            self.arbol.setCurrentItem(item)
            _accion(menu, "Enviar", self.enviar_actual)
            _accion(menu, "Editar…", self._editar)
            _accion(menu, "Duplicar", self._duplicar)
            _accion(menu, "Quitar de Favoritos" if c.favorito else "Añadir a Favoritos", self._alternar_favorito)
            _accion(menu, "Copiar texto del comando", self._copiar)
            submenu = menu.addMenu("Mover a categoría")
            for cat in self.categorias:
                if cat != c.categoria:
                    _accion(submenu, cat, lambda destino=cat: self._mover_a_categoria(c, destino))
            submenu.addSeparator()
            _accion(submenu, "Nueva categoría…", lambda: self._mover_a_categoria(c, None))
            menu.addSeparator()
            _accion(menu, "Eliminar", self._eliminar)

        elif tipo == "cat":
            cat = item.data(0, ROL_ID)
            _accion(menu, "Nuevo comando aquí…", lambda: self.anadir(categoria=cat))
            _accion(menu, "Renombrar categoría…", lambda: self._renombrar_categoria(cat))
            if not any(c.categoria == cat for c in self.comandos):
                _accion(menu, "Eliminar categoría", lambda: self._eliminar_categoria_vacia(cat))
            menu.addSeparator()
            _accion(menu, "Nueva categoría…", self._nueva_categoria)
            _accion(menu, "Gestionar categorías…", self.gestionar_categorias)

        else:
            _accion(menu, "Nuevo comando…", lambda: self.anadir())
            _accion(menu, "Nueva categoría…", self._nueva_categoria)
            _accion(menu, "Gestionar categorías…", self.gestionar_categorias)

        menu.exec(self.arbol.viewport().mapToGlobal(posicion))

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
            self.lblDescripcion.setText("Doble clic en un comando sin parámetros para enviarlo. "
                                        "Clic derecho para más opciones.")
            self.lblVista.setText("")
            self.btnFavorito.setText("☆")
            return

        self.lblTitulo.setText(comando.titulo + ("  ⚠" if comando.confirmar else ""))
        self.lblDescripcion.setText(comando.descripcion or "")
        self.btnFavorito.setText("★" if comando.favorito else "☆")

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

    def _texto_actual(self, avisar=True):
        """Texto final del comando elegido, o None si faltan parámetros."""
        c = self._actual
        if c is None:
            return None
        try:
            texto = c.construir(self._valores())
        except ValueError as e:
            if avisar:
                QMessageBox.warning(self, "Faltan datos", str(e))
                for campo in self._campos:
                    if not campo.text().strip():
                        campo.setFocus()
                        break
            return None
        if c.parametros and c.ultimos_valores != self._valores():
            c.ultimos_valores = self._valores()
            self.cambiado.emit()
        return texto

    def enviar_actual(self):
        c = self._actual
        texto = self._texto_actual()
        if texto is None:
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
        self.enviar_func(texto)

    # ---------------- Repetición ----------------
    def _al_repetir(self, activo: bool):
        if activo:
            if self._actual is None or self._actual.confirmar:
                self.btnRepetir.setChecked(False)
                return
            texto = self._texto_actual()
            if texto is None:
                self.btnRepetir.setChecked(False)
                return
            self._texto_repetido = texto
            self.lblRepitiendo.setText(f"Repitiendo: {texto}")
            self.btnRepetir.setText("■ Detener")
            self.timerRepetir.start(self.spinIntervalo.value())
            self._tick_repetir()
        else:
            self.detener_repeticion()

    def _tick_repetir(self):
        if self._texto_repetido and not self.enviar_func(self._texto_repetido):
            self.detener_repeticion()

    def detener_repeticion(self):
        self.timerRepetir.stop()
        self._texto_repetido = None
        self.lblRepitiendo.setText("")
        self.btnRepetir.setText("⟳ Repetir cada")
        if self.btnRepetir.isChecked():
            self.btnRepetir.blockSignals(True)
            self.btnRepetir.setChecked(False)
            self.btnRepetir.blockSignals(False)
        self._actualizar_botones()

    # ==================================================================
    # Gestión de comandos
    # ==================================================================
    def anadir(self, comando_sugerido: str = "", categoria: str = None):
        dialogo = DialogoComando(categorias=self.categorias, parent=self, comando_sugerido=comando_sugerido)
        if categoria:
            dialogo.comboCategoria.setCurrentText(categoria)
        elif self._actual is not None:
            dialogo.comboCategoria.setCurrentText(self._actual.categoria)
        if not dialogo.exec():
            return
        nuevo = dialogo.comando()
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
        dialogo = DialogoComando(self._actual, self.categorias, self)
        if not dialogo.exec():
            return
        editado = dialogo.comando()
        editado.favorito = self._actual.favorito
        self.comandos[self.comandos.index(self._actual)] = editado
        self._actual = editado
        self._tras_cambio()

    def _duplicar(self):
        if self._actual is None:
            return
        copia = self._actual.copia(nuevo_id=True)
        copia.nombre = self._actual.titulo + " (copia)"
        self.comandos.insert(self.comandos.index(self._actual) + 1, copia)
        self._actual = copia
        self._tras_cambio()

    def _eliminar(self):
        c = self._actual
        if c is None:
            return
        if QMessageBox.question(self, "Eliminar comando",
                                f"¿Eliminar el comando «{c.titulo}»?") != QMessageBox.StandardButton.Yes:
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

    def _alternar_favorito(self):
        if self._actual is None:
            return
        self._actual.favorito = not self._actual.favorito
        self._tras_cambio()

    def _copiar(self):
        texto = self._texto_actual(avisar=False) or (self._actual.comando if self._actual else "")
        if texto:
            QGuiApplication.clipboard().setText(texto)

    def _mover_a_categoria(self, comando, destino):
        if destino is None:
            destino = pedir_nombre_categoria(self, "Nueva categoría", self.categorias)
            if not destino:
                return
            self.categorias.append(destino)
        comando.categoria = destino
        # Se coloca al final de su nueva categoría
        self.comandos.remove(comando)
        posicion = len(self.comandos)
        for i, c in enumerate(self.comandos):
            if c.categoria == destino:
                posicion = i + 1
        self.comandos.insert(posicion, comando)
        self._actual = comando
        self._tras_cambio()

    # ==================================================================
    # Gestión de categorías
    # ==================================================================
    def gestionar_categorias(self):
        dialogo = GestorCategorias(self.categorias, self.comandos, self)
        if not dialogo.exec():
            return
        categorias, comandos = dialogo.resultado()
        id_actual = self._actual.id if self._actual else None
        self.comandos[:] = comandos
        self.categorias[:] = categorias
        self._actual = next((c for c in self.comandos if c.id == id_actual), None)
        self._tras_cambio()

    def _nueva_categoria(self):
        nombre = pedir_nombre_categoria(self, "Nueva categoría", self.categorias)
        if nombre:
            self.categorias.append(nombre)
            self._tras_cambio()

    def _renombrar_categoria(self, viejo):
        nuevo = pedir_nombre_categoria(self, "Renombrar categoría", self.categorias, viejo)
        if not nuevo or nuevo == viejo:
            return
        self.categorias[self.categorias.index(viejo)] = nuevo
        for c in self.comandos:
            if c.categoria == viejo:
                c.categoria = nuevo
        self._tras_cambio()

    def _eliminar_categoria_vacia(self, cat):
        if cat in self.categorias and not any(c.categoria == cat for c in self.comandos):
            self.categorias.remove(cat)
            self._tras_cambio()

    # ==================================================================
    # Importar / exportar / restaurar
    # ==================================================================
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
            guardar_comandos(ruta, self.comandos, self.categorias)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    def _restaurar(self):
        respuesta = QMessageBox.question(
            self, "Restaurar predeterminados",
            "¿Sustituir todos los comandos y categorías por los predeterminados del firmware?\n"
            "Se perderán los comandos que hayas añadido.",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self.comandos[:] = comandos_por_defecto()
            self.categorias[:] = normalizar_categorias([], self.comandos)
            self._actual = None
            self._tras_cambio()

    def _tras_cambio(self):
        self._rellenar_arbol()
        self.cambiado.emit()
