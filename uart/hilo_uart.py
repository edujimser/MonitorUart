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
        # Garantizar que self.ser existe siempre
        self.ser = None

        try:
            self.ser = serial.Serial(self.puerto, self.baudrate, timeout=0.1)
            self.nuevaLinea.emit(f"[INFO] Conectado a {self.puerto}\n")
        except Exception as e:
            self.nuevaLinea.emit(f"[ERROR TX] No se pudo abrir el puerto: {e}\n")
            self.ser = None
            return

        while self.running:
            # Si el puerto se cerró externamente
            if not self.ser or not self.ser.is_open:
                self.nuevaLinea.emit("[ERROR TX] Puerto cerrado\n")
                break

            try:
                if self.ser.in_waiting:
                    raw = self.ser.read(self.ser.in_waiting)

                    try:
                        data = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        data = raw.decode("latin1")

                    self.nuevaLinea.emit("[RX]")
                    self.nuevaLinea.emit(data)

                time.sleep(0.001)
            
            except Exception as e:
                # Verificar si es un error de acceso denegado (PermissionError / Error 13)
                if isinstance(e, PermissionError) or "PermissionError" in str(e) or "Acceso denegado" in str(e):
                    mensaje_usuario = "[ERROR TX] Haga clic en 'Desconectar' en la aplicación y luego desconecte y vuelva a conectar el equipo.\n"
                else:
                    # Para cualquier otro error genérico, mantiene el detalle técnico original
                    mensaje_usuario = f"[ERROR TX] Conexión perdida: {e}\n"

                self.nuevaLinea.emit(mensaje_usuario)
                break

        # Cierre seguro del puerto
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception as e:
            self.nuevaLinea.emit(f"[ERROR TX] Error al cerrar el puerto: {e}\n")


    def detener(self):
        self.running = False

        try:
            if self.ser and hasattr(self.ser, "is_open") and self.ser.is_open:
                self.ser.close()
        except Exception as e:
            print(f"Error al cerrar el puerto: {e}")

    
    
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