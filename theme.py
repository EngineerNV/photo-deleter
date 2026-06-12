"""Design tokens and global styles for Photo Deleter.

A professional dark theme: near-black surfaces, restrained accents,
high-contrast type, and consistent radii — inspired by Material 3 and
Linear-style product design.
"""

from PyQt5 import QtGui

PALETTE = {
    # Surfaces
    "bg_top": "#11151c",
    "bg_bottom": "#0a0d12",
    "surface": "#161a22",
    "surface_high": "#1d232e",
    "surface_overlay": "rgba(13, 16, 22, 0.92)",
    # Strokes
    "border": "rgba(255, 255, 255, 0.08)",
    "border_strong": "rgba(255, 255, 255, 0.16)",
    # Type
    "text": "#eef1f6",
    "text_secondary": "#9aa4b5",
    "text_muted": "#5f6979",
    "ink_dark": "#0d1117",
    # Accents
    "accent": "#5b8cff",
    "accent_hover": "#76a0ff",
    "keep": "#2dd477",
    "keep_hover": "#4ce392",
    "delete": "#f4516c",
    "delete_hover": "#ff7088",
    "skip": "#e8b339",
    "skip_hover": "#f5c75e",
    "undo": "#5aa7f0",
    "undo_hover": "#7cbcf7",
}

BODY_FONT_CANDIDATES = [
    "Inter",
    "SF Pro Text",
    "Segoe UI",
    "Roboto",
    "Helvetica Neue",
    "Arial",
]
TITLE_FONT_CANDIDATES = [
    "Inter",
    "SF Pro Display",
    "Segoe UI",
    "Roboto",
    "Helvetica Neue",
    "Arial",
]


def pick_font(candidates):
    available = set(QtGui.QFontDatabase().families())
    for family in candidates:
        if family in available:
            return family
    return "Sans Serif"


def app_stylesheet(body_font: str, title_font: str) -> str:
    p = PALETTE
    return f"""
    #appRoot {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {p["bg_top"]}, stop:1 {p["bg_bottom"]});
    }}
    QLabel {{
        color: {p["text"]};
        font-family: "{body_font}";
        background: transparent;
    }}
    #appTitle {{
        font-size: 19px;
        font-weight: 700;
        letter-spacing: 0.4px;
        font-family: "{title_font}";
    }}
    #folderChip {{
        color: {p["text_secondary"]};
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 13px;
        padding: 5px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    #statusChip {{
        border-radius: 12px;
        padding: 5px 14px;
        color: {p["text"]};
        border: 1px solid {p["border_strong"]};
        font-size: 12px;
        font-weight: 700;
    }}
    #fileLabel {{
        font-size: 15px;
        font-weight: 700;
    }}
    #metaLabel {{
        font-size: 12px;
        color: {p["text_secondary"]};
        font-weight: 600;
    }}
    #actionLabel {{
        font-size: 11px;
        color: {p["text_muted"]};
    }}
    #hintLabel {{
        font-size: 11px;
        color: {p["text_muted"]};
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    #metaStrip {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 14px;
    }}
    QProgressBar {{
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.07);
        border: none;
        max-height: 6px;
    }}
    QProgressBar::chunk {{
        border-radius: 3px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p["accent"]}, stop:1 {p["keep"]});
    }}
    QToolTip {{
        background: {p["surface_high"]};
        color: {p["text"]};
        border: 1px solid {p["border_strong"]};
        padding: 4px 8px;
        border-radius: 6px;
    }}
    """


def primary_button_style() -> str:
    p = PALETTE
    return f"""
    QPushButton {{
        border-radius: 11px;
        padding: 9px 20px;
        background: {p["accent"]};
        color: {p["ink_dark"]};
        font-weight: 700;
        font-size: 13px;
        border: none;
    }}
    QPushButton:hover {{ background: {p["accent_hover"]}; }}
    QPushButton:pressed {{ padding-top: 10px; padding-bottom: 8px; }}
    """


def ghost_button_style() -> str:
    p = PALETTE
    return f"""
    QPushButton {{
        border-radius: 11px;
        padding: 8px 14px;
        background: {p["surface"]};
        color: {p["text_secondary"]};
        font-weight: 700;
        font-size: 13px;
        border: 1px solid {p["border_strong"]};
    }}
    QPushButton:hover {{
        background: {p["surface_high"]};
        color: {p["text"]};
    }}
    """


def round_action_style(color: str, hover: str, diameter: int) -> str:
    p = PALETTE
    return f"""
    QPushButton {{
        border-radius: {diameter // 2}px;
        min-width: {diameter}px;  max-width: {diameter}px;
        min-height: {diameter}px; max-height: {diameter}px;
        background: {p["surface"]};
        color: {color};
        border: 2px solid {color};
        font-size: {int(diameter * 0.38)}px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        background: {color};
        color: {p["ink_dark"]};
        border-color: {hover};
    }}
    QPushButton:pressed {{
        background: {hover};
        color: {p["ink_dark"]};
    }}
    QPushButton:disabled {{
        background: {p["surface"]};
        color: rgba(255, 255, 255, 0.18);
        border-color: rgba(255, 255, 255, 0.10);
    }}
    """


def finish_button_style() -> str:
    p = PALETTE
    return f"""
    QPushButton {{
        border-radius: 13px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p["keep"]}, stop:1 {p["accent"]});
        color: {p["ink_dark"]};
        font-weight: 800;
        font-size: 15px;
        border: none;
        padding: 13px 18px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p["keep_hover"]}, stop:1 {p["accent_hover"]});
    }}
    QPushButton:pressed {{ padding-top: 14px; padding-bottom: 12px; }}
    """
