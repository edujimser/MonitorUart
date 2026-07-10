import sys
import serial
import serial.tools.list_ports
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox, QStatusBar,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QTextCursor


class HiloUART(QThread):
    nuevaLinea = pyqtSignal(str)

    def __init__(self, puerto, baudrate):
        super().__init__()
        self.puerto = puerto
        self.baudrate = baudrate
        self.running = True

    def run(self):
        try:
            ser = serial.Serial(self.puerto, self.baudrate, timeout=0.1)
            self.nuevaLinea.emit(f"[INFO] Conectado a {self.puerto}\n")
        except:
            self.nuevaLinea.emit("[ERROR] No se pudo abrir el puerto\n")
            return

        while self.running:
            try:
                if ser.in_waiting:
                    # Señal interna para LED RX
                    self.nuevaLinea.emit("[RX]")

                    raw = ser.read(ser.in_waiting)

                    # Decodificación segura
                    try:
                        data = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        data = raw.decode("latin1")

                    self.nuevaLinea.emit(data)

            except:
                self.nuevaLinea.emit("[ERROR] Conexión perdida\n")
                break

        ser.close()

    def detener(self):
        self.running = False


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Monitor UART STM32 – Eduardo")
        self.resize(1000, 700)

        self.grabando = False
        self.archivo_grabacion = None

        # ---------------------------
        # Menú superior estilo Windows
        # ---------------------------
        menu = self.menuBar()

        menuArchivo = menu.addMenu("Archivo")

        accionGuardar = QAction("Guardar log", self)
        accionGuardar.triggered.connect(self.guardarLog)
        menuArchivo.addAction(accionGuardar)

        accionSalir = QAction("Salir", self)
        accionSalir.triggered.connect(self.close)
        menuArchivo.addAction(accionSalir)

        # ---------------------------
        # Panel central
        # ---------------------------
        central = QWidget()
        layout = QHBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # ---------------------------
        # Panel lateral (botonera)
        # ---------------------------
        panel = QVBoxLayout()

        self.comboPuerto = QComboBox()
        for p in serial.tools.list_ports.comports():
            self.comboPuerto.addItem(p.device)

        self.comboBaud = QComboBox()
        for b in ["9600", "115200", "230400", "921600", "2000000"]:
            self.comboBaud.addItem(b)

        self.btnConectar = QPushButton("Conectar")
        self.btnConectar.clicked.connect(self.conectar)

        self.btnDesconectar = QPushButton("Desconectar")
        self.btnDesconectar.clicked.connect(self.desconectar)

        self.btnIniciarGrabacion = QPushButton("Iniciar grabación")
        self.btnIniciarGrabacion.clicked.connect(self.iniciarGrabacion)

        self.btnDetenerGrabacion = QPushButton("Detener grabación")
        self.btnDetenerGrabacion.clicked.connect(self.detenerGrabacion)

        panel.addWidget(QLabel("Puerto"))
        panel.addWidget(self.comboPuerto)
        panel.addWidget(QLabel("Baudrate"))
        panel.addWidget(self.comboBaud)
        panel.addWidget(self.btnConectar)
        panel.addWidget(self.btnDesconectar)
        panel.addSpacing(20)
        panel.addWidget(QLabel("Grabación"))
        panel.addWidget(self.btnIniciarGrabacion)
        panel.addWidget(self.btnDetenerGrabacion)

        # ---------------------------
        # LEDs visuales
        # ---------------------------
        panel.addSpacing(20)
        panel.addWidget(QLabel("Indicadores"))

        panel.addWidget(QLabel("Actividad RX"))
        self.ledRX = QLabel()
        self.ledRX.setFixedSize(20, 20)
        self.ledRX.setStyleSheet("background-color: #444; border-radius: 10px;")
        panel.addWidget(self.ledRX)

        panel.addWidget(QLabel("Estado conexión"))
        self.ledEstado = QLabel()
        self.ledEstado.setFixedSize(20, 20)
        self.ledEstado.setStyleSheet("background-color: red; border-radius: 10px;")
        panel.addWidget(self.ledEstado)

        panel.addStretch()

        # ---------------------------
        # Consola estilo Windows
        # ---------------------------
        self.consola = QTextEdit()
        self.consola.setReadOnly(True)
        self.consola.setStyleSheet("""
            background-color: #1e1e1e;
            color: #d4d4d4;
            font-family: Consolas;
            font-size: 12pt;
        """)

        layout.addLayout(panel, 1)
        layout.addWidget(self.consola, 3)

        # ---------------------------
        # Barra de estado
        # ---------------------------
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Desconectado")

        self.hilo = None

    def conectar(self):
        puerto = self.comboPuerto.currentText()
        baud = int(self.comboBaud.currentText())

        self.hilo = HiloUART(puerto, baud)
        self.hilo.nuevaLinea.connect(self.mostrarTexto)
        self.hilo.start()

        self.ledEstado.setStyleSheet("background-color: green; border-radius: 10px;")
        self.status.showMessage(f"Conectado a {puerto}")

    def desconectar(self):
        if self.hilo:
            self.hilo.detener()
            self.hilo = None

        self.ledEstado.setStyleSheet("background-color: red; border-radius: 10px;")
        self.status.showMessage("Desconectado")

    def mostrarTexto(self, texto):

        # LED RX parpadeo
        if texto == "[RX]":
            self.ledRX.setStyleSheet("background-color: yellow; border-radius: 10px;")
            QTimer.singleShot(120, lambda: self.ledRX.setStyleSheet("background-color: #444; border-radius: 10px;"))
            self.status.showMessage("Recibiendo datos…")
            return

        # LED estado error
        if texto.startswith("[ERROR]"):
            self.ledEstado.setStyleSheet("background-color: red; border-radius: 10px;")
            self.status.showMessage(texto.strip())

        self.consola.insertPlainText(texto)
        self.consola.moveCursor(QTextCursor.MoveOperation.End)

        # Si estamos grabando, escribir en el archivo
        if self.grabando and self.archivo_grabacion:
            self.archivo_grabacion.write(texto.encode("utf-8", errors="ignore"))
            self.archivo_grabacion.flush()

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

    def guardarLog(self):
        nombre, _ = QFileDialog.getSaveFileName(self, "Guardar log", "", "Archivo de texto (*.txt)")
        if nombre:
            texto = self.consola.toPlainText()
            datos = texto.encode("utf-8", errors="ignore")

            with open(nombre, "wb") as f:
                f.write(datos)

            QMessageBox.information(self, "Guardado", "Log guardado correctamente.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())
