"""Custom widgets for Photo Deleter.

SwipeDeck       — Tinder-style draggable card stack with rotation, stamps,
                  fling detection, spring-back, exit/entrance animations.
Toast           — transient feedback pill that fades in and out.
FloatingEmoji   — celebratory emoji that floats upward and fades.
FullscreenViewer— frameless fullscreen image inspector with zoom & pan.
"""

import time

from PyQt5 import QtCore, QtGui, QtWidgets

from theme import PALETTE


def _rounded(rect: QtCore.QRectF, radius: float) -> QtGui.QPainterPath:
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


class SwipeDeck(QtWidgets.QWidget):
    """Draggable photo card with a stacked deck behind it.

    Drag right past the threshold (or fling) to emit ``swiped("keep")``,
    left for ``swiped("delete")``. Releasing early springs the card back.
    ``fly_out`` plays the same exit animation when actions come from
    buttons or keyboard so every path feels identical.
    """

    swiped = QtCore.pyqtSignal(str)  # "keep" | "delete"
    inspect_requested = QtCore.pyqtSignal()

    SWIPE_THRESHOLD_RATIO = 0.28
    FLING_VELOCITY = 0.85  # px / ms
    RADIUS = 20
    STACK_DY = 13
    STACK_SCALE = 0.045
    MARGIN = 10

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(360)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self._pixmap = None
        self._upcoming = []  # scaled pixmaps for the cards behind
        self._message = "Drop a folder here to begin"
        self._hint = ""
        self._interactive = False
        self._drop_highlight = False

        self._drag = QtCore.QPointF(0, 0)
        self._dragging = False
        self._press_pos = None
        self._samples = []  # (ms, x) for fling velocity

        self._enter = 1.0
        self._enter_anim = None
        self._spring_anim = None
        self._exit = None  # dict: pix, t, dir, off0, ang0
        self._exit_anim = None

        self._scaled_cache = {}

    # -- public API ------------------------------------------------------

    def set_image(self, pixmap: QtGui.QPixmap):
        self._pixmap = pixmap
        self._message = None
        self._hint = ""
        self._reset_drag()
        self._animate_enter()
        self.update()

    def set_upcoming(self, pixmaps: list):
        self._upcoming = [p for p in pixmaps if p is not None and not p.isNull()][:2]
        self.update()

    def set_message(self, message: str, hint: str = ""):
        self._pixmap = None
        self._upcoming = []
        self._message = message
        self._hint = hint
        self._reset_drag()
        self.update()

    def set_interactive(self, interactive: bool):
        self._interactive = bool(interactive)
        self.setCursor(
            QtCore.Qt.OpenHandCursor if self._interactive else QtCore.Qt.ArrowCursor
        )

    def set_drop_highlight(self, on: bool):
        self._drop_highlight = bool(on)
        self.update()

    @property
    def has_image(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    def fly_out(self, direction: str):
        """Animate the current card off-screen. direction: keep|delete|skip."""
        if not self.has_image:
            return
        self._exit = {
            "pix": self._pixmap,
            "t": 0.0,
            "dir": direction,
            "off0": QtCore.QPointF(self._drag),
            "ang0": self._current_angle(),
        }
        self._reset_drag()
        self._exit_anim = QtCore.QVariantAnimation(self)
        self._exit_anim.setStartValue(0.0)
        self._exit_anim.setEndValue(1.0)
        self._exit_anim.setDuration(380)
        self._exit_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        self._exit_anim.valueChanged.connect(self._on_exit_tick)
        self._exit_anim.finished.connect(self._on_exit_done)
        self._exit_anim.start()

    # -- animation plumbing -----------------------------------------------

    def _on_exit_tick(self, value):
        if self._exit is not None:
            self._exit["t"] = float(value)
            self.update()

    def _on_exit_done(self):
        self._exit = None
        self.update()

    def _animate_enter(self):
        if self._enter_anim is not None:
            self._enter_anim.stop()
        self._enter = 0.0
        anim = QtCore.QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(260)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._on_enter_tick)
        anim.start()
        self._enter_anim = anim

    def _on_enter_tick(self, value):
        self._enter = float(value)
        self.update()

    def _reset_drag(self):
        if self._spring_anim is not None:
            self._spring_anim.stop()
            self._spring_anim = None
        self._drag = QtCore.QPointF(0, 0)
        self._dragging = False
        self._press_pos = None
        self._samples = []

    def _spring_back(self):
        anim = QtCore.QVariantAnimation(self)
        anim.setStartValue(QtCore.QPointF(self._drag))
        anim.setEndValue(QtCore.QPointF(0, 0))
        anim.setDuration(340)
        anim.setEasingCurve(QtCore.QEasingCurve.OutBack)
        anim.valueChanged.connect(self._on_spring_tick)
        anim.start()
        self._spring_anim = anim

    def _on_spring_tick(self, value):
        self._drag = QtCore.QPointF(value)
        self.update()

    def _current_angle(self) -> float:
        area = self._card_area()
        return 14.0 * self._drag.x() / max(1.0, float(area.width()))

    # -- gestures ----------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._interactive and self.has_image:
            self._reset_drag()
            self._dragging = True
            self._press_pos = QtCore.QPointF(event.pos())
            self._samples = [(time.monotonic() * 1000.0, float(event.pos().x()))]
            self.setCursor(QtCore.Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._dragging and self._press_pos is not None:
            self._drag = QtCore.QPointF(event.pos()) - self._press_pos
            self._samples.append((time.monotonic() * 1000.0, float(event.pos().x())))
            if len(self._samples) > 6:
                self._samples.pop(0)
            self.update()

    def mouseReleaseEvent(self, event):
        if not self._dragging:
            return
        self._dragging = False
        self.setCursor(QtCore.Qt.OpenHandCursor)

        dx = self._drag.x()
        threshold = self.width() * self.SWIPE_THRESHOLD_RATIO
        velocity = self._fling_velocity()

        if dx > threshold or (velocity > self.FLING_VELOCITY and dx > 24):
            self.swiped.emit("keep")
        elif dx < -threshold or (velocity < -self.FLING_VELOCITY and dx < -24):
            self.swiped.emit("delete")
        else:
            self._spring_back()

    def mouseDoubleClickEvent(self, event):
        if self.has_image:
            self.inspect_requested.emit()

    def _fling_velocity(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        t0, x0 = self._samples[0]
        t1, x1 = self._samples[-1]
        dt = max(1.0, t1 - t0)
        return (x1 - x0) / dt

    # -- painting -----------------------------------------------------------

    def _card_area(self) -> QtCore.QRect:
        m = self.MARGIN
        reserve = 2 * self.STACK_DY + 4
        return self.rect().adjusted(m, m, -m, -(m + reserve))

    def _scaled_for(self, pixmap: QtGui.QPixmap, size: QtCore.QSize) -> QtGui.QPixmap:
        key = (pixmap.cacheKey(), size.width(), size.height())
        cached = self._scaled_cache.get(key)
        if cached is not None:
            return cached
        scaled = pixmap.scaled(size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        if len(self._scaled_cache) > 12:
            self._scaled_cache.clear()
        self._scaled_cache[key] = scaled
        return scaled

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHints(
            QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform
        )
        area = self._card_area()

        if self._message is not None:
            self._paint_placeholder(painter, area)
            if self._exit is not None:
                self._paint_exit(painter, area)
            self._paint_drop_highlight(painter)
            return

        # Cards behind the current one (deepest first)
        for depth in (2, 1):
            if len(self._upcoming) >= depth:
                self._paint_back_card(painter, area, self._upcoming[depth - 1], depth)

        if self.has_image:
            self._paint_front_card(painter, area)

        if self._exit is not None:
            self._paint_exit(painter, area)

        self._paint_drop_highlight(painter)

    def _paint_back_card(self, painter, area, pixmap, depth):
        scale = 1.0 - self.STACK_SCALE * depth
        dy = self.STACK_DY * depth
        w = area.width() * scale
        h = area.height() * scale
        rect = QtCore.QRectF(
            area.center().x() - w / 2.0,
            area.y() + (area.height() - h) + dy - (area.height() - h) / 2.0,
            w,
            h,
        )
        painter.save()
        painter.setOpacity(0.55 if depth == 1 else 0.28)
        painter.setClipPath(_rounded(rect, self.RADIUS * scale))
        painter.fillRect(rect, QtGui.QColor(PALETTE["surface_high"]))
        scaled = self._scaled_for(pixmap, rect.size().toSize())
        painter.drawPixmap(
            int(rect.x() + (rect.width() - scaled.width()) / 2),
            int(rect.y() + (rect.height() - scaled.height()) / 2),
            scaled,
        )
        painter.fillRect(rect, QtGui.QColor(0, 0, 0, 110))
        painter.restore()

    def _paint_card(self, painter, area, pixmap, offset, angle, opacity, scale, stamp=None, stamp_opacity=0.0):
        center = QtCore.QPointF(area.center())
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, opacity)))
        painter.translate(center + offset)
        painter.rotate(angle)
        painter.scale(scale, scale)
        painter.translate(-center)

        rect = QtCore.QRectF(area)
        painter.setClipPath(_rounded(rect, self.RADIUS))
        painter.fillRect(rect, QtGui.QColor(PALETTE["surface_high"]))

        scaled = self._scaled_for(pixmap, rect.size().toSize())
        painter.drawPixmap(
            int(rect.x() + (rect.width() - scaled.width()) / 2),
            int(rect.y() + (rect.height() - scaled.height()) / 2),
            scaled,
        )

        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 26))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawPath(_rounded(rect.adjusted(1, 1, -1, -1), self.RADIUS))

        if stamp and stamp_opacity > 0.02:
            self._paint_stamp(painter, rect, stamp, stamp_opacity)

        painter.restore()

    def _paint_stamp(self, painter, rect, kind, opacity):
        is_keep = kind == "keep"
        text = "KEEP" if is_keep else "DELETE"
        color = QtGui.QColor(PALETTE["keep" if is_keep else "delete"])
        color.setAlphaF(max(0.0, min(1.0, opacity)))

        font = QtGui.QFont(painter.font())
        font.setPointSize(26)
        font.setBold(True)
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 2.5)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        tw = metrics.horizontalAdvance(text)
        th = metrics.height()
        pad = 10

        painter.save()
        if is_keep:
            painter.translate(rect.x() + 34, rect.y() + 40)
            painter.rotate(-14)
        else:
            painter.translate(rect.right() - tw - 2 * pad - 34, rect.y() + 40)
            painter.rotate(14)

        box = QtCore.QRectF(0, 0, tw + 2 * pad, th + 2 * (pad - 4))
        pen = QtGui.QPen(color)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(box, 8, 8)
        painter.drawText(box, QtCore.Qt.AlignCenter, text)
        painter.restore()

    def _paint_front_card(self, painter, area):
        enter = self._enter
        offset = QtCore.QPointF(self._drag.x(), self._drag.y() * 0.4 + (1.0 - enter) * 18.0)
        angle = self._current_angle()
        scale = 0.94 + 0.06 * enter
        opacity = 0.25 + 0.75 * enter

        threshold = max(1.0, self.width() * self.SWIPE_THRESHOLD_RATIO)
        dx = self._drag.x()
        stamp = "keep" if dx > 0 else ("delete" if dx < 0 else None)
        stamp_opacity = min(1.0, abs(dx) / threshold)

        self._paint_card(
            painter, area, self._pixmap, offset, angle, opacity, scale,
            stamp=stamp, stamp_opacity=stamp_opacity,
        )

    def _paint_exit(self, painter, area):
        ex = self._exit
        t = ex["t"]
        direction = ex["dir"]
        off0 = ex["off0"]
        w = float(max(1, self.width()))

        if direction == "skip":
            offset = QtCore.QPointF(off0.x(), off0.y() + t * self.height() * 0.55)
            angle = ex["ang0"]
            stamp = None
        else:
            sign = 1.0 if direction == "keep" else -1.0
            target_x = sign * w * 1.25
            offset = QtCore.QPointF(
                off0.x() + (target_x - off0.x()) * t,
                off0.y() * 0.4 + t * 36.0,
            )
            angle = ex["ang0"] + sign * 24.0 * t
            stamp = direction

        self._paint_card(
            painter, area, ex["pix"], offset, angle, 1.0 - t, 1.0,
            stamp=stamp, stamp_opacity=1.0 - t * 0.6,
        )

    def _paint_placeholder(self, painter, area):
        rect = QtCore.QRectF(area)
        painter.save()
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 34))
        pen.setWidth(2)
        pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QtGui.QColor(255, 255, 255, 6))
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

        painter.setPen(QtGui.QColor(PALETTE["text_secondary"]))
        font = QtGui.QFont(painter.font())
        font.setPointSize(15)
        font.setBold(True)
        painter.setFont(font)
        text_rect = rect.adjusted(20, 0, -20, -14 if self._hint else 0)
        painter.drawText(text_rect, QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap, self._message)

        if self._hint:
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(PALETTE["text_muted"]))
            hint_rect = QtCore.QRectF(rect.x() + 20, rect.center().y() + 22, rect.width() - 40, 60)
            painter.drawText(hint_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop | QtCore.Qt.TextWordWrap, self._hint)
        painter.restore()

    def _paint_drop_highlight(self, painter):
        if not self._drop_highlight:
            return
        rect = QtCore.QRectF(self.rect()).adjusted(3, 3, -3, -3)
        pen = QtGui.QPen(QtGui.QColor(PALETTE["accent"]))
        pen.setWidth(3)
        pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QtGui.QColor(91, 140, 255, 26))
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)


class Toast(QtWidgets.QLabel):
    """A transient feedback pill that fades in, holds, and fades out."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet(
            f"""
            background: {PALETTE["surface_overlay"]};
            color: {PALETTE["text"]};
            border: 1px solid {PALETTE["border_strong"]};
            border-radius: 16px;
            padding: 8px 18px;
            font-size: 13px;
            font-weight: 700;
            """
        )
        self._effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._group = None
        self.hide()

    def popup(self, text: str, duration_ms: int = 1300):
        if self._group is not None:
            self._group.stop()
        self.setText(text)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

        fade_in = QtCore.QPropertyAnimation(self._effect, b"opacity")
        fade_in.setDuration(140)
        fade_in.setStartValue(self._effect.opacity())
        fade_in.setEndValue(1.0)

        hold = QtCore.QPauseAnimation(duration_ms)

        fade_out = QtCore.QPropertyAnimation(self._effect, b"opacity")
        fade_out.setDuration(320)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QtCore.QEasingCurve.InQuad)

        group = QtCore.QSequentialAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addAnimation(hold)
        group.addAnimation(fade_out)
        group.finished.connect(self.hide)
        group.start()
        self._group = group

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 96
        self.move(max(0, x), max(0, y))


class FloatingEmoji(QtWidgets.QLabel):
    """An emoji that floats upward and fades out — used for celebrations."""

    def __init__(self, parent: QtWidgets.QWidget, emoji: str, start: QtCore.QPoint):
        super().__init__(emoji, parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("font-size: 44px; background: transparent; border: none;")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedSize(64, 64)
        self.move(start)

        effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)

        group = QtCore.QParallelAnimationGroup(self)

        pos_anim = QtCore.QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(1100)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(QtCore.QPoint(start.x(), start.y() - 150))
        pos_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        fade_anim = QtCore.QPropertyAnimation(effect, b"opacity")
        fade_anim.setDuration(1100)
        fade_anim.setStartValue(1.0)
        fade_anim.setEndValue(0.0)
        fade_anim.setEasingCurve(QtCore.QEasingCurve.InQuad)

        group.addAnimation(pos_anim)
        group.addAnimation(fade_anim)
        group.finished.connect(self.deleteLater)

        self.show()
        self.raise_()
        group.start()
        self._group = group  # prevent garbage collection


class _ZoomImageView(QtWidgets.QWidget):
    """Pannable, zoomable image canvas for the fullscreen viewer."""

    MAX_ZOOM = 6.0

    def __init__(self, pixmap: QtGui.QPixmap):
        super().__init__()
        self._pixmap = pixmap
        self._zoom = 1.0  # multiplier on top of fit-to-window scale
        self._pan = QtCore.QPointF(0, 0)
        self._panning = False
        self._last_pos = None
        self.setCursor(QtCore.Qt.OpenHandCursor)

    def _fit_scale(self) -> float:
        if self._pixmap.isNull():
            return 1.0
        return min(
            self.width() / max(1, self._pixmap.width()),
            self.height() / max(1, self._pixmap.height()),
        )

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QtGui.QColor("#06080b"))
        if self._pixmap.isNull():
            return
        scale = self._fit_scale() * self._zoom
        w = self._pixmap.width() * scale
        h = self._pixmap.height() * scale
        x = (self.width() - w) / 2 + self._pan.x()
        y = (self.height() - h) / 2 + self._pan.y()
        painter.drawPixmap(QtCore.QRectF(x, y, w, h).toRect(), self._pixmap)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.12 if delta > 0 else 1 / 1.12
        new_zoom = max(1.0, min(self.MAX_ZOOM, self._zoom * factor))
        if new_zoom == 1.0:
            self._pan = QtCore.QPointF(0, 0)
        self._zoom = new_zoom
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._panning and self._last_pos is not None and self._zoom > 1.0:
            delta = event.pos() - self._last_pos
            self._pan += QtCore.QPointF(delta)
            self._last_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self._panning = False
        self.setCursor(QtCore.Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):
        self._zoom = 1.0
        self._pan = QtCore.QPointF(0, 0)
        self.update()


class FullscreenViewer(QtWidgets.QDialog):
    """Distraction-free fullscreen inspector. Esc or ✕ closes; wheel zooms."""

    def __init__(self, parent, pixmap: QtGui.QPixmap, caption: str = ""):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setModal(True)

        view = _ZoomImageView(pixmap)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        close_btn = QtWidgets.QPushButton("✕", self)
        close_btn.setFixedSize(40, 40)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                border-radius: 20px;
                background: {PALETTE["surface_overlay"]};
                color: {PALETTE["text"]};
                border: 1px solid {PALETTE["border_strong"]};
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {PALETTE["surface_high"]}; }}
            """
        )
        close_btn.clicked.connect(self.reject)
        self._close_btn = close_btn

        if caption:
            cap = QtWidgets.QLabel(caption, self)
            cap.setStyleSheet(
                f"""
                background: {PALETTE["surface_overlay"]};
                color: {PALETTE["text_secondary"]};
                border-radius: 12px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
                """
            )
            cap.adjustSize()
            self._caption = cap
        else:
            self._caption = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._close_btn.move(self.width() - self._close_btn.width() - 18, 18)
        if self._caption is not None:
            self._caption.adjustSize()
            self._caption.move(
                (self.width() - self._caption.width()) // 2,
                self.height() - self._caption.height() - 22,
            )
