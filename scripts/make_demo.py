"""Generate visual demo assets for the README.

Renders the *real* PhotoDeleter UI offscreen (no display needed) and captures:
  - docs/demo.gif        an animated swipe-to-sort walkthrough
  - docs/screenshot.png  a static hero shot

Run:  QT_QPA_PLATFORM=offscreen python scripts/make_demo.py
"""

import math
import os
import sys
import tempfile

from PIL import Image, ImageDraw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402

from app import ImageSwiper  # noqa: E402

WIN_W, WIN_H = 960, 700
DOCS = os.path.join(ROOT, "docs")

# A pleasant set of sample "photos" so the deck looks real.
SAMPLES = [
    ("Sunrise", (255, 168, 92), (255, 92, 138)),
    ("Harbor", (92, 200, 255), (60, 110, 200)),
    ("Forest", (120, 220, 150), (30, 120, 90)),
    ("Dunes", (240, 210, 120), (200, 130, 70)),
    ("Twilight", (150, 130, 240), (60, 50, 130)),
    ("Coral", (255, 140, 170), (220, 80, 120)),
]


def make_sample(path, label, c1, c2, w=1000, h=750):
    """A diagonal-gradient image with a soft sun disc and a caption bar."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(0, w, 2):  # step 2 for speed; fill the gap below
            t = ((x / w) + (y / h)) / 2
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            px[x, y] = (r, g, b)
            if x + 1 < w:
                px[x + 1, y] = (r, g, b)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse([w * 0.62, h * 0.12, w * 0.62 + 180, h * 0.12 + 180],
                 fill=(255, 255, 255, 60))
    draw.ellipse([w * 0.66, h * 0.16, w * 0.66 + 110, h * 0.16 + 110],
                 fill=(255, 255, 255, 90))
    draw.rectangle([0, h - 70, w, h], fill=(0, 0, 0, 90))
    draw.text((28, h - 52), f"IMG  ·  {label}", fill=(255, 255, 255, 230))
    img.save(path)


def grab(window) -> Image.Image:
    """Render the window to a PIL image."""
    QtWidgets.QApplication.processEvents()
    pixmap = window.grab()
    qimg = pixmap.toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
    ptr = qimg.bits()
    ptr.setsize(qimg.byteCount())
    return Image.frombytes("RGBA", (qimg.width(), qimg.height()),
                           bytes(ptr)).convert("RGB")


def settle(deck):
    """Force entrance animation to its final state for deterministic frames."""
    if deck._enter_anim is not None:
        deck._enter_anim.stop()
    deck._enter = 1.0


def set_drag(window, deck, dx, dy=12):
    deck._drag = QtCore.QPointF(dx, dy)
    deck.update()
    return grab(window)


def set_exit(window, deck, pixmap, direction, t, off0):
    deck._exit = {"pix": pixmap, "t": t, "dir": direction,
                  "off0": off0, "ang0": 14.0 * off0.x() / max(1, deck.width())}
    deck.update()
    return grab(window)


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    tmp = tempfile.mkdtemp(prefix="demo_photos_")
    for i, (label, c1, c2) in enumerate(SAMPLES):
        make_sample(os.path.join(tmp, f"{i:02d}_{label}.png"), label, c1, c2)

    window = ImageSwiper()
    window.sound.set_muted(True)
    window.resize(WIN_W, WIN_H)
    window.show()
    QtWidgets.QApplication.processEvents()

    os.makedirs(DOCS, exist_ok=True)
    frames = []      # list of PIL images
    durations = []   # ms per frame (parallel to `frames`)

    def add(img, ms=90):
        frames.append(img)
        durations.append(ms)

    def hold(img, ms):
        # A single frame shown for `ms` — avoids Pillow merging duplicates.
        add(img, ms)

    # 1) Welcome screen
    hold(grab(window), 1400)

    # 2) Load the folder
    window.load_directory(tmp)
    deck = window.deck
    settle(deck)
    hold(grab(window), 1100)

    threshold = WIN_W * deck.SWIPE_THRESHOLD_RATIO

    def swipe(direction):
        """Animate a drag, then the card flying out, then the next card."""
        sign = 1.0 if direction == "keep" else -1.0
        current = deck._pixmap
        # drag the card toward the edge, stamp growing
        for k in range(0, 7):
            dx = sign * threshold * (k / 6.0) * 1.15
            add(set_drag(window, deck, dx), 70)
        off0 = QtCore.QPointF(sign * threshold * 1.15, 12)
        # commit the action (moves the file, advances the deck)
        if direction == "keep":
            window.keep_current()
        else:
            window.delete_current()
        settle(deck)
        # render the fly-out using the snapshot we captured
        for k in range(1, 6):
            add(set_exit(window, deck, current, direction, k / 5.0, off0), 60)
        deck._exit = None
        hold(grab(window), 650)

    swipe("keep")
    swipe("delete")
    swipe("keep")

    # 3) An undo, to show it in action
    window.undo_last()
    settle(deck)
    hold(grab(window), 1100)

    # 4) Capture a clean hero screenshot here (card centered, stats populated)
    hero = grab(window)
    hero.save(os.path.join(DOCS, "screenshot.png"), optimize=True)

    # 5) Fast-forward to the celebration screen
    while window.current_path:
        window.keep_current()
        settle(deck)
    hold(grab(window), 1900)

    # Downscale for a tighter GIF, then save (palette-optimized, looping)
    scaled = [f.resize((WIN_W // 2, WIN_H // 2), Image.LANCZOS) for f in frames]
    gif_path = os.path.join(DOCS, "demo.gif")
    scaled[0].save(
        gif_path,
        save_all=True,
        append_images=scaled[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )

    print(f"Wrote {gif_path} ({len(scaled)} frames)")
    print(f"Wrote {os.path.join(DOCS, 'screenshot.png')}")


if __name__ == "__main__":
    main()
