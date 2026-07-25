from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QStatusBar,
    QFileDialog, QMessageBox, QLineEdit
)
from gui.menu.menuSuperiorA import MenuSuperiorA
from gui.panels.Consola import Consola
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QTextCursor
import serial.tools.list_ports
from uart.hilo_uart import HiloUART 
import json
import os

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        
        #Aplicar estilo
        self.aplicarEstilo()
        
        #Aplicar título y tamaño de la ventana
        self.setWindowTitle("Monitor UART STM32 v1.0.1")
        self.resize(1000, 700)

        # Inicializar variables 
        self.grabando = False
        self.archivo_grabacion = None
        
        # Timer para refrescar puertos
        self.timerPuertos = QTimer()
        self.timerPuertos.timeout.connect(self.actualizarPuertos)
        self.timerPuertos.start(1000)

        # ---------------------------
        # Menú superior estilo Windows
        # ---------------------------
        menuSuperior = MenuSuperiorA(self)
        self.setMenuBar(menuSuperior)

        menuSuperior.accionGuardar.triggered.connect(self.guardarLog)
        menuSuperior.accionSalir.triggered.connect(self.close)

        # ---------------------------
        # Panel central
        # ---------------------------
        central = QWidget()
        layout = QHBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # ---------------------------
        # Consola 
        # ---------------------------
        self.consola = Consola(self)

        # ---------------------------------------------------------------------------------
        # Panel lateral 
        # ---------------------------------------------------------------------------------
        panel = QVBoxLayout()
        ancho = 180
        
        ruta = os.path.join("config", "serial_config.json")
        with open(ruta, "r") as f:
            cfg = json.load(f)
    
        # Combo de puertos
        self.comboPuerto = QComboBox()
        self.comboPuerto.setFixedWidth(ancho)
        for p in serial.tools.list_ports.comports():
            self.comboPuerto.addItem(p.device)
        
        # Combo de baudrate
        self.comboBaud = QComboBox()
        self.comboBaud.setFixedWidth(ancho)
        self.comboBaud.addItems([str(b) for b in cfg["baudrates"]])

        view = self.comboBaud.view()
        view.setSpacing(0)
        view.setUniformItemSizes(True)
        view.setStyleSheet("QListView::item { height: 18px; }")

        # Combo de bytesize
        self.bytesize = QComboBox()
        self.bytesize.setFixedWidth(ancho)
        for c in cfg["bytesizes"]:
            self.bytesize.addItem(str(c))
            
        # Parity
        self.parity = QComboBox()
        self.parity.setFixedWidth(ancho)
        for p in cfg["parities"]:
            self.parity.addItem(p)

        # Botones
        self.btnConectar = QPushButton("Conectar")
        self.btnConectar.setFixedWidth(ancho)
        self.btnConectar.clicked.connect(self.conectar)

        self.btnDesconectar = QPushButton("Desconectar")
        self.btnDesconectar.setFixedWidth(ancho)
        self.btnDesconectar.clicked.connect(self.desconectar)

        self.btnIniciarGrabacion = QPushButton("Iniciar grabación")
        self.btnIniciarGrabacion.setFixedWidth(ancho)
        self.btnIniciarGrabacion.clicked.connect(self.iniciarGrabacion)

        self.btnDetenerGrabacion = QPushButton("Detener grabación")
        self.btnDetenerGrabacion.setFixedWidth(ancho)
        self.btnDetenerGrabacion.clicked.connect(self.detenerGrabacion)
        
        self.input_tx = QLineEdit()
        self.input_tx.setPlaceholderText("Escribe datos para enviar...")
        layout_tx = QHBoxLayout()
        layout_tx.addWidget(self.input_tx)
        self.btn_enviar = QPushButton("Enviar")
        self.btn_enviar.setFixedWidth(ancho)
        self.btn_enviar.clicked.connect(self.enviar_uart)
        layout_tx.addWidget(self.btn_enviar)

        panel.addWidget(QLabel("Puerto"))
        panel.addWidget(self.comboPuerto)
        panel.addWidget(QLabel("Baudrate"))
        panel.addWidget(self.comboBaud)
        panel.addWidget(QLabel("Bytesize"))
        panel.addWidget(self.bytesize)
        panel.addWidget(self.btnConectar)
        panel.addWidget(self.btnDesconectar)
        panel.addSpacing(20)
        panel.addWidget(QLabel("Grabación"))
        panel.addWidget(self.btnIniciarGrabacion)
        panel.addWidget(self.btnDetenerGrabacion)
        panel.addSpacing(20)
        panel.addWidget(QLabel("Enviar datos"))
        panel.addWidget(self.input_tx)
        panel.addWidget(self.btn_enviar)
        # ---------------------------
        # LEDs horizontales
        # ---------------------------
        panel.addSpacing(20)
        panel.addWidget(QLabel("Indicadores"))

        ledLayout = QHBoxLayout()

        ledLayout.addWidget(QLabel("RX"))
        self.ledRX = QLabel()
        self.ledRX.setFixedSize(18, 18)
        self.ledRX.setStyleSheet("background-color: #444; border-radius: 9px;")
        ledLayout.addWidget(self.ledRX)

        ledLayout.addSpacing(10)

        ledLayout.addWidget(QLabel("Estado"))
        self.ledEstado = QLabel()
        self.ledEstado.setFixedSize(18, 18)
        self.ledEstado.setStyleSheet("background-color: red; border-radius: 9px;")
        ledLayout.addWidget(self.ledEstado)

        panel.addLayout(ledLayout)

        # ---------------------------
        # Información del puerto
        # ---------------------------
        panel.addSpacing(20)
        panel.addWidget(QLabel("Información del puerto"))

        infoLayout = QVBoxLayout()

        self.infoDescripcion = QLabel("Descripción: -")
        self.infoFabricante = QLabel("Fabricante: -")
        self.infoProducto = QLabel("Producto: -")
        self.infoSerial = QLabel("Número de serie: -")
        self.infoHWID = QLabel("HWID: -")

        for lbl in [
            self.infoDescripcion, self.infoFabricante,
            self.infoProducto, self.infoSerial, self.infoHWID
        ]:
            lbl.setStyleSheet("font-size: 10pt; color: #ccc;")
            lbl.setWordWrap(True)
            infoLayout.addWidget(lbl)

        panel.addLayout(infoLayout)
        self.dataPuertos()
        
        # ---------------------------
        # Panel lateral con ancho fijo
        # ---------------------------
        panelWidget = QWidget()
        panelWidget.setLayout(panel)
        panelWidget.setFixedWidth(220)

        layout.addWidget(panelWidget)
        layout.addWidget(self.consola, 1)

        # ---------------------------
        # Barra de estado
        # ---------------------------
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Desconectado")

        self.hilo = None
    
    # ============================================================
    # Aplicar estilo
    # ============================================================
    def aplicarEstilo(self):
        with open("gui/style/ElegantDark.qss", "r") as f:
            estilo = f.read()
            
        self.setStyleSheet(estilo)
    # ============================================================
    # Información del puerto seleccionado
    # ============================================================
    def dataPuertos(self):
        puerto = self.comboPuerto.currentText()

        if not puerto:
            return

        for p in serial.tools.list_ports.comports():
            if p.device == puerto:
                self.infoDescripcion.setText(f"Descripción: {p.description or 'No disponible'}")
                self.infoFabricante.setText(f"Fabricante: {p.manufacturer or 'No disponible'}")
                self.infoProducto.setText(f"Producto: {p.product or 'No disponible'}")
                self.infoSerial.setText(f"Número de serie: {p.serial_number or 'No disponible'}")
                self.infoHWID.setText(f"HWID: {p.hwid or 'No disponible'}")
                return


    # ============================================================
    # Actualizar lista de puertos
    # ============================================================
    def actualizarPuertos(self):
        puertos_actuales = [p.device for p in serial.tools.list_ports.comports()]
        puertos_combo = [self.comboPuerto.itemText(i) for i in range(self.comboPuerto.count())]

        if puertos_actuales != puertos_combo:
            self.comboPuerto.clear()

            for p in puertos_actuales:
                self.comboPuerto.addItem(p)

            if puertos_actuales:
                self.comboPuerto.setCurrentIndex(0)
                self.dataPuertos()


    # ============================================================
    # Conectar
    # ============================================================
    def conectar(self):
        puerto = self.comboPuerto.currentText()
        baud = int(self.comboBaud.currentText())
        bytesize = int(self.bytesize.currentText())

        self.hilo = HiloUART(puerto, baud, bytesize)
        self.hilo.nuevaLinea.connect(self.mostrarTexto)
        self.hilo.start()

        self.ledEstado.setStyleSheet("background-color: green; border-radius: 9px;")
        self.status.showMessage(f"Conectado a {puerto}")


    # ============================================================
    # Desconectar
    # ============================================================
    def desconectar(self):
        if self.hilo:
            self.hilo.detener()
            self.hilo.wait()
            self.hilo = None

        self.ledEstado.setStyleSheet("background-color: red; border-radius: 9px;")
        self.status.showMessage("Desconectado")


    # ============================================================
    # Mostrar texto recibido
    # ============================================================
    def mostrarTexto(self, texto):

        # LED RX parpadeo
        if texto == "[RX]":
            self.ledRX.setStyleSheet("background-color: yellow; border-radius: 9px;")
            QTimer.singleShot(120, lambda: self.ledRX.setStyleSheet("background-color: #444; border-radius: 9px;"))
            self.status.showMessage("Recibiendo datos…")
            return

        # LED estado error
        if texto.startswith("[ERROR TX]"):
            self.ledEstado.setStyleSheet("background-color: red; border-radius: 9px;")
            self.status.showMessage(texto.strip())

        self.consola.insertPlainText(texto)
        self.consola.moveCursor(QTextCursor.MoveOperation.End)

        # Si estamos grabando, escribir en el archivo
        if self.grabando and self.archivo_grabacion:
            self.archivo_grabacion.write(texto.encode("utf-8", errors="ignore"))
            self.archivo_grabacion.flush()


    # ============================================================
    # Grabación
    # ============================================================
    def iniciarGrabacion(self):
        nombre, _ = QFileDialog.getSaveFileName(
            self,
            "Seleccionar archivo de grabación",
            "",
            "Archivo de texto (*.txt)"
        )

        if not nombre:
            return

        try:
            self.archivo_grabacion = open(nombre, "wb")
            self.grabando = True
            self.status.showMessage(f"Grabando en: {nombre}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")


    def detenerGrabacion(self):
        if self.grabando:
            self.grabando = False
            if self.archivo_grabacion:
                self.archivo_grabacion.close()
                self.archivo_grabacion = None
            self.status.showMessage("Grabación detenida")


    # ============================================================
    # Guardar log
    # ============================================================
    def guardarLog(self):
        nombre, _ = QFileDialog.getSaveFileName(self, "Guardar log", "", "Archivo de texto (*.txt)")
        if nombre:
            texto = self.consola.toPlainText()
            datos = texto.encode("utf-8", errors="ignore")

            with open(nombre, "wb") as f:
                f.write(datos)

            QMessageBox.information(self, "Guardado", "Log guardado correctamente.")

    # ============================================================
    # Enviar UART   
    # ============================================================
    def enviar_uart(self):
        if not self.hilo:
            QMessageBox.warning(self, "Advertencia", "No hay conexión UART activa.")
            return
        
        self.hilo.enviar_datos(self.input_tx.text())