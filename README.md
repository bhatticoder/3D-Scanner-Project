# 🧊 3D Scanner & Open-Source Image-to-3D Generator

A complete, open-source pipeline for generating **Blender-ready 3D models from any image** — running **100% locally** on your own laptop. No API keys. No cloud. No payments.

## ✨ Features

- 📷 **Image → 3D Model**: Drop any image, get a full 3D model in seconds
- 🆓 **Completely Free**: Uses [TripoSR](https://github.com/VAST-AI-Research/TripoSR) (MIT licensed by StabilityAI + Tripo)
- 💻 **Runs Locally**: GPU recommended (4GB+ VRAM), but also works on CPU
- 📦 **All Formats**: Automatically exports GLB, OBJ, STL, FBX, and native `.blend`
- 🎬 **Blender Ready**: Studio-lit `.blend` scene with camera, lighting, and materials
- 📡 **3D Scanner Hardware**: PyQt6 desktop app with Arduino turntable support

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Install PyTorch (pick your CUDA version from https://pytorch.org)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install project dependencies
pip install -r requirements.txt
```

### 2. Generate a 3D Model from an Image

```bash
# Basic usage — just give it any image!
python pipeline.py --image photo.jpg --name my_object

# High quality mesh
python pipeline.py --image photo.jpg --name my_object --resolution 512

# Run on CPU (no GPU needed, just slower)
python pipeline.py --image photo.jpg --name my_object --device cpu

# Process a folder of images
python pipeline.py --folder my_photos/ --name scanned_thing

# Convert existing GLB to all formats
python pipeline.py --glb model.glb --name my_model

# Open in Blender after generation
python pipeline.py --image photo.jpg --name my_object --blender
```

### 3. Output

All exported files are saved to `exports/` by default:

| Format | File | Use Case |
|--------|------|----------|
| GLB | `my_object.glb` | Web viewers, Three.js, AR/VR |
| OBJ | `my_object.obj` | Universal 3D format |
| STL | `my_object.stl` | 3D printing |
| FBX | `my_object.fbx` | Game engines (Unity, Unreal) |
| BLEND | `my_object.blend` | Blender editing (with studio scene) |

## 🛠️ Configuration

Edit `config.json` to customize default settings:

```json
{
    "mesh_resolution": 256,
    "device": "auto",
    "foreground_ratio": 0.85,
    "remove_background": true,
    "export_dir": "exports"
}
```

| Setting | Values | Description |
|---------|--------|-------------|
| `mesh_resolution` | 128, 256, 512 | Higher = more detail, slower |
| `device` | "auto", "cuda:0", "cpu" | Compute device |
| `foreground_ratio` | 0.0 - 1.0 | How much of the image the object fills |
| `remove_background` | true/false | Auto-remove image background |

## 📡 Hardware Scanner

The project also includes a full 3D scanner desktop application:

- **`scanner_v3.py`** — PyQt6 desktop app with live camera preview
- **Arduino turntable** — Automated rotation for multi-angle captures
- **3D Viewer** — Built-in Three.js model viewer

```bash
# Launch the scanner app
python scanner_v3.py
```

## 🧠 How It Works

```
📷 Your Image
    ↓
🧠 TripoSR (local AI - StabilityAI + Tripo, MIT License)
    ↓
📦 Raw 3D Mesh (.obj)
    ↓
🔄 Auto-Converter (trimesh + Blender)
    ↓
📁 GLB + OBJ + STL + FBX + .blend (with studio lighting)
```

**TripoSR** is the same core technology behind Tripo's commercial API, but released as open-source under MIT license. It runs a feed-forward neural network that reconstructs 3D geometry from a single image in seconds.

## 📋 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8+ | 3.10 or 3.11 |
| GPU VRAM | 4 GB | 8+ GB |
| RAM | 8 GB | 16+ GB |
| Blender | Any version | 4.0+ or 5.2+ |
| Storage | 3 GB | 5 GB (for model weights) |

> **Note**: The first run downloads ~1.5 GB of AI model weights from Hugging Face. This is a one-time download.

## 📂 Project Structure

```
app/
├── pipeline.py            # Main image-to-3D pipeline (open-source TripoSR)
├── converter.py           # Universal 3D format converter (local)
├── setup_blender_scene.py # Blender studio scene generator
├── scanner_v3.py          # 3D Scanner desktop app (hardware)
├── scanner.spec           # PyInstaller build spec
├── config.json            # Project configuration
├── requirements.txt       # Python dependencies
├── viewer.html            # 3D model viewer (Three.js)
├── three.min.js           # Three.js library
├── OrbitControls.js       # Three.js orbit controls
├── GLTFLoader.js          # Three.js GLTF loader
├── arduino_button/        # Arduino hardware code
├── exports/               # Generated 3D models (output)
└── TripoSR/               # Auto-cloned TripoSR repo (gitignored)
```

## 📄 License

This project uses open-source components:
- **TripoSR**: MIT License (StabilityAI + Tripo)
- **trimesh**: MIT License
- **Blender**: GPL License
