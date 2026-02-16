import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

from backend import ImageBackend


PALETTE = {
    "bg_base": "#040714",
    "bg_mid": "#1a2055",
    "bg_end": "#08243e",
    "panel_bg": "rgba(8, 10, 26, 0.88)",
    "panel_border": "rgba(121, 233, 255, 0.30)",
    "text_primary": "#f6fbff",
    "text_secondary": "#cadbf1",
    "text_muted": "rgba(236, 246, 255, 0.72)",
    "accent_cyan": "#79e9ff",
    "accent_magenta": "#ff4ecf",
    "keep": "#1de8b1",
    "keep_hover": "#16bf90",
    "delete": "#ff5f6d",
    "delete_hover": "#de4957",
    "skip": "#ffba49",
    "skip_hover": "#dc9f37",
    "undo": "#4d8fff",
    "undo_hover": "#3f76d0",
}

BODY_FONT_CANDIDATES = ["Trebuchet MS", "Helvetica Neue", "Arial"]
TITLE_FONT_CANDIDATES = ["Trebuchet MS", "Avenir Next", "Helvetica Neue", "Arial"]


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
                background: rgba(10, 12, 28, 0.92);
                border-radius: 18px;
                border: 1px solid {PALETTE["panel_border"]};
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


class ImageSwiper(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.backend = None
        self.history = []
        self.current_index = -1
        self.current_path = None

        self.body_font = pick_font(BODY_FONT_CANDIDATES)
        self.title_font = pick_font(TITLE_FONT_CANDIDATES)

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
            border-radius: 12px;
            padding: 6px 14px;
            color: {PALETTE["text_primary"]};
            border: 1px solid rgba(255, 255, 255, 0.22);
        }}
        #metaStrip {{
            background: {PALETTE["panel_bg"]};
            border: 1px solid {PALETTE["panel_border"]};
            border-radius: 14px;
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
        }}
        QProgressBar::chunk {{
            border-radius: 6px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {PALETTE["accent_cyan"]}, stop:1 {PALETTE["accent_magenta"]});
        }}
        """

    def _button_style(self, base: str, hover: str) -> str:
        return f"""
        QPushButton {{
            border-radius: 12px;
            background-color: {base};
            color: #05131d;
            font-weight: 700;
            border: none;
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
            "info": "background: rgba(91, 108, 148, 0.30);",
            "active": "background: rgba(71, 196, 255, 0.24); border-color: rgba(121, 233, 255, 0.56);",
            "success": "background: rgba(47, 239, 170, 0.24); border-color: rgba(45, 229, 162, 0.58);",
            "error": "background: rgba(255, 93, 117, 0.25); border-color: rgba(255, 130, 141, 0.58);",
        }
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(styles.get(tone, styles["info"]))

    def _build_ui(self):
        headline = QtWidgets.QLabel("Photo Deleter")
        headline.setStyleSheet(
            f"""
            font-size: 34px;
            font-weight: 700;
            color: {PALETTE["text_primary"]};
            letter-spacing: 1px;
            font-family: "{self.title_font}";
            """
        )

        tagline = QtWidgets.QLabel("Flash through your folders, keep the sparks, delete the noise.")
        tagline.setStyleSheet(f"font-size: 14px; color: {PALETTE['text_secondary']};")

        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setSpacing(2)
        header_layout.addWidget(headline)
        header_layout.addWidget(tagline)

        self.status_chip = QtWidgets.QLabel("Waiting for folder ...")
        self.status_chip.setObjectName("statusChip")
        self.status_chip.setMinimumWidth(210)
        self._set_status("Waiting for folder ...", "info")

        header_row = QtWidgets.QHBoxLayout()
        header_row.setSpacing(14)
        header_row.addLayout(header_layout, stretch=1)
        header_row.addWidget(self.status_chip)

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

        choose_button = QtWidgets.QPushButton("Choose Directory")
        choose_button.setMinimumWidth(210)
        choose_button.setFixedHeight(42)
        choose_button.setCursor(QtCore.Qt.PointingHandCursor)
        choose_button.setStyleSheet(
            """
            QPushButton {
                border-radius: 12px;
                padding: 10px 14px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #79e9ff, stop:1 #ff4ecf);
                color: #02040d;
                font-weight: 700;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8ef5ff, stop:1 #ff79de);
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
        self.progress_label.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 12px;")

        progress_layout = QtWidgets.QVBoxLayout()
        progress_layout.setSpacing(6)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.setSpacing(14)
        footer_layout.addWidget(choose_button)
        footer_layout.addStretch()
        footer_layout.addLayout(progress_layout)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.setSpacing(16)
        main_layout.addLayout(header_row)
        main_layout.addWidget(self.image_card, stretch=1)
        main_layout.addWidget(info_strip)
        main_layout.addLayout(controls_layout)
        main_layout.addLayout(footer_layout)

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
        self.action_label.setText("Last action: none yet.")
        self._set_status(f"Scanning {os.path.basename(directory)} ...", "info")
        QtCore.QTimer.singleShot(120, self.load_next_image)

    def load_next_image(self, advance_index=True):
        if not self.backend:
            return

        if advance_index:
            self.current_index += 1

        img_path = self.backend.get_image(self.current_index)
        if not img_path:
            self.image_card.set_message("All images sorted")
            self._set_status("Complete", "success")
            self.file_label.clear()
            self.update_progress()
            self.update_controls(False)
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
        self.action_label.setText(f"Last action: kept {os.path.basename(dest)}")
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
        self.action_label.setText(f"Last action: deleted {os.path.basename(dest)}")
        self.current_index -= 1
        self.load_next_image()

    def skip_current(self):
        if not self.backend or not self.current_path:
            return
        self.action_label.setText(f"Last action: skipped {os.path.basename(self.current_path)}")
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
        idx = self.backend.index_of_image(restored)
        if idx >= 0:
            self.current_index = idx - 1
        self.action_label.setText(f"Last action: undo {action}")
        self._set_status("Undo complete", "active")
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

    def resizeEvent(self, event):
        super().resizeEvent(event)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ImageSwiper()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
