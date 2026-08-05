import sys, os
from PyQt6.QtWidgets import QTextEdit

class Consola(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    