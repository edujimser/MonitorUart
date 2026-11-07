import os
import sys


def resource_path(relative_path: str) -> str:
    """Ruta a un recurso empaquetado (funciona en desarrollo y dentro del .exe de PyInstaller)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def carpeta_usuario() -> str:
    """Carpeta donde se guarda la configuración del usuario (escribible también desde el .exe).

    Windows: %APPDATA%\\MonitorUART   ·   Linux/macOS: ~/.config/MonitorUART
    """
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    ruta = os.path.join(base, "MonitorUART")
    try:
        os.makedirs(ruta, exist_ok=True)
    except OSError:
        ruta = os.path.abspath(".")
    return ruta
