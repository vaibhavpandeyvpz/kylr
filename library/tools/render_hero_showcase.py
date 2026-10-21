"""Compose authored assets and sampled animation poses for the README hero image.

Run from library with Blender 5.2 headless. --preview renders a small proof;
the default writes the final PNG into docs/media. The editable scene and full
asset shelf stay in ignored build/hero_showcase, outside runtime exports.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

LIB = Path(__file__).resolve().parents[1]
ROOT = LIB.parent
BUILD = LIB / 'build/hero_showcase'
MODELS = LIB / 'models'
sys.path.insert(0, str(MODELS))
sys.path.insert(0, str(MODELS / 'architecture'))
from nvidia_render import configure_gpu


def collection(name, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def move(obj, col):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)


def append_asset(category, asset, col, location=(0, 0, 0), yaw=0):
    path = MODELS / category / asset / (asset + '.blend')
    with bpy.data.libraries.load(str(path)) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(('SK_', 'RIG_'))
                       or not n.startswith(('PRV_', 'CAM_', 'LGT_', 'TXT_'))]
    objects = [o for o in dst.objects if o and o.type in ('MESH', 'ARMATURE', 'EMPTY')]
    root = bpy.data.objects.new(asset + '_placement', None)
    col.objects.link(root)
    for obj in objects:
        move(obj, col)
        if obj.parent not in objects:
            obj.parent = root
        if obj.type == 'ARMATURE' and obj.animation_data:
            obj.animation_data.action = None
            for track in obj.animation_data.nla_tracks:
                track.mute = True
    root.location = location
    root.rotation_euler.z = math.radians(yaw)
    bpy.context.view_layer.update()
    return root, objects


def sample_pose(rig, clip, frame, kind='tensor'):
    path = LIB / 'animations/target/blend' / kind / (clip + '.blend')
    with bpy.data.libraries.load(str(path)) as (src, dst):
        dst.actions = list(src.actions)
    action = dst.actions[0]
    rig.animation_data_create()
    rig.animation_data.action = None
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    track = rig.animation_data.nla_tracks.new()
    track.name = f'Pose / {clip} / frame {frame}'
    strip = track.strips.new(action.name, -frame, action)
    if action.slots:
        strip.action_slot = action.slots[0]
    strip.extrapolation = 'HOLD'
    rig['showcase_clip'] = clip
    rig['showcase_sample_frame'] = frame
    bpy.context.scene.frame_set(0)


def character(label, weapon, head, clip, frame, position, yaw, color, upper_body):
    col = collection('CAST / ' + label, CAST)
    root, objects = append_asset('characters', 'tensor', col, position, yaw)
    root.name = label
    rig = next(o for o in objects if o.type == 'ARMATURE')
    for obj in objects:
        if obj.type != 'MESH':
            continue
        if obj.name.startswith('SK_TensorHead'):
            obj.hide_render = not obj.name.startswith('SK_TensorHead' + head)
            obj.hide_viewport = obj.hide_render
        if obj.name.startswith('SK_TensorUpperBody'):
            obj.hide_render = not obj.name.startswith('SK_TensorUpperBody' + upper_body)
            obj.hide_viewport = obj.hide_render
        for slot in obj.material_slots:
            if slot.material and slot.material.name.startswith('M_Primary_Metallic'):
                mat = slot.material.copy()
                mat.name = 'M_Cast_' + label
                mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*color, 1)
                slot.material = mat
    visible_uppers = [obj for obj in objects if obj.type == 'MESH'
                      and obj.name.startswith('SK_TensorUpperBody') and not obj.hide_render]
    assert len(visible_uppers) == 1 and visible_uppers[0].name.startswith('SK_TensorUpperBody' + upper_body), label
    sample_pose(rig, clip, frame)
    weapon_root, obs = append_asset('weapons', weapon, col)
    body = next(o for o in obs if o.type == 'MESH' and not o.hide_render and o.parent and o.parent.type == 'ARMATURE')
    wrig = body.parent
    # Exclude the weapon's separate projectile rig and its hidden meshes.
    for obj in obs:
        if obj.type == 'MESH' and obj.parent != wrig:
            obj.hide_render = True
    h = json.loads((MODELS / 'weapons' / weapon / (weapon + '_rig.json')).read_text())['hand_sockets']['RightHandSocket']
    socket = Matrix((h['bone_x_blender'], h['bone_y_blender'], h['bone_z_blender'])).transposed().to_4x4()
    socket.translation = h['wrist_blender']
    wrig.parent = None
    con = wrig.constraints.new('CHILD_OF')
    con.target, con.subtarget = rig, 'RightHand'
    con.inverse_matrix = Matrix.Identity(4)
    wrig.matrix_basis = socket.inverted()
    sample_pose(wrig, clip if (LIB / 'animations/target/blend/weapons' / (clip + '.blend')).exists() else weapon + '/idle', frame, 'weapons')
    mount = next((o for o in obs if o.name.split('.')[0] == 'AmmoMount'), None)
    ammo_path = MODELS / 'weapons' / weapon / (weapon + '_ammo.blend')
    if mount and ammo_path.exists():
        with bpy.data.libraries.load(str(ammo_path)) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith(('SK_', 'RIG_'))]
        ammo = list(dst.objects)
        for obj in ammo:
            col.objects.link(obj)
            if obj.parent not in ammo:
                obj.parent = mount
                obj.matrix_parent_inverse = Matrix.Identity(4)
                obj.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    minimum = min((o.evaluated_get(deps).matrix_world @ v.co).z
                  for o in objects if o.type == 'MESH' and not o.hide_render
                  for v in o.evaluated_get(deps).data.vertices)
    root.location.z += position[2] - minimum
    bpy.context.view_layer.update()
    records.append({'character': label, 'head': head, 'upper_body': upper_body.lower(), 'weapon': weapon,
                    'clip': clip, 'sample_frame': frame})
    return next((o for o in obs if o.name.split('.')[0] in ('Muzzle', 'Muzzle1')), None)


def area(name, pos, target, power, color, size):
    data = bpy.data.lights.new('LGT_' + name, 'AREA')
    data.energy, data.color, data.shape, data.size = power, color, 'DISK', size
    obj = bpy.data.objects.new('LGT_' + name, data)
    LIGHTS.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def point(name, pos, power, color, radius):
    data = bpy.data.lights.new('LGT_' + name, 'POINT')
    data.energy, data.color, data.shadow_soft_size = power, color, radius
    obj = bpy.data.objects.new('LGT_' + name, data)
    LIGHTS.objects.link(obj)
    obj.location = pos


def emission(name, color, strength):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1)
    em.inputs['Strength'].default_value = strength
    mat.node_tree.links.new(em.outputs[0], out.inputs['Surface'])
    return mat


def effect_piece(name, location, scale, material, rotation=None):
    source = next(o for o in FX_KIT if o.name.split('.')[0] == name)
    obj = source.copy()
    obj.data = source.data.copy()
    FX.objects.link(obj)
    obj.parent = None
    obj.modifiers.clear()
    obj.matrix_world = Matrix.Identity(4)
    obj.location, obj.scale = location, scale
    if rotation:
        obj.rotation_euler = rotation
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def atlas_burst(location, size, frame):
    mat = bpy.data.materials.new('M_CombustionFlipbook')
    if mat.node_tree is None:
        mat.use_nodes = True
    n, links = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    out, mix = n.new('ShaderNodeOutputMaterial'), n.new('ShaderNodeMixShader')
    transparent, hot = n.new('ShaderNodeBsdfTransparent'), n.new('ShaderNodeEmission')
    tex, uv = n.new('ShaderNodeTexImage'), n.new('ShaderNodeTexCoord')
    tex.image = bpy.data.images.load(str(MODELS / 'effects/combat_effects/source/fireball_atlas.png'), check_existing=True)
    mapping = n.new('ShaderNodeVectorMath')
    mapping.operation = 'MULTIPLY_ADD'
    mapping.inputs[1].default_value = (.25, .25, 1)
    mapping.inputs[2].default_value = ((frame % 4) * .25, (3 - frame // 4) * .25, 0)
    links.new(uv.outputs['UV'], mapping.inputs[0])
    links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
    links.new(tex.outputs['Color'], hot.inputs['Color'])
    hot.inputs['Strength'].default_value = 2.4
    links.new(tex.outputs['Alpha'], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(hot.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    obj = bpy.context.object
    obj.name = 'FX_RocketDetonation'
    move(obj, FX)
    obj.rotation_euler = (CAM.location - obj.location).to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(mat)
    obj.visible_shadow = False


def shelf():
    catalog = collection('ASSET SHELF / authored models (not rendered)')
    catalog.hide_render = True
    catalog.hide_viewport = True
    count = 0
    for generator in sorted(MODELS.rglob('model.py')):
        asset = generator.parent
        path = asset / (asset.name + '.blend')
        if not path.exists():
            continue
        col = collection('/'.join(asset.relative_to(MODELS).parts), catalog)
        with bpy.data.libraries.load(str(path)) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith(('SK_', 'RIG_'))]
        for obj in dst.objects:
            if obj:
                col.objects.link(obj)
        count += 1
    return count


parser = argparse.ArgumentParser()
parser.add_argument('--preview', action='store_true')
parser.add_argument('--no-shelf', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
BUILD.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(MODELS / 'maps/faceoff/faceoff_preview.blend'))
# Preserve every native placement and freeze the fully assembled map pose.
bpy.context.scene.frame_set(73)
bpy.context.view_layer.update()
for obj in list(bpy.context.scene.objects):
    if obj.type == 'CAMERA' or (obj.type == 'LIGHT' and not obj.name.startswith('LGT_Native_')):
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    if obj.type == 'ARMATURE':
        pose = {bone.name: bone.matrix_basis.copy() for bone in obj.pose.bones}
        obj.animation_data_clear()
        for bone in obj.pose.bones:
            bone.matrix_basis = pose[bone.name]
    if obj.name.startswith('PRV_'):
        obj.hide_render = True

bpy.context.view_layer.update()
native_placements = {o.name: o.matrix_world.copy() for o in bpy.context.scene.objects if o.name.startswith('Gizmo_')}
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.frame_start = scene.frame_end = 0
CAST, SET, FX, LIGHTS, CAMERAS = [collection(n) for n in
    ('COL_Cast', 'COL_LunarOutpost', 'COL_Effects', 'COL_Lights', 'COL_Cameras')]
records = []

CAM = bpy.data.objects.new('CAM_Hero', bpy.data.cameras.new('CAM_Hero'))
CAMERAS.objects.link(CAM)
CAM.location = (18.7, 5.0, 2.7)
target = Vector((19.7, 12.2, 1.0))
CAM.rotation_euler = (target - CAM.location).to_track_quat('-Z', 'Y').to_euler()
CAM.data.lens = 32
CAM.data.clip_end = 500
scene.camera = CAM

# Five silhouettes, distinct heads, and a sampled authored stance for each.
character('01 / Vanguard', 'rifle', 'Projector', 'common/idle', 30,
                   (19.2, 11.0, 0), -15, (.07, .19, .23), 'Aegis')
muzzle = character('02 / Breacher', 'flak_cannon', 'Raptor', 'flak_cannon/idle_crouching_aiming', 18,
          (17.9, 10.8, 0), -30, (.29, .13, .065), 'Lamellar')
character('03 / Heavy', 'rocket_launcher', 'Sentinel', 'rocket_launcher/reload', 60,
          (21.5, 12.5, 0), 35, (.25, .29, .32), 'Reactor')
character('04 / Runner', 'bio_rifle', 'Porthole', 'bio_rifle/run_forward', 5,
          (18, 15.3, 0), -45, (.17, .24, .09), 'Conduit')
character('05 / Flanker', 'pistol', 'Arachne', 'pistol/idle_aiming', 13,
          (20.9, 14.5, 0), 15, (.29, .12, .13), 'Vesper')

# The environment is the populated Faceoff scene at its authored transforms.
for lamp in bpy.context.scene.objects:
    if lamp.type == 'LIGHT' and lamp.name.startswith('LGT_Native_'):
        lamp.data.energy *= .6
        position = lamp.matrix_world.translation
        if 14 < position.x < 35 and 14 < position.y < 35 and position.z > .8:
            lamp.data.energy *= 8.0
            lamp.data.color = (1.0, .86, .69)

world = bpy.data.worlds.new('WLD_LunarNight')
scene.world = world
if world.node_tree is None: world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.055, .075, .105, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = .28
# Hard solar key, broad fixture spill and a restrained warm detonation rim.
sun = bpy.data.objects.new('LGT_Sun', bpy.data.lights.new('LGT_Sun', 'SUN'))
LIGHTS.objects.link(sun)
sun.data.energy, sun.data.angle = .65, math.radians(1)
sun.rotation_euler = (math.radians(32), math.radians(-22), math.radians(-28))
area('OutpostFill', (18, 8, 5), (20, 12, 1), 800, (.66, .83, 1), 5)
area('PoleSpill', (4, 4, 4), (0, 0, 1), 950, (.52, .83, 1), 3)
area('SolarRim', (-3, 6, 6), (0, 0, 1), 1100, (1, .69, .42), 4)

KIT = collection('ASSET / effect geometry (not rendered)')
KIT.hide_render = True
_, FX_KIT = append_asset('effects', 'combat_effects', KIT)
hot = emission('M_MuzzleFire', (1, .32, .055), 12)
if muzzle:
    bpy.context.view_layer.update()
    matrix = muzzle.matrix_world.copy()
    flash = effect_piece('SK_FlameEnvelope', matrix.translation, (.035, .22, .035), hot)
    flash.rotation_euler = matrix.to_euler()
    point('Muzzle', matrix.translation, 18, (1, .38, .08), .12)
atlas_burst((27, 13, .8), 2.7, 6)
point('Detonation', (27, 13, 1.1), 650, (1, .21, .035), .7)
effect_piece('SK_BurstRays', (27, 13, .8), (1.3, 1.3, 1.3), hot,
             (math.radians(23), math.radians(35), .4))

scene.render.engine = 'CYCLES'
scene.cycles.samples = 48 if args.preview else 512
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = .04 if args.preview else .012
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.transparent_max_bounces = 8
configure_gpu(scene)
scene.render.resolution_x, scene.render.resolution_y = (1280, 720) if args.preview else (2560, 1440)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = -.3
group = bpy.data.node_groups.new('HeroComposite', 'CompositorNodeTree')
group.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
scene.compositing_node_group = group
nodes = group.nodes
layer = nodes.new('CompositorNodeRLayers')
glare = nodes.new('CompositorNodeGlare')
glare.inputs['Type'].default_value = 'Fog Glow'
glare.inputs['Quality'].default_value = 'High'
glare.inputs['Threshold'].default_value = 2.2
glare.inputs['Strength'].default_value = .12
output = nodes.new('NodeGroupOutput')
group.links.new(layer.outputs['Image'], glare.inputs['Image'])
group.links.new(glare.outputs['Image'], output.inputs['Image'])
count = shelf() if not args.no_shelf else 0
# Install the canonical material rather than packed images in local model caches.
import lunar_material
lunar_material.preview()
for image in list(bpy.data.images):
    if image.users==0 and 'regolith' in image.name.lower():bpy.data.images.remove(image)
scene['showcase_cast'] = json.dumps(records)
scene['asset_shelf_count'] = count
scene.frame_set(0)
bpy.context.view_layer.update()
for name, matrix in native_placements.items():
    actual = bpy.data.objects[name].matrix_world
    assert max(abs(actual[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 1e-4, name
scene['native_faceoff_placements_verified'] = len(native_placements)
output_path = BUILD / 'preview.png' if args.preview else ROOT / 'docs/media/hero-showcase.png'
output_path.parent.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(output_path)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
            area.spaces.active.shading.color_type = 'MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(BUILD / 'hero-showcase.blend'))
(BUILD / 'scene.json').write_text(json.dumps({'cast': records, 'asset_shelf_count': count,
    'resolution': [scene.render.resolution_x, scene.render.resolution_y],
    'image': str(output_path)}, indent=2))
bpy.ops.render.render(write_still=True)
print('[showcase] completed', output_path, flush=True)
