# Photo Deleter API Contract

## Purpose
This file defines the behavior contract between the frontend (`app.py` controller plus the `widgets.py` / `theme.py` / `sounds.py` presentation modules) and `backend.py` (file operations + image list state). The backend is intentionally UI-agnostic and has no PyQt dependency on its move/undo logic, which keeps it unit-testable in isolation.

## Frontend Module Split
- `app.py` — `ImageSwiper` window/controller: session flow, keyboard/drag-drop, calls into the backend.
- `widgets.py` — reusable view components, none of which touch the filesystem:
  - `SwipeDeck` — gesture card stack. Emits `swiped("keep"|"delete")` and `inspect_requested()`. The controller, not the widget, performs the file move.
  - `Toast`, `FloatingEmoji`, `FullscreenViewer` — transient feedback and the zoom/pan inspector.
- `theme.py` — palette, font selection, and stylesheet builders (pure strings).
- `sounds.py` — `SoundManager`, runtime-synthesized WAV cues; degrades silently and supports muting.

## Domain Model
- `source_dir`: user-selected directory that contains sortable images.
- `kept_dir`: `<source_dir>/kept`
- `deleted_dir`: `<source_dir>/deleted`
- `image`: a file path in `source_dir` with extension in `SUPPORTED_EXT`.

## Backend Class
`ImageBackend(images_dir: str)`

### Invariants
- `images_dir` is normalized to absolute path.
- `kept_dir` and `deleted_dir` are created on init if missing.
- Internal `_images` tracks remaining sortable images in deterministic sorted order.
- `total_images` is the original count from init and does not change during a session.

### Public API
1. `get_image(index: int) -> Optional[str]`
- Returns absolute image path for remaining image at `index`.
- Returns `None` for out-of-range.

2. `keep(path: str) -> Optional[str]`
- Moves `path` from `source_dir` to `kept_dir`.
- Returns absolute destination path on success.
- Returns `None` on failure.

3. `delete(path: str) -> Optional[str]`
- Moves `path` from `source_dir` to `deleted_dir`.
- Returns absolute destination path on success.
- Returns `None` on failure.

4. `undo_move(moved_path: str) -> Optional[str]`
- Moves a previously moved file from `kept_dir` or `deleted_dir` back into `source_dir`.
- Restores with collision-safe naming if original name already exists.
- Inserts restored image path back into `_images` in sorted order.
- Returns restored absolute path on success.
- Returns `None` on failure.

5. `index_of_image(path: str) -> int`
- Returns index in current `_images`.
- Returns `-1` if not present.

6. `remaining_count() -> int`
- Count of currently unsorted images.

7. `processed_count() -> int`
- `total_images - remaining_count()`

8. `total_images` (property) -> `int`
- Original session image count.

9. `get_kept_files() -> List[str]` / `get_deleted_files() -> List[str]`
- Sorted filenames currently present in `kept_dir` / `deleted_dir`.
- Used to populate the Finish dialog summary.

10. `finish_delete() -> int`
- Permanently removes every file in `deleted_dir`, then removes the (now empty) directory.
- Returns the number of files removed. Irreversible.

11. `finish_restore_kept() -> int`
- Moves every file in `kept_dir` back to `source_dir` (collision-safe), then removes the directory.
- Returns the number of files restored.

## Move Semantics
- Collision policy for all move operations:
  - Keep original filename if free.
  - Else append `_1`, `_2`, ... before extension until free.
- On successful keep/delete:
  - File is moved on disk.
  - Source path is removed from `_images` if present.
- On successful undo:
  - File is moved back to `source_dir`.
  - Restored path is inserted back into `_images` if absent.

## UI Contract Expectations
- UI treats `keep`/`delete` result as `Optional[str]` destination path, never as boolean.
- UI history item shape: `(action: Literal["keep", "delete"], moved_path: str)`.
- Undo uses `undo_move(moved_path)` and then `index_of_image(restored_path)` to reposition current index.

## Error Handling
- Backend methods do not raise expected operational errors to UI for normal flow.
- Failure is represented by `None` return.
- Backend may log errors for diagnostics.

## Non-Goals (Current Contract)
- No permanent delete/trash integration.
- No recursive directory scan.
- No EXIF/metadata transforms.
