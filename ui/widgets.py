#!/usr/bin/env python3
"""
ui/widgets.py - Widget e dialoghi condivisi da scheda Film e scheda Serie TV:
tabella con drag&drop (Canc/Backspace + Ctrl+A, click per deselezionare),
dialogo duplicati, dialogo "cartella non vuota", Crediti & Privacy.
Le Opzioni (ui/settings_dialog.py) e il Formato Nomi (ui/format_dialog.py)
sono in moduli propri.
"""
from config import VERSION
from localization import tr

from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QColor, QKeySequence, QPainter
from qtpy.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTabWidget, QTextBrowser, QVBoxLayout, QWidget, QAbstractItemView,
)

# Colori del feedback di trascinamento, condivisi da tabelle e finestra principale.
DRAG_ACTIVE_COLOR = QColor(230, 180, 0)   # giallo: si sta trascinando sopra l'area
DRAG_SUCCESS_COLOR = QColor(0, 150, 0)    # verde: il rilascio ha importato qualcosa
DRAG_FAILURE_COLOR = QColor(200, 0, 0)    # rosso: il rilascio non ha importato nulla
DRAG_FLASH_MS = 500  # durata del lampeggio verde/rosso sulle tabelle

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
    delete_requested = Signal()  # Canc/Backspace: la tab decide come rimuovere (items + righe insieme)
    drag_state_changed = Signal(bool)  # True=trascinamento in corso sopra la tabella, False=uscito/rilasciato

    def __init__(self, headers, stretch_cols=(0, 1, 2)):
        super().__init__(0, len(headers))
        self._headers_keys = headers
        self._drag_active = False
        self._flash_color = None
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)
        self.setTextElideMode(ELIDE_RIGHT)
        self.setAcceptDrops(True)
        self.setDragDropMode(DROP_ONLY)
        self.setSelectionBehavior(SELECT_ROWS)
        self.setSelectionMode(EXTENDED_SELECTION)
        self.setWordWrap(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._base_style = """
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
        """
        self._apply_border()

        h = self.horizontalHeader()
        for c in range(len(headers)):
            h.setSectionResizeMode(c, QHeaderView.Stretch if c in stretch_cols else QHeaderView.ResizeToContents)

        self.update_headers()

    def update_headers(self):
        self.setHorizontalHeaderLabels([tr(k) for k in self._headers_keys])

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_active = True
            self._apply_border()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dragLeaveEvent(self, e):
        self._drag_active = False
        self._apply_border()
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        e.acceptProposedAction()
        self._drag_active = False
        self._apply_border()
        if paths:
            self.files_dropped.emit(paths)

    def flash_success(self):
        self._start_flash(DRAG_SUCCESS_COLOR)

    def flash_failure(self):
        self._start_flash(DRAG_FAILURE_COLOR)

    def _start_flash(self, color):
        self._flash_color = color
        self._apply_border()
        self._flash_timer.start(DRAG_FLASH_MS)

    def _clear_flash(self):
        self._flash_color = None
        self._apply_border()

    def _apply_border(self):
        color = DRAG_ACTIVE_COLOR if self._drag_active else self._flash_color
        border_css = f"QTableWidget {{ border: 3px solid {color.name()}; }}" if color else ""
        self.setStyleSheet(self._base_style + border_css)

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
            # Un clic semplice su QUALSIASI riga già selezionata deselezionaa tutto
            # (non solo quando è selezionata una riga sola): utile anche a tabella
            # piena, dove non c'è spazio vuoto su cui cliccare per deselezionare.
            if selected_rows and index.row() in selected_rows:
                self.clearSelection()
                # Molti stili (incluso quello tipico di Linux Mint) confermano la
                # selezione al RILASCIO del tasto, non alla pressione: senza questo,
                # Qt riselezionerebbe la riga un istante dopo, vanificando il clear.
                self._suppress_next_release = True
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "_suppress_next_release", False):
            self._suppress_next_release = False
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.rowCount() == 0 and not self._drag_active and not self._flash_color:
            p = QPainter(self.viewport())
            p.setPen(QColor(128, 128, 128))
            f = p.font()
            f.setBold(False)
            p.setFont(f)
            p.drawText(self.viewport().rect(), ALIGN_CENTER, tr("drag_drop"))
            p.end()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # NON tocca le righe direttamente: emette solo il segnale, così la tab
            # rimuove insieme la riga in tabella E l'item corrispondente in self.items
            # (rimuoverle solo qui le farebbe disallineare — vedi remove_selected nelle tab).
            if self.selectedIndexes():
                self.delete_requested.emit()
            event.accept()
            return
        if event.matches(QKeySequence.SelectAll):
            self.selectAll()
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

