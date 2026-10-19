"""Fresh GLB/FBX round trips, including animated skin transforms and colliders."""
import json
import math
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def corner_walls(meshes):
    vertices=[];faces=[]
    for mesh in meshes:
        start=len(vertices);vertices.extend(mesh.matrix_world@v.co for v in mesh.data.vertices)
        faces.extend(tuple(start+i for i in f.vertices) for f in mesh.data.polygons)
    tree=BVHTree.FromPolygons(vertices,faces)
    for z in (.8,3.3,5.5,6.5):
        width=13.8 if z<2.98 else 13.8-(z-2.98)*.4/.64 if z<3.62 else 13.4
        z *= dimensions.HEIGHT[NAME]
        for sx in (-1,1):
            for sy in (-1,1):
                direction=Vector((sx,sy,0)).normalized()
                exterior=tree.ray_cast(Vector((8*sx,8*sy,z)),-direction)[0]
                interior=tree.ray_cast(Vector((0,0,z)),direction)[0]
                assert exterior is not None and interior is not None,('open corner',sx,sy,z)
                expected_outer=(width-.65)/2;expected_inner=(13-.65)/2
                assert abs(abs(exterior.x)-expected_outer)<1e-4 and abs(abs(interior.x)-expected_inner)<1e-4,('corner wall surface',sx,sy,z,list(exterior),list(interior))
                assert (exterior-interior).length>.28,('corner wall too thin',sx,sy,z)

HERE=Path(__file__).resolve().parent
NAME=HERE.name
sys.path.insert(0,str(HERE.parents[1]))
from material_classes import classified_name,policy

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
    for suffix in (('_col',) if '--collision-only' in sys.argv else ('','_col')):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/f'{NAME}{suffix}.{ext}'
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(rigs)==1 and len(meshes)==(3 if suffix else len(report['meshes'])),(path,rigs,meshes)
            rig=rigs[0];assert {b.name for b in rig.data.bones}==bones
            count=0;points=[];used_materials=set()
            for obj in meshes:
                obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
                assert len(obj.data.loop_triangles)<=(500 if suffix else 5000)
                assert all(abs(v-1)<1e-5 for v in obj.scale)
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
                points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
                if not suffix:
                    used={obj.data.materials[f.material_index].name for f in obj.data.polygons}
                    for face in obj.data.polygons:
                        v=obj.data.vertices[face.vertices[0]]
                        bone=obj.vertex_groups[v.groups[0].group].name
                        if bone in ('LeftDoor','RightDoor'):
                            assert obj.data.materials[face.material_index].name not in tuple(classified_name(name,policy(HERE)) for name in ('M_Primary','M_Secondary')), 'door leaves must use stainless finish'
                    used_materials.update(used)
                    assert used<=set(report['materials']),(used,report['materials'])
                    assert obj.data.uv_layers
                    assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for layer in obj.data.uv_layers for d in layer.data for c in d.uv)
            budget_passed=count<=(1012 if suffix else report['triangle_budget'])
            if suffix:
                corner_walls(meshes)
                trigger=next(o for o in meshes if o.name=='SK_LaboratoryLiftPlatformTrigger')
                assert all(trigger.vertex_groups[v.groups[0].group].name=='CargoLift' for v in trigger.data.vertices)
                trigger.data.calc_loop_triangles();assert len(trigger.data.loop_triangles)==12
            if '--draft' not in sys.argv:assert budget_passed
            if not suffix:
                corner_walls(meshes)
                steel=bpy.data.materials[classified_name('M_Joint',policy(HERE))].node_tree.nodes.get('Principled BSDF')
                assert abs(steel.inputs['Metallic'].default_value-1)<1e-6
                assert used_materials==set(report['materials']),(used_materials,report['materials'])
                assert count==report['triangles']
                for i in range(3):
                    assert abs(min(p[i] for p in points)-report['bounds_m']['lo'][i])<1e-4
                    assert abs(max(p[i] for p in points)-report['bounds_m']['hi'][i])<1e-4
                for mount in report['gizmos']:
                    node=bpy.data.objects.get(mount['name'])
                    assert node is not None,('missing light placement gizmo',path,mount['name'])
                    assert max(abs(node.matrix_world.translation[i]-mount['origin'][i]) for i in range(3))<1e-4,(path,mount['name'],list(node.matrix_world.translation))
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
            results.append(dict(file=path.name,triangles=count,animation_max_error=max(errors),
                geometry_and_animations_passed=True,budget_passed=budget_passed,passed=budget_passed))
            print(f'[{NAME}] {path.name} geometry/animation round trip PASS: {count} triangles; budget {"PASS" if budget_passed else "awaiting exception"}',flush=True)
    (HERE/f'{NAME}_roundtrip_report.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
