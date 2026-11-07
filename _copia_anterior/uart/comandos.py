"""
Biblioteca de comandos guardados para enviar al STM32 con un clic.

Cada comando tiene una parte fija (p. ej. "FLASH_READ_ALL_SECTOR_DIR") y, opcionalmente,
parámetros que se piden al enviarlo y se añaden separados por espacios:
    FLASH_READ_ALL_SECTOR_DIR 1 10 20 4

Se guardan en %APPDATA%\\MonitorUART\\comandos.json. No depende de Qt.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, field, fields


@dataclass
class Comando:
    comando: str                                       # parte fija que se envía
    categoria: str = "General"
    nombre: str = ""                                   # texto en la lista (si está vacío, el comando)
    parametros: list = field(default_factory=list)     # nombres: ["SecIni", "SecFin"]
    ejemplo: str = ""
    descripcion: str = ""
    confirmar: bool = False                            # pedir confirmación antes de enviar
    ultimos_valores: list = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # ------------------------------------------------------------------
    @property
    def titulo(self) -> str:
        return self.nombre.strip() or self.comando

    def validar(self) -> None:
        if not self.comando.strip():
            raise ValueError("El comando no puede estar vacío.")
        if any(not p.strip() for p in self.parametros):
            raise ValueError("Hay un parámetro sin nombre.")

    def valores_ejemplo(self) -> list:
        """Valores de los parámetros sacados del ejemplo ("CMD 0 5" → ["0", "5"])."""
        resto = self.ejemplo.strip()
        if resto.startswith(self.comando.strip()):
            resto = resto[len(self.comando.strip()):]
        valores = resto.split()
        return valores[:len(self.parametros)] if len(valores) >= len(self.parametros) else []

    def construir(self, valores=None) -> str:
        """Texto final a enviar. Lanza ValueError si falta algún parámetro."""
        base = self.comando.strip()
        valores = [str(v).strip() for v in (valores or [])]
        if len(valores) < len(self.parametros):
            valores += [""] * (len(self.parametros) - len(valores))
        for nombre, valor in zip(self.parametros, valores):
            if not valor:
                raise ValueError(f"Falta el parámetro «{nombre}».")
            if re.search(r"\s", valor):
                raise ValueError(f"El parámetro «{nombre}» no puede contener espacios.")
        partes = [base] + valores[:len(self.parametros)]
        return " ".join(partes)

    # ------------------------------------------------------------------
    def a_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def desde_dict(cls, datos: dict) -> "Comando":
        nombres = {f.name for f in fields(cls)}
        limpio = {k: v for k, v in datos.items() if k in nombres}
        for clave in ("parametros", "ultimos_valores"):
            if clave in limpio and not isinstance(limpio[clave], list):
                limpio[clave] = str(limpio[clave]).split()
        return cls(**limpio)

    def copia(self, nuevo_id: bool = False) -> "Comando":
        c = Comando.desde_dict(self.a_dict())
        c.parametros = list(self.parametros)
        c.ultimos_valores = list(self.ultimos_valores)
        if nuevo_id:
            c.id = uuid.uuid4().hex[:8]
        return c


def parsear_parametros(texto: str) -> list:
    """'[SecIni] [SecFin]', 'SecIni SecFin' o 'SecIni, SecFin' → ['SecIni', 'SecFin']."""
    texto = texto.strip()
    if not texto or texto.lower() in ("ninguno", "-", "none"):
        return []
    entre_corchetes = re.findall(r"\[([^\]]+)\]", texto)
    if entre_corchetes:
        return [p.strip() for p in entre_corchetes if p.strip()]
    return [p for p in re.split(r"[,\s]+", texto) if p]


def comandos_por_defecto() -> list:
    """Comandos que entiende el firmware (ThreadFunc_Uart_Rx)."""
    tabla = [
        # categoría, comando, parámetros, ejemplo, descripción, confirmar
        ("TEST", "TEST_TX", "", "TEST_TX", "Ejecuta la prueba de transmisión UART.", False),
        ("TEST", "TEST_FLASH_1", "", "TEST_FLASH_1", "Test Flash: inicialización centinela.", False),
        ("TEST", "TEST_FLASH_2", "", "TEST_FLASH_2", "Test Flash: rellenar la memoria completa.", True),

        ("READ ALL", "FLASH_READ_ALL_SECTOR_HEX", "", "FLASH_READ_ALL_SECTOR_HEX",
         "Lee toda la memoria en hexadecimal.", False),
        ("READ ALL", "FLASH_READ_ALL_SECTOR_ASCII", "", "FLASH_READ_ALL_SECTOR_ASCII",
         "Lee toda la memoria en ASCII.", False),
        ("READ ALL", "FLASH_READ_ALL_SECTOR_DUAL", "", "FLASH_READ_ALL_SECTOR_DUAL",
         "Lee toda la memoria en dual (hex + ASCII).", False),

        ("READ DIR", "FLASH_READ_ALL_SECTOR_DIR", "[Opción] [SecIni] [SecFin] [Pág]",
         "FLASH_READ_ALL_SECTOR_DIR 1 10 20 4",
         "Lee un rango específico. Opción: 1 = Hex, 2 = ASCII, 3 = Dual.", False),

        ("READ ENUM", "FLASH_READ_ALL_SECTOR_ENUM_HEX_LOAD", "", "FLASH_READ_ALL_SECTOR_ENUM_HEX_LOAD",
         "Lee la partición LOAD en hexadecimal.", False),
        ("READ ENUM", "FLASH_READ_ALL_SECTOR_ENUM_ASCII_LOAD", "", "FLASH_READ_ALL_SECTOR_ENUM_ASCII_LOAD",
         "Lee la partición LOAD en ASCII.", False),
        ("READ ENUM", "FLASH_READ_ALL_SECTOR_ENUM_DUAL_LOAD", "", "FLASH_READ_ALL_SECTOR_ENUM_DUAL_LOAD",
         "Lee la partición LOAD en dual.", False),

        ("READ ENUM RANGO", "FLASH_READ_ALL_SECTOR_ENUM_SECTOR_HEX_LOAD", "[SecIni] [SecFin]",
         "FLASH_READ_ALL_SECTOR_ENUM_SECTOR_HEX_LOAD 0 5", "Lee un rango de LOAD en hexadecimal.", False),
        ("READ ENUM RANGO", "FLASH_READ_ALL_SECTOR_ENUM_SECTOR_ASCII_LOAD", "[SecIni] [SecFin]",
         "FLASH_READ_ALL_SECTOR_ENUM_SECTOR_ASCII_LOAD 0 5", "Lee un rango de LOAD en ASCII.", False),
        ("READ ENUM RANGO", "FLASH_READ_ALL_SECTOR_ENUM_SECTOR_DUAL_LOAD", "[SecIni] [SecFin]",
         "FLASH_READ_ALL_SECTOR_ENUM_SECTOR_DUAL_LOAD 0 5", "Lee un rango de LOAD en dual.", False),

        ("ERASE ALL", "FLASH_ERASE_ALL", "", "FLASH_ERASE_ALL",
         "Borrado masivo (mass erase) de todo el chip.", True),
        ("ERASE PART", "FLASH_ERASE_PARTITION", "[ID_Partición]", "FLASH_ERASE_PARTITION 1",
         "Borra la partición completa (p. ej. 1 = LOG_MONITOR).", True),
        ("ERASE ONE", "FLASH_ERASE_ONE_HEX_FOR_SECTOR", "[Dir_Física]", "FLASH_ERASE_ONE_HEX_FOR_SECTOR 40960",
         "Borra el sector que contiene la dirección física indicada.", True),
        ("ERASE ONE", "FLASH_ERASE_ONE_SECTOR_FOR_SECTOR", "[Índice_Sector]",
         "FLASH_ERASE_ONE_SECTOR_FOR_SECTOR 10", "Borra un único sector por su índice lógico (0, 1, 2...).", True),
        ("ERASE RANGE", "FLASH_ERASE_RANGE_HEX_FOR_SECTOR", "[Dir_Ini] [Dir_Fin]",
         "FLASH_ERASE_RANGE_HEX_FOR_SECTOR 0 81920", "Borra desde una dirección física hasta otra.", True),
        ("ERASE RANGE", "FLASH_ERASE_RANGE_SECTOR_FOR_SECTOR", "[SecIni] [SecFin]",
         "FLASH_ERASE_RANGE_SECTOR_FOR_SECTOR 10 50", "Borra un rango de sectores por índices lógicos.", True),
    ]
    return [
        Comando(comando=cmd, categoria=cat, parametros=parsear_parametros(par), ejemplo=ej,
                descripcion=desc, confirmar=conf)
        for cat, cmd, par, ej, desc, conf in tabla
    ]


def cargar_comandos(ruta: str) -> list:
    """Lee los comandos del JSON. Si no existe o está dañado, devuelve los de por defecto."""
    if not os.path.exists(ruta):
        return comandos_por_defecto()
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        lista = datos.get("comandos", []) if isinstance(datos, dict) else datos
        comandos = []
        for d in lista:
            if not isinstance(d, dict):
                continue
            try:
                comandos.append(Comando.desde_dict(d))
            except (TypeError, ValueError):
                continue
        return comandos
    except (OSError, ValueError, AttributeError):
        return comandos_por_defecto()


def guardar_comandos(ruta: str, comandos) -> None:
    """Guarda de forma atómica (no se pierde el archivo si se corta a mitad)."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "comandos": [c.a_dict() for c in comandos]}, f,
                  ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)
