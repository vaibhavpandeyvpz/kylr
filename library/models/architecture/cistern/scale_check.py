"""Tensor scale and standing traversal audit; preview-only, never exports a character.

Run from library with headless Blender 5.2, optionally -- --no-render.
Reads the authored cistern and Tensor plus the existing rifle locomotion clips.
No game integration or physics playtest is performed by this geometric audit.
"""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parents[2]
sys.path.insert(0, str(HERE))
import preview as studio
sys.path.insert(0,str(HERE.parent))
import dimensions
BLOCKER_GEOMETRY = {}


def geometry(objects):
    verts, tris = [], []
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        start = len(verts)
        verts.extend(ev.matrix_world @ v.co for v in mesh.vertices)
        tris.extend(tuple(start + i for i in t.vertices) for t in mesh.loop_triangles)
        ev.to_mesh_clear()
    return verts, tris


def blockers(objects):
    verts, tris = geometry(objects)
    # Walkable floor/ramp contact is intended. Keep all walls, ceilings,
    # door/hinge hardware and furniture; remove only upward-facing low support.
    filtered = []
    for t in tris:
        a, b, c = (verts[i] for i in t)
        normal = (b-a).cross(c-a).normalized()
        if normal.z > .65 and max(a.z, b.z, c.z) < .251:
            continue
        filtered.append(t)
    tree = BVHTree.FromPolygons(verts, filtered, all_triangles=True)
    BLOCKER_GEOMETRY[id(tree)] = (verts, filtered)
    return tree


def ground(y):
    return .10 * max(0, min(1, (y + 7.50) / .60)) * dimensions.HEIGHT[HERE.name]


def support_height(points, y, triangles=()):
    # Plant against the ramp at each foot/contact point, rather than burying
    # the leading foot or hemisphere by placing it at the centre's height.
    height = max(ground(y+p.y)-p.z for p in points)
    for triangle in triangles:
        for ai, bi in zip(triangle, triangle[1:]+triangle[:1]):
            a, b = points[ai], points[bi]
            if min(a.z,b.z) > .30 or abs(a.y-b.y) < 1e-8:
                continue
            for crest in (-7.50,-6.90):
                t = (crest-y-a.y)/(b.y-a.y)
                if 0 < t < 1:
                    z = a.z+(b.z-a.z)*t
                    height = max(height,ground(crest)-z)
    return height + .00002


def capsule():
    # Actual standing game capsule: radius .32m, total height 1.72m.
    verts, faces = [], []
    rings = []
    for centre, angles in ((.32, range(-90, 1, 10)), (1.40, range(0, 91, 10))):
        for angle in angles:
            a = math.radians(angle)
            rings.append((.32*math.cos(a), centre+.32*math.sin(a)))
    for radius, z in rings:
        verts.extend(Vector((radius*math.cos(i*math.tau/48), radius*math.sin(i*math.tau/48), z)) for i in range(48))
    for row in range(len(rings)-1):
        for i in range(48):
            a, b = row*48+i, row*48+(i+1)%48
            c, d = a+48, b+48
            faces.extend(((a, b, d), (a, d, c)))
    return verts, faces


def import_tensor():
    with bpy.data.libraries.load(str(LIBRARY/'models/characters/tensor/tensor.blend'), link=False) as (src, dst):
        dst.objects = src.objects
    objects = [o for o in dst.objects if o]
    for obj in objects:
        bpy.context.scene.collection.objects.link(obj)
    rig = next(o for o in objects if o.type == 'ARMATURE')
    rig.animation_data_clear()
    meshes = [o for o in objects if o.type == 'MESH' and not o.hide_render]
    for obj in objects:
        obj.hide_render = True
    return rig, meshes


def sample_tensor(rig, meshes, clip, frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    # Use world-space skin matrices: glTF bone-axis reconstruction does not
    # need to match Blender's authored local bone axes.
    matrices = {}
    for pb in clip.pose.bones:
        posed = clip.matrix_world @ pb.matrix
        rest = clip.matrix_world @ pb.bone.matrix_local
        matrices[pb.name] = posed @ rest.inverted()
    root_shift = (clip.matrix_world @ clip.pose.bones['Root'].matrix).translation - (clip.matrix_world @ clip.data.bones['Root'].matrix_local).translation
    result, tris, pieces = [], [], []
    for obj in meshes:
        start = len(result)
        local = []
        for vert in obj.data.vertices:
            rest = obj.matrix_world @ vert.co
            point = Vector()
            for group in vert.groups:
                name = obj.vertex_groups[group.group].name
                point += (matrices[name] @ rest) * group.weight
            local.append(point - Vector((root_shift.x, root_shift.y, 0)))
        obj.data.calc_loop_triangles()
        tris.extend(tuple(start+i for i in t.vertices) for t in obj.data.loop_triangles)
        result.extend(local)
        pieces.append((obj, local))
    floor = min(p.z for p in result)
    result = [p-Vector((0, 0, floor)) for p in result]
    return result, tris, pieces, floor


def main():
    studio.open_model()
    scene = bpy.context.scene
    cistern = next(o for o in scene.objects if o.type == 'ARMATURE')
    cistern.animation_data_clear()
    studio.apply_pose(cistern, json.loads(cistern['preview_poses'])['rear_open' if '--rear' in sys.argv else 'open'])
    bpy.context.view_layer.update()
    render_meshes = [o for o in scene.objects if o.type == 'MESH' and o.name.startswith('SK_') and 'Regolith' not in o.name]
    render_blocker = blockers(render_meshes)
    before = set(scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(HERE/'cistern_col.glb'))
    imported = [o for o in scene.objects if o not in before]
    col_rig = next(o for o in imported if o.type == 'ARMATURE')
    col_rig.animation_data_clear()
    # Exported bone axes may differ; copy the world-space skin deformation.
    for pb in col_rig.pose.bones:
        source = cistern.pose.bones[pb.name]
        deformation = cistern.matrix_world @ source.matrix @ source.bone.matrix_local.inverted() @ cistern.matrix_world.inverted()
        pb.matrix = col_rig.matrix_world.inverted() @ deformation @ col_rig.matrix_world @ pb.bone.matrix_local
    bpy.context.view_layer.update()
    collision_blocker = blockers([o for o in imported if o.type == 'MESH' and o.name.startswith('SK_')])
    if '--rear' in sys.argv:
        # Turn the audited surfaces half round so the existing traversal path
        # approaches the rear doorway, with the front door left closed.
        def rear_tree(tree):
            vertices,triangles=BLOCKER_GEOMETRY[id(tree)]
            vertices=[Vector((-p.x,-p.y,p.z)) for p in vertices]
            result=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
            BLOCKER_GEOMETRY[id(result)]=(vertices,triangles)
            return result
        render_blocker=rear_tree(render_blocker)
        collision_blocker=rear_tree(collision_blocker)
    for obj in imported:
        obj.hide_render = True
    tensor, meshes = import_tensor()
    if '--render-only' in sys.argv:
        before = set(scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(LIBRARY/'animations/target/tensor/common/idle.glb'))
        objects = [o for o in scene.objects if o not in before]
        clip = next(o for o in objects if o.type == 'ARMATURE')
        _, _, pieces, floor = sample_tensor(tensor, meshes, clip, 0)
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        render_comparison((pieces, floor))
        return
    report = {'door_width_m':2.0, 'door_height_m':2.70, 'tensor_nominal_height_m':1.753,
              'game_capsule_radius_m':.32, 'game_capsule_height_m':1.72,
              'ramp_rise_m':.10, 'ramp_run_m':.60, 'ramp_angle_deg':math.degrees(math.atan(.10/.60)),
              'lanes_m':[-.15, 0, .15], 'directions':['in', 'out'], 'clips':{}, 'scope':'library geometry; no engine physics playtest'}
    spec=json.loads((HERE/'cistern_rig.json').read_text())['architecture_dimensions']
    report.update(door_width_m=spec['opening_width_m'],door_height_m=spec['opening_height_m'])
    report['ramp_rise_m'] *= dimensions.HEIGHT['cistern']
    report['ramp_angle_deg']=math.degrees(math.atan(report['ramp_rise_m']/report['ramp_run_m']))
    capsule_verts, capsule_tris = capsule()
    capsule_tests = 0
    for x in report['lanes_m']:
        for step in range(95):
            y = -8.8 + step*.1
            lift = support_height(capsule_verts, y, capsule_tris)
            verts = [p+Vector((x, y, lift)) for p in capsule_verts]
            probe = BVHTree.FromPolygons(verts, capsule_tris, all_triangles=True)
            for label, blocker in (('render',render_blocker),('collision',collision_blocker)):
                overlaps = probe.overlap(blocker)
                if overlaps:
                    bv, bt = BLOCKER_GEOMETRY[id(blocker)]
                    print('blocked triangles', [[list(bv[i]) for i in bt[j]] for _,j in overlaps[:8]], flush=True)
                assert not overlaps, ('standing capsule blocked', label, x, y)
            capsule_tests += 1
    preview_sample = None
    for clip_name in ('idle', 'walk_forward', 'run_forward'):
        before = set(scene.objects)
        family = 'common' if clip_name == 'idle' else 'rifle'
        bpy.ops.import_scene.gltf(filepath=str(LIBRARY/'animations/target/tensor'/family/f'{clip_name}.glb'))
        objects = [o for o in scene.objects if o not in before]
        clip = next(o for o in objects if o.type == 'ARMATURE')
        # Imported bind heads must match Tensor, proving the skin transforms
        # below act on the actual authored character in metres.
        mismatch = max(((clip.matrix_world @ clip.data.bones[b.name].matrix_local).translation - (tensor.matrix_world @ b.matrix_local).translation).length for b in tensor.data.bones)
        assert mismatch < .001, ('Tensor bind mismatch', mismatch)
        action = clip.animation_data.action
        lo, hi = map(int, action.frame_range)
        stats = {'frames':[], 'states':0, 'max_width_m':0, 'max_height_m':0, 'max_lateral_extent_m':0}
        for frame in range(lo, hi+1, max(1,(hi-lo)//12)):
            verts, tris, pieces, floor = sample_tensor(tensor, meshes, clip, frame)
            stats['frames'].append(frame)
            stats['max_width_m'] = max(stats['max_width_m'], max(p.x for p in verts)-min(p.x for p in verts))
            stats['max_height_m'] = max(stats['max_height_m'], max(p.z for p in verts))
            stats['max_lateral_extent_m'] = max(stats['max_lateral_extent_m'],max(abs(p.x) for p in verts))
            if preview_sample is None:
                preview_sample = (pieces, floor)
            for heading in (0, math.pi):
                rotation = Matrix.Rotation(heading, 3, 'Z')
                rotated = [rotation @ p for p in verts]
                lifts = {y:support_height(rotated,y,tris) for y in (-8.70,-7.95,-7.65,-7.40,-7.15,-6.90,-6.65,-6.30,-5.80,-4.0,0,1.0)}
                for x in report['lanes_m']:
                    for y in (-8.70,-7.95,-7.65,-7.40,-7.15,-6.90,-6.65,-6.30,-5.80,-4.0,0,1.0):
                        lift = lifts[y]
                        placed = [p+Vector((x,y,lift)) for p in rotated]
                        probe = BVHTree.FromPolygons(placed, tris, all_triangles=True)
                        for label, blocker in (('render',render_blocker),('collision',collision_blocker)):
                            overlaps = probe.overlap(blocker)
                            if overlaps:
                                bv, bt = BLOCKER_GEOMETRY[id(blocker)]
                                print('Tensor bounds',stats,'hit',[[list(bv[i]) for i in bt[j]] for _,j in overlaps[:4]],flush=True)
                            assert not overlaps, ('Tensor blocked',clip_name,frame,label,x,y,heading)
                        stats['states'] += 1
        report['clips'][clip_name] = stats
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    report['capsule_states'] = capsule_tests
    report['result'] = 'PASS'
    report['entrance']='rear' if '--rear' in sys.argv else 'front'
    (HERE/('cistern_rear_scale_report.json' if '--rear' in sys.argv else 'cistern_scale_report.json')).write_text(json.dumps(report, indent=2))
    print('[cistern] Tensor traversal PASS', json.dumps(report), flush=True)
    if '--no-render' in sys.argv:
        return
    render_comparison(preview_sample)


def render_comparison(preview_sample):
    scene = bpy.context.scene
    pieces, floor = preview_sample
    for source, points in pieces:
        mesh = source.data.copy()
        for vertex, point in zip(mesh.vertices, points):
            vertex.co = Matrix.Rotation(math.pi,3,'Z') @ (point-Vector((0,0,floor))) + Vector((0,-7.15,.10*dimensions.HEIGHT[HERE.name]))
        obj = bpy.data.objects.new('ScaleReference_'+source.name, mesh)
        scene.collection.objects.link(obj)
    studio.setup_render()
    cam = studio.create_camera()
    lights = studio.create_lights()
    cam.data.type = 'PERSP'; cam.data.lens = 50
    cam.location = (13,-24,9)
    cam.rotation_euler = (Vector((0,-1.40,1.55))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x = 1600; scene.render.resolution_y = 1100
    studio.aim_lights(lights,cam)
    scene.render.filepath = str(HERE/'cistern_tensor_scale.png')
    bpy.ops.render.render(write_still=True)
    cam.data.lens = 45; cam.location = (3.8,-11.9,3.2)
    cam.rotation_euler = (Vector((0,-7.05,1.40))-cam.location).to_track_quat('-Z','Y').to_euler()
    studio.aim_lights(lights,cam)
    scene.render.filepath = str(HERE/'cistern_tensor_entry.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
