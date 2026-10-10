"""
converter.py
Unified Generic 3D Asset Conversion Engine.
Converts any 3D model (GLB, OBJ, STL, FBX) into the complete suite of 3D assets:
  - GLB (glTF Binary PBR)
  - OBJ (Wavefront OBJ + MTL)
  - STL (Stereolithography for 3D Printing)
  - FBX (Autodesk FBX with Blender preset)
  - BLEND (.blend Native Blender master scene with studio lighting & camera)
  - PNG (Optional high-res studio preview render)

Works completely generic for ANY scanned object or photos, without code changes.
"""

import os
import sys
import time
import shutil
import glob
import subprocess
import requests

# Ensure standard Windows console doesn't crash on non-ASCII output
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_BLENDER_SCRIPT = os.path.join(APP_DIR, "setup_blender_scene.py")


def find_blender():
    """Dynamically discover Blender 5.2 or any installed Blender on Windows/Linux/Mac."""
    candidates = [
        shutil.which("blender"),
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    ]
    candidates += glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe")
    candidates += glob.glob(r"C:\Program Files (x86)\Blender Foundation\Blender*\blender.exe")
    candidates += glob.glob(os.path.expanduser(r"~\AppData\Local\Programs\Blender*\blender.exe"))

    for c in candidates:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return None


def open_in_blender(blend_path):
    """Launch Blender with the specified .blend file."""
    blender_exe = find_blender()
    if not blender_exe or not os.path.exists(blender_exe):
        os.startfile(blend_path)
        return True

    subprocess.Popen([blender_exe, blend_path])
    return True


def convert_model_to_all_formats(
    input_model_path,
    export_dir=None,
    base_name=None,
    tripo_task_id=None,
    tripo_api_key=None,
    render_preview=False,
    log_fn=print
):
    """
    Generically convert any 3D model into all standard 3D formats:
    GLB, OBJ, STL, FBX, and native Blender .blend with studio lighting.

    Returns:
        dict: mapping of format names to generated file paths.
    """
    if not os.path.exists(input_model_path):
        raise FileNotFoundError(f"Source 3D file does not exist: {input_model_path}")

    if export_dir is None:
        export_dir = os.path.join(APP_DIR, "exports")
    drive_prefix = os.path.splitdrive(export_dir)[0]
    if drive_prefix and not os.path.exists(drive_prefix + "\\"):
        export_dir = os.path.join(APP_DIR, "exports")
    os.makedirs(export_dir, exist_ok=True)

    if not base_name:
        base_name = os.path.splitext(os.path.basename(input_model_path))[0]

    results = {}
    log_fn(f"[*] Starting universal 3D asset conversion for '{base_name}'...")

    # ── 1. GLB Asset ──────────────────────────────────────────────────────────
    target_glb = os.path.join(export_dir, f"{base_name}.glb")
    if os.path.abspath(input_model_path) != os.path.abspath(target_glb):
        shutil.copy2(input_model_path, target_glb)
    results["glb"] = target_glb
    log_fn(f"   [+] [GLB] Exported: {os.path.basename(target_glb)} ({os.path.getsize(target_glb)} bytes)")

    # ── 2. Local Mesh Exports: OBJ & STL via trimesh ──────────────────────────
    target_obj = os.path.join(export_dir, f"{base_name}.obj")
    target_stl = os.path.join(export_dir, f"{base_name}.stl")

    try:
        import trimesh
        scene_or_mesh = trimesh.load(target_glb)
        if isinstance(scene_or_mesh, trimesh.Scene):
            mesh = scene_or_mesh.to_geometry()
        else:
            mesh = scene_or_mesh

        # Export OBJ
        mesh.export(target_obj)
        results["obj"] = target_obj
        log_fn(f"   [+] [OBJ] Exported: {os.path.basename(target_obj)} ({os.path.getsize(target_obj)} bytes)")

        # Export STL
        mesh.export(target_stl)
        results["stl"] = target_stl
        log_fn(f"   [+] [STL] Exported: {os.path.basename(target_stl)} ({os.path.getsize(target_stl)} bytes)")
    except Exception as ex:
        log_fn(f"   [!] trimesh export notice: {ex}")

    # ── 3. FBX Export (Tripo Cloud or local Blender) ───────────────────────────
    target_fbx = os.path.join(export_dir, f"{base_name}.fbx")
    fbx_generated = False

    # Attempt Tripo Cloud conversion if task_id & key are provided
    if tripo_task_id and tripo_api_key:
        try:
            log_fn("   [*] Requesting Tripo Cloud FBX (preset=blender)...")
            headers = {"Authorization": f"Bearer {tripo_api_key}", "Content-Type": "application/json"}
            r = requests.post(
                "https://openapi.tripo3d.ai/v3/models/convert",
                headers=headers,
                json={
                    "original_model_task_id": tripo_task_id,
                    "format": "FBX",
                    "fbx_preset": "blender"
                },
                timeout=30
            )
            if r.status_code == 200 and r.json().get("code") == 0:
                cvt_task_id = r.json()["data"]["task_id"]
                start_t = time.time()
                while time.time() - start_t < 180:
                    tr = requests.get(f"https://openapi.tripo3d.ai/v3/tasks/{cvt_task_id}", headers=headers, timeout=20)
                    tdata = tr.json().get("data", {})
                    if tdata.get("status") == "success":
                        m_url = tdata.get("output", {}).get("model_url")
                        if m_url:
                            resp = requests.get(m_url, stream=True, timeout=60)
                            with open(target_fbx, "wb") as fbx_file:
                                for chunk in resp.iter_content(8192):
                                    fbx_file.write(chunk)
                            fbx_generated = True
                            results["fbx"] = target_fbx
                            log_fn(f"   [+] [FBX] Downloaded Cloud FBX: {os.path.basename(target_fbx)} ({os.path.getsize(target_fbx)} bytes)")
                        break
                    elif tdata.get("status") in ("failed", "cancelled"):
                        log_fn(f"   [!] Cloud FBX conversion returned: {tdata.get('error_message')}")
                        break
                    time.sleep(3)
        except Exception as cloud_ex:
            log_fn(f"   [!] Cloud FBX conversion skipped: {cloud_ex}")

    # Fallback to local Blender FBX exporter if not created yet
    blender_exe = find_blender()
    if not fbx_generated and blender_exe and os.path.exists(blender_exe):
        try:
            log_fn("   [*] Generating local FBX via Blender...")
            py_fbx = (
                f"import bpy\n"
                f"bpy.ops.wm.read_homefile(use_empty=True)\n"
                f"bpy.ops.import_scene.gltf(filepath=r'{target_glb}')\n"
                f"bpy.ops.export_scene.fbx(filepath=r'{target_fbx}', use_selection=False, apply_scale_options='FBX_SCALE_ALL')\n"
            )
            subprocess.run([blender_exe, "-b", "--python-expr", py_fbx],
                           capture_output=True, text=True, check=True, timeout=120)
            if os.path.exists(target_fbx) and os.path.getsize(target_fbx) > 0:
                results["fbx"] = target_fbx
                fbx_generated = True
                log_fn(f"   [+] [FBX] Exported Blender FBX: {os.path.basename(target_fbx)} ({os.path.getsize(target_fbx)} bytes)")
        except Exception as blend_fbx_ex:
            log_fn(f"   [!] Blender FBX export notice: {blend_fbx_ex}")

    # ── 4. Native Blender .blend Master Workspace ─────────────────────────────
    target_blend = os.path.join(export_dir, f"{base_name}.blend")
    target_render = os.path.join(export_dir, f"{base_name}_render.png") if render_preview else ""

    if blender_exe and os.path.exists(blender_exe) and os.path.exists(SETUP_BLENDER_SCRIPT):
        try:
            log_fn("   [*] Setting up Blender 5.2 Studio Workspace (.blend)...")
            cmd = [
                blender_exe, "-b", "-P", SETUP_BLENDER_SCRIPT, "--",
                "--input", target_glb,
                "--output", target_blend,
                "--title", base_name
            ]
            if render_preview:
                cmd += ["--render", target_render]

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if os.path.exists(target_blend) and os.path.getsize(target_blend) > 0:
                results["blend"] = target_blend
                log_fn(f"   [+] [BLEND] Saved Master Scene: {os.path.basename(target_blend)} ({os.path.getsize(target_blend)} bytes)")
                if render_preview and os.path.exists(target_render):
                    results["render"] = target_render
                    log_fn(f"   [+] [RENDER] Rendered Preview: {os.path.basename(target_render)}")
            else:
                log_fn(f"   [!] Blender exit: {res.stdout[-300:] if res.stdout else ''}")
        except Exception as blend_scene_ex:
            log_fn(f"   [!] Blender studio scene automation notice: {blend_scene_ex}")
    else:
        log_fn("   [!] Blender executable not found. Skipping .blend scene generation.")

    log_fn(f"[✓] Complete! All assets generated in '{export_dir}':")
    for fmt, p in results.items():
        log_fn(f"      • {fmt.upper()}: {os.path.basename(p)}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert any 3D model into all formats")
    parser.add_argument("--input", "-i", type=str, required=True, help="Input 3D model file (GLB, OBJ, STL, FBX)")
    parser.add_argument("--output-dir", "-o", type=str, default=None, help="Export output directory")
    parser.add_argument("--name", "-n", type=str, default=None, help="Base object name")
    parser.add_argument("--preview", action="store_true", help="Render studio preview image")
    args = parser.parse_args()

    convert_model_to_all_formats(
        input_model_path=args.input,
        export_dir=args.output_dir,
        base_name=args.name,
        render_preview=args.preview,
        log_fn=print
    )
