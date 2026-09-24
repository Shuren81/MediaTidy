#!/usr/bin/env python3
"""
ui/main_window.py - Finestra principale di MediaTidy: barra in alto con Opzioni e
Crediti, e un QTabWidget con le due schede "Film" e "Serie TV".
"""
from config import CONFIG, load_config, save_config
from localization import tr
from ui.movie_tab import MovieTab
from ui.series_tab import SeriesTab
from ui.widgets import CreditsPrivacyDialog
from ui.settings_dialog import SettingsDialog

from qtpy.QtWidgets import (
    QDialog, QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_config()
        self.resize(1450, 780)

        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        self.btn_settings = QPushButton()
        self.btn_settings.clicked.connect(self.open_settings)
        top_bar.addWidget(self.btn_settings)
        self.btn_credits = QPushButton()
        self.btn_credits.clicked.connect(self.open_credits)
        top_bar.addWidget(self.btn_credits)
        top_bar.addStretch(1)
        lay.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.movie_tab = MovieTab()
        self.series_tab = SeriesTab()
        self.movie_tab.status_callback = self.statusBar().showMessage
        self.series_tab.status_callback = self.statusBar().showMessage
        self.tabs.addTab(self.movie_tab, "")
        self.tabs.addTab(self.series_tab, "")
        lay.addWidget(self.tabs, 1)

        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.btn_settings.setText(tr("options"))
        self.btn_credits.setText(tr("credits_btn"))
        self.tabs.setTabText(0, tr("tab_movies"))
        self.tabs.setTabText(1, tr("tab_series"))
        self.statusBar().showMessage(tr("ready_status"))
        self.movie_tab.retranslate_ui()
        self.series_tab.retranslate_ui()

    def open_settings(self):
        before = (CONFIG["dest_movies"], CONFIG["dest_series"], CONFIG["cap_rule"], CONFIG["lang"])
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            save_config()
            if before != (CONFIG["dest_movies"], CONFIG["dest_series"], CONFIG["cap_rule"], CONFIG["lang"]):
                # Gli esiti "Pronto"/"Esiste già" valevano per la configurazione precedente
                self.movie_tab.config_changed()
                self.series_tab.config_changed()
            self.retranslate_ui()

    def open_credits(self):
        dlg = CreditsPrivacyDialog(self)
        dlg.exec_()

    def closeEvent(self, e):
        if self.movie_tab.is_busy() or self.series_tab.is_busy():
            QMessageBox.information(self, tr("busy_title"), tr("busy_msg"))
            e.ignore()
            return
        self.movie_tab.cleanup_before_close()
        self.series_tab.cleanup_before_close()
        e.accept()
