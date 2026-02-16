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
        self._total_images = len(self._images)

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

    @property
    def total_images(self) -> int:
        return self._total_images

    def processed_count(self) -> int:
        return self._total_images - len(self._images)

    def get_image(self, index: int) -> Optional[str]:
        if index < 0 or index >= len(self._images):
            return None
        return self._images[index]

    def _resolve_unique_destination(self, directory: str, filename: str) -> str:
        dest = os.path.join(directory, filename)
        if not os.path.exists(dest):
            return dest

        base, ext = os.path.splitext(filename)
        i = 1
        while True:
            new_name = f"{base}_{i}{ext}"
            dest = os.path.join(directory, new_name)
            if not os.path.exists(dest):
                return dest
            i += 1

    def _move(self, src: str, dest_dir: str) -> Optional[str]:
        try:
            filename = os.path.basename(src)
            dest = self._resolve_unique_destination(dest_dir, filename)
            shutil.move(src, dest)
            if src in self._images:
                self._images.remove(src)
            return dest
        except Exception as e:
            print(f"Move failed: {e}")
            return None

    def keep(self, path: str) -> Optional[str]:
        return self._move(path, self.kept_dir)

    def delete(self, path: str) -> Optional[str]:
        return self._move(path, self.deleted_dir)

    def undo_move(self, moved_path: str) -> Optional[str]:
        moved_path = os.path.abspath(moved_path)
        parent = os.path.dirname(moved_path)
        if parent not in {self.kept_dir, self.deleted_dir}:
            return None
        if not os.path.exists(moved_path):
            return None

        restored = self._move(moved_path, self.images_dir)
        if not restored:
            return None

        if restored not in self._images:
            self._images.append(restored)
            self._images.sort()
        return restored

    def index_of_image(self, path: str) -> int:
        path = os.path.abspath(path)
        try:
            return self._images.index(path)
        except ValueError:
            return -1

    def remaining_count(self) -> int:
        return len(self._images)
