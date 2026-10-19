"""Fresh GLB/FBX round trips, including animated skin transforms and colliders."""
import json
import math
import sys
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
NAME=HERE.name

def material_base(name):
    for classifier in ('Metallic','Glass','Emissive','Diffuse'):
        if name.count('_')>=2 and name.endswith('_'+classifier):return name.removesuffix('_'+classifier)
    return name

def deformation(rig,bn):
    pb=rig.pose.bones[bn]
    return rig.matrix_world@pb.matrix@pb.bone.matrix_local.inverted()@rig.matrix_world.inverted()

def bind_action(rig,action):
    rig.animation_data_create()
    for tr in rig.animation_data.nla_tracks:tr.mute=True
    rig.animation_data.action=None
    for pb in rig.pose.bones:
        pb.location=(0,0,0);pb.rotation_euler=(0,0,0);pb.rotation_quaternion=(1,0,0,0);pb.scale=(1,1,1)
    rig.animation_data.action=action

def main():
    report=json.loads((HERE/f'{NAME}_rig.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    bones={b['name'] for b in report['bones']};expected={}
    for name in report['animations']:
        bind_action(rig,bpy.data.actions[name])
        for f in range(0,97,12):
            bpy.context.scene.frame_set(f)
            expected[name,f]={bn:deformation(rig,bn).copy() for bn in bones}
    results=[]
    for suffix in (('_col',) if '--collision-only' in sys.argv else ('',) if '--render-only' in sys.argv else ('','_col')):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/f'{NAME}{suffix}.{ext}'
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(rigs)==1 and len(meshes)==(1 if suffix else len(report['meshes'])),(path,rigs,meshes)
            rig=rigs[0];assert {b.name for b in rig.data.bones}==bones
            count=0;points=[];used_materials=set()
            for obj in meshes:
                obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
                assert len(obj.data.loop_triangles)<=(500 if suffix else 7500)
                assert all(abs(v-1)<1e-5 for v in obj.scale)
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
                points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
                if not suffix:
                    used={material_base(obj.data.materials[f.material_index].name) for f in obj.data.polygons}
                    used_materials.update(used)
                    assert used<={material_base(m) for m in report['materials']},(used,report['materials'])
                    assert obj.data.uv_layers
                    assert all(math.isfinite(c) for layer in obj.data.uv_layers for d in layer.data for c in d.uv)
                    # SuppliedSurface UVs tile; the final authored painting atlas
                    # remains bounded in 0..1 in both GLB and FBX.
                    assert all(-1e-5<=c<=1.00001 for d in obj.data.uv_layers[-1].data for c in d.uv)
            assert count<=(500 if suffix else 7500)
            if not suffix:
                assert used_materials=={material_base(m) for m in report['materials']},(used_materials,report['materials'])
                assert count==report['triangles']
                for marker in report['gizmos']:
                    obj=bpy.data.objects.get(marker['name']);assert obj is not None,marker
                    position=marker.get('position_m',marker.get('origin'))
                    assert max(abs(obj.matrix_world.translation[i]-position[i]) for i in range(3))<1e-4,(marker,list(obj.matrix_world.translation))
                glass=next(m for m in bpy.data.materials if material_base(m.name)=='M_Glass').node_tree.nodes.get('Principled BSDF')
                assert abs(glass.inputs['Alpha'].default_value-.10)<1e-6
                assert all(v<1e-6 for v in glass.inputs['Base Color'].default_value[:3])
                for i in range(3):
                    assert abs(min(p[i] for p in points)-report['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-report['bounds_m']['hi'][i])<1e-4
            errors=[]
            for name in report['animations']:
                action=next((a for a in bpy.data.actions if a.name.split('|')[-1]==name),None)
                assert action is not None,[a.name for a in bpy.data.actions]
                bind_action(rig,action)
                for f in range(0,97,12):
                    t=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*f/96
                    bpy.context.scene.frame_set(int(t),subframe=t-int(t))
                    for bn,target in expected[name,f].items():
                        got=deformation(rig,bn)
                        error=max(abs(got[i][j]-target[i][j]) for i in range(4) for j in range(4))
                        assert error<.001,(path,name,f,bn,error)
                        errors.append(error)
            results.append(dict(file=path.name,triangles=count,animation_max_error=max(errors),passed=True))
            print(f'[{NAME}] {path.name} round trip PASS: {count} triangles',flush=True)
    (HERE/f'{NAME}_roundtrip_report.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
