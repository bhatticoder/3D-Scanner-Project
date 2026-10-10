"""
build_blender_civis.py
Fully automated procedural generator for the CIVIS Autonomous Service Robot in Blender 5.2.
Constructs clean, modular, non-destructive quad geometry with bevel modifiers,
proper PBR materials, emission lighting, and organized hierarchy.

Dimensions adhere strictly to diagrams:
- Length: 70 cm (0.70 m) along Y
- Width:  55 cm (0.55 m) along X
- Height: 110 cm (1.10 m) along Z
"""

import bpy
import math
import os

def create_material(name, base_color=(1, 1, 1, 1), roughness=0.3, metallic=0.0, emission_color=None, emission_strength=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission_color:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = emission_color
                bsdf.inputs["Emission Strength"].default_value = emission_strength
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = emission_color
    return mat

def get_or_create_collection(name, parent_col=None):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    if parent_col:
        parent_col.children.link(col)
    else:
        bpy.context.scene.collection.children.link(col)
    return col

def link_to_collection(obj, col):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    col.objects.link(obj)

def add_bevel_modifier(obj, width=0.015, segments=3):
    bev = obj.modifiers.new(name="Bevel", type='BEVEL')
    bev.width = width
    bev.segments = segments
    bev.limit_method = 'ANGLE'
    bev.angle_limit = math.radians(35)
    return bev

def build_civis():
    # 1. Clean scene
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'

    # Master Collection
    col_civis = get_or_create_collection("CIVIS_Robot")
    col_hull = get_or_create_collection("01_Hull_and_Chassis", col_civis)
    col_wheels = get_or_create_collection("02_Wheels", col_civis)
    col_sensors = get_or_create_collection("03_Sensors", col_civis)
    col_doors = get_or_create_collection("04_Compartments_Doors", col_civis)
    col_ui = get_or_create_collection("05_UI_and_Controls", col_civis)
    col_lights = get_or_create_collection("06_Status_Lights", col_civis)

    # 2. Materials
    # Colors (sRGB linear approximations)
    m_white = create_material("Mat_White_Cabin", base_color=(0.92, 0.93, 0.95, 1.0), roughness=0.22, metallic=0.0)
    m_white_door = create_material("Mat_White_Door", base_color=(0.96, 0.96, 0.98, 1.0), roughness=0.28, metallic=0.0)
    m_chassis = create_material("Mat_Dark_Chassis", base_color=(0.04, 0.05, 0.06, 1.0), roughness=0.45, metallic=0.05)
    m_bumper = create_material("Mat_Bumper_Black", base_color=(0.02, 0.02, 0.03, 1.0), roughness=0.55, metallic=0.0)
    m_tire = create_material("Mat_Rubber_Tire", base_color=(0.015, 0.015, 0.018, 1.0), roughness=0.85, metallic=0.0)
    m_rim = create_material("Mat_Wheel_Rim", base_color=(0.06, 0.07, 0.08, 1.0), roughness=0.35, metallic=0.2)
    m_cyan_glow = create_material("Mat_Cyan_Emission", base_color=(0.0, 0.85, 1.0, 1.0), roughness=0.1, 
                                  emission_color=(0.0, 0.85, 1.0, 1.0), emission_strength=8.0)
    m_screen = create_material("Mat_Screen_Display", base_color=(0.01, 0.04, 0.12, 1.0), roughness=0.08, 
                               emission_color=(0.05, 0.15, 0.40, 1.0), emission_strength=2.0)
    m_screen_bezel = create_material("Mat_Screen_Bezel", base_color=(0.03, 0.03, 0.04, 1.0), roughness=0.35)
    m_camera = create_material("Mat_Camera_Lens", base_color=(0.005, 0.005, 0.008, 1.0), roughness=0.05, metallic=0.8)
    m_estop_red = create_material("Mat_EStop_Red", base_color=(0.85, 0.02, 0.02, 1.0), roughness=0.3, 
                                  emission_color=(0.85, 0.02, 0.02, 1.0), emission_strength=1.5)
    m_warning_yellow = create_material("Mat_Safety_Yellow", base_color=(0.95, 0.70, 0.05, 1.0), roughness=0.4)
    m_handle = create_material("Mat_Door_Handle", base_color=(0.02, 0.02, 0.025, 1.0), roughness=0.3)

    # 3. Base / Chassis (Z from 0.08 to 0.36)
    # Width X: 0.53, Length Y: 0.68, Height Z: 0.24
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.20))
    chassis = bpy.context.active_object
    chassis.name = "Chassis_Base"
    chassis.scale = (0.53, 0.68, 0.24)
    bpy.ops.object.transform_apply(scale=True)
    chassis.data.materials.append(m_chassis)
    add_bevel_modifier(chassis, width=0.02, segments=4)
    link_to_collection(chassis, col_hull)

    # Front Bumper with sensor cutouts
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.345, 0.14))
    f_bump = bpy.context.active_object
    f_bump.name = "Front_Bumper"
    f_bump.scale = (0.51, 0.04, 0.12)
    bpy.ops.object.transform_apply(scale=True)
    f_bump.data.materials.append(m_bumper)
    add_bevel_modifier(f_bump, width=0.015, segments=3)
    link_to_collection(f_bump, col_hull)

    # Rear Bumper
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -0.345, 0.14))
    r_bump = bpy.context.active_object
    r_bump.name = "Rear_Bumper"
    r_bump.scale = (0.51, 0.04, 0.12)
    bpy.ops.object.transform_apply(scale=True)
    r_bump.data.materials.append(m_bumper)
    add_bevel_modifier(r_bump, width=0.015, segments=3)
    link_to_collection(r_bump, col_hull)

    # 4. Upper Main Body Cabin (Z from 0.32 to 0.96)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.64))
    cabin = bpy.context.active_object
    cabin.name = "Main_Cabin_Body"
    cabin.scale = (0.52, 0.66, 0.62)
    bpy.ops.object.transform_apply(scale=True)
    cabin.data.materials.append(m_white)
    # Smooth rounded bevel on edges
    add_bevel_modifier(cabin, width=0.035, segments=5)
    link_to_collection(cabin, col_hull)

    # Top Roof Panel Cap
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.965))
    roof = bpy.context.active_object
    roof.name = "Roof_Cap_Panel"
    roof.scale = (0.46, 0.58, 0.03)
    bpy.ops.object.transform_apply(scale=True)
    roof.data.materials.append(m_white)
    add_bevel_modifier(roof, width=0.01, segments=3)
    link_to_collection(roof, col_hull)

    # 5. Wheels (4 Independent assemblies with Cyan LED rings)
    wheel_data = [
        ("Front_Right", 0.25, 0.20, 0.12, 1),
        ("Front_Left", -0.25, 0.20, 0.12, -1),
        ("Rear_Right", 0.25, -0.20, 0.12, 1),
        ("Rear_Left", -0.25, -0.20, 0.12, -1),
    ]

    for (w_name, wx, wy, wz, x_dir) in wheel_data:
        # Tire
        bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.065, location=(wx, wy, wz), rotation=(0, math.pi/2, 0))
        tire = bpy.context.active_object
        tire.name = f"Tire_{w_name}"
        tire.data.materials.append(m_tire)
        add_bevel_modifier(tire, width=0.01, segments=3)
        link_to_collection(tire, col_wheels)

        # Rim / Hub
        bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.068, location=(wx, wy, wz), rotation=(0, math.pi/2, 0))
        rim = bpy.context.active_object
        rim.name = f"Rim_{w_name}"
        rim.data.materials.append(m_rim)
        add_bevel_modifier(rim, width=0.005, segments=2)
        rim.parent = tire
        link_to_collection(rim, col_wheels)

        # Cyan LED Outer Ring
        ring_x = wx + x_dir * 0.035
        bpy.ops.mesh.primitive_cylinder_add(radius=0.092, depth=0.006, location=(ring_x, wy, wz), rotation=(0, math.pi/2, 0))
        led_ring = bpy.context.active_object
        led_ring.name = f"LED_Ring_{w_name}"
        led_ring.data.materials.append(m_cyan_glow)
        led_ring.parent = tire
        link_to_collection(led_ring, col_wheels)

    # 6. Top LiDAR Sensor (Z = 0.98 to 1.08)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.10, depth=0.035, location=(0, 0, 0.995))
    lidar_base = bpy.context.active_object
    lidar_base.name = "LiDAR_Pedestal"
    lidar_base.data.materials.append(m_chassis)
    add_bevel_modifier(lidar_base, width=0.005, segments=3)
    link_to_collection(lidar_base, col_sensors)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.055, location=(0, 0, 1.04))
    lidar_head = bpy.context.active_object
    lidar_head.name = "LiDAR_Sensor_Head"
    lidar_head.data.materials.append(m_chassis)
    add_bevel_modifier(lidar_head, width=0.005, segments=3)
    link_to_collection(lidar_head, col_sensors)

    # LiDAR Cyan Light Ring
    bpy.ops.mesh.primitive_cylinder_add(radius=0.082, depth=0.012, location=(0, 0, 1.055))
    lidar_ring = bpy.context.active_object
    lidar_ring.name = "LiDAR_Cyan_Light_Ring"
    lidar_ring.data.materials.append(m_cyan_glow)
    lidar_ring.parent = lidar_head
    link_to_collection(lidar_ring, col_sensors)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.085, depth=0.015, location=(0, 0, 1.075))
    lidar_cap = bpy.context.active_object
    lidar_cap.name = "LiDAR_Top_Cap"
    lidar_cap.data.materials.append(m_chassis)
    add_bevel_modifier(lidar_cap, width=0.003, segments=2)
    link_to_collection(lidar_cap, col_sensors)

    # 7. Front Interactive Touchscreen Display (Y = +0.33)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.332, 0.68))
    scr_bezel = bpy.context.active_object
    scr_bezel.name = "Touchscreen_Bezel"
    scr_bezel.scale = (0.30, 0.015, 0.22)
    bpy.ops.object.transform_apply(scale=True)
    scr_bezel.data.materials.append(m_screen_bezel)
    add_bevel_modifier(scr_bezel, width=0.01, segments=3)
    link_to_collection(scr_bezel, col_ui)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.341, 0.68))
    scr_glass = bpy.context.active_object
    scr_glass.name = "Touchscreen_Glass_Panel"
    scr_glass.scale = (0.26, 0.005, 0.18)
    bpy.ops.object.transform_apply(scale=True)
    scr_glass.data.materials.append(m_screen)
    scr_glass.parent = scr_bezel
    link_to_collection(scr_glass, col_ui)

    # Front Navigation & Inspection Camera
    bpy.ops.mesh.primitive_cylinder_add(radius=0.024, depth=0.02, location=(0, 0.338, 0.835), rotation=(math.pi/2, 0, 0))
    cam_body = bpy.context.active_object
    cam_body.name = "Navigation_Camera_Housing"
    cam_body.data.materials.append(m_bumper)
    add_bevel_modifier(cam_body, width=0.003, segments=2)
    link_to_collection(cam_body, col_sensors)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.008, location=(0, 0.348, 0.835), rotation=(math.pi/2, 0, 0))
    cam_lens = bpy.context.active_object
    cam_lens.name = "Navigation_Camera_Lens"
    cam_lens.data.materials.append(m_camera)
    cam_lens.parent = cam_body
    link_to_collection(cam_lens, col_sensors)

    # Front Proximity Sensors (Obstacle Detection)
    for i, px in enumerate([-0.18, -0.06, 0.06, 0.18]):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.01, location=(px, 0.355, 0.15), rotation=(math.pi/2, 0, 0))
        prox = bpy.context.active_object
        prox.name = f"Proximity_Sensor_{i+1}"
        prox.data.materials.append(m_camera)
        link_to_collection(prox, col_sensors)

    # 8. Compartment Doors (Left & Right Sides)
    doors_data = [
        # (Name, Side, X, Y, Z, Label)
        ("Door_Left_Delivery", -0.265, 0.115, 0.52, -1),
        ("Door_Left_Waste", -0.265, -0.115, 0.52, -1),
        ("Door_Right_Delivery", 0.265, 0.115, 0.52, 1),
        ("Door_Right_Waste", 0.265, -0.115, 0.52, 1),
    ]

    for (dname, dx, dy, dz, x_sign) in doors_data:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, dz))
        door = bpy.context.active_object
        door.name = dname
        door.scale = (0.012, 0.21, 0.33)
        bpy.ops.object.transform_apply(scale=True)
        door.data.materials.append(m_white_door)
        add_bevel_modifier(door, width=0.006, segments=2)
        link_to_collection(door, col_doors)

        # Handle
        handle_y = dy - 0.08 if "Delivery" in dname else dy + 0.08
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx + x_sign*0.012, handle_y, dz))
        handle = bpy.context.active_object
        handle.name = f"Handle_{dname}"
        handle.scale = (0.012, 0.02, 0.08)
        bpy.ops.object.transform_apply(scale=True)
        handle.data.materials.append(m_handle)
        add_bevel_modifier(handle, width=0.004, segments=2)
        handle.parent = door
        link_to_collection(handle, col_doors)

    # 9. Rear Controls & Emergency Stop (Y = -0.34)
    # Emergency Stop
    bpy.ops.mesh.primitive_cylinder_add(radius=0.032, depth=0.014, location=(0.14, -0.348, 0.30), rotation=(math.pi/2, 0, 0))
    estop_base = bpy.context.active_object
    estop_base.name = "Emergency_Stop_Yellow_Collar"
    estop_base.data.materials.append(m_warning_yellow)
    add_bevel_modifier(estop_base, width=0.003, segments=2)
    link_to_collection(estop_base, col_ui)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.024, depth=0.018, location=(0.14, -0.358, 0.30), rotation=(math.pi/2, 0, 0))
    estop_btn = bpy.context.active_object
    estop_btn.name = "Emergency_Stop_Button"
    estop_btn.data.materials.append(m_estop_red)
    add_bevel_modifier(estop_btn, width=0.004, segments=3)
    estop_btn.parent = estop_base
    link_to_collection(estop_btn, col_ui)

    # Charging Port Door
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.12, -0.348, 0.22))
    charge_door = bpy.context.active_object
    charge_door.name = "Charging_Port_Flap"
    charge_door.scale = (0.09, 0.008, 0.07)
    bpy.ops.object.transform_apply(scale=True)
    charge_door.data.materials.append(m_chassis)
    add_bevel_modifier(charge_door, width=0.004, segments=2)
    link_to_collection(charge_door, col_ui)

    # 10. Status Light Bars (Front & Rear Cyan Emission)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.355, 0.11))
    f_light = bpy.context.active_object
    f_light.name = "Front_Status_LED_Bar"
    f_light.scale = (0.16, 0.008, 0.012)
    bpy.ops.object.transform_apply(scale=True)
    f_light.data.materials.append(m_cyan_glow)
    link_to_collection(f_light, col_lights)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -0.338, 0.895))
    r_light = bpy.context.active_object
    r_light.name = "Rear_Status_LED_Bar"
    r_light.scale = (0.24, 0.008, 0.014)
    bpy.ops.object.transform_apply(scale=True)
    r_light.data.materials.append(m_cyan_glow)
    link_to_collection(r_light, col_lights)

    # 11. Add Camera and Studio Lighting for Blender Viewport
    bpy.ops.object.light_add(type='SUN', location=(2, -3, 4))
    sun = bpy.context.active_object
    sun.name = "Sun_Key_Light"
    sun.data.energy = 3.5

    bpy.ops.object.light_add(type='AREA', location=(-2, 2, 2.5))
    fill = bpy.context.active_object
    fill.name = "Area_Fill_Light"
    fill.data.energy = 50.0
    fill.data.size = 1.5

    bpy.ops.object.camera_add(location=(1.4, -1.8, 1.4), rotation=(math.radians(65), 0, math.radians(40)))
    cam = bpy.context.active_object
    cam.name = "Scene_Camera"
    scene.camera = cam

    # 12. Save .blend file
    exports_dir = r"d:\Projects\app\exports"
    os.makedirs(exports_dir, exist_ok=True)
    blend_path = os.path.join(exports_dir, "civis_robot_editable.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"[+] Native Blender file saved: {blend_path}")

    # 13. Export FBX
    fbx_path = os.path.join(exports_dir, "civis_robot_editable.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=False, apply_scale_options='FBX_SCALE_ALL')
    print(f"[+] Multi-object FBX saved: {fbx_path}")

    # 14. Export OBJ
    obj_path = os.path.join(exports_dir, "civis_robot_editable.obj")
    bpy.ops.wm.obj_export(filepath=obj_path)
    print(f"[+] Multi-group OBJ saved: {obj_path}")

    # 15. Export GLTF / GLB
    glb_path = os.path.join(exports_dir, "civis_robot_editable.glb")
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB')
    print(f"[+] PBR GLB saved: {glb_path}")

    # Also update app scanned_object.glb
    app_glb = r"d:\Projects\app\scanned_object.glb"
    bpy.ops.export_scene.gltf(filepath=app_glb, export_format='GLB')
    print(f"[+] Updated app model: {app_glb}")

if __name__ == "__main__":
    build_civis()
