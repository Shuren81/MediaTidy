#!/usr/bin/env python3
"""
ui/settings_dialog.py - Dialogo Opzioni di MediaTidy: impostazioni GLOBALI, condivise
da entrambe le schede (chiave API, lingua di ricerca TMDB, capitalizzazione, smontaggio
automatico, pulizia cartelle di origine, lingua interfaccia, cartella log).

Destinazione, azione Sposta/Copia e formato del nome/cartella sono per scheda e si
trovano invece nel dialogo Formato Nomi (ui/format_dialog.py).
"""
from pathlib import Path

from config import CONFIG, DEFAULT_LOGS_DIR
from localization import tr

from qtpy.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("opts_title"))
        self.resize(500, 380)

        layout = QFormLayout(self)

        # Chiave API TMDB
        self.api_input = QLineEdit(CONFIG["api_key"])
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(tr("tmdb_key"), self.api_input)

        help_label = QLabel(
            f'<a href="https://www.themoviedb.org/documentation/api">{tr("tmdb_link_help")}</a>'
        )
        help_label.setOpenExternalLinks(True)
        layout.addRow("", help_label)

        # Lingua TMDB (di ricerca)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["en-US", "it-IT", "es-ES", "fr-FR", "de-DE", "ja-JP"])
        self.lang_combo.setCurrentText(CONFIG["lang"])
        layout.addRow(tr("tmdb_search_lang"), self.lang_combo)

        # Capitalizzazione (condivisa: vale per Film e Serie TV)
        self.cap_combo = QComboBox()
        self.cap_combo.addItem(tr("cap_1"), 1)
        self.cap_combo.addItem(tr("cap_2"), 2)
        self.cap_combo.addItem(tr("cap_3"), 3)
        idx = self.cap_combo.findData(CONFIG.get("cap_rule", 2))
        self.cap_combo.setCurrentIndex(idx if idx != -1 else 1)
        layout.addRow(tr("capitalization"), self.cap_combo)

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
        self.logs_dir_edit = QLineEdit(CONFIG.get("logs_dir", DEFAULT_LOGS_DIR))
        self.logs_dir_edit.setPlaceholderText(DEFAULT_LOGS_DIR)
        self.logs_dir_button = QPushButton(tr("browse"))
        self.logs_dir_button.clicked.connect(self.choose_logs_directory)

        logs_row = QHBoxLayout()
        logs_row.addWidget(self.logs_dir_edit)
        logs_row.addWidget(self.logs_dir_button)
        layout.addRow(tr("logs_dir_label"), logs_row)

        # Pulsanti OK/Annulla
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow("", buttons)

    def choose_logs_directory(self):
        start_dir = self.logs_dir_edit.text().strip() or DEFAULT_LOGS_DIR
        selected_dir = QFileDialog.getExistingDirectory(
            self, tr("logs_dir_label"), start_dir, QFileDialog.ShowDirsOnly,
        )
        if selected_dir:
            self.logs_dir_edit.setText(selected_dir)

    def accept(self):
        CONFIG["api_key"] = self.api_input.text().strip()
        CONFIG["lang"] = self.lang_combo.currentText()
        CONFIG["cap_rule"] = self.cap_combo.currentData()
        CONFIG["unmount"] = self.unmount_chk.isChecked()
        CONFIG["clean_parent_dir"] = self.clean_dir_chk.isChecked()
        CONFIG["gui_lang"] = self.gui_lang_combo.currentData()
        CONFIG["logs_dir"] = str(Path(self.logs_dir_edit.text().strip() or DEFAULT_LOGS_DIR).expanduser())
        super().accept()
