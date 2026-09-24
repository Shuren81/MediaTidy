#!/usr/bin/env python3
"""
ui/series_tab.py - Scheda "Serie TV": tabella con drag&drop di file o cartelle di
release, Test/Esegui, dialogo di conferma TMDB, menu contestuale (modifica
Stagione/Episodio, codice TMDB, lingua), duplicati e cartelle non vuote.
Usa core/series_handler.py per tutta la logica.
"""
from pathlib import Path

from config import CONFIG
from localization import tr
from media_operations import play_system_sound, send_mint_notification
from tmdb_client import search_tv
from core.movie_handler import DONE_KEYS, ERROR_KEYS, READY_KEYS, SKIP_KEYS, is_done, set_status, status_text
from core.series_handler import SeriesWorker, collect_items_for_path, is_ready
from ui.widgets import (
    ITEM_ENABLED, ITEM_SELECTABLE, ROLE_USER, DuplicateDialog, NonEmptyDirDialog,
    ToggleableListWidget,
)

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QCursor
from qtpy.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QProgressBar, QPushButton, QRadioButton, QSpinBox, QTableWidgetItem,
    QVBoxLayout, QWidget,
)


class TvChoiceDialog(QDialog):
    """Conferma/ricerca manuale della serie quando TMDB non trova un risultato certo."""
    def __init__(self, guessed, results, parent=None, lang=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("series_choice_title"))
        self.resize(680, 440)
        lay = QVBoxLayout(self)
        msg = (tr("series_no_res") if not results else tr("series_uncertain")) + tr("series_choice_msg", guessed=guessed)
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
        for s in results:
            year = (s.get("first_air_date") or "????")[:4]
            overview = (s.get("overview") or "").strip()
            if len(overview) > 140:
                overview = overview[:140] + "…"
            text = f"{s.get('name')} ({year}) — original: {s.get('original_name')}"
            if overview:
                text += f"\n    {overview}"
            item = QListWidgetItem(text)
            item.setData(ROLE_USER, s)
            self.list.addItem(item)
        if results:
            self.list.setCurrentRow(0)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(results))

    def _search(self):
        q = self.query.text().strip()
        if not q:
            return
        try:
            self._fill(search_tv(q, None, lang=self.lang, limit=8))
        except Exception as e:
            QMessageBox.warning(self, tr("error_title"), f"Search failed: {e}")

    def selected(self):
        item = self.list.currentItem()
        return item.data(ROLE_USER) if item else None


SERIES_HEADERS = [
    "series_col_orig", "series_col_show", "series_col_ep", "series_col_new",
    "series_col_dest", "series_col_tmdb", "series_col_status",
]


def _ep_text(it):
    season, episodes = it.get("season"), it.get("episodes")
    if not season or not episodes:
        return "?"
    if len(episodes) > 1:
        return f"S{season:02d}E{episodes[0]:02d}-E{episodes[-1]:02d}"
    return f"S{season:02d}E{episodes[0]:02d}"


class SeriesTab(QWidget):
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
        if CONFIG.get("action", "move") == "move":
            self.radio_move.setChecked(True)
        else:
            self.radio_copy.setChecked(True)
        self.radio_move.toggled.connect(self._update_action_mode)
        self.top_bar.addWidget(self.radio_move)
        self.top_bar.addWidget(self.radio_copy)
        self.top_bar.addStretch(1)
        self.lay.addLayout(self.top_bar)

        self.table = ToggleableListWidget(SERIES_HEADERS, stretch_cols=(0, 1, 3, 4))
        self.table.files_dropped.connect(self.add_paths)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemChanged.connect(self.on_item_changed)
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
        self.btn_rename = QPushButton()

        self.btn_add_files.clicked.connect(self.pick_files)
        self.btn_add_dir.clicked.connect(self.pick_dir)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_test.clicked.connect(lambda: self.start("test"))
        self.btn_rename.clicked.connect(lambda: self.start("action"))

        for b in (self.btn_add_files, self.btn_add_dir, self.btn_remove, self.btn_clear):
            self.row_btns.addWidget(b)
        self.row_btns.addStretch(1)
        self.row_btns.addWidget(self.btn_test)
        self.row_btns.addWidget(self.btn_rename)
        self.lay.addLayout(self.row_btns)

        self.status_callback = None  # impostato da MainWindow -> statusBar().showMessage
        self.retranslate_ui()
        self.update_buttons()

    # ------------------------------------------------------------------ #
    def retranslate_ui(self):
        self.lbl_action.setText(tr("file_action"))
        self.radio_move.setText(tr("move"))
        self.radio_copy.setText(tr("copy"))
        self.btn_add_files.setText(tr("add_files"))
        self.btn_add_dir.setText(tr("add_dir"))
        self.btn_remove.setText(tr("remove_sel"))
        self.btn_clear.setText(tr("clear_all"))
        self.btn_test.setText(tr("test"))
        self.btn_rename.setText(tr("execute"))
        self.table.update_headers()
        for i in range(len(self.items)):
            self.refresh_row(i)

    def _show_status(self, msg):
        if self.status_callback:
            self.status_callback(msg)

    def _update_action_mode(self):
        CONFIG["action"] = "move" if self.radio_move.isChecked() else "copy"

    def config_changed(self):
        for it in self.items:
            if is_ready(it) or it.get("status") == "status_already_exists":
                set_status(it, "status_to_test")
        self.retranslate_ui()
        self.update_buttons()

    # ------------------------------------------------------------------ #
    def pick_files(self):
        from media_operations import VIDEO_EXT
        files, _ = QFileDialog.getOpenFileNames(
            self, "Video", "",
            "Video (" + " ".join(f"*{e}" for e in sorted(VIDEO_EXT)) + ")"
        )
        if files:
            self.add_paths(files)

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr("series_add_release"))
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
        for p in paths:
            new_items = collect_items_for_path(p, known)
            for it in new_items:
                known.add(it["path"])
                self.items.append(it)
                self.table.insertRow(self.table.rowCount())
                self.refresh_row(len(self.items) - 1)
                added += 1
        if not added and paths:
            self._show_status(tr("no_video_found"))
        self.update_buttons()

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
        show_display = it.get("tmdb_localized") or it.get("show_guess") or ""
        cells = [it["path"].name, show_display, _ep_text(it), it["newname"],
                 it["folder"], it["tmdb_id"], status_text(it)]
        self.table.blockSignals(True)
        for c, text in enumerate(cells):
            cell = QTableWidgetItem(text)
            cell.setToolTip(str(it["path"]) if c == 0 else text)
            if c != 5:  # solo la colonna "Codice TMDB" è modificabile a mano
                cell.setFlags(ITEM_ENABLED | ITEM_SELECTABLE)
            if c == 6:
                if key in READY_KEYS or key in DONE_KEYS:
                    cell.setForeground(QColor(0, 140, 0))
                elif key in ERROR_KEYS or key in ("status_already_exists", "series_status_unknown_ep"):
                    cell.setForeground(QColor(200, 0, 0))
                elif key in SKIP_KEYS:
                    cell.setForeground(QColor(128, 128, 128))
            self.table.setItem(i, c, cell)
        self.table.blockSignals(False)

    def on_item_changed(self, item):
        row = item.row()
        col = item.column()
        if col != 5 or not (0 <= row < len(self.items)):
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

    def show_context_menu(self, pos):
        if self._busy():
            return
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self.items):
            return

        it = self.items[row]
        menu = QMenu(self)
        act_ep = menu.addAction(tr("series_ctx_edit_ep"))
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

        if action == act_ep:
            self._edit_episode_dialog(row)
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

    def _edit_episode_dialog(self, row):
        it = self.items[row]
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("series_edit_ep_title"))
        layout = QFormLayout(dlg)

        season_in = QSpinBox()
        season_in.setRange(0, 99)
        season_in.setValue(it.get("season") or 1)
        ep_in = QSpinBox()
        ep_in.setRange(1, 999)
        ep_in.setValue((it.get("episodes") or (1,))[0])
        ep_last_in = QSpinBox()
        ep_last_in.setRange(0, 999)
        ep_last_in.setValue((it.get("episodes") or (0,))[-1] if it.get("episodes") and len(it["episodes"]) > 1 else 0)

        layout.addRow(tr("series_season_label"), season_in)
        layout.addRow(tr("series_episode_label"), ep_in)
        layout.addRow(tr("series_episode_last_label"), ep_last_in)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec_() == QDialog.Accepted:
            season = season_in.value()
            first = ep_in.value()
            last = ep_last_in.value()
            episodes = tuple(range(first, last + 1)) if last and last > first else (first,)
            it["season"] = season
            it["episodes"] = episodes
            it["custom_override"] = False  # nome/cartella vanno ricalcolati al prossimo Test
            set_status(it, "status_to_test")
            self.refresh_row(row)
            self.update_buttons()

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
        self.btn_rename.setEnabled(not busy and any(is_ready(it) for it in self.items))
        for b in self._action_buttons():
            b.setEnabled(not busy)

    def update_buttons_busy(self):
        for b in (self.btn_test, self.btn_rename, *self._action_buttons()):
            b.setEnabled(False)

    def start(self, mode):
        if mode == "test" and not CONFIG["api_key"].strip():
            QMessageBox.warning(self, tr("missing_key_title"), tr("missing_key_msg"))
            return
        if not CONFIG["dest_series"].strip():
            QMessageBox.warning(self, tr("missing_dest_title"), tr("missing_dest_msg"))
            return

        selected_rows = sorted({i.row() for i in self.table.selectedIndexes()})
        candidates = selected_rows or range(len(self.items))
        if mode == "test":
            rows = [i for i in candidates if not is_done(self.items[i])]
        else:
            rows = [i for i in candidates if is_ready(self.items[i])]

        if not rows:
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.worker = SeriesWorker(
            self.items, rows, mode,
            action=CONFIG.get("action", "move"),
            unmount_after=CONFIG.get("unmount", True),
            clean_parent=CONFIG.get("clean_parent_dir", False),
            mounted_by_us=self.mounted_by_us,
        )
        self.worker.status.connect(self._show_status)
        self.worker.error.connect(self.on_error)
        self.worker.mounted.connect(self.on_mounted)
        self.worker.unmounted.connect(self.on_unmounted)
        self.worker.row_update.connect(self.refresh_row)
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
        act_name = tr("test") if self.worker and self.worker.mode == "test" else (tr("move") if CONFIG["action"] == "move" else tr("copy"))
        self._show_status(f"{act_name}: {current}/{total}")

    def on_ask(self, row, results, guessed):
        self.table.selectRow(row)
        dlg = TvChoiceDialog(guessed, results, self, lang=self.items[row].get("lang"))
        choice = dlg.selected() if dlg.exec_() == QDialog.Accepted else None
        self.worker.provide(choice)

    def on_ask_duplicate(self, row):
        self.table.selectRow(row)
        it = self.items[row]
        dlg = DuplicateDialog(it["folder"], it["newname"], self)
        if dlg.exec_() == QDialog.Accepted:
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
        done = sum(1 for it in self.items if it.get("status") in DONE_KEYS)

        if mode == "test":
            msg = tr("done_test", ready=ready)
        else:
            msg = tr("done_action", done=done)
            play_system_sound()
            send_mint_notification(tr("notif_title"), tr("notif_body", done=done))

        if self.worker and self.worker.did_unmount:
            msg += tr("unmounted_msg")
        self._show_status(msg)

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
