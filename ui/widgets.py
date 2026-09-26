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
from media_operations import format_duration, format_size, is_remote

from pathlib import Path

from qtpy.QtCore import QUrl, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QDesktopServices, QKeySequence, QPainter
from qtpy.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)


def _open_folder(path):
    """Apre una cartella locale nel file manager di sistema (nessun effetto se
    il percorso non esiste o siamo su una destinazione remota — non chiamarla in quel caso)."""
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

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
            self.drag_state_changed.emit(True)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dragLeaveEvent(self, e):
        self._drag_active = False
        self._apply_border()
        self.drag_state_changed.emit(False)
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        e.acceptProposedAction()
        self._drag_active = False
        self._apply_border()
        self.drag_state_changed.emit(False)
        if paths:
            self.files_dropped.emit(paths)

    def flash_success(self):
        """Lampeggio verde breve: il rilascio ha importato qualcosa (qui o nell'altra scheda)."""
        self._start_flash(DRAG_SUCCESS_COLOR)

    def flash_failure(self):
        """Lampeggio rosso breve: il rilascio non ha portato nulla di utile."""
        self._start_flash(DRAG_FAILURE_COLOR)

    def _start_flash(self, color):
        self._flash_color = color
        self._apply_border()
        self._flash_timer.start(DRAG_FLASH_MS)

    def _clear_flash(self):
        self._flash_color = None
        self._apply_border()

    def _apply_border(self):
        """Bordo colorato via foglio di stile (mai un QPainter diretto su self: QTableWidget
        eredita da QAbstractScrollArea, che espone solo il viewport() come vera superficie di
        disegno — dipingere su self genera gli avvisi 'Paint device returned engine == 0')."""
        color = DRAG_ACTIVE_COLOR if self._drag_active else self._flash_color
        border_css = f"QTableWidget {{ border: 3px solid {color.name()}; }}" if color else ""
        self.setStyleSheet(self._base_style + border_css)

    def invert_selection(self):
        """Seleziona tutte le righe NON selezionate, deseleziona quelle che lo erano."""
        from qtpy.QtWidgets import QTableWidgetSelectionRange
        selected_rows = {i.row() for i in self.selectedIndexes()}
        self.clearSelection()
        if self.columnCount() == 0:
            return
        for r in range(self.rowCount()):
            if r not in selected_rows:
                self.setRangeSelected(QTableWidgetSelectionRange(r, 0, r, self.columnCount() - 1), True)

    def _invert_selection(self):
        self.invert_selection()

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
        if event.key() == Qt.Key_I and event.modifiers() == Qt.ControlModifier:
            self._invert_selection()
            event.accept()
            return
        super().keyPressEvent(event)


class DuplicateDialog(QDialog):
    def __init__(self, folder, filename, dest=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dup_title"))
        self.resize(560, 300)
        self.choice = "skip"
        self.apply_to_all = False

        lay = QVBoxLayout(self)
        msg = tr("dup_msg", folder=folder, file=filename)
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        if dest and not is_remote(dest):
            btn_open = QPushButton(tr("btn_open_folder"))
            btn_open.clicked.connect(lambda: _open_folder(Path(dest) / folder))
            lay.addWidget(btn_open)

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

        btn_open = QPushButton(tr("btn_open_folder"))
        btn_open.clicked.connect(lambda: _open_folder(dir_path))
        lay.addWidget(btn_open)

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


class BatchDetailsDialog(QDialog):
    """Tabella con i file saltati/in errore di un batch Esegui: nome, stato,
    messaggio. Copia riga singola o intero report, sia da bottone sia dal
    menu contestuale (tasto destro)."""
    def __init__(self, details, parent=None):
        super().__init__(parent)
        self.details = details
        self.setWindowTitle(tr("batch_details_title"))
        self.resize(720, 420)

        lay = QVBoxLayout(self)

        self.table = QTableWidget(len(details), 3)
        self.table.setHorizontalHeaderLabels(
            [tr("batch_col_name"), tr("batch_col_status"), tr("batch_col_message")]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for i, d in enumerate(details):
            self.table.setItem(i, 0, QTableWidgetItem(d["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(d["status"]))
            self.table.setItem(i, 2, QTableWidgetItem(d["message"]))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        lay.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_copy_row = QPushButton(tr("batch_copy_row"))
        self.btn_copy_row.clicked.connect(self._copy_selected_rows)
        self.btn_copy_all = QPushButton(tr("batch_copy_all"))
        self.btn_copy_all.clicked.connect(self._copy_all)
        btn_row.addWidget(self.btn_copy_row)
        btn_row.addWidget(self.btn_copy_all)
        btn_row.addStretch(1)
        btn_close = QPushButton(tr("ok"))
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

    def _row_text(self, r):
        return " | ".join(self.table.item(r, c).text() for c in range(self.table.columnCount()))

    def _copy_selected_rows(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            return
        QApplication.clipboard().setText("\n".join(self._row_text(r) for r in rows))

    def _copy_all(self):
        QApplication.clipboard().setText("\n".join(self._row_text(r) for r in range(self.table.rowCount())))

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        menu = QMenu(self)
        act_copy_row = menu.addAction(tr("batch_copy_row"))
        act_copy_all = menu.addAction(tr("batch_copy_all"))
        exec_func = getattr(menu, "exec_", None) or getattr(menu, "exec")
        action = exec_func(self.table.viewport().mapToGlobal(pos))
        if action == act_copy_row:
            if row >= 0:
                self.table.selectRow(row)
            self._copy_selected_rows()
        elif action == act_copy_all:
            self._copy_all()


class BatchSummaryDialog(QDialog):
    """Riepilogo di fine batch (solo dopo Esegui, mai dopo Test): quanti file
    spostati/copiati, dimensione totale, tempo impiegato, quanti saltati e
    quanti in errore. "Vedi dettagli" apre BatchDetailsDialog con l'elenco
    di tutto ciò che NON è stato spostato/copiato con successo."""
    def __init__(self, succeeded, total_bytes, elapsed, skipped, errors, details, parent=None):
        super().__init__(parent)
        self.details = details
        self.setWindowTitle(tr("batch_summary_title"))
        self.resize(460, 160)

        lay = QVBoxLayout(self)
        msg = tr("batch_summary_msg", succeeded=succeeded, size=format_size(total_bytes),
                 elapsed=format_duration(elapsed), skipped=skipped, errors=errors)
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if details:
            btn_details = QPushButton(tr("batch_view_details"))
            btn_details.clicked.connect(self._show_details)
            btn_row.addWidget(btn_details)
        btn_ok = QPushButton(tr("ok"))
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

    def _show_details(self):
        dlg = BatchDetailsDialog(self.details, self)
        dlg.exec_()
