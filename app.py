import math
import os
import struct
import sys
import tempfile
import wave

from PyQt5 import QtCore, QtGui, QtWidgets

from backend import ImageBackend

try:
    from PyQt5.QtMultimedia import QSoundEffect  # noqa: F401

    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False


PALETTE = {
    "bg_base": "#130c28",
    "bg_mid": "#422a75",
    "bg_end": "#2d74b5",
    "panel_bg": "rgba(38, 25, 77, 0.78)",
    "panel_border": "rgba(133, 234, 255, 0.52)",
    "text_primary": "#fef6ff",
    "text_secondary": "#d8e8ff",
    "text_muted": "rgba(246, 235, 255, 0.84)",
    "accent_cyan": "#7be8ff",
    "accent_magenta": "#f883ff",
    "accent_lilac": "#b8a7ff",
    "accent_pink": "#ff8dd0",
    "ink_dark": "#1a0f31",
    "keep": "#1de8b1",
    "keep_hover": "#16bf90",
    "delete": "#ff7ca8",
    "delete_hover": "#e66996",
    "skip": "#ffd06f",
    "skip_hover": "#e7b95d",
    "undo": "#7db2ff",
    "undo_hover": "#6799e4",
}

BODY_FONT_CANDIDATES = ["Verdana", "Trebuchet MS", "Helvetica Neue", "Arial"]
TITLE_FONT_CANDIDATES = ["Impact", "Trebuchet MS", "Avenir Next", "Helvetica Neue", "Arial"]


def pick_font(candidates):
    available = set(QtGui.QFontDatabase().families())
    for family in candidates:
        if family in available:
            return family
    return "Sans Serif"


class AspectRatioImageLabel(QtWidgets.QLabel):
    def __init__(self, text: str = ""):
        super().__init__(text)
        self._source_pixmap = None
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setScaledContents(False)

    def set_source_pixmap(self, pixmap: QtGui.QPixmap):
        self._source_pixmap = pixmap
        super().setPixmap(QtGui.QPixmap())
        super().setText("")
        self.update()

    def set_message(self, message: str):
        self._source_pixmap = None
        super().setPixmap(QtGui.QPixmap())
        super().setText(message)
        self.update()

    def paintEvent(self, event):
        if self._source_pixmap and not self._source_pixmap.isNull():
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            rect = self.contentsRect()
            scaled = self._source_pixmap.scaled(
                rect.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) // 2
            y = rect.y() + (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            return
        super().paintEvent(event)


class ImageCard(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("imageCard")
        self.setStyleSheet(
            f"""
            #imageCard {{
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(31, 17, 64, 0.97), stop:0.46 rgba(72, 45, 138, 0.94), stop:1 rgba(36, 101, 170, 0.92));
                border-radius: 22px;
                border: 2px solid {PALETTE["panel_border"]};
            }}
            """
        )
        self.setMinimumHeight(340)

        shadow = QtWidgets.QGraphicsDropShadowEffect(blurRadius=34, xOffset=0, yOffset=18)
        shadow.setColor(QtGui.QColor(0, 0, 0, 205))
        self.setGraphicsEffect(shadow)

        self.pixmap_label = AspectRatioImageLabel("Pick a directory to begin sorting.")
        self.pixmap_label.setStyleSheet(
            f"""
            color: {PALETTE["text_muted"]};
            font-size: 18px;
            font-weight: 600;
            """
        )
        self.pixmap_label.setMinimumHeight(260)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self.pixmap_label)

    def set_image(self, pixmap: QtGui.QPixmap):
        self.pixmap_label.set_source_pixmap(pixmap)

    def set_message(self, message: str):
        self.pixmap_label.set_message(message)


class FloatingReaction(QtWidgets.QLabel):
    """Animated emoji that floats upward and fades out."""

    def __init__(self, parent: QtWidgets.QWidget, emoji: str, start: QtCore.QPoint):
        super().__init__(emoji, parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("font-size: 64px; background: transparent; border: none;")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedSize(90, 90)
        self.move(start)

        opacity_fx = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_fx)

        group = QtCore.QParallelAnimationGroup(self)

        pos_anim = QtCore.QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(900)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(QtCore.QPoint(start.x(), start.y() - 130))
        pos_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        fade_anim = QtCore.QPropertyAnimation(opacity_fx, b"opacity")
        fade_anim.setDuration(900)
        fade_anim.setStartValue(1.0)
        fade_anim.setEndValue(0.0)
        fade_anim.setEasingCurve(QtCore.QEasingCurve.InQuad)

        group.addAnimation(pos_anim)
        group.addAnimation(fade_anim)
        group.finished.connect(self.deleteLater)

        self.show()
        self.raise_()
        group.start()
        self._group = group  # prevent garbage-collection


class SoundManager:
    """Generates short audio feedback tones.  Silently degrades when unavailable."""

    def __init__(self):
        self._effects: dict = {}
        self._enabled = False
        if not _HAS_MULTIMEDIA:
            return
        try:
            self._tmp_dir = tempfile.mkdtemp(prefix="photo_deleter_sfx_")
            melodies = {
                "keep": [(523, 80), (659, 80), (784, 120)],
                "delete": [(370, 120), (311, 160)],
                "skip": [(440, 60)],
                "undo": [(523, 60), (440, 80)],
                "finish": [(523, 80), (659, 80), (784, 80), (1047, 200)],
            }
            for name, notes in melodies.items():
                path = self._make_wav(name, notes)
                effect = QSoundEffect()
                effect.setSource(QtCore.QUrl.fromLocalFile(path))
                effect.setVolume(0.4)
                self._effects[name] = effect
            self._enabled = True
        except Exception:
            pass

    # -- wav generation ------------------------------------------------
    _AMPLITUDE_SCALE = 0.25
    _ENVELOPE_FADE_S = 0.003  # seconds for attack / release ramp

    def _make_wav(self, name: str, notes: list) -> str:
        rate = 22050
        frames = bytearray()
        for freq, ms in notes:
            n = int(rate * ms / 1000)
            for i in range(n):
                t = i / rate
                env = min(1.0, i / max(1, rate * self._ENVELOPE_FADE_S)) * min(
                    1.0, (n - i) / max(1, rate * self._ENVELOPE_FADE_S)
                )
                val = int(self._AMPLITUDE_SCALE * env * math.sin(2 * math.pi * freq * t) * 32767)
                frames.extend(struct.pack("<h", max(-32767, min(32767, val))))
        path = os.path.join(self._tmp_dir, f"{name}.wav")
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(bytes(frames))
        return path

    def play(self, name: str):
        if self._enabled and name in self._effects:
            try:
                self._effects[name].play()
            except Exception:
                pass


class FinishDialog(QtWidgets.QDialog):
    """Confirmation dialog shown when the user clicks **Finish**."""

    def __init__(self, parent: QtWidgets.QWidget, kept_files: list, deleted_files: list):
        super().__init__(parent)
        self.setWindowTitle("Finish Session")
        self.setModal(True)
        self.setMinimumSize(480, 360)
        self._kept = kept_files
        self._deleted = deleted_files
        self.delete_confirmed = False
        self.restore_confirmed = False
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                    stop:0 {PALETTE["bg_base"]}, stop:1 {PALETTE["bg_mid"]});
            }}
            QLabel {{
                color: {PALETTE["text_primary"]};
                background: transparent;
            }}
            QCheckBox {{
                color: {PALETTE["text_primary"]};
                font-size: 14px;
                spacing: 10px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 20px; height: 20px;
                border: 2px solid {PALETTE["accent_lilac"]};
                border-radius: 4px;
                background: rgba(255,255,255,0.08);
            }}
            QCheckBox::indicator:checked {{
                background: {PALETTE["keep"]};
                border-color: {PALETTE["keep"]};
            }}
            """
        )

        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(30, 26, 30, 26)

        title = QtWidgets.QLabel("\U0001F389  Session Complete!")
        title.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {PALETTE['text_primary']};")
        title.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(title)

        summary = QtWidgets.QLabel(
            f"\U0001F4CA  {len(self._kept)} kept  \u2022  {len(self._deleted)} marked for deletion"
        )
        summary.setStyleSheet(f"font-size: 14px; color: {PALETTE['text_secondary']};")
        summary.setAlignment(QtCore.Qt.AlignCenter)
        summary.setWordWrap(True)
        lay.addWidget(summary)

        lay.addSpacing(6)

        self.delete_check = QtWidgets.QCheckBox(
            f"\U0001F5D1  Permanently delete {len(self._deleted)} photo(s)"
        )
        self.delete_check.setChecked(bool(self._deleted))
        self.delete_check.setEnabled(bool(self._deleted))
        lay.addWidget(self.delete_check)

        self.restore_check = QtWidgets.QCheckBox(
            f"\U0001F4C1  Restore {len(self._kept)} kept photo(s) to original folder"
        )
        self.restore_check.setChecked(bool(self._kept))
        self.restore_check.setEnabled(bool(self._kept))
        lay.addWidget(self.restore_check)

        lay.addSpacing(4)

        warn = QtWidgets.QLabel("\u26A0\uFE0F  Deleted photos are permanently removed and cannot be recovered.")
        warn.setStyleSheet(f"font-size: 12px; color: {PALETTE['delete']}; font-weight: 600;")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        lay.addStretch()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(12)

        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setFixedHeight(42)
        cancel.setCursor(QtCore.Qt.PointingHandCursor)
        cancel.setStyleSheet(
            f"""
            QPushButton {{
                border-radius: 12px;
                background: rgba(255,255,255,0.12);
                color: {PALETTE["text_primary"]};
                font-weight: 700;
                border: 1px solid rgba(255,255,255,0.25);
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.20); }}
            """
        )
        cancel.clicked.connect(self.reject)

        confirm = QtWidgets.QPushButton("\u2705  Confirm & Finish")
        confirm.setFixedHeight(42)
        confirm.setCursor(QtCore.Qt.PointingHandCursor)
        confirm.setStyleSheet(
            f"""
            QPushButton {{
                border-radius: 12px;
                background: {PALETTE["keep"]};
                color: {PALETTE["ink_dark"]};
                font-weight: 700;
                border: 1px solid rgba(255,255,255,0.35);
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {PALETTE["keep_hover"]}; }}
            """
        )
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

        self.body_font = pick_font(BODY_FONT_CANDIDATES)
        self.title_font = pick_font(TITLE_FONT_CANDIDATES)
        self.sound = SoundManager()

        self.setWindowTitle("Photo Deleter")
        self.setMinimumSize(900, 620)
        self.setObjectName("appRoot")
        self.setStyleSheet(self._app_stylesheet())

        self._build_ui()
        self._connect_shortcuts()

    def _app_stylesheet(self) -> str:
        return f"""
        #appRoot {{
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 {PALETTE["bg_base"]}, stop:0.55 {PALETTE["bg_mid"]}, stop:1 {PALETTE["bg_end"]});
        }}
        QLabel {{
            color: {PALETTE["text_primary"]};
            font-family: "{self.body_font}";
        }}
        #statusChip {{
            border-radius: 14px;
            padding: 7px 16px;
            color: {PALETTE["text_primary"]};
            border: 1px solid rgba(255, 255, 255, 0.22);
            font-weight: 700;
        }}
        #metaStrip {{
            background: {PALETTE["panel_bg"]};
            border: 2px solid {PALETTE["panel_border"]};
            border-radius: 16px;
        }}
        #fileLabel {{
            font-size: 17px;
            font-weight: 600;
        }}
        #actionLabel {{
            font-size: 12px;
            color: {PALETTE["text_muted"]};
        }}
        QProgressBar {{
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.22);
        }}
        QProgressBar::chunk {{
            border-radius: 6px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {PALETTE["accent_cyan"]}, stop:1 {PALETTE["accent_magenta"]});
        }}
        #windowPanel {{
            background: rgba(16, 10, 34, 0.34);
            border: 2px solid rgba(255, 255, 255, 0.24);
            border-radius: 18px;
        }}
        #windowChrome {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(250, 163, 236, 0.62), stop:1 rgba(120, 234, 255, 0.52));
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.28);
        }}
        #chromeMark {{
            min-width: 14px;
            max-width: 14px;
            min-height: 14px;
            max-height: 14px;
            border: 1px solid rgba(20, 15, 43, 0.34);
            border-radius: 3px;
            background: rgba(255, 255, 255, 0.44);
            color: rgba(20, 15, 43, 0.72);
            font-size: 10px;
            font-weight: 900;
        }}
        #accentBadge {{
            background: rgba(16, 22, 47, 0.57);
            border: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 10px;
            padding: 4px 10px;
            color: {PALETTE["text_primary"]};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        """

    def _button_style(self, base: str, hover: str) -> str:
        return f"""
        QPushButton {{
            border-radius: 14px;
            background-color: {base};
            color: {PALETTE["ink_dark"]};
            font-weight: 700;
            border: 1px solid rgba(255, 255, 255, 0.32);
            padding: 0 12px;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
        QPushButton:pressed {{
            background-color: {hover};
            padding-top: 1px;
        }}
        QPushButton:disabled {{
            background-color: rgba(255, 255, 255, 0.16);
            color: rgba(255, 255, 255, 0.5);
        }}
        """

    def _set_status(self, text: str, tone: str):
        styles = {
            "info": "background: rgba(169, 125, 252, 0.28);",
            "active": "background: rgba(83, 218, 255, 0.26); border-color: rgba(151, 238, 255, 0.62);",
            "success": "background: rgba(94, 247, 186, 0.26); border-color: rgba(125, 243, 197, 0.66);",
            "error": "background: rgba(255, 124, 172, 0.28); border-color: rgba(255, 176, 204, 0.66);",
        }
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(styles.get(tone, styles["info"]))

    def _build_ui(self):
        headline = QtWidgets.QLabel("PHOTO DELETER")
        headline.setStyleSheet(
            f"""
            font-size: 33px;
            font-weight: 700;
            color: {PALETTE["text_primary"]};
            letter-spacing: 2px;
            font-family: "{self.title_font}";
            """
        )

        tagline = QtWidgets.QLabel("Sort photos quickly with keyboard shortcuts and one-click actions.")
        tagline.setStyleSheet(f"font-size: 13px; color: {PALETTE['text_secondary']}; font-weight: 600;")

        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setSpacing(1)
        header_layout.addWidget(headline)
        header_layout.addWidget(tagline)

        badges_layout = QtWidgets.QHBoxLayout()
        badges_layout.setSpacing(8)
        for label in ["SHORTCUTS: ARROWS", "SPACE: SKIP", "CTRL+Z: UNDO"]:
            badge = QtWidgets.QLabel(label)
            badge.setObjectName("accentBadge")
            badges_layout.addWidget(badge)
        badges_layout.addStretch()
        header_layout.addLayout(badges_layout)

        self.status_chip = QtWidgets.QLabel("Waiting for folder ...")
        self.status_chip.setObjectName("statusChip")
        self.status_chip.setMinimumWidth(210)
        self._set_status("Waiting for folder ...", "info")

        header_row = QtWidgets.QHBoxLayout()
        header_row.setSpacing(14)
        header_row.addLayout(header_layout, stretch=1)
        header_row.addWidget(self.status_chip)

        chrome = QtWidgets.QFrame()
        chrome.setObjectName("windowChrome")
        chrome_layout = QtWidgets.QHBoxLayout(chrome)
        chrome_layout.setContentsMargins(10, 6, 10, 6)
        chrome_layout.setSpacing(8)
        for _ in range(1):
            mark = QtWidgets.QLabel("X")
            mark.setObjectName("chromeMark")
            mark.setAlignment(QtCore.Qt.AlignCenter)
            chrome_layout.addWidget(mark)
        chrome_text = QtWidgets.QLabel("session panel")
        chrome_text.setStyleSheet(f"color: {PALETTE['ink_dark']}; font-size: 11px; font-weight: 700;")
        chrome_layout.addWidget(chrome_text)
        chrome_layout.addStretch()

        self.image_card = ImageCard()

        self.file_label = QtWidgets.QLabel("")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setWordWrap(True)

        self.action_label = QtWidgets.QLabel("Last action: none yet.")
        self.action_label.setObjectName("actionLabel")

        info_strip = QtWidgets.QFrame()
        info_strip.setObjectName("metaStrip")
        info_layout = QtWidgets.QVBoxLayout(info_strip)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(4)
        info_layout.addWidget(self.file_label)
        info_layout.addWidget(self.action_label)

        self.keep_button = QtWidgets.QPushButton("Keep")
        self.delete_button = QtWidgets.QPushButton("Delete")
        self.skip_button = QtWidgets.QPushButton("Skip")
        self.undo_button = QtWidgets.QPushButton("Undo")

        buttons = [
            (self.keep_button, PALETTE["keep"], PALETTE["keep_hover"]),
            (self.delete_button, PALETTE["delete"], PALETTE["delete_hover"]),
            (self.skip_button, PALETTE["skip"], PALETTE["skip_hover"]),
            (self.undo_button, PALETTE["undo"], PALETTE["undo_hover"]),
        ]
        for button, base, hover in buttons:
            button.setFixedHeight(48)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setStyleSheet(self._button_style(base, hover))

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(12)
        controls_layout.addWidget(self.delete_button, stretch=1)
        controls_layout.addWidget(self.skip_button, stretch=1)
        controls_layout.addWidget(self.keep_button, stretch=1)
        controls_layout.addWidget(self.undo_button, stretch=1)

        # -- Finish button (hidden until session is complete) ----------
        self.finish_button = QtWidgets.QPushButton("\U0001F3C1  Finish")
        self.finish_button.setFixedHeight(48)
        self.finish_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.finish_button.setStyleSheet(
            f"""
            QPushButton {{
                border-radius: 14px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {PALETTE["accent_cyan"]}, stop:0.5 {PALETTE["accent_magenta"]},
                    stop:1 {PALETTE["accent_pink"]});
                color: {PALETTE["ink_dark"]};
                font-weight: 700;
                font-size: 15px;
                border: 2px solid rgba(255,255,255,0.45);
                padding: 0 18px;
            }}
            QPushButton:hover {{
                border-color: rgba(255,255,255,0.75);
            }}
            QPushButton:pressed {{
                padding-top: 1px;
            }}
            """
        )
        self.finish_button.clicked.connect(self._show_finish_dialog)
        self.finish_button.hide()

        choose_button = QtWidgets.QPushButton("Load Folder")
        choose_button.setMinimumWidth(210)
        choose_button.setFixedHeight(42)
        choose_button.setCursor(QtCore.Qt.PointingHandCursor)
        choose_button.setStyleSheet(
            """
            QPushButton {
                border-radius: 12px;
                padding: 10px 14px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7be8ff, stop:0.53 #bba8ff, stop:1 #ff8bd6);
                color: #140f2b;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #98f2ff, stop:0.53 #cab9ff, stop:1 #fface2);
            }
            QPushButton:pressed {
                padding-top: 11px;
            }
            """
        )
        choose_button.clicked.connect(self.choose_directory)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setFixedWidth(260)
        self.progress_bar.setTextVisible(False)

        self.progress_label = QtWidgets.QLabel("0 / 0 images sorted")
        self.progress_label.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px; font-weight: 600;")

        # -- live stat counters ----------------------------------------
        self.stat_kept_label = QtWidgets.QLabel("\U0001F4C1 0 kept")
        self.stat_kept_label.setStyleSheet(
            f"color: {PALETTE['keep']}; font-size: 11px; font-weight: 700; background: transparent;"
        )
        self.stat_deleted_label = QtWidgets.QLabel("\U0001F5D1 0 deleted")
        self.stat_deleted_label.setStyleSheet(
            f"color: {PALETTE['delete']}; font-size: 11px; font-weight: 700; background: transparent;"
        )
        self.stat_skipped_label = QtWidgets.QLabel("\u23ED 0 skipped")
        self.stat_skipped_label.setStyleSheet(
            f"color: {PALETTE['skip']}; font-size: 11px; font-weight: 700; background: transparent;"
        )

        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setSpacing(14)
        stats_row.addWidget(self.stat_kept_label)
        stats_row.addWidget(self.stat_deleted_label)
        stats_row.addWidget(self.stat_skipped_label)

        progress_layout = QtWidgets.QVBoxLayout()
        progress_layout.setSpacing(4)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addLayout(stats_row)

        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.setSpacing(14)
        footer_layout.addWidget(choose_button)
        footer_layout.addStretch()
        footer_layout.addLayout(progress_layout)

        panel = QtWidgets.QFrame()
        panel.setObjectName("windowPanel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(12)
        panel_layout.addWidget(chrome)
        panel_layout.addLayout(header_row)
        panel_layout.addWidget(self.image_card, stretch=1)
        panel_layout.addWidget(info_strip)
        panel_layout.addLayout(controls_layout)
        panel_layout.addWidget(self.finish_button)
        panel_layout.addLayout(footer_layout)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.addWidget(panel)

        self.keep_button.clicked.connect(self.keep_current)
        self.delete_button.clicked.connect(self.delete_current)
        self.skip_button.clicked.connect(self.skip_current)
        self.undo_button.clicked.connect(self.undo_last)

        self.update_controls(False)

    def _connect_shortcuts(self):
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.keep_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.delete_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.skip_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, activated=self.undo_last)

    def choose_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Image Directory")
        if not directory:
            return

        self.backend = ImageBackend(directory)
        self.history.clear()
        self.current_index = -1
        self.current_path = None
        self.kept_count = 0
        self.deleted_count = 0
        self.skipped_count = 0
        self.action_label.setText("Last action: none yet.")
        self.finish_button.hide()
        self._update_stats()
        self._set_status(f"Scanning {os.path.basename(directory)} ...", "info")
        QtCore.QTimer.singleShot(120, self.load_next_image)

    def load_next_image(self, advance_index=True):
        if not self.backend:
            return

        if advance_index:
            self.current_index += 1

        img_path = self.backend.get_image(self.current_index)
        if not img_path:
            self.image_card.set_message("\U0001F389 All images sorted!")
            self._set_status("Complete", "success")
            self.file_label.clear()
            self.update_progress()
            self.update_controls(False)
            self.finish_button.show()
            self.sound.play("finish")
            return

        pixmap = QtGui.QPixmap(img_path)
        if pixmap.isNull():
            self.image_card.set_message(f"Could not load {os.path.basename(img_path)}")
            self.file_label.setText("File might be corrupted.")
            self._set_status("Image load failed", "error")
            self.update_controls(False)
            return

        self.current_path = img_path
        self._apply_pixmap(pixmap)
        self.file_label.setText(os.path.basename(img_path))
        self._set_status("Ready", "active")
        self.update_progress()
        self.update_controls(True)

    def _apply_pixmap(self, pixmap: QtGui.QPixmap):
        self.image_card.set_image(pixmap)

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
        self.action_label.setText(f"Last action: kept {os.path.basename(dest)}")
        self._flash_card(PALETTE["keep"])
        self._show_reaction("\U0001F60A")
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
        self.action_label.setText(f"Last action: deleted {os.path.basename(dest)}")
        self._flash_card(PALETTE["delete"])
        self._show_reaction("\U0001F5D1\uFE0F")
        self.sound.play("delete")
        self._update_stats()
        self.current_index -= 1
        self.load_next_image()

    def skip_current(self):
        if not self.backend or not self.current_path:
            return
        self.skipped_count += 1
        self.action_label.setText(f"Last action: skipped {os.path.basename(self.current_path)}")
        self._show_reaction("\u23ED\uFE0F")
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
        self.action_label.setText(f"Last action: undo {action}")
        self._set_status("Undo complete", "active")
        self._show_reaction("\u21A9\uFE0F")
        self.sound.play("undo")
        self._update_stats()
        self.finish_button.hide()
        self.load_next_image()

    def update_progress(self):
        if not self.backend:
            self.progress_bar.setValue(0)
            self.progress_label.setText("0 / 0 images sorted")
            return
        total = self.backend.total_images
        processed = self.backend.processed_count()
        percent = int((processed / total) * 100) if total else 0
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{processed} / {total} images sorted")

    def update_controls(self, enabled):
        has_images = bool(enabled and self.backend and self.backend.remaining_count() > 0)
        self.keep_button.setEnabled(has_images)
        self.delete_button.setEnabled(has_images)
        self.skip_button.setEnabled(has_images)
        self.undo_button.setEnabled(bool(self.history))

    # -- visual / audio helpers ----------------------------------------

    def _update_stats(self):
        self.stat_kept_label.setText(f"\U0001F4C1 {self.kept_count} kept")
        self.stat_deleted_label.setText(f"\U0001F5D1 {self.deleted_count} deleted")
        self.stat_skipped_label.setText(f"\u23ED {self.skipped_count} skipped")

    def _show_reaction(self, emoji: str):
        """Float an emoji reaction over the image card."""
        card_center = self.image_card.rect().center()
        mapped = self.image_card.mapTo(self, card_center)
        start = QtCore.QPoint(mapped.x() - 45, mapped.y() - 45)
        FloatingReaction(self, emoji, start)

    _card_original_stylesheet: str = ""

    def _flash_card(self, color: str):
        """Briefly highlight the image-card border."""
        if not self._card_original_stylesheet:
            self._card_original_stylesheet = self.image_card.styleSheet()
        flash = f"""
        #imageCard {{
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(31, 17, 64, 0.97), stop:0.46 rgba(72, 45, 138, 0.94),
                stop:1 rgba(36, 101, 170, 0.92));
            border-radius: 22px;
            border: 3px solid {color};
        }}
        """
        self.image_card.setStyleSheet(flash)
        QtCore.QTimer.singleShot(
            280, lambda: self.image_card.setStyleSheet(self._card_original_stylesheet)
        )

    # -- finish dialog -------------------------------------------------

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
        summary = " \u2022 ".join(parts) if parts else "No changes made."
        self._set_status("Finished", "success")
        self.action_label.setText(summary)
        self.image_card.set_message("\u2728  All done!  \u2728")
        self.finish_button.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ImageSwiper()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
