"""Independent GLB/FBX geometry, UV, rigid weights and action round trips."""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import model


def main():
    source=json.loads((HERE/'satellite_rig.json').read_text());results=[]
    for suffix in (('',) if '--render-only' in sys.argv else ('','_col')):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/f'satellite{suffix}.{ext}'
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(rigs)==1 and len(meshes)==(1 if suffix else 2),(ext,[o.name for o in meshes])
            rig=rigs[0];assert {b.name for b in rig.data.bones}=={'Root','Elevation'}
            points=[];count=0;used_materials=set()
            for obj in meshes:
                assert all(abs(v-1)<1e-5 for v in obj.scale)
                obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
                assert len(obj.data.loop_triangles)<=(500 if suffix else 5000)
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
                points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
                if not suffix:
                    used_materials.update(obj.data.materials[f.material_index].name for f in obj.data.polygons)
                    assert obj.data.uv_layers
                    assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for layer in obj.data.uv_layers for d in layer.data for c in d.uv)
            if suffix:assert count<=500,count
            if not suffix:
                assert used_materials==set(source['materials'])
                assert count==source['triangles']
                for i in range(3):
                    assert abs(min(p[i] for p in points)-source['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-source['bounds_m']['hi'][i])<1e-4
            rig.animation_data_create()
            for t in rig.animation_data.nla_tracks:t.mute=True
            errors=[]
            for name,spec in model.animation_specs().items():
                action=next((a for a in bpy.data.actions if a.name.split('|')[-1]==name),None)
                assert action is not None,[a.name for a in bpy.data.actions]
                rig.animation_data.action=action
                keys=spec[2][model.ELEV];n=keys[-1][0]
                for f,angle in keys:
                    sample=action.frame_range[0]+(action.frame_range[1]-action.frame_range[0])*f/n
                    bpy.context.scene.frame_set(int(sample),subframe=sample-int(sample))
                    p=model.PIVOT
                    expected=Matrix.Translation(p)@Matrix.Rotation(math.radians(angle),4,'X')@Matrix.Translation(-p)
                    pb=rig.pose.bones['Elevation']
                    got=rig.matrix_world@pb.matrix@pb.bone.matrix_local.inverted()@rig.matrix_world.inverted()
                    error=max(abs(got[i][j]-expected[i][j]) for i in range(4) for j in range(4))
                    assert error<.001,(suffix,ext,name,f,error)
                    root=rig.pose.bones['Root']
                    fixed=rig.matrix_world@root.matrix@root.bone.matrix_local.inverted()@rig.matrix_world.inverted()
                    assert max(abs(fixed[i][j]-(1 if i==j else 0)) for i in range(4) for j in range(4))<.001
                    errors.append(error)
                if spec[0]:assert abs(keys[0][1]-keys[-1][1])<1e-8
            results.append(dict(file=path.name,triangles=count,animation_max_error=max(errors),passed=True))
            print(f'[satellite] {path.name} round trip PASS: {count} triangles',flush=True)
    (HERE/'satellite_roundtrip_report.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
