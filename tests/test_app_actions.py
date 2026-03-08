import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from PyQt5 import QtWidgets
except ImportError:
    QtWidgets = None

from backend import ImageBackend

if QtWidgets is not None:
    from app import ImageSwiper
else:
    ImageSwiper = None

from PIL import Image


def write_fake_image(path: Path):
    image = Image.new("RGB", (1, 1), (255, 255, 255))
    image.save(path, format="PNG")


_QAPP = None


def get_qapp():
    global _QAPP
    if QtWidgets is None:
        return None
    if _QAPP is None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
        _QAPP = app
    return _QAPP


@unittest.skipIf(QtWidgets is None, "PyQt5 is not installed")
class AppActionTests(unittest.TestCase):
    def test_button_methods_keep_delete_undo(self):
        qapp = get_qapp()
        self.assertIsNotNone(qapp)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "frame.png"
            write_fake_image(source)

            swiper = ImageSwiper()
            swiper.backend = ImageBackend(str(tmp_path))
            swiper.current_index = 0
            swiper.current_path = str(source)

            swiper.keep_current()
            kept_path = tmp_path / "kept" / "frame.png"
            self.assertTrue(kept_path.exists())
            self.assertFalse(source.exists())
            self.assertEqual(len(swiper.history), 1)

            swiper.undo_last()
            self.assertTrue(source.exists())
            self.assertEqual(len(swiper.history), 0)

            swiper.current_path = str(source)
            swiper.delete_current()
            deleted_path = tmp_path / "deleted" / "frame.png"
            self.assertTrue(deleted_path.exists())
            self.assertFalse(source.exists())
            self.assertEqual(len(swiper.history), 1)

            swiper.undo_last()
            self.assertTrue(source.exists())
            self.assertEqual(len(swiper.history), 0)

    def test_stat_counters_update(self):
        qapp = get_qapp()
        self.assertIsNotNone(qapp)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for name in ("a.png", "b.png", "c.png"):
                write_fake_image(tmp_path / name)

            swiper = ImageSwiper()
            swiper.backend = ImageBackend(str(tmp_path))
            swiper.current_index = 0
            swiper.current_path = str(tmp_path / "a.png")

            swiper.keep_current()
            self.assertEqual(swiper.kept_count, 1)

            swiper.current_path = str(tmp_path / "b.png")
            swiper.delete_current()
            self.assertEqual(swiper.deleted_count, 1)

            swiper.current_path = str(tmp_path / "c.png")
            swiper.skip_current()
            self.assertEqual(swiper.skipped_count, 1)

    def test_finish_button_shown_when_complete(self):
        qapp = get_qapp()
        self.assertIsNotNone(qapp)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            write_fake_image(tmp_path / "only.png")

            swiper = ImageSwiper()
            swiper.backend = ImageBackend(str(tmp_path))
            self.assertTrue(swiper.finish_button.isHidden())

            swiper.current_index = 0
            swiper.current_path = str(tmp_path / "only.png")
            swiper.keep_current()
            # After the last image is sorted, finish button should no longer be hidden
            self.assertFalse(swiper.finish_button.isHidden())

    def test_load_next_image_skips_unreadable_files(self):
        qapp = get_qapp()
        self.assertIsNotNone(qapp)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bad = tmp_path / "bad.png"
            bad.write_text("not an image", encoding="utf-8")
            good = tmp_path / "good.png"
            write_fake_image(good)

            swiper = ImageSwiper()
            swiper.backend = ImageBackend(str(tmp_path))
            swiper.current_index = -1

            swiper.load_next_image()

            self.assertEqual(swiper.current_path, str(good))
            self.assertIn("good.png", swiper.file_label.text())
            self.assertIn("Skipped unreadable file", swiper.action_label.text())
            self.assertTrue(swiper.keep_button.isEnabled())



if __name__ == "__main__":
    unittest.main()
