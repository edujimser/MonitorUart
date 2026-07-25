import serial
import serial.tools.list_ports
import time
from PyQt6.QtCore import QThread, pyqtSignal

class HiloUART(QThread):
    nuevaLinea = pyqtSignal(str)

    def __init__(self, puerto, baudrate, bytesize):
            super().__init__()
            self.puerto = puerto
            self.baudrate = baudrate
            self.bytesize = bytesize
            self.running = True

    def run(self):
        try:
            self.ser = serial.Serial(self.puerto, self.baudrate, timeout=0.1)
            self.nuevaLinea.emit(f"[INFO] Conectado a {self.puerto}\n")
        except:
            self.nuevaLinea.emit("[ERROR TX] No se pudo abrir el puerto\n")
            return

        while self.running:
            if not self.ser.is_open:
                self.nuevaLinea.emit("[ERROR TX] Puerto cerrado\n")
                break
            try:
                if self.ser.in_waiting:
                    raw = self.ser.read(self.ser.in_waiting)

                    try:
                        data = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        data = raw.decode("latin1")
                    
                    # Emitir la línea recibida al hilo principal
                    self.nuevaLinea.emit("[RX]")
                    self.nuevaLinea.emit(data)
                    
                time.sleep(0.001)

            except:
                self.nuevaLinea.emit("[ERROR TX] Conexión perdida\n")
                break

        self.ser.close()


    def detener(self):
         if  self.ser.is_open: 
             self.running = False
    
    
    def enviar_datos(self, datos):
        try:
            if not self.ser or not self.ser.is_open: 
                self.nuevaLinea.emit("[ERROR] Puerto cerrado, no se pueden enviar datos\n")
                return

            if datos is None:
                self.nuevaLinea.emit("[ERROR] No se pueden enviar datos nulos\n")
                return

            datos = datos.strip()
            if not datos:
                self.nuevaLinea.emit("[ERROR] No se pueden enviar datos vacíos\n")
                return

            datos += "\n"

            self.ser.write(datos.encode('utf-8'))
            self.nuevaLinea.emit(f"[TX] {datos}")

        except Exception as e:
            self.nuevaLinea.emit(f"[ERROR] No se pudo enviar datos: {str(e)}\n")