#!/usr/bin/env python3
"""
ui/main_window.py - Finestra principale di MediaTidy: barra in alto (Opzioni,
Formato Nomi a sinistra — Log, Crediti & Privacy a destra), un'area di drop comune
che smista automaticamente Film/Serie TV, e il QTabWidget con le due schede.
"""
from config import CONFIG, load_config, save_config
from localization import tr
from media_operations import get_log_dir
from core.media_classifier import classify_paths, to_series_item
from ui.movie_tab import MovieTab
from ui.series_tab import SeriesTab
from ui.settings_dialog import SettingsDialog
from ui.format_dialog import FormatDialog
from ui.widgets import CreditsPrivacyDialog, DropZone

from qtpy.QtCore import QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QDialog, QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_config()
        self.resize(1450, 780)

        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)

        # --- Barra in alto: Opzioni/Formato a sinistra, Log/Crediti a destra ---
        top_bar = QHBoxLayout()
        self.btn_settings = QPushButton()
        self.btn_settings.clicked.connect(self.open_settings)
        top_bar.addWidget(self.btn_settings)

        self.btn_format = QPushButton()
        self.btn_format.clicked.connect(self.open_format)
        top_bar.addWidget(self.btn_format)

        top_bar.addStretch(1)

        self.btn_log = QPushButton()
        self.btn_log.setToolTip("Apri la cartella dei log e dei file CSV")
        self.btn_log.clicked.connect(self.open_log_folder)
        top_bar.addWidget(self.btn_log)

        self.btn_credits = QPushButton()
        self.btn_credits.clicked.connect(self.open_credits)
        top_bar.addWidget(self.btn_credits)

        lay.addLayout(top_bar)

        # --- Area di drop comune: smista Film/Serie da sola ---
        self.drop_zone = DropZone("add_media_drop")
        self.drop_zone.files_dropped.connect(lambda paths: self._dispatch(paths, default_hint=None))
        lay.addWidget(self.drop_zone)

        self.tabs = QTabWidget()
        self.movie_tab = MovieTab()
        self.series_tab = SeriesTab()

        self.movie_tab.status_callback = self.statusBar().showMessage
        self.series_tab.status_callback = self.statusBar().showMessage

        # Il drag&drop sulle tabelle passa anch'esso dal triage: ogni tabella resta
        # ricettiva a tutto e si "autocorregge" spostando nell'altra scheda ciò che
        # non è suo (vedi _dispatch). Il default_hint privilegia il tipo della scheda
        # su cui l'utente ha trascinato, solo per i casi genuinamente ambigui.
        self.movie_tab.table.files_dropped.connect(lambda paths: self._dispatch(paths, default_hint="movie"))
        self.series_tab.table.files_dropped.connect(lambda paths: self._dispatch(paths, default_hint="series"))

        self.tabs.addTab(self.movie_tab, "")
        self.tabs.addTab(self.series_tab, "")
        lay.addWidget(self.tabs, 1)

        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.btn_settings.setText(tr("options"))
        self.btn_format.setText(tr("format_btn"))
        self.btn_log.setText(tr("log_btn"))
        self.btn_credits.setText(tr("credits_btn"))
        self.drop_zone.retranslate()

        self.tabs.setTabText(0, tr("tab_movies"))
        self.tabs.setTabText(1, tr("tab_series"))

        self.statusBar().showMessage(tr("ready_status"))
        self.movie_tab.retranslate_ui()
        self.series_tab.retranslate_ui()

    # ------------------------------------------------------------------ #
    #  Triage automatico Film / Serie TV
    # ------------------------------------------------------------------ #
    def _dispatch(self, paths, default_hint):
        """Classifica i percorsi trascinati (senza rete) e li smista nella scheda
        giusta; per i casi ambiguous chiede all'utente, con un default suggerito
        dalla scheda/zona su cui è avvenuto il drop."""
        classified = classify_paths(paths)
        if not classified:
            self.statusBar().showMessage(tr("no_video_found"))
            return

        movie_known = self.movie_tab.known_paths()
        series_known = self.series_tab.known_paths()
        n_movies = n_series = 0

        for cf in classified:
            if cf.path in movie_known or cf.path in series_known:
                continue

            kind = cf.kind
            if kind == "ambiguous":
                kind = self._ask_ambiguous(cf, default_hint)
                if kind is None:
                    continue  # l'utente ha scelto di saltare questo file

            if kind == "movie":
                self.movie_tab.add_item(cf.path, cf.release_dir is not None)
                movie_known.add(cf.path)
                n_movies += 1
            else:
                self.series_tab.add_item(to_series_item(cf))
                series_known.add(cf.path)
                n_series += 1

        self.movie_tab.update_buttons()
        self.series_tab.update_buttons()
        if n_movies or n_series:
            self.statusBar().showMessage(tr("triage_result", movies=n_movies, series=n_series))

    def _ask_ambiguous(self, cf, default_hint):
        box = QMessageBox(self)
        box.setWindowTitle(tr("ambiguous_title"))
        box.setText(tr("ambiguous_msg", name=cf.path.name))
        btn_movie = box.addButton(tr("ambiguous_btn_movie"), QMessageBox.YesRole)
        btn_series = box.addButton(tr("ambiguous_btn_series"), QMessageBox.NoRole)
        box.addButton(QMessageBox.Cancel)
        if default_hint == "movie":
            box.setDefaultButton(btn_movie)
        elif default_hint == "series":
            box.setDefaultButton(btn_series)
        box.exec_()
        clicked = box.clickedButton()
        if clicked == btn_movie:
            return "movie"
        if clicked == btn_series:
            return "series"
        return None

    # ------------------------------------------------------------------ #
    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            save_config()
            self.retranslate_ui()

    def open_format(self):
        before = (
            CONFIG["dest_movies"], CONFIG["action_movies"], CONFIG["movie_title_mode"],
            CONFIG["movie_include_tmdb_id"], CONFIG["movie_include_country"],
            CONFIG["movie_include_director"], CONFIG["movie_download_poster"],
            CONFIG["dest_series"], CONFIG["action_series"], CONFIG["series_title_mode"],
            CONFIG["series_include_tmdb_id"], CONFIG["series_include_episode_title"],
            CONFIG["series_download_show_poster"], CONFIG["series_download_season_poster"],
        )
        dlg = FormatDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            save_config()
            after = (
                CONFIG["dest_movies"], CONFIG["action_movies"], CONFIG["movie_title_mode"],
                CONFIG["movie_include_tmdb_id"], CONFIG["movie_include_country"],
                CONFIG["movie_include_director"], CONFIG["movie_download_poster"],
                CONFIG["dest_series"], CONFIG["action_series"], CONFIG["series_title_mode"],
                CONFIG["series_include_tmdb_id"], CONFIG["series_include_episode_title"],
                CONFIG["series_download_show_poster"], CONFIG["series_download_season_poster"],
            )
            if before != after:
                # Gli esiti "Pronto"/"Esiste già" valevano per la configurazione precedente.
                self.movie_tab.config_changed()
                self.series_tab.config_changed()

    def open_credits(self):
        dlg = CreditsPrivacyDialog(self)
        dlg.exec_()

    def open_log_folder(self):
        """Crea, se necessario, e apre la cartella configurata per log e CSV."""
        try:
            log_dir = get_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))
            if not opened:
                raise RuntimeError("Il sistema non ha aperto la cartella.")
        except Exception as error:
            QMessageBox.warning(self, "Cartella log", f"Non è stato possibile aprire la cartella dei log:\n{error}")

    def closeEvent(self, event):
        if self.movie_tab.is_busy() or self.series_tab.is_busy():
            QMessageBox.information(self, tr("busy_title"), tr("busy_msg"))
            event.ignore()
            return

        self.movie_tab.cleanup_before_close()
        self.series_tab.cleanup_before_close()
        event.accept()
