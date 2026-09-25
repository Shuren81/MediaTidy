#!/usr/bin/env python3
"""
media_tidy.py - Punto di ingresso di MediaTidy (Rinomina e Organizza Film e Serie TV).

Avvia la QApplication e la finestra principale (ui/main_window.py), che ospita le
due schede: Film (core/movie_handler.py) e Serie TV (core/series_handler.py).
"""
import sys
from pathlib import Path

from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

from ui.main_window import MainWindow

ICON_PATH = Path(__file__).resolve().parent / "MT_Icon.png"


def main():
    app = QApplication(sys.argv)

    # Percorso relativo allo script, non alla cartella da cui si lancia il comando:
    # funziona indipendentemente da dove viene avviato python3 media_tidy.py.
    if ICON_PATH.is_file():
        icon = QIcon(str(ICON_PATH))
        app.setWindowIcon(icon)
    else:
        icon = None

    w = MainWindow()
    if icon is not None:
        w.setWindowIcon(icon)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
