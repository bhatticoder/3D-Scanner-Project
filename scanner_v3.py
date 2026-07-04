import os, sys, json, time, threading
import glob as _glob
import requests, cv2

if getattr(sys, 'frozen', False):
    # Running as a bundled executable
    APP_DIR = sys._MEIPASS
else:
    # Running as normal python script
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SCAN_FOLDER = os.path.join(os.environ["USERPROFILE"], "Documents", "3D_Scanner", "scan")
DEFAULT_EXPORT_DIR = os.path.join(os.environ["USERPROFILE"], "Documents", "3D_Scanner", "exports")
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
    QHeaderView, QFormLayout
)
from PyQt6.QtCore  import Qt, QThread, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui   import QImage, QPixmap, QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore    import QWebEngineSettings, QWebEngineProfile

# ── Paths & Config ────────────────────────────────────────────────────────────
_SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
APP_DIR            = _SCRIPT_DIR
SCAN_FOLDER        = os.path.join(APP_DIR, "scan")
DEFAULT_MODEL_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "scanned_object.glb")
DEFAULT_EXPORT_DIR = os.path.join(APP_DIR, "exports")
os.makedirs(SCAN_FOLDER, exist_ok=True)
os.makedirs(DEFAULT_EXPORT_DIR, exist_ok=True)

CONFIG_PATH    = os.path.join(APP_DIR, "config.json")
DEFAULT_CONFIG = {
    "tripo_api_key": "",
    "arduino_port":  "COM4",
    "arduino_baud":  9600,
    "output_path":   DEFAULT_MODEL_PATH,
    "export_dir":    DEFAULT_EXPORT_DIR,
    "num_images":    4,
    "rotation_step": 10,
    "camera_index":  1,
    "students":      []
}

def load_settings():
    if os.path.exists(CONFIG_PATH):
        try:
            d = json.load(open(CONFIG_PATH))
            for k, v in DEFAULT_CONFIG.items():
                d.setdefault(k, v)
            return d
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_settings(s):
    json.dump(s, open(CONFIG_PATH, "w"), indent=4)

SETTINGS = load_settings()


# ── Settings Dialog ───────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(540)
        self.setStyleSheet("""
            QDialog      { background:#1a1a1a; color:#fff; }
            QLabel       { color:#ccc; }
            QLineEdit, QSpinBox {
                background:#111; color:#fff;
                border:1px solid #444; padding:4px; border-radius:3px;
            }
            QPushButton  { background:#2b719e; color:#fff; padding:6px 12px;
                           border-radius:4px; border:none; font-weight:bold; }
            QPushButton:hover { background:#3b8dc0; }
            QGroupBox    { border:1px solid #333; margin-top:1ex;
                           font-weight:bold; color:#777; }
            QTableWidget { background:#111; color:#fff;
                           gridline-color:#333; border:1px solid #444; }
            QHeaderView::section { background:#222; color:#aaa; border:1px solid #333; }
        """)

        main_lay = QVBoxLayout(self)

        # ── API & Hardware ────────────────────────────────────────────────────
        hw_box = QGroupBox("API & Hardware")
        form   = QFormLayout(hw_box)

        self.ent_token = QLineEdit(settings.get("tripo_api_key", ""))
        self.ent_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.ent_token.setPlaceholderText("tsk_…")
        form.addRow("API Token:", self.ent_token)

        self.ent_port = QLineEdit(settings.get("arduino_port", "COM4"))
        form.addRow("COM Port:", self.ent_port)

        self.spn_baud = QSpinBox()
        self.spn_baud.setRange(1200, 115200)
        self.spn_baud.setSingleStep(9600)
        self.spn_baud.setValue(settings.get("arduino_baud", 9600))
        form.addRow("Baud Rate:", self.spn_baud)

        self.spn_images = QSpinBox()
        self.spn_images.setRange(1, 72)
        self.spn_images.setValue(settings.get("num_images", 4))
        self.spn_images.setToolTip(
            "Number of manual capture views in Manual Scan mode."
        )
        form.addRow("Manual Images:", self.spn_images)

        # Export directory row
        exp_row = QHBoxLayout()
        self.ent_export = QLineEdit(settings.get("export_dir", DEFAULT_EXPORT_DIR))
        self.ent_export.setReadOnly(True)
        btn_browse_exp = QPushButton("Browse...")
        btn_browse_exp.setStyleSheet("background:#334455; max-width:80px; font-size:11px;")
        btn_browse_exp.clicked.connect(self._browse_export_dir)
        exp_row.addWidget(self.ent_export, stretch=5)
        exp_row.addWidget(btn_browse_exp, stretch=1)
        form.addRow("Export Folder:", exp_row)

        main_lay.addWidget(hw_box)

        # ── FYP Team ──────────────────────────────────────────────────────────
        stu_box = QGroupBox("FYP Team Members")
        stu_lay = QVBoxLayout(stu_box)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Name", "Roll No"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(140)

        for stu in settings.get("students", []):
            self._add_row(stu.get("name", ""), stu.get("roll", ""))

        stu_lay.addWidget(self.table)

        row_btns = QHBoxLayout()
        btn_add = QPushButton("＋  Add Student")
        btn_add.setStyleSheet("background:#2e7d32;")
        btn_add.clicked.connect(lambda: self._add_row())
        btn_rem = QPushButton("−  Remove Selected")
        btn_rem.setStyleSheet("background:#7b1c1c;")
        btn_rem.clicked.connect(self._remove_row)
        row_btns.addWidget(btn_add); row_btns.addWidget(btn_rem)
        stu_lay.addLayout(row_btns)
        main_lay.addWidget(stu_box)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Save).setStyleSheet("background:#1b5e20;")
        main_lay.addWidget(btns)

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
        self.settings["tripo_api_key"] = self.ent_token.text().strip()
        self.settings["arduino_port"]  = self.ent_port.text().strip()
        self.settings["arduino_baud"]  = self.spn_baud.value()
        self.settings["num_images"]    = self.spn_images.value()
        self.settings["export_dir"]    = self.ent_export.text().strip()
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
    new_frame               = pyqtSignal(QPixmap)
    frame_ready_for_capture = pyqtSignal(object)

    def __init__(self, cam_index=1, parent=None):
        super().__init__(parent)
        self.cam_index = cam_index
        self.running   = True

    def run(self):
        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fallback to the other index
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


# ── Scan Thread ───────────────────────────────────────────────────────────────
class HardwareScanThread(QThread):
    log_msg       = pyqtSignal(str)
    scan_complete = pyqtSignal(str)
    scan_error    = pyqtSignal(str)

    def __init__(self, settings, mode, frame_supplier=None, parent=None):
        super().__init__(parent)
        self.settings      = settings
        self.scan_mode     = mode
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
                    try:
                        if serial:
                            # Connect to your Arduino on COM8 / 9600 baud rate
                            arduino = serial.Serial(
                                self.settings["arduino_port"],
                                self.settings["arduino_baud"], timeout=1)
                            time.sleep(2) # Connection handshake buffer
                            self.log_msg.emit(f"Arduino connected! Starting FULLY AUTOMATIC loop for {num_images} steps.")
                    except Exception as e:
                        self.log_msg.emit(f"[ERROR] Arduino Serial Connection Failed: {e}")
                        raise RuntimeError("Could not connect to the specified Arduino COM port.")

                    # Clear out old images inside your scan folder before capturing
                    import glob as _glob
                    for old in _glob.glob(os.path.join(SCAN_FOLDER, "img_*.jpg")):
                        try: os.remove(old)
                        except Exception: pass

                    self.log_msg.emit(
                        f"Arduino connected. Auto Turntable will capture {num_images} images "
                        f"with {rotation_step}° steps."
                    )

                    # Core Automatic Iteration Loop
                    for idx in range(num_images):
                        if not self.isRunning():
                            break

                        self.log_msg.emit(f"==> Step {idx + 1}/{num_images}: Rotating {rotation_step}°...")
                        if arduino and arduino.is_open:
                            arduino.reset_input_buffer()
                            arduino.reset_output_buffer()
                            arduino.write(b'R\n')
                            arduino.flush()
                            self.log_msg.emit("Serial command sent: R")
                            time.sleep(2.0)
                        else:
                            time.sleep(2.0)

                        self.log_msg.emit("Capturing live camera frame...")
                        frame = self._get_latest_frame()
                        if frame is None:
                            self.log_msg.emit("[WARN] No live frame available yet. Waiting for camera...")
                            wait_start = time.time()
                            while self.isRunning() and frame is None and time.time() - wait_start < 5.0:
                                time.sleep(0.1)
                                frame = self._get_latest_frame()

                        if frame is not None:
                            name = f"img_{idx}.jpg"
                            cv2.imwrite(os.path.join(SCAN_FOLDER, name), frame)
                            self.log_msg.emit(f"[📸] Saved {name} ({idx + 1}/{num_images})")
                        else:
                            self.log_msg.emit(f"[ERROR] Live frame unavailable at step {idx + 1}.")

                    if arduino and arduino.is_open:
                        arduino.close()

                # ── AUTOMATIC TRIPO3D PIPELINE UPLOAD ──
                self.log_msg.emit("All steps completed successfully! Processing views for Tripo3D...")
                tid = self._submit()
                self.log_msg.emit(f"Remote cloud compiler task created. ID: {tid}")
                url = self._poll(tid)
                self.log_msg.emit("Downloading compiled 3D mesh asset…")
                self._dl(url)
                self.scan_complete.emit(self.settings["output_path"])
                
            except Exception as e:
                self.scan_error.emit(str(e))

    def _submit(self):
        h = {"Authorization": f"Bearer {self.settings['tripo_api_key']}"}
        
        # Discover all dynamically generated images inside the scan folder
        found_images = sorted(
            _glob.glob(os.path.join(SCAN_FOLDER, "img_*.jpg")),
            key=lambda p: int(os.path.splitext(os.path.basename(p))[0].replace("img_", ""))
        )
        
        n_captured = len(found_images)
        if n_captured == 0:
            raise FileNotFoundError("No image files found in your local scan folder. Cannot compile.")

        # Dynamically sample exactly 4 perfectly distributed orthographic angles 
        # from whatever image pool count you choose (e.g. 4, 8, 16, 36)
        selected_images = []
        for i in range(4):
            # Safe rounding sequence ensures exact cross-sectional coverage across variable pool loops
            idx = int(round((i * n_captured) / 4.0)) % n_captured
            selected_images.append(found_images[idx])

        self.log_msg.emit(f"[INFO] Pool size: {n_captured} frames. Dynamically downsampled to 4 key perspective angles.")

        tokens = []
        for path in selected_images:
            name = os.path.basename(path)
            
            if os.path.getsize(path) == 0:
                raise RuntimeError(f"Image file {name} is empty (0 bytes).")

            with open(path, "rb") as f:
                r = requests.post(
                    "https://api.tripo3d.ai/v2/openapi/upload/sts", 
                    headers=h, 
                    files={"file": (name, f, "image/jpeg")}
                )
                r.raise_for_status()
                res_json = r.json()
                
                if res_json.get("code") != 0:
                    raise RuntimeError(f"Tripo3D Upload Error: {res_json.get('msg', 'Unknown Error')}")
                
                data_block = res_json.get("data")
                if not data_block:
                    raise KeyError(f"Missing data block in upload response. Response: {res_json}")
                
                # FIXED: Tripo3D STS endpoint uses 'image_token' instead of 'file_token'
                token = data_block.get("image_token") or data_block.get("file_token")
                if not token:
                    raise KeyError(f"Could not locate an image token. Keys available: {list(data_block.keys())}")
                    
                tokens.append(token)

        # Assemble your explicit payload mappings with structural validation
        payload = {
            "type": "multiview_to_model",
            "output_format": "glb",
            "files": [
                {"type": "jpg", "file_token": tokens[0], "orientation": "front"},
                {"type": "jpg", "file_token": tokens[1], "orientation": "right"}, 
                {"type": "jpg", "file_token": tokens[2], "orientation": "back"}, 
                {"type": "jpg", "file_token": tokens[3], "orientation": "left"},  
            ]
        }
        
        r = requests.post("https://api.tripo3d.ai/v2/openapi/task", headers={**h, "Content-Type": "application/json"}, json=payload)
        r.raise_for_status()
        
        task_json = r.json()
        if task_json.get("code") != 0:
            raise RuntimeError(f"Tripo3D Task Creation Error: {task_json.get('msg')}")
            
        return task_json["data"]["task_id"]

    def _poll(self, tid):
        while True:
            r = requests.get(f"https://api.tripo3d.ai/v2/openapi/task/{tid}", headers={"Authorization":f"Bearer {self.settings['tripo_api_key']}"})
            r.raise_for_status()
            d = r.json()["data"]
            self.log_msg.emit(f"Status: {d['status'].upper()}")
            if d["status"] == "success":
                out = d.get("output",{})
                return out[0].get("model") if isinstance(out,list) else (out.get("pbr_model") or out.get("model"))
            if d["status"] in ("failed","error"): raise RuntimeError("Tripo3D processing failed.")
            time.sleep(3)

    def _dl(self, url):
            r = requests.get(url, stream=True)
            r.raise_for_status()
            with open(self.settings["output_path"],"wb") as f:
                for chunk in r.iter_content(8192): 
                    f.write(chunk)


# ── Main Window ───────────────────────────────────────────────────────────────
class ModernScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Complete 3D Scanner Application")
        self.resize(1100, 680)
        self.setStyleSheet("""
            QMainWindow  { background:#101010; color:#fff; }
            QLabel       { color:#fff; }
            QTextBrowser { background:#151515; color:#ccc; border:1px solid #333; }
            QPushButton  { background:#2b719e; color:#fff; padding:8px;
                           border-radius:4px; border:none; font-weight:bold; }
            QPushButton:hover    { background:#3b8dc0; }
            QPushButton:disabled { background:#555; color:#888; }
            QLineEdit  { background:#1a1a1a; color:#fff; padding:5px;
                         border:1px solid #444; border-radius:3px; }
            QSpinBox   { background:#1a1a1a; color:#fff; padding:4px;
                         border:1px solid #444; border-radius:3px; }
            QGroupBox  { border:1px solid #333; margin-top:1ex;
                         font-weight:bold; color:#777; }
        """)

        # State
        self.current_manual_orientation = "front"
        self.manual_capture_count       = 0
        self.latest_frame               = None
        self.scan_thread                = None
        self._httpd                     = None
        self.camera_index               = SETTINGS.get("camera_index", 1)
        self.camera_enabled             = True
        self.camera_frame_lock          = threading.Lock()
        self._cam_auto_paused           = False  # True when stopped for Auto Turntable

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self._left_panel())
        root.addWidget(self._right_panel())

        self._start_camera_thread()  # Start after both panels built

    # ── Camera management ─────────────────────────────────────────────────────
    def _start_camera_thread(self):
        self.camera_thread = CameraThread(cam_index=self.camera_index)
        self.camera_thread.new_frame.connect(self.update_video_feed)
        self.camera_thread.frame_ready_for_capture.connect(self.store_frame)
        self.camera_thread.start()
        self.camera_enabled = True
        self.btn_cam_toggle.setText("⏸  Disable Camera")
        self.btn_cam_toggle.setStyleSheet("background:#6d4c41;")

    def _stop_camera_thread(self):
        self.camera_thread.stop()
        self.camera_enabled = False
        self.btn_cam_toggle.setText("▶  Enable Camera")
        self.btn_cam_toggle.setStyleSheet("background:#2e7d32;")
        if self.stack.currentIndex() == 0:
            self.cam_lbl.setPixmap(QPixmap())
            self.cam_lbl.setText("[ CAMERA DISABLED ]")

    # ── UI builders ───────────────────────────────────────────────────────────
    def _left_panel(self):
        p = QFrame(); p.setFixedWidth(300)
        p.setStyleSheet("background:#1a1a1a;")
        lay = QVBoxLayout(p); lay.setContentsMargins(20, 20, 20, 20)

        # Title row + ⚙ gear button
        title_row = QHBoxLayout()
        t = QLabel("3D RECONSTRUCTION")
        f = QFont(); f.setPointSize(13); f.setBold(True); t.setFont(f)
        title_row.addWidget(t, stretch=1)
        btn_gear = QPushButton("⚙")
        btn_gear.setFixedSize(32, 32)
        btn_gear.setToolTip("Open Settings")
        btn_gear.setStyleSheet(
            "background:#333; font-size:16px; padding:0; border-radius:4px;"
        )
        btn_gear.clicked.connect(self.open_settings)
        title_row.addWidget(btn_gear)
        lay.addLayout(title_row)
        lay.addSpacing(12)

        # Mode toggle
        self.mode_btn = QPushButton("Mode: Auto Turntable")
        self.mode_btn.setStyleSheet("background:#333;")
        self.mode_btn.clicked.connect(self.toggle_mode)
        lay.addWidget(self.mode_btn)
        lay.addSpacing(6)

        # Images-per-scan spinbox
        img_row = QHBoxLayout()
        lbl_img = QLabel("Manual shots:")
        lbl_img.setStyleSheet("color:#aaa; font-size:12px;")
        img_row.addWidget(lbl_img)
        self.spn_images = QSpinBox()
        self.spn_images.setRange(1, 72)
        self.spn_images.setValue(SETTINGS.get("num_images", 4))
        self.spn_images.setFixedWidth(68)
        self.spn_images.setToolTip(
            "Number of manual captures in Manual Scan mode."
        )
        self.spn_images.valueChanged.connect(
            lambda v: SETTINGS.update({"num_images": v})
        )
        img_row.addWidget(self.spn_images)
        lay.addLayout(img_row)
        lay.addSpacing(6)

        # Scan / compile button
        self.btn_action = QPushButton("Execute Hardware Loop")
        self.btn_action.clicked.connect(self.start_scan)
        lay.addWidget(self.btn_action)

        # Manual capture button (hidden in Auto mode)
        self.btn_capture = QPushButton("Capture View (1)")
        self.btn_capture.setStyleSheet("background:#bd6813;")
        self.btn_capture.setDisabled(True)
        self.btn_capture.clicked.connect(self.capture_manual)
        lay.addWidget(self.btn_capture)
        lay.addSpacing(6)

        # Re-process
        self.btn_reprocess = QPushButton("Re-Process Existing Images")
        self.btn_reprocess.setStyleSheet("background:#2e7d32;")
        self.btn_reprocess.clicked.connect(self.reprocess_existing_images)
        lay.addWidget(self.btn_reprocess)
        lay.addSpacing(6)

        # Load GLB
        self.btn_load = QPushButton("Load External .GLB Mesh")
        self.btn_load.setStyleSheet("background:#444;")
        self.btn_load.clicked.connect(self.load_mesh)
        lay.addWidget(self.btn_load)
        lay.addSpacing(4)

        # Back to Camera (visible when viewer is active)
        self.btn_back_cam = QPushButton("🔙  Back to Camera")
        self.btn_back_cam.setStyleSheet("background:#0d47a1;")
        self.btn_back_cam.clicked.connect(self.back_to_camera)
        lay.addWidget(self.btn_back_cam)
        lay.addSpacing(10)

        # Camera controls row
        cam_row = QHBoxLayout()
        self.btn_cam_toggle = QPushButton("⏸  Disable Camera")
        self.btn_cam_toggle.setStyleSheet("background:#6d4c41;")
        self.btn_cam_toggle.setToolTip("Enable or disable the live camera feed")
        self.btn_cam_toggle.clicked.connect(self.toggle_camera)
        cam_row.addWidget(self.btn_cam_toggle, stretch=1)

        self.btn_cam_switch = QPushButton("📷 Ext")
        self.btn_cam_switch.setFixedWidth(72)
        self.btn_cam_switch.setStyleSheet("background:#4a148c;")
        self.btn_cam_switch.clicked.connect(self.switch_camera)
        cam_row.addWidget(self.btn_cam_switch)
        lay.addLayout(cam_row)
        self._refresh_cam_switch_label()
        lay.addSpacing(10)

        # Diagnostics
        diag_lbl = QLabel("SYSTEM DIAGNOSTICS")
        diag_lbl.setStyleSheet("color:#aaaaaa; font-weight:bold;")
        lay.addWidget(diag_lbl)
        self.txt = QTextBrowser()
        self.txt.setOpenExternalLinks(True)
        lay.addWidget(self.txt)

        # FYP attribution at bottom
        self.lbl_fyp = QLabel("")
        self.lbl_fyp.setStyleSheet("color:#555; font-size:10px;")
        self.lbl_fyp.setWordWrap(True)
        self.lbl_fyp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_fyp)
        self._refresh_fyp_label()

        return p

    def _right_panel(self):
        p = QFrame(); p.setStyleSheet("background:#101010;")
        lay = QVBoxLayout(p); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self.stack = QStackedWidget()

        # Index 0 – live camera feed
        self.cam_lbl = QLabel("[ INITIALIZING LIVE VIEWPORT ]")
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_lbl.setStyleSheet("background:#050505; color:#666;")
        self.stack.addWidget(self.cam_lbl)

        # Index 1 – 3-D viewer (WebEngine)
        profile = QWebEngineProfile.defaultProfile()
        s = profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

        self.webview = QWebEngineView()
        self.stack.addWidget(self.webview)
        lay.addWidget(self.stack)
        return p

    # ── Helpers ───────────────────────────────────────────────────────────────
    def log(self, msg):
        self.txt.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _refresh_fyp_label(self):
        students = SETTINGS.get("students", [])
        if students:
            parts = [
                f"{s['name']} ({s['roll']})"
                for s in students if s.get("name") or s.get("roll")
            ]
            self.lbl_fyp.setText("FYP: " + " | ".join(parts) if parts else "")
        else:
            self.lbl_fyp.setText("FYP Members name here.....")

    def _refresh_cam_switch_label(self):
        if self.camera_index == 1:
            self.btn_cam_switch.setText("📷 Ext")
            self.btn_cam_switch.setToolTip(
                "Currently: External webcam\nClick to switch to Laptop camera"
            )
        else:
            self.btn_cam_switch.setText("💻 Lap")
            self.btn_cam_switch.setToolTip(
                "Currently: Laptop camera\nClick to switch to External webcam"
            )

    def _update_capture_btn_label(self):
        num  = self.spn_images.value()
        done = self.manual_capture_count
        if done < num:
            self.btn_capture.setText(f"Capture View ({done + 1}/{num})")
        else:
            self.btn_capture.setText("All Views Captured ✔")

    # ── Slots ─────────────────────────────────────────────────────────────────
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
            # Sync spinbox with possibly-updated value
            self.spn_images.blockSignals(True)
            self.spn_images.setValue(SETTINGS.get("num_images", 4))
            self.spn_images.blockSignals(False)
            self._refresh_fyp_label()
            self.log("Settings saved.")

    @pyqtSlot()
    def toggle_mode(self):
        if "Auto" in self.mode_btn.text():
            self.mode_btn.setText("Mode: Manual Scan")
            self.btn_action.setText("Compile Manual Views")
            self.btn_action.setDisabled(True)
            self.btn_capture.setEnabled(True)
            self.manual_capture_count = 0
            self._update_capture_btn_label()
            self.log("Switched to Manual capture mode.")
        else:
            self.mode_btn.setText("Mode: Auto Turntable")
            self.btn_action.setText("Execute Hardware Loop")
            self.btn_action.setEnabled(True)
            self.btn_capture.setDisabled(True)
            self.log("Switched to Auto Turntable mode.")

    @pyqtSlot()
    def toggle_camera(self):
        if self.camera_enabled:
            self._stop_camera_thread()
            self.log("Camera disabled.")
        else:
            self._start_camera_thread()
            if self.stack.currentIndex() == 0:
                self.cam_lbl.setText("[ LIVE VIEWPORT ]")
            self.log("Camera enabled.")

    @pyqtSlot()
    def switch_camera(self):
        was_enabled = self.camera_enabled
        if was_enabled:
            self.camera_thread.stop()
        self.camera_index = 1 - self.camera_index
        SETTINGS["camera_index"] = self.camera_index
        self._refresh_cam_switch_label()
        label = "External webcam" if self.camera_index == 1 else "Laptop camera"
        self.log(f"Switched to {label}.")
        if was_enabled:
            self._start_camera_thread()

    @pyqtSlot()
    def capture_manual(self):
        if self.latest_frame is None:
            self.log("[WARN] No camera frame available yet.")
            return
        idx  = self.manual_capture_count
        name = f"img_{idx}.jpg"
        cv2.imwrite(os.path.join(SCAN_FOLDER, name), self.latest_frame)
        self.log(f"Saved: {name}")
        self.manual_capture_count += 1
        num = self.spn_images.value()
        if self.manual_capture_count >= num:
            self.btn_capture.setText("All Views Captured ✔")
            self.btn_capture.setDisabled(True)
            self.btn_action.setEnabled(True)
            self.log(f"All {num} views captured — click 'Compile Manual Views'.")
        else:
            self._update_capture_btn_label()

    @pyqtSlot()
    def start_scan(self):
        self.btn_action.setDisabled(True)
        self.btn_capture.setDisabled(True)
        self.btn_reprocess.setDisabled(True)

        mode = "Auto Turntable" if "Auto" in self.mode_btn.text() else "Manual Scan"
        self._cam_auto_paused = False

        if mode == "Auto Turntable" and not self.camera_enabled:
            self.log("Enabling camera for Auto Turntable capture.")
            self._start_camera_thread()

        self.scan_thread = HardwareScanThread(
            SETTINGS,
            mode,
            frame_supplier=self.get_latest_frame
        )
        self.scan_thread.log_msg.connect(self.log)
        self.scan_thread.scan_complete.connect(self.show_model)
        self.scan_thread.scan_error.connect(self.on_scan_error)
        self.scan_thread.start()

    @pyqtSlot()
    def reprocess_existing_images(self):
        self.btn_action.setDisabled(True)
        self.btn_capture.setDisabled(True)
        self.btn_reprocess.setDisabled(True)
        self.log("Bypassing camera. Launching compiler with existing local folder files…")
        self._cam_auto_paused = False
        self.scan_thread = HardwareScanThread(SETTINGS, "Reprocess")
        self.scan_thread.log_msg.connect(self.log)
        self.scan_thread.scan_complete.connect(self.show_model)
        self.scan_thread.scan_error.connect(self.on_scan_error)
        self.scan_thread.start()

    @pyqtSlot(str)
    def on_scan_error(self, err_msg):
        self.log(f"ERROR: {err_msg}")
        self.btn_reprocess.setEnabled(True)
        if "Auto" in self.mode_btn.text():
            self.btn_action.setEnabled(True)
        # Restart camera if it was auto-paused
        if self._cam_auto_paused:
            self._cam_auto_paused = False
            self._start_camera_thread()
            self.log("Camera resumed.")

    @pyqtSlot()
    def load_mesh(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load 3D Model", "", "GLB Files (*.glb)"
        )
        if path:
            self.show_model(path)

    @pyqtSlot()
    def back_to_camera(self):
        self.stack.setCurrentIndex(0)
        if self.camera_enabled:
            self.cam_lbl.setText("[ LIVE VIEWPORT ]")
        else:
            self.cam_lbl.setText("[ CAMERA DISABLED ]")
        self.log("Switched back to camera view.")

    @pyqtSlot(str)
    def show_model(self, glb_path):
        import http.server, urllib.parse

        # Restart camera if it was auto-paused during Auto Turntable
        if self._cam_auto_paused:
            self._cam_auto_paused = False
            self._start_camera_thread()
            self.log("Camera resumed.")

        if hasattr(self, '_httpd') and self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass
            self._httpd = None

        try:
            glb_bytes = open(glb_path, "rb").read()
        except Exception as e:
            self.log(f"ERROR reading GLB: {e}")
            return

        # Read local Three.js files from app directory
        js_files = {}  # path-key → bytes
        for js_name in ("three.min.js", "OrbitControls.js", "GLTFLoader.js"):
            js_path = os.path.join(APP_DIR, js_name)
            if os.path.exists(js_path):
                js_files[f"/{js_name}"] = open(js_path, "rb").read()
            else:
                self.log(f"[WARN] Missing {js_name} in app folder. Local viewer may fail.")

        glb_filename = os.path.basename(glb_path)
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>3D Viewer</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{ width:100%; height:100%; background:#1a1a1a; overflow:hidden; }}
    canvas {{ display:block; width:100%; height:100%; }}
    #info {{
      display:none; position:absolute; inset:0;
      color:#999; font:16px sans-serif;
      justify-content:center; align-items:center; text-align:center;
    }}
  </style>
</head>
<body>
  <div id="container"></div>
  <div id="info" style="z-index: 9999;"><p>Loading 3D model…</p></div>

  <script src="/three.min.js"></script>
  <script src="/OrbitControls.js"></script>
  <script src="/GLTFLoader.js"></script>
  <script>
    window.onerror = function(msg, url, line, col, error) {{
      document.getElementById('info').style.display = 'flex';
      document.getElementById('info').innerHTML = '<p style="color:red; font-size:18px; background:rgba(0,0,0,0.8); padding:20px; border-radius:5px;">JS Error: ' + msg + '<br>Line: ' + line + '</p>';
      return false;
    }};
    
    var scene, camera, renderer, controls;

    function init() {{
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x1a1a1a);

      camera = new THREE.PerspectiveCamera(
        45, window.innerWidth / window.innerHeight, 0.01, 1000
      );
      camera.position.set(0, 2, 5);

      renderer = new THREE.WebGLRenderer({{ antialias: true }});
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setPixelRatio(window.devicePixelRatio);
      try {{ renderer.outputEncoding = THREE.sRGBEncoding; }} catch(e) {{}}
      document.getElementById('container').appendChild(renderer.domElement);

      // Lights
      scene.add(new THREE.AmbientLight(0xffffff, 0.8));
      var d1 = new THREE.DirectionalLight(0xffffff, 1.0);
      d1.position.set(5, 10, 7); scene.add(d1);
      var d2 = new THREE.DirectionalLight(0xffffff, 0.5);
      d2.position.set(-5, 5, -7); scene.add(d2);

      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 2.0;

      var loader = new THREE.GLTFLoader();
      loader.load('/model.glb', function(gltf) {{
        var model = gltf.scene;
        scene.add(model);
        var box = new THREE.Box3().setFromObject(model);
        var center = box.getCenter(new THREE.Vector3());
        var size = box.getSize(new THREE.Vector3());
        controls.target.copy(center);
        var maxDim = Math.max(size.x, size.y, size.z);
        camera.position.copy(center);
        camera.position.z += maxDim * 2.5;
        camera.lookAt(center);
        controls.update();
      }}, undefined, function(error) {{
        console.error('GLB load error:', error);
        document.getElementById('info').style.display = 'flex';
        document.getElementById('info').innerHTML = '<p style="color:red; font-size:18px; background:rgba(0,0,0,0.8); padding:20px;">Failed to load GLB: ' + ((error && error.message) ? error.message : error) + '</p>';
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
                    self_h.end_headers(); self_h.wfile.write(html_bytes)
                elif p == "/model.glb":
                    self_h.send_response(200)
                    self_h.send_header("Content-Type", "model/gltf-binary")
                    self_h.send_header("Content-Length", str(len(glb_bytes)))
                    self_h.send_header("Access-Control-Allow-Origin", "*")
                    self_h.end_headers(); self_h.wfile.write(glb_bytes)
                elif p in js_files:
                    data = js_files[p]
                    self_h.send_response(200)
                    self_h.send_header("Content-Type", "application/javascript")
                    self_h.send_header("Content-Length", str(len(data)))
                    self_h.end_headers(); self_h.wfile.write(data)
                else:
                    self_h.send_response(404); self_h.end_headers()

        # SUPER IMPORTANT: Use ThreadingHTTPServer so browser parallel downloads don't deadlock!
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

        viewer_url = f"http://127.0.0.1:{port}/"
        self.webview.setUrl(QUrl(viewer_url))
        self.stack.setCurrentIndex(1)
        self.log(f"Viewer active: {glb_filename}")
        self.log(f'<a href="{viewer_url}" style="color:#64B5F6; text-decoration:underline;">&#128279; CLICK HERE TO OPEN 3D VIEWER IN BROWSER</a>')

        import webbrowser
        try:
            webbrowser.open(viewer_url)
        except Exception as e:
            self.log(f"Could not auto-open browser: {e}")

        self.btn_reprocess.setEnabled(True)
        if "Auto" in self.mode_btn.text():
            self.btn_action.setEnabled(True)

    def closeEvent(self, event):
        if self.camera_enabled:
            self.camera_thread.stop()
        if hasattr(self, '_httpd') and self._httpd:
            self._httpd.shutdown()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    w   = ModernScannerApp()
    w.show()
    sys.exit(app.exec())