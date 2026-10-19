"""Round-trip the delivery geometry and sampled animated transforms."""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
NAME=HERE.name

def main():
    source=json.loads((HERE/f'{NAME}_rig.json').read_text());results=[]
    for suffix in (('',) if '--render-only' in sys.argv else ('','_col')):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/f'{NAME}{suffix}.{ext}'
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(rigs)==1 and len(meshes)==1
            rig=rigs[0];assert {b.name for b in rig.data.bones}=={'Root','Anemometer','WindVane'}
            count=0;points=[]
            for obj in meshes:
                obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
                assert all(abs(v-1)<1e-5 for v in obj.scale)
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
                points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
                if not suffix:
                    assert {obj.data.materials[f.material_index].name for f in obj.data.polygons}==set(source['materials'])
                    assert obj.data.uv_layers
                    assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for layer in obj.data.uv_layers for d in layer.data for c in d.uv)
            assert count<=(500 if suffix else 5000)
            if not suffix:
                assert count==source['triangles']
                for i in range(3):
                    assert abs(min(p[i] for p in points)-source['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-source['bounds_m']['hi'][i])<1e-4
            rig.animation_data_create()
            for track in rig.animation_data.nla_tracks:track.mute=True
            errors=[]
            for name in ('measure','gust'):
                action=next((a for a in bpy.data.actions if a.name.split('|')[-1]==name),None)
                assert action is not None,[a.name for a in bpy.data.actions]
                rig.animation_data.action=action
                n=120 if name=='measure' else 90;speed=6 if name=='measure' else 12;amplitude=25 if name=='measure' else 45
                for f in range(0,n+1,15):
                    sample=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*f/n
                    bpy.context.scene.frame_set(int(sample),subframe=sample-int(sample))
                    for bone,x,angle in (('Anemometer',-.39,speed*f),('WindVane',.39,amplitude*math.sin(math.tau*f/n))):
                        p=Vector((x,0,2.318));expected=Matrix.Translation(p)@Matrix.Rotation(math.radians(angle),4,'Z')@Matrix.Translation(-p)
                        pb=rig.pose.bones[bone]
                        got=rig.matrix_world@pb.matrix@pb.bone.matrix_local.inverted()@rig.matrix_world.inverted()
                        error=max(abs(got[i][j]-expected[i][j]) for i in range(4) for j in range(4))
                        assert error<.001,(suffix,ext,name,f,bone,error)
                        errors.append(error)
            results.append(dict(file=path.name,triangles=count,animation_max_error=max(errors),passed=True))
            print(f'[{NAME}] {path.name} round trip PASS: {count} triangles',flush=True)
    (HERE/f'{NAME}_roundtrip_report.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
