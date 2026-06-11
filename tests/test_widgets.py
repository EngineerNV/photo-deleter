import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except ImportError:
    QtWidgets = None

if QtWidgets is not None:
    from widgets import SwipeDeck, Toast, _ZoomImageView


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


def make_pixmap(w=24, h=24, color=QtCore.Qt.white if QtWidgets else None):
    pixmap = QtGui.QPixmap(w, h)
    pixmap.fill(color)
    return pixmap


def mouse_event(event_type, x, y):
    return QtGui.QMouseEvent(
        event_type,
        QtCore.QPointF(x, y),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )


@unittest.skipIf(QtWidgets is None, "PyQt5 is not installed")
class SwipeDeckTests(unittest.TestCase):
    def setUp(self):
        get_qapp()
        self.deck = SwipeDeck()
        self.deck.resize(600, 420)
        self.swipes = []
        self.deck.swiped.connect(self.swipes.append)

    def _press_drag_release(self, x0, x1, y=200):
        self.deck.mousePressEvent(mouse_event(QtCore.QEvent.MouseButtonPress, x0, y))
        self.deck.mouseMoveEvent(mouse_event(QtCore.QEvent.MouseMove, x1, y))
        self.deck.mouseReleaseEvent(mouse_event(QtCore.QEvent.MouseButtonRelease, x1, y))

    def _arm(self):
        self.deck.set_image(make_pixmap())
        self.deck.set_interactive(True)

    def test_set_image_makes_deck_have_image(self):
        self.assertFalse(self.deck.has_image)
        self.deck.set_image(make_pixmap())
        self.assertTrue(self.deck.has_image)

    def test_set_message_clears_image(self):
        self.deck.set_image(make_pixmap())
        self.deck.set_message("done", "hint")
        self.assertFalse(self.deck.has_image)

    def test_drag_right_past_threshold_emits_keep(self):
        self._arm()
        self._press_drag_release(300, 520)  # dx=220 > 600*0.28=168
        self.assertEqual(self.swipes, ["keep"])

    def test_drag_left_past_threshold_emits_delete(self):
        self._arm()
        self._press_drag_release(300, 80)  # dx=-220
        self.assertEqual(self.swipes, ["delete"])

    def test_small_drag_springs_back_without_signal(self):
        self._arm()
        self._press_drag_release(300, 310)  # dx=10, below fling minimum too
        self.assertEqual(self.swipes, [])
        self.assertIsNotNone(self.deck._spring_anim)

    def test_not_interactive_ignores_gestures(self):
        self.deck.set_image(make_pixmap())
        self.deck.set_interactive(False)
        self._press_drag_release(300, 520)
        self.assertEqual(self.swipes, [])

    def test_no_image_ignores_gestures(self):
        self.deck.set_interactive(True)
        self._press_drag_release(300, 520)
        self.assertEqual(self.swipes, [])

    def test_fly_out_without_image_is_noop(self):
        self.deck.fly_out("keep")
        self.assertIsNone(self.deck._exit)

    def test_fly_out_starts_exit_animation(self):
        self.deck.set_image(make_pixmap())
        self.deck.fly_out("keep")
        self.assertIsNotNone(self.deck._exit)
        self.assertEqual(self.deck._exit["dir"], "keep")

    def test_set_upcoming_filters_null_pixmaps(self):
        self.deck.set_upcoming([make_pixmap(), QtGui.QPixmap(), None])
        self.assertEqual(len(self.deck._upcoming), 1)

    def test_set_upcoming_caps_at_two(self):
        self.deck.set_upcoming([make_pixmap(), make_pixmap(), make_pixmap()])
        self.assertEqual(len(self.deck._upcoming), 2)

    def test_double_click_emits_inspect(self):
        hits = []
        self.deck.inspect_requested.connect(lambda: hits.append(True))
        self.deck.set_image(make_pixmap())
        self.deck.mouseDoubleClickEvent(
            mouse_event(QtCore.QEvent.MouseButtonDblClick, 300, 200)
        )
        self.assertEqual(hits, [True])

    def test_scaled_cache_reuses_results(self):
        pixmap = make_pixmap(100, 100)
        size = QtCore.QSize(50, 50)
        first = self.deck._scaled_for(pixmap, size)
        second = self.deck._scaled_for(pixmap, size)
        self.assertIs(first, second)

    def test_paint_runs_in_every_state(self):
        # Painting must never raise, whatever state the deck is in.
        for setup in (
            lambda: self.deck.set_message("welcome", "hint"),
            lambda: self.deck.set_image(make_pixmap()),
            lambda: self.deck.set_upcoming([make_pixmap(), make_pixmap()]),
            lambda: self.deck.fly_out("delete"),
            lambda: self.deck.set_drop_highlight(True),
        ):
            setup()
            image = QtGui.QImage(600, 420, QtGui.QImage.Format_ARGB32)
            self.deck.render(image)  # exercises paintEvent offscreen


@unittest.skipIf(QtWidgets is None, "PyQt5 is not installed")
class ToastTests(unittest.TestCase):
    def setUp(self):
        get_qapp()
        self.parent = QtWidgets.QWidget()
        self.parent.resize(800, 600)
        self.toast = Toast(self.parent)

    def test_starts_hidden(self):
        self.assertTrue(self.toast.isHidden())

    def test_popup_shows_text(self):
        self.toast.popup("Kept photo.jpg")
        self.assertFalse(self.toast.isHidden())
        self.assertEqual(self.toast.text(), "Kept photo.jpg")

    def test_popup_replaces_previous(self):
        self.toast.popup("first")
        self.toast.popup("second")
        self.assertEqual(self.toast.text(), "second")


@unittest.skipIf(QtWidgets is None, "PyQt5 is not installed")
class ZoomImageViewTests(unittest.TestCase):
    class _WheelStub:
        def __init__(self, dy):
            self._dy = dy

        def angleDelta(self):
            return QtCore.QPoint(0, self._dy)

    def setUp(self):
        get_qapp()
        self.view = _ZoomImageView(make_pixmap(200, 100))
        self.view.resize(400, 300)

    def test_zoom_in_increases_zoom(self):
        self.view.wheelEvent(self._WheelStub(120))
        self.assertGreater(self.view._zoom, 1.0)

    def test_zoom_never_drops_below_fit(self):
        self.view.wheelEvent(self._WheelStub(-120))
        self.assertEqual(self.view._zoom, 1.0)

    def test_zoom_is_clamped_at_max(self):
        for _ in range(60):
            self.view.wheelEvent(self._WheelStub(120))
        self.assertLessEqual(self.view._zoom, self.view.MAX_ZOOM)

    def test_double_click_resets_zoom_and_pan(self):
        self.view.wheelEvent(self._WheelStub(120))
        self.view._pan = QtCore.QPointF(40, 40)
        self.view.mouseDoubleClickEvent(
            mouse_event(QtCore.QEvent.MouseButtonDblClick, 10, 10)
        )
        self.assertEqual(self.view._zoom, 1.0)
        self.assertEqual(self.view._pan, QtCore.QPointF(0, 0))


if __name__ == "__main__":
    unittest.main()
