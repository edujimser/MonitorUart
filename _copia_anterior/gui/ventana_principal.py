import json
import os
import re
import time
from collections import deque
from datetime import datetime

import serial.tools.list_ports
from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QDockWidget, QMainWindow, QMessageBox, QPushButton, QScrollArea, QStatusBar, QTabWidget,
    QVBoxLayout, QWidget,
)

from gui.dialogs.gestor_terminales import GestorTerminales
from gui.menu.menuSuperiorA import MenuSuperiorA
from gui.panels.Consola import Consola
from gui.panels.LineaEnvio import LineaEnvio
from gui.panels.PanelComandos import PanelComandos
from uart.hilo_uart import HiloUART
from uart.comandos import cargar_comandos, guardar_comandos
from uart.parse import Clasificador, cargar_reglas, guardar_reglas
from utils.grabador import Grabador
from utils.logger import obtener_logger
from utils.rutas import carpeta_usuario, resource_path

VERSION = "1.2.0"

COLOR_DEFECTO = "#e0e0e0"    # líneas que no coinciden con ninguna terminal
COLOR_APP_INFO = "#7fdbca"   # mensajes de la propia aplicación
COLOR_APP_ERROR = "#ff8800"
COLOR_TX = "#addb67"         # lo que enviamos nosotros

FINES_LINEA = [
    ("LF  (\\n)", "\n"),
    ("CR+LF  (\\r\\n)", "\r\n"),
    ("CR  (\\r)", "\r"),
    ("Ninguno", ""),
]

ID_GENERAL = "__general__"
MAX_LINEAS_EN_PAUSA = 50_000
ANCHO = 180


def _clave_natural(device: str):
    """Ordena COM2 antes que COM10."""
    numero = re.search(r"(\d+)$", device)
    return (re.sub(r"\d+$", "", device), int(numero.group(1)) if numero else 0)


def _icono_color(color: str) -> QIcon:
    pixmap = QPixmap(12, 12)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor("#555555"))
    painter.drawEllipse(1, 1, 10, 10)
    painter.end()
    return QIcon(pixmap)


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"Monitor UART STM32 v{VERSION}")
        self.resize(1450, 800)

        self.log = obtener_logger()
        self.ajustes = QSettings()

        # ---------------- Estado ----------------
        self.hilo = None
        self._hilos_finalizando = set()   # hilos que tardaron en parar: se liberan al terminar
        self._conectado = False
        self._puerto_actual = None
        self._esperando_reconexion = None
        self._puerto_ausente = False
        self._intentos_reconexion = 0
        self._info_puertos = {}

        self.grabador = Grabador()
        self._pausado = False
        self._buffer_pausa = deque(maxlen=MAX_LINEAS_EN_PAUSA)
        self._bytes_rx = 0
        self._lineas_rx = 0

        # Terminales
        self._ruta_reglas = os.path.join(carpeta_usuario(), "terminales.json")
        self._ruta_comandos = os.path.join(carpeta_usuario(), "comandos.json")
        self.reglas = cargar_reglas(self._ruta_reglas)
        self.clasificador = Clasificador(self.reglas)
        self._reglas_por_id = {}
        self.consolas_term = {}   # id de regla -> Consola
        self._no_leidos = {}      # id -> nº de líneas nuevas sin ver

        # ---------------- Menú ----------------
        self.menu = MenuSuperiorA(self)
        self.setMenuBar(self.menu)
        self.menu.accionGuardar.triggered.connect(self.guardarConsolaActual)
        self.menu.accionGuardarTodas.triggered.connect(self.guardarTodas)
        self.menu.accionSalir.triggered.connect(self.close)
        self.menu.accionLimpiarActual.triggered.connect(self.limpiarConsolaActual)
        self.menu.accionLimpiarTodas.triggered.connect(self.limpiarTodas)
        self.menu.accionGestionar.triggered.connect(self.gestionarTerminales)
        self.menu.accionAcercaDe.triggered.connect(self.acercaDe)

        # ---------------- Pestañas de consolas ----------------
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._al_cambiar_pestana)

        self.consolaGeneral = Consola("General", COLOR_DEFECTO)
        self.tabs.addTab(self.consolaGeneral, _icono_color(COLOR_DEFECTO), "General")
        self._construir_terminales()

        # ---------------- Panel central ----------------
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._crear_panel_lateral())
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # Panel acoplable de comandos guardados (a la derecha)
        self._crear_panel_comandos()

        # Menú y panel comparten estado
        self.menu.accionMarcasTiempo.toggled.connect(self.chkMarcasTiempo.setChecked)
        self.chkMarcasTiempo.toggled.connect(self.menu.accionMarcasTiempo.setChecked)
        self.menu.accionPausa.toggled.connect(self.btnPausa.setChecked)
        self.btnPausa.toggled.connect(self.menu.accionPausa.setChecked)

        # ---------------- Barra de estado ----------------
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lblEstadisticas = QLabel()
        self.status.addPermanentWidget(self.lblEstadisticas)
        self.status.showMessage("Desconectado")
        self._actualizar_estadisticas()

        # ---------------- Temporizadores ----------------
        self.timerPuertos = QTimer(self)
        self.timerPuertos.timeout.connect(self.actualizarPuertos)
        self.timerPuertos.start(1000)

        self.timerLedRx = QTimer(self)
        self.timerLedRx.setSingleShot(True)
        self.timerLedRx.timeout.connect(lambda: self._set_led(self.ledRX, "rx", "off"))

        self.timerEstadisticas = QTimer(self)
        self.timerEstadisticas.timeout.connect(self._actualizar_estadisticas)
        self.timerEstadisticas.start(500)

        self.aplicarEstilo()
        self._cargar_ajustes()
        self.actualizarPuertos()
        self._set_estado_controles("desconectado")

    # ==================================================================
    # Construcción de la interfaz
    # ==================================================================
    def _crear_panel_lateral(self) -> QWidget:
        cfg = self._cargar_config_serie()
        panel = QVBoxLayout()

        def titulo(texto):
            lbl = QLabel(texto)
            lbl.setObjectName("tituloSeccion")
            return lbl

        # ---------- Conexión ----------
        self.comboPuerto = QComboBox()
        self.comboPuerto.setFixedWidth(ANCHO)
        self.comboPuerto.currentIndexChanged.connect(self.dataPuertos)

        self.comboBaud = QComboBox()
        self.comboBaud.setFixedWidth(ANCHO)
        self.comboBaud.addItems([str(b) for b in cfg["baudrates"]])
        self.comboBaud.setCurrentText("115200")

        self.bytesize = QComboBox()
        self.bytesize.setFixedWidth(ANCHO)
        self.bytesize.addItems([str(b) for b in cfg["bytesizes"]])
        self.bytesize.setCurrentText("8")

        self.parity = QComboBox()
        self.parity.setFixedWidth(ANCHO)
        self.parity.addItems([str(p) for p in cfg["parities"]])

        self.stopbits = QComboBox()
        self.stopbits.setFixedWidth(ANCHO)
        self.stopbits.addItems(["1", "1.5", "2"])

        self.btnConectar = QPushButton("Conectar")
        self.btnConectar.setFixedWidth(ANCHO)
        self.btnConectar.clicked.connect(lambda: self.conectar())

        self.btnDesconectar = QPushButton("Desconectar")
        self.btnDesconectar.setFixedWidth(ANCHO)
        self.btnDesconectar.clicked.connect(self.desconectar)

        self.chkReconectar = QCheckBox("Reconectar automáticamente")
        self.chkReconectar.setToolTip(
            "Si el dispositivo se desconecta (reset de la placa, cable USB...), "
            "se vuelve a conectar solo cuando el puerto reaparece."
        )

        panel.addWidget(titulo("Conexión"))
        for etiqueta, widget in (("Puerto", self.comboPuerto), ("Baudrate", self.comboBaud),
                                 ("Bytesize", self.bytesize), ("Paridad", self.parity),
                                 ("Bits de parada", self.stopbits)):
            panel.addWidget(QLabel(etiqueta))
            panel.addWidget(widget)
        panel.addSpacing(4)
        panel.addWidget(self.btnConectar)
        panel.addWidget(self.btnDesconectar)
        panel.addWidget(self.chkReconectar)

        # ---------- Consolas ----------
        self.btnLimpiarTodo = QPushButton("Limpiar todas las consolas")
        self.btnLimpiarTodo.setObjectName("btnLimpiarTodo")
        self.btnLimpiarTodo.setFixedWidth(ANCHO)
        self.btnLimpiarTodo.clicked.connect(self.limpiarTodas)

        self.btnPausa = QPushButton("Pausar visualización")
        self.btnPausa.setObjectName("btnPausa")
        self.btnPausa.setCheckable(True)
        self.btnPausa.setFixedWidth(ANCHO)
        self.btnPausa.toggled.connect(self._al_pausar)

        self.btnTerminales = QPushButton("Gestionar terminales…")
        self.btnTerminales.setFixedWidth(ANCHO)
        self.btnTerminales.clicked.connect(self.gestionarTerminales)

        self.chkMarcasTiempo = QCheckBox("Marcas de tiempo")

        panel.addSpacing(12)
        panel.addWidget(titulo("Consolas"))
        panel.addWidget(self.btnLimpiarTodo)
        panel.addWidget(self.btnPausa)
        panel.addWidget(self.btnTerminales)
        panel.addWidget(self.chkMarcasTiempo)

        # ---------- Grabación ----------
        self.btnIniciarGrabacion = QPushButton("Iniciar grabación")
        self.btnIniciarGrabacion.setFixedWidth(ANCHO)
        self.btnIniciarGrabacion.clicked.connect(self.iniciarGrabacion)

        self.btnDetenerGrabacion = QPushButton("Detener grabación")
        self.btnDetenerGrabacion.setFixedWidth(ANCHO)
        self.btnDetenerGrabacion.clicked.connect(self.detenerGrabacion)
        self.btnDetenerGrabacion.setEnabled(False)

        self.lblGrabacion = QLabel("Sin grabar")
        self.lblGrabacion.setObjectName("infoLabel")
        self.lblGrabacion.setWordWrap(True)

        panel.addSpacing(12)
        panel.addWidget(titulo("Grabación"))
        panel.addWidget(self.btnIniciarGrabacion)
        panel.addWidget(self.btnDetenerGrabacion)
        panel.addWidget(self.lblGrabacion)

        # ---------- Envío ----------
        self.input_tx = LineaEnvio()
        self.input_tx.setFixedWidth(ANCHO)
        self.input_tx.setPlaceholderText("Datos a enviar (Enter)")
        self.input_tx.setToolTip("Enter para enviar · Flechas ↑/↓ para el historial")
        self.input_tx.returnPressed.connect(self.enviar_uart)

        self.comboFinLinea = QComboBox()
        self.comboFinLinea.setFixedWidth(ANCHO)
        for texto, valor in FINES_LINEA:
            self.comboFinLinea.addItem(texto, valor)

        self.btn_enviar = QPushButton("Enviar")
        self.btn_enviar.setFixedWidth(ANCHO)
        self.btn_enviar.clicked.connect(self.enviar_uart)

        panel.addSpacing(12)
        panel.addWidget(titulo("Enviar datos"))
        panel.addWidget(self.input_tx)
        panel.addWidget(QLabel("Fin de línea"))
        panel.addWidget(self.comboFinLinea)
        panel.addWidget(self.btn_enviar)

        self.btnGuardarComando = QPushButton("Guardar como comando…")
        self.btnGuardarComando.setFixedWidth(ANCHO)
        self.btnGuardarComando.setToolTip("Guardar lo escrito en el panel de comandos para enviarlo con un clic")
        self.btnGuardarComando.clicked.connect(self._guardar_texto_como_comando)
        panel.addWidget(self.btnGuardarComando)

        # ---------- LEDs ----------
        panel.addSpacing(12)
        panel.addWidget(titulo("Indicadores"))
        leds = QHBoxLayout()
        leds.addWidget(QLabel("RX"))
        self.ledRX = QLabel()
        self.ledRX.setFixedSize(18, 18)
        self.ledRX.setObjectName("ledRX")
        self.ledRX.setProperty("rx", "off")
        leds.addWidget(self.ledRX)
        leds.addSpacing(10)
        leds.addWidget(QLabel("Estado"))
        self.ledEstado = QLabel()
        self.ledEstado.setFixedSize(18, 18)
        self.ledEstado.setObjectName("ledEstado")
        self.ledEstado.setProperty("estado", "desconectado")
        leds.addWidget(self.ledEstado)
        leds.addStretch(1)
        panel.addLayout(leds)

        # ---------- Información del puerto ----------
        panel.addSpacing(12)
        panel.addWidget(titulo("Información del puerto"))
        self.infoDescripcion = QLabel("Descripción: -")
        self.infoFabricante = QLabel("Fabricante: -")
        self.infoProducto = QLabel("Producto: -")
        self.infoSerial = QLabel("Número de serie: -")
        self.infoHWID = QLabel("HWID: -")
        for lbl in (self.infoDescripcion, self.infoFabricante, self.infoProducto,
                    self.infoSerial, self.infoHWID):
            lbl.setObjectName("infoLabel")
            lbl.setWordWrap(True)
            panel.addWidget(lbl)

        panel.addStretch(1)

        contenido = QWidget()
        contenido.setLayout(panel)

        # Con scroll: en pantallas pequeñas no se corta el panel
        scroll = QScrollArea()
        scroll.setObjectName("panelLateral")
        scroll.setWidget(contenido)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(ANCHO + 44)
        return scroll

    def _cargar_config_serie(self) -> dict:
        cfg = {"baudrates": [9600, 115200], "bytesizes": [8], "parities": ["None"]}
        ruta = resource_path(os.path.join("config", "serial_config.json"))
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError) as e:
            self.log.warning("No se pudo leer %s: %s", ruta, e)
        return cfg

    def aplicarEstilo(self):
        ruta_qss = resource_path(os.path.join("gui", "style", "ElegantDark.qss"))
        try:
            with open(ruta_qss, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except OSError as e:
            self.log.error("No se pudo aplicar el estilo: %s", e)

    @staticmethod
    def _set_led(led: QLabel, propiedad: str, valor: str):
        if led.property(propiedad) == valor:
            return
        led.setProperty(propiedad, valor)
        led.style().unpolish(led)
        led.style().polish(led)

    # ==================================================================
    # Terminales (pestañas)
    # ==================================================================
    def _construir_terminales(self):
        """Crea/actualiza/elimina pestañas según las reglas, conservando el contenido existente."""
        activas = [r for r in self.reglas if r.activo]
        ids_activos = {r.id for r in activas}

        for id_ in list(self.consolas_term):
            if id_ not in ids_activos:
                consola = self.consolas_term.pop(id_)
                indice = self.tabs.indexOf(consola)
                if indice >= 0:
                    self.tabs.removeTab(indice)
                consola.deleteLater()
                self._no_leidos.pop(id_, None)

        for posicion, regla in enumerate(activas, start=1):   # 0 = General
            consola = self.consolas_term.get(regla.id)
            if consola is None:
                consola = Consola(regla.nombre, regla.color)
                self.consolas_term[regla.id] = consola
                self.tabs.insertTab(posicion, consola, regla.nombre)
            else:
                indice = self.tabs.indexOf(consola)
                if indice != posicion:
                    self.tabs.tabBar().moveTab(indice, posicion)
            consola.set_titulo(regla.nombre, regla.color)

        self._reglas_por_id = {r.id: r for r in self.reglas}
        self.clasificador = Clasificador(self.reglas)
        for id_ in self.consolas_term:
            self._actualizar_titulo_pestana(id_)

    def _actualizar_titulo_pestana(self, id_: str):
        if id_ == ID_GENERAL:
            consola, nombre, color = self.consolaGeneral, "General", COLOR_DEFECTO
        else:
            consola = self.consolas_term.get(id_)
            regla = self._reglas_por_id.get(id_)
            if consola is None or regla is None:
                return
            nombre, color = regla.nombre, regla.color

        indice = self.tabs.indexOf(consola)
        if indice < 0:
            return
        n = self._no_leidos.get(id_, 0)
        self.tabs.setTabText(indice, f"{nombre} ({n})" if n else nombre)
        self.tabs.setTabIcon(indice, _icono_color(color))

    def _id_de_consola(self, consola):
        if consola is self.consolaGeneral:
            return ID_GENERAL
        for id_, c in self.consolas_term.items():
            if c is consola:
                return id_
        return None

    def _al_cambiar_pestana(self, _indice: int):
        id_ = self._id_de_consola(self.tabs.currentWidget())
        if id_ and self._no_leidos.get(id_):
            self._no_leidos[id_] = 0
            self._actualizar_titulo_pestana(id_)

    def gestionarTerminales(self):
        dialogo = GestorTerminales(self.reglas, self)
        if not dialogo.exec():
            return
        self.reglas = dialogo.reglas()
        try:
            guardar_reglas(self._ruta_reglas, self.reglas)
        except OSError as e:
            QMessageBox.warning(self, "Aviso", f"Las terminales se aplicarán, pero no se pudieron guardar:\n{e}")
        self._construir_terminales()
        self.status.showMessage("Terminales actualizadas", 3000)

    # ==================================================================
    # Recepción y enrutado de líneas
    # ==================================================================
    def _formatear(self, marca: float, linea: str) -> str:
        if self.chkMarcasTiempo.isChecked():
            return f"{datetime.fromtimestamp(marca).strftime('%H:%M:%S.%f')[:-3]}  {linea}"
        return linea

    def _procesar_lineas(self, items):
        """items: lista de (marca_de_tiempo, linea) que llega del hilo."""
        self._lineas_rx += len(items)

        # La grabación sigue aunque la visualización esté en pausa
        if self.grabador.activo:
            try:
                self.grabador.escribir([self._formatear(m, l) for m, l in items])
            except OSError as e:
                self._mensaje_app(f"Grabación detenida por un error de escritura: {e}", error=True)
                self._actualizar_controles_grabacion()

        if self._pausado:
            self._buffer_pausa.extend(items)
            return

        self._mostrar(items)

    def _mostrar(self, items):
        general = []
        por_terminal = {}

        for marca, linea in items:
            texto = self._formatear(marca, linea)
            coincidencias = self.clasificador.clasificar(linea)

            if not coincidencias:
                general.append((texto, COLOR_DEFECTO))
                continue

            if any(r.en_general for r in coincidencias):
                general.append((texto, coincidencias[0].color))
            for regla in coincidencias:
                por_terminal.setdefault(regla.id, []).append((texto, regla.color))

        actual = self.tabs.currentWidget()

        if general:
            self.consolaGeneral.agregar_lineas(general)
            if actual is not self.consolaGeneral:
                self._sumar_no_leidos(ID_GENERAL, len(general))

        for id_, lineas in por_terminal.items():
            consola = self.consolas_term.get(id_)
            if consola is None:
                continue
            consola.agregar_lineas(lineas)
            if actual is not consola:
                self._sumar_no_leidos(id_, len(lineas))

    def _sumar_no_leidos(self, id_: str, n: int):
        self._no_leidos[id_] = self._no_leidos.get(id_, 0) + n
        self._actualizar_titulo_pestana(id_)

    def _mensaje_app(self, texto: str, error: bool = False, color: str = None):
        """Mensaje de la propia aplicación: solo en General (y en la grabación)."""
        etiqueta = "[APP-ERROR]" if error else "[APP]"
        linea = self._formatear(time.time(), f"{etiqueta} {texto}")
        self.consolaGeneral.agregar_lineas([(linea, color or (COLOR_APP_ERROR if error else COLOR_APP_INFO))])
        if self.grabador.activo:
            try:
                self.grabador.escribir([linea])
            except OSError:
                pass
        (self.log.warning if error else self.log.info)(texto)

    def _al_pausar(self, pausado: bool):
        self._pausado = pausado
        self.btnPausa.setText("Reanudar visualización" if pausado else "Pausar visualización")
        if not pausado and self._buffer_pausa:
            pendientes = list(self._buffer_pausa)
            self._buffer_pausa.clear()
            self._mostrar(pendientes)
        self._actualizar_estadisticas()

    def _actividad_rx(self, n_bytes: int):
        self._bytes_rx += n_bytes
        self._set_led(self.ledRX, "rx", "on")
        self.timerLedRx.start(120)

    @staticmethod
    def _num(valor, decimales: int = 0) -> str:
        """Formato español: 12.345,6"""
        texto = f"{valor:,.{decimales}f}"
        return texto.replace(",", "§").replace(".", ",").replace("§", ".")

    def _actualizar_estadisticas(self):
        texto = f"RX: {self._num(self._bytes_rx / 1024, 1)} kB · {self._num(self._lineas_rx)} líneas"
        if self._pausado:
            texto = f"⏸ EN PAUSA ({self._num(len(self._buffer_pausa))} pendientes) · " + texto
        if self.grabador.activo:
            texto = "● GRABANDO · " + texto
        self.lblEstadisticas.setText(texto)

    # ==================================================================
    # Puertos
    # ==================================================================
    def actualizarPuertos(self):
        try:
            puertos = sorted(serial.tools.list_ports.comports(), key=lambda p: _clave_natural(p.device))
        except Exception as e:
            self.log.warning("Error al listar puertos: %s", e)
            return

        self._info_puertos = {p.device: p for p in puertos}
        dispositivos = [p.device for p in puertos]
        en_combo = [self.comboPuerto.itemData(i) for i in range(self.comboPuerto.count())]

        if dispositivos != en_combo:
            seleccionado = self.comboPuerto.currentData() or self.ajustes.value("puerto", "")
            self.comboPuerto.blockSignals(True)
            self.comboPuerto.clear()
            for p in puertos:
                desc = p.description if p.description and p.description not in ("n/a", p.device) else ""
                self.comboPuerto.addItem(f"{p.device}  —  {desc}" if desc else p.device, p.device)
                self.comboPuerto.setItemData(self.comboPuerto.count() - 1, p.description or "",
                                             Qt.ItemDataRole.ToolTipRole)
            indice = self.comboPuerto.findData(seleccionado)
            if indice >= 0:
                self.comboPuerto.setCurrentIndex(indice)
            self.comboPuerto.blockSignals(False)
            self.dataPuertos()

        self._comprobar_reconexion(dispositivos)

    def dataPuertos(self):
        p = self._info_puertos.get(self.comboPuerto.currentData())
        if p is None:
            valores = ["-"] * 5
        else:
            valores = [p.description, p.manufacturer, p.product, p.serial_number, p.hwid]
            valores = [v or "No disponible" for v in valores]
        for lbl, nombre, valor in zip(
            (self.infoDescripcion, self.infoFabricante, self.infoProducto, self.infoSerial, self.infoHWID),
            ("Descripción", "Fabricante", "Producto", "Número de serie", "HWID"),
            valores,
        ):
            lbl.setText(f"{nombre}: {valor}")

    def _comprobar_reconexion(self, dispositivos):
        """Reconecta cuando el puerto perdido desaparece y vuelve a aparecer."""
        puerto = self._esperando_reconexion
        if not puerto or self.hilo is not None or not self.chkReconectar.isChecked():
            return
        if puerto not in dispositivos:
            self._puerto_ausente = True
            return
        if self._puerto_ausente:
            self._puerto_ausente = False
            indice = self.comboPuerto.findData(puerto)
            if indice >= 0:
                self.comboPuerto.setCurrentIndex(indice)
                self._mensaje_app(f"{puerto} ha vuelto a aparecer: reconectando…")
                self.conectar(silencioso=True)

    # ==================================================================
    # Conexión
    # ==================================================================
    def conectar(self, silencioso: bool = False):
        if self.hilo is not None:
            return

        puerto = self.comboPuerto.currentData()
        if not puerto:
            if not silencioso:
                QMessageBox.warning(self, "Error", "No se ha seleccionado ningún puerto COM.")
            return

        try:
            baud = int(self.comboBaud.currentText())
            bytesize = int(self.bytesize.currentText())
        except ValueError:
            QMessageBox.warning(self, "Error", "Baudrate o bytesize no válidos.")
            return

        self._esperando_reconexion = None
        self._puerto_actual = puerto

        hilo = HiloUART(puerto, baud, bytesize, self.parity.currentText(), self.stopbits.currentText())
        hilo.lineasRecibidas.connect(self._procesar_lineas)
        hilo.actividadRx.connect(self._actividad_rx)
        hilo.conectado.connect(self._al_conectar)
        hilo.errorConexion.connect(lambda msg, s=silencioso: self._al_error_conexion(msg, s))
        hilo.aviso.connect(lambda msg: self._mensaje_app(msg, error=True))
        hilo.finished.connect(lambda h=hilo: self._al_hilo_terminado(h))
        self.hilo = hilo

        self._set_estado_controles("conectando")
        self.status.showMessage(f"Conectando a {puerto}…")
        hilo.start()

    def _al_conectar(self, puerto: str):
        self._conectado = True
        self._intentos_reconexion = 0
        self._set_led(self.ledEstado, "estado", "conectado")
        self._set_estado_controles("conectado")
        config = (f"{self.comboBaud.currentText()} baudios, {self.bytesize.currentText()}"
                  f"{self.parity.currentText()[:1].upper()}{self.stopbits.currentText()}")
        self.status.showMessage(f"Conectado a {puerto} ({config})")
        self._mensaje_app(f"Conectado a {puerto} ({config})")

    def _al_error_conexion(self, mensaje: str, silencioso: bool):
        estaba_conectado = self._conectado
        self._conectado = False
        self._set_led(self.ledEstado, "estado", "error")
        self.status.showMessage(mensaje)
        self._mensaje_app(mensaje, error=True)

        if estaba_conectado:
            if self.chkReconectar.isChecked() and self._puerto_actual:
                self._esperando_reconexion = self._puerto_actual
                self._puerto_ausente = False
                self._intentos_reconexion = 0
                self._mensaje_app("Esperando a que el dispositivo vuelva a conectarse…")
        elif silencioso:
            # Fallo en una reconexión automática: el puerto USB recién enumerado a veces
            # tarda en estar listo. Se reintenta en el siguiente segundo (máx. 5 veces).
            if self.chkReconectar.isChecked() and self._intentos_reconexion < 5:
                self._intentos_reconexion += 1
                self._esperando_reconexion = self._puerto_actual
                self._puerto_ausente = True
        else:
            QMessageBox.critical(self, "Error de conexión", mensaje)

    def _al_hilo_terminado(self, hilo):
        self._hilos_finalizando.discard(hilo)
        if hilo is not self.hilo:
            return   # desconexión manual: ya se gestionó en desconectar()
        # El hilo terminó solo (error o pérdida de conexión)
        self.hilo = None
        hilo.deleteLater()
        self._conectado = False
        self._set_estado_controles("desconectado")
        if self.ledEstado.property("estado") != "error":
            self._set_led(self.ledEstado, "estado", "desconectado")

    def desconectar(self):
        self._esperando_reconexion = None
        hilo = self.hilo
        if hilo is None:
            return
        self.hilo = None
        hilo.detener()

        if hilo.wait(2000):
            hilo.deleteLater()
        else:
            # No se destruye un QThread en marcha: se libera cuando termine
            self.log.warning("El hilo UART tardó en detenerse")
            self._hilos_finalizando.add(hilo)
            hilo.finished.connect(hilo.deleteLater)

        estaba_conectado = self._conectado
        self._conectado = False
        self._set_led(self.ledEstado, "estado", "desconectado")
        self._set_estado_controles("desconectado")
        self.status.showMessage("Desconectado")
        if estaba_conectado:
            self._mensaje_app(f"Desconectado de {self._puerto_actual}")

    def _set_estado_controles(self, estado: str):
        conectado = estado == "conectado"
        libre = estado == "desconectado"
        for w in (self.comboPuerto, self.comboBaud, self.bytesize, self.parity, self.stopbits):
            w.setEnabled(libre)
        self.btnConectar.setEnabled(libre)
        self.btnDesconectar.setEnabled(not libre)
        self.btn_enviar.setEnabled(conectado)
        self.input_tx.setEnabled(True)   # se puede escribir siempre (p. ej. para guardarlo como comando)

    # ==================================================================
    # Envío
    # ==================================================================
    def enviar_uart(self):
        texto = self.input_tx.text()
        if not texto.strip():
            return
        if self.enviar_texto(texto):
            self.input_tx.agregar_historial(texto)
            self.input_tx.clear()

    def enviar_texto(self, texto: str) -> bool:
        """Envía un texto por la UART (con el fin de línea elegido) y lo muestra como [TX]."""
        if self.hilo is None or not self._conectado:
            QMessageBox.warning(self, "Advertencia", "No hay conexión UART activa.\nConecta primero el puerto.")
            return False

        fin = self.comboFinLinea.currentData() or ""
        if not self.hilo.enviar(texto + fin):
            self._mensaje_app("No se pudo enviar: el puerto no está abierto", error=True)
            return False

        linea = self._formatear(time.time(), f"[TX] {texto}")
        self.consolaGeneral.agregar_lineas([(linea, COLOR_TX)])
        if self.grabador.activo:
            try:
                self.grabador.escribir([linea])
            except OSError:
                pass
        self.status.showMessage(f"Enviado: {texto}", 3000)
        return True

    # ==================================================================
    # Comandos guardados
    # ==================================================================
    def _crear_panel_comandos(self):
        self.comandos = cargar_comandos(self._ruta_comandos)
        self.panelComandos = PanelComandos(self.comandos)
        self.panelComandos.enviar.connect(self.enviar_texto)
        self.panelComandos.cambiado.connect(self._guardar_comandos)

        self.dockComandos = QDockWidget("Comandos", self)
        self.dockComandos.setObjectName("dockComandos")   # necesario para recordar su posición
        self.dockComandos.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.dockComandos.setWidget(self.panelComandos)
        self.dockComandos.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockComandos)

        accion = self.dockComandos.toggleViewAction()
        accion.setText("Panel de comandos")
        accion.setShortcut("Ctrl+K")
        self.menu.menuComandos.addAction(accion)
        self.menu.accionNuevoComando.triggered.connect(lambda: self._mostrar_comandos_y(self.panelComandos.anadir))

    def _mostrar_comandos_y(self, funcion):
        self.dockComandos.show()
        self.dockComandos.raise_()
        funcion()

    def _guardar_texto_como_comando(self):
        texto = self.input_tx.text().strip()
        self._mostrar_comandos_y(lambda: self.panelComandos.anadir(comando_sugerido=texto))

    def _guardar_comandos(self):
        try:
            guardar_comandos(self._ruta_comandos, self.comandos)
        except OSError as e:
            QMessageBox.warning(self, "Aviso", f"No se pudieron guardar los comandos:\n{e}")

    # ==================================================================
    # Limpiar / guardar
    # ==================================================================
    def limpiarConsolaActual(self):
        consola = self.tabs.currentWidget()
        if isinstance(consola, Consola):
            consola.limpiar()

    def limpiarTodas(self):
        self.consolaGeneral.limpiar()
        for consola in self.consolas_term.values():
            consola.limpiar()
        self._buffer_pausa.clear()
        self._no_leidos.clear()
        self._actualizar_titulo_pestana(ID_GENERAL)
        for id_ in self.consolas_term:
            self._actualizar_titulo_pestana(id_)
        self.status.showMessage("Consolas limpiadas", 2000)

    def guardarConsolaActual(self):
        consola = self.tabs.currentWidget()
        if isinstance(consola, Consola) and consola.guardar():
            self.status.showMessage("Consola guardada", 3000)

    def guardarTodas(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta donde guardar las consolas")
        if not carpeta:
            return
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        consolas = [self.consolaGeneral] + list(self.consolas_term.values())
        guardadas = 0
        for consola in consolas:
            nombre = re.sub(r"[^\w\-]+", "_", consola.titulo).strip("_") or "consola"
            if consola.guardar(os.path.join(carpeta, f"{fecha}_{nombre}.txt")):
                guardadas += 1
        QMessageBox.information(self, "Guardado", f"Se han guardado {guardadas} consolas en:\n{carpeta}")

    # ==================================================================
    # Grabación
    # ==================================================================
    def iniciarGrabacion(self):
        sugerido = f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        nombre, _ = QFileDialog.getSaveFileName(self, "Seleccionar archivo de grabación", sugerido,
                                                "Archivo de texto (*.txt)")
        if not nombre:
            return
        try:
            self.grabador.iniciar(nombre)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")
            return
        self._actualizar_controles_grabacion()
        self.status.showMessage(f"Grabando en: {nombre}")

    def detenerGrabacion(self):
        if self.grabador.activo:
            self.grabador.detener()
            self.status.showMessage("Grabación detenida", 3000)
        self._actualizar_controles_grabacion()

    def _actualizar_controles_grabacion(self):
        activo = self.grabador.activo
        self.btnIniciarGrabacion.setEnabled(not activo)
        self.btnDetenerGrabacion.setEnabled(activo)
        self.lblGrabacion.setText(f"Grabando en:\n{os.path.basename(self.grabador.ruta)}" if activo else "Sin grabar")
        self._actualizar_estadisticas()

    # ==================================================================
    # Ajustes persistentes
    # ==================================================================
    def _cargar_ajustes(self):
        a = self.ajustes
        geometria = a.value("geometria")
        if geometria is not None:
            self.restoreGeometry(geometria)
        estado = a.value("estado_ventana")
        if estado is not None:
            self.restoreState(estado)   # posición y visibilidad del panel de comandos
        for combo, clave in ((self.comboBaud, "baudrate"), (self.bytesize, "bytesize"),
                             (self.parity, "paridad"), (self.stopbits, "stopbits")):
            valor = a.value(clave)
            if valor is not None and combo.findText(str(valor)) >= 0:
                combo.setCurrentText(str(valor))
        indice = self.comboFinLinea.findText(str(a.value("fin_linea", "")))
        if indice >= 0:
            self.comboFinLinea.setCurrentIndex(indice)
        self.chkMarcasTiempo.setChecked(a.value("marcas_tiempo", False, type=bool))
        self.chkReconectar.setChecked(a.value("reconectar", True, type=bool))

    def _guardar_ajustes(self):
        a = self.ajustes
        a.setValue("geometria", self.saveGeometry())
        a.setValue("estado_ventana", self.saveState())
        a.setValue("puerto", self.comboPuerto.currentData() or "")
        a.setValue("baudrate", self.comboBaud.currentText())
        a.setValue("bytesize", self.bytesize.currentText())
        a.setValue("paridad", self.parity.currentText())
        a.setValue("stopbits", self.stopbits.currentText())
        a.setValue("fin_linea", self.comboFinLinea.currentText())
        a.setValue("marcas_tiempo", self.chkMarcasTiempo.isChecked())
        a.setValue("reconectar", self.chkReconectar.isChecked())

    # ==================================================================
    def acercaDe(self):
        QMessageBox.about(
            self, "Acerca de MonitorUART",
            f"<b>MonitorUART v{VERSION}</b><br>"
            "Monitor serie para STM32 con terminales por tipo de mensaje y comandos guardados.<br><br>"
            f"Configuración:<br><code>{carpeta_usuario()}</code>",
        )

    def closeEvent(self, evento):
        self.timerPuertos.stop()
        self.desconectar()
        self.grabador.detener()
        self._guardar_ajustes()
        evento.accept()
