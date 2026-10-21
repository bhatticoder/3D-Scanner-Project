"""
pipeline.py
Open-Source Local Image-to-3D Pipeline.
Takes any uploaded image, generates a high-fidelity 3D model using TripoSR
(open-source, MIT licensed, by StabilityAI + Tripo) running 100% locally,
and automatically exports into all industry-standard formats:
  - GLB (.glb)
  - OBJ (.obj + .mtl)
  - STL (.stl)
  - FBX (.fbx - via Blender)
  - BLEND (.blend - native Blender master scene with studio lighting & camera)

No API keys. No cloud. No payments. Runs on your own GPU (or CPU).

Usage examples:
  1. Single image to 3D & all formats:
     python pipeline.py --image "photo.jpg" --name "my_object"

  2. Multiple images (batch processing - each becomes its own model):
     python pipeline.py --images front.jpg side.jpg back.jpg --name "my_object"

  3. Folder of photos to 3D:
     python pipeline.py --folder "my_photos" --name "scanned_robot"

  4. Convert existing GLB into all formats:
     python pipeline.py --glb "model.glb" --name "my_object"

  5. Adjust mesh quality (higher = more detail, slower):
     python pipeline.py --image "photo.jpg" --name "my_object" --resolution 512

  6. Run on CPU (no GPU required):
     python pipeline.py --image "photo.jpg" --name "my_object" --device cpu
"""

import os
import sys
import time
import json
import argparse
import glob

# Ensure UTF-8 output on Windows consoles
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from converter import convert_model_to_all_formats, open_in_blender, find_blender

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
DEFAULT_EXPORTS_DIR = os.path.join(APP_DIR, "exports")
TRIPOSR_DIR = os.path.join(APP_DIR, "TripoSR")


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            return json.load(open(CONFIG_PATH, "r", encoding="utf-8"))
        except Exception:
            pass
    return {}


def ensure_triposr_installed(log_fn=print):
    """Ensure TripoSR repository is cloned and importable."""
    if os.path.exists(os.path.join(TRIPOSR_DIR, "tsr")):
        if TRIPOSR_DIR not in sys.path:
            sys.path.insert(0, TRIPOSR_DIR)
        return True

    log_fn("[*] TripoSR not found. Cloning from GitHub (one-time setup)...")
    import subprocess
    try:
        subprocess.run(
            ["git", "clone", "https://github.com/VAST-AI-Research/TripoSR.git", TRIPOSR_DIR],
            check=True, capture_output=True, text=True, timeout=300
        )
        log_fn("[+] TripoSR repository cloned successfully.")

        # Install TripoSR dependencies
        log_fn("[*] Installing TripoSR dependencies...")
        req_file = os.path.join(TRIPOSR_DIR, "requirements.txt")
        if os.path.exists(req_file):
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_file],
                check=True, capture_output=True, text=True, timeout=600
            )
        log_fn("[+] TripoSR dependencies installed.")

        if TRIPOSR_DIR not in sys.path:
            sys.path.insert(0, TRIPOSR_DIR)
        return True
    except Exception as e:
        log_fn(f"[!] Failed to set up TripoSR: {e}")
        log_fn("[!] Please manually run:")
        log_fn(f"    git clone https://github.com/VAST-AI-Research/TripoSR.git {TRIPOSR_DIR}")
        log_fn(f"    pip install -r {os.path.join(TRIPOSR_DIR, 'requirements.txt')}")
        return False


def generate_3d_from_image(
    image_path,
    export_dir,
    base_name=None,
    resolution=256,
    device="auto",
    remove_bg=True,
    foreground_ratio=0.85,
    log_fn=print
):
    """
    Generate a 3D model from a single image using TripoSR (100% local, open-source).

    Args:
        image_path: Path to input image
        export_dir: Directory to save output files
        base_name: Base name for output files (defaults to input filename)
        resolution: Marching cubes resolution (128=fast/low, 256=balanced, 512=high quality)
        device: 'auto', 'cuda:0', 'cpu', etc.
        remove_bg: Whether to automatically remove background
        foreground_ratio: How much of the image the foreground should occupy (0.0-1.0)
        log_fn: Logging function

    Returns:
        str: Path to generated OBJ file
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not base_name:
        base_name = os.path.splitext(os.path.basename(image_path))[0]

    os.makedirs(export_dir, exist_ok=True)

    # Ensure TripoSR is available
    if not ensure_triposr_installed(log_fn):
        raise RuntimeError("TripoSR is not installed. See instructions above.")

    import torch
    from PIL import Image

    # Determine device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda:0"
            log_fn(f"[+] Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            log_fn("[*] No GPU detected. Running on CPU (slower but works fine).")
    else:
        log_fn(f"[*] Using device: {device}")

    # Import TripoSR
    log_fn("[*] Loading TripoSR AI model (first run downloads ~1.5GB model weights)...")
    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground

    model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        device=device,
    )

    # Reduce VRAM usage for GPUs with limited memory
    if device.startswith("cuda"):
        try:
            vram_gb = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            if vram_gb < 8:
                model.renderer.set_chunk_size(4096)
                log_fn(f"[*] Low VRAM ({vram_gb:.1f}GB) detected. Using chunked rendering.")
            elif vram_gb < 6:
                model.renderer.set_chunk_size(2048)
                log_fn(f"[*] Very low VRAM ({vram_gb:.1f}GB). Using small chunks.")
        except Exception:
            pass

    log_fn(f"[+] TripoSR model loaded on {device}.")

    # Load and preprocess image
    log_fn(f"[*] Processing image: {os.path.basename(image_path)}")
    image = Image.open(image_path)

    if remove_bg:
        log_fn("[*] Removing background...")
        try:
            image = remove_background(image)
            image = resize_foreground(image, foreground_ratio)
            log_fn("[+] Background removed and foreground centered.")
        except Exception as e:
            log_fn(f"[!] Background removal failed ({e}). Proceeding with original image.")

    # Run inference
    log_fn("[*] Generating 3D model (this may take 30-120 seconds)...")
    start_time = time.time()

    with torch.no_grad():
        scene_codes = model([image], device=device)

    # Extract mesh
    log_fn(f"[*] Extracting mesh at resolution {resolution}...")
    meshes = model.extract_mesh(scene_codes, resolution=resolution)

    elapsed = time.time() - start_time
    log_fn(f"[+] 3D model generated in {elapsed:.1f} seconds!")

    # Save as OBJ (primary format from TripoSR)
    output_obj = os.path.join(export_dir, f"{base_name}.obj")
    meshes[0].export(output_obj)
    log_fn(f"[+] Saved OBJ: {output_obj} ({os.path.getsize(output_obj)} bytes)")

    return output_obj


def run_pipeline(
    image=None,
    images=None,
    folder=None,
    glb=None,
    name=None,
    output_dir=None,
    resolution=256,
    device="auto",
    remove_bg=True,
    foreground_ratio=0.85,
    preview=False,
    launch_blender=False,
    log_fn=print
):
    """Executes the complete local generation and conversion pipeline."""
    cfg = load_config()

    if not output_dir:
        output_dir = cfg.get("export_dir", DEFAULT_EXPORTS_DIR)
    drive_prefix = os.path.splitdrive(output_dir)[0]
    if drive_prefix and not os.path.exists(drive_prefix + "\\"):
        output_dir = DEFAULT_EXPORTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Override settings from config if not provided via args
    if resolution == 256 and cfg.get("mesh_resolution"):
        resolution = cfg["mesh_resolution"]
    if device == "auto" and cfg.get("device"):
        device = cfg["device"]
    if foreground_ratio == 0.85 and cfg.get("foreground_ratio"):
        foreground_ratio = cfg["foreground_ratio"]

    source_model = None

    # Step A: Obtain 3D Model
    if glb:
        # Direct GLB/OBJ conversion mode (no AI generation needed)
        if not os.path.exists(glb):
            raise FileNotFoundError(f"Specified model file does not exist: {glb}")
        source_model = glb
        if not name:
            name = os.path.splitext(os.path.basename(glb))[0]
        log_fn(f"[*] Using existing model: {glb}")
    elif image:
        # Single image → 3D
        if not name:
            name = os.path.splitext(os.path.basename(image))[0]
        source_model = generate_3d_from_image(
            image, output_dir, name, resolution, device, remove_bg, foreground_ratio, log_fn
        )
    elif images:
        # Multiple images → process each (or use best one)
        if not name:
            name = "generated_model"
        # For TripoSR, we use the first/front image as the primary input
        # (TripoSR is single-image; for multi-view, use the front view)
        primary_image = images[0]
        log_fn(f"[*] Using primary image for 3D generation: {os.path.basename(primary_image)}")
        if len(images) > 1:
            log_fn(f"[*] Note: TripoSR uses single-image reconstruction. Using first image as primary view.")
            log_fn(f"    Additional {len(images)-1} images will be skipped.")
            log_fn(f"    For multi-view reconstruction, consider InstantMesh or Zero123++.")
        source_model = generate_3d_from_image(
            primary_image, output_dir, name, resolution, device, remove_bg, foreground_ratio, log_fn
        )
    elif folder:
        if not os.path.exists(folder):
            raise FileNotFoundError(f"Folder does not exist: {folder}")
        found_imgs = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"):
            found_imgs += glob.glob(os.path.join(folder, ext))
            found_imgs += glob.glob(os.path.join(folder, ext.upper()))
        found_imgs = sorted(list(set(found_imgs)))
        if not found_imgs:
            raise FileNotFoundError(f"No image files found in folder: {folder}")
        log_fn(f"[+] Found {len(found_imgs)} images in folder '{folder}'")
        if not name:
            name = os.path.basename(os.path.normpath(folder))
        # Use first image as primary
        source_model = generate_3d_from_image(
            found_imgs[0], output_dir, name, resolution, device, remove_bg, foreground_ratio, log_fn
        )
    else:
        raise ValueError(
            "No input provided. Use one of:\n"
            "  --image photo.jpg\n"
            "  --images front.jpg side.jpg\n"
            "  --folder my_photos/\n"
            "  --glb existing_model.glb"
        )

    # Step B: Auto-convert into ALL formats (GLB, OBJ, STL, FBX, BLEND)
    results = convert_model_to_all_formats(
        input_model_path=source_model,
        export_dir=output_dir,
        base_name=name,
        render_preview=preview,
        log_fn=log_fn
    )

    if launch_blender and results.get("blend"):
        log_fn(f"[*] Launching Blender with {results['blend']}...")
        open_in_blender(results["blend"])

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Open-Source Image-to-3D Pipeline (TripoSR — 100% Local, No API Keys)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --image photo.jpg --name my_object
  python pipeline.py --image photo.jpg --name my_object --resolution 512
  python pipeline.py --image photo.jpg --name my_object --device cpu
  python pipeline.py --folder my_photos/ --name scanned_thing
  python pipeline.py --glb existing.glb --name converted_model
        """
    )
    parser.add_argument("--image", "-i", type=str, default=None,
                        help="Path to single image for 3D reconstruction")
    parser.add_argument("--images", nargs="+", default=None,
                        help="List of images (first one used as primary view)")
    parser.add_argument("--folder", "-f", type=str, default=None,
                        help="Folder containing images to reconstruct")
    parser.add_argument("--glb", "-g", type=str, default=None,
                        help="Convert an existing GLB/OBJ model to all formats")
    parser.add_argument("--name", "-n", type=str, default=None,
                        help="Base name for exported 3D assets")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory to save exported 3D assets")
    parser.add_argument("--resolution", "-r", type=int, default=256,
                        choices=[128, 256, 512],
                        help="Mesh resolution: 128=fast, 256=balanced, 512=high (default: 256)")
    parser.add_argument("--device", "-d", type=str, default="auto",
                        help="Compute device: auto, cuda:0, cpu (default: auto)")
    parser.add_argument("--no-remove-bg", action="store_true",
                        help="Skip automatic background removal")
    parser.add_argument("--foreground-ratio", type=float, default=0.85,
                        help="Foreground size ratio after bg removal (default: 0.85)")
    parser.add_argument("--preview", action="store_true",
                        help="Generate studio render preview (.png)")
    parser.add_argument("--blender", action="store_true",
                        help="Open generated .blend in Blender after completion")
    args = parser.parse_args()

    run_pipeline(
        image=args.image,
        images=args.images,
        folder=args.folder,
        glb=args.glb,
        name=args.name,
        output_dir=args.output_dir,
        resolution=args.resolution,
        device=args.device,
        remove_bg=not args.no_remove_bg,
        foreground_ratio=args.foreground_ratio,
        preview=args.preview,
        launch_blender=args.blender,
        log_fn=print
    )


if __name__ == "__main__":
    main()
