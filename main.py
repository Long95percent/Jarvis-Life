import sys
import os
import json
import webbrowser
import uuid
import time
import subprocess
import urllib.request
import urllib.error
import shutil
import re
from collections import deque
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QDialog, QScrollArea, QMenu, QFrame,
                             QGraphicsDropShadowEffect, QComboBox, QMessageBox,
                             QFileDialog, QTextEdit, QTextBrowser,
                             QGraphicsOpacityEffect, QSizePolicy, QFormLayout,
                             QTabWidget, QTabBar, QCheckBox, QSplitter, QToolButton)
from PyQt6.QtCore import Qt, QUrl, QMimeData, pyqtSignal, QObject, QThread, QPropertyAnimation, QEasingCurve, QTimer, QPoint, QEvent, QSequentialAnimationGroup
from PyQt6.QtGui import QColor, QAction, QDrag, QIcon, QFont, QLinearGradient, QDesktopServices, QFontDatabase

from llm_client import (
    load_llm_config, save_llm_config, get_agent,
    normalize_llm_config, is_ollama_endpoint,
    chat_openai_compatible_stream, chat_ollama_stream
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR and BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CONFIG_FILE = "tasks_config.json"

# --- 样式常量 (V2.1 - Soft Matte & Accessible) ---
ACCENT_BLUE = "#5A77D4"  # Dusty Blue / 莫兰迪灰蓝
BG_DARK = "#1A1A1D"      # Soft Charcoal / 柔和深炭灰
CARD_BG = "#242429"      # Muted Gray / 弱紫调深灰
TEXT_MAIN = "#D1D1D6"    # Off-White / 带灰度的暖白
TEXT_SUB = "#8E8E93"     # Muted Gray / 哑光灰
BORDER_LIGHT = "rgba(255, 255, 255, 0.15)"

GLOBAL_QSS = """
QDialog#AgentDialog {
    background-color: #1A1A24;
}

QFrame#GlassSurface {
    background-color: #1E1E2E;
    border: none;
    border-radius: 12px;
}

QFrame#HistoryPane {
    background-color: #1E1E2E;
    border: none;
    border-right: 2px solid rgba(255, 255, 255, 10);
    border-top-left-radius: 12px;
    border-bottom-left-radius: 12px;
}

QFrame#ChatPane {
    background-color: #1E1E2E;
    border: none;
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
}

QScrollArea#ChatScroll, QScrollArea#ChatScroll > QWidget, QScrollArea#ChatScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}

QListWidget#HistoryList {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#HistoryList::item {
    color: rgba(255, 255, 255, 170);
    padding: 12px 12px;
    border-radius: 8px;
    margin-bottom: 8px;
    background-color: #38384D;
}
QListWidget#HistoryList::item:selected {
    background-color: transparent;
    border: 2px solid #5A77D4;
    color: white;
}
QListWidget#HistoryList::item:hover {
    background-color: rgba(255, 255, 255, 24);
}

QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #8B5CF6);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    padding: 10px 14px;
}
QPushButton#PrimaryButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60AFFF, stop:1 #B466FF); }
QPushButton#PrimaryButton:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #7C3AED); }
QPushButton#PrimaryButton:disabled { background: none; background-color: rgba(255,255,255,20); color: rgba(255,255,255,120); }

QPushButton#DangerButton {
    background-color: transparent;
    color: #A0A0A5;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
    font-weight: 700;
    font-size: 12px;
    padding: 10px 14px;
}
QPushButton#DangerButton:hover { background-color: rgba(255,255,255,20); color: white; }
QPushButton#DangerButton:disabled { border-color: rgba(255,255,255,0.1); color: rgba(255,255,255,60); }

QTextEdit#ChatInput {
    background-color: transparent;
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #D1D1D6;
    padding: 12px 12px;
    font-size: 14px;
    font-weight: 450;
}
QTextEdit#ChatInput:focus {
    border: 2px solid #3B82F6;
    background-color: rgba(59, 130, 246, 0.05);
}

QFrame#UserBubble {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #8B5CF6);
    border: none;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 2px;
}

QFrame#AgentBubble {
    background-color: #2B2B3D;
    border: none;
    border-top-left-radius: 2px;
    border-top-right-radius: 14px;
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
}

QTextBrowser#BubbleText {
    background: transparent;
    border: none;
    color: #D1D1D6;
    font-size: 13px;
}
QTextBrowser#BubbleText a { color: #5FB3B3; }

QFrame#MetaBox {
    background-color: rgba(0, 0, 0, 26);
    border: 2px solid rgba(255, 255, 255, 14);
    border-radius: 6px;
}
QToolButton#MetaToggle {
    background: transparent;
    border: none;
    color: #8E8E93;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 10px;
    text-align: left;
}
QToolButton#MetaToggle:hover {
    background-color: rgba(255, 255, 255, 10);
    border-radius: 6px;
}
QTextBrowser#MetaText {
    background: transparent;
    border: none;
    color: #5FB3B3;
    font-size: 12px;
    font-family: "Cascadia Mono","Consolas","SF Mono","Menlo",monospace;
}

QScrollBar:vertical {
    background: transparent;
    width: 3px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 20);
    border-radius: 1px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 100);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: transparent; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

def _new_mode_id():
    return uuid.uuid4().hex

def _open_resource(value: str):
    value = (value or "").strip()
    if not value:
        return
    try:
        if value.startswith(("http://", "https://", "obsidian://")):
            QDesktopServices.openUrl(QUrl(value))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.normpath(value)))
    except Exception:
        return

def _resource_kind(value: str) -> str:
    v = (value or "").strip().lower()
    if v.startswith(("http://", "https://", "obsidian://")):
        return "Link"
    if ":\\" in v or v.startswith(("\\\\", "/")):
        return "Path"
    if v.endswith((".exe", ".lnk", ".bat", ".cmd")):
        return "Software"
    return "Text"

def _detect_local_launch(folder_path: str):
    folder = (folder_path or "").strip()
    if not folder or not os.path.isdir(folder):
        return None
    candidates = [
        ("cmd", [os.path.join(folder, "run.bat")]),
        ("cmd", [os.path.join(folder, "start.bat")]),
        ("cmd", [os.path.join(folder, "serve.bat")]),
        ("exe", [os.path.join(folder, "server.exe")]),
        ("exe", [os.path.join(folder, "main.exe")]),
        ("py", [os.path.join(folder, "server.py")]),
        ("py", [os.path.join(folder, "app.py")]),
        ("py", [os.path.join(folder, "main.py")]),
    ]
    for kind, paths in candidates:
        p = paths[0]
        if os.path.isfile(p):
            if kind == "cmd":
                return ["cmd", "/c", p]
            if kind == "exe":
                return [p]
            if kind == "py":
                return [sys.executable, p]
    return None


class StyledButton(QPushButton):
    def __init__(self, text, primary=False, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.setFixedSize(90, 32) if not primary else self.setFixedSize(110, 36)
        self.setup_style()
        if self.primary:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(15)
            shadow.setColor(QColor("#6C6F93"))
            shadow.setOffset(0, 0)
            self.setGraphicsEffect(shadow)

    def setup_style(self):
        if self.primary:
            style = f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6C6F93, stop:1 #5B82A8);
                    color: {TEXT_MAIN}; border-radius: 10px;
                    font-weight: bold; border: none; font-size: 13px;
                }}
                QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5B82A8, stop:1 #5B82A8); }}
                QPushButton:pressed {{ background-color: {ACCENT_BLUE}; }}
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: transparent; color: {TEXT_MAIN}; border-radius: 6px;
                    font-weight: 500; border: 2px solid rgba(255,255,255,0.08); font-size: 12px;
                }}
                QPushButton:hover {{ border-color: {ACCENT_BLUE}; color: {ACCENT_BLUE}; }}
            """
        self.setStyleSheet(style)


class ToggleSwitch(QFrame):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(50, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._knob = QFrame(self)
        self._knob.setFixedSize(22, 22)
        self._knob.move(3, 3)

        self._anim = QPropertyAnimation(self._knob, b"pos", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._apply_style()
        self._apply_position(animate=False)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked: bool, emit_signal: bool = True):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self._apply_style()
        self._apply_position(animate=True)
        if emit_signal:
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def _apply_style(self):
        if self._checked:
            bg = "#5A77D4"
        else:
            bg = "rgba(255, 255, 255, 0.12)"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border-radius: 14px;
            }}
        """)
        self._knob.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.92);
                border-radius: 11px;
            }
        """)

    def _apply_position(self, animate: bool):
        y = 3
        x_off = 3
        x_on = self.width() - self._knob.width() - 3
        target = x_on if self._checked else x_off
        if not animate:
            self._knob.move(target, y)
            return
        self._anim.stop()
        self._anim.setStartValue(self._knob.pos())
        self._anim.setEndValue(QPoint(target, y))
        self._anim.start()


class LinkItemWidget(QWidget):
    def __init__(self, path="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.input = QLineEdit(path)
        self.input.setPlaceholderText("Paste link or drop path...")
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {CARD_BG}; border: 2px solid {BORDER_LIGHT};
                color: {TEXT_MAIN}; padding: 8px; border-radius: 6px; font-size: 13px;
            }}
            QLineEdit:focus {{ border: 2px solid {ACCENT_BLUE}; }}
        """)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #C25B56; border-radius: 14px; font-size: 16px; }
            QPushButton:hover { background-color: rgba(194, 91, 86, 0.2); }
        """)
        self.del_btn.clicked.connect(self.deleteLater)

        layout.addWidget(self.input)
        layout.addWidget(self.del_btn)


class ConfigDialog(QDialog):
    def __init__(self, task_name="", paths=None, parent=None, title="Edit Workflow", name_placeholder="Task Name (e.g. Deep Learning Research)"):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(480, 500)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_MAIN};")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        head_label = QLabel(title)
        head_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        layout.addWidget(head_label)

        self.name_input = QLineEdit(task_name)
        self.name_input.setPlaceholderText(name_placeholder)
        self.name_input.setStyleSheet(f"""
            background-color: {CARD_BG}; border: 2px solid {BORDER_LIGHT}; 
            padding: 12px; border-radius: 6px; font-size: 15px; color: {TEXT_MAIN};
        """)
        if not name_placeholder:
            self.name_input.hide()
        else:
            layout.addWidget(self.name_input)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        if paths:
            for p in paths:
                self.add_row(p)

        btn_layout = QHBoxLayout()
        add_btn = StyledButton("+ Add Item", False)
        add_btn.clicked.connect(lambda: self.add_row(""))
        save_btn = StyledButton("Save Settings", True)
        save_btn.clicked.connect(self.accept)

        btn_layout.addWidget(add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def add_row(self, path):
        row = LinkItemWidget(path)
        self.list_layout.addWidget(row)

    def get_data(self):
        paths = []
        for i in range(self.list_layout.count()):
            w = self.list_layout.itemAt(i).widget()
            if isinstance(w, LinkItemWidget) and w.input.text():
                paths.append(w.input.text().strip())
        return self.name_input.text().strip(), paths


class CommandExecWorker(QObject):
    line = pyqtSignal(str)
    done = pyqtSignal(int)

    def __init__(self, command: str, cwd: str | None = None):
        super().__init__()
        self.command = (command or "").strip()
        self.cwd = (cwd or "").strip() or None

    def run(self):
        try:
            if not self.command:
                self.done.emit(0)
                return
            p = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            try:
                if p.stdout:
                    for ln in p.stdout:
                        if ln:
                            self.line.emit(ln.rstrip("\n"))
            finally:
                try:
                    if p.stdout:
                        p.stdout.close()
                except Exception:
                    pass
            code = p.wait()
            self.done.emit(int(code))
        except Exception:
            self.done.emit(1)


class ModelSettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(560, 480)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_MAIN};")

        self.cfg = normalize_llm_config(cfg)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(26, 26, 26, 26)

        head = QLabel("Configuration")
        head.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        layout.addWidget(head)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 2px solid {BORDER_LIGHT}; border-radius: 14px; background: {CARD_BG}; }}
            QTabBar::tab {{ background: {BG_DARK}; color: {TEXT_SUB}; padding: 8px 16px; border: 2px solid transparent; }}
            QTabBar::tab:selected {{ background: {CARD_BG}; color: {TEXT_MAIN}; border-top: 2px solid {ACCENT_BLUE}; font-weight: bold; }}
        """)

        # --- LLM Tab ---
        llm_tab = QWidget()
        llm_layout = QVBoxLayout(llm_tab)
        llm_layout.setSpacing(18)
        llm_layout.setContentsMargins(16, 16, 16, 16)

        row = QHBoxLayout()
        row.setSpacing(12)
        label = QLabel("Active Agent")
        label.setStyleSheet(f"font-size: 13px; color: {TEXT_SUB};")
        self.agent_combo = QComboBox()
        self.agent_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {CARD_BG}; border: 2px solid {BORDER_LIGHT};
                border-radius: 6px; padding: 8px 10px; color: {TEXT_MAIN};
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        for a in self.cfg.get("agents", []):
            self.agent_combo.addItem(a.get("name") or a.get("id"), a.get("id"))
        active_id = self.cfg.get("active_agent_id")
        idx = self.agent_combo.findData(active_id)
        if idx >= 0:
            self.agent_combo.setCurrentIndex(idx)
        self.agent_combo.currentIndexChanged.connect(self._sync_form)
        
        self.new_api_btn = QPushButton("New API")
        self.new_api_btn.setFixedSize(80, 32)
        self.new_api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_api_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {TEXT_MAIN}; border-radius: 6px; font-weight: bold; border: 2px solid {BORDER_LIGHT}; font-size: 12px; }}
            QPushButton:hover {{ border-color: {ACCENT_BLUE}; color: {ACCENT_BLUE}; }}
        """)
        self.new_api_btn.clicked.connect(self._on_new_api_clicked)
        
        row.addWidget(label)
        row.addWidget(self.agent_combo, 1)
        row.addWidget(self.new_api_btn)
        llm_layout.addLayout(row)

        self.api_frame = QFrame()
        self.api_frame.setStyleSheet(f"QFrame {{ background-color: transparent; border: none; }}")
        api_layout = QVBoxLayout(self.api_frame)
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.setSpacing(12)

        self.api_base = QLineEdit()
        self.api_base.setPlaceholderText("Base URL (e.g. https://api.openai.com/v1)")
        self.api_base.setStyleSheet(f"""
            QLineEdit {{ background-color: {CARD_BG}; border: 2px solid {BORDER_LIGHT}; color: {TEXT_MAIN}; padding: 10px; border-radius: 6px; font-size: 13px; }}
            QLineEdit:focus {{ border: 2px solid {ACCENT_BLUE}; }}
        """)
        api_layout.addWidget(self.api_base)

        self.api_model = QLineEdit()
        self.api_model.setPlaceholderText("Model (e.g. gpt-4o-mini)")
        self.api_model.setStyleSheet(self.api_base.styleSheet())
        api_layout.addWidget(self.api_model)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("API Key")
        self.api_key.setStyleSheet(self.api_base.styleSheet())
        api_layout.addWidget(self.api_key)

        llm_layout.addWidget(self.api_frame)

        self.local_frame = QFrame()
        self.local_frame.setStyleSheet(self.api_frame.styleSheet())
        local_layout = QVBoxLayout(self.local_frame)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(12)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        self.local_folder = QLineEdit()
        self.local_folder.setPlaceholderText("Local model folder path")
        self.local_folder.setStyleSheet(self.api_base.styleSheet())
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedSize(80, 34)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_folder)
        browse_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {TEXT_MAIN}; border-radius: 6px; font-weight: bold; border: 2px solid {BORDER_LIGHT}; font-size: 12px; }}
            QPushButton:hover {{ border-color: {ACCENT_BLUE}; color: {ACCENT_BLUE}; }}
        """)
        folder_row.addWidget(self.local_folder, 1)
        folder_row.addWidget(browse_btn)
        local_layout.addLayout(folder_row)

        self.local_base = QLineEdit()
        self.local_base.setPlaceholderText("Local Base URL (OpenAI-compatible, e.g. http://127.0.0.1:8000/v1)")
        self.local_base.setStyleSheet(self.api_base.styleSheet())
        local_layout.addWidget(self.local_base)

        self.local_model = QLineEdit()
        self.local_model.setPlaceholderText("Local model name (server side)")
        self.local_model.setStyleSheet(self.api_base.styleSheet())
        local_layout.addWidget(self.local_model)

        engine_row = QHBoxLayout()
        engine_row.setSpacing(12)
        engine_label = QLabel("Agent Engine")
        engine_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SUB};")
        self.engine_combo = QComboBox()
        self.engine_combo.setStyleSheet(self.agent_combo.styleSheet())
        self.engine_combo.addItem("Auto (Detect by URL)", "auto")
        self.engine_combo.addItem("Native Ollama (Best for 502 errors)", "ollama_native")
        self.engine_combo.addItem("OpenAI-Compatible (Standard)", "openai_compatible")
        engine_row.addWidget(engine_label)
        engine_row.addWidget(self.engine_combo, 1)
        local_layout.addLayout(engine_row)

        llm_layout.addWidget(self.local_frame)
        llm_layout.addStretch()
        tabs.addTab(llm_tab, "LLM Models")

        # --- Permissions Tab ---
        perm_tab = QWidget()
        perm_layout = QVBoxLayout(perm_tab)
        perm_layout.setSpacing(16)
        perm_layout.setContentsMargins(16, 16, 16, 16)
        
        perm_info = QLabel("Configure the file system permissions for the AI Agent.")
        perm_info.setWordWrap(True)
        perm_info.setStyleSheet(f"color: {TEXT_SUB}; font-size: 13px;")
        perm_layout.addWidget(perm_info)
        
        self.full_access_cb = QCheckBox("Enable Full Access (Requires Administrator privileges)")
        self.full_access_cb.setStyleSheet(f"color: white; font-size: 14px; font-weight: bold;")
        perms = self.cfg.get("agent_permissions", {})
        self.full_access_cb.setChecked(perms.get("full_access", False))
        self.full_access_cb.stateChanged.connect(self._on_perm_change)
        perm_layout.addWidget(self.full_access_cb)
        
        self.restricted_dir_widget = QWidget()
        rd_layout = QVBoxLayout(self.restricted_dir_widget)
        rd_layout.setContentsMargins(0, 0, 0, 0)
        rd_layout.setSpacing(6)
        
        rd_label = QLabel("Restricted Root Directory (D: drive only):")
        rd_label.setStyleSheet(f"color: {TEXT_SUB}; font-size: 13px;")
        rd_layout.addWidget(rd_label)
        
        self.restricted_dir_input = QLineEdit()
        self.restricted_dir_input.setText(perms.get("restricted_root_dir", "D:\\"))
        self.restricted_dir_input.setStyleSheet(self.api_base.styleSheet())
        self.restricted_dir_input.textChanged.connect(self._validate_d_drive)
        rd_layout.addWidget(self.restricted_dir_input)
        
        perm_layout.addWidget(self.restricted_dir_widget)
        perm_layout.addStretch()
        tabs.addTab(perm_tab, "Agent Permissions")

        skills_tab = QWidget()
        skills_layout = QVBoxLayout(skills_tab)
        skills_layout.setContentsMargins(0, 0, 0, 0)
        
        skills_scroll = QScrollArea()
        skills_scroll.setWidgetResizable(True)
        skills_scroll.setFrameShape(QFrame.Shape.NoFrame)
        skills_scroll.setStyleSheet("background: transparent;")
        
        skills_content = QWidget()
        skills_content_layout = QVBoxLayout(skills_content)
        skills_content_layout.setSpacing(14)
        skills_content_layout.setContentsMargins(16, 16, 16, 16)

        tools_head = QLabel("Tools Installer (Command Line)")
        tools_head.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        skills_content_layout.addWidget(tools_head)

        tools_desc = QLabel("Run a pip command to install LangChain tool packages (runs in the current Python environment).")
        tools_desc.setWordWrap(True)
        tools_desc.setStyleSheet(f"color: {TEXT_SUB}; font-size: 13px;")
        skills_content_layout.addWidget(tools_desc)

        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(10)
        self.tools_cmd = QLineEdit()
        self.tools_cmd.setPlaceholderText('pip install -U langchain-community')
        self.tools_cmd.setStyleSheet(self.api_base.styleSheet())
        cmd_row.addWidget(self.tools_cmd, 1)

        self.run_cmd_btn = QPushButton("Run")
        self.run_cmd_btn.setFixedSize(80, 34)
        self.run_cmd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_cmd_btn.clicked.connect(self._run_tools_command)
        self.run_cmd_btn.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6C6F93, stop:1 #5B82A8); color: {TEXT_MAIN}; border-radius: 6px; font-weight: bold; border: none; font-size: 12px; }}
            QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5B82A8, stop:1 #5B82A8); }}
            QPushButton:pressed {{ background-color: {ACCENT_BLUE}; }}
        """)
        cmd_row.addWidget(self.run_cmd_btn)
        skills_content_layout.addLayout(cmd_row)

        self.tools_output = QTextBrowser()
        self.tools_output.setOpenExternalLinks(True)
        self.tools_output.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CARD_BG};
                border: 2px solid {BORDER_LIGHT};
                border-radius: 6px;
                padding: 8px;
                color: {TEXT_MAIN};
                font-size: 12px;
            }}
        """)
        self.tools_output.setMinimumHeight(140)
        skills_content_layout.addWidget(self.tools_output)

        skills_head = QLabel("Skills (Dynamic Tool Plugins)")
        skills_head.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        skills_content_layout.addWidget(skills_head)

        base_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
        skills_desc = QLabel('Set skills as JSON. Each item can be a string "module:callable" or an object like {"ref": "module:callable", "enabled": true, "kwargs": {}}.\n\nSkill files should be importable by Python; the default import base includes:\n' + base_dir)
        skills_desc.setWordWrap(True)
        skills_desc.setStyleSheet(f"color: {TEXT_SUB}; font-size: 13px;")
        skills_content_layout.addWidget(skills_desc)

        self.skills_json = QTextEdit()
        self.skills_json.setStyleSheet(f"""
            QTextEdit {{
                background-color: {CARD_BG};
                border: 2px solid {BORDER_LIGHT};
                border-radius: 6px;
                padding: 10px;
                color: {TEXT_MAIN};
                font-size: 12px;
            }}
        """)
        self.skills_json.setMinimumHeight(180)
        self._skills_parsed = self.cfg.get("skills", []) if isinstance(self.cfg.get("skills"), list) else []
        self.skills_json.setPlainText(json.dumps(self._skills_parsed, ensure_ascii=False, indent=2))
        skills_content_layout.addWidget(self.skills_json)
        skills_content_layout.addStretch()

        skills_scroll.setWidget(skills_content)
        skills_layout.addWidget(skills_scroll)

        tabs.addTab(skills_tab, "Skills & Tools")
        
        layout.addWidget(tabs)

        self._on_perm_change() # Init visibility

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        cancel_btn = StyledButton("Cancel", False)
        cancel_btn.clicked.connect(self.reject)
        save_btn = StyledButton("Save", True)
        save_btn.clicked.connect(self.accept)
        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(save_btn)
        layout.addLayout(btn_bar)

        self._sync_form()
        self._cmd_thread: QThread | None = None
        self._cmd_worker: CommandExecWorker | None = None

    def _validate_d_drive(self, text):
        if not text.upper().startswith("D:\\") and text.upper() != "D:":
            self.restricted_dir_input.setStyleSheet(f"QLineEdit {{ background-color: #3b1c1c; border: 2px solid #C25B56; color: {TEXT_MAIN}; padding: 10px; border-radius: 6px; font-size: 13px; }}")
            self.restricted_dir_input.setToolTip("Must be on D: drive")
        else:
            self.restricted_dir_input.setStyleSheet(f"QLineEdit {{ background-color: {CARD_BG}; border: 2px solid {BORDER_LIGHT}; color: {TEXT_MAIN}; padding: 10px; border-radius: 6px; font-size: 13px; }} QLineEdit:focus {{ border: 2px solid {ACCENT_BLUE}; }}")
            self.restricted_dir_input.setToolTip("")

    def _on_perm_change(self):
        is_full = self.full_access_cb.isChecked()
        self.restricted_dir_widget.setEnabled(not is_full)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.local_folder.text() or os.getcwd())
        if folder:
            self.local_folder.setText(folder)

    def _normalize_tools_command(self, cmd: str):
        c = (cmd or "").strip()
        if not c:
            return ""
        low = c.lower()
        exe = f"\"{sys.executable}\""
        if low.startswith("pip "):
            return f"{exe} -m pip {c[4:].lstrip()}"
        if low.startswith("python -m pip "):
            return f"{exe} -m pip {c[len('python -m pip '):].lstrip()}"
        if low.startswith("python "):
            return f"{exe} {c[len('python '):].lstrip()}"
        return c

    def _append_tools_output(self, line: str):
        self.tools_output.append(line)

    def _on_tools_command_done(self, code: int):
        self.run_cmd_btn.setEnabled(True)
        self.tools_output.append(f"\n[exit code: {int(code)}]\n")
        if self._cmd_thread is not None:
            self._cmd_thread.quit()
            self._cmd_thread.wait(2000)
        self._cmd_thread = None
        self._cmd_worker = None

    def _run_tools_command(self):
        raw = self.tools_cmd.text().strip()
        cmd = self._normalize_tools_command(raw)
        if not cmd:
            return
        if self._cmd_thread is not None:
            return
        self.tools_output.clear()
        self.tools_output.append(cmd)
        self.tools_output.append("")
        self.run_cmd_btn.setEnabled(False)

        self._cmd_thread = QThread(self)
        self._cmd_worker = CommandExecWorker(cmd, cwd=os.getcwd())
        self._cmd_worker.moveToThread(self._cmd_thread)
        self._cmd_thread.started.connect(self._cmd_worker.run)
        self._cmd_worker.line.connect(self._append_tools_output)
        self._cmd_worker.done.connect(self._on_tools_command_done)
        self._cmd_worker.done.connect(self._cmd_thread.quit)
        self._cmd_thread.start()

    def _on_new_api_clicked(self):
        import string
        import random
        from PyQt6.QtWidgets import QInputDialog
        
        # 1. Ask user for the new API name
        name, ok = QInputDialog.getText(self, "New API Model", "Enter a name for the new API Model:", QLineEdit.EchoMode.Normal, "My Custom API")
        if not ok or not name.strip():
            return
            
        name = name.strip()
        # 2. Generate unique ID
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        new_id = f"api_{suffix}"
        
        # 3. Create the new agent config
        new_agent = {
            "id": new_id,
            "name": name,
            "type": "api",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "extra_body": {},
            "stream_options": {}
        }
        
        # 4. Save current form state before adding
        self._save_current_to_cfg()
        
        # 5. Add to config
        agents = self.cfg.setdefault("agents", [])
        agents.append(new_agent)
        self.cfg.setdefault("secrets", {})[new_id] = {"api_key": ""}
        
        # 6. Update combo box
        self.agent_combo.blockSignals(True)
        self.agent_combo.addItem(name, new_id)
        idx = self.agent_combo.findData(new_id)
        self.agent_combo.setCurrentIndex(idx)
        self.agent_combo.blockSignals(False)
        
        # 7. Sync UI
        self._sync_form()

    def _save_current_to_cfg(self):
        agent_id = self._current_agent_id()
        if not agent_id:
            return
        agent = get_agent(self.cfg, agent_id)
        if not agent:
            return
            
        if agent.get("type") == "api":
            agent["base_url"] = self.api_base.text().strip()
            agent["model"] = self.api_model.text().strip()
            self.cfg.setdefault("secrets", {}).setdefault(agent_id, {})
            self.cfg["secrets"][agent_id]["api_key"] = self.api_key.text().strip()
        else:
            agent["folder_path"] = self.local_folder.text().strip()
            agent["base_url"] = self.local_base.text().strip()
            agent["model"] = self.local_model.text().strip()
            agent["engine"] = self.engine_combo.currentData() or "auto"

    def _current_agent_id(self):
        return self.agent_combo.currentData()

    def _sync_form(self):
        # We don't save to config on initial load or if no agent is selected
        if hasattr(self, '_loaded_once') and self._current_agent_id():
            self._save_current_to_cfg()
        self._loaded_once = True
        
        agent_id = self._current_agent_id()
        agent = get_agent(self.cfg, agent_id) or {}
        agent_type = agent.get("type")

        is_api = agent_type == "api"
        self.api_frame.setVisible(is_api)
        self.local_frame.setVisible(not is_api)

        if is_api:
            self.api_base.setText(agent.get("base_url") or "")
            self.api_model.setText(agent.get("model") or "")
            self.api_key.setText(((self.cfg.get("secrets") or {}).get(agent_id) or {}).get("api_key") or "")
        else:
            self.local_folder.setText(agent.get("folder_path") or "")
            self.local_base.setText(agent.get("base_url") or "")
            self.local_model.setText(agent.get("model") or "")
            
            engine = agent.get("engine") or "auto"
            idx = self.engine_combo.findData(engine)
            if idx >= 0:
                self.engine_combo.setCurrentIndex(idx)

    def get_updated_config(self):
        cfg = normalize_llm_config(self.cfg)
        agent_id = self._current_agent_id()
        cfg["active_agent_id"] = agent_id
        agent = get_agent(cfg, agent_id) or {}
        if agent.get("type") == "api":
            agent["base_url"] = self.api_base.text().strip()
            agent["model"] = self.api_model.text().strip()
            cfg["secrets"].setdefault(agent_id, {})
            cfg["secrets"][agent_id]["api_key"] = self.api_key.text().strip()
        else:
            agent["folder_path"] = self.local_folder.text().strip()
            agent["base_url"] = self.local_base.text().strip()
            agent["model"] = self.local_model.text().strip()
            agent["engine"] = self.engine_combo.currentData() or "auto"
            
        # Update permissions
        old_full_access = cfg.get("agent_permissions", {}).get("full_access", False)
        new_full_access = self.full_access_cb.isChecked()
        
        restricted_dir = self.restricted_dir_input.text().strip()
        if restricted_dir.upper() == "D:":
            restricted_dir = "D:\\"
        elif not restricted_dir.upper().startswith("D:\\"):
            restricted_dir = "D:\\"
            
        cfg["agent_permissions"] = {
            "full_access": new_full_access,
            "restricted_root_dir": restricted_dir
        }

        cfg["skills"] = self._skills_parsed if isinstance(self._skills_parsed, list) else []
        
        if new_full_access and not old_full_access:
            import ctypes
            try:
                if not ctypes.windll.shell32.IsUserAnAdmin():
                    QMessageBox.information(self, "Restart Required", "Full access requires Administrator privileges. Please restart ShadowLink as Administrator.")
            except Exception:
                pass
                
        return cfg

    def accept(self):
        try:
            raw = (self.skills_json.toPlainText() or "").strip()
            parsed = json.loads(raw) if raw else []
            if isinstance(parsed, dict):
                parsed = [parsed]
            if not isinstance(parsed, list):
                raise ValueError("Skills JSON must be a list or an object")
            self._skills_parsed = parsed
        except Exception as e:
            QMessageBox.warning(self, "Invalid Skills JSON", str(e))
            return
        super().accept()


class ResourceRow(QFrame):
    def __init__(self, value: str, parent=None):
        super().__init__(parent)
        self.value = (value or "").strip()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 2px solid {BORDER_LIGHT};
                border-radius: 14px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)

        kind = QLabel(_resource_kind(self.value))
        kind.setStyleSheet(f"font-size: 11px; color: {TEXT_SUB}; background: transparent;")

        text = QLabel(self.value)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setStyleSheet(f"font-size: 13px; color: {TEXT_MAIN}; background: transparent;")

        left.addWidget(kind)
        left.addWidget(text)

        open_btn = QPushButton("Open")
        open_btn.setFixedSize(70, 30)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_resource(self.value))
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(90, 119, 212, 0.15);
                color: {ACCENT_BLUE}; border-radius: 15px;
                font-weight: bold; border: none; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_BLUE}; color: {TEXT_MAIN}; }}
        """)

        layout.addLayout(left)
        layout.addStretch()
        layout.addWidget(open_btn)


class ModeManager(QObject):
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "chat"

    @property
    def current_mode(self):
        return self._current_mode

    def toggle_mode(self):
        self._current_mode = "agent" if self._current_mode == "chat" else "chat"
        self.mode_changed.emit(self._current_mode)

    def set_mode(self, mode: str):
        if mode in ("chat", "agent") and self._current_mode != mode:
            self._current_mode = mode
            self.mode_changed.emit(self._current_mode)

class LocalResourcesDialog(QDialog):
    def __init__(self, task_name: str, resources: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local Resources")
        self.setMinimumSize(520, 560)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_MAIN};")

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(26, 26, 26, 26)

        head = QLabel(task_name or "Resources")
        head.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        sub = QLabel("All stored links / paths / software / notes")
        sub.setStyleSheet(f"font-size: 12px; color: {TEXT_SUB};")

        layout.addWidget(head)
        layout.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        list_layout = QVBoxLayout(container)
        list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_layout.setSpacing(12)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        items = [(r or "").strip() for r in (resources or []) if (r or "").strip()]
        items.sort(key=lambda x: (_resource_kind(x), x.lower()))
        if not items:
            empty = QLabel("No resources yet.")
            empty.setStyleSheet(f"font-size: 13px; color: {TEXT_SUB};")
            list_layout.addWidget(empty)
        else:
            for it in items:
                list_layout.addWidget(ResourceRow(it))

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = StyledButton("Close", False)
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)


class CollapsibleMetaBox(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MetaBox")
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.toggle_btn = QToolButton(self)
        self.toggle_btn.setObjectName("MetaToggle")
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_btn.setText("Agent 正在处理逻辑…")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_btn)

        self.body = QTextBrowser(self)
        self.body.setObjectName("MetaText")
        self.body.setOpenExternalLinks(True)
        self.body.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.body.setFrameShape(QFrame.Shape.NoFrame)
        self.body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body.document().setDocumentMargin(0)
        self.body.setVisible(False)
        layout.addWidget(self.body)

        self.setVisible(False)

    def set_meta_text(self, text: str):
        t = (text or "").strip("\n")
        self.body.setPlainText(t)
        has = bool(t.strip())
        self.setVisible(has)
        if has and self._expanded:
            self.body.setVisible(True)

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        self._expanded = bool(expanded)
        self.toggle_btn.setArrowType(Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow)
        self.body.setVisible(self._expanded and self.isVisible())


class AgentDialog(QDialog):
    def __init__(self, task_name: str, resources: list[str], mode_id: str, llm_cfg: dict, app_window, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setObjectName("AgentDialog")
        self.task_name = task_name
        self.resources = resources or []
        self.mode_id = (mode_id or "").strip()
        self.llm_cfg = normalize_llm_config(llm_cfg)
        self.app_window = app_window
        self.messages: list[dict] = []
        self._active_thread: QThread | None = None
        self._active_worker: QObject | None = None
        self._rag_thread: QThread | None = None
        self._rag_worker: QObject | None = None
        self._index_thread: QThread | None = None
        self._index_worker: QObject | None = None
        self._index_bubble: QFrame | None = None
        self._index_browser: QTextBrowser | None = None
        self._animations: list[QPropertyAnimation] = []
        self._current_bubble: QFrame | None = None
        self._current_browser: QTextBrowser | None = None
        self._bubble_meta: dict[QFrame, CollapsibleMetaBox] = {}
        self._current_reply_raw: str = ""
        self._current_reply_final: str = ""
        self._current_reply_meta: str = ""
        self._router_buffer: str = ""
        self._router_mode: str = "final"
        self._render_queue: deque[str] = deque()
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._flush_render)
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(480)
        self._cursor_timer.timeout.connect(self._on_cursor_tick)
        self._cursor_visible = True
        self._stream_finished = False
        self._stream_error = ""
        self._rag_enabled = False
        self._use_history = False
        self._paused = False
        
        from history_manager import HistoryManager
        self.hm = HistoryManager()
        self.session_id = None
        
        self.mode_manager = ModeManager(self)
        self.mode_manager.mode_changed.connect(self._on_mode_changed)

        self.setWindowTitle("Agent")
        self.setMinimumSize(960, 640)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(0)

        glass = QFrame(self)
        glass.setObjectName("GlassSurface")
        glass_shadow = QGraphicsDropShadowEffect(glass)
        glass_shadow.setBlurRadius(32)
        glass_shadow.setOffset(0, 10)
        glass_shadow.setColor(QColor(0, 0, 0, 120))
        glass.setGraphicsEffect(glass_shadow)
        root_layout.addWidget(glass, 1)

        glass_layout = QHBoxLayout(glass)
        glass_layout.setContentsMargins(0, 0, 0, 0)
        glass_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, glass)
        splitter.setHandleWidth(0)
        splitter.setChildrenCollapsible(False)
        glass_layout.addWidget(splitter, 1)

        self.history_frame = QFrame(splitter)
        self.history_frame.setObjectName("HistoryPane")
        self.history_frame.setMinimumWidth(240)
        self.history_frame.setMaximumWidth(280)
        hist_layout = QVBoxLayout(self.history_frame)
        hist_layout.setContentsMargins(20, 24, 20, 24)
        hist_layout.setSpacing(16)

        self.new_chat_btn = StyledButton("+ New Chat", True, self.history_frame)
        self.new_chat_btn.setFixedHeight(44)
        self.new_chat_btn.setStyleSheet(self.new_chat_btn.styleSheet() + "font-size: 14px; font-weight: bold; border-radius: 12px;")
        self.new_chat_btn.clicked.connect(self._on_new_chat)
        hist_layout.addWidget(self.new_chat_btn)

        hist_title = QLabel("CHAT HISTORY", self.history_frame)
        hist_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #8E8E93; letter-spacing: 1px;")
        hist_layout.addWidget(hist_title)

        from PyQt6.QtWidgets import QListWidget
        self.hist_list = QListWidget(self.history_frame)
        self.hist_list.setObjectName("HistoryList")
        self.hist_list.itemClicked.connect(self._on_hist_item_clicked)
        self.hist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_list.customContextMenuRequested.connect(self._show_hist_context_menu)
        hist_layout.addWidget(self.hist_list, 1)

        chat_pane = QFrame(splitter)
        chat_pane.setObjectName("ChatPane")
        layout = QVBoxLayout(chat_pane)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        self.scan_line = QFrame(chat_pane)
        self.scan_line.setFixedHeight(2)
        self.scan_line.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 transparent, stop:0.5 {ACCENT_BLUE}, stop:1 transparent);")
        self.scan_line.hide()
        self.scan_anim = QPropertyAnimation(self.scan_line, b"pos")
        self.scan_anim.setDuration(1200)
        self.scan_anim.setLoopCount(-1)
        self.scan_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        top = QHBoxLayout()
        top.setSpacing(16)
        top.setAlignment(Qt.AlignmentFlag.AlignTop)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        head = QLabel(task_name or "Agent", chat_pane)
        head.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        active_agent = get_agent(self.llm_cfg, self.llm_cfg.get("active_agent_id")) or {}
        sub = QLabel(f"Active: {active_agent.get('name') or active_agent.get('id') or 'Unknown'}", chat_pane)
        sub.setStyleSheet("font-size: 13px; color: #8E8E93;")
        title_box.addWidget(head)
        title_box.addWidget(sub)
        top.addLayout(title_box)
        top.addStretch()
        
        btn_style = "QPushButton { background-color: #2B2B3D; color: #E5E5E5; border: 2px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 6px 12px; font-size: 13px; } QPushButton:hover { background-color: #38384D; }"
        self.mode_btn = QPushButton("Mode: Chat")
        self.mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn.setStyleSheet(btn_style)
        self.mode_btn.clicked.connect(self.mode_manager.toggle_mode)
        top.addWidget(self.mode_btn)

        self.index_btn = QPushButton("Build/Update Index")
        self.index_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.index_btn.setStyleSheet(btn_style)
        self.index_btn.clicked.connect(self.start_index_build)
        top.addWidget(self.index_btn)
        
        self.panel_btn = QPushButton("Activity Log")
        self.panel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.panel_btn.setStyleSheet(btn_style)
        self.panel_btn.setToolTip("Show background activity logs (RAG latency, tools used, etc.)")
        self.panel_btn.clicked.connect(self.toggle_panel)
        top.addWidget(self.panel_btn)

        res_btn = QPushButton("Resources")
        res_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        res_btn.setStyleSheet(btn_style)
        res_btn.clicked.connect(self.open_resources)
        top.addWidget(res_btn)
        layout.addLayout(top)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: rgba(255,255,255,0.1); margin: 8px 0px;")
        layout.addWidget(separator)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("ChatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(24)
        self.chat_scroll.setWidget(self.chat_container)

        self.panel_frame = QFrame()
        self.panel_frame.setFixedWidth(280)
        self.panel_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 2px solid {BORDER_LIGHT};
                border-radius: 14px;
            }}
        """)
        panel_layout = QVBoxLayout(self.panel_frame)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)
        panel_title = QLabel("Activity Log")
        panel_title.setStyleSheet("font-size: 14px; font-weight: 800; color: white;")
        panel_layout.addWidget(panel_title)
        self.panel_text = QTextBrowser()
        self.panel_text.setOpenExternalLinks(True)
        panel_layout.addWidget(self.panel_text, 1)
        self.panel_frame.setVisible(False)

        main_row = QHBoxLayout()
        main_row.setSpacing(12)
        main_row.addWidget(self.chat_scroll, 1)
        main_row.addWidget(self.panel_frame)
        layout.addLayout(main_row, 1)

        input_bar = QFrame()
        input_bar.setStyleSheet("QFrame { background: transparent; border: none; }")
        ib = QVBoxLayout(input_bar)
        ib.setContentsMargins(0, 0, 0, 0)
        ib.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        self.rag_label = QLabel("RAGWorker OFF")
        self.rag_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SUB};
                font-size: 12px;
                font-weight: 700;
                padding-left: 2px;
                padding-right: 2px;
            }}
        """)

        self.rag_switch = ToggleSwitch(False)
        self.rag_switch.toggled.connect(self._on_rag_toggled)
        
        self.hist_label = QLabel("Use History OFF")
        self.hist_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SUB};
                font-size: 12px;
                font-weight: 700;
                padding-left: 2px;
                padding-right: 2px;
            }}
        """)
        self.hist_switch = ToggleSwitch(False)
        self.hist_switch.toggled.connect(self._on_hist_toggled)

        top_row.addWidget(self.rag_label)
        top_row.addWidget(self.rag_switch)
        top_row.addWidget(self.hist_label)
        top_row.addWidget(self.hist_switch)
        top_row.addStretch()

        sys_ready = QLabel("✓ System Ready")
        sys_ready.setStyleSheet("color: #4ADE80; font-size: 12px; font-weight: bold;")
        top_row.addWidget(sys_ready)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(12)
        bottom_row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.input_box = QTextEdit()
        self.input_box.setObjectName("ChatInput")
        self.input_box.setPlaceholderText("Type your message…")
        self.input_box.setMinimumHeight(44)
        self.input_box.setMaximumHeight(150)
        self.input_box.installEventFilter(self)
        
        # Style the ChatInput directly to match the rounded search bar look
        self.input_box.setStyleSheet("QTextEdit#ChatInput { background-color: #242430; border: 2px solid rgba(255,255,255,0.1); border-radius: 22px; padding: 10px 16px; font-size: 14px; color: #D1D1D6; } QTextEdit#ChatInput:focus { border: 2px solid #3B82F6; }")

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedSize(84, 44)
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(90, 44)
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send_clicked)

        bottom_row.addWidget(self.input_box, 1)
        bottom_row.addWidget(self.stop_btn, 0, Qt.AlignmentFlag.AlignBottom)
        bottom_row.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        ib.addLayout(top_row)
        ib.addLayout(bottom_row)
        layout.addWidget(input_bar)

        splitter.addWidget(self.history_frame)
        splitter.addWidget(chat_pane)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 780])

        self._refresh_history_list()
        
        sessions = self.hm.get_sessions(self.mode_id)
        if sessions:
            first_item = self.hist_list.item(0)
            if first_item:
                self._on_hist_item_clicked(first_item)
        else:
            self._on_new_chat()

    def _on_hist_toggled(self, checked: bool):
        self._use_history = checked
        self.hist_label.setText("Use History ON" if checked else "Use History OFF")
        self.hist_label.setStyleSheet(f"""
            QLabel {{
                color: {ACCENT_BLUE if checked else TEXT_SUB};
                font-size: 12px;
                font-weight: 700;
                padding-left: 2px;
                padding-right: 2px;
            }}
        """)

    def _refresh_history_list(self):
        from PyQt6.QtWidgets import QListWidgetItem
        self.hist_list.clear()
        sessions = self.hm.get_sessions(self.mode_id)
        for s in sessions:
            title = s["title"]
            if s["is_pinned"]:
                title = "📌 " + title
            if s["is_protected"]:
                title = "🔒 " + title
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            self.hist_list.addItem(item)

    def _on_new_chat(self):
        self.session_id = self.hm.create_session(self.mode_id, "New Chat")
        self.messages.clear()
        self._clear_chat_ui()
        self._add_system_card()
        self._refresh_history_list()

    def _on_hist_item_clicked(self, item):
        sid = item.data(Qt.ItemDataRole.UserRole)
        self.session_id = sid
        self._clear_chat_ui()
        self.messages.clear()
        msgs = self.hm.get_messages(sid)
        if not msgs:
            self._add_system_card()
        for m in msgs:
            role = m["role"]
            content = m["content"]
            self.messages.append({"role": role, "content": content})
            self._add_bubble(role, content)

    def _show_hist_context_menu(self, pos):
        item = self.hist_list.itemAt(pos)
        if not item:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        sinfo = self.hm.get_session_by_id(sid)
        if not sinfo:
            return

        from PyQt6.QtWidgets import QMenu, QInputDialog
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background-color: {CARD_BG}; color: white; border: 2px solid {BORDER_LIGHT}; }} QMenu::item:selected {{ background: {ACCENT_BLUE}; }}")

        action_rename = menu.addAction("Rename")
        action_pin = menu.addAction("Unpin" if sinfo["is_pinned"] else "Pin")
        action_protect = menu.addAction("Unprotect" if sinfo["is_protected"] else "Protect")
        action_delete = menu.addAction("Delete")

        action = menu.exec(self.hist_list.mapToGlobal(pos))
        if action == action_rename:
            new_title, ok = QInputDialog.getText(self, "Rename Session", "Enter new title:", text=sinfo["title"])
            if ok and new_title.strip():
                self.hm.rename_session(sid, new_title.strip())
                self._refresh_history_list()
        elif action == action_pin:
            self.hm.toggle_pin(sid, not sinfo["is_pinned"])
            self._refresh_history_list()
        elif action == action_protect:
            self.hm.toggle_protect(sid, not sinfo["is_protected"])
            self._refresh_history_list()
        elif action == action_delete:
            self.hm.delete_session(sid)
            # Deep cleanup of archives
            archive_dir = os.path.join("rag_indexes", self.mode_id, "history_archives")
            if os.path.exists(archive_dir):
                for f in os.listdir(archive_dir):
                    if f.startswith(sid):
                        try:
                            os.remove(os.path.join(archive_dir, f))
                        except Exception:
                            pass
            
            # Auto rebuild index to remove it from FAISS
            self.start_index_build()

            if self.session_id == sid:
                # Need to clear current chat if it's the one being deleted
                self.session_id = None
                self._clear_chat_ui()
                self._add_system_card()
            
            self._refresh_history_list()

    def _clear_chat_ui(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()
        self._current_bubble = None
        self._current_browser = None
        self._bubble_meta.clear()
        self._current_reply_raw = ""
        self._current_reply_final = ""
        self._current_reply_meta = ""
        self._router_buffer = ""
        self._router_mode = "final"
        self._index_bubble = None
        self._index_browser = None

    def _on_mode_changed(self, mode: str):
        self.mode_btn.setText(f"Mode: {mode.capitalize()}")
        if mode == "agent":
            active_agent = get_agent(self.llm_cfg, self.llm_cfg.get("active_agent_id")) or {}
            base_url = (active_agent.get("base_url") or "").strip()
            is_ollama = "127.0.0.1:11434" in base_url or "localhost:11434" in base_url or is_ollama_endpoint(base_url)
            if active_agent.get("type") == "local" and (is_ollama or active_agent.get("engine") == "ollama_native"):
                QMessageBox.warning(self, "Agent Mode Limitation", 
                    "Local models (Ollama) often struggle with tool-calling and complex agent tasks. "
                    "For best results, please switch to a cloud-based API model (DeepSeek/OpenAI/etc.) in Settings.")

    def _on_rag_toggled(self, enabled: bool):
        self._rag_enabled = bool(enabled)
        if self._rag_enabled:
            self.rag_label.setText("RAGWorker ON")
            self.rag_label.setStyleSheet(f"""
                QLabel {{
                    color: {ACCENT_BLUE};
                    font-size: 12px;
                    font-weight: 800;
                    padding-left: 2px;
                    padding-right: 2px;
                }}
            """)
        else:
            self.rag_label.setText("RAGWorker OFF")
            self.rag_label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_SUB};
                    font-size: 12px;
                    font-weight: 700;
                    padding-left: 2px;
                    padding-right: 2px;
                }}
            """)

    def stop_generation(self):
        self._panel_append("[System] User stopped generation.")
        if self._active_worker:
            self._active_worker.cancel()
        if self._rag_worker:
            self._rag_worker.cancel()
        if self._index_worker:
            self._index_worker.cancel()
            
        self.stop_btn.setEnabled(False)
        self._render_queue.clear()
        if self._cursor_timer.isActive():
            self._cursor_timer.stop()
        
        if not self._stream_finished:
            self._stream_error = "Stopped by user."

    def open_resources(self):
        # We now edit repo_paths which are independent from Quick Resources
        d = ConfigDialog(
            task_name=self.task_name,
            paths=self.resources,
            parent=self,
            title="Edit Resource Repo",
            name_placeholder=""
        )
        if d.exec() == QDialog.DialogCode.Accepted:
            _, new_paths = d.get_data()
            self.resources = new_paths
            # Save back to tasks_config.json via MainWindow
            for t in self.app_window.tasks_data:
                if t.get("mode_id") == self.mode_id:
                    t["repo_paths"] = new_paths
                    break
            self.app_window.save_config()

    def toggle_panel(self):
        show = not self.panel_frame.isVisible()
        self.panel_frame.setVisible(show)

    def _panel_append(self, text: str):
        if not self.panel_text:
            return
        t = (text or "").strip()
        if not t:
            return
        cur = self.panel_text.toPlainText().strip()
        merged = (cur + "\n" + t).strip() if cur else t
        lines = merged.splitlines()
        if len(lines) > 300:
            merged = "\n".join(lines[-300:])
        self.panel_text.setPlainText(merged)
        sb = self.panel_text.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def start_index_build(self):
        if self._index_thread is not None:
            return
        if not self.mode_id:
            self._add_bubble("assistant", "[Index] mode_id is empty.")
            return
        self._index_bubble, self._index_browser = self._add_bubble("assistant", "[Indexing] Starting...")

        if self.rag_switch.isChecked():
            self.rag_switch.setChecked(False)
        self.rag_switch.setEnabled(False)
        self.index_btn.setEnabled(False)

        worker = IndexWorker(self.mode_id)
        thread = QThread(self)
        self._index_thread = thread
        self._index_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_index_progress)
        worker.done.connect(self._on_index_done)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_index_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._start_scan_line()
        thread.start()

    def _on_index_progress(self, msg: str):
        if self._index_browser and self._index_bubble:
            self._update_bubble(self._index_browser, self._index_bubble, f"[Indexing] {msg}")

    def _on_index_thread_finished(self):
        self._index_thread = None
        self._index_worker = None
        self._index_browser = None
        self._index_bubble = None
        self._stop_scan_line()
        self.rag_switch.setEnabled(True)
        self.index_btn.setEnabled(True)

    def _on_index_done(self, message: str, error: str):
        if error:
            if self._index_browser and self._index_bubble:
                self._update_bubble(self._index_browser, self._index_bubble, f"[Index Error] {error}")
            else:
                self._add_bubble("assistant", f"[Index Error] {error}")
            return
        if self._index_browser and self._index_bubble:
            self._update_bubble(self._index_browser, self._index_bubble, f"[Index] {message}")
        else:
            self._add_bubble("assistant", f"[Index] {message}")

    def _add_system_card(self):
        msg = QLabel("Chat is ready. Configure models via the gear icon on the main panel if needed.")
        msg.setWordWrap(True)
        msg.setStyleSheet(f"font-size: 12px; color: {TEXT_SUB};")
        self.chat_layout.addWidget(msg)
        self._scroll_to_bottom(animate=False)

    def _should_autoscroll(self) -> bool:
        bar = self.chat_scroll.verticalScrollBar()
        if not bar:
            return True
        return bar.value() >= bar.maximum() - 90

    def _scroll_to_bottom(self, animate: bool = True, force: bool = False):
        bar = self.chat_scroll.verticalScrollBar()
        if not force and not self._should_autoscroll():
            return
        target = bar.maximum()
        if not animate:
            bar.setValue(target)
            return
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(220)
        anim.setStartValue(bar.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animations.append(anim)
        anim.finished.connect(lambda: self._animations.remove(anim) if anim in self._animations else None)
        anim.start()

    def _bubble_max_width(self) -> int:
        vp = self.chat_scroll.viewport()
        w = vp.width() if vp else 860
        return max(540, min(1110, int(w * 0.95)))

    def _resize_bubble_content(self, browser: QTextBrowser, bubble: QFrame):
        if not browser or not bubble:
            return
        max_bubble_width = self._bubble_max_width()
        bubble.setMaximumWidth(max_bubble_width)
        padding_x = 34
        browser.document().setTextWidth(-1)
        ideal_width = browser.document().idealWidth()
        actual_content_width = min(max(220, int(ideal_width)), max_bubble_width - padding_x)
        browser.document().setTextWidth(actual_content_width)
        doc_height = browser.document().size().height()
        browser.setFixedSize(int(actual_content_width) + 2, int(doc_height) + 8)

    def eventFilter(self, obj, event):
        if obj is self.input_box:
            if event.type() == QEvent.Type.FocusIn:
                self._set_input_glow(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_input_glow(False)
        return super().eventFilter(obj, event)

    def _set_input_glow(self, enabled: bool):
        if not hasattr(self, "_input_glow_effect") or self._input_glow_effect is None:
            self._input_glow_effect = QGraphicsDropShadowEffect(self.input_box)
            self._input_glow_effect.setOffset(0, 0)
            self._input_glow_effect.setBlurRadius(0)
            self._input_glow_effect.setColor(QColor(0, 0, 0, 0))
            self.input_box.setGraphicsEffect(self._input_glow_effect)

        if enabled:
            self._input_glow_effect.setColor(QColor(62, 99, 255, 120))
            if hasattr(self, "_input_glow_pulse") and self._input_glow_pulse:
                self._input_glow_pulse.stop()
            pulse = QPropertyAnimation(self._input_glow_effect, b"blurRadius", self)
            pulse.setDuration(1600)
            pulse.setKeyValueAt(0.0, 8)
            pulse.setKeyValueAt(0.5, 22)
            pulse.setKeyValueAt(1.0, 8)
            pulse.setLoopCount(-1)
            pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
            pulse.start()
            self._input_glow_pulse = pulse
            return

        if hasattr(self, "_input_glow_pulse") and self._input_glow_pulse:
            self._input_glow_pulse.stop()
            self._input_glow_pulse = None
        self._input_glow_effect.setColor(QColor(0, 0, 0, 0))
        anim = QPropertyAnimation(self._input_glow_effect, b"blurRadius", self)
        anim.setDuration(180)
        anim.setStartValue(self._input_glow_effect.blurRadius())
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animations.append(anim)
        anim.finished.connect(lambda: self._animations.remove(anim) if anim in self._animations else None)
        anim.start()

    def _on_send_clicked(self):
        self._play_send_button_animation()
        self.send_message()

    def _play_send_button_animation(self):
        btn = self.send_btn
        if not btn or not btn.isEnabled():
            return
        g0 = btn.geometry()
        shrink = 3
        g1 = g0.adjusted(shrink, shrink, -shrink, -shrink)
        a1 = QPropertyAnimation(btn, b"geometry", self)
        a1.setDuration(80)
        a1.setStartValue(g0)
        a1.setEndValue(g1)
        a1.setEasingCurve(QEasingCurve.Type.OutCubic)
        a2 = QPropertyAnimation(btn, b"geometry", self)
        a2.setDuration(120)
        a2.setStartValue(g1)
        a2.setEndValue(g0)
        a2.setEasingCurve(QEasingCurve.Type.OutCubic)
        group = QSequentialAnimationGroup(self)
        group.addAnimation(a1)
        group.addAnimation(a2)
        group.start()

    def _on_cursor_tick(self):
        if not self._current_bubble or not self._current_browser:
            return
        if self._stream_finished:
            return
        self._cursor_visible = not self._cursor_visible
        self._render_current_stream_ui()

    def _split_stream_parts(self, chunk: str) -> list[str]:
        s = chunk or ""
        if not s:
            return []
        out: list[str] = []
        buf = ""
        for ch in s:
            buf += ch
            if ch == "\n" or len(buf) >= 12:
                out.append(buf)
                buf = ""
        if buf:
            out.append(buf)
        return out

    def _route_stream(self, text: str) -> tuple[str, str]:
        self._router_buffer += text
        final_out: list[str] = []
        meta_out: list[str] = []

        pattern = r"(<think>|</think>|(?:^|\n)(?:Thought:|Action:|Action Input:|Observation:|Final:|\\*\\*Observation\\*\\*:))"
        while True:
            m = re.search(pattern, self._router_buffer)
            if not m:
                break
            idx = m.start()
            token = m.group(0)
            prefix = self._router_buffer[:idx]
            self._router_buffer = self._router_buffer[idx + len(token):]
            if token.startswith("\n"):
                prefix += "\n"
                token = token[1:]

            if self._router_mode == "final":
                final_out.append(prefix)
            else:
                meta_out.append(prefix)

            t = token.strip()
            if t == "<think>":
                self._router_mode = "meta"
                continue
            if t == "</think>":
                self._router_mode = "final"
                continue
            if t == "Final:":
                self._router_mode = "final"
                continue
            if t in ("Thought:", "Action:", "Action Input:", "Observation:", "**Observation:**"):
                self._router_mode = "meta"
                meta_out.append(t)
                continue

        if len(self._router_buffer) > 96:
            safe = self._router_buffer[:-48]
            self._router_buffer = self._router_buffer[-48:]
            if self._router_mode == "final":
                final_out.append(safe)
            else:
                meta_out.append(safe)

        return ("".join(final_out), "".join(meta_out))

    def _flush_router(self) -> tuple[str, str]:
        buf = self._router_buffer
        self._router_buffer = ""
        if not buf:
            return ("", "")
        if self._router_mode == "final":
            return (buf, "")
        return ("", buf)

    def _render_current_stream_ui(self):
        if not self._current_browser or not self._current_bubble:
            return
        cursor = "▍" if self._cursor_visible else ""
        shown = self._current_reply_final
        if not shown and not self._current_reply_meta and self._current_reply_raw:
            shown = self._current_reply_raw
        self._current_browser.setPlainText((shown or "").rstrip("\n") + cursor)
        self._resize_bubble_content(self._current_browser, self._current_bubble)
        meta = self._bubble_meta.get(self._current_bubble)
        if meta:
            meta.set_meta_text(self._current_reply_meta)
        self._scroll_to_bottom(animate=True)

    def _add_bubble(self, role: str, text: str):
        role = role or "assistant"
        text = (text or "").strip("\n")
        is_user = role == "user"
        was_at_bottom = self._should_autoscroll()
        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        bubble = QFrame()
        bubble.setObjectName("UserBubble" if is_user else "AgentBubble")
        bubble.setFrameShape(QFrame.Shape.NoFrame)
        bubble.setLineWidth(0)
        b = QVBoxLayout(bubble)
        b.setContentsMargins(14, 12, 14, 12)
        b.setSpacing(10)

        meta_box = None
        if not is_user:
            meta_box = CollapsibleMetaBox(bubble)
            b.addWidget(meta_box)
            self._bubble_meta[bubble] = meta_box

        content = QTextBrowser(bubble)
        content.setObjectName("BubbleText")
        content.setOpenExternalLinks(True)
        content.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        content.setFrameShape(QFrame.Shape.NoFrame)
        content.setFrameShadow(QFrame.Shadow.Plain)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.document().setDocumentMargin(0)

        if text.strip():
            content.setMarkdown(text)
        else:
            content.setPlainText("")
        self._resize_bubble_content(content, bubble)
        b.addWidget(content)

        if is_user:
            outer.addStretch()
            outer.addWidget(bubble, 0)
        else:
            outer.addWidget(bubble, 0)
            outer.addStretch()

        row = QWidget()
        row.setLayout(outer)
        self.chat_layout.addWidget(row)

        if not is_user:
            shadow = QGraphicsDropShadowEffect(bubble)
            shadow.setBlurRadius(28)
            shadow.setOffset(0, 10)
            shadow.setColor(QColor(0, 0, 0, 120))
            bubble.setGraphicsEffect(shadow)

        if was_at_bottom:
            self._scroll_to_bottom(animate=True, force=True)
        return bubble, content

    def _update_bubble(self, browser: QTextBrowser, bubble: QFrame, text: str):
        try:
            if not browser or not bubble:
                return
            browser.setMarkdown(text)
            self._resize_bubble_content(browser, bubble)
            self._scroll_to_bottom(animate=True)
        except Exception:
            pass

    def _enqueue_chunk(self, chunk: str):
        if not chunk:
            return
        for part in self._split_stream_parts(chunk):
            self._render_queue.append(part)
        if not self._paused:
            if not self._render_timer.isActive():
                self._render_timer.start()
            if not self._cursor_timer.isActive():
                self._cursor_timer.start()

    def _flush_render(self):
        if self._paused:
            if self._render_timer.isActive():
                self._render_timer.stop()
            return
        if not self._current_browser or not self._current_bubble:
            self._render_queue.clear()
            if self._render_timer.isActive():
                self._render_timer.stop()
            return
        if not self._render_queue:
            if self._render_timer.isActive():
                self._render_timer.stop()
            if self._stream_finished:
                self._finalize_stream()
            return

        pulled = []
        budget = 18
        while self._render_queue and budget > 0:
            p = self._render_queue.popleft()
            pulled.append(p)
            budget -= max(1, len(p))

        delta = "".join(pulled)
        if delta:
            self._current_reply_raw += delta
            final_add, meta_add = self._route_stream(delta)
            if final_add:
                self._current_reply_final += final_add
            if meta_add:
                self._current_reply_meta += meta_add
            self._render_current_stream_ui()

    def _finalize_stream(self):
        self.stop_btn.setEnabled(False)
        self.send_btn.setDisabled(False)
        if self._cursor_timer.isActive():
            self._cursor_timer.stop()
        if self._stream_error:
            if self._current_browser and self._current_bubble:
                self._update_bubble(self._current_browser, self._current_bubble, f"[Error] {self._stream_error}")
            self._stream_error = ""
            self._stream_finished = False
            return
        final_add, meta_add = self._flush_router()
        if final_add:
            self._current_reply_final += final_add
        if meta_add:
            self._current_reply_meta += meta_add

        shown = (self._current_reply_final or "").strip()
        fallback = (self._current_reply_raw or "").strip()
        visible_text = shown if shown else fallback
        if self._current_browser and self._current_bubble:
            self._update_bubble(self._current_browser, self._current_bubble, visible_text)
            meta = self._bubble_meta.get(self._current_bubble)
            if meta:
                meta.set_meta_text(self._current_reply_meta)

        if self._current_reply_raw:
            self.messages.append({"role": "assistant", "content": self._current_reply_raw})
            if self.session_id:
                self.hm.add_message(self.session_id, "assistant", self._current_reply_raw)
                self._refresh_history_list()
                self._check_and_archive_history()
        self._stream_finished = False

    def _check_and_archive_history(self):
        if not self.session_id:
            return
        msgs = self.hm.get_messages(self.session_id)
        if len(msgs) > 40:
            to_archive = msgs[:-20] # Keep last 20
            if not to_archive:
                return
            
            archive_dir = os.path.join("rag_indexes", self.mode_id, "history_archives")
            os.makedirs(archive_dir, exist_ok=True)
            
            sinfo = self.hm.get_session_by_id(self.session_id)
            title = sinfo["title"] if sinfo else "Session"
            
            timestamp = int(time.time())
            filename = f"{self.session_id}_{timestamp}.md"
            filepath = os.path.join(archive_dir, filename)
            
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# Archive for {title}\n\n")
                    for m in to_archive:
                        role = "User" if m["role"] == "user" else "Agent"
                        f.write(f"**{role}**: {m['content']}\n\n")
                
                # Delete archived messages from DB
                last_ts = to_archive[-1]["timestamp"]
                self.hm.delete_messages_up_to(self.session_id, last_ts)
                
                self._panel_append(f"[System] History compressed. Archived {len(to_archive)} messages to {filepath}")
                
                # Build index automatically
                self.start_index_build()
                
                # Update current messages in UI
                self.messages = msgs[-20:]
            except Exception as e:
                self._panel_append(f"[System] Failed to archive history: {e}")

    def _build_messages(self):
        return list(self.messages)

    def send_message(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        
        if not self.session_id:
            self._on_new_chat()
            
        self.hm.add_message(self.session_id, "user", text)
        
        sinfo = self.hm.get_session_by_id(self.session_id)
        if sinfo and sinfo["title"] == "New Chat":
            new_title = text[:15].strip()
            if len(text) > 15:
                new_title += "..."
            self.hm.rename_session(self.session_id, new_title)
            self._refresh_history_list()
            
        self.input_box.clear()
        self.messages.append({"role": "user", "content": text})
        self._add_bubble("user", text)
        self.send_btn.setDisabled(True)
        if self._rag_enabled:
            self._start_rag_request(text)
        else:
            self._start_chat_request()

    def _start_rag_request(self, question: str):
        if self._rag_thread is not None:
            return
        if not self.mode_id:
            self._start_chat_request()
            return

        self._current_bubble, self._current_browser = self._add_bubble("assistant", "Retrieving…")
        self._current_reply_raw = ""
        self._current_reply_final = ""
        self._current_reply_meta = ""
        self._router_buffer = ""
        self._router_mode = "final"

        worker = RAGWorker(self.mode_id, question, top_k=4, budget_chars=1600, use_history=self._use_history)
        thread = QThread(self)
        self._rag_thread = thread
        self._rag_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_rag_done)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_rag_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._start_scan_line()
        thread.start()

    def _on_rag_thread_finished(self):
        self._rag_thread = None
        self._rag_worker = None
        self._stop_scan_line()

    def _on_rag_done(self, context: str, error: str, stats: dict):
        if error:
            if self._current_browser and self._current_bubble:
                self._update_bubble(self._current_browser, self._current_bubble, f"[RAG Error] {error}")
            self.send_btn.setDisabled(False)
            return

        if isinstance(stats, dict) and stats:
            ms = stats.get("retrieve_ms")
            sources = stats.get("sources") or []
            if ms is not None:
                self._panel_append(f"[RAG] {ms} ms")
            if sources:
                self._panel_append("[RAG] Sources:\n" + "\n".join([f"- {s}" for s in sources[:10]]))

        base_messages = self._build_messages()
        ctx = (context or "").strip()
        if ctx:
            base_messages.insert(len(base_messages) - 1, {"role": "system", "content": "Use the following context if relevant:\n\n" + ctx})
        self._start_chat_request(messages_override=base_messages, use_existing_bubble=True)

    def _start_chat_request(self, messages_override: list[dict] | None = None, use_existing_bubble: bool = False):
        if self._active_thread is not None:
            return
        cfg = normalize_llm_config(self.llm_cfg)
        agent_id = cfg.get("active_agent_id")
        agent = get_agent(cfg, agent_id) or {}
        messages = messages_override if isinstance(messages_override, list) else self._build_messages()
        worker = ChatWorker(
            llm_cfg=cfg,
            agent=agent,
            messages=messages,
            mode=self.mode_manager.current_mode,
            mode_id=self.mode_id,
            ensure_local_runner=self.app_window.ensure_local_model_running if self.app_window else None,
        )
        thread = QThread(self)
        self._active_thread = thread
        self._active_worker = worker
        
        self._current_reply_raw = ""
        self._current_reply_final = ""
        self._current_reply_meta = ""
        self._router_buffer = ""
        self._router_mode = "final"
        self._render_queue.clear()
        self._stream_finished = False
        self._stream_error = ""
        self._paused = False
        self.stop_btn.setEnabled(True)
        if not use_existing_bubble or self._current_bubble is None or self._current_browser is None:
            self._current_bubble, self._current_browser = self._add_bubble("assistant", "")
        else:
            self._current_browser.setPlainText("")
            self._resize_bubble_content(self._current_browser, self._current_bubble)
            meta = self._bubble_meta.get(self._current_bubble)
            if meta:
                meta.set_meta_text("")

        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.chunk_received.connect(self._enqueue_chunk)
        worker.tool_event.connect(self._on_tool_event)
        worker.done.connect(self._on_chat_done)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        if not self._render_timer.isActive():
            self._render_timer.start()
        self._start_scan_line()
        thread.start()

    def _start_scan_line(self):
        parent = self.scan_line.parentWidget()
        w = parent.width()
        self.scan_line.setFixedWidth(int(w * 0.4))
        self.scan_line.show()
        self.scan_anim.setStartValue(QPoint(-self.scan_line.width(), 0))
        self.scan_anim.setEndValue(QPoint(w, 0))
        self.scan_anim.start()

    def _stop_scan_line(self):
        self.scan_anim.stop()
        self.scan_line.hide()

    def _on_thread_finished(self):
        self._active_thread = None
        self._active_worker = None
        self._stream_finished = True
        self._stop_scan_line()

    def closeEvent(self, event):
        if self._render_timer.isActive():
            self._render_timer.stop()
        if self._cursor_timer.isActive():
            self._cursor_timer.stop()

        if self._index_worker:
            self._index_worker.cancel()
        if self._active_worker:
            self._active_worker.cancel()
        if self._rag_worker:
            self._rag_worker.cancel()

        if self._rag_thread is not None and self._rag_thread.isRunning():
            try:
                self._rag_thread.quit()
                self._rag_thread.wait(100)
            except Exception:
                pass
        if self._index_thread is not None and self._index_thread.isRunning():
            try:
                self._index_thread.quit()
                self._index_thread.wait(100)
            except Exception:
                pass
        if self._active_thread is not None and self._active_thread.isRunning():
            try:
                self._active_thread.quit()
                self._active_thread.wait(100)
            except Exception:
                pass
        super().closeEvent(event)

    def _on_chat_done(self, reply: str, error: str):
        if error:
            self._render_queue.clear()
            self._stream_error = error
            self._stream_finished = True
            if not self._paused:
                self._finalize_stream()
            return
        
        self._stream_finished = True
        if not self._paused and not self._render_queue:
            self._finalize_stream()

    def _on_tool_event(self, ev: dict):
        if not isinstance(ev, dict):
            return
        phase = (ev.get("phase") or "").strip()
        name = (ev.get("name") or "").strip()
        ms = ev.get("ms")
        ok = ev.get("ok")
        if phase == "start":
            self._panel_append(f"[Tool] {name} (start)")
            return
        if phase == "end":
            tail = ""
            if ms is not None:
                tail += f" {int(ms)}ms"
            if ok is False:
                tail += " ERROR"
            self._panel_append(f"[Tool] {name} (end){tail}")
            return


class RAGWorker(QObject):
    done = pyqtSignal(str, str, dict)

    def __init__(self, mode_id: str, query: str, top_k: int = 4, budget_chars: int = 1600, use_history: bool = False):
        super().__init__()
        self.mode_id = (mode_id or "").strip()
        self.query = (query or "").strip()
        self.top_k = int(top_k)
        self.budget_chars = int(budget_chars)
        self.use_history = use_history
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self._is_cancelled:
                return
            if not self.mode_id:
                self.done.emit("", "mode_id is empty", {})
                return
            if not self.query:
                self.done.emit("", "", {})
                return
            from rag_engine import RAGEngine

            rag = RAGEngine()
            rag.set_mode(self.mode_id)
            t0 = time.perf_counter()
            hits = rag.retrieve(self.query, top_k=self.top_k)
            
            if self.use_history:
                rag_hist = RAGEngine()
                rag_hist.set_mode(self.mode_id, subdir="history")
                hist_hits = rag_hist.retrieve(self.query, top_k=self.top_k)
                hits.extend(hist_hits)
                hits.sort(key=lambda x: x.get("score", 0), reverse=True)
                hits = hits[:self.top_k]
                
            t1 = time.perf_counter()
            ctx = self._build_context(hits, self.budget_chars)
            srcs = []
            seen = set()
            for h in hits or []:
                s = (h.get("source") or "").strip()
                if not s:
                    continue
                k = s.lower()
                if k in seen:
                    continue
                seen.add(k)
                srcs.append(os.path.basename(s) if os.path.basename(s) else s)
            stats = {"retrieve_ms": int((t1 - t0) * 1000), "sources": srcs}
            self.done.emit(ctx, "", stats)
        except Exception as e:
            self.done.emit("", str(e), {})

    def _build_context(self, hits: list, budget_chars: int):
        items = [h for h in (hits or []) if isinstance(h, dict) and (h.get("text") or "").strip()]
        used = 0
        out = []
        for i, h in enumerate(items, 1):
            source = (h.get("source") or h.get("doc_id") or "").strip()
            text = (h.get("text") or "").strip()
            block = f"[{i}] {source}\n{text}\n"
            if used + len(block) > budget_chars:
                remain = max(0, budget_chars - used - len(f"[{i}] {source}\n") - 1)
                if remain <= 0:
                    break
                out.append(f"[{i}] {source}\n{text[:remain]}…\n")
                used = budget_chars
                break
            out.append(block)
            used += len(block)
        return "\n".join(out).strip()


class IndexWorker(QObject):
    done = pyqtSignal(str, str)
    progress = pyqtSignal(str)

    def __init__(self, mode_id: str):
        super().__init__()
        self.mode_id = (mode_id or "").strip()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self.mode_id:
                self.done.emit("", "mode_id is empty")
                return
            if self._is_cancelled:
                return

            from rag_engine import WorkflowResourcesPlugin, RAGEngine, ChatHistoryPlugin

            self.progress.emit("Initializing indexing engine...")
            plugin = WorkflowResourcesPlugin()
            sig = plugin.signature(self.mode_id)
            mode_dir = os.path.join("rag_indexes", self.mode_id)
            os.makedirs(mode_dir, exist_ok=True)
            sig_path = os.path.join(mode_dir, "sources_manifest.json")

            # Collect normal docs
            docs = plugin.collect_documents(self.mode_id)
            
            # Collect history docs
            hist_plugin = ChatHistoryPlugin()
            hist_docs = hist_plugin.collect_documents(self.mode_id)

            if not docs and not hist_docs:
                self.done.emit("No readable documents or history found.", "")
                return

            def on_progress(msg):
                self.progress.emit(msg)
                
            chunks = 0
            if docs:
                rag = RAGEngine()
                rag.set_mode(self.mode_id)
                rag.clear() # Clear memory state to ensure fresh index build
                c = rag.ingest(
                    docs, 
                    cancel_check=lambda: self._is_cancelled,
                    progress_callback=on_progress
                )
                if c == -1:
                    self.done.emit("Indexing cancelled. Original index preserved.", "")
                    return
                chunks += c
                with open(sig_path, "w", encoding="utf-8") as f:
                    json.dump(sig, f, ensure_ascii=False, indent=2)
            
            hist_chunks = 0
            if hist_docs:
                rag_hist = RAGEngine()
                rag_hist.set_mode(self.mode_id, subdir="history")
                rag_hist.clear()
                hc = rag_hist.ingest(
                    hist_docs, 
                    cancel_check=lambda: self._is_cancelled,
                    progress_callback=on_progress
                )
                if hc == -1:
                    self.done.emit("Indexing cancelled. Original index preserved.", "")
                    return
                hist_chunks += hc

            self.done.emit(f"Indexed {len(docs)} documents ({chunks} chunks), {len(hist_docs)} history sessions ({hist_chunks} chunks).", "")
        except Exception as e:
            self.done.emit("", str(e))


class ChatWorker(QObject):
    chunk_received = pyqtSignal(str)
    done = pyqtSignal(str, str)
    tool_event = pyqtSignal(dict)

    def __init__(self, llm_cfg: dict, agent: dict, messages: list[dict], mode: str = "chat", mode_id: str = "", ensure_local_runner=None):
        super().__init__()
        self.llm_cfg = llm_cfg
        self.agent = agent
        self.messages = messages
        self.mode = (mode or "chat").strip()
        self.mode_id = (mode_id or "").strip()
        self.ensure_local_runner = ensure_local_runner
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.mode == "agent":
                self._run_react_loop()
                return
            self._run_chat_once(self.messages)
        except urllib.error.HTTPError as e:
            try:
                raw = e.read().decode("utf-8", errors="replace")
                self.done.emit("", f"HTTP {e.code}: {raw}")
            except Exception:
                self.done.emit("", f"HTTP error: {e}")
        except Exception as e:
            self.done.emit("", str(e))

    def _run_chat_once(self, messages):
        agent_type = (self.agent.get("type") or "").strip()
        base_url = (self.agent.get("base_url") or "").strip()
        model = (self.agent.get("model") or "").strip()
        full_reply = ""

        if agent_type == "api":
            agent_id = self.agent.get("id")
            api_key = (((self.llm_cfg.get("secrets") or {}).get(agent_id) or {}).get("api_key") or "").strip()
            if not api_key:
                raise RuntimeError("API Key is empty. Click the gear icon to set it.")
            extra_body = self.agent.get("extra_body") if isinstance(self.agent.get("extra_body"), dict) else None
            stream_options = self.agent.get("stream_options") if isinstance(self.agent.get("stream_options"), dict) else None
            for chunk in chat_openai_compatible_stream(base_url, api_key, model, messages, extra_body=extra_body, stream_options=stream_options):
                if self._is_cancelled:
                    break
                full_reply += chunk
                self.chunk_received.emit(chunk)
            self.done.emit(full_reply, "")
            return

        if agent_type == "local":
            folder_path = (self.agent.get("folder_path") or "").strip()
            if self.ensure_local_runner is not None:
                self.ensure_local_runner(folder_path, self.agent)
            
            # Use /api/chat if it's an Ollama endpoint (more robust for chat mode)
            if is_ollama_endpoint(base_url) or "127.0.0.1:11434" in base_url or "localhost:11434" in base_url:
                for chunk in chat_ollama_stream(base_url, model, messages):
                    if self._is_cancelled:
                        break
                    full_reply += chunk
                    self.chunk_received.emit(chunk)
            else:
                for chunk in chat_openai_compatible_stream(base_url, None, model, messages):
                    if self._is_cancelled:
                        break
                    full_reply += chunk
                    self.chunk_received.emit(chunk)
            self.done.emit(full_reply, "")
            return

        raise RuntimeError("Unknown agent type.")

    def _run_react_loop(self):
        from langgraph.prebuilt import create_react_agent
        from langchain_core.tools import Tool
        
        agent_type = (self.agent.get("type") or "").strip()
        base_url = (self.agent.get("base_url") or "").strip()
        model_name = (self.agent.get("model") or "").strip()

        if agent_type == "local":
            is_ollama = "127.0.0.1:11434" in base_url or "localhost:11434" in base_url or is_ollama_endpoint(base_url)
            engine = (self.agent.get("engine") or "auto").strip()
            if is_ollama or engine == "ollama_native":
                raise RuntimeError("Local models (Ollama) are not powerful enough for Agent mode. Please use a cloud-based API model (like DeepSeek, OpenAI, or Claude) for reliable tool execution.")

        api_key = "dummy"
        if agent_type == "api":
            agent_id = self.agent.get("id")
            api_key = (((self.llm_cfg.get("secrets") or {}).get(agent_id) or {}).get("api_key") or "").strip()
            if not api_key:
                raise RuntimeError("API Key is empty. Click the gear icon to set it.")
        elif agent_type == "local":
            folder_path = (self.agent.get("folder_path") or "").strip()
            if self.ensure_local_runner is not None:
                self.ensure_local_runner(folder_path, self.agent)
        else:
            raise RuntimeError("Unknown agent type.")
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            streaming=True,
            temperature=0.7
        )

        tools = self._build_langchain_tools()

        perms = self.llm_cfg.get("agent_permissions", {}) if isinstance(self.llm_cfg, dict) else {}
        full_access = bool(perms.get("full_access", False))
        restricted_root = (perms.get("restricted_root_dir") or "D:\\").strip()
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop").replace("\\", "/")
        allowed_roots = []
        if full_access:
            for ch in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                p = f"{ch}:\\"
                if os.path.exists(p):
                    allowed_roots.append(p)
        else:
            allowed_roots.append(restricted_root if restricted_root else "D:\\")

        allowed_roots_display = []
        for r in allowed_roots:
            allowed_roots_display.append(str(r).replace("\\", "/"))

        system_prompt = (
            "You are ShadowLink Agent, a helpful and intelligent AI assistant.\n\n"
            "You can answer user questions directly, OR use tools if you need to look up information.\n"
            "If you just want to talk to the user, simply reply with your message.\n\n"
            "IMPORTANT SYSTEM CONTEXT:\n"
            "- You are running on a Windows system.\n"
            f"- The user's Desktop absolute path is: {desktop_path}\n"
            f"- Allowed root directories: {', '.join(allowed_roots_display)}\n"
            "- If the Desktop is not under an allowed root directory, you MUST NOT claim to create files on Desktop. Use an allowed root directory instead and tell the user where the file is created.\n"
            "- Always use absolute Windows paths when calling file tools.\n"
        )

        agent_executor = create_react_agent(llm, tools, prompt=system_prompt)

        # Convert all messages to langgraph format
        chat_history = []
        for m in self.messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "assistant":
                chat_history.append(("assistant", content))
            else:
                chat_history.append(("user", content))

        # Use stream_mode="updates" to only get the diff/changes from each node.
        # This is the most reliable way to avoid re-emitting full message history.
        try:
            for chunk in agent_executor.stream(
                {"messages": chat_history},
                stream_mode="updates"
            ):
                if self._is_cancelled:
                    break
                
                # chunk is a dict like {'agent': {'messages': [...]}} or {'tools': {'messages': [...]}}
                for node_name, update in chunk.items():
                    new_msgs = update.get("messages", [])
                    for msg in new_msgs:
                        # We only want to output NEW assistant or tool messages.
                        if msg.type == "ai" and msg.content:
                            # It's an assistant message
                            if isinstance(msg.content, str):
                                self.chunk_received.emit(msg.content + "\n\n")
                            elif isinstance(msg.content, list):
                                for part in msg.content:
                                    if isinstance(part, dict) and "text" in part:
                                        self.chunk_received.emit(part["text"] + "\n\n")
                        
                        elif msg.type == "tool" and msg.content:
                            # It's a tool observation
                            self.chunk_received.emit(f"**Observation:**\n```\n{str(msg.content)[:1000]}...\n```\n\n")
                            
            self.done.emit("Agent execution completed.", "")
        except InterruptedError:
            self.done.emit("", "Cancelled")
        except Exception as e:
            err = str(e)
            if "502" in err:
                try:
                    llm2 = ChatOpenAI(
                        model=model_name,
                        api_key=api_key,
                        base_url=base_url,
                        streaming=False,
                        temperature=0.7
                    )
                    agent2 = create_react_agent(llm2, tools, prompt=system_prompt)
                    result = agent2.invoke({"messages": chat_history})
                    msgs = result.get("messages", []) if isinstance(result, dict) else []
                    text = ""
                    for msg in reversed(msgs):
                        try:
                            if getattr(msg, "type", "") == "ai" and getattr(msg, "content", None):
                                text = msg.content if isinstance(msg.content, str) else str(msg.content)
                                break
                        except Exception:
                            continue
                    if text:
                        self.chunk_received.emit(text)
                        self.done.emit("Agent execution completed.", "")
                        return
                except Exception:
                    pass
            self.done.emit("", err)

    def _stream_text(self, messages):
        agent_type = (self.agent.get("type") or "").strip()
        base_url = (self.agent.get("base_url") or "").strip()
        model = (self.agent.get("model") or "").strip()
        full_reply = ""

        if agent_type == "api":
            agent_id = self.agent.get("id")
            api_key = (((self.llm_cfg.get("secrets") or {}).get(agent_id) or {}).get("api_key") or "").strip()
            if not api_key:
                raise RuntimeError("API Key is empty. Click the gear icon to set it.")
            extra_body = self.agent.get("extra_body") if isinstance(self.agent.get("extra_body"), dict) else None
            stream_options = self.agent.get("stream_options") if isinstance(self.agent.get("stream_options"), dict) else None
            for chunk in chat_openai_compatible_stream(base_url, api_key, model, messages, extra_body=extra_body, stream_options=stream_options):
                if self._is_cancelled:
                    break
                full_reply += chunk
                self.chunk_received.emit(chunk)
            return full_reply

        if agent_type == "local":
            folder_path = (self.agent.get("folder_path") or "").strip()
            if self.ensure_local_runner is not None:
                self.ensure_local_runner(folder_path, self.agent)
            if is_ollama_endpoint(base_url):
                for chunk in chat_ollama_stream(base_url, model, messages):
                    if self._is_cancelled:
                        break
                    full_reply += chunk
                    self.chunk_received.emit(chunk)
            else:
                for chunk in chat_openai_compatible_stream(base_url, None, model, messages):
                    if self._is_cancelled:
                        break
                    full_reply += chunk
                    self.chunk_received.emit(chunk)
            return full_reply

        raise RuntimeError("Unknown agent type.")

    def _parse_action(self, text: str):
        if not text:
            return None
        m = None
        for m2 in re.finditer(r"^Action:\s*(?P<tool>[A-Za-z0-9_\-]+)\s*$", text, flags=re.M):
            m = m2
        if not m:
            return None
        tool = m.group("tool").strip()
        input_m = re.search(r"^Action Input:\s*(?P<input>[\s\S]+?)\s*(?=^Thought:|^Final:|^Action:|\Z)", text[m.end():], flags=re.M)
        raw = ""
        if input_m:
            raw = (input_m.group("input") or "").strip()
        if not raw:
            return (tool, {})
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return (tool, data)
            return (tool, {"value": data})
        except Exception:
            return (tool, {"text": raw})

    def _build_langchain_tools(self):
        from langchain_core.tools import Tool
        
        def _list_resources(args):
            # args might be string or dict depending on the agent parsing
            if isinstance(args, dict):
                mid = args.get("mode_id", self.mode_id)
            else:
                mid = self.mode_id
                
            if not mid:
                return "[]"
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = []
            paths = []
            for t in data if isinstance(data, list) else []:
                if isinstance(t, dict) and t.get("mode_id") == mid:
                    raw = t.get("repo_paths", t.get("paths", []))
                    paths = raw if isinstance(raw, list) else []
                    break
            return json.dumps(paths, ensure_ascii=False, indent=2)

        def _read_file(args):
            if isinstance(args, dict):
                path = args.get("path", "")
                max_chars = int(args.get("max_chars", 2000))
            else:
                path = args
                max_chars = 2000
                
            path = str(path).strip()
            if not path:
                return "ERROR: path is empty"
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read(max_chars + 1)
            except Exception:
                try:
                    with open(path, "r", encoding="gb18030", errors="ignore") as f:
                        txt = f.read(max_chars + 1)
                except Exception:
                    return "ERROR: cannot read file"
            if len(txt) > max_chars:
                txt = txt[:max_chars] + "…"
            return txt

        def _search_kb(args):
            if isinstance(args, dict):
                q = args.get("query", "")
                top_k = int(args.get("top_k", 3))
            else:
                q = args
                top_k = 3
                
            q = str(q).strip()
            if not q:
                return "[]"
            from rag_engine import RAGEngine
            rag = RAGEngine()
            rag.set_mode(self.mode_id)
            t0 = time.perf_counter()
            hits = rag.retrieve(q, top_k=top_k)
            t1 = time.perf_counter()
            slim = [{"source": h.get("source"), "score": h.get("score"), "text": (h.get("text") or "")[:400]} for h in hits]
            payload = {"ms": int((t1 - t0) * 1000), "hits": slim}
            return json.dumps(payload, ensure_ascii=False, indent=2)

        # Build base tools
        tools = [
            Tool(
                name="list_workflow_resources",
                description="List current workflow resources. Input should be empty or a dict with mode_id.",
                func=_list_resources
            ),
            Tool(
                name="search_local_kb",
                description="Search local vector index (RAG). Input should be the search query string.",
                func=_search_kb
            )
        ]
        
        # Integrate LangChain Community Toolkits for infrastructure
        from langchain_community.agent_toolkits import FileManagementToolkit
        from langchain_community.tools import DuckDuckGoSearchRun
        
        web_tool = DuckDuckGoSearchRun(
            name="web_search",
            description="A wrapper around DuckDuckGo Search. Input should be a search query."
        )
        tools.append(web_tool)

        try:
            from skill_interface import load_skill_tools_with_report
            extra_tools, report = load_skill_tools_with_report(self.llm_cfg.get("skills", []), {"llm_cfg": self.llm_cfg, "mode_id": self.mode_id})

            def _skills_status(args):
                return json.dumps(report, ensure_ascii=False, indent=2)

            tools.append(
                Tool(
                    name="skills_status",
                    description="Show loaded skills and load errors. Input should be empty.",
                    func=_skills_status
                )
            )
            for t in extra_tools:
                tools.append(t)
        except Exception:
            pass
        
        import os
        perms = self.llm_cfg.get("agent_permissions", {})
        full_access = bool(perms.get("full_access", False))
        restricted_root = (perms.get("restricted_root_dir") or "D:\\").strip()
        if not restricted_root.upper().startswith("D:\\"):
            restricted_root = "D:\\"
        if not os.path.exists(restricted_root):
            try:
                os.makedirs(restricted_root, exist_ok=True)
            except Exception:
                restricted_root = "D:\\"

        def _wrap_tool(t, name_override=None):
            tool_name = name_override or getattr(t, "name", "") or "tool"
            
            # Use StructuredTool to handle multi-parameter dict inputs cleanly
            from langchain_core.tools import StructuredTool
            
            def _run(*args, **kwargs):
                self.tool_event.emit({"phase": "start", "name": tool_name})
                t0 = time.perf_counter()
                try:
                    if hasattr(t, "run"):
                        if kwargs and not args:
                            # If it expects string but we got a dict, format it
                            if getattr(t, "args_schema", None) is None and len(kwargs) == 1:
                                out = t.run(list(kwargs.values())[0])
                            else:
                                out = t.run(kwargs)
                        elif args and not kwargs:
                            out = t.run(args[0] if len(args) == 1 else args)
                        else:
                            out = t.run(args, **kwargs)
                    else:
                        out = t.invoke(kwargs if kwargs else args[0])
                    ms = (time.perf_counter() - t0) * 1000
                    self.tool_event.emit({"phase": "end", "name": tool_name, "ok": True, "ms": int(ms)})
                    return out
                except Exception as e:
                    ms = (time.perf_counter() - t0) * 1000
                    self.tool_event.emit({"phase": "end", "name": tool_name, "ok": False, "ms": int(ms)})
                    return "ERROR: " + str(e)
            
            # If the original tool has an args_schema, we should use it so LLM knows how to pass arguments
            schema = getattr(t, "args_schema", None)
            desc = getattr(t, "description", "") or ""
            
            return StructuredTool(
                name=tool_name,
                description=desc,
                func=_run,
                args_schema=schema
            )

        tools = [_wrap_tool(t) for t in tools]

        if full_access:
            drives = []
            for ch in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                p = f"{ch}:\\"
                if os.path.exists(p):
                    drives.append(ch)
            for ch in drives:
                toolkit = FileManagementToolkit(root_dir=f"{ch}:\\")
                for t in toolkit.get_tools():
                    tools.append(_wrap_tool(t, name_override=f"{t.name}_{ch}"))
        else:
            toolkit = FileManagementToolkit(root_dir=restricted_root)
            for t in toolkit.get_tools():
                tools.append(_wrap_tool(t))

        return tools

    def _build_tools(self):
        return [
            {"name": "list_workflow_resources", "description": "List current workflow resources. Input: {\"mode_id\": \"...\"}"},
            {"name": "read_text_file", "description": "Read a local text/markdown file. Input: {\"path\": \"...\", \"max_chars\": 2000}"},
            {"name": "search_local_kb", "description": "Search local vector index (RAG). Input: {\"query\": \"...\", \"top_k\": 3}"},
        ]

    def _call_tool(self, tools, name: str, tool_input: dict):
        allow = {t["name"] for t in tools}
        if name not in allow:
            return f"ERROR: tool not allowed: {name}"
        if name == "list_workflow_resources":
            mid = (tool_input.get("mode_id") or self.mode_id or "").strip()
            if not mid:
                return "[]"
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = []
            paths = []
            for t in data if isinstance(data, list) else []:
                if isinstance(t, dict) and t.get("mode_id") == mid:
                    raw = t.get("repo_paths", t.get("paths", []))
                    paths = raw if isinstance(raw, list) else []
                    break
            return json.dumps(paths, ensure_ascii=False, indent=2)

        if name == "read_text_file":
            path = (tool_input.get("path") or "").strip()
            if not path:
                return "ERROR: path is empty"
            max_chars = int(tool_input.get("max_chars") or 2000)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read(max_chars + 1)
            except Exception:
                try:
                    with open(path, "r", encoding="gb18030", errors="ignore") as f:
                        txt = f.read(max_chars + 1)
                except Exception:
                    return "ERROR: cannot read file"
            if len(txt) > max_chars:
                txt = txt[:max_chars] + "…"
            return txt

        if name == "search_local_kb":
            q = (tool_input.get("query") or "").strip()
            if not q:
                return "[]"
            top_k = int(tool_input.get("top_k") or 3)
            from rag_engine import RAGEngine
            rag = RAGEngine()
            rag.set_mode(self.mode_id)
            hits = rag.retrieve(q, top_k=top_k)
            slim = [{"source": h.get("source"), "score": h.get("score"), "text": (h.get("text") or "")[:400]} for h in hits]
            return json.dumps(slim, ensure_ascii=False, indent=2)

        return "ERROR: tool not implemented"

    def _compact_observation(self, text: str, budget_chars: int):
        t = (text or "").strip()
        if len(t) <= budget_chars:
            return t
        head = t[: int(budget_chars * 0.6)]
        tail = t[-int(budget_chars * 0.3):]
        return head + "\n...\n" + tail


class TaskWidget(QFrame):
    def __init__(self, name, paths, mode_id, marked=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.paths = paths
        self.mode_id = mode_id
        self.marked = marked
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(85)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#TaskCard {{
                background-color: {CARD_BG};
                border: 2px solid {BORDER_LIGHT};
                border-radius: 18px;
            }}
        """)
        self.setObjectName("TaskCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        v_info = QVBoxLayout()
        v_info.setSpacing(2)
        v_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(self.name)
        self.title_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {TEXT_MAIN}; background:transparent;")

        self.sub_label = QLabel(f"● {len(self.paths)} Automation Items")
        self.sub_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SUB}; background:transparent;")

        v_info.addWidget(self.title_label)
        v_info.addWidget(self.sub_label)
        layout.addLayout(v_info)
        layout.addStretch()

        self.go_btn = QPushButton("Go")
        self.go_btn.setFixedSize(60, 32)
        self.go_btn.clicked.connect(self.launch)
        self.go_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 122, 255, 0.15);
                color: {ACCENT_BLUE}; border-radius: 16px;
                font-weight: bold; border: none; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_BLUE}; color: white; }}
        """)
        layout.addWidget(self.go_btn)

        # 星标按钮（标记事件）
        self.mark_btn = QPushButton("★" if self.marked else "☆")
        self.mark_btn.setFixedSize(36, 32)
        self.mark_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ACCENT_BLUE};
                font-size: 18px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                color: #FFD700;
            }}
        """)
        self.mark_btn.clicked.connect(self.toggle_mark)
        layout.addWidget(self.mark_btn)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow)

    def toggle_mark(self):
        self.marked = not self.marked
        self.mark_btn.setText("★" if self.marked else "☆")
        self.window().update_task_mark(self)

    def enterEvent(self, event):
        self.setStyleSheet(
            f"QFrame#TaskCard {{ background-color: #333337; border: 2px solid {ACCENT_BLUE}; border-radius: 18px; }}")
        self.shadow.setBlurRadius(30)
        self.shadow.setYOffset(8)

    def leaveEvent(self, event):
        self.setStyleSheet(
            f"QFrame#TaskCard {{ background-color: {CARD_BG}; border: 2px solid {BORDER_LIGHT}; border-radius: 18px; }}")
        self.shadow.setBlurRadius(20)
        self.shadow.setYOffset(4)

    def launch(self):
        for p in self.paths:
            try:
                if p.startswith(("http", "obsidian://")):
                    QDesktopServices.openUrl(QUrl(p))
                else:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.normpath(p)))
            except Exception as e:
                print(f"Failed to open {p}: {e}")

    def mouseDoubleClickEvent(self, event):
        self.window().edit_task(self)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #2D2D30;
                color: #E6E6E6;
                border: 2px solid #3A3A3C;
                padding: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 8px 14px;
                border-radius: 10px;
                margin: 2px 4px;
            }}
            QMenu::item:selected {{
                background-color: rgba(0, 122, 255, 0.22);
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(255, 255, 255, 0.08);
                margin: 6px 10px;
            }}
        """)
        agent_act = QAction("Open Agent", self)
        edit_act = QAction("Modify Configuration", self)
        del_act = QAction("Delete Workflow", self)

        agent_act.triggered.connect(lambda: self.window().open_agent(self))
        edit_act.triggered.connect(lambda: self.window().edit_task(self))
        del_act.triggered.connect(lambda: self.window().remove_task(self))

        menu.addAction(agent_act)
        menu.addAction(edit_act)
        menu.addAction(del_act)
        menu.exec(event.globalPos())


class FocusFlow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ShadowLink")
        self.resize(520, 750)
        self.setAcceptDrops(False)
        self.llm_cfg = load_llm_config()
        self._local_model_process = None
        self._agent_windows: list[AgentDialog] = []
        self.tasks_data = self.load_config()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #1E1E1E; }}
            QScrollArea {{ border: none; background-color: #1E1E1E; }}
            #ListContainer {{ background-color: #1E1E1E; }}
            #TaskCard {{ border-radius: 12px; }}
            QScrollBar:vertical {{
                border: none; background: transparent; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: #3A3A3C; border-radius: 3px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(85)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(25, 0, 25, 0)

        title_v = QVBoxLayout()
        title_v.setSpacing(2)
        title_v.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        m_title = QLabel("ShadowLink")
        m_title.setStyleSheet("font-size: 26px; font-weight: bold; color: white; letter-spacing: -1px;")
        s_title = QLabel("Ready to work?")
        s_title.setStyleSheet("color: #808080; font-size: 13px;")
        title_v.addWidget(m_title)
        title_v.addWidget(s_title)

        add_btn = QPushButton("+ New")
        add_btn.setFixedSize(85, 36)
        add_btn.clicked.connect(self.add_task)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3E3E42; color: #DCDCDC; border-radius: 18px; 
                font-weight: bold; border: none; font-size: 13px;
            }
            QPushButton:hover { background-color: #505050; color: white; }
        """)

        gear_btn = QPushButton("⚙")
        gear_btn.setFixedSize(36, 36)
        gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gear_btn.clicked.connect(self.open_model_settings)
        gear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3E3E42;
                color: #DCDCDC;
                border-radius: 18px;
                font-size: 16px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #505050; color: white; }}
        """)

        h_layout.addLayout(title_v)
        h_layout.addStretch()
        h_layout.addWidget(gear_btn)
        h_layout.addWidget(add_btn)
        self.main_layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().setStyleSheet(f"background-color: #1E1E1E;")

        self.container = QWidget()
        self.container.setObjectName("ListContainer")
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(25, 25, 25, 25)
        self.list_layout.setSpacing(18)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

        self.refresh()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        modified = False
                        for task in data:
                            if 'marked' not in task:
                                task['marked'] = False
                                modified = True
                            if 'paths' not in task or not isinstance(task.get('paths'), list):
                                task['paths'] = []
                                modified = True
                            if 'mode_id' not in task or not task.get('mode_id'):
                                task['mode_id'] = _new_mode_id()
                                modified = True
                        if modified:
                            try:
                                with open(CONFIG_FILE, 'w', encoding='utf-8') as wf:
                                    json.dump(data, wf, ensure_ascii=False, indent=4)
                            except Exception:
                                pass
                        return data
                    return []
            except:
                return []
        return []

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.tasks_data, f, ensure_ascii=False, indent=4)

    def refresh(self):
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for task in self.tasks_data:
            w = TaskWidget(task.get('name', ''), task.get('paths', []), task.get('mode_id'), task.get('marked', False), self)
            self.list_layout.addWidget(w)

    def update_task_mark(self, widget):
        idx = self.list_layout.indexOf(widget)
        if idx == -1:
            return
        self.tasks_data[idx]['marked'] = widget.marked
        self.save_config()

    def add_task(self):
        d = ConfigDialog(parent=self)
        if d.exec():
            name, paths = d.get_data()
            if name:
                self.tasks_data.append({"name": name, "paths": paths, "marked": False, "mode_id": _new_mode_id()})
                self.save_config()
                self.refresh()

    def edit_task(self, widget):
        idx = self.list_layout.indexOf(widget)
        if idx == -1:
            return
        d = ConfigDialog(widget.name, widget.paths, self)
        if d.exec():
            name, paths = d.get_data()
            if not name and not paths:
                self.tasks_data.pop(idx)
            else:
                old_marked = self.tasks_data[idx].get('marked', False)
                old_mode_id = self.tasks_data[idx].get('mode_id') or _new_mode_id()
                self.tasks_data[idx] = {"name": name, "paths": paths, "marked": old_marked, "mode_id": old_mode_id}
            self.save_config()
            self.refresh()

    def remove_task(self, widget):
        idx = self.list_layout.indexOf(widget)
        if idx == -1:
            return
        self.tasks_data.pop(idx)
        self.save_config()
        self.refresh()

    def open_agent(self, widget):
        idx = self.list_layout.indexOf(widget)
        if idx == -1:
            return
        task = self.tasks_data[idx]
        task_name = task.get('name', '')
        # Fallback to paths if repo_paths doesn't exist yet
        resources = task.get('repo_paths', task.get('paths', []))
        mode_id = task.get('mode_id', '')
        self.llm_cfg = load_llm_config()
        d = AgentDialog(task_name, resources, mode_id, self.llm_cfg, self, None)
        d.setWindowModality(Qt.WindowModality.NonModal)
        d.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._agent_windows.append(d)
        d.destroyed.connect(lambda *_: self._agent_windows.remove(d) if d in self._agent_windows else None)
        d.show()
        d.raise_()
        d.activateWindow()

    def open_model_settings(self):
        cfg = load_llm_config()
        old_full = bool((cfg.get("agent_permissions") or {}).get("full_access", False))
        d = ModelSettingsDialog(cfg, self)
        if d.exec():
            new_cfg = d.get_updated_config()
            if save_llm_config(new_cfg):
                self.llm_cfg = new_cfg
                new_full = bool((new_cfg.get("agent_permissions") or {}).get("full_access", False))
                if new_full and not old_full:
                    try:
                        import ctypes
                        if not ctypes.windll.shell32.IsUserAnAdmin():
                            exe = sys.executable
                            params = " ".join([f"\\\"{a}\\\"" for a in sys.argv])
                            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
                            QApplication.quit()
                    except Exception:
                        pass
            else:
                QMessageBox.warning(self, "Error", "Failed to save llm_config.json")

    def ensure_local_model_running(self, folder_path: str, agent: dict):
        folder = (folder_path or "").strip()
        if not folder:
            return
        if not os.path.isdir(folder):
            return
        if self._local_model_process is not None and self._local_model_process.poll() is None:
            return
        cmd = _detect_local_launch(folder)
        if not cmd:
            return
        try:
            self._local_model_process = subprocess.Popen(
                cmd,
                cwd=folder,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
            )
            time.sleep(0.4)
        except Exception:
            self._local_model_process = None


def run_app():
    app = QApplication(sys.argv)
    app.setApplicationName("ShadowLink")
    families = set(QFontDatabase.families())
    preferred = [
        "Segoe UI Variable",
        "Segoe UI",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans CJK SC",
        "PingFang SC",
    ]
    font = QFont()
    font.setFamilies([
        "Inter",
        "Source Han Sans",
        "Source Han Sans SC",
        "Source Han Sans CN",
        "Noto Sans SC",
        "Noto Sans CJK SC",
        "Segoe UI Variable",
        "Microsoft YaHei UI",
        "PingFang SC"
    ])
    font.setPointSize(11)
    font.setWeight(QFont.Weight.Medium)
    app.setFont(font)
    app.setStyleSheet(GLOBAL_QSS)

    window = FocusFlow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit("main.py 是业务入口模块，请通过 launcher.py 启动应用。")
