"""
Clasificación de mensajes en terminales.

Cada terminal tiene una regla: si una línea cumple la regla, se muestra en esa
terminal (además de en la consola General, salvo que se indique lo contrario).

Tipos de regla:
- "prefijo":  la línea empieza por el texto          → p. ej. "[ERR"
- "contiene": la línea contiene el texto en cualquier parte
- "regex":    expresión regular de Python (re.search)

Este módulo no depende de Qt.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, field, fields

TIPOS_FILTRO = {
    "prefijo": "Empieza por",
    "contiene": "Contiene",
    "regex": "Expresión regular",
}


@dataclass
class ReglaTerminal:
    nombre: str
    patron: str
    tipo: str = "prefijo"
    color: str = "#e0e0e0"
    activo: bool = True
    mayusculas: bool = False     # True = distingue mayúsculas/minúsculas
    en_general: bool = True      # True = la línea también se ve en la consola General
    alerta: bool = False         # True = aviso (sonido + parpadeo en la barra de tareas) al llegar
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self):
        self._regex = None
        self._valida = False
        try:
            self.validar()
        except ValueError:
            pass   # una regla inválida simplemente no coincide con nada

    # ------------------------------------------------------------------
    def validar(self):
        """Comprueba la regla y la prepara. Lanza ValueError con un mensaje claro."""
        self._valida = False
        if not self.nombre.strip():
            raise ValueError("El nombre no puede estar vacío.")
        if self.tipo not in TIPOS_FILTRO:
            raise ValueError(f"Tipo de filtro desconocido: {self.tipo}")
        if not self.patron:
            raise ValueError("El patrón no puede estar vacío.")

        if self.tipo == "regex":
            flags = 0 if self.mayusculas else re.IGNORECASE
            try:
                self._regex = re.compile(self.patron, flags)
            except re.error as e:
                raise ValueError(f"Expresión regular no válida: {e}") from None
        else:
            self._regex = None
            self._patron_cmp = self.patron if self.mayusculas else self.patron.casefold()

        self._valida = True

    def coincide(self, linea: str) -> bool:
        if not self.activo or not self._valida:
            return False

        if self.tipo == "regex":
            return self._regex.search(linea) is not None

        texto = linea if self.mayusculas else linea.casefold()
        if self.tipo == "prefijo":
            return texto.lstrip().startswith(self._patron_cmp)
        return self._patron_cmp in texto   # "contiene"

    # ------------------------------------------------------------------
    def a_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def desde_dict(cls, datos: dict) -> "ReglaTerminal":
        nombres = {f.name for f in fields(cls)}
        limpio = {k: v for k, v in datos.items() if k in nombres}
        return cls(**limpio)

    def copia(self) -> "ReglaTerminal":
        return ReglaTerminal.desde_dict(self.a_dict())


class Clasificador:
    """Decide a qué terminales va cada línea."""

    def __init__(self, reglas):
        self.reglas = [r for r in reglas if r.activo]

    def clasificar(self, linea: str) -> list:
        """Devuelve la lista de reglas que coinciden con la línea (en orden de prioridad)."""
        return [r for r in self.reglas if r.coincide(linea)]


def reglas_por_defecto() -> list:
    # Prefijos que envía el firmware (tabla MSG_TYPETEXT de TxUart.c).
    return [
        ReglaTerminal(nombre="Errores", patron="[ERR", tipo="prefijo", color="#ff5c5c", alerta=True),
        ReglaTerminal(nombre="Test", patron="[TST]", tipo="prefijo", color="#c792ea"),
        ReglaTerminal(nombre="Flash", patron="[FL1]", tipo="prefijo", color="#ffcb6b"),
        ReglaTerminal(nombre="Web", patron="[WEB]", tipo="prefijo", color="#82aaff"),
    ]


def cargar_reglas(ruta: str) -> list:
    """Lee las reglas del JSON. Si no existe o está dañado, devuelve las de por defecto."""
    if not os.path.exists(ruta):
        return reglas_por_defecto()
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        reglas = []
        for d in datos.get("terminales", []):
            if not isinstance(d, dict):
                continue
            try:
                reglas.append(ReglaTerminal.desde_dict(d))
            except (TypeError, ValueError):
                continue   # se ignora la entrada dañada, no todo el archivo
        return reglas
    except (OSError, ValueError, AttributeError):
        return reglas_por_defecto()


def guardar_reglas(ruta: str, reglas) -> None:
    """Guarda de forma atómica: si se corta a mitad, no se pierde el archivo anterior."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "terminales": [r.a_dict() for r in reglas]}, f,
                  ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)
