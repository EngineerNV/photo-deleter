"""Synthesized audio feedback for Photo Deleter.

Generates short, soft UI sounds at startup (no bundled assets) and plays
them through QSoundEffect. Degrades silently when QtMultimedia or an
audio device is unavailable. Supports muting.
"""

import math
import os
import random
import struct
import tempfile
import wave

from PyQt5 import QtCore

try:
    from PyQt5.QtMultimedia import QSoundEffect

    _HAS_MULTIMEDIA = True
except ImportError:  # pragma: no cover - depends on platform packages
    _HAS_MULTIMEDIA = False

_RATE = 22050


def _tone(freq: float, ms: int, vol: float = 0.5, decay: float = 5.0) -> list:
    """A soft sine tone with gentle harmonics and exponential decay."""
    n = int(_RATE * ms / 1000)
    dur = ms / 1000.0
    out = []
    attack = max(1, int(_RATE * 0.004))
    for i in range(n):
        t = i / _RATE
        env = min(1.0, i / attack) * math.exp(-decay * t / dur)
        s = (
            math.sin(2 * math.pi * freq * t)
            + 0.30 * math.sin(4 * math.pi * freq * t)
            + 0.12 * math.sin(6 * math.pi * freq * t)
        )
        out.append(vol * env * s / 1.42)
    return out


def _swoosh(ms: int = 110, vol: float = 0.18) -> list:
    """Low-passed noise burst — the sound of a card flying off."""
    n = int(_RATE * ms / 1000)
    out = []
    y = 0.0
    for i in range(n):
        x = random.uniform(-1.0, 1.0)
        y += 0.18 * (x - y)  # one-pole low-pass
        env = math.sin(math.pi * i / max(1, n))  # smooth in & out
        out.append(vol * env * y * 3.0)
    return out


def _silence(ms: int) -> list:
    return [0.0] * int(_RATE * ms / 1000)


def _mix_to_wav(path: str, samples: list):
    frames = bytearray()
    for s in samples:
        val = int(max(-1.0, min(1.0, s)) * 32767)
        frames.extend(struct.pack("<h", val))
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_RATE)
        wf.writeframes(bytes(frames))


def _build_clips() -> dict:
    """Return name -> sample list for every UI sound."""
    return {
        # Rising major arpeggio + swoosh: positive, quick
        "keep": _swoosh(90) + _tone(659, 70) + _tone(784, 70) + _tone(1047, 150, decay=4.0),
        # Soft descending minor pair: decisive but not punishing
        "delete": _swoosh(90) + _tone(440, 80, vol=0.42) + _tone(349, 150, vol=0.42, decay=4.0),
        # Barely-there tick
        "skip": _tone(700, 40, vol=0.25, decay=8.0),
        # Quick down-up "rewind"
        "undo": _tone(587, 55, vol=0.4) + _tone(880, 90, vol=0.4, decay=4.5),
        # Victory arpeggio
        "finish": (
            _tone(523, 85) + _tone(659, 85) + _tone(784, 85)
            + _tone(1047, 240, decay=3.0)
        ),
        # Gentle two-note hello when a folder loads
        "open": _tone(523, 55, vol=0.3) + _silence(15) + _tone(784, 110, vol=0.3, decay=4.0),
    }


class SoundManager:
    """Plays the synthesized UI sounds. Silently degrades when unavailable."""

    def __init__(self, muted: bool = False):
        self._effects: dict = {}
        self._enabled = False
        self._muted = bool(muted)
        if not _HAS_MULTIMEDIA:
            return
        try:
            self._tmp_dir = tempfile.mkdtemp(prefix="photo_deleter_sfx_")
            for name, samples in _build_clips().items():
                path = os.path.join(self._tmp_dir, f"{name}.wav")
                _mix_to_wav(path, samples)
                effect = QSoundEffect()
                effect.setSource(QtCore.QUrl.fromLocalFile(path))
                effect.setVolume(0.45)
                self._effects[name] = effect
            self._enabled = True
        except Exception:
            pass

    @property
    def muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool):
        self._muted = bool(muted)

    def play(self, name: str):
        if self._muted or not self._enabled or name not in self._effects:
            return
        try:
            self._effects[name].play()
        except Exception:
            pass
