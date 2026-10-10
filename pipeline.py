"""
pipeline.py
Universal 3D Scanning & AI Reconstruction Pipeline.
Takes any uploaded photos (single photo, 4 orthographic angle photos, or a folder of images),
generates a high-fidelity 3D model using Tripo3D V3 API, downloads the asset, and
automatically exports it into all industry-standard formats:
  - GLB (.glb)
  - OBJ (.obj + .mtl)
  - STL (.stl)
  - FBX (.fbx - Blender & animation preset)
  - BLEND (.blend - native Blender master scene with studio lighting & camera)

Usage examples:
  1. Single image to 3D & all formats:
     python pipeline.py --image "civis_images/civis_front_view.jpg" --name "my_object"

  2. Multiview photos (4 perspectives) to 3D & all formats:
     python pipeline.py --images front.jpg right.jpg back.jpg left.jpg --name "my_object"

  3. Folder of photos to 3D:
     python pipeline.py --folder "civis_images" --name "scanned_robot"

  4. Convert existing GLB into all formats:
     python pipeline.py --glb "scanned_object.glb" --name "my_object"

  5. Process existing Tripo Task ID:
     python pipeline.py --task "c22c343c-8472-4365-91be-ad3e913e32cd" --name "my_object"
"""

import os
import sys
import time
import json
import argparse
import requests
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
BASE_URL = "https://openapi.tripo3d.ai"


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            return json.load(open(CONFIG_PATH, "r", encoding="utf-8"))
        except Exception:
            pass
    return {}


def upload_file_to_tripo(file_path, api_key):
    """Uploads an image or file to Tripo V3 files endpoint and returns file_token."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".bmp": "image/bmp"
    }.get(ext, "image/jpeg")

    fname = os.path.basename(file_path)
    headers = {"Authorization": f"Bearer {api_key}"}

    with open(file_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/v3/files",
            headers=headers,
            files={"file": (fname, f, mime)},
            timeout=60
        )
        r.raise_for_status()
        res = r.json()
        if res.get("code") != 0:
            raise RuntimeError(f"Tripo file upload failed: {res.get('message', res.get('msg', 'Unknown'))}")
        return res["data"]["file_token"]


def poll_tripo_task(task_id, api_key, timeout=900, poll_interval=4, log_fn=print):
    """Polls a Tripo task until success, failed, or cancelled."""
    headers = {"Authorization": f"Bearer {api_key}"}
    start_time = time.time()
    log_fn(f"[*] Monitoring Tripo task {task_id} (timeout={timeout}s)...")

    while time.time() - start_time < timeout:
        r = requests.get(f"{BASE_URL}/v3/tasks/{task_id}", headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", {})
        status = data.get("status", "unknown")
        progress = data.get("progress", 0)

        log_fn(f"   [{time.strftime('%H:%M:%S')}] Status: {status.upper()} | Progress: {progress}%")

        if status == "success":
            out = data.get("output", {})
            model_url = out.get("model_url")
            if not model_url and isinstance(out, list) and len(out) > 0:
                model_url = out[0].get("model_url")
            if not model_url:
                raise RuntimeError("Task succeeded but no model_url in response output.")
            return model_url
        elif status in ("failed", "cancelled"):
            err_msg = data.get("error_message", "Unknown error")
            err_code = data.get("error_code", "N/A")
            raise RuntimeError(f"Tripo task {status}: [{err_code}] {err_msg}")

        time.sleep(poll_interval)

    raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds.")


def generate_from_single_image(image_path, api_key, export_dir, base_name=None, log_fn=print):
    """Generates 3D model from a single photo using Tripo V3 image-to-model."""
    if not base_name:
        base_name = os.path.splitext(os.path.basename(image_path))[0]

    log_fn(f"[*] Uploading source photo: {image_path}")
    file_token = upload_file_to_tripo(image_path, api_key)
    log_fn(f"[+] File uploaded. Token: {file_token[:24]}...")

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    if ext not in ("jpg", "jpeg", "png", "webp", "bmp"):
        ext = "jpg"

    payload = {
        "model_version": "v2.5-20250123",
        "file": {
            "type": ext,
            "file_token": file_token
        },
        "texture": True,
        "pbr": True
    }

    log_fn("[*] Creating 3D generation task (image-to-model)...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(f"{BASE_URL}/v3/generation/image-to-model", headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    res = r.json()
    if res.get("code") != 0:
        raise RuntimeError(f"Task creation failed: {res.get('message', res.get('msg'))}")

    task_id = res["data"]["task_id"]
    log_fn(f"[+] Task created: {task_id}")

    model_url = poll_tripo_task(task_id, api_key, log_fn=log_fn)
    log_fn("[*] Downloading generated GLB model...")

    glb_path = os.path.join(export_dir, f"{base_name}.glb")
    r_dl = requests.get(model_url, stream=True, timeout=120)
    r_dl.raise_for_status()
    with open(glb_path, "wb") as f:
        for chunk in r_dl.iter_content(8192):
            f.write(chunk)
    log_fn(f"[+] Downloaded GLB: {glb_path} ({os.path.getsize(glb_path)} bytes)")

    return glb_path, task_id


def generate_from_multiview_images(image_paths, api_key, export_dir, base_name=None, log_fn=print):
    """
    Generates 3D model from multiple photos (up to 4 orthographic views: front, right, back, left)
    using Tripo V3 multiview-to-model API.
    """
    if not image_paths:
        raise ValueError("No images provided for multiview generation.")

    if not base_name:
        base_name = "multiview_object"

    # We need 4 slots: front, right, back, left.
    # If fewer than 4 provided, cycle or distribute them.
    orientations = ["front", "right", "back", "left"]
    selected = []
    if len(image_paths) == 1:
        return generate_from_single_image(image_paths[0], api_key, export_dir, base_name, log_fn)
    elif len(image_paths) >= 4:
        selected = image_paths[:4]
    else:
        # 2 or 3 images: map sequentially
        selected = image_paths

    log_fn(f"[*] Uploading {len(selected)} perspective images...")
    files_payload = []
    for idx, img_p in enumerate(selected):
        token = upload_file_to_tripo(img_p, api_key)
        ext = os.path.splitext(img_p)[1].lower().lstrip(".")
        if ext not in ("jpg", "jpeg", "png", "webp", "bmp"):
            ext = "jpg"
        orient = orientations[idx] if idx < len(orientations) else "front"
        files_payload.append({
            "type": ext,
            "file_token": token,
            "orientation": orient
        })
        log_fn(f"   [+] Uploaded view {idx+1}/{len(selected)} ({orient}): {os.path.basename(img_p)}")

    payload = {
        "model_version": "v2.5-20250123",
        "files": files_payload,
        "texture": True,
        "pbr": True
    }

    log_fn("[*] Submitting multiview-to-model task to Tripo V3...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(f"{BASE_URL}/v3/generation/multiview-to-model", headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    res = r.json()
    if res.get("code") != 0:
        raise RuntimeError(f"Multiview task creation failed: {res.get('message', res.get('msg'))}")

    task_id = res["data"]["task_id"]
    log_fn(f"[+] Task created: {task_id}")

    model_url = poll_tripo_task(task_id, api_key, log_fn=log_fn)
    log_fn("[*] Downloading generated GLB model...")

    glb_path = os.path.join(export_dir, f"{base_name}.glb")
    r_dl = requests.get(model_url, stream=True, timeout=120)
    r_dl.raise_for_status()
    with open(glb_path, "wb") as f:
        for chunk in r_dl.iter_content(8192):
            f.write(chunk)
    log_fn(f"[+] Downloaded GLB: {glb_path} ({os.path.getsize(glb_path)} bytes)")

    return glb_path, task_id


def run_pipeline(
    image=None,
    images=None,
    folder=None,
    glb=None,
    task=None,
    name=None,
    output_dir=None,
    api_key=None,
    preview=False,
    launch_blender=False,
    log_fn=print
):
    """Executes the complete generation and conversion pipeline."""
    cfg = load_config()
    if not api_key:
        api_key = cfg.get("tripo_api_key", "")

    if not output_dir:
        output_dir = cfg.get("export_dir", DEFAULT_EXPORTS_DIR)
    drive_prefix = os.path.splitdrive(output_dir)[0]
    if drive_prefix and not os.path.exists(drive_prefix + "\\"):
        output_dir = DEFAULT_EXPORTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    glb_file = None
    task_id = None

    # Step A: Obtain GLB model
    if glb:
        if not os.path.exists(glb):
            raise FileNotFoundError(f"Specified GLB file does not exist: {glb}")
        glb_file = glb
        if not name:
            name = os.path.splitext(os.path.basename(glb))[0]
    elif task:
        if not api_key:
            raise ValueError("Tripo API key required to monitor task.")
        if not name:
            name = f"model_{task[:8]}"
        task_id = task
        model_url = poll_tripo_task(task_id, api_key, log_fn=log_fn)
        glb_file = os.path.join(output_dir, f"{name}.glb")
        log_fn("[*] Downloading generated GLB...")
        r_dl = requests.get(model_url, stream=True, timeout=120)
        r_dl.raise_for_status()
        with open(glb_file, "wb") as f:
            for chunk in r_dl.iter_content(8192):
                f.write(chunk)
    elif image:
        if not api_key:
            raise ValueError("Tripo API key required to generate 3D from image. Add it in config.json or use --api-key.")
        glb_file, task_id = generate_from_single_image(image, api_key, output_dir, name, log_fn=log_fn)
        if not name:
            name = os.path.splitext(os.path.basename(image))[0]
    elif images:
        if not api_key:
            raise ValueError("Tripo API key required. Add it in config.json or use --api-key.")
        if not name:
            name = "multiview_scan"
        glb_file, task_id = generate_from_multiview_images(images, api_key, output_dir, name, log_fn=log_fn)
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
        glb_file, task_id = generate_from_multiview_images(found_imgs, api_key, output_dir, name, log_fn=log_fn)
    else:
        # Default: check project root scanned_object.glb
        default_glb = os.path.join(APP_DIR, "scanned_object.glb")
        if os.path.exists(default_glb):
            log_fn(f"[*] No inputs provided. Using default project model: {default_glb}")
            glb_file = default_glb
            name = "scanned_object"
        else:
            raise ValueError("No input provided. Use --image, --images, --folder, --glb, or --task.")

    # Also update the primary scanned_object.glb in app directory
    app_glb = os.path.join(APP_DIR, "scanned_object.glb")
    if os.path.abspath(glb_file) != os.path.abspath(app_glb):
        try:
            import shutil
            shutil.copy2(glb_file, app_glb)
        except Exception:
            pass

    # Step B: Auto-convert into ALL formats (OBJ, STL, FBX, BLEND, PNG)
    results = convert_model_to_all_formats(
        input_model_path=glb_file,
        export_dir=output_dir,
        base_name=name,
        tripo_task_id=task_id,
        tripo_api_key=api_key,
        render_preview=preview,
        log_fn=log_fn
    )

    if launch_blender and results.get("blend"):
        log_fn(f"[*] Launching Blender with {results['blend']}...")
        open_in_blender(results["blend"])

    return results


def main():
    parser = argparse.ArgumentParser(description="Universal 3D Scanning & AI Reconstruction Pipeline")
    parser.add_argument("--image", "-i", type=str, default=None, help="Path to single image for 3D reconstruction")
    parser.add_argument("--images", nargs="+", default=None, help="List of 2-4 angle images for multiview reconstruction")
    parser.add_argument("--folder", "-f", type=str, default=None, help="Folder containing images to reconstruct")
    parser.add_argument("--glb", "-g", type=str, default=None, help="Convert an existing GLB model to all formats")
    parser.add_argument("--task", "-t", type=str, default=None, help="Download & convert an existing Tripo task ID")
    parser.add_argument("--name", "-n", type=str, default=None, help="Base name for exported 3D assets")
    parser.add_argument("--output-dir", "-o", type=str, default=None, help="Directory to save exported 3D assets")
    parser.add_argument("--api-key", "-k", type=str, default=None, help="Tripo API key (defaults to config.json)")
    parser.add_argument("--preview", action="store_true", help="Generate studio render preview (.png)")
    parser.add_argument("--blender", action="store_true", help="Open generated .blend in Blender after completion")
    args = parser.parse_args()

    run_pipeline(
        image=args.image,
        images=args.images,
        folder=args.folder,
        glb=args.glb,
        task=args.task,
        name=args.name,
        output_dir=args.output_dir,
        api_key=args.api_key,
        preview=args.preview,
        launch_blender=args.blender,
        log_fn=print
    )


if __name__ == "__main__":
    main()
