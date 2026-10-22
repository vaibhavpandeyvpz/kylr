"""Compose authored assets and sampled animation poses for the README hero image.

Run from library with Blender 5.2 headless. --preview renders a small proof;
the default writes the final PNG into docs/media. The editable scene and full
asset shelf stay in ignored build/hero_showcase, outside runtime exports.
Sampled feet are seated against the rendered terrain; scene.json records each
cast member's stance adjustment and verified foot clearances.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

LIB = Path(__file__).resolve().parents[1]
ROOT = LIB.parent
BUILD = LIB / 'build/hero_showcase'
MODELS = LIB / 'models'
sys.path.insert(0, str(LIB / 'tools'))
from showcase_effects import muzzle_flash, rocket_burst
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


def terrain_surface():
    """Use the rendered lunar mesh, excluding hidden native template collections."""
    visible = set()
    def visit(col):
        if col.hide_render:
            return
        visible.add(col)
        for child in col.children:
            visit(child)
    visit(bpy.context.scene.collection)
    vertices, faces = [], []
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if (obj.type != 'MESH' or obj.hide_render
                or not any(col in visible for col in obj.users_collection)
                or not obj.name.startswith(('SK_FaceoffLunarGround', 'SK_ArchitectureRegolith'))):
            continue
        evaluated = obj.evaluated_get(deps)
        start = len(vertices)
        vertices.extend(evaluated.matrix_world @ v.co for v in evaluated.data.vertices)
        faces.extend(tuple(start + i for i in face.vertices) for face in evaluated.data.polygons)
    assert faces, 'Hero requires the populated Faceoff terrain'
    return BVHTree.FromPolygons(vertices, faces)


def posed_feet(objects):
    """Sample deformed foot/toe vertices, triangle centres and edge midpoints."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    feet = {'Left': [], 'Right': []}
    for obj in objects:
        if obj.type != 'MESH' or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(deps)
        evaluated.data.calc_loop_triangles()
        for side, samples in feet.items():
            groups = {g.index for g in obj.vertex_groups if g.name in (side+'Foot', side+'Toes')}
            indices = {v.index for v in obj.data.vertices
                       if any(g.group in groups and g.weight > .9 for g in v.groups)}
            points = {i: evaluated.matrix_world @ evaluated.data.vertices[i].co for i in indices}
            samples.extend(points.values())
            for tri in evaluated.data.loop_triangles:
                if all(i in points for i in tri.vertices):
                    a, b, c = (points[i] for i in tri.vertices)
                    samples.extend(((a+b+c)/3, (a+b)/2, (b+c)/2, (c+a)/2))
    assert all(feet.values()), 'Hero requires both native foot meshes'
    return feet


def ground_character(root, objects):
    """Seat both posed feet on terrain using a small rigid stance adjustment.

    Balance their terrain clearances before lifting the cast; the sampled joint
    pose and hand/weapon relationships remain intact.
    """
    feet = posed_feet(objects)
    pivot = root.matrix_world.translation.copy()
    # Rotate about a horizontal axis perpendicular to the stance. This changes
    # the relative foot height without stretching or re-keying the mechanical rig.
    centres = [sum(points, Vector())/len(points) for points in feet.values()]
    across = centres[1]-centres[0]
    axis = Vector((across.y, -across.x, 0)).normalized()
    def clearances(angle, samples=feet):
        rotation = Matrix.Rotation(angle, 3, axis)
        result = []
        for points in samples.values():
            gaps = []
            for point in points:
                p = pivot + rotation @ (point-pivot)
                hit, normal, _, _ = GROUND.ray_cast(Vector((p.x,p.y,10)), Vector((0,0,-1)), 30)
                assert hit is not None and normal.z > .7, (root.name, 'missing walkable terrain', list(p))
                gaps.append(p.z-hit.z)
            result.append(min(gaps))
        return result
    lo, hi = -math.radians(15), math.radians(15)
    low, high = clearances(lo), clearances(hi)
    assert (low[0]-low[1])*(high[0]-high[1]) <= 0, (root.name, 'stance needs another location')
    for _ in range(24):
        angle = (lo+hi)/2
        gaps = clearances(angle)
        if (gaps[0]-gaps[1])*(low[0]-low[1]) > 0:
            lo, low = angle, gaps
        else:
            hi = angle
    angle = (lo+hi)/2
    gaps = clearances(angle)
    lift = .002-min(gaps)
    rotation = Matrix.Rotation(angle, 4, axis)
    root.matrix_world = Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot) @ root.matrix_world
    root.location.z += lift
    bpy.context.view_layer.update()
    # Re-evaluate the skinned rig after placement, independently of the solver's
    # predicted rigid transform, so constraints cannot silently break contact.
    contacts = clearances(0, posed_feet(objects))
    assert all(.0019 <= gap <= .0021 for gap in contacts), (root.name, 'foot contact', contacts)
    report = {'terrain_clearance_m': dict(zip(feet, contacts)),
              'stance_rotation_degrees': math.degrees(angle), 'vertical_adjustment_m': lift,
              'samples_per_foot': {side:len(points) for side,points in feet.items()}}
    print('[showcase] ground contact', root.name, json.dumps(report), flush=True)
    return report


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
    contact = ground_character(root, objects)
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
    records.append({'character': label, 'head': head, 'upper_body': upper_body.lower(), 'weapon': weapon,
                    'clip': clip, 'sample_frame': frame, 'ground_contact': contact})
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
GROUND = terrain_surface()

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
if muzzle:
    bpy.context.view_layer.update()
    matrix = muzzle.matrix_world.copy()
    muzzle_flash(matrix,effect_piece)
    point('Muzzle',matrix.translation,18,(1,.38,.08),.12)
rocket_burst((23.7,13.5,.3),effect_piece)
point('Detonation',(23.7,13.5,.8),650,(1,.21,.035),.7)

scene.render.engine = 'CYCLES'
scene.cycles.samples = 48 if args.preview else 128
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
