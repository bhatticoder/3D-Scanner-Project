"""
convert_civis_to_blender.py
Generic Blender Batch & Model Conversion script.
Converts any 3D models in the exports folder or specified input model
into fully editable native Blender .blend scenes with studio lighting, camera,
floor plane, and packed PBR textures.

Usage:
    python convert_civis_to_blender.py [MODEL_PATH]
"""

import os
import sys
import glob
from converter import convert_model_to_all_formats

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")

def main():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        target_path = sys.argv[1]
        name = os.path.splitext(os.path.basename(target_path))[0]
        print(f"[*] Converting specified model: {target_path}")
        convert_model_to_all_formats(target_path, export_dir=EXPORTS_DIR, base_name=name)
        return

    # Check for any models in exports or root
    models = glob.glob(os.path.join(EXPORTS_DIR, "*.glb"))
    if not models:
        root_glb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_object.glb")
        if os.path.exists(root_glb):
            models = [root_glb]

    if not models:
        print("[!] No GLB models found in exports/ or project root.")
        return

    print(f"[*] Found {len(models)} model(s) to process into Blender workspaces...")
    for m in models:
        name = os.path.splitext(os.path.basename(m))[0]
        print(f"[*] Processing: {os.path.basename(m)}")
        convert_model_to_all_formats(m, export_dir=EXPORTS_DIR, base_name=name)

    print("[✓] All conversions completed successfully!")

if __name__ == "__main__":
    main()
