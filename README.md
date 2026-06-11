# Photo Deleter — Swipe to Triage Your Photos

A fast, keyboard-and-gesture-driven desktop app for sorting a folder of photos
into **keep** and **delete** piles. Built with Python and PyQt5, it borrows the
swipe-card mechanic from apps like Tinder and the calm, high-contrast styling of
modern product UIs — so triaging hundreds of photos feels quick and satisfying
instead of tedious.

## Highlights

- **Swipe to sort** — drag the photo card **right to keep**, **left to delete**.
  Cards rotate as you drag, show a live **KEEP / DELETE** stamp, fling on a flick,
  and spring back if you let go early.
- **Card deck** — the next two photos are previewed in a stack behind the current
  one, so you always know what's coming.
- **Round action buttons** — Undo · Delete · Skip · Keep, for when you'd rather
  click than swipe.
- **Full keyboard control** — `→` keep · `←` delete · `Space` skip · `Ctrl+Z`
  undo · `F` inspect · `M` mute · `O` open · `R` resume last folder.
- **Fullscreen inspector** — double-click (or press `F`) to open a photo
  fullscreen with **scroll-to-zoom** and **drag-to-pan**.
- **Synthesized sound design** — soft, non-intrusive cues for keep / delete /
  skip / undo / finish, generated at runtime (no bundled audio). Toggle with `M`.
- **Polished motion** — animated card transitions, floating-emoji celebration on
  completion, toast notifications, and an animated progress bar.
- **Drag & drop** — drop a folder straight onto the window to start.
- **Resume where you left off** — the app remembers your last folder.
- **Safe by default** — "delete" only **moves** files to a `deleted/` folder.
  Nothing is permanently removed until you confirm at the **Finish** step.

## How It Works

Photos are shown one at a time from the folder you choose. For each photo:

- **Keep** → moves it to a `kept/` subfolder.
- **Delete** → moves it to a `deleted/` subfolder.
- **Skip** → leaves it in place and moves on.
- **Undo** → reverses your last keep/delete.

`kept/` and `deleted/` are created automatically, and filename collisions are
handled by appending a number (e.g. `image_1.jpg`). When every photo is sorted,
the **Finish** dialog lets you choose to **permanently delete** the `deleted/`
pile and/or **restore** the `kept/` pile back to the original folder.

Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`.

## Project Layout

| File | Responsibility |
|------|----------------|
| `app.py` | Main window, controller, session flow |
| `widgets.py` | `SwipeDeck` (gesture card stack), `Toast`, `FloatingEmoji`, `FullscreenViewer` |
| `theme.py` | Design tokens (palette, fonts) and stylesheet builders |
| `sounds.py` | Runtime-synthesized UI sound effects |
| `backend.py` | File operations + remaining-image state (UI-agnostic) |
| `tests/` | Backend contract, app actions, and widget/gesture tests |

## Installation

Requires Python 3 and PyQt5.

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd photo-deleter
   ```

2. **Create and activate a virtual environment (recommended):**
   - macOS/Linux:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - Windows:
     ```bash
     python -m venv .venv
     .venv\Scripts\activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Run

```bash
python app.py
```

## Usage

1. **Open a folder** — click **Open Folder**, press `O`, or drag a folder onto
   the window.
2. **Sort** — swipe the card right/left, use the round buttons, or use the
   keyboard shortcuts. Double-click a photo (or press `F`) to inspect it
   fullscreen.
3. **Finish** — when all photos are sorted, click **Finish session** and choose
   whether to permanently delete and/or restore.

Your sorted photos live in the `kept/` and `deleted/` subfolders of the folder
you selected.

## Testing

The full suite runs headless — no manual clicking, no display required:

```bash
pytest -q
```

On a headless machine, force Qt's offscreen platform:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

Coverage includes the backend file-operation contract, the app's
keep/delete/skip/undo actions, and the swipe-gesture logic (threshold swipes,
fling detection, spring-back, fullscreen zoom clamping, and paint-in-every-state
safety).
