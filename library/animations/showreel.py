"""The showreel of Tensor's animation library (animations/target, built by retarget.py), rendered in the previews'
studio: every clip in turn, its name captioned, a static front-left camera following the hips
(user: no orbit, so the character's and the weapon's poses read).

Used by models/characters/tensor/animate.py (Tensor alone: his own clips and every weapon family's stance, no
weapon shown) and each weapon's animate.py (Tensor holding that weapon through all its clips, the weapon's own
bones playing their synced clips).
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

LIB = Path(__file__).resolve().parents[1]
TARGET = LIB / "animations" / "target"
CHAR = LIB / "models" / "characters" / "tensor"
WEAPONS = LIB / "models" / "weapons"
FPS = 30
RES = (1280, 720)
SAMPLES = 8
LOOP_MIN = 45     # a loop shorter than this (frames) plays twice, so its motion reads
GAP = 8           # frames the last pose holds between clips
# Tensor's own reel shows each weapon family's stance once, on these weapons.
FAMILY_REELS = (("rifle", "rifle stance"), ("pistol", "pistol stance"))   # (every long gun holds as the rifle family)


def manifest():
    path = TARGET / "manifest.json"
    if not path.exists():
        raise SystemExit("[showreel] no animations/target/manifest.json - run animations/retarget.py first")
    return json.loads(path.read_text())


def tensor_clips():
    """Tensor's reel: his own clips, then each family's stances (captioned by family, no weapon)."""
    man = manifest()
    out = [(k, k.split("/", 1)[1].replace("_", " ")) for k in man if k.startswith("common/")]
    for weapon, label in FAMILY_REELS:
        out += [(k, f"{label}: {k.split('/', 1)[1].replace('_', ' ')}") for k in man if k.startswith(f"{weapon}/")]
    return out, man


def weapon_clips(weapon):
    man = manifest()
    return [(k, k.split("/", 1)[1].replace("_", " ")) for k in man if k.startswith(f"{weapon}/")], man


def load_action(path):
    with bpy.data.libraries.load(str(path)) as (src, dst):
        dst.actions = list(src.actions)
    return dst.actions[0]


def build_studio(scene):
    """The previews' studio: the camera sees a near-white sweep; lighting and reflections see grey walls, a
    darker floor, a bright strip light round the horizon and a softbox overhead."""
    world = scene.world or bpy.data.worlds.new("WLD_Preview")
    scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    coord, xyz = nodes.new("ShaderNodeTexCoord"), nodes.new("ShaderNodeSeparateXYZ")
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
    path, mix = nodes.new("ShaderNodeLightPath"), nodes.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(env_bg.outputs["Background"], mix.inputs[1])
    links.new(cam_bg.outputs["Background"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])


def setup_scene(end, out_path):
    scene = bpy.context.scene
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = SAMPLES
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 0, end
    image = scene.render.image_settings
    if "media_type" in image.bl_rna.properties:
        image.media_type = "VIDEO"
    image.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.filepath = str(out_path)
    if hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = True
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    build_studio(scene)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    ground = bpy.context.active_object
    mat = bpy.data.materials.new("M_ShowreelGround")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.62, 0.63, 0.64, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    ground.data.materials.append(mat)
    for name, direction, energy in (("LGT_Key", (-1, -1, 1.3), 4.0), ("LGT_Fill", (1, -0.4, 0.5), 1.2),
                                    ("LGT_Rim", (0.4, 1, 0.9), 3.0), ("LGT_Kick", (1, 0.6, 0.4), 1.5)):
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, type="SUN"))
        light.data.energy, light.data.angle = energy, math.radians(6)
        light.rotation_euler = (-Vector(direction)).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(light)


def lay_strips(obj, items, track_name):
    """Clips end to end on one NLA track: [(start frame, action, repeat)]; each holds its last pose on."""
    obj.animation_data_create()
    obj.animation_data.action = None
    track = obj.animation_data.nla_tracks.new()
    track.name = track_name
    for start, act, repeat in items:
        strip = track.strips.new(act.name, int(start), act)
        if hasattr(strip, "action_slot") and act.slots:
            strip.action_slot = act.slots[0]
        strip.repeat = repeat
        strip.extrapolation = "HOLD_FORWARD"


def attach_pack(weapon):
    """The weapon's ammo pack is its own model (<weapon>_ammo.blend, user): brought in and hung on the weapon's
    AmmoMount gizmo, where it rides the pack's bone (a reload's release, carry and insert). Returns its objects."""
    mount = bpy.data.objects.get("AmmoMount")
    path = WEAPONS / weapon / f"{weapon}_ammo.blend"
    if mount is None or not path.exists():
        return []
    with bpy.data.libraries.load(str(path)) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o)
        o.parent = mount
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Matrix.Identity(4)
    return list(dst.objects)


def attach_weapon(rig, weapon):
    """The weapon's rig and meshes, riding the firing hand: its RightHandSocket frame (the hand bone's frame
    on the grip, from its _rig.json) on the RightHand bone."""
    wdir = WEAPONS / weapon
    with bpy.data.libraries.load(str(wdir / f"{weapon}.blend")) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(("SK_", "RIG_", "AmmoMount", "Muzzle"))]
    objs = [o for o in dst.objects if o is not None and not o.hide_render]
    body = next(o for o in objs if o.type == "MESH" and o.parent and o.parent.type == "ARMATURE")
    wrig = body.parent          # the weapon's own rig (a projectile weapon's file also holds the projectile's)
    objs = [o for o in objs if o.type != "ARMATURE" or o == wrig]
    objs = [o for o in objs if o.type != "MESH" or o.parent == wrig]
    objs = [o for o in objs if o.type != "EMPTY" or o.parent == wrig]
    for o in objs:
        bpy.context.scene.collection.objects.link(o)
    attach_pack(weapon)
    mag = wrig.pose.bones.get("Mag")
    for c in [c for c in mag.constraints if c.type == "LIMIT_LOCATION"] if mag else []:
        mag.constraints.remove(c)   # a reload carries the pack off its rails, in the hand (the clips place it)
    h = json.loads((wdir / f"{weapon}_rig.json").read_text())["hand_sockets"]["RightHandSocket"]
    sock = Matrix((h["bone_x_blender"], h["bone_y_blender"], h["bone_z_blender"])).transposed().to_4x4()
    sock.translation = h["wrist_blender"]
    con = wrig.constraints.new("CHILD_OF")
    con.target, con.subtarget = rig, "RightHand"
    con.inverse_matrix = Matrix.Identity(4)
    wrig.matrix_basis = sock.inverted()
    return wrig


def setup_camera(rig, end):
    scene = bpy.context.scene
    boom = bpy.data.objects.new("CAM_Boom", None)
    scene.collection.objects.link(boom)
    follow = boom.constraints.new("COPY_LOCATION")
    follow.target, follow.subtarget, follow.use_z = rig, "Hips", False
    boom.rotation_euler = (0, 0, math.radians(45))   # static at Tensor's front left (user: no orbit, so the poses read)
    target = bpy.data.objects.new("CAM_Target", None)
    scene.collection.objects.link(target)
    target.parent, target.location = boom, (0, 0, 0.9)
    cam = bpy.data.objects.new("CAM_Showreel", bpy.data.cameras.new("CAM_Showreel"))
    cam.data.lens, cam.data.sensor_width = 35, 36
    scene.collection.objects.link(cam)
    cam.parent, cam.location = boom, (0, -4.4, 1.3)
    aim = cam.constraints.new("TRACK_TO")
    aim.target, aim.track_axis, aim.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    scene.camera = cam
    return cam


def weapon_camera(wrig, weapon):
    """Pin the animated weapon at bottom right; the character rig stays invisible."""
    scene = bpy.context.scene
    cam = bpy.data.objects.new("CAM_FPS", bpy.data.cameras.new("CAM_FPS"))
    cam.data.lens, cam.data.sensor_width = 17.5, 36
    cam.data.clip_start, cam.data.clip_end = 0.01, 60.0
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (0, 0, 1.6)
    cam.rotation_euler = Vector((0, -1, 0)).to_track_quat("-Z", "Y").to_euler()
    if wrig:
        for constraint in list(wrig.constraints):
            wrig.constraints.remove(constraint)
        wrig.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        corners = []
        for obj in scene.objects:
            ancestor = obj.parent
            while ancestor is not None and ancestor != wrig:
                ancestor = ancestor.parent
            if obj.type == "MESH" and ancestor == wrig and not obj.hide_render:
                corners.extend(wrig.matrix_world.inverted() @ obj.matrix_world @ Vector(c) for c in obj.bound_box)
        lo = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
        hi = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
        center = (lo + hi) * 0.5
        orientation = cam.matrix_world.inverted().to_3x3() @ Matrix.Rotation(-0.35, 3, "Z")
        points = [orientation @ (Vector((x, y, z)) - center)
                  for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        half_x = cam.data.sensor_width / (2 * cam.data.lens)
        half_y = half_x * RES[1] / RES[0]
        x, y, width, height = (0.55, 0.69, 0.60, 0.74) if weapon == "lightning_gun" else (0.52, 0.64, 0.62, 0.74)
        left, right = (2 * x - 1) * half_x, (2 * (x + width) - 1) * half_x
        bottom, top = (1 - 2 * (y + height)) * half_y, (1 - 2 * y) * half_y
        depth = 1.1

        def limits(size):
            return (max(left * (depth - p.z * size) - p.x * size for p in points),
                    min(right * (depth - p.z * size) - p.x * size for p in points),
                    max(bottom * (depth - p.z * size) - p.y * size for p in points),
                    min(top * (depth - p.z * size) - p.y * size for p in points))

        small, large = 0.0, (depth - 0.055) / max(p.z for p in points)
        for _ in range(32):
            candidate = (small + large) * 0.5
            lx, rx, by, ty = limits(candidate)
            if lx <= rx and by <= ty:
                small = candidate
            else:
                large = candidate
        lx, rx, by, ty = limits(small)
        offset = Vector(((lx + rx) * 0.5, (by + ty) * 0.5, -depth))
        offset.x = (2 * 0.625 - 1) * half_x * depth
        wrig.matrix_world = (cam.matrix_world @ Matrix.Translation(offset) @ orientation.to_4x4()
                            @ Matrix.Scale(small, 4) @ Matrix.Translation(-center))
        pivot = wrig.matrix_world @ center
        target = cam.matrix_world @ Vector((0, 0, -20))
        muzzle = next(obj for obj in scene.objects if obj.name.startswith("Muzzle") and obj.parent == wrig)
        for _ in range(8):
            bpy.context.view_layer.update()
            forward = muzzle.matrix_world.to_3x3().col[1].normalized()
            desired = (target - muzzle.matrix_world.translation).normalized()
            rotation = forward.rotation_difference(desired).to_matrix().to_4x4()
            wrig.matrix_world = Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot) @ wrig.matrix_world
    return cam


def caption(cam, timeline, header):
    """The clip's name, lower left in the frame, updated every frame."""
    curve = bpy.data.curves.new("TXT_Caption", "FONT")
    curve.size, curve.body = 0.028, header
    txt = bpy.data.objects.new("TXT_Caption", curve)
    bpy.context.scene.collection.objects.link(txt)
    txt.parent = cam
    half = cam.data.sensor_width / 2 / cam.data.lens                   # the frame's half-width a metre ahead
    txt.location = (-0.955 * half, -0.93 * half * RES[1] / RES[0], -1.0)   # inside its lower left corner
    curve.size = 0.028 * half / 0.514
    mat = bpy.data.materials.new("M_Caption")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    curve.materials.append(mat)

    def update(scene, *_):
        f = scene.frame_current
        name = next((t for s, e, t in timeline if s <= f < e + GAP), timeline[-1][2] if timeline else "")
        curve.body = f"{header}   {name}"

    bpy.app.handlers.frame_change_pre.append(update)


def render(clips, man, out_path, header, weapon=None, dry=False, fps=False):
    """Every clip in turn on Tensor (and the weapon's synced clips on the weapon), rendered to out_path; with `fps`
    only the camera-pinned weapon is visible."""
    bpy.ops.wm.open_mainfile(filepath=str(CHAR / "tensor.blend"))
    rig = bpy.data.objects["RIG_Tensor"]
    if fps:                                   # (before the weapon comes in: only his own meshes)
        for o in bpy.context.scene.objects:
            if o.type == "MESH":
                o.hide_render = True
                o.hide_viewport = True
    wrig = attach_weapon(rig, weapon) if weapon else None
    t, items, witems, timeline = 0, [], [], []
    for key, title in clips:
        info = man[key]
        act = load_action(TARGET / "blend" / "tensor" / f"{key}.blend")
        n = info["frames"]
        repeat = max(2, math.ceil(24 / n)) if info["loop"] and n < LOOP_MIN else 1   # (an aim pose holds 24 frames)
        items.append((t, act, repeat))
        if wrig and info.get("weapon_file"):
            wact = load_action(TARGET / "blend" / "weapons" / f"{key}.blend")
            witems.append((t, wact, repeat))
        timeline.append((t, t + n * repeat, title))
        t += n * repeat + GAP
    end = max(t - GAP, 1)
    lay_strips(rig, items, "Showreel")
    if wrig:
        lay_strips(wrig, witems, "Showreel")
    setup_scene(end, out_path)
    cam = weapon_camera(wrig, weapon) if fps else setup_camera(rig, end)
    caption(cam, timeline, header)
    print(f"[showreel] {len(clips)} clips, {end} frames ({end / FPS:.0f} s) -> {out_path}")
    if dry:
        return
    bpy.ops.render.render(animation=True)
    print(f"[showreel] wrote {out_path}")
