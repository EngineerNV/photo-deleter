"""Photo Deleter — a swipe-to-sort photo triage app.

Tinder-style mechanics: drag the card right to keep, left to delete,
or use the round action buttons / keyboard. Built with PyQt5.
"""

import os
import sys
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from backend import ImageBackend
from sounds import SoundManager
from theme import (
    PALETTE,
    BODY_FONT_CANDIDATES,
    TITLE_FONT_CANDIDATES,
    app_stylesheet,
    finish_button_style,
    ghost_button_style,
    pick_font,
    primary_button_style,
    round_action_style,
)
from widgets import FloatingEmoji, FullscreenViewer, SwipeDeck, Toast

MAX_DISPLAY_DIM = 1600
MAX_PREVIEW_DIM = 900

WELCOME_MESSAGE = "Drop a photo folder here\nor press  O  to open one"
WELCOME_HINT = "Drag right to keep · drag left to delete · double-click to inspect"


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class FinishDialog(QtWidgets.QDialog):
    """Confirmation dialog shown when the user clicks **Finish**."""

    def __init__(self, parent: QtWidgets.QWidget, kept_files: list, deleted_files: list):
        super().__init__(parent)
        self.setWindowTitle("Finish Session")
        self.setModal(True)
        self.setMinimumSize(460, 340)
        self._kept = kept_files
        self._deleted = deleted_files
        self.delete_confirmed = False
        self.restore_confirmed = False
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(
            f"""
            QDialog {{ background: {PALETTE["bg_top"]}; }}
            QLabel {{ color: {PALETTE["text"]}; background: transparent; }}
            QCheckBox {{
                color: {PALETTE["text"]};
                font-size: 13px;
                spacing: 10px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 20px; height: 20px;
                border: 2px solid {PALETTE["border_strong"]};
                border-radius: 6px;
                background: {PALETTE["surface"]};
            }}
            QCheckBox::indicator:checked {{
                background: {PALETTE["keep"]};
                border-color: {PALETTE["keep"]};
            }}
            """
        )

        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(30, 28, 30, 26)

        title = QtWidgets.QLabel("Session complete")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(title)

        summary = QtWidgets.QLabel(
            f"{len(self._kept)} kept   ·   {len(self._deleted)} marked for deletion"
        )
        summary.setStyleSheet(
            f"font-size: 13px; color: {PALETTE['text_secondary']}; font-weight: 600;"
        )
        summary.setAlignment(QtCore.Qt.AlignCenter)
        summary.setWordWrap(True)
        lay.addWidget(summary)

        lay.addSpacing(8)

        self.delete_check = QtWidgets.QCheckBox(
            f"Permanently delete {len(self._deleted)} photo(s)"
        )
        self.delete_check.setChecked(bool(self._deleted))
        self.delete_check.setEnabled(bool(self._deleted))
        lay.addWidget(self.delete_check)

        self.restore_check = QtWidgets.QCheckBox(
            f"Restore {len(self._kept)} kept photo(s) to the original folder"
        )
        self.restore_check.setChecked(bool(self._kept))
        self.restore_check.setEnabled(bool(self._kept))
        lay.addWidget(self.restore_check)

        lay.addSpacing(4)

        warn = QtWidgets.QLabel(
            "Deleted photos are permanently removed and cannot be recovered."
        )
        warn.setStyleSheet(
            f"font-size: 12px; color: {PALETTE['delete']}; font-weight: 700;"
        )
        warn.setWordWrap(True)
        lay.addWidget(warn)

        lay.addStretch()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(12)

        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setFixedHeight(42)
        cancel.setCursor(QtCore.Qt.PointingHandCursor)
        cancel.setStyleSheet(ghost_button_style())
        cancel.clicked.connect(self.reject)

        confirm = QtWidgets.QPushButton("Confirm && Finish")
        confirm.setFixedHeight(42)
        confirm.setCursor(QtCore.Qt.PointingHandCursor)
        confirm.setStyleSheet(primary_button_style())
        confirm.clicked.connect(self._on_confirm)

        btn_row.addWidget(cancel, stretch=1)
        btn_row.addWidget(confirm, stretch=1)
        lay.addLayout(btn_row)

    def _on_confirm(self):
        self.delete_confirmed = self.delete_check.isChecked()
        self.restore_confirmed = self.restore_check.isChecked()
        self.accept()


class ImageSwiper(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.backend = None
        self.history = []
        self.current_index = -1
        self.current_path = None
        self.kept_count = 0
        self.deleted_count = 0
        self.skipped_count = 0

        self.settings = QtCore.QSettings("photo-deleter", "PhotoDeleter")
        self.body_font = pick_font(BODY_FONT_CANDIDATES)
        self.title_font = pick_font(TITLE_FONT_CANDIDATES)
        self.sound = SoundManager(muted=self.settings.value("sound/muted", False, bool))

        self._pixmap_cache = {}  # path -> display pixmap
        self._progress_anim = None

        self.setWindowTitle("Photo Deleter")
        self.setMinimumSize(880, 660)
        self.setObjectName("appRoot")
        self.setStyleSheet(app_stylesheet(self.body_font, self.title_font))
        self.setAcceptDrops(True)

        self._build_ui()
        self._connect_shortcuts()
        self._show_welcome()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self):
        # Top bar -------------------------------------------------------
        title = QtWidgets.QLabel("Photo Deleter")
        title.setObjectName("appTitle")

        self.folder_chip = QtWidgets.QLabel("No folder")
        self.folder_chip.setObjectName("folderChip")

        self.status_chip = QtWidgets.QLabel("")
        self.status_chip.setObjectName("statusChip")
        self._set_status("Waiting for folder", "info")

        self.mute_button = QtWidgets.QPushButton(self._mute_glyph())
        self.mute_button.setFixedSize(38, 38)
        self.mute_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.mute_button.setToolTip("Toggle sound (M)")
        self.mute_button.setStyleSheet(ghost_button_style())
        self.mute_button.clicked.connect(self.toggle_mute)

        open_button = QtWidgets.QPushButton("Open Folder")
        open_button.setCursor(QtCore.Qt.PointingHandCursor)
        open_button.setToolTip("Choose a folder of photos (O)")
        open_button.setStyleSheet(primary_button_style())
        open_button.clicked.connect(self.choose_directory)

        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setSpacing(10)
        top_bar.addWidget(title)
        top_bar.addWidget(self.folder_chip)
        top_bar.addStretch()
        top_bar.addWidget(self.status_chip)
        top_bar.addWidget(self.mute_button)
        top_bar.addWidget(open_button)

        # Swipe deck ------------------------------------------------------
        self.deck = SwipeDeck()
        self.deck.swiped.connect(self._on_deck_swiped)
        self.deck.inspect_requested.connect(self.open_fullscreen)

        # Meta strip ------------------------------------------------------
        self.file_label = QtWidgets.QLabel("")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setWordWrap(True)

        self.meta_label = QtWidgets.QLabel("")
        self.meta_label.setObjectName("metaLabel")

        self.action_label = QtWidgets.QLabel("No actions yet.")
        self.action_label.setObjectName("actionLabel")

        meta_strip = QtWidgets.QFrame()
        meta_strip.setObjectName("metaStrip")
        meta_layout = QtWidgets.QVBoxLayout(meta_strip)
        meta_layout.setContentsMargins(16, 10, 16, 10)
        meta_layout.setSpacing(2)
        meta_layout.addWidget(self.file_label)
        meta_layout.addWidget(self.meta_label)
        meta_layout.addWidget(self.action_label)

        # Round action buttons (Tinder-style) ----------------------------
        self.undo_button = self._round_button(
            "↺", PALETTE["undo"], PALETTE["undo_hover"], 52, "Undo last action (Ctrl+Z)"
        )
        self.delete_button = self._round_button(
            "✕", PALETTE["delete"], PALETTE["delete_hover"], 64, "Delete — move to deleted/ (←)"
        )
        self.skip_button = self._round_button(
            "»", PALETTE["skip"], PALETTE["skip_hover"], 52, "Skip for now (Space)"
        )
        self.keep_button = self._round_button(
            "♥", PALETTE["keep"], PALETTE["keep_hover"], 64, "Keep — move to kept/ (→)"
        )

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.setSpacing(18)
        actions_row.addStretch()
        actions_row.addWidget(self.undo_button)
        actions_row.addWidget(self.delete_button)
        actions_row.addWidget(self.skip_button)
        actions_row.addWidget(self.keep_button)
        actions_row.addStretch()

        # Finish button (hidden until session is complete) ---------------
        self.finish_button = QtWidgets.QPushButton("Finish session")
        self.finish_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.finish_button.setStyleSheet(finish_button_style())
        self.finish_button.clicked.connect(self._show_finish_dialog)
        self.finish_button.hide()

        # Footer: progress + stats + hints --------------------------------
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)

        self.progress_label = QtWidgets.QLabel("0 / 0 sorted")
        self.progress_label.setObjectName("metaLabel")

        self.stat_kept_label = QtWidgets.QLabel("0 kept")
        self.stat_kept_label.setStyleSheet(
            f"color: {PALETTE['keep']}; font-size: 11px; font-weight: 700;"
        )
        self.stat_deleted_label = QtWidgets.QLabel("0 deleted")
        self.stat_deleted_label.setStyleSheet(
            f"color: {PALETTE['delete']}; font-size: 11px; font-weight: 700;"
        )
        self.stat_skipped_label = QtWidgets.QLabel("0 skipped")
        self.stat_skipped_label.setStyleSheet(
            f"color: {PALETTE['skip']}; font-size: 11px; font-weight: 700;"
        )

        hints = QtWidgets.QLabel(
            "→ Keep    ← Delete    Space Skip    Ctrl+Z Undo    F Inspect    M Mute    O Open"
        )
        hints.setObjectName("hintLabel")

        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setSpacing(14)
        stats_row.addWidget(self.progress_label)
        stats_row.addSpacing(10)
        stats_row.addWidget(self.stat_kept_label)
        stats_row.addWidget(self.stat_deleted_label)
        stats_row.addWidget(self.stat_skipped_label)
        stats_row.addStretch()
        stats_row.addWidget(hints)

        # Root layout -----------------------------------------------------
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)
        root.addLayout(top_bar)
        root.addWidget(self.deck, stretch=1)
        root.addWidget(meta_strip)
        root.addLayout(actions_row)
        root.addWidget(self.finish_button)
        root.addWidget(self.progress_bar)
        root.addLayout(stats_row)

        self.keep_button.clicked.connect(self.keep_current)
        self.delete_button.clicked.connect(self.delete_current)
        self.skip_button.clicked.connect(self.skip_current)
        self.undo_button.clicked.connect(self.undo_last)

        self.toast = Toast(self)

        self.update_controls(False)

    def _round_button(self, glyph, color, hover, diameter, tooltip):
        button = QtWidgets.QPushButton(glyph)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setStyleSheet(round_action_style(color, hover, diameter))
        return button

    def _connect_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.keep_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.delete_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.skip_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, activated=self.undo_last)
        QtWidgets.QShortcut(QtGui.QKeySequence("F"), self, activated=self.open_fullscreen)
        QtWidgets.QShortcut(QtGui.QKeySequence("M"), self, activated=self.toggle_mute)
        QtWidgets.QShortcut(QtGui.QKeySequence("O"), self, activated=self.choose_directory)
        QtWidgets.QShortcut(QtGui.QKeySequence("R"), self, activated=self.resume_last_folder)

    # -- status / welcome -----------------------------------------------

    def _set_status(self, text: str, tone: str):
        styles = {
            "info": f"background: {PALETTE['surface']};",
            "active": "background: rgba(91, 140, 255, 0.18); border-color: rgba(91, 140, 255, 0.55);",
            "success": "background: rgba(45, 212, 119, 0.16); border-color: rgba(45, 212, 119, 0.55);",
            "error": "background: rgba(244, 81, 108, 0.16); border-color: rgba(244, 81, 108, 0.55);",
        }
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(styles.get(tone, styles["info"]))

    def _show_welcome(self):
        hint = WELCOME_HINT
        last_dir = self.settings.value("session/last_dir", "", str)
        if last_dir and os.path.isdir(last_dir):
            hint += f"\nPress  R  to resume “{os.path.basename(last_dir)}”"
        self.deck.set_message(WELCOME_MESSAGE, hint)

    # -- image loading ------------------------------------------------------

    def _load_pixmap(self, path: str, max_dim: int = MAX_DISPLAY_DIM):
        key = (path, max_dim)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached
        reader = QtGui.QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid() and (size.width() > max_dim or size.height() > max_dim):
            size.scale(max_dim, max_dim, QtCore.Qt.KeepAspectRatio)
            reader.setScaledSize(size)
        image = reader.read()
        pixmap = QtGui.QPixmap.fromImage(image) if not image.isNull() else QtGui.QPixmap()
        if len(self._pixmap_cache) > 8:
            self._pixmap_cache.clear()
        self._pixmap_cache[key] = pixmap
        return pixmap

    def _upcoming_pixmaps(self):
        if not self.backend:
            return []
        out = []
        for offset in (1, 2):
            path = self.backend.get_image(self.current_index + offset)
            if path:
                pixmap = self._load_pixmap(path, MAX_PREVIEW_DIM)
                if not pixmap.isNull():
                    out.append(pixmap)
        return out

    def _set_meta_for(self, path: str):
        parts = []
        try:
            stat = os.stat(path)
            pixmap = self._pixmap_cache.get((path, MAX_DISPLAY_DIM))
            reader = QtGui.QImageReader(path)
            size = reader.size()
            if size.isValid():
                parts.append(f"{size.width()} × {size.height()} px")
            elif pixmap is not None and not pixmap.isNull():
                parts.append(f"{pixmap.width()} × {pixmap.height()} px")
            parts.append(human_size(stat.st_size))
            parts.append(datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y"))
        except OSError:
            pass
        if self.backend:
            position = self.backend.processed_count() + 1
            parts.append(f"{position} of {self.backend.total_images}")
        self.meta_label.setText("   ·   ".join(parts))

    # -- directory handling ---------------------------------------------

    def choose_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Image Directory")
        if not directory:
            return
        self.load_directory(directory)

    def resume_last_folder(self):
        last_dir = self.settings.value("session/last_dir", "", str)
        if last_dir and os.path.isdir(last_dir):
            self.load_directory(last_dir)

    def load_directory(self, directory: str):
        self.backend = ImageBackend(directory)
        self.history.clear()
        self.current_index = -1
        self.current_path = None
        self.kept_count = 0
        self.deleted_count = 0
        self.skipped_count = 0
        self._pixmap_cache.clear()
        self.action_label.setText("No actions yet.")
        self.finish_button.hide()
        self.folder_chip.setText(os.path.basename(directory) or directory)
        self.settings.setValue("session/last_dir", directory)
        self._update_stats()

        total = self.backend.total_images
        if total:
            self.toast.popup(f"Loaded {total} photo(s)")
            self.sound.play("open")
        self._set_status("Ready", "active")
        self.load_next_image()

    # -- drag & drop -------------------------------------------------------

    def _drop_dir(self, mime: QtCore.QMimeData):
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            path = url.toLocalFile()
            if path and os.path.isdir(path):
                return path
        return None

    def dragEnterEvent(self, event):
        if self._drop_dir(event.mimeData()):
            event.acceptProposedAction()
            self.deck.set_drop_highlight(True)

    def dragLeaveEvent(self, event):
        self.deck.set_drop_highlight(False)

    def dropEvent(self, event):
        self.deck.set_drop_highlight(False)
        directory = self._drop_dir(event.mimeData())
        if directory:
            event.acceptProposedAction()
            self.load_directory(directory)

    # -- core flow -----------------------------------------------------------

    def load_next_image(self, advance_index=True):
        if not self.backend:
            return

        if advance_index:
            self.current_index += 1

        while True:
            img_path = self.backend.get_image(self.current_index)
            if not img_path:
                self._on_session_complete()
                return

            pixmap = self._load_pixmap(img_path)
            if not pixmap.isNull():
                self.current_path = img_path
                self.deck.set_image(pixmap)
                self.deck.set_upcoming(self._upcoming_pixmaps())
                self.file_label.setText(os.path.basename(img_path))
                self._set_meta_for(img_path)
                self._set_status("Ready", "active")
                self.update_progress()
                self.update_controls(True)
                return

            self.action_label.setText(
                f"Skipped unreadable file: {os.path.basename(img_path)}"
            )
            self.current_index += 1

    def _on_session_complete(self):
        self.current_path = None
        summary = (
            f"{self.kept_count} kept · {self.deleted_count} deleted · "
            f"{self.skipped_count} skipped"
        )
        self.deck.set_message("All photos sorted 🎉", summary)
        self._set_status("Complete", "success")
        self.file_label.clear()
        self.meta_label.setText(summary)
        self.update_progress()
        self.update_controls(False)
        self.finish_button.show()
        self.sound.play("finish")
        self._celebrate()

    def _on_deck_swiped(self, direction: str):
        if direction == "keep":
            self.keep_current()
        elif direction == "delete":
            self.delete_current()

    def keep_current(self):
        if not self.backend or not self.current_path:
            return
        dest = self.backend.keep(self.current_path)
        if not dest:
            self.action_label.setText("Keep failed: could not move file")
            self._set_status("Move failed", "error")
            return
        self.history.append(("keep", dest))
        self.kept_count += 1
        name = os.path.basename(dest)
        self.action_label.setText(f"Kept {name}")
        self.deck.fly_out("keep")
        self.toast.popup(f"♥ Kept {name}")
        self.sound.play("keep")
        self._update_stats()
        self.current_index -= 1
        self.load_next_image()

    def delete_current(self):
        if not self.backend or not self.current_path:
            return
        dest = self.backend.delete(self.current_path)
        if not dest:
            self.action_label.setText("Delete failed: could not move file")
            self._set_status("Move failed", "error")
            return
        self.history.append(("delete", dest))
        self.deleted_count += 1
        name = os.path.basename(dest)
        self.action_label.setText(f"Deleted {name}")
        self.deck.fly_out("delete")
        self.toast.popup(f"✕ Deleted {name}")
        self.sound.play("delete")
        self._update_stats()
        self.current_index -= 1
        self.load_next_image()

    def skip_current(self):
        if not self.backend or not self.current_path:
            return
        self.skipped_count += 1
        self.action_label.setText(f"Skipped {os.path.basename(self.current_path)}")
        self.deck.fly_out("skip")
        self.sound.play("skip")
        self._update_stats()
        self.load_next_image()

    def undo_last(self):
        if not self.backend or not self.history:
            return
        action, moved_path = self.history.pop()
        restored = self.backend.undo_move(moved_path)
        if not restored:
            self.action_label.setText("Undo failed: file missing")
            self._set_status("Undo failed", "error")
            return
        if action == "keep":
            self.kept_count = max(0, self.kept_count - 1)
        elif action == "delete":
            self.deleted_count = max(0, self.deleted_count - 1)
        idx = self.backend.index_of_image(restored)
        if idx >= 0:
            self.current_index = idx - 1
        self.action_label.setText(f"Undid {action}: {os.path.basename(restored)}")
        self._set_status("Undo complete", "active")
        self.toast.popup(f"↺ Undid {action}")
        self.sound.play("undo")
        self._update_stats()
        self.finish_button.hide()
        self.load_next_image()

    # -- progress & stats -----------------------------------------------

    def update_progress(self):
        if not self.backend:
            self.progress_bar.setValue(0)
            self.progress_label.setText("0 / 0 sorted")
            return
        total = self.backend.total_images
        processed = self.backend.processed_count()
        percent = int((processed / total) * 100) if total else 0
        self._animate_progress(percent)
        self.progress_label.setText(f"{processed} / {total} sorted")

    def _animate_progress(self, value: int):
        if self._progress_anim is not None:
            self._progress_anim.stop()
        anim = QtCore.QPropertyAnimation(self.progress_bar, b"value")
        anim.setDuration(260)
        anim.setStartValue(self.progress_bar.value())
        anim.setEndValue(value)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.start()
        self._progress_anim = anim

    def update_controls(self, enabled):
        has_images = bool(enabled and self.backend and self.backend.remaining_count() > 0)
        self.keep_button.setEnabled(has_images)
        self.delete_button.setEnabled(has_images)
        self.skip_button.setEnabled(has_images)
        self.undo_button.setEnabled(bool(self.history))
        self.deck.set_interactive(has_images)

    def _update_stats(self):
        self.stat_kept_label.setText(f"{self.kept_count} kept")
        self.stat_deleted_label.setText(f"{self.deleted_count} deleted")
        self.stat_skipped_label.setText(f"{self.skipped_count} skipped")

    # -- extras -------------------------------------------------------------

    def toggle_mute(self):
        self.sound.set_muted(not self.sound.muted)
        self.settings.setValue("sound/muted", self.sound.muted)
        self.mute_button.setText(self._mute_glyph())
        self.toast.popup("Sound off" if self.sound.muted else "Sound on")

    def _mute_glyph(self) -> str:
        return "🔇" if self.sound.muted else "🔊"

    def open_fullscreen(self):
        if not self.current_path:
            return
        pixmap = QtGui.QPixmap(self.current_path)  # full resolution for inspection
        if pixmap.isNull():
            return
        caption = (
            f"{os.path.basename(self.current_path)}   ·   scroll to zoom · "
            "drag to pan · double-click to reset · Esc to close"
        )
        viewer = FullscreenViewer(self, pixmap, caption)
        viewer.showFullScreen()
        viewer.exec_()

    def _celebrate(self):
        center = self.deck.mapTo(self, self.deck.rect().center())
        for i, emoji in enumerate(("✨", "🎉", "✨")):
            offset = (i - 1) * 90
            FloatingEmoji(self, emoji, QtCore.QPoint(center.x() + offset - 32, center.y()))

    # -- finish dialog ----------------------------------------------------

    def _show_finish_dialog(self):
        if not self.backend:
            return
        kept = self.backend.get_kept_files()
        deleted = self.backend.get_deleted_files()
        dlg = FinishDialog(self, kept, deleted)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        deleted_n = 0
        restored_n = 0
        if dlg.delete_confirmed:
            deleted_n = self.backend.finish_delete()
        if dlg.restore_confirmed:
            restored_n = self.backend.finish_restore_kept()

        parts = []
        if deleted_n:
            parts.append(f"{deleted_n} photo(s) permanently deleted")
        if restored_n:
            parts.append(f"{restored_n} photo(s) restored")
        summary = " · ".join(parts) if parts else "No changes made."
        self._set_status("Finished", "success")
        self.action_label.setText(summary)
        self.deck.set_message("All done ✨", summary)
        self.finish_button.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast._reposition()


def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Photo Deleter")
    window = ImageSwiper()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
