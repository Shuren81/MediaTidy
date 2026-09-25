#!/usr/bin/env python3
"""
ui/format_dialog.py - Dialogo "Formato Nomi": destinazione, modalità titolo e
toggle di formato — indipendenti per Film e per Serie TV. L'azione Sposta/Copia
non è più qui: resta solo il radio button di ciascuna scheda (unico punto dove
si imposta, più comodo da raggiungere durante il lavoro quotidiano).
"""
from config import CONFIG
from localization import tr

from qtpy.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

TITLE_MODE_KEYS = ("original", "localized", "orig_loc", "loc_orig")
TITLE_MODE_LABELS = ("title_mode_original", "title_mode_localized", "title_mode_orig_loc", "title_mode_loc_orig")


class _FormatTab(QWidget):
    """Una scheda (Film o Serie) del dialogo Formato Nomi: destinazione e titolo
    in comune + una lista di checkbox specifici passata da fuori."""

    def __init__(self, dest_label, dest_value, checkbox_specs, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.dest = QLineEdit(dest_value)
        browse_btn = QPushButton(tr("browse"))
        browse_btn.clicked.connect(self._browse)
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.dest)
        dest_row.addWidget(browse_btn)
        layout.addRow(dest_label, dest_row)

        self.title_combo = QComboBox()
        for key, label_key in zip(TITLE_MODE_KEYS, TITLE_MODE_LABELS):
            self.title_combo.addItem(tr(label_key), key)
        layout.addRow(tr("title_mode_label"), self.title_combo)

        # checkbox_specs: lista di (config_key, label_key, note_key_o_None)
        self._checkboxes = {}
        for config_key, label_key, note_key in checkbox_specs:
            chk = QCheckBox(tr(label_key))
            chk.setChecked(CONFIG.get(config_key, True))
            self._checkboxes[config_key] = chk
            layout.addRow("", chk)
            if note_key:
                note = QLabel(tr(note_key))
                note.setWordWrap(True)
                note.setStyleSheet("color: #888; font-size: 11px; margin-left: 4px;")
                layout.addRow("", note)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("browse"), self.dest.text())
        if d:
            self.dest.setText(d)

    def set_title_mode(self, mode):
        idx = self.title_combo.findData(mode)
        self.title_combo.setCurrentIndex(idx if idx != -1 else 2)

    def title_mode(self):
        return self.title_combo.currentData()

    def checkbox(self, config_key):
        return self._checkboxes[config_key].isChecked()


class FormatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("format_title"))
        self.resize(560, 380)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        self.movie_tab = _FormatTab(
            tr("dest_movies_label"), CONFIG["dest_movies"],
            [
                ("movie_include_tmdb_id", "movie_include_tmdb_id", "movie_tmdb_id_note"),
                ("movie_include_country", "movie_include_country", None),
                ("movie_include_director", "movie_include_director", None),
                ("movie_download_poster", "movie_download_poster", None),
            ],
        )
        self.movie_tab.set_title_mode(CONFIG["movie_title_mode"])
        tabs.addTab(self.movie_tab, tr("format_tab_movies"))

        self.series_tab = _FormatTab(
            tr("dest_series_label"), CONFIG["dest_series"],
            [
                ("series_include_tmdb_id", "series_include_tmdb_id", "series_tmdb_id_note"),
                ("series_include_country", "series_include_country", None),
                ("series_include_episode_title", "series_include_episode_title", None),
                ("series_download_show_poster", "series_download_show_poster", None),
                ("series_download_season_poster", "series_download_season_poster", None),
            ],
        )
        self.series_tab.set_title_mode(CONFIG["series_title_mode"])
        tabs.addTab(self.series_tab, tr("format_tab_series"))

        layout.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def accept(self):
        CONFIG["dest_movies"] = self.movie_tab.dest.text().strip()
        CONFIG["movie_title_mode"] = self.movie_tab.title_mode()
        CONFIG["movie_include_tmdb_id"] = self.movie_tab.checkbox("movie_include_tmdb_id")
        CONFIG["movie_include_country"] = self.movie_tab.checkbox("movie_include_country")
        CONFIG["movie_include_director"] = self.movie_tab.checkbox("movie_include_director")
        CONFIG["movie_download_poster"] = self.movie_tab.checkbox("movie_download_poster")

        CONFIG["dest_series"] = self.series_tab.dest.text().strip()
        CONFIG["series_title_mode"] = self.series_tab.title_mode()
        CONFIG["series_include_tmdb_id"] = self.series_tab.checkbox("series_include_tmdb_id")
        CONFIG["series_include_country"] = self.series_tab.checkbox("series_include_country")
        CONFIG["series_include_episode_title"] = self.series_tab.checkbox("series_include_episode_title")
        CONFIG["series_download_show_poster"] = self.series_tab.checkbox("series_download_show_poster")
        CONFIG["series_download_season_poster"] = self.series_tab.checkbox("series_download_season_poster")
        super().accept()
