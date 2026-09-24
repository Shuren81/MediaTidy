#!/usr/bin/env python3
"""
media_tidy.py - Punto di ingresso di MediaTidy (Rinomina e Organizza Film e Serie TV).

Avvia la QApplication e la finestra principale (ui/main_window.py), che ospita le
due schede: Film (core/movie_handler.py) e Serie TV (core/series_handler.py).
"""
import sys

from qtpy.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
