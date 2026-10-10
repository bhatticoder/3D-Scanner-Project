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
    QHeaderView, QFormLayout, QCheckBox, QProgressBar
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


# ── Universal 3D Converter Integration ─────────────────────────────────────────
from converter import convert_model_to_all_formats, open_in_blender, find_blender


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


# ── Image-to-Model Thread (Tripo V3 API) ─────────────────────────────────────
class ImageToModelThread(QThread):
    """Generates a 3D model from a single image using Tripo V3 image-to-model API."""
    log_msg       = pyqtSignal(str)
    progress_pct  = pyqtSignal(int)
    scan_complete = pyqtSignal(str)
    scan_error    = pyqtSignal(str)

    def __init__(self, image_path, settings, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.settings   = settings

    def run(self):
        try:
            api_key = self.settings.get("tripo_api_key", "")
            if not api_key:
                raise RuntimeError("No Tripo API key configured. Go to Settings ⚙ to add your key.")

            h = {"Authorization": f"Bearer {api_key}"}
            base_url = "https://openapi.tripo3d.ai"

            # Step 1: Upload the image
            self.log_msg.emit("📤 Uploading image to Tripo3D cloud...")
            self.progress_pct.emit(10)

            with open(self.image_path, "rb") as f:
                fname = os.path.basename(self.image_path)
                ext = os.path.splitext(fname)[1].lower()
                mime = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp",
                    ".bmp": "image/bmp"
                }.get(ext, "image/jpeg")

                r = requests.post(
                    f"{base_url}/v3/files",
                    headers=h,
                    files={"file": (fname, f, mime)}
                )
                r.raise_for_status()
                res = r.json()

                if res.get("code") != 0:
                    raise RuntimeError(f"Upload failed: {res.get('message', 'Unknown error')}")

                file_token = res["data"]["file_token"]
                self.log_msg.emit(f"✅ Image uploaded. Token: {file_token[:20]}...")

            # Step 2: Create image-to-model task
            self.log_msg.emit("🔨 Creating 3D generation task (image-to-model)...")
            self.progress_pct.emit(25)

            payload = {
                "model_version": "v2.5-20250123",
                "file": {
                    "type": ext.lstrip(".") if ext.lstrip(".") in ("jpg","jpeg","png","webp","bmp") else "jpg",
                    "file_token": file_token
                },
                "texture": True,
                "pbr": True
            }

            r = requests.post(
                f"{base_url}/v3/generation/image-to-model",
                headers={**h, "Content-Type": "application/json"},
                json=payload
            )
            r.raise_for_status()
            task_res = r.json()

            if task_res.get("code") != 0:
                raise RuntimeError(f"Task creation failed: {task_res.get('message', 'Unknown error')}")

            task_id = task_res["data"]["task_id"]
            self.log_msg.emit(f"🆔 Task created: {task_id}")

            # Step 3: Poll for completion
            self.log_msg.emit("⏳ Waiting for 3D model generation...")
            self.progress_pct.emit(35)

            start_time = time.time()
            timeout = 600  # 10 minutes max
            while True:
                if time.time() - start_time > timeout:
                    raise TimeoutError("3D generation timed out after 10 minutes.")

                r = requests.get(
                    f"{base_url}/v3/tasks/{task_id}",
                    headers=h
                )
                r.raise_for_status()
                d = r.json()["data"]

                status = d["status"]
                progress = d.get("progress", 0)

                # Map progress to our bar (35-85%)
                mapped_pct = 35 + int(progress * 0.5)
                self.progress_pct.emit(min(mapped_pct, 85))

                self.log_msg.emit(f"   Status: {status.upper()} | Progress: {progress}%")

                if status == "success":
                    out = d.get("output", {})
                    model_url = out.get("model_url")
                    if not model_url:
                        raise RuntimeError("Task succeeded but no model_url in output.")
                    break
                elif status in ("failed", "cancelled"):
                    err_msg = d.get("error_message", "Unknown error")
                    err_code = d.get("error_code", "N/A")
                    raise RuntimeError(f"Generation {status}: [{err_code}] {err_msg}")

                time.sleep(3)

            # Step 4: Download the model
            self.log_msg.emit("📥 Downloading 3D model...")
            self.progress_pct.emit(90)

            r = requests.get(model_url, stream=True)
            r.raise_for_status()

            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            clean_name = os.path.splitext(os.path.basename(self.image_path))[0]
            final_path = os.path.join(export_dir, f"{clean_name}_{timestamp}.glb")

            with open(final_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

            self.settings["output_path"] = final_path
            self.log_msg.emit(f"✅ Model saved: {final_path}")

            # Step 5: Auto-export additional formats (OBJ, STL, FBX, BLEND)
            self.progress_pct.emit(95)
            self._export_formats(final_path, task_id=task_id)

            self.progress_pct.emit(100)
            self.scan_complete.emit(final_path)

        except Exception as e:
            self.scan_error.emit(str(e))

    def _export_formats(self, glb_path, task_id=None):
        """Export to OBJ, STL, FBX, and Blender .blend for universal compatibility."""
        try:
            self.log_msg.emit("🔄 Generating universal exports (OBJ, STL, FBX, BLEND)...")
            clean_name = os.path.splitext(os.path.basename(glb_path))[0]
            convert_model_to_all_formats(
                glb_path,
                export_dir=os.path.dirname(glb_path),
                base_name=clean_name,
                tripo_task_id=task_id,
                tripo_api_key=self.settings.get("tripo_api_key"),
                log_fn=lambda m: self.log_msg.emit(m)
            )
            self.log_msg.emit("✅ Universal exports generated: GLB, OBJ, STL, FBX, .BLEND")
        except Exception as e:
            self.log_msg.emit(f"[WARN] Multi-format export warning: {e}")


# ── Multiview-to-Model Thread (Tripo V3 API) ─────────────────────────────────
class MultiviewToModelThread(QThread):
    """Generates a 3D model from multiple perspective photos using Tripo V3 multiview-to-model API."""
    log_msg       = pyqtSignal(str)
    progress_pct  = pyqtSignal(int)
    scan_complete = pyqtSignal(str)
    scan_error    = pyqtSignal(str)

    def __init__(self, image_paths, settings, base_name="multiview_model", parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.settings    = settings
        self.base_name   = base_name

    def run(self):
        try:
            api_key = self.settings.get("tripo_api_key", "")
            if not api_key:
                raise RuntimeError("No Tripo API key configured. Go to Settings ⚙ to add your key.")

            from pipeline import generate_from_multiview_images
            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            full_base = f"{self.base_name}_{timestamp}"

            self.log_msg.emit(f"📤 Uploading {len(self.image_paths)} images to Tripo3D cloud...")
            self.progress_pct.emit(15)

            glb_path, task_id = generate_from_multiview_images(
                self.image_paths,
                api_key,
                export_dir,
                base_name=full_base,
                log_fn=lambda m: self.log_msg.emit(m)
            )
            self.progress_pct.emit(85)

            self.log_msg.emit("🔄 Generating universal exports (OBJ, STL, FBX, BLEND)...")
            convert_model_to_all_formats(
                glb_path,
                export_dir=export_dir,
                base_name=full_base,
                tripo_task_id=task_id,
                tripo_api_key=api_key,
                log_fn=lambda m: self.log_msg.emit(m)
            )

            self.settings["output_path"] = glb_path
            self.progress_pct.emit(100)
            self.scan_complete.emit(glb_path)
        except Exception as e:
            self.scan_error.emit(str(e))


# ── Blender Export Thread ─────────────────────────────────────────────────────
class BlenderExportThread(QThread):
    """Converts a GLB model to FBX, OBJ, STL, GLB, and native Blender .blend."""
    log_msg       = pyqtSignal(str)
    export_done   = pyqtSignal(str)
    export_error  = pyqtSignal(str)

    def __init__(self, glb_path, export_format, settings, parent=None):
        super().__init__(parent)
        self.glb_path      = glb_path
        self.export_format = export_format  # "FBX", "OBJ", "GLB", "STL", "BLEND"
        self.settings      = settings

    def run(self):
        try:
            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(self.glb_path))[0]
            fmt_upper = self.export_format.upper()

            self.log_msg.emit(f"🔄 Exporting to {fmt_upper} for Blender...")

            results = convert_model_to_all_formats(
                self.glb_path,
                export_dir=export_dir,
                base_name=f"{base_name}_{timestamp}",
                tripo_api_key=self.settings.get("tripo_api_key"),
                log_fn=lambda m: self.log_msg.emit(m)
            )

            target_key = fmt_upper.lower()
            if target_key in results:
                self.export_done.emit(results[target_key])
            else:
                self.export_done.emit(results.get("blend", results.get("glb", self.glb_path)))

        except Exception as e:
            self.export_error.emit(str(e))


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
                    "https://openapi.tripo3d.ai/v3/files", 
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
                
                # V3: The response key changed from image_token back to file_token
                token = data_block.get("file_token")
                if not token:
                    raise KeyError(f"Could not locate an image token. Keys available: {list(data_block.keys())}")
                    
                tokens.append(token)

        # Assemble your explicit payload mappings with structural validation
        payload = {
            "model_version": "v2.5-20250123",
            "files": [
                {"type": "jpg", "file_token": tokens[0], "orientation": "front"},
                {"type": "jpg", "file_token": tokens[1], "orientation": "right"}, 
                {"type": "jpg", "file_token": tokens[2], "orientation": "back"}, 
                {"type": "jpg", "file_token": tokens[3], "orientation": "left"},  
            ]
        }
        
        r = requests.post("https://openapi.tripo3d.ai/v3/generation/multiview-to-model", headers={**h, "Content-Type": "application/json"}, json=payload)
        r.raise_for_status()
        
        task_json = r.json()
        if task_json.get("code") != 0:
            raise RuntimeError(f"Tripo3D Task Creation Error: {task_json.get('msg')}")
            
        return task_json["data"]["task_id"]

    def _poll(self, tid):
        while True:
            r = requests.get(f"https://openapi.tripo3d.ai/v3/tasks/{tid}", headers={"Authorization":f"Bearer {self.settings['tripo_api_key']}"})
            r.raise_for_status()
            d = r.json()["data"]
            self.log_msg.emit(f"Status: {d['status'].upper()}")
            if d["status"] == "success":
                out = d.get("output",{})
                return out[0].get("model_url") if isinstance(out,list) else out.get("model_url")
            if d["status"] in ("failed","cancelled"): raise RuntimeError(f"Tripo3D processing failed with status {d['status']}: {d.get('error_message', 'Unknown Error')}")
            time.sleep(3)

    def _dl(self, url):
            r = requests.get(url, stream=True)
            r.raise_for_status()
            
            export_dir = self.settings.get("export_dir", DEFAULT_EXPORT_DIR)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            final_path = os.path.join(export_dir, f"scanned_model_{timestamp}.glb")
            
            with open(final_path, "wb") as f:
                for chunk in r.iter_content(8192): 
                    f.write(chunk)
            
            self.settings["output_path"] = final_path
            
            # Automatically export ALL formats: GLB, OBJ, STL, FBX, BLEND
            try:
                self.log_msg.emit("🔄 Generating universal exports (OBJ, STL, FBX, BLEND)...")
                convert_model_to_all_formats(
                    final_path,
                    export_dir=export_dir,
                    base_name=f"scanned_model_{timestamp}",
                    tripo_api_key=self.settings.get("tripo_api_key"),
                    log_fn=lambda m: self.log_msg.emit(m)
                )
                self.log_msg.emit("✅ Universal exports generated: GLB, OBJ, STL, FBX, .BLEND")
            except Exception as e:
                self.log_msg.emit(f"[WARN] Universal format export warning: {e}")


# ── Main Window ───────────────────────────────────────────────────────────────
class ModernScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Object Scanner & Reconstruction Studio")
        self.resize(1200, 740)
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
            QProgressBar {
                background:#222; border:1px solid #444; border-radius:4px;
                text-align:center; color:#fff; font-weight:bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00BCD4, stop:1 #2196F3);
                border-radius:3px;
            }
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
        self._current_model_path        = None   # Track loaded model for export
        self._labels_visible            = True    # Toggle labels on/off

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
        p = QFrame(); p.setFixedWidth(320)
        p.setStyleSheet("background:#1a1a1a;")
        lay = QVBoxLayout(p); lay.setContentsMargins(16, 16, 16, 16)

        # Title row + ⚙ gear button
        title_row = QHBoxLayout()
        t = QLabel("3D OBJECT SCANNER")
        f = QFont(); f.setPointSize(13); f.setBold(True); t.setFont(f)
        t.setStyleSheet("color:#00BCD4;")
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
        lay.addSpacing(8)

        # ── Progress Bar ──────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)
        lay.addSpacing(4)

        # ── AI 3D Reconstruction from Photos ─────────────────────────────────
        gen_box = QGroupBox("✨ AI 3D Reconstruction")
        gen_box.setStyleSheet("""
            QGroupBox { 
                border: 1px solid #00BCD4; margin-top:1ex; 
                font-weight:bold; color:#00BCD4; 
                padding-top: 14px;
            }
        """)
        gen_lay = QVBoxLayout(gen_box)

        self.btn_gen_image = QPushButton("📸  Single Photo → 3D")
        self.btn_gen_image.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00897B, stop:1 #00BCD4);
                color: #fff; font-size: 11px; padding: 7px;
                border-radius: 5px;
            }
            QPushButton:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ACC1, stop:1 #26C6DA);
            }
        """)
        self.btn_gen_image.clicked.connect(self.generate_from_image)
        gen_lay.addWidget(self.btn_gen_image)

        self.btn_gen_multi = QPushButton("🖼️  Multiple Photos (Multiview)")
        self.btn_gen_multi.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00695C, stop:1 #00897B);
                color: #fff; font-size: 11px; padding: 7px;
                border-radius: 5px;
            }
            QPushButton:hover { background: #009688; }
        """)
        self.btn_gen_multi.clicked.connect(self.generate_from_multiple_images)
        gen_lay.addWidget(self.btn_gen_multi)

        self.btn_gen_folder = QPushButton("📁  Folder of Photos → 3D")
        self.btn_gen_folder.setStyleSheet("""
            QPushButton { 
                background: #37474F; color: #fff; font-size: 11px; padding: 6px;
                border-radius: 5px;
            }
            QPushButton:hover { background: #455A64; }
        """)
        self.btn_gen_folder.clicked.connect(self.generate_from_folder)
        gen_lay.addWidget(self.btn_gen_folder)

        self.lbl_selected_img = QLabel("Select any photo(s) to reconstruct")
        self.lbl_selected_img.setStyleSheet("color:#666; font-size:10px;")
        self.lbl_selected_img.setWordWrap(True)
        gen_lay.addWidget(self.lbl_selected_img)

        lay.addWidget(gen_box)
        lay.addSpacing(6)

        # Mode toggle
        self.mode_btn = QPushButton("Mode: Auto Turntable")
        self.mode_btn.setStyleSheet("background:#333;")
        self.mode_btn.clicked.connect(self.toggle_mode)
        lay.addWidget(self.mode_btn)
        lay.addSpacing(4)

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
        lay.addSpacing(4)

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
        lay.addSpacing(4)

        # Re-process
        self.btn_reprocess = QPushButton("Re-Process Existing Images")
        self.btn_reprocess.setStyleSheet("background:#2e7d32;")
        self.btn_reprocess.clicked.connect(self.reprocess_existing_images)
        lay.addWidget(self.btn_reprocess)
        lay.addSpacing(4)

        # Load GLB
        self.btn_load = QPushButton("Load External .GLB Mesh")
        self.btn_load.setStyleSheet("background:#444;")
        self.btn_load.clicked.connect(self.load_mesh)
        lay.addWidget(self.btn_load)
        lay.addSpacing(4)

        # View Scanned Model button
        self.btn_view_model = QPushButton("🌐  View Scanned 3D Model")
        self.btn_view_model.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00838F, stop:1 #00ACC1);
                color: #fff; font-weight: bold; font-size: 11px; padding: 7px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #26C6DA; }
        """)
        self.btn_view_model.setToolTip("Directly load and view the current 3D model in the interactive viewer")
        self.btn_view_model.clicked.connect(self.view_loaded_model)
        lay.addWidget(self.btn_view_model)
        lay.addSpacing(4)

        # ── Export to Blender Section ─────────────────────────────────────────
        export_box = QGroupBox("📦 Export to Blender")
        export_box.setStyleSheet("""
            QGroupBox { 
                border: 1px solid #FF9800; margin-top:1ex;
                font-weight:bold; color:#FF9800;
                padding-top: 14px;
            }
        """)
        exp_lay = QVBoxLayout(export_box)

        btn_row = QHBoxLayout()
        self.btn_export_fbx = QPushButton("FBX")
        self.btn_export_fbx.setStyleSheet("background:#E65100; font-size:11px; padding:5px;")
        self.btn_export_fbx.setToolTip("Export as FBX — best for Blender & animation")
        self.btn_export_fbx.clicked.connect(lambda: self.export_for_blender("FBX"))

        self.btn_export_obj = QPushButton("OBJ")
        self.btn_export_obj.setStyleSheet("background:#BF360C; font-size:11px; padding:5px;")
        self.btn_export_obj.setToolTip("Export as OBJ — universal 3D format")
        self.btn_export_obj.clicked.connect(lambda: self.export_for_blender("OBJ"))

        self.btn_export_stl = QPushButton("STL")
        self.btn_export_stl.setStyleSheet("background:#8D6E63; font-size:11px; padding:5px;")
        self.btn_export_stl.setToolTip("Export as STL — for 3D printing")
        self.btn_export_stl.clicked.connect(lambda: self.export_for_blender("STL"))

        self.btn_export_glb = QPushButton("GLB")
        self.btn_export_glb.setStyleSheet("background:#546E7A; font-size:11px; padding:5px;")
        self.btn_export_glb.setToolTip("Copy GLB to export folder")
        self.btn_export_glb.clicked.connect(lambda: self.export_for_blender("GLB"))

        self.btn_export_blend = QPushButton("BLEND")
        self.btn_export_blend.setStyleSheet("background:#F57C00; font-size:11px; padding:5px; font-weight:bold;")
        self.btn_export_blend.setToolTip("Generate Native Blender .blend Master Scene")
        self.btn_export_blend.clicked.connect(lambda: self.export_for_blender("BLEND"))

        btn_row.addWidget(self.btn_export_fbx)
        btn_row.addWidget(self.btn_export_obj)
        btn_row.addWidget(self.btn_export_stl)
        btn_row.addWidget(self.btn_export_glb)
        btn_row.addWidget(self.btn_export_blend)
        exp_lay.addLayout(btn_row)

        self.btn_open_blender = QPushButton("🚀  Open in Blender 5.2")
        self.btn_open_blender.setStyleSheet("""
            QPushButton {
                background: #D84315; color:#fff; font-size:11px; font-weight:bold;
                padding:6px; border-radius:4px;
            }
            QPushButton:hover { background: #BF360C; }
        """)
        self.btn_open_blender.setToolTip("Open the current 3D model directly inside Blender")
        self.btn_open_blender.clicked.connect(self.open_current_in_blender)
        exp_lay.addWidget(self.btn_open_blender)

        self.lbl_export_status = QLabel("Load or generate a model first")
        self.lbl_export_status.setStyleSheet("color:#666; font-size:10px;")
        self.lbl_export_status.setWordWrap(True)
        exp_lay.addWidget(self.lbl_export_status)

        lay.addWidget(export_box)
        lay.addSpacing(4)

        # ── Label Toggle & Back ───────────────────────────────────────────────
        ctrl_row = QHBoxLayout()

        self.btn_toggle_labels = QPushButton("🏷  Labels: ON")
        self.btn_toggle_labels.setStyleSheet("background:#37474F; font-size:11px;")
        self.btn_toggle_labels.clicked.connect(self.toggle_labels)
        ctrl_row.addWidget(self.btn_toggle_labels)

        self.btn_back_cam = QPushButton("🔙  Camera")
        self.btn_back_cam.setStyleSheet("background:#0d47a1; font-size:11px;")
        self.btn_back_cam.clicked.connect(self.back_to_camera)
        ctrl_row.addWidget(self.btn_back_cam)

        lay.addLayout(ctrl_row)
        lay.addSpacing(6)

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
        lay.addSpacing(6)

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

    # ── AI 3D Reconstruction from Photos ─────────────────────────────────
    @pyqtSlot()
    def generate_from_image(self):
        """Pick a single photo and reconstruct 3D model."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo for 3D Generation", "",
            "Images (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*)"
        )
        if not path:
            return

        self.lbl_selected_img.setText(f"📁 {os.path.basename(path)}")
        self.log(f"Selected single photo: {path}")

        self._set_gen_buttons_state(False, "⏳ Generating...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.img_thread = ImageToModelThread(path, SETTINGS, self)
        self.img_thread.log_msg.connect(self.log)
        self.img_thread.progress_pct.connect(self.progress_bar.setValue)
        self.img_thread.scan_complete.connect(self._on_gen_complete)
        self.img_thread.scan_error.connect(self._on_gen_error)
        self.img_thread.start()

    @pyqtSlot()
    def generate_from_multiple_images(self):
        """Pick multiple perspective photos (front, right, back, left) for multiview reconstruction."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select 2-4 Perspective Photos", "",
            "Images (*.jpg *.jpeg *.png *.webp *.bmp);;All Files (*)"
        )
        if not paths:
            return

        self.lbl_selected_img.setText(f"📁 {len(paths)} photos selected")
        self.log(f"Selected {len(paths)} photos for multiview reconstruction.")

        self._set_gen_buttons_state(False, "⏳ Generating Multiview...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.multi_thread = MultiviewToModelThread(paths, SETTINGS, base_name="multiview_model", parent=self)
        self.multi_thread.log_msg.connect(self.log)
        self.multi_thread.progress_pct.connect(self.progress_bar.setValue)
        self.multi_thread.scan_complete.connect(self._on_gen_complete)
        self.multi_thread.scan_error.connect(self._on_gen_error)
        self.multi_thread.start()

    @pyqtSlot()
    def generate_from_folder(self):
        """Select a folder of photos for automated multiview reconstruction."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder of Photos")
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
        self.lbl_selected_img.setText(f"📁 {base_name} ({len(found)} photos)")
        self.log(f"Found {len(found)} photos in '{folder}'. Starting multiview reconstruction...")

        self._set_gen_buttons_state(False, "⏳ Processing Folder...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.multi_thread = MultiviewToModelThread(found, SETTINGS, base_name=base_name, parent=self)
        self.multi_thread.log_msg.connect(self.log)
        self.multi_thread.progress_pct.connect(self.progress_bar.setValue)
        self.multi_thread.scan_complete.connect(self._on_gen_complete)
        self.multi_thread.scan_error.connect(self._on_gen_error)
        self.multi_thread.start()

    def _set_gen_buttons_state(self, enabled, status_text=None):
        self.btn_gen_image.setEnabled(enabled)
        self.btn_gen_multi.setEnabled(enabled)
        self.btn_gen_folder.setEnabled(enabled)
        if enabled:
            self.btn_gen_image.setText("📸  Single Photo → 3D")
            self.btn_gen_multi.setText("🖼️  Multiple Photos (Multiview)")
            self.btn_gen_folder.setText("📁  Folder of Photos → 3D")
        elif status_text:
            self.btn_gen_image.setText(status_text)

    @pyqtSlot(str)
    def _on_gen_complete(self, glb_path):
        self._set_gen_buttons_state(True)
        self.progress_bar.setValue(100)
        self.log("🎉 3D model generation and multi-format conversion complete!")
        self.show_model(glb_path)

    @pyqtSlot(str)
    def _on_gen_error(self, err):
        self._set_gen_buttons_state(True)
        self.progress_bar.setVisible(False)
        self.log(f"❌ Generation error: {err}")
        QMessageBox.critical(self, "Generation Error", err)

    @pyqtSlot()
    def open_current_in_blender(self):
        """Open the current model or its .blend master scene in Blender."""
        if not self._current_model_path or not os.path.exists(self._current_model_path):
            QMessageBox.warning(self, "No Model", "No 3D model loaded. Generate or load a model first.")
            return

        export_dir = SETTINGS.get("export_dir", DEFAULT_EXPORT_DIR)
        base_name = os.path.splitext(os.path.basename(self._current_model_path))[0]
        blend_path = os.path.join(export_dir, f"{base_name}.blend")

        if not os.path.exists(blend_path):
            self.log("Creating native Blender master workspace first...")
            self.export_for_blender("BLEND")
            return

        self.log(f"🚀 Opening Blender with {blend_path}...")
        open_in_blender(blend_path)

    # ── Export to Blender ─────────────────────────────────────────────────────
    @pyqtSlot()
    def export_for_blender(self, fmt):
        """Export the current model in the specified format for Blender."""
        if not self._current_model_path or not os.path.exists(self._current_model_path):
            QMessageBox.warning(self, "No Model", "No 3D model loaded. Generate or load a model first.")
            return

        if fmt == "GLB":
            # Just copy the GLB to exports
            export_dir = SETTINGS.get("export_dir", DEFAULT_EXPORT_DIR)
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(export_dir, f"blender_export_{timestamp}.glb")
            import shutil
            shutil.copy2(self._current_model_path, dest)
            self.log(f"✅ GLB copied to: {dest}")
            self.lbl_export_status.setText(f"✅ Exported: {os.path.basename(dest)}")
            self.lbl_export_status.setStyleSheet("color:#4CAF50; font-size:10px;")
            
            # Open the folder
            os.startfile(export_dir)
            return

        self.log(f"Starting {fmt} export for Blender...")
        self.lbl_export_status.setText(f"⏳ Exporting {fmt}...")
        self.lbl_export_status.setStyleSheet("color:#FF9800; font-size:10px;")

        self._export_thread = BlenderExportThread(
            self._current_model_path, fmt, SETTINGS, self
        )
        self._export_thread.log_msg.connect(self.log)
        self._export_thread.export_done.connect(self._on_export_done)
        self._export_thread.export_error.connect(self._on_export_error)
        self._export_thread.start()

    @pyqtSlot(str)
    def _on_export_done(self, path):
        self.lbl_export_status.setText(f"✅ {os.path.basename(path)}")
        self.lbl_export_status.setStyleSheet("color:#4CAF50; font-size:10px;")
        self.log(f"🎉 Export complete: {path}")
        
        # Open the export folder
        export_dir = os.path.dirname(path)
        os.startfile(export_dir)

    @pyqtSlot(str)
    def _on_export_error(self, err):
        self.lbl_export_status.setText(f"❌ Export failed")
        self.lbl_export_status.setStyleSheet("color:#F44336; font-size:10px;")
        self.log(f"❌ Export error: {err}")

    # ── Label Toggle ──────────────────────────────────────────────────────────
    @pyqtSlot()
    def toggle_labels(self):
        self._labels_visible = not self._labels_visible
        state = "ON" if self._labels_visible else "OFF"
        self.btn_toggle_labels.setText(f"🏷  Labels: {state}")
        # Send JS command to toggle labels in the viewer
        if self.stack.currentIndex() == 1:
            self.webview.page().runJavaScript(
                f"if(window.toggleLabels) window.toggleLabels({str(self._labels_visible).lower()});"
            )
        self.log(f"Labels: {state}")

    # ── Scan actions ──────────────────────────────────────────────────────────
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
    def view_loaded_model(self):
        target_path = self._current_model_path
        if not target_path or not os.path.exists(target_path):
            default_path = os.path.join(APP_DIR, "scanned_object.glb")
            if os.path.exists(default_path):
                target_path = default_path
        if target_path and os.path.exists(target_path):
            self.show_model(target_path)
            self.log(f"Displaying 3D model: {os.path.basename(target_path)}")
        else:
            self.log("ERROR: No 3D model found to display. Generate or load a model first.")

    # Backwards compatibility alias
    def view_civis_model(self):
        self.view_loaded_model()

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

        self._current_model_path = glb_path
        self.lbl_export_status.setText(f"Ready: {os.path.basename(glb_path)}")
        self.lbl_export_status.setStyleSheet("color:#4CAF50; font-size:10px;")

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
  <title>3D Model Viewer — {glb_filename}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{ width:100%; height:100%; background:#0d1117; overflow:hidden; font-family:'Segoe UI',sans-serif; }}
    canvas {{ display:block; width:100%; height:100%; }}
    #info {{
      display:none; position:absolute; inset:0;
      color:#999; font:16px sans-serif;
      justify-content:center; align-items:center; text-align:center;
    }}
    
    /* ── 3D Label Styles ── */
    .label-3d {{
      position: absolute;
      pointer-events: none;
      transform: translate(-50%, -100%);
      z-index: 100;
      transition: opacity 0.3s ease;
    }}
    .label-3d.hidden {{
      opacity: 0 !important;
      pointer-events: none;
    }}
    .label-dot {{
      width: 10px; height: 10px;
      border-radius: 50%;
      margin: 0 auto 4px;
      box-shadow: 0 0 8px currentColor, 0 0 16px currentColor;
      animation: pulse 2s ease-in-out infinite;
    }}
    .label-line {{
      width: 2px; height: 26px;
      margin: 0 auto;
      background: linear-gradient(to bottom, currentColor, transparent);
    }}
    .label-card {{
      background: rgba(13, 17, 23, 0.92);
      border: 1px solid;
      border-radius: 8px;
      padding: 5px 10px;
      white-space: nowrap;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }}
    .label-name {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }}
    .label-desc {{
      font-size: 9px;
      opacity: 0.8;
      margin-top: 2px;
    }}
    
    /* ── Header Bar ── */
    #header {{
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 44px;
      background: linear-gradient(180deg, rgba(13,17,23,0.95) 0%, rgba(13,17,23,0) 100%);
      display: flex;
      align-items: center;
      padding: 0 20px;
      z-index: 200;
    }}
    #header h1 {{
      font-size: 14px;
      font-weight: 600;
      color: #00BCD4;
      letter-spacing: 0.5px;
    }}
    #header .dims {{
      margin-left: auto;
      font-size: 12px;
      color: #00E676;
      font-weight: 600;
      letter-spacing: 0.5px;
      background: rgba(0, 230, 118, 0.1);
      padding: 4px 10px;
      border-radius: 4px;
      border: 1px solid rgba(0, 230, 118, 0.2);
    }}
    
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); opacity:1; }}
      50% {{ transform: scale(1.4); opacity:0.6; }}
    }}
  </style>
</head>
<body>
  <div id="header">
    <h1 id="model-title">{glb_filename}</h1>
    <span class="dims" id="model-dims">Measuring dimensions…</span>
  </div>
  <div id="container"></div>
  <div id="info" style="z-index: 9999;"><p>Loading 3D model…</p></div>
  <div id="labels-container"></div>

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
    var labelElements = [];
    var labelPositions = [];
    var labelsVisible = true;

    function createDimensionLabels(box, center, size) {{
      var container = document.getElementById('labels-container');
      container.innerHTML = '';
      labelElements = [];
      labelPositions = [];

      var wCm = (size.x * 100).toFixed(1);
      var lCm = (size.y * 100).toFixed(1);
      var hCm = (size.z * 100).toFixed(1);

      var markers = [
        {{ name: 'Height (Top)', desc: hCm + ' cm', pos: new THREE.Vector3(center.x, box.max.y, center.z), color: '#00BCD4' }},
        {{ name: 'Width (X-Span)', desc: wCm + ' cm', pos: new THREE.Vector3(box.max.x, center.y, center.z), color: '#FF9800' }},
        {{ name: 'Depth (Z-Span)', desc: lCm + ' cm', pos: new THREE.Vector3(center.x, center.y, box.max.z), color: '#4CAF50' }},
        {{ name: 'Origin Center', desc: 'Anchor Point', pos: center.clone(), color: '#E91E63' }}
      ];

      markers.forEach(function(m) {{
        var el = document.createElement('div');
        el.className = 'label-3d';
        el.style.color = m.color;
        el.innerHTML = 
          '<div class="label-card" style="border-color:' + m.color + '">' +
            '<div class="label-name" style="color:' + m.color + '">' + m.name + '</div>' +
            '<div class="label-desc">' + m.desc + '</div>' +
          '</div>' +
          '<div class="label-line"></div>' +
          '<div class="label-dot" style="background:' + m.color + '; color:' + m.color + '"></div>';
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
        
        var x = (pos.x * 0.5 + 0.5) * width;
        var y = (-pos.y * 0.5 + 0.5) * height;
        
        if (pos.z > 1) {{
          labelElements[i].style.opacity = '0';
        }} else {{
          labelElements[i].style.opacity = labelsVisible ? '1' : '0';
          labelElements[i].style.left = x + 'px';
          labelElements[i].style.top = y + 'px';
        }}
      }}
    }}

    // Global toggle function callable from Python
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
      scene.background = new THREE.Color(0x0d1117);

      camera = new THREE.PerspectiveCamera(
        45, window.innerWidth / window.innerHeight, 0.01, 1000
      );
      camera.position.set(0, 2, 5);

      renderer = new THREE.WebGLRenderer({{ antialias: true }});
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setPixelRatio(window.devicePixelRatio);
      try {{ renderer.outputEncoding = THREE.sRGBEncoding; }} catch(e) {{}}
      document.getElementById('container').appendChild(renderer.domElement);

      // Studio 3-point lighting
      scene.add(new THREE.AmbientLight(0xffffff, 0.6));
      
      var d1 = new THREE.DirectionalLight(0xffffff, 1.0);
      d1.position.set(5, 10, 7); scene.add(d1);
      var d2 = new THREE.DirectionalLight(0xffffff, 0.5);
      d2.position.set(-5, 5, -7); scene.add(d2);
      var d3 = new THREE.DirectionalLight(0x00BCD4, 0.3);
      d3.position.set(0, -3, 5); scene.add(d3);

      // Subtle ground grid
      var gridHelper = new THREE.GridHelper(4, 20, 0x1a2332, 0x111827);
      scene.add(gridHelper);

      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 1.5;

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

        // Dynamically calculate and display real dimensions in cm
        var dimsEl = document.getElementById('model-dims');
        if (dimsEl) {{
          var wCm = (size.x * 100).toFixed(1);
          var lCm = (size.y * 100).toFixed(1);
          var hCm = (size.z * 100).toFixed(1);
          dimsEl.textContent = wCm + ' × ' + lCm + ' × ' + hCm + ' cm';
        }}

        // Create bounding measurement annotations
        createDimensionLabels(box, center, size);

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