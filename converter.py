"""
converter.py
Unified Generic 3D Asset Conversion Engine (100% Local, Open-Source).
Converts any 3D model (GLB, OBJ, STL, FBX) into the complete suite of 3D assets:
  - GLB (glTF Binary PBR)
  - OBJ (Wavefront OBJ + MTL)
  - STL (Stereolithography for 3D Printing)
  - FBX (Autodesk FBX via local Blender)
  - BLEND (.blend Native Blender master scene with studio lighting & camera)
  - PNG (Optional high-res studio preview render)

No cloud APIs. No paid services. Everything runs locally.
Works completely generic for ANY image, scanned object, or photo.
"""

import os
import sys
import time
import shutil
import glob
import subprocess

# Ensure standard Windows console doesn't crash on non-ASCII output
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_BLENDER_SCRIPT = os.path.join(APP_DIR, "setup_blender_scene.py")


def find_blender():
    """Dynamically discover Blender on Windows/Linux/Mac."""
    candidates = [
        shutil.which("blender"),
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    ]
    candidates += glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe")
    candidates += glob.glob(r"C:\Program Files (x86)\Blender Foundation\Blender*\blender.exe")
    candidates += glob.glob(os.path.expanduser(r"~\AppData\Local\Programs\Blender*\blender.exe"))

    # Linux/Mac
    candidates += glob.glob("/usr/bin/blender")
    candidates += glob.glob("/usr/local/bin/blender")
    candidates += glob.glob("/snap/bin/blender")
    candidates += glob.glob("/Applications/Blender.app/Contents/MacOS/Blender")

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
    render_preview=False,
    log_fn=print
):
    """
    Generically convert any 3D model into all standard 3D formats:
    GLB, OBJ, STL, FBX, and native Blender .blend with studio lighting.
    Everything runs 100% locally — no cloud APIs.

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
    input_ext = os.path.splitext(input_model_path)[1].lower()
    log_fn(f"[*] Starting universal 3D asset conversion for '{base_name}'...")

    # ── 1. Load mesh via trimesh ──────────────────────────────────────────────
    try:
        import trimesh
        scene_or_mesh = trimesh.load(input_model_path)
        if isinstance(scene_or_mesh, trimesh.Scene):
            mesh = scene_or_mesh.to_geometry()
        else:
            mesh = scene_or_mesh
        has_trimesh = True
    except Exception as ex:
        log_fn(f"   [!] trimesh load notice: {ex}")
        mesh = None
        has_trimesh = False

    # ── 2. GLB Asset ──────────────────────────────────────────────────────────
    target_glb = os.path.join(export_dir, f"{base_name}.glb")
    if input_ext == ".glb" and os.path.abspath(input_model_path) != os.path.abspath(target_glb):
        shutil.copy2(input_model_path, target_glb)
        results["glb"] = target_glb
        log_fn(f"   [+] [GLB] Copied: {os.path.basename(target_glb)} ({os.path.getsize(target_glb)} bytes)")
    elif has_trimesh and input_ext != ".glb":
        try:
            mesh.export(target_glb)
            results["glb"] = target_glb
            log_fn(f"   [+] [GLB] Exported: {os.path.basename(target_glb)} ({os.path.getsize(target_glb)} bytes)")
        except Exception as e:
            log_fn(f"   [!] GLB export notice: {e}")
    elif input_ext == ".glb":
        results["glb"] = input_model_path
        log_fn(f"   [+] [GLB] Using source: {os.path.basename(input_model_path)}")

    # ── 3. OBJ Asset ─────────────────────────────────────────────────────────
    target_obj = os.path.join(export_dir, f"{base_name}.obj")
    if input_ext == ".obj" and os.path.abspath(input_model_path) != os.path.abspath(target_obj):
        shutil.copy2(input_model_path, target_obj)
        results["obj"] = target_obj
        log_fn(f"   [+] [OBJ] Copied: {os.path.basename(target_obj)} ({os.path.getsize(target_obj)} bytes)")
    elif input_ext == ".obj" and os.path.abspath(input_model_path) == os.path.abspath(target_obj):
        results["obj"] = target_obj
        log_fn(f"   [+] [OBJ] Using source: {os.path.basename(target_obj)}")
    elif has_trimesh:
        try:
            mesh.export(target_obj)
            results["obj"] = target_obj
            log_fn(f"   [+] [OBJ] Exported: {os.path.basename(target_obj)} ({os.path.getsize(target_obj)} bytes)")
        except Exception as e:
            log_fn(f"   [!] OBJ export notice: {e}")

    # ── 4. STL Asset ─────────────────────────────────────────────────────────
    target_stl = os.path.join(export_dir, f"{base_name}.stl")
    if has_trimesh:
        try:
            mesh.export(target_stl)
            results["stl"] = target_stl
            log_fn(f"   [+] [STL] Exported: {os.path.basename(target_stl)} ({os.path.getsize(target_stl)} bytes)")
        except Exception as e:
            log_fn(f"   [!] STL export notice: {e}")

    # ── 5. FBX Export via local Blender ────────────────────────────────────────
    target_fbx = os.path.join(export_dir, f"{base_name}.fbx")
    blender_exe = find_blender()

    # Determine the best source file for Blender import
    blender_source = None
    if results.get("glb"):
        blender_source = results["glb"]
    elif results.get("obj"):
        blender_source = results["obj"]
    elif input_ext in (".glb", ".gltf", ".obj", ".fbx", ".stl"):
        blender_source = input_model_path

    if blender_exe and os.path.exists(blender_exe) and blender_source:
        try:
            log_fn("   [*] Generating FBX via local Blender...")
            src_ext = os.path.splitext(blender_source)[1].lower()

            if src_ext in (".glb", ".gltf"):
                import_line = f"bpy.ops.import_scene.gltf(filepath=r'{blender_source}')"
            elif src_ext == ".obj":
                import_line = f"bpy.ops.wm.obj_import(filepath=r'{blender_source}')"
            elif src_ext == ".fbx":
                import_line = f"bpy.ops.import_scene.fbx(filepath=r'{blender_source}')"
            elif src_ext == ".stl":
                import_line = f"bpy.ops.wm.stl_import(filepath=r'{blender_source}')"
            else:
                import_line = f"bpy.ops.import_scene.gltf(filepath=r'{blender_source}')"

            py_fbx = (
                f"import bpy\n"
                f"bpy.ops.wm.read_homefile(use_empty=True)\n"
                f"{import_line}\n"
                f"bpy.ops.export_scene.fbx(filepath=r'{target_fbx}', use_selection=False, apply_scale_options='FBX_SCALE_ALL')\n"
            )
            subprocess.run([blender_exe, "-b", "--python-expr", py_fbx],
                           capture_output=True, text=True, check=True, timeout=120)
            if os.path.exists(target_fbx) and os.path.getsize(target_fbx) > 0:
                results["fbx"] = target_fbx
                log_fn(f"   [+] [FBX] Exported: {os.path.basename(target_fbx)} ({os.path.getsize(target_fbx)} bytes)")
        except Exception as blend_fbx_ex:
            log_fn(f"   [!] Blender FBX export notice: {blend_fbx_ex}")
    else:
        if not blender_exe:
            log_fn("   [!] Blender not found. Skipping FBX export. Install Blender for FBX support.")

    # ── 6. Native Blender .blend Master Workspace ─────────────────────────────
    target_blend = os.path.join(export_dir, f"{base_name}.blend")
    target_render = os.path.join(export_dir, f"{base_name}_render.png") if render_preview else ""

    if blender_exe and os.path.exists(blender_exe) and os.path.exists(SETUP_BLENDER_SCRIPT) and blender_source:
        try:
            log_fn("   [*] Setting up Blender Studio Workspace (.blend)...")
            cmd = [
                blender_exe, "-b", "-P", SETUP_BLENDER_SCRIPT, "--",
                "--input", blender_source,
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
            log_fn(f"   [!] Blender studio scene notice: {blend_scene_ex}")
    else:
        if not blender_exe:
            log_fn("   [!] Blender not found. Skipping .blend scene generation.")

    log_fn(f"[✓] Complete! All assets generated in '{export_dir}':")
    for fmt, p in results.items():
        log_fn(f"      • {fmt.upper()}: {os.path.basename(p)}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert any 3D model into all formats (100% local)")
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
