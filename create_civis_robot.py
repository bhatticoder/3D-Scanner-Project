"""
Generate a detailed 3D GLB model of the CIVIS Autonomous Service Robot
matching dimensions: Length 70cm (0.7m), Width 55cm (0.55m), Height 110cm (1.1m).
Includes:
- Dark lower chassis & wheel wells
- 4 Wheels with blue LED accents
- White main body cabin
- Front touchscreen and navigation camera
- Top 360 LiDAR scanner dome with cyan illumination ring
- Side compartment doors (Waste & Delivery)
- Rear emergency stop, charging port, and rear status light
- Front obstacle proximity sensors
"""

import numpy as np
import trimesh
from trimesh.visual import ColorVisuals

def create_civis_robot():
    scene = trimesh.Scene()

    def set_color(mesh, rgba):
        colors = np.tile(rgba, (len(mesh.faces), 1))
        mesh.visual = ColorVisuals(mesh, face_colors=colors)
        return mesh

    # Colors (RGBA)
    C_WHITE_BODY = [240, 242, 245, 255]
    C_WHITE_PANEL = [252, 252, 254, 255]
    C_DARK_CHASSIS = [38, 42, 48, 255]
    C_DARK_BUMPER = [28, 30, 35, 255]
    C_WHEEL_TIRE = [20, 20, 22, 255]
    C_WHEEL_HUB = [45, 48, 54, 255]
    C_CYAN_LED = [0, 200, 255, 255]
    C_SCREEN_BLUE = [15, 30, 65, 255]
    C_SCREEN_GLASS = [10, 15, 25, 255]
    C_CAMERA_LENS = [10, 10, 10, 255]
    C_LIDAR_BASE = [30, 32, 36, 255]
    C_LIDAR_GLASS = [15, 25, 35, 255]
    C_RED_ESTOP = [220, 35, 35, 255]
    C_YELLOW_WARN = [245, 180, 20, 255]
    C_DOOR_HANDLE = [20, 22, 26, 255]
    C_SENSOR_LENS = [15, 18, 22, 255]

    # Dimensions
    # Width = 0.55m (X: -0.275 to +0.275)
    # Length = 0.70m (Z: -0.35 to +0.35)
    # Height = 1.10m (Y: 0.0 to 1.10)

    # 1. Lower Chassis (Base)
    # Y from 0.08 to 0.35
    chassis = trimesh.creation.box(extents=[0.53, 0.26, 0.68])
    chassis.apply_translation([0, 0.21, 0])
    set_color(chassis, C_DARK_CHASSIS)
    scene.add_geometry(chassis, node_name="Chassis")

    # Front & Rear Bumpers
    f_bumper = trimesh.creation.box(extents=[0.51, 0.12, 0.04])
    f_bumper.apply_translation([0, 0.14, 0.345])
    set_color(f_bumper, C_DARK_BUMPER)
    scene.add_geometry(f_bumper, node_name="FrontBumper")

    r_bumper = trimesh.creation.box(extents=[0.51, 0.12, 0.04])
    r_bumper.apply_translation([0, 0.14, -0.345])
    set_color(r_bumper, C_DARK_BUMPER)
    scene.add_geometry(r_bumper, node_name="RearBumper")

    # 2. Main White Upper Body Cabin (Y from 0.34 to 0.96)
    main_body = trimesh.creation.box(extents=[0.52, 0.62, 0.66])
    main_body.apply_translation([0, 0.65, 0])
    set_color(main_body, C_WHITE_BODY)
    scene.add_geometry(main_body, node_name="MainBody")

    # Rounded Upper Cap
    roof_cap = trimesh.creation.box(extents=[0.48, 0.04, 0.60])
    roof_cap.apply_translation([0, 0.97, 0])
    set_color(roof_cap, C_WHITE_PANEL)
    scene.add_geometry(roof_cap, node_name="RoofCap")

    # 3. Four Wheels with cyan accent rings
    wheel_radius = 0.12
    wheel_width = 0.06
    # Wheel positions: X = +-0.25, Y = 0.12, Z = +-0.21
    wheel_positions = [
        ([0.25, 0.12, 0.20], "FrontRight"),
        ([-0.25, 0.12, 0.20], "FrontLeft"),
        ([0.25, 0.12, -0.20], "RearRight"),
        ([-0.25, 0.12, -0.20], "RearLeft"),
    ]

    for (pos, name) in wheel_positions:
        # Tire (cylinder aligned along X-axis)
        tire = trimesh.creation.cylinder(radius=wheel_radius, height=wheel_width, sections=24)
        rot = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1])
        tire.apply_transform(rot)
        tire.apply_translation(pos)
        set_color(tire, C_WHEEL_TIRE)
        scene.add_geometry(tire, node_name=f"Tire_{name}")

        # Hubcap
        hub = trimesh.creation.cylinder(radius=wheel_radius * 0.75, height=wheel_width + 0.005, sections=24)
        hub.apply_transform(rot)
        hub.apply_translation(pos)
        set_color(hub, C_WHEEL_HUB)
        scene.add_geometry(hub, node_name=f"Hub_{name}")

        # Cyan LED Ring on outer face
        sign_x = 1 if pos[0] > 0 else -1
        ring_pos = [pos[0] + sign_x * (wheel_width / 2 + 0.003), pos[1], pos[2]]
        ring = trimesh.creation.cylinder(radius=wheel_radius * 0.76, height=0.004, sections=24)
        ring.apply_transform(rot)
        ring.apply_translation(ring_pos)
        set_color(ring, C_CYAN_LED)
        scene.add_geometry(ring, node_name=f"LedRing_{name}")

    # 4. Top LiDAR Sensor Unit (360 scanning)
    # Centered at top: X=0, Y=0.99 to 1.08, Z=0
    lidar_pedestal = trimesh.creation.cylinder(radius=0.10, height=0.03, sections=24)
    lidar_pedestal.apply_translation([0, 0.995, 0])
    set_color(lidar_pedestal, C_LIDAR_BASE)
    scene.add_geometry(lidar_pedestal, node_name="LiDARPedestal")

    lidar_body = trimesh.creation.cylinder(radius=0.08, height=0.06, sections=24)
    lidar_body.apply_translation([0, 1.04, 0])
    set_color(lidar_body, C_LIDAR_GLASS)
    scene.add_geometry(lidar_body, node_name="LiDARBody")

    lidar_ring = trimesh.creation.cylinder(radius=0.082, height=0.012, sections=24)
    lidar_ring.apply_translation([0, 1.055, 0])
    set_color(lidar_ring, C_CYAN_LED)
    scene.add_geometry(lidar_ring, node_name="LiDARCyanRing")

    lidar_cap = trimesh.creation.cylinder(radius=0.085, height=0.015, sections=24)
    lidar_cap.apply_translation([0, 1.075, 0])
    set_color(lidar_cap, C_LIDAR_BASE)
    scene.add_geometry(lidar_cap, node_name="LiDARCap")

    # 5. Front Display Screen Panel (Z = +0.33)
    # Bezel
    screen_bezel = trimesh.creation.box(extents=[0.30, 0.22, 0.02])
    screen_bezel.apply_translation([0, 0.68, 0.33])
    set_color(screen_bezel, C_DARK_CHASSIS)
    scene.add_geometry(screen_bezel, node_name="ScreenBezel")

    # Active Touchscreen Glass
    screen_glass = trimesh.creation.box(extents=[0.26, 0.18, 0.01])
    screen_glass.apply_translation([0, 0.68, 0.342])
    set_color(screen_glass, C_SCREEN_BLUE)
    scene.add_geometry(screen_glass, node_name="Touchscreen")

    # Front Camera (Navigation & Inspection)
    cam_housing = trimesh.creation.cylinder(radius=0.025, height=0.025, sections=16)
    rot_x = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
    cam_housing.apply_transform(rot_x)
    cam_housing.apply_translation([0, 0.84, 0.335])
    set_color(cam_housing, C_DARK_BUMPER)
    scene.add_geometry(cam_housing, node_name="CameraHousing")

    cam_lens = trimesh.creation.cylinder(radius=0.016, height=0.008, sections=16)
    cam_lens.apply_transform(rot_x)
    cam_lens.apply_translation([0, 0.84, 0.348])
    set_color(cam_lens, C_CAMERA_LENS)
    scene.add_geometry(cam_lens, node_name="CameraLens")

    # Front Proximity Sensors (Obstacle Detection)
    for px in [-0.18, -0.06, 0.06, 0.18]:
        prox = trimesh.creation.cylinder(radius=0.012, height=0.01, sections=12)
        prox.apply_transform(rot_x)
        prox.apply_translation([px, 0.15, 0.348])
        set_color(prox, C_SENSOR_LENS)
        scene.add_geometry(prox, node_name=f"ProximitySensor_{px}")

    # Front Status LED Light Bar
    f_led_bar = trimesh.creation.box(extents=[0.16, 0.012, 0.008])
    f_led_bar.apply_translation([0, 0.11, 0.348])
    set_color(f_led_bar, C_CYAN_LED)
    scene.add_geometry(f_led_bar, node_name="FrontLEDBar")

    # 6. Side Compartments & Doors (Left & Right)
    # Left Side: Delivery & Waste (X = -0.265)
    # Door Panels
    left_door1 = trimesh.creation.box(extents=[0.01, 0.34, 0.22])
    left_door1.apply_translation([-0.263, 0.52, 0.12])
    set_color(left_door1, C_WHITE_PANEL)
    scene.add_geometry(left_door1, node_name="LeftDoorDelivery")

    left_door2 = trimesh.creation.box(extents=[0.01, 0.34, 0.22])
    left_door2.apply_translation([-0.263, 0.52, -0.12])
    set_color(left_door2, C_WHITE_PANEL)
    scene.add_geometry(left_door2, node_name="LeftDoorWaste")

    # Door Handles
    h1 = trimesh.creation.box(extents=[0.015, 0.08, 0.018])
    h1.apply_translation([-0.27, 0.50, 0.015])
    set_color(h1, C_DOOR_HANDLE)
    scene.add_geometry(h1, node_name="LeftHandleDelivery")

    h2 = trimesh.creation.box(extents=[0.015, 0.08, 0.018])
    h2.apply_translation([-0.27, 0.50, -0.015])
    set_color(h2, C_DOOR_HANDLE)
    scene.add_geometry(h2, node_name="LeftHandleWaste")

    # Right Side: Waste & Delivery (X = +0.265)
    right_door1 = trimesh.creation.box(extents=[0.01, 0.34, 0.22])
    right_door1.apply_translation([0.263, 0.52, 0.12])
    set_color(right_door1, C_WHITE_PANEL)
    scene.add_geometry(right_door1, node_name="RightDoorDelivery")

    right_door2 = trimesh.creation.box(extents=[0.01, 0.34, 0.22])
    right_door2.apply_translation([0.263, 0.52, -0.12])
    set_color(right_door2, C_WHITE_PANEL)
    scene.add_geometry(right_door2, node_name="RightDoorWaste")

    rh1 = trimesh.creation.box(extents=[0.015, 0.08, 0.018])
    rh1.apply_translation([0.27, 0.50, 0.015])
    set_color(rh1, C_DOOR_HANDLE)
    scene.add_geometry(rh1, node_name="RightHandleDelivery")

    rh2 = trimesh.creation.box(extents=[0.015, 0.08, 0.018])
    rh2.apply_translation([0.27, 0.50, -0.015])
    set_color(rh2, C_DOOR_HANDLE)
    scene.add_geometry(rh2, node_name="RightHandleWaste")

    # 7. Rear Face (Z = -0.34)
    # Rear Top Status Light
    r_status_led = trimesh.creation.box(extents=[0.24, 0.015, 0.008])
    r_status_led.apply_translation([0, 0.90, -0.334])
    set_color(r_status_led, C_CYAN_LED)
    scene.add_geometry(r_status_led, node_name="RearStatusLight")

    # Emergency Stop Button
    estop_base = trimesh.creation.cylinder(radius=0.03, height=0.015, sections=20)
    estop_base.apply_transform(rot_x)
    estop_base.apply_translation([0.14, 0.30, -0.342])
    set_color(estop_base, C_YELLOW_WARN)
    scene.add_geometry(estop_base, node_name="EmergencyStopBase")

    estop_btn = trimesh.creation.cylinder(radius=0.022, height=0.018, sections=20)
    estop_btn.apply_transform(rot_x)
    estop_btn.apply_translation([0.14, 0.30, -0.352])
    set_color(estop_btn, C_RED_ESTOP)
    scene.add_geometry(estop_btn, node_name="EmergencyStopButton")

    # Charging Port Flap
    charge_flap = trimesh.creation.box(extents=[0.08, 0.06, 0.01])
    charge_flap.apply_translation([-0.12, 0.22, -0.342])
    set_color(charge_flap, C_DARK_CHASSIS)
    scene.add_geometry(charge_flap, node_name="ChargingPort")

    return scene

if __name__ == "__main__":
    import os
    print("Generating CIVIS 3D model...")
    scene = create_civis_robot()
    
    # Save GLB
    out_glb = "d:/Projects/app/scanned_object.glb"
    scene.export(out_glb)
    print(f"Exported: {out_glb} ({os.path.getsize(out_glb)} bytes)")

    # Save to exports/
    exports_dir = "d:/Projects/app/exports"
    os.makedirs(exports_dir, exist_ok=True)
    civis_glb = os.path.join(exports_dir, "civis_robot.glb")
    scene.export(civis_glb)
    print(f"Exported: {civis_glb}")

    # Export OBJ and STL for Blender
    mesh = scene.dump(concatenate=True)
    civis_obj = os.path.join(exports_dir, "civis_robot.obj")
    mesh.export(civis_obj)
    print(f"Exported: {civis_obj}")

    civis_stl = os.path.join(exports_dir, "civis_robot.stl")
    mesh.export(civis_stl)
    print(f"Exported: {civis_stl}")

    print("CIVIS 3D robot model ready for Blender & Viewer!")
