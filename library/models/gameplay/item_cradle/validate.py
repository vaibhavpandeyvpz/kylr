"""Fresh render/collider GLB and FBX round trips; authored pose seam audit."""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cradle_validation',HERE/'model.py')
s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
info=json.loads((HERE/'item_cradle_rig.json').read_text())

def check_imported_envelope(body):
    evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    points=[body.matrix_world@v.co for v in mesh.vertices]
    # Both Blender importers restore the authored Z-up coordinates.
    assert max(abs(v[i]) for v in points for i in (0,1))<=s.FOOTPRINT/2+.0002
    assert min(v.z for v in points)>=-1e-4
    evaluated.to_mesh_clear()

bpy.ops.wm.open_mainfile(filepath=str(HERE/'item_cradle.blend'))
rig=bpy.data.objects['RIG_ItemCradle'];body=bpy.data.objects['SK_ItemCradle']
for angle in (0,s.OPEN/2,s.OPEN):
    s.f.reset_pose(rig)
    for name in s.NAMES:s.f.set_joint(rig,s.f.resolve_joints()[name],angle)
    bpy.context.view_layer.update()
    mesh=bpy.data.meshes.new_from_object(body.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    obj=bpy.data.objects.new('CHECK_Pose',mesh);bpy.context.scene.collection.objects.link(obj)
    s.check_coplanar(obj)
    assert min(v.co.z for v in mesh.vertices)>-1e-5
    bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
report=[]
for stem in ('item_cradle','item_cradle_col'):
    for ext in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=HERE/f'{stem}.{ext}'
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        assert set(rig.data.bones.keys())=={'Root','ItemSocket',*s.NAMES}
        for name in ('open','close'):
            assert any(name in a.name and s.f.action_fcurves(a) for a in bpy.data.actions),name
        rig.animation_data_create();rig.animation_data.action=None
        for track in rig.animation_data.nla_tracks:track.mute=True
        for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
        tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        assert tris<=(info['triangle_budget'] if stem=='item_cradle' else 500),tris
        for obj in meshes:
            assert all(abs(v-1)<1e-5 for v in obj.scale)
            for v in obj.data.vertices:
                weights=[g.weight for g in v.groups if g.weight>1e-6]
                assert len(weights)==1 and abs(weights[0]-1)<1e-5
        if stem=='item_cradle':
            body=meshes[0]
            def base(name):
                for classifier in ('Metallic','Glass','Emissive','Diffuse'):
                    if name.count('_')>=2 and name.endswith('_'+classifier):return name.removesuffix('_'+classifier)
                return name
            assert set(base(m.name) for m in body.data.materials)==set(base(m) for m in info['materials'])
            assert all(math.isfinite(c) and -1e-5<=c<=1+1e-5 for layer in body.data.uv_layers for uv in layer.data for c in uv.uv)
            points=[body.matrix_world@v.co for v in body.data.vertices]
            assert abs(min(v.z for v in points))<1e-4
            assert abs(max(v.z for v in points)-(.777+s.HOOK_RISE)*s.SCALE)<.0002
            for axis in (0,1):
                assert abs(max(v[axis] for v in points)-min(v[axis] for v in points)-s.FOOTPRINT)<.0002
            mount=bpy.data.objects['ItemMount']
            assert (mount.matrix_world.translation-s.f.Vector(s.f.MOUNT)).length<1e-4
            assert abs(max(v.z for v in points)-mount.matrix_world.translation.z-.10)<1e-4
        else:
            assert {o.name for o in meshes}=={'SK_ItemCradleBaseCol',*('SK_ItemCradleClaw'+tag+'Col' for tag in s.TAGS)}
            for obj in meshes:
                expected='Clamp'+obj.name.removeprefix('SK_ItemCradleClaw').removesuffix('Col') if 'Claw' in obj.name else 'Root'
                assert all(obj.vertex_groups[v.groups[0].group].name==expected for v in obj.data.vertices)
        # Check actual imported motion rather than action names alone.
        action=next(a for a in bpy.data.actions if 'open' in a.name)
        rig.animation_data.action=action
        if action.slots:rig.animation_data.action_slot=action.slots[0]
        first,last=map(float,action.frame_range)
        bpy.context.scene.frame_set(math.floor(first),subframe=first-math.floor(first));bpy.context.view_layer.update()
        initial=rig.pose.bones[s.NAMES[0]].matrix.to_quaternion()
        if stem=='item_cradle':check_imported_envelope(body)
        bpy.context.scene.frame_set(math.floor(last),subframe=last-math.floor(last));bpy.context.view_layer.update()
        final=rig.pose.bones[s.NAMES[0]].matrix.to_quaternion()
        if stem=='item_cradle':check_imported_envelope(body)
        assert abs(math.degrees(initial.rotation_difference(final).angle)-s.OPEN)<.03
        if stem=='item_cradle':
            for half_frame in range(math.floor(first*2),math.ceil(last*2)+1):
                bpy.context.scene.frame_set(half_frame//2,subframe=(half_frame%2)/2)
                bpy.context.view_layer.update()
                check_imported_envelope(body)
        report.append({'file':path.name,'triangles':tris,'status':'PASS'})
        print(f'[item_cradle] {path.name}: {tris} triangles, six bones, rigid weights, actions and 25 degree travel PASS')
(HERE/'item_cradle_validation.json').write_text(json.dumps(report,indent=2))
