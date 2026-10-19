"""Native GLB/FBX render and collision round trips, including motion matrices."""
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix

HERE=Path(__file__).resolve().parent

def bind(rig,action):
    rig.animation_data_create()
    for track in rig.animation_data.nla_tracks:track.mute=True
    rig.animation_data.action=None
    for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    rig.animation_data.action=action

def matrix(rig,bn):
    p=rig.pose.bones[bn]
    return rig.matrix_world@p.matrix@p.bone.matrix_local.inverted()@rig.matrix_world.inverted()

def main():
    source=json.loads((HERE/'shelter_rig.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(HERE/'shelter.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    bones={b['name'] for b in source['bones']};expected={}
    for name,info in source['animations'].items():
        bind(rig,bpy.data.actions[name])
        a,b=map(int,info['frames'])
        for f in range(a,b+1):
            bpy.context.scene.frame_set(f)
            expected[name,f]={bn:matrix(rig,bn).copy() for bn in bones}
    results=[]
    for suffix in ('','_col'):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/f'shelter{suffix}.{ext}'
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
            rig=rigs[0];assert {b.name for b in rig.data.bones}==bones
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(meshes)==(1 if suffix else 2)
            count=0;points=[];materials=set()
            for obj in meshes:
                obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
                assert all(abs(v-1)<1e-5 for v in obj.scale)
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
                points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
                if not suffix:
                    materials.update(obj.data.materials[f.material_index].name for f in obj.data.polygons)
                    assert obj.data.uv_layers
                    assert all(math.isfinite(c) for layer in obj.data.uv_layers for d in layer.data for c in d.uv)
            assert count<=(500 if suffix else 5000)
            if not suffix:
                assert count==source['triangles'] and materials==set(source['materials'])
                apron=next(o for o in meshes if o.name=='SK_ArchitectureRegolith')
                assert {apron.vertex_groups[v.groups[0].group].name for v in apron.data.vertices}=={'Root'}
                assert all(-2.50001<=p.x<=2.50001 and -2.50001<=p.y<=2.50001 for p in points)
                for i in range(3):
                    assert abs(min(p[i] for p in points)-source['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-source['bounds_m']['hi'][i])<1e-4
                assert not any(o.type=='LIGHT' for o in bpy.context.scene.objects)
                g=bpy.data.materials['M_Glass'].node_tree.nodes.get('Principled BSDF')
                assert abs(g.inputs['Alpha'].default_value-.10)<1e-5 and max(g.inputs['Base Color'].default_value[:3])<1e-5
                for info in source['gizmos']:assert bpy.data.objects.get(info['name']) is not None
            else:assert not any('Regolith' in o.name for o in meshes)
            errors=[]
            for name,info in source['animations'].items():
                action=next(a for a in bpy.data.actions if a.name.split('|')[-1]==name)
                bind(rig,action);a,b=info['frames']
                for f in range(int(a),int(b)+1):
                    t=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*(f-a)/(b-a)
                    bpy.context.scene.frame_set(int(t),subframe=t-int(t))
                    for bn,target in expected[name,f].items():
                        got=matrix(rig,bn);error=max(abs(got[i][j]-target[i][j]) for i in range(4) for j in range(4))
                        assert error<.001,(path.name,name,f,bn,error)
                        errors.append(error)
            results.append(dict(file=path.name,triangles=count,animation_max_matrix_error=max(errors),passed=True))
            print(f'[shelter] {path.name} round trip PASS: {count} triangles',flush=True)
    (HERE/'shelter_roundtrip_report.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
