"""Fresh render/collider GLB/FBX round trips and exact outer motion envelope."""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('barricade_source',HERE/'model.py')
s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
from material_classes import classified_name, policy
material_policy=policy(HERE)
info=json.loads(s.RIG_JSON_PATH.read_text())

def points(meshes):
    result=[]
    deps=bpy.context.evaluated_depsgraph_get()
    for body in meshes:
        obj=body.evaluated_get(deps);mesh=obj.to_mesh()
        result.extend(obj.matrix_world@v.co for v in mesh.vertices)
        obj.to_mesh_clear()
    return result

def envelope(meshes,label):
    p=points(meshes)
    assert all(s.PATCH[0]-.0002<=v.x<=s.PATCH[1]+.0002 and
               s.PATCH[2]-.0002<=v.y<=s.PATCH[3]+.0002 for v in p),label
    return p

report=[]
for stem in ('barricade','barricade_col'):
    for ext in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=HERE/f'{stem}.{ext}'
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
        assert meshes,path
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        joints=s.resolve_joints();pistons=s.resolve_pistons(joints)
        expected=set(joints)|{bone for p in pistons for bone in (p.cylinder,p.rod,*p.stage_names)}
        assert set(rig.data.bones.keys())==expected,(path,list(rig.data.bones.keys()))
        rig.animation_data_create();rig.animation_data.action=None
        for track in rig.animation_data.nla_tracks:track.mute=True
        for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        assert tris<=(s.TRI_BUDGET if stem=='barricade' else 500),(stem,tris)
        for obj in meshes:
            assert all(abs(v-1)<1e-5 for v in obj.scale)
            for vertex in obj.data.vertices:
                weights=[g.weight for g in vertex.groups if g.weight>1e-6]
                assert len(weights)==1 and abs(weights[0]-1)<1e-5
        p=envelope(meshes,'rest')
        if stem=='barricade':
            # The shared kit reserves M_Emissive, but this barricade has no
            # lights. Exporters may discard that unused material slot.
            used={obj.data.materials[p.material_index].name
                  for obj in meshes for p in obj.data.polygons}
            assert used=={classified_name(name,material_policy) for name in (s.PRI,s.SEC,s.FRM,s.JNT)},used
            assert abs(max(v.x for v in p)-min(v.x for v in p)-s.OUTER_W)<.0002
            assert abs(max(v.y for v in p)-min(v.y for v in p)-s.OUTER_L)<.0002
            assert abs(min(v.z for v in p)+s.PIT_D)<.0002
            assert all(math.isfinite(c) and -1e-5<=c<=1+1e-5
                       for obj in meshes for layer in obj.data.uv_layers
                       for uv in layer.data for c in uv.uv)
        for name in ('raise','lower'):
            action=next(a for a in bpy.data.actions if name in a.name and s.action_fcurves(a))
            rig.animation_data.action=action
            if action.slots:rig.animation_data.action_slot=action.slots[0]
            first,last=map(float,action.frame_range)
            angles=[]
            for frame in range(math.floor(first*2),math.ceil(last*2)+1):
                bpy.context.scene.frame_set(frame//2,subframe=(frame%2)/2)
                bpy.context.view_layer.update()
                envelope(meshes,f'{stem}.{ext} {name} {frame/2}')
                if frame in (math.floor(first*2),math.ceil(last*2)):
                    angles.append(rig.pose.bones[s.SLAB].matrix.to_quaternion())
            assert abs(math.degrees(angles[0].rotation_difference(angles[1]).angle)-s.RAISE)<.03
        report.append(dict(file=path.name,triangles=tris,status='PASS'))
        print(f'[barricade] {path.name}: {tris} tris, 2 x 4 m outer footprint and all half-frame motion samples PASS',flush=True)
out=HERE.parents[2]/'target'/'barricade_validation.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n')
