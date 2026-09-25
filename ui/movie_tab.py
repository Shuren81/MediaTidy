#!/usr/bin/env python3
"""
ui/movie_tab.py - Scheda "Film": tabella con drag&drop, Test/Esegui (selezionati/
tutti), dialogo di conferma TMDB, menu contestuale (modifica personalizzata, codice
TMDB, lingua), duplicati e cartelle non vuote. Usa core/movie_handler.py per la logica.
"""
from pathlib import Path

from config import CONFIG
from localization import tr
from media_operations import VIDEO_EXT, play_system_sound, send_mint_notification
from text_utils import sanitize_title
from tmdb_client import search_movie
from core.movie_handler import (
    DONE_KEYS, ERROR_KEYS, MovieWorker, READY_KEYS, SKIP_KEYS, find_videos,
    is_done, is_ready, set_status, status_text,
)
from ui.widgets import (
    ALIGN_CENTER, ITEM_ENABLED, ITEM_SELECTABLE, ROLE_USER, DuplicateDialog,
    NonEmptyDirDialog, ToggleableListWidget,
)

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QCursor
from qtpy.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QProgressBar, QPushButton, QRadioButton, QTableWidgetItem, QVBoxLayout, QWidget,
)

# Colonne su cui il doppio click apre "Modifica personalizzata" (nome + cartella)
CUSTOM_EDIT_COLS = (1, 2)


class ChoiceDialog(QDialog):
    """Conferma/ricerca manuale del film quando TMDB non trova un risultato certo."""
    def __init__(self, guessed, results, parent=None, lang=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("movie_choice_title"))
        self.resize(680, 440)
        lay = QVBoxLayout(self)
        msg = (tr("movie_no_res") if not results else tr("movie_uncertain")) + tr("movie_choice_msg", guessed=guessed)
        lay.addWidget(QLabel(msg))

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        lay.addWidget(self.list)

        row = QHBoxLayout()
        self.query = QLineEdit(guessed)
        self.query.returnPressed.connect(self._search)
        btn = QPushButton(tr("search_btn"))
        btn.clicked.connect(self._search)
        row.addWidget(self.query)
        row.addWidget(btn)
        lay.addLayout(row)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(tr("ok"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(tr("skip_file"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self._fill(results)

    def _fill(self, results):
        self.list.clear()
        for m in results:
            year = (m.get("release_date") or "????")[:4]
            overview = (m.get("overview") or "").strip()
            if len(overview) > 140:
                overview = overview[:140] + "…"
            text = f"{m.get('title')} ({year}) — original: {m.get('original_title')}"
            if overview:
                text += f"\n    {overview}"
            item = QListWidgetItem(text)
            item.setData(ROLE_USER, m)
            self.list.addItem(item)
        if results:
            self.list.setCurrentRow(0)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(results))

    def _search(self):
        q = self.query.text().strip()
        if not q:
            return
        try:
            self._fill(search_movie(q, None, lang=self.lang, limit=8))
        except Exception as e:
            QMessageBox.warning(self, tr("error_title"), f"Search failed: {e}")

    def selected(self):
        item = self.list.currentItem()
        return item.data(ROLE_USER) if item else None


MOVIE_HEADERS = ["movie_col_orig", "movie_col_new", "movie_col_dest", "movie_col_tmdb", "movie_col_status"]


class MovieTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.worker = None
        self.mounted_by_us = None

        self.lay = QVBoxLayout(self)

        self.top_bar = QHBoxLayout()
        self.lbl_action = QLabel()
        self.top_bar.addWidget(self.lbl_action)
        self.radio_move = QRadioButton()
        self.radio_copy = QRadioButton()
        self._set_radio_from_config()
        self.radio_move.toggled.connect(self._update_action_mode)
        self.top_bar.addWidget(self.radio_move)
        self.top_bar.addWidget(self.radio_copy)
        self.top_bar.addStretch(1)
        self.lay.addLayout(self.top_bar)

        self.table = ToggleableListWidget(MOVIE_HEADERS, stretch_cols=(0, 1, 2))
        # Il drag&drop sulla tabella passa dal triage automatico di MainWindow, non da
        # add_paths direttamente: vedi MainWindow._dispatch. add_paths resta usato solo
        # dai pulsanti "Aggiungi file/cartella" di QUESTA scheda (scelta esplicita).
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.delete_requested.connect(self.remove_selected)
        self.lay.addWidget(self.table, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.lay.addWidget(self.progress_bar)

        self.row_btns = QHBoxLayout()
        self.btn_add_files = QPushButton()
        self.btn_add_dir = QPushButton()
        self.btn_remove = QPushButton()
        self.btn_clear = QPushButton()
        self.btn_test = QPushButton()
        self.btn_exec_sel = QPushButton()
        self.btn_exec_all = QPushButton()

        self.btn_add_files.clicked.connect(self.pick_files)
        self.btn_add_dir.clicked.connect(self.pick_dir)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_test.clicked.connect(lambda: self.start("test"))
        self.btn_exec_sel.clicked.connect(lambda: self.start("action", scope="selected"))
        self.btn_exec_all.clicked.connect(lambda: self.start("action", scope="all"))

        for b in (self.btn_add_files, self.btn_add_dir, self.btn_remove, self.btn_clear):
            self.row_btns.addWidget(b)
        self.row_btns.addStretch(1)
        self.row_btns.addWidget(self.btn_test)
        self.row_btns.addWidget(self.btn_exec_sel)
        self.row_btns.addWidget(self.btn_exec_all)
        self.lay.addLayout(self.row_btns)

        self.status_callback = None  # impostato da MainWindow -> statusBar().showMessage
        self.retranslate_ui()
        self.update_buttons()

    # ------------------------------------------------------------------ #
    def _set_radio_from_config(self):
        if CONFIG.get("action_movies", "move") == "move":
            self.radio_move.setChecked(True)
        else:
            self.radio_copy.setChecked(True)

    def retranslate_ui(self):
        self.lbl_action.setText(tr("file_action"))
        self.radio_move.setText(tr("move"))
        self.radio_copy.setText(tr("copy"))
        self.btn_add_files.setText(tr("add_files"))
        self.btn_add_dir.setText(tr("add_dir"))
        self.btn_remove.setText(tr("remove_sel"))
        self.btn_clear.setText(tr("clear_all"))
        self.btn_test.setText(tr("test"))
        self.table.update_headers()
        for i in range(len(self.items)):
            self.refresh_row(i)
        self.update_buttons()

    def _show_status(self, msg):
        if self.status_callback:
            self.status_callback(msg)

    def _update_action_mode(self):
        CONFIG["action_movies"] = "move" if self.radio_move.isChecked() else "copy"
        self.update_buttons()

    def config_changed(self):
        """Chiamato da MainWindow dopo che Opzioni o Formato Nomi sono stati salvati."""
        for it in self.items:
            if is_ready(it) or it.get("status") == "status_already_exists":
                set_status(it, "status_to_test")
        self.radio_move.blockSignals(True)
        self.radio_copy.blockSignals(True)
        self._set_radio_from_config()
        self.radio_move.blockSignals(False)
        self.radio_copy.blockSignals(False)
        self.retranslate_ui()

    # ------------------------------------------------------------------ #
    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Video", "",
            "Video (" + " ".join(f"*{e}" for e in sorted(VIDEO_EXT)) + ")"
        )
        if files:
            self.add_paths(files)

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr("add_dir"))
        if d:
            self.add_paths([d])

    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _action_buttons(self):
        return (self.btn_add_files, self.btn_add_dir, self.btn_remove, self.btn_clear)

    def add_paths(self, paths):
        if self._busy():
            return
        known = {it["path"] for it in self.items}
        added = 0
        for p in map(Path, paths):
            from_dir = p.is_dir()
            for f in find_videos(p):
                if f in known:
                    continue
                known.add(f)
                self.add_item(f, from_dir)
                added += 1
        if not added and paths:
            self._show_status(tr("no_video_found"))
        self.update_buttons()

    def add_item(self, path, from_dir):
        """Aggiunge un file già individuato come film (usato anche dal triage automatico)."""
        self.items.append({
            "path": path,
            "from_dir": from_dir,
            "tmdb_id": "",
            "folder": "",
            "newname": "",
            "status": "status_to_test",
            "status_detail": "",
            "poster_path": None,
            "custom_override": False,
            "force_overwrite": False,
            "lang": None,
        })
        self.table.insertRow(self.table.rowCount())
        self.refresh_row(len(self.items) - 1)

    def known_paths(self):
        return {it["path"] for it in self.items}

    def remove_selected(self):
        if self._busy():
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            del self.items[r]
            self.table.removeRow(r)
        self.update_buttons()

    def clear_all(self):
        if self._busy():
            return
        self.items.clear()
        self.table.setRowCount(0)
        self.update_buttons()

    def refresh_row(self, i):
        it = self.items[i]
        key = it.get("status", "status_to_test")
        cells = [it["path"].name, it["newname"], it["folder"], it["tmdb_id"], status_text(it)]
        self.table.blockSignals(True)
        for c, text in enumerate(cells):
            cell = QTableWidgetItem(text)
            cell.setToolTip(str(it["path"]) if c == 0 else text)
            if c != 3:
                cell.setFlags(ITEM_ENABLED | ITEM_SELECTABLE)
            if c == 4:
                if key in READY_KEYS or key in DONE_KEYS:
                    cell.setForeground(QColor(0, 140, 0))
                elif key in ERROR_KEYS or key == "status_already_exists":
                    cell.setForeground(QColor(200, 0, 0))
                elif key in SKIP_KEYS:
                    cell.setForeground(QColor(128, 128, 128))
            self.table.setItem(i, c, cell)
        self.table.blockSignals(False)

    def on_item_changed(self, item):
        row = item.row()
        col = item.column()
        if col != 3 or not (0 <= row < len(self.items)):
            return
        if self._busy():
            self.refresh_row(row)
            return
        it = self.items[row]
        val = item.text().strip()
        it["tmdb_id"] = val
        set_status(it, "status_id_tmdb" if val else "status_to_test")
        self.refresh_row(row)
        self.update_buttons()

    def on_item_double_clicked(self, item):
        row = item.row()
        if self._busy() or not (0 <= row < len(self.items)):
            return
        if item.column() in CUSTOM_EDIT_COLS:
            self._edit_custom_dialog(row)

    def show_context_menu(self, pos):
        if self._busy():
            return
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self.items):
            return

        it = self.items[row]
        menu = QMenu(self)
        act_custom = menu.addAction(tr("ctx_custom"))
        act_tmdb = menu.addAction(tr("ctx_tmdb"))
        act_lang = menu.addAction(tr("ctx_lang"))

        if it.get("status") == "status_already_exists":
            menu.addSeparator()
            act_overwrite = menu.addAction(tr("ctx_overwrite"))
            act_suffix = menu.addAction(tr("ctx_suffix"))
        else:
            act_overwrite = None
            act_suffix = None

        menu.addSeparator()
        act_remove = menu.addAction(tr("ctx_remove"))

        exec_func = getattr(menu, "exec_", None) or getattr(menu, "exec")
        action = exec_func(QCursor.pos())

        if action == act_custom:
            self._edit_custom_dialog(row)
        elif action == act_tmdb:
            self._edit_tmdb_dialog(row)
        elif action == act_lang:
            self._change_lang_dialog(row)
        elif act_overwrite and action == act_overwrite:
            it["force_overwrite"] = True
            set_status(it, "status_ready_overwrite")
            self.refresh_row(row)
            self.update_buttons()
        elif act_suffix and action == act_suffix:
            p = Path(it["newname"])
            it["newname"] = f"{p.stem}{tr('copy_suffix')}{p.suffix}"
            set_status(it, "status_ready_suffix")
            self.refresh_row(row)
            self.update_buttons()
        elif action == act_remove:
            del self.items[row]
            self.table.removeRow(row)
            self.update_buttons()

    def _edit_custom_dialog(self, row, allow_reset=True):
        """Nome/cartella personalizzati. allow_reset=False quando chiamato dalla
        risoluzione duplicati, dove "torna automatico" non risolverebbe nulla
        senza un nuovo Test (il nome resterebbe quello che ha causato il duplicato)."""
        it = self.items[row]
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("custom_edit_title"))
        layout = QFormLayout(dlg)

        name_in = QLineEdit(it["newname"] or it["path"].name)
        folder_in = QLineEdit(it["folder"])
        layout.addRow(tr("new_filename"), name_in)
        layout.addRow(tr("dest_subfolder"), folder_in)

        if allow_reset and it.get("custom_override"):
            reset_row = QHBoxLayout()
            btn_reset = QPushButton(tr("reset_auto_name"))
            btn_reset.clicked.connect(lambda: dlg.done(2))
            reset_row.addWidget(btn_reset)
            reset_row.addStretch(1)
            layout.addRow("", reset_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        while True:
            result = dlg.exec_()
            if result == 2:  # "Ripristina nome automatico"
                it["custom_override"] = False
                set_status(it, "status_to_test")
                self.refresh_row(row)
                self.update_buttons()
                return True
            if result != QDialog.Accepted:
                return False

            raw_name = name_in.text().strip()
            raw_folder = folder_in.text().strip()
            folder_path = Path(raw_folder) if raw_folder else None
            name = sanitize_title(raw_name, fix_apos=False)
            invalid = (
                not name or name in (".", "..")
                or "/" in raw_name or "\\" in raw_name
                or (folder_path is not None
                    and (folder_path.is_absolute() or ".." in folder_path.parts))
            )
            if invalid:
                QMessageBox.warning(self, tr("invalid_custom_title"), tr("invalid_custom_msg"))
                continue
            it["newname"] = name
            it["folder"] = ("/".join(sanitize_title(part, fix_apos=False) for part in folder_path.parts)
                             if folder_path else "")
            it["custom_override"] = True
            set_status(it, "status_ready_custom")
            self.refresh_row(row)
            self.update_buttons()
            return True

    def _edit_tmdb_dialog(self, row):
        it = self.items[row]
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("edit_tmdb_title"))
        layout = QFormLayout(dlg)
        id_in = QLineEdit(it["tmdb_id"])
        layout.addRow(tr("tmdb_id_label"), id_in)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec_() == QDialog.Accepted:
            it["tmdb_id"] = id_in.text().strip()
            set_status(it, "status_id_tmdb")
            self.refresh_row(row)
            self.update_buttons()

    def _change_lang_dialog(self, row):
        it = self.items[row]
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("select_lang_title"))
        layout = QFormLayout(dlg)
        combo = QComboBox()
        combo.addItems(["en-US", "it-IT", "es-ES", "fr-FR", "de-DE", "ja-JP"])
        combo.setCurrentText(it.get("lang") or CONFIG.get("lang", "en-US"))
        layout.addRow(tr("lang_label"), combo)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec_() == QDialog.Accepted:
            it["lang"] = combo.currentText()
            set_status(it, "status_to_test")
            self.refresh_row(row)
            self.update_buttons()

    def update_buttons(self, idle=False):
        busy = not idle and self._busy()
        self.btn_test.setEnabled(not busy and bool(self.items))
        for b in self._action_buttons():
            b.setEnabled(not busy)

        selected_rows = {i.row() for i in self.table.selectedIndexes()}
        n_ready_all = sum(1 for it in self.items if is_ready(it))
        n_ready_sel = sum(1 for i in selected_rows if is_ready(self.items[i]))
        action_word = tr("action_move_short") if CONFIG.get("action_movies", "move") == "move" else tr("action_copy_short")

        self.btn_exec_sel.setText(f"{action_word} {tr('exec_sel_suffix', n=n_ready_sel)}")
        self.btn_exec_sel.setEnabled(not busy and n_ready_sel > 0)
        self.btn_exec_all.setText(f"{action_word} {tr('exec_all_suffix', n=n_ready_all)}")
        self.btn_exec_all.setEnabled(not busy and n_ready_all > 0)

    def update_buttons_busy(self):
        for b in (self.btn_test, self.btn_exec_sel, self.btn_exec_all, *self._action_buttons()):
            b.setEnabled(False)

    def start(self, mode, scope="selected"):
        if mode == "test" and not CONFIG["api_key"].strip():
            QMessageBox.warning(self, tr("missing_key_title"), tr("missing_key_msg"))
            return
        if not CONFIG["dest_movies"].strip():
            QMessageBox.warning(self, tr("missing_dest_title"), tr("missing_dest_msg"))
            return

        if mode == "test":
            selected_rows = sorted({i.row() for i in self.table.selectedIndexes()})
            candidates = selected_rows or range(len(self.items))
            rows = [i for i in candidates if not is_done(self.items[i])]
        else:
            if scope == "selected":
                candidates = sorted({i.row() for i in self.table.selectedIndexes()})
            else:
                candidates = range(len(self.items))
            rows = [i for i in candidates if is_ready(self.items[i])]

        if not rows:
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.worker = MovieWorker(
            self.items, rows, mode,
            action=CONFIG.get("action_movies", "move"),
            unmount_after=CONFIG.get("unmount", True),
            clean_parent=CONFIG.get("clean_parent_dir", False),
            mounted_by_us=self.mounted_by_us,
        )
        self.worker.status.connect(self._show_status)
        self.worker.error.connect(self.on_error)
        self.worker.mounted.connect(self.on_mounted)
        self.worker.unmounted.connect(self.on_unmounted)
        self.worker.row_update.connect(self.refresh_row)
        self.worker.row_update.connect(lambda _i: self.update_buttons())
        self.worker.file_progress.connect(self.progress_bar.setValue)
        self.worker.progress.connect(self.on_progress)
        self.worker.ask.connect(self.on_ask)
        self.worker.ask_duplicate.connect(self.on_ask_duplicate)
        self.worker.ask_non_empty_dir.connect(self.on_ask_non_empty_dir)
        self.worker.all_done.connect(lambda: self.on_done(mode))
        self.worker.finished.connect(lambda: self.update_buttons(idle=True))
        self.update_buttons_busy()
        self.worker.start()

    def on_progress(self, current, total):
        if self.worker and self.worker.mode == "test":
            act_name = tr("test")
        else:
            act_name = tr("move") if CONFIG.get("action_movies", "move") == "move" else tr("copy")
        self._show_status(f"{act_name}: {current}/{total}")

    def on_ask(self, row, results, guessed):
        self.table.selectRow(row)
        dlg = ChoiceDialog(guessed, results, self, lang=self.items[row].get("lang"))
        choice = dlg.selected() if dlg.exec_() == QDialog.Accepted else None
        self.worker.provide(choice)

    def on_ask_duplicate(self, row):
        self.table.selectRow(row)
        it = self.items[row]
        dlg = DuplicateDialog(it["folder"], it["newname"], self)
        if dlg.exec_() == QDialog.Accepted:
            if dlg.choice == "custom" and not self._edit_custom_dialog(row, allow_reset=False):
                self.worker.provide_dup_choice("skip", False)
            else:
                self.worker.provide_dup_choice(dlg.choice, dlg.apply_to_all)
        else:
            self.worker.provide_dup_choice("skip", False)

    def on_ask_non_empty_dir(self, row, folder_path, size_str):
        self.table.selectRow(row)
        dlg = NonEmptyDirDialog(folder_path, size_str, self)
        if dlg.exec_() == QDialog.Accepted:
            self.worker.provide_non_empty_choice(dlg.choice, dlg.apply_to_all)
        else:
            self.worker.provide_non_empty_choice("no", False)

    def on_done(self, mode):
        self.progress_bar.setVisible(False)
        ready = sum(1 for it in self.items if is_ready(it))
        done = sum(1 for it in self.items if is_done(it))

        if mode == "test":
            msg = tr("done_test", ready=ready)
        else:
            msg = tr("done_action", done=done)
            play_system_sound()
            send_mint_notification(tr("notif_title"), tr("notif_body", done=done))

        if self.worker and self.worker.did_unmount:
            msg += tr("unmounted_msg")
        self._show_status(msg)
        self.update_buttons(idle=True)

    def on_error(self, msg):
        self.progress_bar.setVisible(False)
        self._show_status(msg)
        QMessageBox.warning(self, tr("error_title"), msg)

    def on_mounted(self, mp):
        self.mounted_by_us = mp

    def on_unmounted(self):
        self.mounted_by_us = None

    def is_busy(self):
        return self._busy()

    def cleanup_before_close(self):
        from media_operations import unmount_share
        if self.mounted_by_us and CONFIG.get("unmount", True):
            try:
                unmount_share(self.mounted_by_us)
            except Exception:
                pass
