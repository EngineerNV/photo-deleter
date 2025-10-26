import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore
from backend import ImageBackend


class ImageSwiper(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend = None
        self.setWindowTitle("Photo Deleter - Image Swiper")
        self.setMinimumSize(800, 600)

        # UI elements
        self.image_label = QtWidgets.QLabel("Please choose a directory to start.", alignment=QtCore.Qt.AlignCenter)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.image_label.setStyleSheet("background-color: #222; color: #ddd")

        self.choose_dir_button = QtWidgets.QPushButton("Choose Directory")
        self.keep_button = QtWidgets.QPushButton("Keep")
        self.keep_button.setStyleSheet("background-color: #28a745; color: white;")
        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setStyleSheet("background-color: #dc3545; color: white;")

        # layout
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self.choose_dir_button)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.keep_button)
        btn_layout.addWidget(self.delete_button)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.image_label, stretch=1)
        main_layout.addLayout(btn_layout)

        # signals
        self.choose_dir_button.clicked.connect(self.choose_directory)
        self.keep_button.clicked.connect(self.keep_current)
        self.delete_button.clicked.connect(self.delete_current)

        # keyboard shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self, activated=self.delete_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self, activated=self.keep_current)
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.next_image)

        self.current_index = -1
        self.update_button_state()

    def choose_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Image Directory")
        if directory:
            self.backend = ImageBackend(directory)
            self.current_index = -1
            self.load_next()

    def update_button_state(self):
        has_backend = self.backend is not None
        has_images = has_backend and self.backend.remaining_count() > 0
        self.keep_button.setEnabled(has_images)
        self.delete_button.setEnabled(has_images)

    def load_next(self):
        if not self.backend:
            self.image_label.setText("Please choose a directory to start.")
            self.update_button_state()
            return

        self.current_index += 1
        img_path = self.backend.get_image(self.current_index)
        if img_path is None:
            self.image_label.setText("No more images")
            self.update_button_state()
            return

        pixmap = QtGui.QPixmap(img_path)
        if pixmap.isNull():
            self.image_label.setText(f"Failed to load: {os.path.basename(img_path)}")
            return

        # scale pixmap to label while keeping aspect ratio
        scaled = pixmap.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.setToolTip(img_path)
        self.update_button_state()

    def resizeEvent(self, event):
        # reload current image to rescale
        if not self.backend:
            return super().resizeEvent(event)
        img_path = self.backend.get_image(self.current_index)
        if img_path:
            pixmap = QtGui.QPixmap(img_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled)
        return super().resizeEvent(event)

    def keep_current(self):
        if not self.backend:
            return
        img = self.backend.get_image(self.current_index)
        if img:
            self.backend.keep(img)
            # Adjust index because backend removes the current item; keep pointer at same position
            self.current_index -= 1
        self.next_image()

    def delete_current(self):
        if not self.backend:
            return
        img = self.backend.get_image(self.current_index)
        if img:
            self.backend.delete(img)
            # Adjust index because backend removes the current item; keep pointer at same position
            self.current_index -= 1
        self.next_image()

    def next_image(self):
        self.load_next()


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = ImageSwiper()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
