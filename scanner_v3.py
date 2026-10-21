"""
scanner_v3.py
Professional 3D Object Scanner & AI Neural Reconstruction Studio.
High-precision industrial desktop application built with PyQt6 and Three.js WebEngine.
Supports automated Arduino turntables, manual camera loops, local open-source
TripoSR neural reconstruction, and universal CAD/Blender format exports.
"""

import os
import sys
import json
import time
import threading
import glob as _glob
import requests
import cv2

if getattr(sys, 'frozen', False):
    APP_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SCAN_FOLDER = os.path.join(APP_DIR, "scan")
DEFAULT_EXPORT_DIR = os.path.join(APP_DIR, "exports")
DEFAULT_MODEL_PATH = os.path.join(DEFAULT_EXPORT_DIR, "scanned_model.glb")
os.makedirs(SCAN_FOLDER, exist_ok=True)
os.makedirs(DEFAULT_EXPORT_DIR, exist_ok=True)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--enable-webgl "
    "--ignore-gpu-blocklist "
    "--disable-gpu-sandbox "
    "--enable-gpu-rasterization "
    "--disable-web-security "
    "--allow-running-insecure-content"
)

try:
    import serial
except ImportError:
    serial = None

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextBrowser, QFrame,
    QFileDialog, QMessageBox, QGroupBox, QStackedWidget, QDialog,
    QDialogButtonBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QCheckBox, QProgressBar, QComboBox,
    QTabWidget, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile

# ── Paths & Config ────────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
DEFAULT_CONFIG = {
    "tripo_api_key": "",
    "arduino_port": "COM4",
    "arduino_baud": 9600,
    "output_path": DEFAULT_MODEL_PATH,
    "export_dir": DEFAULT_EXPORT_DIR,
    "num_images": 8,
    "rotation_step": 10,
    "camera_index": 1,
    "mesh_resolution": 256,
    "device": "auto",
    "foreground_ratio": 0.85,
    "remove_background": True,
    "students": []
}


def load_settings():
    if os.path.exists(CONFIG_PATH):
        try:
            d = json.load(open(CONFIG_PATH, "r", encoding="utf-8"))
            for k, v in DEFAULT_CONFIG.items():
                d.setdefault(k, v)
            return d
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_settings(s):
    json.dump(s, open(CONFIG_PATH, "w", encoding="utf-8"), indent=4)


SETTINGS = load_settings()

# ── Universal 3D Converter & Pipeline ─────────────────────────────────────────
from converter import convert_model_to_all_formats, open_in_blender, find_blender
try:
    from pipeline import generate_3d_from_image
except ImportError:
    generate_3d_from_image = None


# ── Global Professional Engineering Stylesheet ───────────────────────────────
GLOBAL_STYLESHEET = """
QMainWindow {
    background-color: #0b0d13;
    color: #e2e8f0;
}

QWidget {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Roboto, sans-serif;
    color: #cbd5e1;
    font-size: 12px;
}

/* ── Panels & Cards ── */
QFrame#dockPanel {
    background-color: #121620;
    border-right: 1px solid #1f2737;
}

QFrame#viewportFrame {
    background-color: #07090e;
}

QGroupBox {
    background-color: #161b26;
    border: 1px solid #232c3d;
    border-radius: 6px;
    margin-top: 18px;
    padding: 14px 12px 10px 12px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    color: #94a3b8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: #161b26;
    color: #38bdf8;
    text-transform: uppercase;
}

/* ── Typography & Labels ── */
QLabel {
    color: #cbd5e1;
}

QLabel#headingLabel {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#metaLabel {
    color: #64748b;
    font-size: 11px;
}

QLabel#statusPill {
    font-family: 'Consolas', monospace;
    font-size: 10px;
    font-weight: 600;
    color: #10b981;
    background-color: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.25);
    padding: 3px 8px;
    border-radius: 4px;
}

/* ── Buttons ── */
QPushButton {
    background-color: #1e2638;
    color: #f1f5f9;
    border: 1px solid #2e3b52;
    border-radius: 5px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 11px;
}

QPushButton:hover {
    background-color: #263147;
    border-color: #3d4e6d;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #182030;
}

QPushButton:disabled {
    background-color: #131722;
    color: #475569;
    border-color: #1a2230;
}

/* Primary Action Accent Button */
QPushButton#primaryActionBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    font-weight: 700;
}

QPushButton#primaryActionBtn:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

QPushButton#primaryActionBtn:pressed {
    background-color: #1e40af;
}

/* Accent Studio Button */
QPushButton#studioActionBtn {
    background-color: #d97706;
    color: #ffffff;
    border: 1px solid #f59e0b;
    font-weight: 700;
}

QPushButton#studioActionBtn:hover {
    background-color: #b45309;
    border-color: #fbbf24;
}

/* Segmented Tab Button */
QPushButton#segmentBtn {
    background-color: #141924;
    border: 1px solid #232d3f;
    border-radius: 4px;
    padding: 5px 10px;
    color: #94a3b8;
}

QPushButton#segmentBtn:hover {
    color: #e2e8f0;
    background-color: #1c2333;
}

QPushButton#segmentBtn[active="true"] {
    background-color: rgba(37, 99, 235, 0.2);
    border-color: #3b82f6;
    color: #60a5fa;
}

/* ── Form Inputs ── */
QLineEdit, QSpinBox, QComboBox {
    background-color: #0e121a;
    color: #f8fafc;
    border: 1px solid #242d3e;
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: #2563eb;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #121622;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    selection-background-color: #2563eb;
}

/* ── Terminal Console ── */
QTextBrowser {
    background-color: #0a0d14;
    color: #94a3b8;
    border: 1px solid #1c2433;
    border-radius: 5px;
    font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px;
    padding: 6px;
    line-height: 1.4;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: #0e121a;
    border: 1px solid #242d3e;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #0d1017;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #252d3d;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3b465c;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ── Dialogs & Tables ── */
QDialog {
    background-color: #0f131c;
    color: #f1f5f9;
}

QTableWidget {
    background-color: #0e121a;
    color: #e2e8f0;
    gridline-color: #1e2637;
    border: 1px solid #232d3f;
    border-radius: 4px;
    selection-background-color: #1e3a8a;
}

QHeaderView::section {
    background-color: #141924;
    color: #94a3b8;
    border: 1px solid #1e2637;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 11px;
}

QTabWidget::pane {
    border: 1px solid #232d3f;
    background-color: #131722;
    border-radius: 5px;
    top: -1px;
}

QTabBar::tab {
    background-color: #0d1017;
    color: #8b949e;
    border: 1px solid #232d3f;
    border-bottom: none;
    padding: 6px 14px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #131722;
    color: #60a5fa;
    border-bottom: 1px solid #131722;
    font-weight: 600;
}
"""


# ── Settings Dialog ───────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Studio Configuration & Hardware Settings")
        self.resize(600, 480)
        self.setStyleSheet(GLOBAL_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        tabs = QTabWidget()

        # ── Tab 1: Hardware & Serial ──
        tab_hw = QWidget()
        form_hw = QFormLayout(tab_hw)
        form_hw.setContentsMargins(14, 16, 14, 14)
        form_hw.setSpacing(12)

        self.ent_port = QLineEdit(settings.get("arduino_port", "COM4"))
        form_hw.addRow("Arduino Serial Port:", self.ent_port)

        self.spn_baud = QSpinBox()
        self.spn_baud.setRange(1200, 115200)
        self.spn_baud.setSingleStep(9600)
        self.spn_baud.setValue(settings.get("arduino_baud", 9600))
        form_hw.addRow("Serial Baud Rate:", self.spn_baud)

        self.spn_rot_step = QSpinBox()
        self.spn_rot_step.setRange(5, 90)
        self.spn_rot_step.setSingleStep(5)
        self.spn_rot_step.setValue(settings.get("rotation_step", 10))
        self.spn_rot_step.setSuffix(" °")
        form_hw.addRow("Rotation Step Angle:", self.spn_rot_step)

        self.spn_images = QSpinBox()
        self.spn_images.setRange(1, 72)
        self.spn_images.setValue(settings.get("num_images", 8))
        form_hw.addRow("Manual Capture Shots:", self.spn_images)

        self.spn_cam_idx = QSpinBox()
        self.spn_cam_idx.setRange(0, 4)
        self.spn_cam_idx.setValue(settings.get("camera_index", 1))
        form_hw.addRow("Default Camera Index:", self.spn_cam_idx)

        tabs.addTab(tab_hw, "Hardware & Turntable")

        # ── Tab 2: Neural Reconstruction Engine ──
        tab_ai = QWidget()
        form_ai = QFormLayout(tab_ai)
        form_ai.setContentsMargins(14, 16, 14, 14)
        form_ai.setSpacing(12)

        self.cmb_res = QComboBox()
        self.cmb_res.addItems(["128 — Fast Preview", "256 — Balanced Quality", "512 — High Fidelity"])
        res_val = settings.get("mesh_resolution", 256)
        idx = {128: 0, 256: 1, 512: 2}.get(res_val, 1)
        self.cmb_res.setCurrentIndex(idx)
        form_ai.addRow("Mesh Resolution:", self.cmb_res)

        self.cmb_device = QComboBox()
        self.cmb_device.addItems(["auto (GPU if available)", "cuda:0 (NVIDIA GPU)", "cpu (Standard CPU)"])
        dev_val = settings.get("device", "auto")
        dev_idx = {"auto": 0, "cuda:0": 1, "cpu": 2}.get(dev_val, 0)
        self.cmb_device.setCurrentIndex(dev_idx)
        form_ai.addRow("Compute Device:", self.cmb_device)

        self.chk_rembg = QCheckBox("Automatically remove background before 3D reconstruction")
        self.chk_rembg.setChecked(settings.get("remove_background", True))
        form_ai.addRow("Background Isolation:", self.chk_rembg)

        # Export directory row
        exp_row = QHBoxLayout()
        self.ent_export = QLineEdit(settings.get("export_dir", DEFAULT_EXPORT_DIR))
        btn_browse_exp = QPushButton("Browse...")
        btn_browse_exp.clicked.connect(self._browse_export_dir)
        exp_row.addWidget(self.ent_export, stretch=4)
        exp_row.addWidget(btn_browse_exp, stretch=1)
        form_ai.addRow("Exports Destination:", exp_row)

        self.ent_token = QLineEdit(settings.get("tripo_api_key", ""))
        self.ent_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.ent_token.setPlaceholderText("Optional cloud API token (leave blank for local TripoSR)")
        form_ai.addRow("Optional Cloud Key:", self.ent_token)

        tabs.addTab(tab_ai, "Neural Engine & Quality")

        # ── Tab 3: FYP Attribution ──
        tab_team = QWidget()
        lay_team = QVBoxLayout(tab_team)
        lay_team.setContentsMargins(14, 16, 14, 14)
        lay_team.setSpacing(10)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Student / Member Name", "Roll / Registration Number"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for stu in settings.get("students", []):
            self._add_row(stu.get("name", ""), stu.get("roll", ""))

        lay_team.addWidget(self.table)

        row_btns = QHBoxLayout()
        btn_add = QPushButton("Add Member")
        btn_add.clicked.connect(lambda: self._add_row())
        btn_rem = QPushButton("Remove Selected")
        btn_rem.clicked.connect(self._remove_row)
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_rem)
        lay_team.addLayout(row_btns)

        tabs.addTab(tab_team, "Project Attribution")
        layout.addWidget(tabs)

        # ── Save / Cancel ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryActionBtn")
        layout.addWidget(btns)

    def _browse_export_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Export Directory", self.ent_export.text())
        if d:
            self.ent_export.setText(d)

    def _add_row(self, name="", roll=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        self.table.setItem(r, 1, QTableWidgetItem(roll))

    def _remove_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _save(self):
        self.settings["arduino_port"] = self.ent_port.text().strip()
        self.settings["arduino_baud"] = self.spn_baud.value()
        self.settings["rotation_step"] = self.spn_rot_step.value()
        self.settings["num_images"] = self.spn_images.value()
        self.settings["camera_index"] = self.spn_cam_idx.value()

        res_map = {0: 128, 1: 256, 2: 512}
        self.settings["mesh_resolution"] = res_map.get(self.cmb_res.currentIndex(), 256)

        dev_map = {0: "auto", 1: "cuda:0", 2: "cpu"}
        self.settings["device"] = dev_map.get(self.cmb_device.currentIndex(), "auto")
        self.settings["remove_background"] = self.chk_rembg.isChecked()
        self.settings["export_dir"] = self.ent_export.text().strip()
        self.settings["tripo_api_key"] = self.ent_token.text().strip()

        students = []
        for r in range(self.table.rowCount()):
            n = (self.table.item(r, 0) or QTableWidgetItem("")).text().strip()
            k = (self.table.item(r, 1) or QTableWidgetItem("")).text().strip()
            if n or k:
                students.append({"name": n, "roll": k})
        self.settings["students"] = students

        save_settings(self.settings)
        self.accept()


# ── Camera Thread ─────────────────────────────────────────────────────────────
class CameraThread(QThread):
    new_frame = pyqtSignal(QPixmap)
    frame_ready_for_capture = pyqtSignal(object)

    def __init__(self, cam_index=1, parent=None):
        super().__init__(parent)
        self.cam_index = cam_index
        self.running = True

    def run(self):
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1 - self.cam_index, cv2.CAP_DSHOW)
        while self.running:
            ret, frame = cap.read()
            if ret and frame is not None:
                self.frame_ready_for_capture.emit(frame)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                self.new_frame.emit(
                    QPixmap.fromImage(QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888))
                )
            self.msleep(30)
        cap.release()

    def stop(self):
        self.running = False
        self.wait()


# ── Local / Cloud Neural Reconstruction Thread ────────────────────────────────
class ReconstructionThread(QThread):
    """
    Executes neural 3D reconstruction from a single image or batch of images.
    Uses local open-source TripoSR by default (no API keys required).
    Falls back to cloud if explicitly configured.
    """
    log_msg = pyqtSignal(str)
    progress_pct = pyqtSignal(int)
    scan_complete = pyqtSignal(str)
    scan_error = pyqtSignal(str)

    def __init__(self, image_paths, settings, base_name=None, parent=None):
        super().__init__(parent)
        if isinstance(image_paths, str):
            self.image_paths = [image_paths]
        else:
            self.image_paths = image_paths
        self.settings = settings
        self.base_name = base_name

    def run(self):
        try:
            if not self.image_paths:
                raise ValueError("No input images provided for reconstruction.")

            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)

            primary_image = self.image_paths[0]
            if not os.path.exists(primary_image):
                raise FileNotFoundError(f"Image not found: {primary_image}")

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            if not self.base_name:
                self.base_name = os.path.splitext(os.path.basename(primary_image))[0]
            clean_name = f"{self.base_name}_{timestamp}"

            self.log_msg.emit(f"[*] Starting neural 3D reconstruction for '{self.base_name}'...")
            self.progress_pct.emit(10)

            # Check if local pipeline is available
            source_mesh = None
            if generate_3d_from_image is not None:
                self.log_msg.emit("[*] Initializing local TripoSR neural reconstruction model...")
                self.progress_pct.emit(25)

                resolution = self.settings.get("mesh_resolution", 256)
                device = self.settings.get("device", "auto")
                remove_bg = self.settings.get("remove_background", True)
                fg_ratio = self.settings.get("foreground_ratio", 0.85)

                source_mesh = generate_3d_from_image(
                    image_path=primary_image,
                    export_dir=export_dir,
                    base_name=clean_name,
                    resolution=resolution,
                    device=device,
                    remove_bg=remove_bg,
                    foreground_ratio=fg_ratio,
                    log_fn=lambda m: self.log_msg.emit(m)
                )
                self.progress_pct.emit(75)

            if not source_mesh or not os.path.exists(source_mesh):
                raise RuntimeError("Neural reconstruction did not produce an output mesh.")

            self.log_msg.emit("[*] Generating universal export formats (GLB, OBJ, STL, FBX, BLEND)...")
            self.progress_pct.emit(85)

            results = convert_model_to_all_formats(
                input_model_path=source_mesh,
                export_dir=export_dir,
                base_name=clean_name,
                log_fn=lambda m: self.log_msg.emit(m)
            )

            final_glb = results.get("glb") or source_mesh
            self.progress_pct.emit(100)
            self.log_msg.emit(f"[✓] Reconstruction successful. Target asset: {os.path.basename(final_glb)}")
            self.scan_complete.emit(final_glb)

        except Exception as e:
            self.scan_error.emit(str(e))


# ── Hardware Turntable Scan Thread ────────────────────────────────────────────
class HardwareScanThread(QThread):
    log_msg = pyqtSignal(str)
    progress_pct = pyqtSignal(int)
    scan_complete = pyqtSignal(str)
    scan_error = pyqtSignal(str)

    def __init__(self, settings, mode, frame_supplier=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.scan_mode = mode
        self.frame_supplier = frame_supplier

    def _get_latest_frame(self):
        if callable(self.frame_supplier):
            return self.frame_supplier()
        return None

    def run(self):
        try:
            rotation_step = self.settings.get("rotation_step", 10)
            if rotation_step <= 0:
                rotation_step = 10
            num_images = int(round(360.0 / rotation_step))
            if num_images < 1:
                num_images = 1

            if self.scan_mode == "Auto Turntable":
                arduino = None
                port = self.settings.get("arduino_port", "COM4")
                baud = self.settings.get("arduino_baud", 9600)

                try:
                    if serial:
                        arduino = serial.Serial(port, baud, timeout=1)
                        time.sleep(2)
                        self.log_msg.emit(f"[+] Arduino connected on {port} ({baud} baud). Starting automated loop for {num_images} steps.")
                except Exception as e:
                    self.log_msg.emit(f"[!] Serial hardware notice: {e}")

                # Clean scan folder
                for old in _glob.glob(os.path.join(SCAN_FOLDER, "img_*.jpg")):
                    try: os.remove(old)
                    except Exception: pass

                for idx in range(num_images):
                    if not self.isRunning():
                        break

                    self.log_msg.emit(f"[*] Step {idx + 1}/{num_images}: Rotating turntable {rotation_step}°...")
                    pct = int(((idx) / float(num_images)) * 60)
                    self.progress_pct.emit(pct)

                    if arduino and arduino.is_open:
                        arduino.reset_input_buffer()
                        arduino.reset_output_buffer()
                        arduino.write(b'R\n')
                        arduino.flush()
                        time.sleep(1.8)
                    else:
                        time.sleep(1.2)

                    frame = self._get_latest_frame()
                    if frame is None:
                        wait_start = time.time()
                        while self.isRunning() and frame is None and time.time() - wait_start < 4.0:
                            time.sleep(0.1)
                            frame = self._get_latest_frame()

                    if frame is not None:
                        name = f"img_{idx}.jpg"
                        cv2.imwrite(os.path.join(SCAN_FOLDER, name), frame)
                        self.log_msg.emit(f"   [+] Saved frame: {name}")

                if arduino and arduino.is_open:
                    arduino.close()

            # Process captured frames
            found_images = sorted(
                _glob.glob(os.path.join(SCAN_FOLDER, "img_*.jpg")),
                key=lambda p: int(os.path.splitext(os.path.basename(p))[0].replace("img_", ""))
            )
            if not found_images:
                raise FileNotFoundError("No image frames found in scan folder to reconstruct.")

            self.log_msg.emit(f"[*] Total captured frames: {len(found_images)}. Launching neural reconstructor...")
            self.progress_pct.emit(65)

            primary = found_images[0]
            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_name = f"turntable_scan_{timestamp}"

            source_mesh = generate_3d_from_image(
                image_path=primary,
                export_dir=export_dir,
                base_name=base_name,
                resolution=self.settings.get("mesh_resolution", 256),
                device=self.settings.get("device", "auto"),
                remove_bg=self.settings.get("remove_background", True),
                log_fn=lambda m: self.log_msg.emit(m)
            )

            self.progress_pct.emit(85)
            self.log_msg.emit("[*] Auto-converting to GLB, OBJ, STL, FBX, and native BLEND...")

            results = convert_model_to_all_formats(
                input_model_path=source_mesh,
                export_dir=export_dir,
                base_name=base_name,
                log_fn=lambda m: self.log_msg.emit(m)
            )

            final_glb = results.get("glb") or source_mesh
            self.progress_pct.emit(100)
            self.scan_complete.emit(final_glb)

        except Exception as e:
            self.scan_error.emit(str(e))


# ── Blender Export Thread ─────────────────────────────────────────────────────
class BlenderExportThread(QThread):
    log_msg = pyqtSignal(str)
    export_done = pyqtSignal(str)
    export_error = pyqtSignal(str)

    def __init__(self, glb_path, export_format, settings, parent=None):
        super().__init__(parent)
        self.glb_path = glb_path
        self.export_format = export_format
        self.settings = settings

    def run(self):
        try:
            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(self.glb_path))[0]
            fmt_upper = self.export_format.upper()

            self.log_msg.emit(f"[*] Exporting asset to {fmt_upper}...")

            results = convert_model_to_all_formats(
                self.glb_path,
                export_dir=export_dir,
                base_name=f"{base_name}_{timestamp}",
                log_fn=lambda m: self.log_msg.emit(m)
            )

            target_key = fmt_upper.lower()
            if target_key in results:
                self.export_done.emit(results[target_key])
            else:
                self.export_done.emit(results.get("blend", results.get("glb", self.glb_path)))

        except Exception as e:
            self.export_error.emit(str(e))


# ── Main Application Window ───────────────────────────────────────────────────
class ModernScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Scanner Studio — Professional Hardware Capture & Reconstruction")
        self.resize(1340, 840)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(GLOBAL_STYLESHEET)

        # State Variables
        self.manual_capture_count = 0
        self.latest_frame = None
        self.scan_thread = None
        self._httpd = None
        self.camera_index = SETTINGS.get("camera_index", 1)
        self.camera_enabled = True
        self.camera_frame_lock = threading.Lock()
        self._cam_auto_paused = False
        self._current_model_path = None
        self._labels_visible = True

        # Root Central Layout
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Top Header Bar
        root.addWidget(self._build_top_header())

        # 2. Main Workstation Body (Splitter for resizable control dock)
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setHandleWidth(1)
        body_splitter.addWidget(self._build_left_dock())
        body_splitter.addWidget(self._build_right_viewport())
        body_splitter.setSizes([380, 960])
        root.addWidget(body_splitter, stretch=1)

        # Start Camera Thread
        self._start_camera_thread()

    # ── Top Studio Header ─────────────────────────────────────────────────────
    def _build_top_header(self):
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #10141d; border-bottom: 1px solid #1e2637; padding: 0 16px;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 0, 12, 0)
        h_lay.setSpacing(14)

        # Branding
        title = QLabel("3D SCANNER STUDIO")
        title.setObjectName("headingLabel")
        h_lay.addWidget(title)

        pro_badge = QLabel("PRO")
        pro_badge.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 9px; font-weight: 700;"
            "color: #38bdf8; background: rgba(56, 189, 248, 0.12);"
            "border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 6px; border-radius: 3px;"
        )
        h_lay.addWidget(pro_badge)

        h_lay.addSpacing(16)

        # Hardware & Engine Telemetry Chips
        self.lbl_hw_chip = QLabel(f"TURNTABLE: {SETTINGS.get('arduino_port', 'COM4')}")
        self.lbl_hw_chip.setObjectName("statusPill")
        h_lay.addWidget(self.lbl_hw_chip)

        self.lbl_engine_chip = QLabel("ENGINE: TRIPOSR LOCAL")
        self.lbl_engine_chip.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 10px; font-weight: 600;"
            "color: #94a3b8; background: #161b26; border: 1px solid #232c3d;"
            "padding: 3px 8px; border-radius: 4px;"
        )
        h_lay.addWidget(self.lbl_engine_chip)

        h_lay.addStretch(1)

        # Action Shortcuts
        btn_open_exp = QPushButton("Exports Folder")
        btn_open_exp.setToolTip("Open output directory containing exported 3D assets")
        btn_open_exp.clicked.connect(self.open_export_dir)
        h_lay.addWidget(btn_open_exp)

        btn_settings = QPushButton("Settings")
        btn_settings.setToolTip("Configure hardware serial, camera, and neural engine")
        btn_settings.clicked.connect(self.open_settings)
        h_lay.addWidget(btn_settings)

        return header

    # ── Left Control Dock ─────────────────────────────────────────────────────
    def _build_left_dock(self):
        dock = QFrame()
        dock.setObjectName("dockPanel")
        dock.setMinimumWidth(340)
        dock.setMaximumWidth(460)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        # ── 1. Turntable & Hardware Capture ──
        hw_box = QGroupBox("Hardware Capture & Turntable")
        hw_lay = QVBoxLayout(hw_box)
        hw_lay.setSpacing(8)

        # Mode Segmented Switcher
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        self.btn_mode_auto = QPushButton("Automated Turntable")
        self.btn_mode_auto.setObjectName("segmentBtn")
        self.btn_mode_auto.setProperty("active", True)
        self.btn_mode_auto.clicked.connect(lambda: self._set_capture_mode("Auto"))

        self.btn_mode_manual = QPushButton("Manual Scan")
        self.btn_mode_manual.setObjectName("segmentBtn")
        self.btn_mode_manual.setProperty("active", False)
        self.btn_mode_manual.clicked.connect(lambda: self._set_capture_mode("Manual"))

        mode_row.addWidget(self.btn_mode_auto)
        mode_row.addWidget(self.btn_mode_manual)
        hw_lay.addLayout(mode_row)

        # Angle & Shots Telemetry
        shots_row = QHBoxLayout()
        self.lbl_shots_info = QLabel("Rotary Step: 10° (36 views)")
        self.lbl_shots_info.setObjectName("metaLabel")
        shots_row.addWidget(self.lbl_shots_info)

        self.spn_images = QSpinBox()
        self.spn_images.setRange(1, 72)
        self.spn_images.setValue(SETTINGS.get("num_images", 8))
        self.spn_images.setFixedWidth(64)
        self.spn_images.valueChanged.connect(self._on_shots_changed)
        shots_row.addWidget(self.spn_images)
        hw_lay.addLayout(shots_row)

        # Primary Loop Action Button
        self.btn_action = QPushButton("Execute Turntable Loop")
        self.btn_action.setObjectName("primaryActionBtn")
        self.btn_action.setFixedHeight(32)
        self.btn_action.clicked.connect(self.start_scan)
        hw_lay.addWidget(self.btn_action)

        # Manual Capture Button
        self.btn_capture = QPushButton("Capture View (1/8)")
        self.btn_capture.setFixedHeight(28)
        self.btn_capture.setVisible(False)
        self.btn_capture.clicked.connect(self.capture_manual)
        hw_lay.addWidget(self.btn_capture)

        # Camera Hardware Toolbar
        cam_row = QHBoxLayout()
        cam_row.setSpacing(6)
        self.btn_cam_toggle = QPushButton("Pause Camera")
        self.btn_cam_toggle.clicked.connect(self.toggle_camera)
        cam_row.addWidget(self.btn_cam_toggle, stretch=3)

        self.btn_cam_switch = QPushButton("Ext Camera")
        self.btn_cam_switch.clicked.connect(self.switch_camera)
        cam_row.addWidget(self.btn_cam_switch, stretch=2)
        hw_lay.addLayout(cam_row)

        # Re-process button
        self.btn_reprocess = QPushButton("Re-Process Existing Frames")
        self.btn_reprocess.clicked.connect(self.reprocess_existing_images)
        hw_lay.addWidget(self.btn_reprocess)

        lay.addWidget(hw_box)

        # ── 2. Neural 3D Reconstruction ──
        ai_box = QGroupBox("Neural 3D Reconstruction")
        ai_lay = QVBoxLayout(ai_box)
        ai_lay.setSpacing(8)

        ai_btn_row = QHBoxLayout()
        ai_btn_row.setSpacing(6)

        self.btn_gen_image = QPushButton("Single Image")
        self.btn_gen_image.setToolTip("Reconstruct complete 3D geometry from a single photo")
        self.btn_gen_image.clicked.connect(self.generate_from_image)
        ai_btn_row.addWidget(self.btn_gen_image)

        self.btn_gen_multi = QPushButton("Multi-Angle")
        self.btn_gen_multi.setToolTip("Process multiple perspective captures")
        self.btn_gen_multi.clicked.connect(self.generate_from_multiple_images)
        ai_btn_row.addWidget(self.btn_gen_multi)

        self.btn_gen_folder = QPushButton("Batch Directory")
        self.btn_gen_folder.setToolTip("Select a folder containing photos")
        self.btn_gen_folder.clicked.connect(self.generate_from_folder)
        ai_btn_row.addWidget(self.btn_gen_folder)
        ai_lay.addLayout(ai_btn_row)

        self.lbl_selected_img = QLabel("Select an image or directory to reconstruct")
        self.lbl_selected_img.setObjectName("metaLabel")
        self.lbl_selected_img.setWordWrap(True)
        ai_lay.addWidget(self.lbl_selected_img)

        # Minimalist Linear Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        ai_lay.addWidget(self.progress_bar)

        lay.addWidget(ai_box)

        # ── 3. Asset Pipeline & Blender ──
        exp_box = QGroupBox("Asset Exports & Blender Studio")
        exp_lay = QVBoxLayout(exp_box)
        exp_lay.setSpacing(8)

        # Export Grid
        grid_row = QHBoxLayout()
        grid_row.setSpacing(4)
        for fmt in ("GLB", "OBJ", "STL", "FBX", "BLEND"):
            btn = QPushButton(fmt)
            btn.clicked.connect(lambda checked, f=fmt: self.export_for_blender(f))
            grid_row.addWidget(btn)
        exp_lay.addLayout(grid_row)

        # Open in Blender Action
        self.btn_open_blender = QPushButton("Launch in Blender Studio")
        self.btn_open_blender.setObjectName("studioActionBtn")
        self.btn_open_blender.setFixedHeight(30)
        self.btn_open_blender.clicked.connect(self.open_current_in_blender)
        exp_lay.addWidget(self.btn_open_blender)

        load_row = QHBoxLayout()
        self.btn_load = QPushButton("Import External GLB")
        self.btn_load.clicked.connect(self.load_mesh)
        load_row.addWidget(self.btn_load)

        self.lbl_export_status = QLabel("Ready for generation")
        self.lbl_export_status.setObjectName("metaLabel")
        load_row.addWidget(self.lbl_export_status)
        exp_lay.addLayout(load_row)

        lay.addWidget(exp_box)

        # ── 4. Diagnostics & Console ──
        diag_box = QGroupBox("Activity Console & Diagnostics")
        diag_lay = QVBoxLayout(diag_box)
        diag_lay.setSpacing(6)

        self.txt = QTextBrowser()
        self.txt.setMinimumHeight(130)
        self.txt.setOpenExternalLinks(True)
        diag_lay.addWidget(self.txt)

        self.lbl_fyp = QLabel("")
        self.lbl_fyp.setObjectName("metaLabel")
        self.lbl_fyp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diag_lay.addWidget(self.lbl_fyp)
        self._refresh_fyp_label()

        lay.addWidget(diag_box)
        lay.addStretch(1)

        scroll.setWidget(content)
        dock_lay = QVBoxLayout(dock)
        dock_lay.setContentsMargins(0, 0, 0, 0)
        dock_lay.addWidget(scroll)
        return dock

    # ── Right Main Viewport ───────────────────────────────────────────────────
    def _build_right_viewport(self):
        vp = QFrame()
        vp.setObjectName("viewportFrame")
        lay = QVBoxLayout(vp)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Viewport Header Toolbar
        vp_header = QFrame()
        vp_header.setFixedHeight(42)
        vp_header.setStyleSheet("background-color: #0d1118; border-bottom: 1px solid #1c2433; padding: 0 16px;")
        vh_lay = QHBoxLayout(vp_header)
        vh_lay.setContentsMargins(12, 0, 12, 0)
        vh_lay.setSpacing(10)

        # Viewport Mode Segment
        self.btn_vp_cam = QPushButton("Camera Feed")
        self.btn_vp_cam.setObjectName("segmentBtn")
        self.btn_vp_cam.setProperty("active", True)
        self.btn_vp_cam.clicked.connect(self.back_to_camera)

        self.btn_vp_3d = QPushButton("3D WebGL Viewport")
        self.btn_vp_3d.setObjectName("segmentBtn")
        self.btn_vp_3d.setProperty("active", False)
        self.btn_vp_3d.clicked.connect(self.view_loaded_model)

        vh_lay.addWidget(self.btn_vp_cam)
        vh_lay.addWidget(self.btn_vp_3d)
        vh_lay.addSpacing(16)

        # Dynamic Dimensions / Status Label
        self.lbl_vp_telemetry = QLabel("SENSOR READY — AWAITING CAPTURE")
        self.lbl_vp_telemetry.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 11px; font-weight: 600; color: #38bdf8;"
        )
        vh_lay.addWidget(self.lbl_vp_telemetry)

        vh_lay.addStretch(1)

        # 3D Viewport Controls
        self.btn_toggle_labels = QPushButton("Labels: ON")
        self.btn_toggle_labels.setToolTip("Toggle 3D measurement bounding callouts")
        self.btn_toggle_labels.clicked.connect(self.toggle_labels)
        vh_lay.addWidget(self.btn_toggle_labels)

        lay.addWidget(vp_header)

        # Viewport Stack
        self.stack = QStackedWidget()

        # Page 0: Live Camera Feed
        self.cam_lbl = QLabel("[ LIVE VIEWPORT INITIALIZING ]")
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_lbl.setStyleSheet("background-color: #07090e; color: #475569; font-family: 'Consolas', monospace;")
        self.stack.addWidget(self.cam_lbl)

        # Page 1: 3D WebGL Viewport
        profile = QWebEngineProfile.defaultProfile()
        s = profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

        self.webview = QWebEngineView()
        self.stack.addWidget(self.webview)

        lay.addWidget(self.stack, stretch=1)
        return vp

    # ── Camera Management ─────────────────────────────────────────────────────
    def _start_camera_thread(self):
        self.camera_thread = CameraThread(cam_index=self.camera_index)
        self.camera_thread.new_frame.connect(self.update_video_feed)
        self.camera_thread.frame_ready_for_capture.connect(self.store_frame)
        self.camera_thread.start()
        self.camera_enabled = True
        self.btn_cam_toggle.setText("Pause Camera")
        self._refresh_cam_switch_label()

    def _stop_camera_thread(self):
        self.camera_thread.stop()
        self.camera_enabled = False
        self.btn_cam_toggle.setText("Resume Camera")
        if self.stack.currentIndex() == 0:
            self.cam_lbl.setPixmap(QPixmap())
            self.cam_lbl.setText("[ CAMERA SENSOR PAUSED ]")

    # ── Helpers & State Sync ──────────────────────────────────────────────────
    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        prefix = f'<span style="color:#64748b;">[{timestamp}]</span> '
        if "[+]" in msg or "[✓]" in msg:
            colored = f'{prefix}<span style="color:#10b981;">{msg}</span>'
        elif "[!]" in msg or "[WARN]" in msg:
            colored = f'{prefix}<span style="color:#f59e0b;">{msg}</span>'
        elif "[ERROR]" in msg or "ERROR" in msg:
            colored = f'{prefix}<span style="color:#ef4444;">{msg}</span>'
        elif "[*]" in msg:
            colored = f'{prefix}<span style="color:#38bdf8;">{msg}</span>'
        else:
            colored = f'{prefix}<span style="color:#cbd5e1;">{msg}</span>'
        self.txt.append(colored)

    def _refresh_fyp_label(self):
        students = SETTINGS.get("students", [])
        if students:
            parts = [f"{s.get('name', '')} ({s.get('roll', '')})" for s in students if s.get("name") or s.get("roll")]
            self.lbl_fyp.setText("FYP Team: " + " | ".join(parts))
        else:
            self.lbl_fyp.setText("FYP Team Attribution")

    def _refresh_cam_switch_label(self):
        if self.camera_index == 1:
            self.btn_cam_switch.setText("Ext Camera")
        else:
            self.btn_cam_switch.setText("Built-in")

    def _set_capture_mode(self, mode):
        is_auto = (mode == "Auto")
        self.btn_mode_auto.setProperty("active", is_auto)
        self.btn_mode_manual.setProperty("active", not is_auto)
        self.btn_mode_auto.style().unpolish(self.btn_mode_auto)
        self.btn_mode_auto.style().polish(self.btn_mode_auto)
        self.btn_mode_manual.style().unpolish(self.btn_mode_manual)
        self.btn_mode_manual.style().polish(self.btn_mode_manual)

        if is_auto:
            self.btn_action.setText("Execute Turntable Loop")
            self.btn_action.setEnabled(True)
            self.btn_capture.setVisible(False)
            self.log("[*] Switched to Automated Turntable mode.")
        else:
            self.btn_action.setText("Compile Captured Views")
            self.btn_action.setEnabled(False)
            self.btn_capture.setVisible(True)
            self.manual_capture_count = 0
            self._update_capture_btn_label()
            self.log("[*] Switched to Manual Capture mode.")

    def _on_shots_changed(self, val):
        SETTINGS["num_images"] = val
        step = SETTINGS.get("rotation_step", 10)
        self.lbl_shots_info.setText(f"Rotary Step: {step}° ({val} views)")

    def _update_capture_btn_label(self):
        num = self.spn_images.value()
        done = self.manual_capture_count
        if done < num:
            self.btn_capture.setText(f"Capture View ({done + 1}/{num})")
            self.btn_capture.setEnabled(True)
        else:
            self.btn_capture.setText("All Views Captured")
            self.btn_capture.setEnabled(False)
            self.btn_action.setEnabled(True)

    # ── Slots & Actions ───────────────────────────────────────────────────────
    @pyqtSlot(object)
    def store_frame(self, frame):
        with self.camera_frame_lock:
            self.latest_frame = frame.copy()

    def get_latest_frame(self):
        with self.camera_frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    @pyqtSlot(QPixmap)
    def update_video_feed(self, px):
        if self.stack.currentIndex() == 0:
            self.cam_lbl.setPixmap(px.scaled(
                self.cam_lbl.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))

    @pyqtSlot()
    def open_settings(self):
        dlg = SettingsDialog(SETTINGS, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.spn_images.setValue(SETTINGS.get("num_images", 8))
            self.lbl_hw_chip.setText(f"TURNTABLE: {SETTINGS.get('arduino_port', 'COM4')}")
            self._refresh_fyp_label()
            self.log("[✓] Studio configuration updated.")

    @pyqtSlot()
    def open_export_dir(self):
        export_dir = SETTINGS.get("export_dir", DEFAULT_EXPORT_DIR)
        os.makedirs(export_dir, exist_ok=True)
        os.startfile(export_dir)

    @pyqtSlot()
    def toggle_camera(self):
        if self.camera_enabled:
            self._stop_camera_thread()
            self.log("[*] Camera sensor paused.")
        else:
            self._start_camera_thread()
            self.log("[*] Camera sensor resumed.")

    @pyqtSlot()
    def switch_camera(self):
        was_enabled = self.camera_enabled
        if was_enabled:
            self.camera_thread.stop()
        self.camera_index = 1 - self.camera_index
        SETTINGS["camera_index"] = self.camera_index
        self._refresh_cam_switch_label()
        self.log(f"[*] Switched camera index to {self.camera_index}.")
        if was_enabled:
            self._start_camera_thread()

    @pyqtSlot()
    def capture_manual(self):
        frame = self.get_latest_frame()
        if frame is None:
            self.log("[!] Live frame unavailable. Waiting for sensor...")
            return

        idx = self.manual_capture_count
        name = f"img_{idx}.jpg"
        cv2.imwrite(os.path.join(SCAN_FOLDER, name), frame)
        self.log(f"[+] Saved view {idx + 1}: {name}")
        self.manual_capture_count += 1
        self._update_capture_btn_label()

    # ── AI Reconstruction Triggers ────────────────────────────────────────────
    @pyqtSlot()
    def generate_from_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image for 3D Reconstruction", "",
            "Images (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*)"
        )
        if not path:
            return

        self.lbl_selected_img.setText(os.path.basename(path))
        self.log(f"[*] Target image selected: {path}")

        self._set_ui_processing_state(True, "Generating 3D Mesh...")
        self.reconstruction_thread = ReconstructionThread(path, SETTINGS, parent=self)
        self.reconstruction_thread.log_msg.connect(self.log)
        self.reconstruction_thread.progress_pct.connect(self.progress_bar.setValue)
        self.reconstruction_thread.scan_complete.connect(self._on_reconstruction_complete)
        self.reconstruction_thread.scan_error.connect(self._on_reconstruction_error)
        self.reconstruction_thread.start()

    @pyqtSlot()
    def generate_from_multiple_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Perspective Images", "",
            "Images (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*)"
        )
        if not paths:
            return

        self.lbl_selected_img.setText(f"{len(paths)} photos selected")
        self.log(f"[*] Selected {len(paths)} multi-view images.")

        self._set_ui_processing_state(True, "Processing Multi-View...")
        self.reconstruction_thread = ReconstructionThread(paths, SETTINGS, base_name="multiview_model", parent=self)
        self.reconstruction_thread.log_msg.connect(self.log)
        self.reconstruction_thread.progress_pct.connect(self.progress_bar.setValue)
        self.reconstruction_thread.scan_complete.connect(self._on_reconstruction_complete)
        self.reconstruction_thread.scan_error.connect(self._on_reconstruction_error)
        self.reconstruction_thread.start()

    @pyqtSlot()
    def generate_from_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Photos Directory")
        if not folder:
            return

        found = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"):
            found += _glob.glob(os.path.join(folder, ext))
            found += _glob.glob(os.path.join(folder, ext.upper()))
        found = sorted(list(set(found)))

        if not found:
            QMessageBox.warning(self, "No Photos", f"No supported image files found in '{folder}'.")
            return

        base_name = os.path.basename(os.path.normpath(folder))
        self.lbl_selected_img.setText(f"{base_name} ({len(found)} images)")
        self.log(f"[*] Directory loaded: {len(found)} images found.")

        self._set_ui_processing_state(True, "Processing Folder...")
        self.reconstruction_thread = ReconstructionThread(found, SETTINGS, base_name=base_name, parent=self)
        self.reconstruction_thread.log_msg.connect(self.log)
        self.reconstruction_thread.progress_pct.connect(self.progress_bar.setValue)
        self.reconstruction_thread.scan_complete.connect(self._on_reconstruction_complete)
        self.reconstruction_thread.scan_error.connect(self._on_reconstruction_error)
        self.reconstruction_thread.start()

    def _set_ui_processing_state(self, processing, label_text=None):
        self.btn_gen_image.setEnabled(not processing)
        self.btn_gen_multi.setEnabled(not processing)
        self.btn_gen_folder.setEnabled(not processing)
        self.btn_action.setEnabled(not processing)
        self.progress_bar.setVisible(processing)
        if processing:
            self.progress_bar.setValue(0)
            if label_text:
                self.lbl_export_status.setText(label_text)
        else:
            self.lbl_export_status.setText("Ready for export")

    @pyqtSlot(str)
    def _on_reconstruction_complete(self, glb_path):
        self._set_ui_processing_state(False)
        self.log(f"[✓] Reconstruction and format conversion complete: {os.path.basename(glb_path)}")
        self.show_model(glb_path)

    @pyqtSlot(str)
    def _on_reconstruction_error(self, err):
        self._set_ui_processing_state(False)
        self.log(f"[!] Reconstruction failed: {err}")
        QMessageBox.critical(self, "Reconstruction Error", err)

    # ── Hardware Loop Actions ─────────────────────────────────────────────────
    @pyqtSlot()
    def start_scan(self):
        self._set_ui_processing_state(True, "Executing Loop...")
        mode = "Auto Turntable" if self.btn_mode_auto.property("active") else "Manual Scan"

        self.scan_thread = HardwareScanThread(
            SETTINGS,
            mode,
            frame_supplier=self.get_latest_frame,
            parent=self
        )
        self.scan_thread.log_msg.connect(self.log)
        self.scan_thread.progress_pct.connect(self.progress_bar.setValue)
        self.scan_thread.scan_complete.connect(self._on_reconstruction_complete)
        self.scan_thread.scan_error.connect(self._on_reconstruction_error)
        self.scan_thread.start()

    @pyqtSlot()
    def reprocess_existing_images(self):
        found = _glob.glob(os.path.join(SCAN_FOLDER, "img_*.jpg"))
        if not found:
            QMessageBox.warning(self, "No Images", "Scan folder contains no captured frames.")
            return

        self._set_ui_processing_state(True, "Re-Processing...")
        self.reconstruction_thread = ReconstructionThread(found, SETTINGS, base_name="reprocessed_scan", parent=self)
        self.reconstruction_thread.log_msg.connect(self.log)
        self.reconstruction_thread.progress_pct.connect(self.progress_bar.setValue)
        self.reconstruction_thread.scan_complete.connect(self._on_reconstruction_complete)
        self.reconstruction_thread.scan_error.connect(self._on_reconstruction_error)
        self.reconstruction_thread.start()

    # ── Viewport Switching & Loading ──────────────────────────────────────────
    @pyqtSlot()
    def back_to_camera(self):
        self.stack.setCurrentIndex(0)
        self.btn_vp_cam.setProperty("active", True)
        self.btn_vp_3d.setProperty("active", False)
        self.btn_vp_cam.style().unpolish(self.btn_vp_cam)
        self.btn_vp_cam.style().polish(self.btn_vp_cam)
        self.btn_vp_3d.style().unpolish(self.btn_vp_3d)
        self.btn_vp_3d.style().polish(self.btn_vp_3d)
        self.lbl_vp_telemetry.setText("SENSOR READY — AWAITING CAPTURE")

    @pyqtSlot()
    def load_mesh(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load 3D Model Asset", "", "3D Assets (*.glb *.gltf *.obj *.stl *.fbx)"
        )
        if path:
            self.show_model(path)

    @pyqtSlot()
    def view_loaded_model(self):
        if self._current_model_path and os.path.exists(self._current_model_path):
            self.show_model(self._current_model_path)
        else:
            default_path = os.path.join(APP_DIR, "scanned_object.glb")
            if os.path.exists(default_path):
                self.show_model(default_path)
            else:
                self.log("[!] No active 3D asset found. Generate or load a model first.")

    @pyqtSlot()
    def toggle_labels(self):
        self._labels_visible = not self._labels_visible
        state = "ON" if self._labels_visible else "OFF"
        self.btn_toggle_labels.setText(f"Labels: {state}")
        if self.stack.currentIndex() == 1:
            self.webview.page().runJavaScript(
                f"if(window.toggleLabels) window.toggleLabels({str(self._labels_visible).lower()});"
            )

    @pyqtSlot()
    def open_current_in_blender(self):
        if not self._current_model_path or not os.path.exists(self._current_model_path):
            QMessageBox.warning(self, "No Asset", "No 3D model loaded. Generate or import a model first.")
            return

        export_dir = SETTINGS.get("export_dir", DEFAULT_EXPORT_DIR)
        base_name = os.path.splitext(os.path.basename(self._current_model_path))[0]
        blend_path = os.path.join(export_dir, f"{base_name}.blend")

        if not os.path.exists(blend_path):
            self.log("[*] Compiling native Blender workspace (.blend)...")
            self.export_for_blender("BLEND")
            return

        self.log(f"[+] Launching Blender Studio with {os.path.basename(blend_path)}...")
        open_in_blender(blend_path)

    @pyqtSlot()
    def export_for_blender(self, fmt):
        if not self._current_model_path or not os.path.exists(self._current_model_path):
            QMessageBox.warning(self, "No Asset", "No 3D model loaded. Generate or import a model first.")
            return

        if fmt == "GLB":
            export_dir = SETTINGS.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(export_dir, f"export_{timestamp}.glb")
            import shutil
            shutil.copy2(self._current_model_path, dest)
            self.log(f"[✓] GLB asset exported to: {dest}")
            self.lbl_export_status.setText(os.path.basename(dest))
            os.startfile(export_dir)
            return

        self.log(f"[*] Exporting asset as {fmt}...")
        self.lbl_export_status.setText(f"Exporting {fmt}...")

        self._export_thread = BlenderExportThread(
            self._current_model_path, fmt, SETTINGS, self
        )
        self._export_thread.log_msg.connect(self.log)
        self._export_thread.export_done.connect(self._on_export_done)
        self._export_thread.export_error.connect(lambda e: self.log(f"[!] Export error: {e}"))
        self._export_thread.start()

    @pyqtSlot(str)
    def _on_export_done(self, path):
        self.lbl_export_status.setText(os.path.basename(path))
        self.log(f"[✓] Export generated: {path}")
        os.startfile(os.path.dirname(path))

    # ── Three.js WebGL Viewport Server & Injection ────────────────────────────
    @pyqtSlot(str)
    def show_model(self, model_path):
        import http.server
        import urllib.parse

        self._current_model_path = model_path
        self.lbl_export_status.setText(os.path.basename(model_path))

        # Update viewport navigation buttons
        self.stack.setCurrentIndex(1)
        self.btn_vp_cam.setProperty("active", False)
        self.btn_vp_3d.setProperty("active", True)
        self.btn_vp_cam.style().unpolish(self.btn_vp_cam)
        self.btn_vp_cam.style().polish(self.btn_vp_cam)
        self.btn_vp_3d.style().unpolish(self.btn_vp_3d)
        self.btn_vp_3d.style().polish(self.btn_vp_3d)

        if hasattr(self, '_httpd') and self._httpd:
            try: self._httpd.shutdown()
            except Exception: pass
            self._httpd = None

        try:
            model_bytes = open(model_path, "rb").read()
        except Exception as e:
            self.log(f"[!] Error reading 3D model asset: {e}")
            return

        js_files = {}
        for js_name in ("three.min.js", "OrbitControls.js", "GLTFLoader.js"):
            js_path = os.path.join(APP_DIR, js_name)
            if os.path.exists(js_path):
                js_files[f"/{js_name}"] = open(js_path, "rb").read()

        model_filename = os.path.basename(model_path)
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>3D Viewport — {model_filename}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{ width:100%; height:100%; background:#07090e; overflow:hidden; font-family:'Segoe UI',sans-serif; }}
    canvas {{ display:block; width:100%; height:100%; }}
    
    /* ── Minimalist Engineering Callouts ── */
    .label-3d {{
      position: absolute;
      pointer-events: none;
      transform: translate(-50%, -100%);
      z-index: 100;
      transition: opacity 0.2s ease;
      will-change: transform, opacity;
    }}
    .label-3d.hidden {{ opacity: 0 !important; }}
    
    .label-card {{
      background: rgba(10, 14, 22, 0.94);
      border: 1px solid #233044;
      border-radius: 4px;
      padding: 3px 8px;
      white-space: nowrap;
      box-shadow: 0 4px 16px rgba(0,0,0,0.6);
      font-family: 'Consolas', monospace;
    }}
    .label-name {{
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }}
    .label-desc {{
      font-size: 11px;
      font-weight: 600;
      color: #f1f5f9;
      margin-top: 1px;
    }}
    .label-line {{
      width: 1px;
      height: 20px;
      margin: 0 auto;
      background: currentColor;
      opacity: 0.5;
    }}
    .label-dot {{
      width: 5px;
      height: 5px;
      border-radius: 50%;
      margin: 0 auto;
      background: currentColor;
    }}
    
    #info-overlay {{
      display:none; position:absolute; inset:0;
      color:#94a3b8; font:14px sans-serif;
      justify-content:center; align-items:center; text-align:center;
    }}
  </style>
</head>
<body>
  <div id="container"></div>
  <div id="info-overlay"></div>
  <div id="labels-container"></div>

  <script src="/three.min.js"></script>
  <script src="/OrbitControls.js"></script>
  <script src="/GLTFLoader.js"></script>
  <script>
    var scene, camera, renderer, controls;
    var labelElements = [];
    var labelPositions = [];
    var labelsVisible = true;

    function createDimensionLabels(box, center, size) {{
      var container = document.getElementById('labels-container');
      container.innerHTML = '';
      labelElements = [];
      labelPositions = [];

      var wCm = (size.x * 100).toFixed(1);
      var hCm = (size.y * 100).toFixed(1);
      var dCm = (size.z * 100).toFixed(1);

      var markers = [
        {{ name: 'Height (Z)', desc: hCm + ' cm', pos: new THREE.Vector3(center.x, box.max.y, center.z), color: '#38bdf8' }},
        {{ name: 'Width (X)', desc: wCm + ' cm', pos: new THREE.Vector3(box.max.x, center.y, center.z), color: '#10b981' }},
        {{ name: 'Depth (Y)', desc: dCm + ' cm', pos: new THREE.Vector3(center.x, center.y, box.max.z), color: '#f59e0b' }}
      ];

      markers.forEach(function(m) {{
        var el = document.createElement('div');
        el.className = 'label-3d';
        el.style.color = m.color;
        el.innerHTML = 
          '<div class="label-card" style="border-color:' + m.color + '66">' +
            '<div class="label-name" style="color:' + m.color + '">' + m.name + '</div>' +
            '<div class="label-desc">' + m.desc + '</div>' +
          '</div>' +
          '<div class="label-line"></div>' +
          '<div class="label-dot"></div>';
        container.appendChild(el);
        labelElements.push(el);
        labelPositions.push(m.pos);
      }});
    }}

    function updateLabels() {{
      if (!camera || !renderer) return;
      var width = renderer.domElement.clientWidth;
      var height = renderer.domElement.clientHeight;

      for (var i = 0; i < labelElements.length; i++) {{
        var pos = labelPositions[i].clone();
        pos.project(camera);

        if (pos.z > 1.0 || !labelsVisible) {{
          labelElements[i].style.opacity = '0';
        }} else {{
          labelElements[i].style.opacity = '1';
          labelElements[i].style.left = ((pos.x * 0.5 + 0.5) * width) + 'px';
          labelElements[i].style.top = ((-pos.y * 0.5 + 0.5) * height) + 'px';
        }}
      }}
    }}

    window.toggleLabels = function(visible) {{
      labelsVisible = visible;
      labelElements.forEach(function(el) {{
        if (visible) {{
          el.classList.remove('hidden');
        }} else {{
          el.classList.add('hidden');
        }}
      }});
    }};

    function init() {{
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x07090e);

      camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.01, 1000);
      camera.position.set(0, 1.8, 4.0);

      renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      try {{ renderer.outputEncoding = THREE.sRGBEncoding; }} catch(e) {{}}
      document.getElementById('container').appendChild(renderer.domElement);

      // Studio Lighting
      scene.add(new THREE.AmbientLight(0xffffff, 0.55));
      var d1 = new THREE.DirectionalLight(0xfff7ed, 1.2);
      d1.position.set(4, 7, 5); scene.add(d1);
      var d2 = new THREE.DirectionalLight(0xe0f2fe, 0.6);
      d2.position.set(-5, 4, -4); scene.add(d2);
      var d3 = new THREE.DirectionalLight(0x38bdf8, 0.4);
      d3.position.set(0, -4, -6); scene.add(d3);

      // Ground Grid
      var grid = new THREE.GridHelper(3.0, 30, 0x1f2737, 0x111622);
      scene.add(grid);

      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.06;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 1.0;

      var loader = new THREE.GLTFLoader();
      loader.load('/model.glb', function(gltf) {{
        var model = gltf.scene;
        scene.add(model);

        var box = new THREE.Box3().setFromObject(model);
        var center = box.getCenter(new THREE.Vector3());
        var size = box.getSize(new THREE.Vector3());

        model.position.x -= center.x;
        model.position.y -= box.min.y;
        model.position.z -= center.z;

        box.setFromObject(model);
        var groundedCenter = box.getCenter(new THREE.Vector3());

        var maxDim = Math.max(size.x, size.y, size.z);
        camera.position.set(groundedCenter.x, groundedCenter.y + maxDim * 0.4, groundedCenter.z + maxDim * 2.2);
        controls.target.copy(groundedCenter);
        controls.update();

        createDimensionLabels(box, groundedCenter, size);
      }}, undefined, function(err) {{
        document.getElementById('info-overlay').style.display = 'flex';
        document.getElementById('info-overlay').textContent = 'Error loading GLB asset.';
      }});

      window.addEventListener('resize', function() {{
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
      }});

      animate();
    }}

    function animate() {{
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
      updateLabels();
    }}

    window.onload = init;
  </script>
</body>
</html>"""

        html_bytes = html.encode("utf-8")

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self_h):
                p = urllib.parse.urlparse(self_h.path).path
                if p in ("/", "/index.html"):
                    self_h.send_response(200)
                    self_h.send_header("Content-Type", "text/html; charset=utf-8")
                    self_h.send_header("Content-Length", str(len(html_bytes)))
                    self_h.end_headers()
                    self_h.wfile.write(html_bytes)
                elif p == "/model.glb":
                    self_h.send_response(200)
                    self_h.send_header("Content-Type", "model/gltf-binary")
                    self_h.send_header("Content-Length", str(len(model_bytes)))
                    self_h.send_header("Access-Control-Allow-Origin", "*")
                    self_h.end_headers()
                    self_h.wfile.write(model_bytes)
                elif p in js_files:
                    data = js_files[p]
                    self_h.send_response(200)
                    self_h.send_header("Content-Type", "application/javascript")
                    self_h.send_header("Content-Length", str(len(data)))
                    self_h.end_headers()
                    self_h.wfile.write(data)
                else:
                    self_h.send_response(404)
                    self_h.end_headers()

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

        viewer_url = f"http://127.0.0.1:{port}/"
        self.webview.setUrl(QUrl(viewer_url))
        self.lbl_vp_telemetry.setText(f"ACTIVE ASSET: {model_filename}")
        self.log(f"[✓] 3D Viewport active: {model_filename}")

    def closeEvent(self, event):
        if self.camera_enabled and hasattr(self, 'camera_thread'):
            self.camera_thread.stop()
        if hasattr(self, '_httpd') and self._httpd:
            self._httpd.shutdown()
        event.accept()


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    w = ModernScannerApp()
    w.show()
    sys.exit(app.exec())