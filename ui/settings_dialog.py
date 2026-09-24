#!/usr/bin/env python3
"""
ui/settings_dialog.py - Dialogo Opzioni di MediaTidy.
"""
from pathlib import Path

from config import CONFIG
from localization import tr
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("opts_title"))
        self.resize(500, 400)

        layout = QFormLayout(self)

        # Chiave API TMDB
        self.api_input = QLineEdit(CONFIG["api_key"])
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(tr("tmdb_key"), self.api_input)

        help_label = QLabel(
            f'<a href="https://www.themoviedb.org/documentation/api">'
            f'{tr("tmdb_link_help")}</a>'
        )
        help_label.setOpenExternalLinks(True)
        layout.addRow("", help_label)

        # Destinazione Film
        self.dest_movies_input = QLineEdit(CONFIG["dest_movies"])
        self.dest_movies_btn = QPushButton(tr("browse"))
        self.dest_movies_btn.clicked.connect(self.browse_dest_movies)

        row_movies = QHBoxLayout()
        row_movies.addWidget(self.dest_movies_input)
        row_movies.addWidget(self.dest_movies_btn)
        layout.addRow("Destinazione Film:", row_movies)

        # Destinazione Serie TV
        self.dest_series_input = QLineEdit(CONFIG["dest_series"])
        self.dest_series_btn = QPushButton(tr("browse"))
        self.dest_series_btn.clicked.connect(self.browse_dest_series)

        row_series = QHBoxLayout()
        row_series.addWidget(self.dest_series_input)
        row_series.addWidget(self.dest_series_btn)
        layout.addRow("Destinazione Serie TV:", row_series)

        # Lingua TMDB
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["en-US", "it-IT", "es-ES", "fr-FR", "de-DE", "ja-JP"])
        self.lang_combo.setCurrentText(CONFIG["lang"])
        layout.addRow(tr("tmdb_search_lang"), self.lang_combo)

        # Capitalizzazione
        self.cap_combo = QComboBox()
        self.cap_combo.addItem(tr("cap_1"), 1)
        self.cap_combo.addItem(tr("cap_2"), 2)
        self.cap_combo.addItem(tr("cap_3"), 3)
        self.cap_combo.setCurrentIndex(CONFIG["cap_rule"] - 1)
        layout.addRow(tr("capitalization"), self.cap_combo)

        # Azione file
        self.action_combo = QComboBox()
        self.action_combo.addItem(tr("move"), "move")
        self.action_combo.addItem(tr("copy"), "copy")

        idx = self.action_combo.findData(CONFIG["action"])
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)
        layout.addRow(tr("file_action"), self.action_combo)

        # Checkbox
        self.unmount_chk = QCheckBox(tr("unmount_chk"))
        self.unmount_chk.setChecked(CONFIG["unmount"])
        layout.addRow("", self.unmount_chk)

        self.clean_dir_chk = QCheckBox(tr("clean_dir_chk"))
        self.clean_dir_chk.setChecked(CONFIG["clean_parent_dir"])
        layout.addRow("", self.clean_dir_chk)

        # Lingua interfaccia
        self.gui_lang_combo = QComboBox()
        self.gui_lang_combo.addItem("Italiano", "it")
        self.gui_lang_combo.addItem("English", "en")

        idx = self.gui_lang_combo.findData(CONFIG["gui_lang"])
        if idx >= 0:
            self.gui_lang_combo.setCurrentIndex(idx)
        layout.addRow(tr("gui_lang_label"), self.gui_lang_combo)

        # Percorso log e CSV
        default_logs_dir = str(
            Path.home() / ".local" / "share" / "MediaTidy" / "logs"
        )

        self.logs_dir_edit = QLineEdit(
            CONFIG.get("logs_dir", default_logs_dir)
        )
        self.logs_dir_edit.setPlaceholderText(default_logs_dir)

        self.logs_dir_button = QPushButton("Sfoglia…")
        self.logs_dir_button.clicked.connect(self.choose_logs_directory)

        logs_row = QHBoxLayout()
        logs_row.addWidget(self.logs_dir_edit)
        logs_row.addWidget(self.logs_dir_button)
        layout.addRow("Cartella log:", logs_row)

        # Pulsanti OK/Annulla
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow("", buttons)

    def choose_logs_directory(self):
        default_dir = str(
            Path.home() / ".local" / "share" / "MediaTidy" / "logs"
        )
        start_dir = self.logs_dir_edit.text().strip() or default_dir

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Scegli la cartella dei log",
            start_dir,
            QFileDialog.ShowDirsOnly,
        )

        if selected_dir:
            self.logs_dir_edit.setText(selected_dir)

    def browse_dest_movies(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Destinazione Film",
        )
        if directory:
            self.dest_movies_input.setText(directory)

    def browse_dest_series(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Destinazione Serie TV",
        )
        if directory:
            self.dest_series_input.setText(directory)

    def accept(self):
        CONFIG["api_key"] = self.api_input.text().strip()
        CONFIG["dest_movies"] = self.dest_movies_input.text().strip()
        CONFIG["dest_series"] = self.dest_series_input.text().strip()
        CONFIG["lang"] = self.lang_combo.currentText()
        CONFIG["cap_rule"] = self.cap_combo.currentData()
        CONFIG["action"] = self.action_combo.currentData()
        CONFIG["unmount"] = self.unmount_chk.isChecked()
        CONFIG["clean_parent_dir"] = self.clean_dir_chk.isChecked()
        CONFIG["gui_lang"] = self.gui_lang_combo.currentData()

        default_logs_dir = str(
            Path.home() / ".local" / "share" / "MediaTidy" / "logs"
        )
        logs_dir = self.logs_dir_edit.text().strip() or default_logs_dir
        CONFIG["logs_dir"] = str(Path(logs_dir).expanduser())

        super().accept()
