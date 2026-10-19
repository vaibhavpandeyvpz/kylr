"""Render the weapon's three showcases (user: one of the weapon alone, one of it held, one from the FPS view):

  <folder>_showcase.mp4  the weapon on its own, turning once right round (the camera orbits 360 deg over the whole
                         video, the lights with it) while it plays all its own actions: scene["preview_actions"] in
                         order (each held at its last pose until the next takes over; the first held at its start
                         before it plays), then any of the rig's actions that list leaves out.
  <folder>_held.mp4      its showreel: Tensor holding it through every clip of its animation library (see
                         animations/showreel.py): the weapon riding his firing hand (its RightHandSocket on his
                         RightHand bone, as in the game), its own bones playing their synced clips; each clip captioned.
  <folder>_fps.mp4       camera-pinned weapon and animated machinery at bottom right.

Run headless from the repo root (the showcase after model.py, the held reel after Tensor's model.py and
animations/retarget.py):
    blender --background --factory-startup --python models/weapons/<name>/animate.py [-- showcase|held|fps] [--no-render]

Model-agnostic for weapons: the name comes from the folder. The .blend is never saved.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "animations"))
import showreel  # noqa: E402

NAME = HERE.name
BLEND_PATH = HERE / f"{NAME}.blend"
OUT = HERE / f"{NAME}_showcase.mp4"
HELD_OUT = HERE / f"{NAME}_held.mp4"
FPS_OUT = HERE / f"{NAME}_fps.mp4"
RES = (1280, 720)
LENS_MM = 50
GAP = 12            # frames between one action ending and the next starting
LEAD, TAIL = 18, 24  # frames held before the first action and after the last
LIGHTS = {"LGT_Key": ((-0.6, 0.7, 0.6), 4.0), "LGT_Fill": ((0.8, 0.1, 0.6), 1.2), "LGT_Rim": ((0.4, 0.6, -1.0), 3.0)}


def frame_box(scene):
    if "preview_frame" in scene:
        f = json.loads(scene["preview_frame"])
        return Vector(f["lo"]), Vector(f["hi"])
    pts = [o.matrix_world @ Vector(c) for o in scene.objects if o.type == "MESH" and not o.hide_render
           for c in o.bound_box]
    return (Vector(min(p[i] for p in pts) for i in range(3)), Vector(max(p[i] for p in pts) for i in range(3)))


def sequence(scene, rig, names):
    """One NLA track per action, stacked in play order, so each holds until the next overrides it."""
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    rig.animation_data.action = None
    start = LEAD
    for i, name in enumerate(names):
        action = bpy.data.actions[name]
        track = rig.animation_data.nla_tracks.new()
        track.name = f"showcase_{name}"
        strip = track.strips.new(name, int(start), action)
        strip.extrapolation = "HOLD" if i == 0 else "HOLD_FORWARD"
        print(f"[{NAME}] {name}: frames {int(start)}-{int(strip.frame_end)}")
        start = strip.frame_end + GAP
    scene.frame_start, scene.frame_end = 0, int(start - GAP + TAIL)


def rig_camera(scene, lo, hi):
    """The camera orbiting the weapon once, from its front left round and back (user: rotating 360 deg once), the
    studio lights turning with it so every side is lit as it comes round."""
    center = (lo + hi) / 2
    radius = (hi - lo).length / 2
    cam_data = bpy.data.cameras.new("CAM_Showcase")
    cam_data.lens, cam_data.sensor_width = LENS_MM, 36.0
    cam = bpy.data.objects.new("CAM_Showcase", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    tan_half = (cam_data.sensor_width / 2) / LENS_MM * RES[1] / RES[0]
    distance = radius * 1.08 / tan_half
    cam_data.clip_start, cam_data.clip_end = 0.01, distance * 4
    lights = []
    for name, (offset, energy) in LIGHTS.items():
        data = bpy.data.lights.new(name, type="SUN")
        data.energy, data.angle = energy, math.radians(8)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        lights.append((obj, Vector(offset).normalized()))
    base = math.atan2(-1, -1)                       # from its front left to start
    n = max(scene.frame_end - scene.frame_start, 1)
    for f in range(scene.frame_start, scene.frame_end + 1):
        az = base + 2 * math.pi * (f - scene.frame_start) / n
        d = Vector((math.cos(az), math.sin(az), 0.35)).normalized()
        cam.location = center + d * distance
        look = (-d).to_track_quat("-Z", "Y")
        cam.rotation_euler = look.to_euler()
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        rot = look.to_matrix()
        for obj, offset in lights:
            obj.rotation_euler = (-(rot @ offset)).to_track_quat("-Z", "Y").to_euler()
            obj.keyframe_insert("rotation_euler", frame=f)
    for o in [cam] + [obj for obj, _ in lights]:
        for fc in (o.animation_data.action.fcurves if hasattr(o.animation_data.action, "fcurves") else []):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def setup_render(scene):
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    world = scene.world or bpy.data.worlds.new("WLD_Showcase")
    scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.18, 0.19, 0.21, 1.0)
    bg.inputs["Strength"].default_value = 0.6
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.filepath = str(OUT)


def showcase(dry):
    if not BLEND_PATH.exists():
        raise SystemExit(f"[{NAME}] {BLEND_PATH} not found - run model.py first")
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))
    showreel.attach_pack(NAME)                                          # (the ammo pack is its own model)
    scene = bpy.context.scene
    names = json.loads(scene["preview_actions"]) if "preview_actions" in scene else []
    rig = next((o for o in scene.objects if o.type == "ARMATURE" and o.animation_data and names
                and any(t.name == names[0] for t in o.animation_data.nla_tracks)), None)
    if rig is None:
        raise SystemExit(f"[{NAME}] no animated armature / scene['preview_actions'] in {BLEND_PATH}")
    own = [t.name for t in rig.animation_data.nla_tracks if t.name in bpy.data.actions]
    names += [a for a in own if a not in names]                        # (every action the weapon has)
    sequence(scene, rig, names)
    lo, hi = frame_box(scene)
    rig_camera(scene, lo, hi)
    print(f"[{NAME}] showcase: frames {scene.frame_start}-{scene.frame_end} at {scene.render.fps} fps")
    if dry:
        return
    setup_render(scene)
    bpy.ops.render.render(animation=True)
    print(f"[{NAME}] rendered {OUT}")


def held(dry, fps=False):
    clips, man = showreel.weapon_clips(NAME)
    if not clips:
        raise SystemExit(f"[{NAME}] no clips for this weapon in animations/target - run animations/retarget.py first")
    showreel.render(clips, man, FPS_OUT if fps else HELD_OUT, NAME.replace("_", " ").upper(), weapon=NAME, dry=dry,
                    fps=fps)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = "--no-render" in args
    which = [a for a in args if a in ("showcase", "held", "fps")] or ["showcase", "held", "fps"]
    if "showcase" in which:
        showcase(dry)
    if "held" in which:
        held(dry)
    if "fps" in which:
        held(dry, fps=True)


if __name__ == "__main__":
    main()
