"""Render a showcase video of a prop's own animations, from the model built by model.py.

Run headless from the repo root (after model.py):
    blender --background --factory-startup --python models/architecture/hangar/animate.py
    ... animate.py -- --no-render     (set up and report only)

Model-agnostic for animated props: the name comes from the folder. It opens <folder>.blend, plays
the armature's actions listed in scene["preview_actions"] one after another (each held at its
last pose until the next takes over; the first is held at its start before it plays), with a
camera that frames scene["preview_frame"] (or every renderable mesh) and swings gently round the
front; the objects listed in scene["preview_show"] (hidden from the stills, e.g. a stand-in character or a
shield) are shown. The .blend is never saved. Output: <folder>_showcase.mp4 (H.264, 1280x720, the scene's fps).
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
NAME = HERE.name
BLEND_PATH = HERE / f"{NAME}.blend"
OUT = HERE / f"{NAME}_showcase.mp4"
RES = (1280, 720)
LENS_MM = 50
GAP = 12            # frames between one action ending and the next starting
LEAD, TAIL = 18, 24  # frames held before the first action and after the last
SWING = 25          # camera swing either side of the front-left view, degrees
LIGHTS = {"LGT_Key": ((-0.6, 0.7, 0.6), 4.5), "LGT_Fill": ((0.8, 0.1, 0.6), 0.9), "LGT_Rim": ((0.4, 0.6, -1.0), 4.0),
          "LGT_Kick": ((-0.9, 0.2, -0.5), 2.0)}  # the previews' lights: a kick rim from the other side too


def frame_box(scene):
    if "showcase_frame" in scene:
        f = json.loads(scene["showcase_frame"])
        return Vector(f["lo"]), Vector(f["hi"])
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
    base = math.atan2(-1, -1)
    n = scene.frame_end - scene.frame_start
    corners=[Vector((x,y,z)) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]
    for f in range(scene.frame_start, scene.frame_end + 1, 4):
        az = base + math.radians(SWING) * math.sin(2 * math.pi * (f - scene.frame_start) / max(n, 1))
        lift_start=scene.get('inspection_lift_start',scene.frame_end+1)
        u=max(0,min(1,(f-lift_start+12)/24))
        u=u*u*(3-2*u)
        d = Vector((math.cos(az), math.sin(az), 0.35+.60*u)).normalized()
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        inv=cam.rotation_euler.to_matrix().transposed()
        local=[inv@(p-center) for p in corners]
        tan_x=(cam_data.sensor_width/2)/LENS_MM
        distance=max(max(p.z+abs(p.x)*1.08/tan_x,
                         p.z+abs(p.y)*1.08/(tan_x*RES[1]/RES[0])) for p in local)
        cam.location = center + d * distance
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    cam_data.clip_end=100
    rot = (-Vector((-1, -1, 0.35)).normalized()).to_track_quat("-Z", "Y").to_matrix()
    for name, (offset, energy) in LIGHTS.items():
        data = bpy.data.lights.new(name, type="SUN")
        data.energy, data.angle = energy, math.radians(8)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.rotation_euler = (-(rot @ Vector(offset).normalized())).to_track_quat("-Z", "Y").to_euler()


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


def setup_render(scene):
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    if hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = True  # real reflections for stainless steel and titanium
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    build_studio(scene)  # the previews' studio
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.filepath = str(OUT)


def main():
    if not BLEND_PATH.exists():
        raise SystemExit(f"[{NAME}] {BLEND_PATH} not found - run model.py first")
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))
    scene = bpy.context.scene
    rig = next((o for o in scene.objects if o.type == "ARMATURE" and o.animation_data), None)
    if rig is None or "preview_actions" not in scene:
        raise SystemExit(f"[{NAME}] no animated armature / scene['preview_actions'] in {BLEND_PATH}")
    for name in json.loads(scene.get("preview_show", "[]")):
        bpy.data.objects[name].hide_render = False
    sequence(scene, rig, json.loads(scene["preview_actions"]))
    # Library-only cutaway copies expose the cargo mechanism during lift clips.
    # Runtime meshes and the saved source scene are unchanged by this render.
    sys.path.insert(0,str(HERE))
    import inspection
    lift_start=int(next(t.strips[0].frame_start for t in rig.animation_data.nla_tracks
                       if t.name=='showcase_lift_up'))
    scene['inspection_lift_start']=lift_start
    originals,copies=inspection.cutaway()
    for obj in originals:
        obj.hide_render=False;obj.keyframe_insert('hide_render',frame=0)
        obj.hide_render=True;obj.keyframe_insert('hide_render',frame=lift_start)
    for obj in copies:
        obj.hide_render=True;obj.keyframe_insert('hide_render',frame=0)
        obj.hide_render=False;obj.keyframe_insert('hide_render',frame=lift_start)
    inspection.inspection_lights()
    lo, hi = frame_box(scene)
    rig_camera(scene, lo, hi)
    print(f"[{NAME}] showcase: frames {scene.frame_start}-{scene.frame_end} at {scene.render.fps} fps")
    if "--no-render" in sys.argv:
        return
    setup_render(scene)
    bpy.ops.render.render(animation=True)
    print(f"[{NAME}] rendered {OUT}")


if __name__ == "__main__":
    main()
