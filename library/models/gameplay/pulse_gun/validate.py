"""Fresh GLB/FBX round trips: rigid skin, gizmos, both pose clips and actuator pins."""
import json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
from material_classes import classified_name,policy
NAME=HERE.name

def reset(rig):
    rig.animation_data_create().action=None
    for t in rig.animation_data.nla_tracks:t.mute=True
    for pb in rig.pose.bones:
        pb.rotation_mode='QUATERNION';pb.rotation_quaternion=(1,0,0,0)
        pb.rotation_euler=(0,0,0);pb.location=(0,0,0);pb.scale=(1,1,1)
    bpy.context.view_layer.update()

def main():
    source=json.loads((HERE/f'{NAME}_rig.json').read_text());results=[]
    required={'Root','Yaw','Elevation','Barrel','ElevatorCylinder','ElevatorRod'}
    base=Vector(next(j['pivot'] for j in source['joints'] if j['bone']=='Yaw'))
    pivot=Vector(next(j['pivot'] for j in source['joints'] if j['bone']=='Elevation'))
    piston=source['pistons'][0]
    for suffix in (('',) if '--render-only' in sys.argv else ('','_col')):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/f'{NAME}{suffix}.{ext}'
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(rigs)==1 and len(meshes)==1,(len(rigs),len(meshes))
            rig=rigs[0];assert required<={b.name for b in rig.data.bones}
            actions={a.name.rsplit('|',1)[-1].removesuffix('.001'):a for a in bpy.data.actions}
            assert {'armed','unarmed'}<=set(actions),list(actions)
            obj=meshes[0];obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
            assert count<=(500 if suffix else source['triangle_budget'])
            assert all(abs(v-1)<1e-5 for v in obj.scale)
            assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
            reset(rig)
            if not suffix:
                assert count==source['triangles']
                assert {obj.data.materials[p.material_index].name for p in obj.data.polygons}==set(source['materials'])
                emissive=obj.data.materials.find(classified_name('M_Emissive',policy(HERE)))
                assert emissive>=0,'Authored emissive material must survive export'
                groups={g.index:g.name for g in obj.vertex_groups}
                assert not any(p.material_index==emissive and groups[obj.data.vertices[p.vertices[0]].groups[0].group] in ('ElevatorCylinder','ElevatorRod') for p in obj.data.polygons)
                assert obj.data.uv_layers
                assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for layer in obj.data.uv_layers for d in layer.data for c in d.uv)
                assert all(bpy.data.objects.get(g['name']) for g in source['gizmos'])
                points=[obj.matrix_world@v.co for v in obj.data.vertices]
                for i in range(3):
                    assert abs(min(p[i] for p in points)-source['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-source['bounds_m']['hi'][i])<1e-4
                muzzle=bpy.data.objects['Muzzle'];rest_muzzle=muzzle.matrix_world.translation.copy()
                assert (muzzle.matrix_world.to_3x3()@Vector((0,1,0))-Vector((0,-1,0))).length<1e-4
            pose_frames=0
            for name,angle in (('armed',15),('unarmed',60)):
                reset(rig);action=actions[name];rig.animation_data.action=action
                for frame in (action.frame_range[0],sum(action.frame_range)/2,action.frame_range[1]):
                    bpy.context.scene.frame_set(int(frame));bpy.context.view_layer.update()
                    pitch=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(-angle),4,'X')@Matrix.Translation(-pivot)
                    expected_b=pitch@Vector(piston['b']);a=Vector(piston['a']);axis=(expected_b-a).normalized()
                    for bone,head,direction in (('ElevatorCylinder',a,axis),('ElevatorRod',expected_b,-axis)):
                        pb=rig.pose.bones[bone]
                        actual_head=rig.matrix_world@pb.head
                        actual_axis=(rig.matrix_world.to_3x3()@pb.matrix.to_3x3()@Vector((0,1,0))).normalized()
                        assert (actual_head-head).length<1e-4,(name,bone,'pin alignment',tuple(actual_head),tuple(head))
                        assert actual_axis.dot(direction)>.99999,(name,bone,'actuator aim',tuple(actual_axis),tuple(direction))
                    if not suffix:assert (muzzle.matrix_world.translation-pitch@rest_muzzle).length<1e-4,(name,'muzzle')
                    assert piston['cylinder_length_m']+piston['rod_length_m']-(expected_b-a).length>.035
                    pose_frames+=1
            if not suffix:
                for yaw in (-180,-90,0,90,180):
                    for elevation in (0,30,60):
                        reset(rig)
                        for bone,value in (('Yaw',yaw),('Elevation',elevation)):
                            pb=rig.pose.bones[bone];pb.rotation_mode='XYZ';pb.rotation_euler.x=math.radians(value)
                        bpy.context.view_layer.update()
                        yaw_m=Matrix.Translation(base)@Matrix.Rotation(math.radians(yaw),4,'Z')@Matrix.Translation(-base)
                        pitch_m=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(-elevation),4,'X')@Matrix.Translation(-pivot)
                        assert (muzzle.matrix_world.translation-yaw_m@pitch_m@rest_muzzle).length<1e-4
                        assert abs((rig.pose.bones['Elevation'].head-rig.pose.bones['Yaw'].head).length-(pivot-base).length)<1e-4
            results.append(dict(file=path.name,triangles=count,pose_samples=pose_frames,passed=True))
            print(f'[{NAME}] {path.name}: PASS {count} triangles; both poses and actuator pins aligned',flush=True)
    (HERE/f'{NAME}_roundtrip_report.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
