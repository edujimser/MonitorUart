"""
Hilo de comunicación con el puerto serie.

Mejoras respecto a la versión anterior:
- Entrega LÍNEAS completas (no trozos sueltos), necesario para clasificar por prefijo.
- Agrupa las líneas en lotes cada ~50 ms: con tráfico intenso la interfaz no se satura
  con miles de señales por segundo.
- Cada línea lleva la hora a la que se recibió (para las marcas de tiempo).
- Usa paridad y bits de parada (antes el combo de paridad no se aplicaba).
- El puerto solo lo toca este hilo: la interfaz ya no lo cierra desde otro hilo
  (eso podía provocar errores aleatorios al desconectar). Los envíos pasan por una cola.
- Lectura bloqueante con timeout en vez de un bucle con sleep(0.001): mucho menos uso de CPU.
"""

import queue
import threading
import time

import serial
from PyQt6.QtCore import QThread, pyqtSignal

from uart.lineas import EnsambladorLineas

PARIDADES = {
    "None": serial.PARITY_NONE, "N": serial.PARITY_NONE,
    "Even": serial.PARITY_EVEN, "E": serial.PARITY_EVEN,
    "Odd": serial.PARITY_ODD, "O": serial.PARITY_ODD,
    "Mark": serial.PARITY_MARK, "M": serial.PARITY_MARK,
    "Space": serial.PARITY_SPACE, "S": serial.PARITY_SPACE,
}

BITS_PARADA = {
    "1": serial.STOPBITS_ONE,
    "1.5": serial.STOPBITS_ONE_POINT_FIVE,
    "2": serial.STOPBITS_TWO,
}


class HiloUART(QThread):
    # Lista de tuplas (marca_de_tiempo: float, linea: str)
    lineasRecibidas = pyqtSignal(list)
    # Nº de bytes recibidos desde la última notificación (para el LED RX y estadísticas)
    actividadRx = pyqtSignal(int)
    # El puerto se abrió correctamente
    conectado = pyqtSignal(str)
    # No se pudo abrir el puerto o se perdió la conexión (texto para el usuario)
    errorConexion = pyqtSignal(str)
    # Avisos que no cortan la conexión (p. ej. fallo puntual al escribir)
    aviso = pyqtSignal(str)

    TIMEOUT_LECTURA = 0.05          # s que bloquea read() si no llegan datos
    INTERVALO_EMISION = 0.05        # s entre lotes enviados a la interfaz
    MAX_LOTE = 500                  # líneas máx. por lote
    TIEMPO_LINEA_INCOMPLETA = 0.2   # s sin datos para mostrar una línea sin '\n'

    def __init__(self, puerto, baudrate, bytesize=8, paridad="None", stopbits="1", parent=None):
        super().__init__(parent)
        self.puerto = puerto
        self.baudrate = int(baudrate)
        self.bytesize = int(bytesize)
        self.paridad = PARIDADES.get(str(paridad), serial.PARITY_NONE)
        self.stopbits = BITS_PARADA.get(str(stopbits), serial.STOPBITS_ONE)

        self._activo = threading.Event()
        self._activo.set()
        self._cola_tx = queue.Queue()
        self._abierto = threading.Event()

    # ------------------------------------------------------------------
    # API pública (se llama desde el hilo de la interfaz)
    # ------------------------------------------------------------------
    def detener(self):
        """Pide al hilo que termine. El propio hilo cierra el puerto (en < 0,1 s)."""
        self._activo.clear()

    def enviar(self, texto: str) -> bool:
        """Encola un texto para enviarlo. Devuelve False si el puerto no está abierto."""
        if not self._abierto.is_set() or not self._activo.is_set():
            return False
        self._cola_tx.put(texto.encode("utf-8"))
        return True

    # ------------------------------------------------------------------
    # Hilo
    # ------------------------------------------------------------------
    def run(self):
        try:
            ser = serial.Serial(
                port=self.puerto,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.paridad,
                stopbits=self.stopbits,
                timeout=self.TIMEOUT_LECTURA,
                write_timeout=1.0,
            )
        except (serial.SerialException, OSError) as e:
            self.errorConexion.emit(self._mensaje_amigable(e, al_abrir=True))
            return
        except ValueError as e:
            self.errorConexion.emit(f"Configuración del puerto no válida: {e}")
            return

        self._abierto.set()
        self.conectado.emit(self.puerto)

        ensamblador = EnsambladorLineas()
        pendientes = []
        bytes_pendientes = 0
        ultimo_envio = time.monotonic()
        ultimo_rx = ultimo_envio
        motivo_error = None

        try:
            while self._activo.is_set():
                self._procesar_tx(ser)

                n = ser.in_waiting
                datos = ser.read(n if n > 0 else 1)   # bloquea hasta TIMEOUT_LECTURA si no hay nada
                ahora = time.monotonic()

                if datos:
                    ultimo_rx = ahora
                    bytes_pendientes += len(datos)
                    marca = time.time()
                    for linea in ensamblador.alimentar(datos):
                        pendientes.append((marca, linea))

                elif ensamblador.pendiente and (ahora - ultimo_rx) >= self.TIEMPO_LINEA_INCOMPLETA:
                    resto = ensamblador.vaciar()
                    if resto is not None:
                        pendientes.append((time.time(), resto))

                if (ahora - ultimo_envio) >= self.INTERVALO_EMISION or len(pendientes) >= self.MAX_LOTE:
                    if bytes_pendientes:
                        self.actividadRx.emit(bytes_pendientes)
                        bytes_pendientes = 0
                    if pendientes:
                        self.lineasRecibidas.emit(pendientes)
                        pendientes = []
                    ultimo_envio = ahora

        except (serial.SerialException, OSError) as e:
            motivo_error = self._mensaje_amigable(e)

        finally:
            self._abierto.clear()

            # No perder lo que quedara a medias
            resto = ensamblador.vaciar()
            if resto is not None:
                pendientes.append((time.time(), resto))
            if bytes_pendientes:
                self.actividadRx.emit(bytes_pendientes)
            if pendientes:
                self.lineasRecibidas.emit(pendientes)

            try:
                ser.close()
            except Exception:
                pass

        # Solo es un error si nadie pidió parar
        if motivo_error and self._activo.is_set():
            self.errorConexion.emit(motivo_error)

    def _procesar_tx(self, ser):
        while True:
            try:
                datos = self._cola_tx.get_nowait()
            except queue.Empty:
                return
            try:
                ser.write(datos)
            except serial.SerialTimeoutException:
                # Error puntual: no cortamos la conexión
                self.aviso.emit("Tiempo de escritura agotado: el dispositivo no acepta datos")

    @staticmethod
    def _mensaje_amigable(e, al_abrir=False) -> str:
        texto = str(e)
        bajo = texto.lower()

        if isinstance(e, PermissionError) or "permissionerror" in bajo or "acceso denegado" in bajo \
                or "access is denied" in bajo or "errno 13" in bajo:
            if al_abrir:
                return ("No se puede abrir el puerto: está ocupado por otro programa o no hay permisos. "
                        "Cierra otros monitores serie (STM32CubeIDE, PuTTY, Arduino...) y vuelve a intentarlo.")
            return ("Se ha perdido el acceso al puerto. Pulsa 'Desconectar', desconecta y vuelve a "
                    "conectar el equipo.")

        if "filenotfounderror" in bajo or "could not open port" in bajo or "no such file" in bajo \
                or "el sistema no puede encontrar" in bajo:
            return "El puerto no existe o el dispositivo se ha desconectado."

        if "clearcommerror" in bajo or "device reports readiness" in bajo or "writefile failed" in bajo \
                or "readfile failed" in bajo:
            return "El dispositivo se ha desconectado (cable USB retirado o placa reiniciada)."

        if al_abrir:
            return f"No se pudo abrir el puerto: {texto}"
        return f"Conexión perdida: {texto}"
