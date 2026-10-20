"""Render compact account-customisation portraits from the authored Tensor rig.

Run from library/: blender --background --factory-startup --python
tools/render_customisation.py -- [--proof]. PNG intermediates stay in build/;
run tools/install_customisation_thumbnails.py from the repository root afterward.
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import bpy
from mathutils import Vector
warnings.filterwarnings('ignore', category=DeprecationWarning)

LIB = Path(__file__).resolve().parents[1]
ROOT = LIB.parent
OUT = LIB / 'build/customisation'

def sample_pose(rig, clip, frame):
    path = LIB/'animations/target/blend/tensor'/(clip+'.blend')
    with bpy.data.libraries.load(str(path)) as (source, target):
        target.actions = list(source.actions)
    action = target.actions[0]
    rig.animation_data_create()
    rig.animation_data.action = None
    for track in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(track)
    track = rig.animation_data.nla_tracks.new()
    strip = track.strips.new(action.name,-frame,action)
    if action.slots:
        strip.action_slot = action.slots[0]
    strip.extrapolation = 'HOLD'
    bpy.context.scene.frame_set(0)


def color(value):
    rgb = [int(value[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', action='store_true')
    parser.add_argument('--section', choices=['all','heads','emotes','armor'], default='all')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    palette = json.loads((ROOT/'game/data/online_palette.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(LIB/'models/characters/tensor/tensor.blend'))
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH' and o.name.startswith('SK_Tensor')]
    rig = next(o for o in scene.objects if o.type == 'ARMATURE' and o.name.startswith('RIG_Tensor'))
    for o in list(scene.objects):
        if o not in meshes and o != rig and o.type in ('MESH','LIGHT','CAMERA'):
            bpy.data.objects.remove(o, do_unlink=True)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 24
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new('Portrait studio')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.24,.28,.32,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .6
    cameras = bpy.data.collections.new('COL_Cameras')
    scene.collection.children.link(cameras)
    camera = bpy.data.objects.new('CAM_Customisation',bpy.data.cameras.new('Portrait lens'))
    cameras.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'ORTHO'
    for name, point, power, size in [('Key',(2,-3,4),350,3),('Fill',(-3,-2,2),220,3),('Rim',(1,2,3),450,2)]:
        data = bpy.data.lights.new(name,'AREA');data.energy = power;data.shape = 'DISK';data.size = size
        light = bpy.data.objects.new(name,data);scene.collection.objects.link(light)
        light.location = point;light.rotation_euler = (Vector((0,0,1))-light.location).to_track_quat('-Z','Y').to_euler()

    def paint(primary, secondary='silver'):
        for mat in bpy.data.materials:
            key = primary if mat.name.startswith('M_Primary') else secondary if mat.name.startswith('M_Secondary') else None
            if key and mat.use_nodes:
                mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*color(palette[key]),1)

    def head(value, only=False):
        for obj in meshes:
            obj.hide_render = (not obj.name.startswith('SK_TensorHead'+value.capitalize()) if obj.name.startswith('SK_TensorHead') else only)

    def frame(center, scale):
        center = Vector(center)
        camera.location = center+Vector((2,-3,1)).normalized()*4
        camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale = scale

    def render(name):
        target = OUT/(name+'.png');target.parent.mkdir(parents=True,exist_ok=True)
        scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)
        print('[customisation]',name,flush=True)

    colors = ['blue'] if args.proof else list(palette)
    for variant in (['projector','sentinel','porthole','raptor','arachne'] if args.section in ('all','heads') else []):
        sample_pose(rig,'common/idle',12)
        head(variant,True)
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        points = [o.evaluated_get(deps).matrix_world @ v.co for o in meshes if not o.hide_render for v in o.evaluated_get(deps).data.vertices]
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        frame((low+high)*.5, max(high-low)*1.55)
        for primary in colors:
            paint(primary);render('heads/'+variant+'/'+primary)
        if args.proof: break
    poses = {'victory_chicken_dance':38,'victory_gangnam_style':52,'victory_hip_hop_dancing':40,'victory_macarena_dance':62,'victory_wave_hip_hop_dance':52}
    for emote, pose in (poses.items() if args.section in ('all','emotes') else []):
        head('projector');sample_pose(rig,'common/'+emote,pose)
        frame((0,0,.95),2.2)
        for primary in colors:
            paint(primary);render('emotes/'+emote+'/'+primary)
        if args.proof: break
    head('projector');sample_pose(rig,'common/idle',12);frame((0,-.03,1.24),.58)
    for obj in meshes:
        if obj.name.startswith('SK_TensorHead'): obj.hide_render = True
    for primary in (colors if args.section in ('all','armor') else []):
        for secondary in (['silver'] if args.proof else palette):
            paint(primary,secondary);render('armor/'+primary+'/'+secondary)


if __name__ == '__main__':
    main()
