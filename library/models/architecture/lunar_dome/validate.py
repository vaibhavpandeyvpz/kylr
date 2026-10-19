"""Fresh-scene GLB/FBX mesh, skeleton and every-frame mechanism checks."""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
NAME=HERE.name
sys.path.insert(0,str(HERE.parents[1]))
from material_classes import classified_name,policy
RUBBER=classified_name('M_Rubber',policy(HERE))
meta=json.loads((HERE/f'{NAME}_rig.json').read_text())

def skin(rig,name):
    bone=rig.pose.bones[name]
    return (rig.matrix_world@bone.matrix)@(rig.matrix_world@bone.bone.matrix_local).inverted()

for companion in ('','_col'):
    for suffix in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=str(HERE/f'{NAME}{companion}.{suffix}')
        if suffix=='glb':bpy.ops.import_scene.gltf(filepath=path)
        else:bpy.ops.import_scene.fbx(filepath=path)
        rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
        assert len(rigs)==1
        rig=rigs[0]
        assert set(rig.data.bones.keys())=={'Root','Door','Lock'}
        assert rig.data.bones['Door'].parent.name=='Root'
        assert rig.data.bones['Lock'].parent.name=='Door'
        for track in rig.animation_data.nla_tracks:track.mute=True
        actions={a.name.split('|')[-1]:a for a in bpy.data.actions}
        assert set(actions)=={'open','close'},list(actions)
        pivot=Vector(next(b['head'] for b in meta['bones'] if b['name']=='Door'))
        frames=0
        for name,action in actions.items():
            rig.animation_data.action=action
            lo,hi=map(int,action.frame_range)
            endpoints=[]
            for f in range(lo,hi+1):
                bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
                door=skin(rig,'Door');lock=door.inverted()@skin(rig,'Lock')
                angle=math.degrees(math.atan2(door[1][0],door[0][0]))
                slide=lock.translation.x
                assert -.01<=angle<=110.01,(companion,suffix,name,f,angle)
                assert -.0001<=slide<=.0751,(companion,suffix,name,f,slide)
                if angle>.01:assert slide>=.0749,(name,f,'lock not retracted',slide)
                assert (door@pivot-pivot).length<1e-4,('hinge drift',name,f)
                if f in (lo,hi):endpoints.append(angle)
                frames+=1
            expected=(0,110) if name=='open' else (110,0)
            assert all(abs(a-b)<.01 for a,b in zip(endpoints,expected)),(name,endpoints)
        rig.animation_data.action=None
        for bone in rig.pose.bones:
            bone.location=(0,0,0);bone.rotation_quaternion=(1,0,0,0);bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)
        bpy.context.view_layer.update()
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_LunarDome')]
        assert len(meshes)==(7 if companion else 1),[o.name for o in meshes]
        counts={}
        for obj in meshes:
            assert all(abs(s-1)<1e-5 for s in obj.scale)
            obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
            assert count<=(500 if companion else meta['triangle_budget']),(obj.name,count)
            counts[obj.name]=count
            for v in obj.data.vertices:
                assert len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6
            if companion:continue
            assert count==meta['triangles']
            points=[obj.matrix_world@v.co for v in obj.data.vertices]
            # The notched foundation must stop at the vestibule's front foot.
            assert all(p.y>=-2.94001 for p in points if abs(p.x)<.716 and p.z<.181),('floor projects past threshold',suffix)
            for key,fn in (('lo',min),('hi',max)):
                actual=[fn(v[i] for v in points) for i in range(3)]
                assert all(abs(a-b)<1e-4 for a,b in zip(actual,meta['bounds_m'][key])),(suffix,key,actual)
            mats={obj.data.materials[f.material_index].name for f in obj.data.polygons}
            assert mats==set(meta['materials']),mats
            assert obj.data.uv_layers
            for layer in obj.data.uv_layers:
                assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for uv in layer.data for c in uv.uv)
            glass=bpy.data.materials['M_Glass']
            bsdf=next(n for n in glass.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            assert abs(bsdf.inputs['Alpha'].default_value-.32)<.01
            rubber=bpy.data.materials[RUBBER]
            bsdf=next(n for n in rubber.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            assert abs(bsdf.inputs['Metallic'].default_value)<1e-6
            assert abs(bsdf.inputs['Roughness'].default_value-.85)<.01
            seal_points=[points[i] for f in obj.data.polygons
                if obj.data.materials[f.material_index].name==RUBBER for i in f.vertices]
            assert any(p.z>2.16 for p in seal_points),'missing top shroud seal'
            assert min(p.x for p in seal_points)<-.64 and max(p.x for p in seal_points)>.64,'missing side shroud seals'
        print(f'[{NAME}{companion}] {suffix} PASS: {counts}; Root/Door/Lock; {frames} motion frames',flush=True)
meta['checks']['roundtrips']=['glb','fbx']
meta['checks']['collision_roundtrips']=['glb','fbx']
(HERE/f'{NAME}_rig.json').write_text(json.dumps(meta,indent=2))
