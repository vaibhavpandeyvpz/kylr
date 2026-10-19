"""Round-trip scale, rigid skin, sparse clips and native motion verification."""
import json
import math
import sys
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import model

def matrix(rig,bn):
    p=rig.pose.bones[bn]
    return rig.matrix_world@p.matrix@p.bone.matrix_local.inverted()@rig.matrix_world.inverted()

def bind(rig,action):
    rig.animation_data_create()
    for t in rig.animation_data.nla_tracks:t.mute=True
    rig.animation_data.action=None
    for p in rig.pose.bones:
        p.location=(0,0,0);p.rotation_euler=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
    rig.animation_data.action=action

def main():
    report=json.loads((HERE/'hub_rig.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(HERE/'hub.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    bones={b['name'] for b in report['bones']};expected={}
    for name in report['animations']:
        bind(rig,bpy.data.actions[name])
        for f in range(0,97,12):
            bpy.context.scene.frame_set(f)
            expected[name,f]={bn:matrix(rig,bn).copy() for bn in bones}
    results=[]
    for suffix in ('','_col'):
        for ext in ('glb','fbx'):
            path=HERE/f'hub{suffix}.{ext}'
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
            rig=rigs[0];assert {b.name for b in rig.data.bones}==bones
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            count=0;points=[];materials=set()
            for o in meshes:
                o.data.calc_loop_triangles();count+=len(o.data.loop_triangles)
                assert len(o.data.loop_triangles)<=(500 if suffix else 5000)
                assert all(abs(v-1)<1e-5 for v in o.scale)
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in o.data.vertices)
                points.extend(o.matrix_world@v.co for v in o.data.vertices)
                if not suffix:
                    materials.update(o.data.materials[f.material_index].name for f in o.data.polygons)
                    assert o.data.uv_layers
                    assert all(math.isfinite(c) for layer in o.data.uv_layers for d in layer.data for c in d.uv)
            assert count<=(1000 if suffix else report['triangle_budget'])
            if not suffix:
                assert count==report['triangles'] and materials==set(report['materials'])
                assert len(meshes)==3
                assert not any(o.type=='LIGHT' for o in bpy.context.scene.objects)
                g=bpy.data.materials['M_Glass'].node_tree.nodes.get('Principled BSDF')
                assert abs(g.inputs['Alpha'].default_value-.1)<1e-5 and max(g.inputs['Base Color'].default_value[:3])<1e-5
                assert all(-3.00001<=p.x<=3.00001 and -3.00001<=p.y<=3.00001 for p in points)
                for i in range(3):
                    assert abs(min(p[i] for p in points)-report['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-report['bounds_m']['hi'][i])<1e-4
                terrain=next(o for o in meshes if o.name=='SK_ArchitectureRegolith')
                assert {terrain.vertex_groups[v.groups[0].group].name for v in terrain.data.vertices}=={'Root'}
            else:assert not any('Regolith' in o.name for o in meshes)
            errors=[]
            for name in report['animations']:
                action=next(a for a in bpy.data.actions if a.name.split('|')[-1]==name)
                allowed=model.controlled_bones(name)
                if allowed:
                    paths=model.kit.action_fcurves(action)
                    keyed={f.data_path.split('"')[1] for f in paths if 'pose.bones[' in f.data_path}
                    assert keyed==allowed,(path,name,keyed,allowed)
                bind(rig,action)
                for f in range(0,97,12):
                    t=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*f/96
                    bpy.context.scene.frame_set(int(t),subframe=t-int(t))
                    for bn,target in expected[name,f].items():
                        got=matrix(rig,bn);error=max(abs(got[i][j]-target[i][j]) for i in range(4) for j in range(4))
                        assert error<.001,(path,name,f,bn,error)
                        errors.append(error)
                if allowed:
                    bind(rig,None)
                    peers=bones-allowed-{'Root'}
                    for bn in peers:rig.pose.bones[bn].location[1]=.37
                    bpy.context.view_layer.update();held={bn:matrix(rig,bn).copy() for bn in peers}
                    rig.animation_data.action=action
                    for f in (0,24,48,72,96):
                        t=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*f/96
                        bpy.context.scene.frame_set(int(t),subframe=t-int(t))
                        for bn,target in held.items():
                            got=matrix(rig,bn)
                            assert max(abs(got[i][j]-target[i][j]) for i in range(4) for j in range(4))<1e-5,(path,name,bn,'peer reset')
            results.append(dict(file=path.name,triangles=count,animation_max_error=max(errors),passed=True))
            print(f'[hub] {path.name}: round trip and independent doors PASS',flush=True)
    (HERE/'hub_roundtrip_report.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
