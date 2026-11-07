"""
Gestión de las categorías del panel de comandos: añadir, renombrar, eliminar y ordenar.

Trabaja sobre copias: si se pulsa Cancelar no cambia nada.
"""

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QMessageBox, QPushButton, QVBoxLayout,
)

from uart.comandos import normalizar_categorias


def pedir_nombre_categoria(parent, titulo, existentes, actual=""):
    """Pide un nombre de categoría válido y no repetido. Devuelve el nombre o None."""
    while True:
        nombre, ok = QInputDialog.getText(parent, titulo, "Nombre de la categoría:", text=actual)
        if not ok:
            return None
        nombre = nombre.strip()
        if not nombre:
            QMessageBox.warning(parent, titulo, "El nombre no puede estar vacío.")
            continue
        if nombre != actual and nombre in existentes:
            QMessageBox.warning(parent, titulo, f"Ya existe una categoría llamada «{nombre}».")
            continue
        return nombre


class GestorCategorias(QDialog):
    def __init__(self, categorias, comandos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionar categorías")
        self.resize(460, 400)

        self._comandos = [c.copia() for c in comandos]
        self._categorias = normalizar_categorias(categorias, self._comandos)

        self.lista = QListWidget()
        self.lista.setObjectName("listaCategorias")
        self.lista.currentRowChanged.connect(lambda _f: self._actualizar_botones())
        self.lista.itemDoubleClicked.connect(lambda _i: self._renombrar())

        self.btnAnadir = QPushButton("Añadir…")
        self.btnRenombrar = QPushButton("Renombrar…")
        self.btnEliminar = QPushButton("Eliminar…")
        self.btnSubir = QPushButton("Subir")
        self.btnBajar = QPushButton("Bajar")
        self.btnOrdenar = QPushButton("Ordenar A-Z")

        self.btnAnadir.clicked.connect(self._anadir)
        self.btnRenombrar.clicked.connect(self._renombrar)
        self.btnEliminar.clicked.connect(self._eliminar)
        self.btnSubir.clicked.connect(lambda: self._mover(-1))
        self.btnBajar.clicked.connect(lambda: self._mover(+1))
        self.btnOrdenar.clicked.connect(self._ordenar)

        columna = QVBoxLayout()
        for b in (self.btnAnadir, self.btnRenombrar, self.btnEliminar, self.btnSubir, self.btnBajar):
            columna.addWidget(b)
        columna.addStretch(1)
        columna.addWidget(self.btnOrdenar)

        centro = QHBoxLayout()
        centro.addWidget(self.lista, 1)
        centro.addLayout(columna)

        info = QLabel("El orden de esta lista es el orden en el panel de comandos. "
                      "Puedes crear categorías vacías y llenarlas después.")
        info.setWordWrap(True)
        info.setObjectName("infoLabel")

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(centro, 1)
        layout.addWidget(botones)

        self._refrescar(0)

    # ------------------------------------------------------------------
    def resultado(self):
        """(categorias, comandos) tras los cambios."""
        return list(self._categorias), self._comandos

    # ------------------------------------------------------------------
    def _num_comandos(self, categoria):
        return sum(1 for c in self._comandos if c.categoria == categoria)

    def _refrescar(self, seleccion=-1):
        self.lista.clear()
        for cat in self._categorias:
            n = self._num_comandos(cat)
            self.lista.addItem(f"{cat}    ({n} comando{'s' if n != 1 else ''})")
        if self._categorias:
            self.lista.setCurrentRow(min(max(seleccion, 0), len(self._categorias) - 1))
        self._actualizar_botones()

    def _actual(self):
        fila = self.lista.currentRow()
        return fila if 0 <= fila < len(self._categorias) else -1

    def _actualizar_botones(self):
        fila = self._actual()
        hay = fila >= 0
        self.btnRenombrar.setEnabled(hay)
        self.btnEliminar.setEnabled(hay)
        self.btnSubir.setEnabled(hay and fila > 0)
        self.btnBajar.setEnabled(hay and fila < len(self._categorias) - 1)

    def _anadir(self):
        nombre = pedir_nombre_categoria(self, "Nueva categoría", self._categorias)
        if nombre:
            fila = self._actual()
            posicion = fila + 1 if fila >= 0 else len(self._categorias)
            self._categorias.insert(posicion, nombre)
            self._refrescar(posicion)

    def _renombrar(self):
        fila = self._actual()
        if fila < 0:
            return
        viejo = self._categorias[fila]
        nuevo = pedir_nombre_categoria(self, "Renombrar categoría", self._categorias, viejo)
        if nuevo and nuevo != viejo:
            self._categorias[fila] = nuevo
            for c in self._comandos:
                if c.categoria == viejo:
                    c.categoria = nuevo
            self._refrescar(fila)

    def _eliminar(self):
        fila = self._actual()
        if fila < 0:
            return
        cat = self._categorias[fila]
        n = self._num_comandos(cat)

        if n == 0:
            if QMessageBox.question(self, "Eliminar categoría",
                                    f"¿Eliminar la categoría vacía «{cat}»?") == QMessageBox.StandardButton.Yes:
                del self._categorias[fila]
                self._refrescar(fila)
            return

        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Question)
        caja.setWindowTitle("Eliminar categoría")
        caja.setText(f"La categoría «{cat}» tiene {n} comando{'s' if n != 1 else ''}.\n¿Qué quieres hacer con ellos?")
        otras = [c for c in self._categorias if c != cat]
        btnMover = caja.addButton("Moverlos a otra categoría…", QMessageBox.ButtonRole.AcceptRole) if otras else None
        btnBorrar = caja.addButton("Eliminarlos también", QMessageBox.ButtonRole.DestructiveRole)
        caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caja.exec()
        pulsado = caja.clickedButton()

        if btnMover is not None and pulsado is btnMover:
            destino, ok = QInputDialog.getItem(self, "Mover comandos", f"Mover los comandos de «{cat}» a:",
                                               otras, 0, False)
            if not ok:
                return
            for c in self._comandos:
                if c.categoria == cat:
                    c.categoria = destino
        elif pulsado is btnBorrar:
            if QMessageBox.question(self, "Confirmar",
                                    f"Se eliminarán {n} comandos. ¿Seguro?") != QMessageBox.StandardButton.Yes:
                return
            self._comandos = [c for c in self._comandos if c.categoria != cat]
        else:
            return

        del self._categorias[fila]
        self._refrescar(fila)

    def _mover(self, delta):
        fila = self._actual()
        destino = fila + delta
        if fila >= 0 and 0 <= destino < len(self._categorias):
            cats = self._categorias
            cats[fila], cats[destino] = cats[destino], cats[fila]
            self._refrescar(destino)

    def _ordenar(self):
        self._categorias.sort(key=str.casefold)
        self._refrescar(0)
