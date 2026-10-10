"""
setup_blender_scene.py
Generic Blender 5.2 Studio Scene Generator.
Automatically imports any 3D model (GLB, OBJ, FBX, STL),
sets up professional 3-point studio lighting, ground shadow floor,
hero camera, world environment, packs all textures, and saves an
editable .blend master scene file.

Usage from command line:
    blender.exe -b -P setup_blender_scene.py -- --input "model.glb" --output "model.blend" --render "preview.png" --title "Object_Name"
"""

import sys
import os
import argparse
import math

try:
    import bpy
    import mathutils
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


def parse_args():
    # User arguments are passed after '--'
    argv = sys.argv
    if "--" in argv:
        args_to_parse = argv[argv.index("--") + 1:]
    else:
        args_to_parse = []

    parser = argparse.ArgumentParser(description="Automated Blender Studio Scene Generator")
    parser.add_argument("--input", "-i", type=str, required=False, default="",
                        help="Input 3D model file (GLB, GLTF, OBJ, FBX, STL)")
    parser.add_argument("--output", "-o", type=str, required=False, default="",
                        help="Output .blend file path")
    parser.add_argument("--render", "-r", type=str, required=False, default="",
                        help="Output render preview image path (.png)")
    parser.add_argument("--title", "-t", type=str, required=False, default="Scanned_Model",
                        help="Scene / Model title")
    parser.add_argument("--texture", type=str, required=False, default="",
                        help="Optional texture PNG path if separate from OBJ/STL")
    return parser.parse_args(args_to_parse)


def import_3d_file(file_path):
    """Import a 3D file into Blender based on its file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    print(f"[*] Importing model ({ext}): {file_path}")

    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=file_path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=file_path)
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=file_path)
        else:
            bpy.ops.import_scene.obj(filepath=file_path)
    elif ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=file_path)
        else:
            bpy.ops.import_mesh.stl(filepath=file_path)
    else:
        raise ValueError(f"Unsupported 3D file format: {ext}")


def setup_studio_scene(input_path, output_blend, render_path="", title="Scanned_Model", texture_path=""):
    """Creates a complete professional studio scene for the imported model."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # 1. Reset Blender to a clean, empty workspace
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'

    # 2. Import 3D file
    import_3d_file(input_path)

    # 3. Create Model Collection
    col_model = bpy.data.collections.new(f"01_{title}_Model")
    scene.collection.children.link(col_model)

    mesh_objs = [obj for obj in scene.objects if obj.type == 'MESH']
    if not mesh_objs:
        print("[!] Warning: No mesh objects found in imported model.")
        return

    print(f"[+] Found {len(mesh_objs)} mesh object(s)")

    # 4. Calculate bounding box & bounds across all meshes
    min_coord = [float('inf')] * 3
    max_coord = [float('-inf')] * 3

    for obj in mesh_objs:
        # Move into Model collection
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col_model.objects.link(obj)

        # Smooth shading for organic quality
        for poly in obj.data.polygons:
            poly.use_smooth = True

        # Hook texture if provided for OBJ/STL
        if texture_path and os.path.exists(texture_path):
            if not obj.data.materials:
                mat = bpy.data.materials.new(name=f"Mat_{title}_PBR")
                mat.use_nodes = True
                obj.data.materials.append(mat)
            else:
                mat = obj.data.materials[0]
                mat.use_nodes = True

            nodes = mat.node_tree.nodes
            bsdf = nodes.get("Principled BSDF")
            if bsdf and not any(n.type == 'TEX_IMAGE' for n in nodes):
                tex_node = nodes.new(type='ShaderNodeTexImage')
                try:
                    tex_node.image = bpy.data.images.load(texture_path)
                    mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                except Exception as ex:
                    print(f"Texture mapping notice: {ex}")

        # Compute world bounding box
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            for i in range(3):
                min_coord[i] = min(min_coord[i], world_corner[i])
                max_coord[i] = max(max_coord[i], world_corner[i])

    dim = [max_coord[i] - min_coord[i] for i in range(3)]
    center_x = (max_coord[0] + min_coord[0]) * 0.5
    center_y = (max_coord[1] + min_coord[1]) * 0.5
    max_dim = max(dim) if max(dim) > 0.01 else 1.0

    print(f"[+] Bounding dimensions: X={dim[0]:.3f}m, Y={dim[1]:.3f}m, Z={dim[2]:.3f}m (Max: {max_dim:.3f}m)")

    # 5. Center in X, Y and Ground bottom of model to Z=0
    z_offset = -min_coord[2]
    x_offset = -center_x
    y_offset = -center_y

    for obj in mesh_objs:
        obj.location.x += x_offset
        obj.location.y += y_offset
        obj.location.z += z_offset
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        obj.select_set(False)

    target_z = dim[2] * 0.5

    # 6. Studio Lighting Collection
    col_lights = bpy.data.collections.new("02_Studio_Lighting")
    scene.collection.children.link(col_lights)

    # Key Light (Warm soft primary light)
    key_data = bpy.data.lights.new(name="Key_Light", type='AREA')
    key_data.energy = max(350.0 * (max_dim ** 1.2), 200.0)
    key_data.size = max(max_dim * 1.5, 2.0)
    key_data.color = (1.0, 0.96, 0.92)
    key_obj = bpy.data.objects.new(name="Key_Light", object_data=key_data)
    key_obj.location = (max_dim * 1.5, -max_dim * 2.0, max_dim * 2.0)
    col_lights.objects.link(key_obj)
    key_dir = mathutils.Vector((0, 0, target_z)) - key_obj.location
    key_obj.rotation_euler = key_dir.to_track_quat('-Z', 'Y').to_euler()

    # Fill Light (Cool ambient fill light)
    fill_data = bpy.data.lights.new(name="Fill_Light", type='AREA')
    fill_data.energy = max(180.0 * (max_dim ** 1.2), 100.0)
    fill_data.size = max(max_dim * 2.0, 2.5)
    fill_data.color = (0.85, 0.92, 1.0)
    fill_obj = bpy.data.objects.new(name="Fill_Light", object_data=fill_data)
    fill_obj.location = (-max_dim * 1.8, -max_dim * 1.5, max_dim * 1.5)
    col_lights.objects.link(fill_obj)
    fill_dir = mathutils.Vector((0, 0, target_z)) - fill_obj.location
    fill_obj.rotation_euler = fill_dir.to_track_quat('-Z', 'Y').to_euler()

    # Rim / Accent Light (Highlights object silhouette)
    rim_data = bpy.data.lights.new(name="Rim_Light", type='AREA')
    rim_data.energy = max(450.0 * (max_dim ** 1.2), 250.0)
    rim_data.size = max(max_dim * 1.5, 2.0)
    rim_data.color = (0.60, 0.85, 1.0)
    rim_obj = bpy.data.objects.new(name="Rim_Light", object_data=rim_data)
    rim_obj.location = (0.0, max_dim * 2.2, max_dim * 2.2)
    col_lights.objects.link(rim_obj)
    rim_dir = mathutils.Vector((0, 0, target_z)) - rim_obj.location
    rim_obj.rotation_euler = rim_dir.to_track_quat('-Z', 'Y').to_euler()

    # Ground Shadow Plane
    bpy.ops.mesh.primitive_plane_add(size=max(max_dim * 8.0, 10.0), location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Studio_Floor"
    for c in list(plane.users_collection):
        c.objects.unlink(plane)
    col_lights.objects.link(plane)

    floor_mat = bpy.data.materials.new("Studio_Floor_Mat")
    floor_mat.use_nodes = True
    bsdf_floor = floor_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf_floor:
        bsdf_floor.inputs["Base Color"].default_value = (0.08, 0.09, 0.11, 1.0)
        bsdf_floor.inputs["Roughness"].default_value = 0.4
    plane.data.materials.append(floor_mat)

    # 7. Hero Camera Collection
    col_cam = bpy.data.collections.new("03_Cameras")
    scene.collection.children.link(col_cam)

    cam_data = bpy.data.cameras.new("Hero_Camera")
    cam_data.lens = 50
    cam_obj = bpy.data.objects.new("Hero_Camera", cam_data)
    cam_dist = max(max_dim * 2.8, 3.0)
    cam_obj.location = (cam_dist * 0.45, -cam_dist * 0.85, target_z + cam_dist * 0.25)
    cam_dir = mathutils.Vector((0, 0, target_z)) - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
    col_cam.objects.link(cam_obj)
    scene.camera = cam_obj

    # 8. World environment settings
    world = scene.world
    if not world:
        world = bpy.data.worlds.new("Studio_World")
        scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.04, 0.04, 0.06, 1.0)
        bg_node.inputs["Strength"].default_value = 0.6

    # 9. Pack all textures into .blend
    try:
        bpy.ops.file.pack_all()
        print("[+] Textures successfully packed into Blender workspace.")
    except Exception as e:
        print(f"[!] Texture packing notice: {e}")

    # 10. Save master .blend file FIRST so the project file is always guaranteed
    out_dir = os.path.dirname(os.path.abspath(output_blend))
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"[+] Successfully saved Blender workspace: {output_blend} ({os.path.getsize(output_blend)} bytes)")

    # 11. Optional studio preview rendering
    if render_path:
        os.makedirs(os.path.dirname(os.path.abspath(render_path)), exist_ok=True)
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.filepath = render_path
        # Use CYCLES with CPU or WORKBENCH to avoid headless OpenGL shader crash
        try:
            scene.render.engine = 'BLENDER_WORKBENCH'
            print(f"[*] Rendering studio preview to {render_path}...")
            bpy.ops.render.render(write_still=True)
            print(f"[+] Render preview saved: {render_path}")
        except Exception as e:
            print(f"[!] Headless preview render skipped: {e}")


if __name__ == "__main__":
    if not IN_BLENDER:
        print("This script is designed to run inside Blender (blender -b -P setup_blender_scene.py -- ...)")
        sys.exit(1)

    args = parse_args()
    if not args.input:
        # Default fallback to scanned_object.glb in project root
        project_root = os.path.dirname(os.path.abspath(__file__))
        default_glb = os.path.join(project_root, "scanned_object.glb")
        if os.path.exists(default_glb):
            args.input = default_glb
        else:
            print("[!] Error: No input model specified. Use --input <path_to_model>")
            sys.exit(1)

    if not args.output:
        base = os.path.splitext(os.path.basename(args.input))[0]
        exports_dir = os.path.join(os.path.dirname(os.path.abspath(args.input)), "exports")
        args.output = os.path.join(exports_dir, f"{base}.blend")

    if not args.render:
        base = os.path.splitext(os.path.basename(args.output))[0]
        args.render = os.path.join(os.path.dirname(args.output), f"{base}_render.png")

    setup_studio_scene(
        input_path=args.input,
        output_blend=args.output,
        render_path=args.render,
        title=args.title,
        texture_path=args.texture
    )
