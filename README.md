# 🛠️ MonitorUART

[![Python Version](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=flat&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-blue?style=flat)](../../releases)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MonitorUART** es una aplicación de escritorio moderna desarrollada con Python 3.12 y PyQt6 para la monitorización, depuración y registro en tiempo real de comunicaciones serie (UART / Puerto COM).

---

## 📸 Captura de Pantalla

> *(Añade aquí una captura de pantalla de la aplicación)*
> ![MonitorUART Interface](docs/screenshot.png)

---

## ✨ Características Principales

- 🔌 **Gestión Serie Robusta:** Configuración y detección automática de puertos COM en tiempo real.
- 🎨 **Consola Tematizada:** Interfaz oscura (QSS) con estilos legibles, resaltado de mensajes y control de scroll.
- 🧵 **Multihilo con QThread:** Lectura continua del puerto serie en segundo plano sin congelar la interfaz gráfica.
- 📂 **Exportación de Logs:** Módulo para guardar eventos y datos recibidos en tiempo real.
- ⚠️ **Manejo Inteligente de Errores:** Detección de puerto bloqueado (Acceso denegado) con instrucciones amigables para el usuario.

---

## 📥 Descarga Ejecutable (Windows)

No necesitas tener Python ni ninguna librería instalada para usar la aplicación. Puedes descargar el ejecutable listo para usar desde la sección de entregas:

👉 **[Descargar MonitorUART.exe en Releases](../../releases/latest)**

---

## 🛠️ Instalación para Desarrolladores

Si deseas ejecutar o modificar el código fuente desde tu entorno local:

### 1. Clonar el repositorio
```bash
git clone [https://github.com/TU_USUARIO/MonitorUART.git](https://github.com/TU_USUARIO/MonitorUART.git)
cd MonitorUART
