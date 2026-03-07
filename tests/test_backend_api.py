import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from backend import ImageBackend


def write_fake_image(path: Path):
    image = Image.new("RGB", (1, 1), (255, 255, 255))
    image.save(path, format="PNG")


class BackendContractTests(unittest.TestCase):
    def test_keep_delete_and_undo_contract(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_path = tmp_path / "sample.png"
            write_fake_image(image_path)

            backend = ImageBackend(str(tmp_path))
            self.assertEqual(backend.total_images, 1)
            self.assertEqual(backend.get_image(0), str(image_path))

            kept_dest = backend.keep(str(image_path))
            self.assertIsNotNone(kept_dest)
            self.assertTrue(kept_dest.endswith("kept/sample.png"))
            self.assertFalse(image_path.exists())
            self.assertEqual(backend.remaining_count(), 0)
            self.assertEqual(backend.processed_count(), 1)

            restored_from_keep = backend.undo_move(kept_dest)
            self.assertEqual(restored_from_keep, str(image_path))
            self.assertTrue(image_path.exists())
            self.assertEqual(backend.remaining_count(), 1)
            self.assertEqual(backend.index_of_image(str(image_path)), 0)

            deleted_dest = backend.delete(str(image_path))
            self.assertIsNotNone(deleted_dest)
            self.assertTrue(deleted_dest.endswith("deleted/sample.png"))
            self.assertFalse(image_path.exists())
            self.assertEqual(backend.remaining_count(), 0)

            restored_from_delete = backend.undo_move(deleted_dest)
            self.assertEqual(restored_from_delete, str(image_path))
            self.assertTrue(image_path.exists())
            self.assertEqual(backend.remaining_count(), 1)

    def test_finish_delete_removes_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for name in ("a.png", "b.png", "c.png"):
                write_fake_image(tmp_path / name)

            backend = ImageBackend(str(tmp_path))
            self.assertEqual(backend.total_images, 3)

            # Delete two images
            backend.delete(str(tmp_path / "a.png"))
            backend.delete(str(tmp_path / "b.png"))

            deleted_files = backend.get_deleted_files()
            self.assertEqual(len(deleted_files), 2)
            self.assertTrue((tmp_path / "deleted").is_dir())

            count = backend.finish_delete()
            self.assertEqual(count, 2)
            self.assertFalse((tmp_path / "deleted").exists())

    def test_finish_restore_kept_moves_back(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for name in ("x.png", "y.png"):
                write_fake_image(tmp_path / name)

            backend = ImageBackend(str(tmp_path))
            backend.keep(str(tmp_path / "x.png"))
            backend.keep(str(tmp_path / "y.png"))

            kept_files = backend.get_kept_files()
            self.assertEqual(len(kept_files), 2)

            count = backend.finish_restore_kept()
            self.assertEqual(count, 2)
            # Files restored to original directory
            self.assertTrue((tmp_path / "x.png").exists())
            self.assertTrue((tmp_path / "y.png").exists())
            self.assertFalse((tmp_path / "kept").exists())

    def test_get_kept_and_deleted_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            write_fake_image(tmp_path / "img1.png")
            write_fake_image(tmp_path / "img2.png")

            backend = ImageBackend(str(tmp_path))
            self.assertEqual(backend.get_kept_files(), [])
            self.assertEqual(backend.get_deleted_files(), [])

            backend.keep(str(tmp_path / "img1.png"))
            backend.delete(str(tmp_path / "img2.png"))

            self.assertEqual(backend.get_kept_files(), ["img1.png"])
            self.assertEqual(backend.get_deleted_files(), ["img2.png"])


if __name__ == "__main__":
    unittest.main()
