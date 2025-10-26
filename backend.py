import os
import shutil
from typing import List, Optional


class ImageBackend:
    """Simple backend to iterate images and move them to kept/ or deleted/ directories.

    Contract:
    - inputs: path to images directory
    - outputs: file operations (move) into kept/ and deleted/ subfolders
    - error modes: permission errors and missing files
    - success: returns paths via get_image and performs move operations
    """

    SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

    def __init__(self, images_dir: str):
        self.images_dir = os.path.abspath(images_dir)
        self.kept_dir = os.path.join(self.images_dir, "kept")
        self.deleted_dir = os.path.join(self.images_dir, "deleted")
        os.makedirs(self.kept_dir, exist_ok=True)
        os.makedirs(self.deleted_dir, exist_ok=True)

        self._images = self._scan_images()

    def _scan_images(self) -> List[str]:
        files = []
        for entry in os.listdir(self.images_dir):
            path = os.path.join(self.images_dir, entry)
            if os.path.isfile(path):
                _, ext = os.path.splitext(entry.lower())
                if ext in self.SUPPORTED_EXT:
                    files.append(path)
        files.sort()
        return files

    def get_image(self, index: int) -> Optional[str]:
        if index < 0 or index >= len(self._images):
            return None
        return self._images[index]

    def _move(self, src: str, dest_dir: str) -> bool:
        try:
            filename = os.path.basename(src)
            dest = os.path.join(dest_dir, filename)
            # handle name collisions
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                i = 1
                while True:
                    new_name = f"{base}_{i}{ext}"
                    dest = os.path.join(dest_dir, new_name)
                    if not os.path.exists(dest):
                        break
                    i += 1
            shutil.move(src, dest)
            # remove from internal list
            if src in self._images:
                self._images.remove(src)
            return True
        except Exception as e:
            print(f"Move failed: {e}")
            return False

    def keep(self, path: str) -> bool:
        return self._move(path, self.kept_dir)

    def delete(self, path: str) -> bool:
        return self._move(path, self.deleted_dir)

    def remaining_count(self) -> int:
        return len(self._images)
