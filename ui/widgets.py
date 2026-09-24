#!/usr/bin/env python3
"""
ui/widgets.py - Widget e dialoghi condivisi da scheda Film e scheda Serie TV:
tabella con drag&drop, dialogo duplicati, dialogo "cartella non vuota",
Opzioni, Crediti & Privacy.
"""
from config import CONFIG, VERSION
from localization import tr

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QPainter
from qtpy.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTabWidget, QTextBrowser, QVBoxLayout, QWidget, QAbstractItemView,
)

# Compatibilità per costanti Qt tra PyQt5, PyQt6 e PySide
try:
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    ROLE_USER = Qt.ItemDataRole.UserRole
    ITEM_ENABLED = Qt.ItemFlag.ItemIsEnabled
    ITEM_SELECTABLE = Qt.ItemFlag.ItemIsSelectable
    ECHO_PASSWORD = QLineEdit.EchoMode.Password
    DROP_ONLY = QAbstractItemView.DragDropMode.DropOnly
    SELECT_ROWS = QAbstractItemView.SelectionBehavior.SelectRows
    EXTENDED_SELECTION = QAbstractItemView.SelectionMode.ExtendedSelection
    ELIDE_RIGHT = Qt.TextElideMode.ElideRight
except AttributeError:
    ALIGN_CENTER = Qt.AlignCenter
    ROLE_USER = Qt.UserRole
    ITEM_ENABLED = Qt.ItemIsEnabled
    ITEM_SELECTABLE = Qt.ItemIsSelectable
    ECHO_PASSWORD = QLineEdit.Password
    DROP_ONLY = QAbstractItemView.DropOnly
    SELECT_ROWS = QAbstractItemView.SelectRows
    EXTENDED_SELECTION = QAbstractItemView.ExtendedSelection
    ELIDE_RIGHT = Qt.ElideRight


class ToggleableListWidget(QTableWidget):
    """Tabella con drag&drop e deselezione con un clic su una riga già selezionata.
    Generica: la scheda Film e la scheda Serie TV la usano con colonne diverse."""
    files_dropped = Signal(list)

    def __init__(self, headers, stretch_cols=(0, 1, 2)):
        super().__init__(0, len(headers))
        self._headers_keys = headers
        self.setTextElideMode(ELIDE_RIGHT)
        self.setAcceptDrops(True)
        self.setDragDropMode(DROP_ONLY)
        self.setSelectionBehavior(SELECT_ROWS)
        self.setSelectionMode(EXTENDED_SELECTION)
        self.setWordWrap(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setStyleSheet("""
            QHeaderView::section {
                font-weight: bold;
                font-size: 13px;
                background-color: #e2e2e2;
                padding: 6px;
                border: 1px solid #c0c0c0;
            }
            QTableWidget::item {
                font-weight: normal;
                font-size: 13px;
                padding: 4px;
            }
        """)

        h = self.horizontalHeader()
        for c in range(len(headers)):
            h.setSectionResizeMode(c, QHeaderView.Stretch if c in stretch_cols else QHeaderView.ResizeToContents)

        self.update_headers()

    def update_headers(self):
        self.setHorizontalHeaderLabels([tr(k) for k in self._headers_keys])

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        from qtpy.QtWidgets import QApplication
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        e.acceptProposedAction()
        self.files_dropped.emit(paths)

    def mousePressEvent(self, event):
        from qtpy.QtWidgets import QApplication
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.clearSelection()
            super().mousePressEvent(event)
            return
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.NoModifier:
            selected_rows = {i.row() for i in self.selectedIndexes()}
            if len(selected_rows) == 1 and index.row() in selected_rows:
                self.clearSelection()
                return
        super().mousePressEvent(event)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.rowCount() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(128, 128, 128))
            f = p.font()
            f.setBold(False)
            p.setFont(f)
            p.drawText(self.viewport().rect(), ALIGN_CENTER, tr("drag_drop"))
            
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            rows = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
            for r in rows:
                self.removeRow(r)
            event.accept()
            return
        super().keyPressEvent(event)


class DuplicateDialog(QDialog):
    def __init__(self, folder, filename, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dup_title"))
        self.resize(560, 260)
        self.choice = "skip"
        self.apply_to_all = False

        lay = QVBoxLayout(self)
        msg = tr("dup_msg", folder=folder, file=filename)
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        btn_layout = QVBoxLayout()
        self.btn_overwrite = QPushButton(tr("dup_opt1"))
        self.btn_suffix = QPushButton(tr("dup_opt2"))
        self.btn_custom = QPushButton(tr("dup_opt3"))
        self.btn_skip = QPushButton(tr("dup_opt4"))

        self.btn_overwrite.clicked.connect(lambda: self._select("overwrite"))
        self.btn_suffix.clicked.connect(lambda: self._select("suffix"))
        self.btn_custom.clicked.connect(lambda: self._select("custom"))
        self.btn_skip.clicked.connect(lambda: self._select("skip"))

        btn_layout.addWidget(self.btn_overwrite)
        btn_layout.addWidget(self.btn_suffix)
        btn_layout.addWidget(self.btn_custom)
        btn_layout.addWidget(self.btn_skip)
        lay.addLayout(btn_layout)

        self.chk_all = QCheckBox(tr("dup_apply_all"))
        lay.addWidget(self.chk_all)

    def _select(self, choice):
        self.choice = choice
        self.apply_to_all = self.chk_all.isChecked()
        self.accept()


class NonEmptyDirDialog(QDialog):
    def __init__(self, dir_path, size_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("non_empty_dir_title"))
        self.resize(520, 220)
        self.choice = "no"
        self.apply_to_all = False

        lay = QVBoxLayout(self)
        msg = tr("non_empty_dir_msg", folder=dir_path, size=size_str)
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        btn_layout = QHBoxLayout()
        self.btn_yes = QPushButton(tr("btn_yes"))
        self.btn_yes_all = QPushButton(tr("btn_yes_to_all"))
        self.btn_no = QPushButton(tr("btn_no"))

        self.btn_yes.clicked.connect(lambda: self._select("yes", False))
        self.btn_yes_all.clicked.connect(lambda: self._select("yes", True))
        self.btn_no.clicked.connect(lambda: self._select("no", False))

        btn_layout.addWidget(self.btn_yes)
        btn_layout.addWidget(self.btn_yes_all)
        btn_layout.addWidget(self.btn_no)
        lay.addLayout(btn_layout)

    def _select(self, choice, apply_all):
        self.choice = choice
        self.apply_to_all = apply_all
        self.accept()


class CreditsPrivacyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MediaTidy — Crediti & Privacy Policy")
        self.resize(600, 450)

        lay = QVBoxLayout(self)
        tabs = QTabWidget()

        tab_credits = QWidget()
        l_cred = QVBoxLayout(tab_credits)
        credits_html = f"""
        <h2>MediaTidy v{VERSION}</h2>
        <p><b>Autore e Sviluppatore:</b> Michele Shuren Bancheri</p>
        <p><b>Ringraziamenti speciali:</b><br>
        Un ringraziamento particolare a mia moglie, la scrittrice <b>Keyla Damaer</b><br>
        (<a href="https://keyladamaer.com/">https://keyladamaer.com/</a>).</p>
        <hr>
        <p><b>Librerie e Tecnologie:</b><br>
        - Python & QtPy (PyQt/PySide)<br>
        - API ufficiali di TMDB (The Movie Database)</p>
        <p><b>Licenza:</b> MIT License</p>
        """
        browser_cred = QTextBrowser()
        browser_cred.setOpenExternalLinks(True)
        browser_cred.setHtml(credits_html)
        l_cred.addWidget(browser_cred)
        tabs.addTab(tab_credits, "Crediti")

        tab_privacy = QWidget()
        l_priv = QVBoxLayout(tab_privacy)
        privacy_html = """
        <h3>Informativa sulla Privacy</h3>
        <p><b>MediaTidy</b> rispetta la tua privacy e i tuoi dati personali:</p>
        <ul>
            <li><b>Nessuna raccolta dati:</b> Il software non raccoglie, memorizza o invia alcun dato personale o file a server di terze parti.</li>
            <li><b>Utilizzo API TMDB:</b> L'unica connessione di rete effettuata dall'applicazione avviene verso le API ufficiali di <b>TMDB (The Movie Database)</b> esclusivamente per interrogare e scaricare i metadati (film e serie TV) e i poster relativi ai file video selezionati dall'utente.</li>
            <li><b>Chiave API:</b> La chiave API inserita dall'utente viene memorizzata esclusivamente in locale tramite il sistema di configurazione nativo.</li>
        </ul>
        """
        browser_priv = QTextBrowser()
        browser_priv.setOpenExternalLinks(True)
        browser_priv.setHtml(privacy_html)
        l_priv.addWidget(browser_priv)
        tabs.addTab(tab_privacy, "Privacy Policy")

        lay.addWidget(tabs)

        btn_close = QPushButton(tr("ok"))
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close)


class SettingsDialog(QDialog):
    """Opzioni condivise da entrambe le schede (chiave API, destinazione, lingua
    TMDB, capitalizzazione, smontaggio automatico, pulizia cartelle di origine)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("opts_title"))
        self.resize(540, 350)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.gui_lang_combo = QComboBox()
        self.gui_lang_combo.addItem("Italiano", "it")
        self.gui_lang_combo.addItem("English", "en")
        idx_g = self.gui_lang_combo.findData(CONFIG.get("gui_lang", "it"))
        if idx_g != -1:
            self.gui_lang_combo.setCurrentIndex(idx_g)

        self.api_key = QLineEdit(CONFIG["api_key"])
        self.api_key.setEchoMode(ECHO_PASSWORD)

        self.lbl_tmdb_help = QLabel(tr("tmdb_link_help"))
        self.lbl_tmdb_help.setOpenExternalLinks(True)

        self.dest = QLineEdit(CONFIG["dest"])
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(self.dest)
        browse_btn = QPushButton(tr("browse"))
        browse_btn.clicked.connect(self._browse)
        dest_layout.addWidget(browse_btn)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["en-US", "it-IT", "es-ES", "fr-FR", "de-DE", "ja-JP"])
        self.lang_combo.setCurrentText(CONFIG.get("lang", "en-US"))

        self.cap_combo = QComboBox()
        self.cap_combo.addItem(tr("cap_1"), 1)
        self.cap_combo.addItem(tr("cap_2"), 2)
        self.cap_combo.addItem(tr("cap_3"), 3)
        idx = self.cap_combo.findData(CONFIG.get("cap_rule", 2))
        if idx != -1:
            self.cap_combo.setCurrentIndex(idx)

        self.chk_unmount = QCheckBox(tr("unmount_chk"))
        self.chk_unmount.setChecked(CONFIG.get("unmount", True))

        self.chk_clean_dir = QCheckBox(tr("clean_dir_chk"))
        self.chk_clean_dir.setChecked(CONFIG.get("clean_parent_dir", False))
        if CONFIG.get("action", "move") == "copy":
            self.chk_clean_dir.setEnabled(False)

        form.addRow(tr("gui_lang_label"), self.gui_lang_combo)
        form.addRow(tr("tmdb_key"), self.api_key)
        form.addRow("", self.lbl_tmdb_help)
        form.addRow(tr("dest_folder"), dest_layout)
        form.addRow(tr("tmdb_search_lang"), self.lang_combo)
        form.addRow(tr("capitalization"), self.cap_combo)
        form.addRow("", self.chk_unmount)
        form.addRow("", self.chk_clean_dir)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("dest_folder"), self.dest.text())
        if d:
            self.dest.setText(d)

    def _save(self):
        CONFIG["gui_lang"] = self.gui_lang_combo.currentData()
        CONFIG["api_key"] = self.api_key.text().strip()
        CONFIG["dest"] = self.dest.text().strip()
        CONFIG["lang"] = self.lang_combo.currentText()
        CONFIG["cap_rule"] = self.cap_combo.currentData()
        CONFIG["unmount"] = self.chk_unmount.isChecked()
        CONFIG["clean_parent_dir"] = self.chk_clean_dir.isChecked()
        self.accept()
