"""Original KYLR VFX geometry and texture generator; no external asset inputs."""
from pathlib import Path
import hashlib
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from texture_io import write_png
NAME = HERE.name
MATERIAL_CLASSIFIERS = {'M_Effect': 'Emissive'}
SEED = 971183
TEXTURE_SAMPLES = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    collection = bpy.data.collections.new('COL_CombatEffects')
    scene.collection.children.link(collection)
    return collection


def mesh(collection, name, vertices, faces, uv):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    data.uv_layers.new(name='EffectCoordinates')
    for polygon in data.polygons:
        polygon.use_smooth = True
        for loop_index in polygon.loop_indices:
            data.uv_layers.active.data[loop_index].uv = uv[data.loops[loop_index].vertex_index]
    obj = bpy.data.objects.new('SK_' + name, data)
    collection.objects.link(obj)
    return obj


def sphere(collection, name, lobes=False, sides=24, rings=12):
    vertices, uv, faces = [], [], []
    # Split the UV seam and poles; faces skip zero-area polar quads.
    for row in range(rings + 1):
        phi = math.pi * row / rings
        for column in range(sides + 1):
            theta = math.tau * column / sides
            modulation = 1.0
            if lobes:
                modulation += 0.25 * math.sin(theta * 5 + math.sin(phi * 3)) * math.sin(phi)**2
                modulation += 0.12 * math.cos(theta * 9 - phi * 4) * math.sin(phi)
            radius = 0.5 * modulation
            vertices.append((radius * math.sin(phi) * math.cos(theta), radius * math.sin(phi) * math.sin(theta), radius * math.cos(phi)))
            uv.append((column / sides, row / rings))
    for row in range(rings):
        for column in range(sides):
            a = row * (sides + 1) + column
            b = a + sides + 1
            if row == 0:
                faces.append((a, b, b + 1))
            elif row == rings - 1:
                faces.append((a, b, a + 1))
            else:
                faces.append((a, b, b + 1, a + 1))
    return mesh(collection, name, vertices, faces, uv)


def nozzle(collection):
    vertices, uv, faces = [], [], []
    sides, rows = 16, 12
    # Local -Y emission becomes the exported emitter axis; the rig manifest
    # records it explicitly so consumers do not infer the axis from origins.
    for row in range(rows + 1):
        t = row / rows
        radius = 0.12 + t * 0.38
        for column in range(sides + 1):
            angle = math.tau * column / sides
            vertices.append((math.cos(angle) * radius, -t, math.sin(angle) * radius))
            uv.append((column / sides, t))
    for row in range(rows):
        for column in range(sides):
            a = row * (sides + 1) + column
            faces.append((a, a + 1, a + sides + 2, a + sides + 1))
    return mesh(collection, 'Nozzle', vertices, faces, uv)


def ring(collection):
    vertices, uv, faces = [], [], []
    for column in range(65):
        theta = math.tau * column / 64
        for side, radius in enumerate((0.82, 1.0)):
            vertices.append((math.cos(theta) * radius, math.sin(theta) * radius, 0))
            uv.append((column / 64, side))
        if column < 64:
            a = column * 2
            faces.append((a, a + 1, a + 3, a + 2))
    return mesh(collection, 'PressureRing', vertices, faces, uv)


def ribbon(collection, variant):
    rng = np.random.default_rng(SEED + variant)
    vertices, uv, faces = [], [], []
    for row in range(25):
        t = row / 24
        amplitude = math.sin(math.pi * t) * 0.17
        x, z = rng.uniform(-amplitude, amplitude, 2)
        for side in range(2):
            vertices.append((x + (side - 0.5) * 0.07, -t, z))
            uv.append((side, t))
        if row < 24:
            a = row * 2
            faces.append((a, a + 1, a + 3, a + 2))
    return mesh(collection, 'ElectricalRibbon' + str(variant), vertices, faces, uv)


def flame_envelope(collection):
    """Lofted comet-shaped hot-gas envelope with asymmetric rolling lobes."""
    vertices, uv, faces = [], [], []
    rows, sides = 20, 24
    for row in range(rows + 1):
        t = row / rows
        body = 0.055 + 0.42 * math.sin(math.pi * t)**0.7 * (1.0-t*0.55)
        offset_x = math.sin(t * 8.0) * 0.065 * t
        offset_z = math.sin(t * 11.0+0.7) * 0.06 * t
        for column in range(sides + 1):
            theta = math.tau * column / sides
            rolling = 1 + 0.19*math.sin(theta*5-t*12) + 0.11*math.cos(theta*3+t*21)
            radius = body * rolling
            vertices.append((offset_x+radius*math.cos(theta), -t, offset_z+radius*math.sin(theta)))
            uv.append((column / sides, t))
    for row in range(rows):
        for column in range(sides):
            a = row*(sides+1)+column
            faces.append((a,a+1,a+sides+2,a+sides+1))
    return mesh(collection, 'FlameEnvelope', vertices, faces, uv)


def spiral_sheets(collection):
    """Four flowing, twisted membranes instead of crossed flat glow cards."""
    vertices, uv, faces = [], [], []
    for sheet in range(4):
        base = len(vertices)
        for row in range(25):
            t = row/24
            theta = sheet*math.pi*0.5 + t*5.4
            radius = 0.12 + 0.32*math.sin(math.pi*t)
            for side in range(2):
                spread = (side-0.5)*(0.1+0.2*math.sin(math.pi*t))
                vertices.append((math.cos(theta+spread)*radius, -t, math.sin(theta+spread)*radius))
                uv.append((side,t))
            if row < 24:
                a = base+row*2
                faces.append((a,a+1,a+3,a+2))
    return mesh(collection, 'VortexSheets', vertices, faces, uv)


def burst_rays(collection):
    """Independent asymmetric tapered streaks, laid out in three dimensions."""
    vertices, uv, faces = [], [], []
    rng = np.random.default_rng(SEED+511)
    for index in range(8):
        theta = index*math.tau/8
        direction = Vector((math.cos(theta),math.sin(theta),rng.uniform(-0.55,0.55))).normalized()
        tangent = direction.cross(Vector((0,0,1))).normalized()
        side = direction.cross(tangent).normalized()
        base = len(vertices)
        length = rng.uniform(0.65,1.0)
        for row in range(3):
            distance = (0.3,0.58,length)[row]
            width = (0.004,0.009,0.001)[row]
            for corner in range(4):
                angle = corner*math.pi/2
                point = direction*distance + (tangent*math.cos(angle)+side*math.sin(angle))*width
                vertices.append(tuple(point))
                uv.append((corner/3,row/2))
            if row < 2:
                for corner in range(4):
                    a = base+row*4+corner
                    b = base+row*4+(corner+1)%4
                    faces.append((a,b,b+4,a+4))
    return mesh(collection, 'BurstRays', vertices, faces, uv)


def fragment_chip(collection):
    """Small asymmetric, thick casing fragment for ballistic particle motion."""
    top = [(-0.5,-0.25,0.035),(0.4,-0.35,0.06),(0.5,0.2,0.02),(-0.1,0.5,0.04)]
    vertices = top + [(x,y,z-0.07) for x,y,z in top]
    faces = [(0,1,2,3),(7,6,5,4)]
    for i in range(4):
        j = (i+1)%4
        faces.append((j,i,i+4,j+4))
    uv = [(x+0.5,y+0.5) for x,y,z in vertices]
    obj = mesh(collection,'FragmentChip',vertices,faces,uv)
    for polygon in obj.data.polygons: polygon.use_smooth = False
    return obj


def induction_cage(collection):
    vertices, uv, faces = [], [], []
    for index in range(3):
        rotation = Matrix.Rotation(index*0.75,3,'X') @ Matrix.Rotation(index*0.45,3,'Z')
        base = len(vertices)
        for segment in range(49):
            angle = segment*math.tau/48
            for edge,radius in enumerate((0.52,0.55)):
                point = rotation @ Vector((math.cos(angle)*radius,0,math.sin(angle)*radius))
                vertices.append(tuple(point))
                uv.append((segment/48,edge))
            if segment < 48:
                a = base+segment*2
                faces.append((a,a+1,a+3,a+2))
    return mesh(collection,'InductionCage',vertices,faces,uv)


def skin(collection, objects):
    data = bpy.data.armatures.new('CombatEffects')
    rig = bpy.data.objects.new('RIG_CombatEffects', data)
    collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bone = data.edit_bones.new('Root')
    bone.head, bone.tail = (0, 0, 0), (0, 0, 0.1)
    bpy.ops.object.mode_set(mode='OBJECT')
    for obj in objects:
        obj.parent = rig
        group = obj.vertex_groups.new(name='Root')
        group.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
        modifier = obj.modifiers.new('RootSkin', 'ARMATURE')
        modifier.object = rig
    return rig


def validate(objects):
    counts = {}
    for obj in objects:
        obj.data.calc_loop_triangles()
        count = len(obj.data.loop_triangles)
        assert count <= 1500, (obj.name, count)
        for triangle in obj.data.loop_triangles:
            a, b, c = (obj.data.vertices[index].co for index in triangle.vertices)
            assert (b-a).cross(c-a).length > 1e-10, (obj.name, 'degenerate triangle')
        for vertex in obj.data.vertices:
            assert all(math.isfinite(value) for value in vertex.co)
            influences = [entry for entry in vertex.groups if entry.weight > 1e-7]
            assert len(influences) == 1 and abs(influences[0].weight-1.0) < 1e-6, (obj.name, vertex.index, [(entry.group, entry.weight) for entry in vertex.groups])
        for loop in obj.data.uv_layers.active.data:
            assert all(math.isfinite(value) and -1e-6 <= value <= 1.000001 for value in loop.uv)
        counts[obj.name] = count
    assert sum(counts.values()) <= 5000, counts
    return counts


def save_texture(name, rgba):
    height, width, channels = rgba.shape
    assert channels == 4 and np.isfinite(rgba).all()
    write_png(HERE/(name+'.png'),rgba)
    samples = []
    for x, y in [(0,0),(width//3,height//5),(width-1,height-1)]:
        samples.append({'pixel':[x,y], 'rgba8':np.rint(np.clip(rgba[y,x],0,1)*255).astype(int).tolist()})
    TEXTURE_SAMPLES[name+'.png'] = samples


def textures():
    rng = np.random.default_rng(SEED)
    n = 256
    y, x = np.mgrid[0:n, 0:n] / n
    channels = []
    for channel in range(4):
        field = np.zeros((n, n))
        for octave in range(5):
            frequency = 2**octave
            for harmonic in range(5):
                a, b = rng.integers(-frequency, frequency+1, 2)
                if a == 0 and b == 0:
                    a = frequency
                field += np.sin(math.tau*(a*x+b*y)+rng.uniform(0, math.tau)) / (frequency * 5)
        field = (field-field.min()) / max(float(field.max()-field.min()), 1e-6)
        channels.append(field)
    turbulence = np.stack(channels, axis=-1)
    save_texture('turbulence_rgba', turbulence)
    for smoke in (False, True):
        atlas = np.zeros((512, 512, 4), dtype=np.float32)
        yy, xx = np.mgrid[0:128, 0:128] / 127 * 2-1
        for frame in range(16):
            age = frame / 15
            density = np.zeros((128, 128))
            for lobe in range(9):
                angle = lobe * 2.39996323
                spread = 0.05 + 0.33*age
                center_x = math.cos(angle)*spread
                center_y = math.sin(angle)*spread + (age*0.12 if smoke else 0)
                width = 0.14 + age * 0.21 + (lobe % 3) * 0.035
                density += np.exp(-((xx-center_x)**2+(yy-center_y)**2)/(width*width)) * (0.6 + lobe*0.04)
            noise = turbulence[::2, ::2, frame % 4]
            density = np.clip(density * (0.3+noise*0.9), 0, 1)
            density *= np.clip(1-(xx*xx+yy*yy), 0, 1)**0.5
            if frame == 15:
                density[:] = 0
            tile = np.ones((128, 128, 4), dtype=np.float32)
            tile[:, :, :3] = density[:, :, None]
            tile[:, :, 3] = density
            row, col = divmod(frame, 4)
            atlas[row*128:(row+1)*128, col*128:(col+1)*128] = tile
        save_texture('smoke_atlas' if smoke else 'gas_atlas', atlas)


def main():
    collection = reset()
    objects = [sphere(collection, 'ThermalShell'), sphere(collection, 'BurstShell', True), nozzle(collection), ring(collection), ribbon(collection, 0), ribbon(collection, 1)]
    objects.extend([flame_envelope(collection),spiral_sheets(collection),burst_rays(collection),fragment_chip(collection)])
    objects.extend([sphere(collection,'PacketShell',sides=12,rings=8),induction_cage(collection)])
    objects.append(mesh(collection, 'AxialCard', [(-0.5, 0, 0), (0.5, 0, 0), (0.5, -1, 0), (-0.5, -1, 0)], [(0, 3, 2, 1)], [(0, 0), (1, 0), (1, 1), (0, 1)]))
    material = bpy.data.materials.new('M_Effect_Emissive')
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.8, 0.35, 0.08, 1)
    bsdf.inputs['Emission Color'].default_value = (0.8, 0.35, 0.08, 1)
    bsdf.inputs['Emission Strength'].default_value = 0.3
    for obj in objects:
        obj.data.materials.append(material)
    rig = skin(collection, objects)
    counts = validate(objects)
    textures()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects + [rig]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=str(HERE / (NAME+'.glb')), export_format='GLB', use_selection=True, export_yup=True, export_skins=True, export_def_bones=True, export_animations=False, export_materials='EXPORT')
    bpy.ops.export_scene.fbx(filepath=str(HERE / (NAME+'.fbx')), use_selection=True, object_types={'MESH', 'ARMATURE'}, global_scale=1, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type='OFF', add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=True, bake_anim=False, path_mode='COPY', embed_textures=True)
    metadata = {'generator': 'model.py', 'seed': SEED, 'bone': 'Root', 'visual_only': True, 'axis_blender': [0, -1, 0], 'triangles': counts, 'bounds_blender': {obj.name: {'min': list(map(min, zip(*(vertex.co for vertex in obj.data.vertices)))), 'max': list(map(max, zip(*(vertex.co for vertex in obj.data.vertices))))} for obj in objects}, 'textures': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(HERE.glob('*_*.png')) if path.stem in ['turbulence_rgba', 'gas_atlas', 'smoke_atlas']}, 'texture_samples':TEXTURE_SAMPLES}
    (HERE / (NAME+'_rig.json')).write_text(json.dumps(metadata, indent=2)+'\n')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / (NAME+'.blend')), compress=True)
    print('[combat_effects] generated original kit:', sum(counts.values()), 'triangles; three procedural textures')


def roundtrip():
    expected = json.loads((HERE / (NAME+'_rig.json')).read_text())
    for extension in ('glb', 'fbx'):
        reset()
        path = str(HERE / (NAME+'.'+extension))
        if extension == 'glb':
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            bpy.ops.import_scene.fbx(filepath=path, use_anim=False)
        # The importer creates a hidden Icosphere bone-display helper. It is not
        # part of the delivered mesh set and has no skin weights.
        objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name in expected['triangles']]
        assert len(objects) == len(expected['triangles']), (extension, [obj.name for obj in bpy.context.scene.objects])
        display_helpers = {bone.custom_shape for obj in bpy.context.scene.objects if obj.type == 'ARMATURE' for bone in obj.pose.bones if bone.custom_shape}
        assert not [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj not in objects and obj not in display_helpers]
        counts = validate(objects)
        assert counts == expected['triangles'], (extension, counts)
        rigs = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
        assert len(rigs) == 1 and list(rigs[0].data.bones.keys()) == ['Root']
        for obj in objects:
            corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            minimum = [min(point[axis] for point in corners) for axis in range(3)]
            maximum = [max(point[axis] for point in corners) for axis in range(3)]
            bounds = expected['bounds_blender'][obj.name]
            assert max(abs(a-b) for a, b in zip(minimum, bounds['min'])) < 1e-4, (extension, obj.name, minimum)
            assert max(abs(a-b) for a, b in zip(maximum, bounds['max'])) < 1e-4, (extension, obj.name, maximum)
        print('[combat_effects] roundtrip passed:', extension, counts)


if __name__ == '__main__':
    roundtrip() if '--roundtrip' in sys.argv else main()
