"""Render preview PNGs of the model built by model.py.

Run headless from the repo root (after model.py):
    blender --background --factory-startup --python models/weapons/grenade_launcher/preview.py

Opens <folder>.blend next to this script and writes <folder>_<view>.png alongside it.
The .blend is never saved; cameras and lights exist only for the render.
Model-agnostic: the model name comes from the folder, so this file can be copied as-is.

View names follow Blender's viewport convention (character faces -Y):
    front = seen from -Y, right = seen from +X, left = seen from -X.

Optional metadata written by model.py (read generically; nothing model-specific lives here):
    armature["preview_poses"]       JSON {pose: {bone: {"rot": [x, y, z] deg, "loc": [x, y, z]}}}
                                    -> <folder>_pose_<pose>.png from the front_left camera
    armature["preview_pose_views"]  JSON {pose: [view, ...]} -> <folder>_pose_<pose>_<view>.png from each
                                    listed view instead (e.g. front, back, front_left, rear_right)
    scene["preview_team_colors"]    JSON {team: {material: [r, g, b]}} -> <folder>_team_<team>.png
    scene["preview_variants"]       JSON {slot: {"default": name, "objects": {variant: mesh}}} -> for each
                                    variant, only its mesh shown in that slot: <folder>_<slot>_<variant>.png
                                    (3/4 close-up framed on it), _side.png (profile) and _full.png (whole
                                    character, 3/4)
    scene["preview_solo"]           JSON {tag: {"objects": [mesh, ...], "pose": {bone: {"rot": ...}}, "views":
                                    [view, ...]}} -> those meshes alone (every other mesh hidden; they may
                                    be hidden from the other renders), their armature posed:
                                    <folder>_<tag>_<view>.png framed on them (e.g. a weapon's projectile)
    scene["preview_frame"]          JSON {"lo": [x, y, z], "hi": [x, y, z]} -> frame the views on this box
                                    instead of on every renderable mesh (e.g. a prop set into a floor or
                                    wall, shown with a preview-only floor/wall mesh around it)
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
# Collider previews can call render_view without open_model; shared helpers
# must be importable in either entry path.
import sys
_models_root = next(p for p in HERE.parents if p.name == "models")
if str(_models_root) not in sys.path:
    sys.path.insert(0, str(_models_root))
NAME = HERE.name
BLEND_PATH = HERE / f"{NAME}.blend"

AXIS_RES = (1024, 1024)
CINEMATIC_RES = (1920, 1080)
CINEMATIC_LENS_MM = 70  # mild telephoto compression for a hero full-body read
MARGIN = 1.12  # breathing room around the silhouette

# name: (direction from subject to camera, projection, resolution). Named after the model's own sides: it faces
# -Y, so its left is +X (the "left" view shows its left side; Blender's viewport names are the other way round).
VIEWS = {
    "top": ((0, 0, 1), "ORTHO", AXIS_RES),
    "bottom": ((0, 0, -1), "ORTHO", AXIS_RES),
    "right": ((-1, 0, 0), "ORTHO", AXIS_RES),
    "left": ((1, 0, 0), "ORTHO", AXIS_RES),
    "front": ((0, -1, 0), "ORTHO", AXIS_RES),
    "back": ((0, 1, 0), "ORTHO", AXIS_RES),
    "front_left": ((1, -1, 0.35), "PERSP", CINEMATIC_RES),
    "rear_right": ((-1, 1, 0.35), "PERSP", CINEMATIC_RES),
}

# Three-point rig, expressed in camera space: (right, up, toward camera), energy.
LIGHTS = {
    "LGT_Key": ((-0.6, 0.7, 0.6), 4.5),
    "LGT_Fill": ((0.8, 0.1, 0.6), 0.9),
    "LGT_Rim": ((0.4, 0.6, -1.0), 4.0),
    "LGT_Kick": ((-0.9, 0.2, -0.5), 2.0),  # a second rim from the other side, to outline the silhouette
}


def attach_pack():
    """The ammo pack is its own model (<name>_ammo.blend, user): brought in and hung on the weapon's AmmoMount gizmo,
    where it rides the pack's bone through the actions and poses."""
    mount = bpy.data.objects.get("AmmoMount")
    path = HERE / f"{NAME}_ammo.blend"
    if mount is None or not path.exists():
        return
    with bpy.data.libraries.load(str(path)) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o)
        o.parent = mount
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Matrix.Identity(4)


def open_model():
    if not BLEND_PATH.exists():
        raise SystemExit(f"[{NAME}] {BLEND_PATH} not found - run model.py first")
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))
    import sys
    models=next(p for p in Path(__file__).resolve().parents if p.name=='models')
    sys.path.insert(0,str(models));sys.path.insert(0,str(models/'architecture'))
    from preview_gizmos import install
    from lunar_material import preview
    preview();install()

    attach_pack()


def setup_render():
    scene = bpy.context.scene
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    # Eevee is "BLENDER_EEVEE_NEXT" in 4.2-4.x and "BLENDER_EEVEE" otherwise.
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 64
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100

    if hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = True  # real reflections for stainless steel and titanium
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    build_studio(scene)


def build_studio(scene):
    """A photo studio: the camera sees a near-white sweep (dark paints and matte black read against it);
    everything else (lighting, reflections) sees a studio of grey walls, a darker floor, a bright strip
    light round the horizon and a softbox overhead, so stainless steel reads silver with crisp highlights instead
    of mirroring black."""
    world = scene.world or bpy.data.worlds.new("WLD_Preview")
    scene.world = world
    if world.node_tree is None:  # pre-5.x worlds; use_nodes is deprecated in 5.x
        world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    coord = nodes.new("ShaderNodeTexCoord")
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Generated"], xyz.inputs[0])

    def ramp(stops, interpolation="EASE"):
        r = nodes.new("ShaderNodeValToRGB")
        r.color_ramp.interpolation = interpolation
        els = r.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for el, (pos, col) in zip(els, stops):
            el.position, el.color = pos, (*col, 1.0)
        return r

    # Elevation (-1..1 -> 0..1) drives both gradients.
    lift = nodes.new("ShaderNodeMapRange")
    lift.inputs["From Min"].default_value, lift.inputs["From Max"].default_value = -1.0, 1.0
    links.new(xyz.outputs["Z"], lift.inputs["Value"])
    sweep = ramp([(0.0, (2.3, 2.45, 2.7)), (0.5, (3.0, 3.15, 3.4)), (1.0, (3.6, 3.75, 4.0))])
    studio = ramp([(0.0, (0.1, 0.1, 0.11)), (0.46, (0.22, 0.22, 0.23)), (0.5, (0.42, 0.42, 0.44)),
                   (0.56, (0.5, 0.5, 0.52)), (0.58, (4.0, 4.0, 3.9)), (0.66, (4.0, 4.0, 3.9)), (0.68, (0.55, 0.55, 0.57)),
                   (0.9, (0.6, 0.6, 0.62)), (0.94, (5.0, 5.0, 4.9)), (1.0, (5.0, 5.0, 4.9))], "LINEAR")
    for r in (sweep, studio):
        links.new(lift.outputs["Result"], r.inputs["Fac"])
    cam_bg, env_bg = nodes.new("ShaderNodeBackground"), nodes.new("ShaderNodeBackground")
    links.new(sweep.outputs["Color"], cam_bg.inputs["Color"])
    links.new(studio.outputs["Color"], env_bg.inputs["Color"])
    env_bg.inputs["Strength"].default_value = 1.2
    path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(env_bg.outputs["Background"], mix.inputs[1])
    links.new(cam_bg.outputs["Background"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])



def subject_bounds(objects=None):
    """Bounds of the renderable meshes (or of `objects`), as posed."""
    bpy.context.view_layer.update()
    if objects is None and "preview_frame" in bpy.context.scene:
        frame = json.loads(bpy.context.scene["preview_frame"])
        lo, hi = Vector(frame["lo"]), Vector(frame["hi"])
        return (lo + hi) / 2, [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    meshes = objects or [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]
    if not meshes:
        raise SystemExit(f"[{NAME}] no renderable meshes in {BLEND_PATH}")
    # Evaluated vertices, so posed armatures are framed as posed.
    corners = []
    for o in meshes:
        ev = o.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        corners += [ev.matrix_world @ v.co for v in mesh.vertices]
        ev.to_mesh_clear()
    lo = Vector(min(c[i] for c in corners) for i in range(3))
    hi = Vector(max(c[i] for c in corners) for i in range(3))
    # All 8 corners of the combined box, used for exact framing.
    box = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    return (lo + hi) / 2, box


def create_camera():
    cam_data = bpy.data.cameras.new("CAM_Preview")
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new("CAM_Preview", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def create_lights():
    lights = {}
    for name, (_, energy) in LIGHTS.items():
        data = bpy.data.lights.new(name, type="SUN")
        data.energy = energy
        data.angle = math.radians(8)  # soft-ish shadows
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        lights[name] = obj
    return lights


def orient_camera(cam, direction):
    """Point the camera along -direction; top/bottom get a fixed up so front reads at the bottom."""
    d = Vector(direction).normalized()
    if abs(d.z) > 0.999:
        cam.rotation_euler = (0.0, 0.0, 0.0) if d.z > 0 else (math.pi, 0.0, 0.0)
    else:
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


def frame_camera(cam, center, box, direction, projection, res, margin=MARGIN):
    """Place the camera so the whole bounding box fits the frame with `margin`."""
    rot = cam.rotation_euler.to_matrix()
    inv = rot.transposed()
    local = [inv @ (c - center) for c in box]  # box corners in camera axes, relative to center
    aspect = res[1] / res[0]
    d = Vector(direction).normalized()

    if projection == "ORTHO":
        cam.data.type = "ORTHO"
        width = max(abs(p.x) for p in local) * 2
        height = max(abs(p.y) for p in local) * 2
        cam.data.ortho_scale = max(width, height / aspect) * margin
        depth = max(abs(p.z) for p in local)
        distance = depth + 10.0
        cam.data.clip_end = distance + depth + 10.0
    else:
        cam.data.type = "PERSP"
        cam.data.lens = CINEMATIC_LENS_MM
        tan_x = (cam.data.sensor_width / 2) / cam.data.lens
        tan_y = tan_x * aspect
        # Corner at camera-space (x, y, z) fits when |x| <= (distance - z) * tan.
        distance = max(max(p.z + abs(p.x) * margin / tan_x, p.z + abs(p.y) * margin / tan_y) for p in local)
        cam.data.clip_end = distance * 4

    cam.data.clip_start = 0.01
    cam.location = center + d * distance


def aim_lights(lights, cam):
    rot = cam.rotation_euler.to_matrix()
    for name, (offset, _) in LIGHTS.items():
        from_dir = rot @ Vector(offset).normalized()
        lights[name].rotation_euler = (-from_dir).to_track_quat("-Z", "Y").to_euler()


def render_view(cam, lights, view, suffix=None, subject=None, margin=MARGIN):
    """Render one view; `subject` (mesh objects) frames the camera on those instead of everything."""
    scene = bpy.context.scene
    direction, projection, res = VIEWS[view]
    center, box = subject_bounds(subject)
    scene.render.resolution_x, scene.render.resolution_y = res
    orient_camera(cam, direction)
    frame_camera(cam, center, box, direction, projection, res, margin)
    aim_lights(lights, cam)

    out = HERE / f"{NAME}_{suffix or view}.png"
    scene.render.filepath = str(out)
    from preview_gizmos import face_labels
    face_labels(cam)
    bpy.ops.render.render(write_still=True)
    print(f"[{NAME}] rendered {out}")


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def render_poses(cam, lights):
    for rig in [o for o in bpy.context.scene.objects if o.type == "ARMATURE" and "preview_poses" in o]:
        pose_views = json.loads(rig["preview_pose_views"]) if "preview_pose_views" in rig else {}
        for pose, bones in json.loads(rig["preview_poses"]).items():
            apply_pose(rig, bones)
            if pose in pose_views:
                for view in pose_views[pose]:
                    render_view(cam, lights, view, f"pose_{pose}_{view}")
            else:
                render_view(cam, lights, "front_left", f"pose_{pose}")
        reset_pose(rig)


def render_teams(cam, lights):
    scene = bpy.context.scene
    if "preview_team_colors" not in scene:
        return

    def base_color(name):
        mat = bpy.data.materials[name]
        return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"]

    teams = json.loads(scene["preview_team_colors"])
    originals = {m: tuple(base_color(m).default_value) for colors in teams.values() for m in colors}
    for team, colors in teams.items():
        for mat, rgb in colors.items():
            base_color(mat).default_value = (*rgb, 1.0)
        render_view(cam, lights, "front_left", f"team_{team}")
    for mat, rgba in originals.items():
        base_color(mat).default_value = rgba


def apply_pose(rig, bones):
    reset_pose(rig)
    for bone, entry in bones.items():
        pb = rig.pose.bones[bone]
        if "rot" in entry:
            pb.rotation_mode = "XYZ" if pb.rotation_mode == "QUATERNION" else pb.rotation_mode
            pb.rotation_euler = [math.radians(a) for a in entry["rot"]]
        if "loc" in entry:
            pb.location = entry["loc"]



def render_variants(cam, lights):
    """Each variant of each swappable slot (e.g. heads) on its own: close-up, profile, full body."""
    scene = bpy.context.scene
    if "preview_variants" not in scene:
        return
    for slot, info in json.loads(scene["preview_variants"]).items():
        objects = {v: bpy.data.objects[name] for v, name in info["objects"].items()}
        shown = {v: o.hide_render for v, o in objects.items()}
        for variant, obj in objects.items():
            for o in objects.values():
                o.hide_render = o is not obj
            render_view(cam, lights, "front_left", f"{slot}_{variant}", subject=[obj], margin=1.9)
            render_view(cam, lights, "right", f"{slot}_{variant}_side", subject=[obj], margin=1.6)
            render_view(cam, lights, "front_left", f"{slot}_{variant}_full")
        for v, o in objects.items():
            o.hide_render = shown[v]


def render_solo(cam, lights):
    """Each solo subject on its own, posed, framed on it from its listed views."""
    scene = bpy.context.scene
    if "preview_solo" not in scene:
        return
    meshes = [o for o in scene.objects if o.type == "MESH"]
    shown = {o.name: o.hide_render for o in meshes}
    for tag, info in json.loads(scene["preview_solo"]).items():
        subject = [bpy.data.objects[n] for n in info["objects"]]
        for o in meshes:
            o.hide_render = o not in subject
        rigs = {o.find_armature() for o in subject} - {None}
        for rig in rigs:
            apply_pose(rig, info.get("pose", {}))
        for view in info.get("views", ["front_left"]):
            render_view(cam, lights, view, f"{tag}_{view}", subject=subject)
        for rig in rigs:
            reset_pose(rig)
    for o in meshes:
        o.hide_render = shown[o.name]


def render_views():
    cam = create_camera()
    lights = create_lights()
    for view in VIEWS:
        render_view(cam, lights, view)
    render_poses(cam, lights)
    render_teams(cam, lights)
    render_variants(cam, lights)
    from preview_gizmos import ghost_model,restore_model
    saved=ghost_model()
    render_view(cam, lights, "front_left", "gizmos")
    restore_model(saved)
    render_solo(cam, lights)


def main():
    open_model()
    setup_render()
    render_views()


if __name__ == "__main__":
    main()
