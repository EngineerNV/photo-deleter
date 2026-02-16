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


if __name__ == "__main__":
    unittest.main()
