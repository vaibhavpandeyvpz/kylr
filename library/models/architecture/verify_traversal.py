"""Unscaled Tensor locomotion and standing capsule in compact architecture.

Checks both render geometry and exported blocking collision. The other closed
buildings have dedicated scale_check.py audits covering their ramps and lifts.
Run Blender headlessly from library/, optionally -- --only asset ... .
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import verify_dimensions as dimensions_audit
import dimensions
spec=importlib.util.spec_from_file_location('tensor_samples',HERE/'hangar/scale_check.py')
tensor=importlib.util.module_from_spec(spec);spec.loader.exec_module(tensor)


def blockers(objects,floor):
    verts,faces=tensor.geometry(objects)
    triangles=[]
    for face in faces:
        a,b,c=(verts[i] for i in face)
        normal=(b-a).cross(c-a).normalized()
        if normal.z>.65 and max(a.z,b.z,c.z)<=floor+.001:continue
        triangles.append(face)
    return BVHTree.FromPolygons(verts,triangles,all_triangles=True)


def audit(name):
    folder=HERE/name;report=json.loads((folder/f'{name}_rig.json').read_text())
    floor=report['architecture_dimensions']['rooms'][0]['floor_m']
    # Cargo blocking collision intentionally fills the traction rail recesses;
    # plant probes on its supported top, 19 mm above the bare render deck.
    if name.startswith('container'):floor=max(floor,.20*dimensions.HEIGHT[name])
    bpy.ops.wm.open_mainfile(filepath=str(folder/f'{name}.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    poses=json.loads(rig['preview_poses']);dimensions_audit.pose(rig,poses['open_all' if name=='hub' else 'open'])
    render=blockers([o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_') and 'Regolith' not in o.name],floor)
    before=set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(folder/f'{name}_col.glb'))
    imported=[o for o in bpy.context.scene.objects if o not in before]
    collider=next(o for o in imported if o.type=='ARMATURE');collider.animation_data_clear()
    for pb in collider.pose.bones:
        for constraint in list(pb.constraints):pb.constraints.remove(constraint)
        source=rig.pose.bones[pb.name]
        deformation=rig.matrix_world@source.matrix@source.bone.matrix_local.inverted()@rig.matrix_world.inverted()
        pb.matrix=collider.matrix_world.inverted()@deformation@collider.matrix_world@pb.bone.matrix_local
    bpy.context.view_layer.update()
    collision=blockers([o for o in imported if o.type=='MESH' and o.name.startswith('SK_') and 'Trigger' not in o.name],floor)
    if name=='hub':routes=[(axis,[i*.1 for i in range(-29,30)]) for axis in (0,1)]
    elif name=='habitat_pod':routes=[(1,[-1.95+i*.05 for i in range(40)])]
    else:
        half=report['dimensions_m']['depth']/2
        # The short cabin terminates at a bulkhead; enter to its centre without
        # deliberately walking the robot's forward limbs into that rear wall.
        end=half+.2 if name=='container_long' else 0
        routes=[(1,[-half-.2+i*.1 for i in range(round((end+half+.2)/.1)+1)])]
    bodies=[('capsule',*tensor.capsule())]
    character,meshes=tensor.import_tensor();scene=bpy.context.scene
    for clip_name in ('idle','walk_forward','run_forward'):
        before=set(scene.objects);family='common' if clip_name=='idle' else 'rifle'
        bpy.ops.import_scene.gltf(filepath=str(tensor.LIBRARY/f'animations/target/tensor/{family}/{clip_name}.glb'))
        objects=[o for o in scene.objects if o not in before]
        clip=next(o for o in objects if o.type=='ARMATURE')
        mismatch=max(((clip.matrix_world@clip.data.bones[b.name].matrix_local).translation-(character.matrix_world@b.matrix_local).translation).length for b in character.data.bones)
        assert mismatch<.001,('Tensor bind mismatch',mismatch)
        low,high=map(int,clip.animation_data.action.frame_range)
        for frame in range(low,high+1,max(1,(high-low)//12)):
            verts,faces,_,_=tensor.sample_tensor(character,meshes,clip,frame)
            bodies.append((f'{clip_name}:{frame}',verts,faces))
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
    count=0
    for label,verts,faces in bodies:
        for axis,coordinates in routes:
            for heading in (0,math.pi):
                rotation=Matrix.Rotation(heading+(math.pi/2 if axis==0 else 0),3,'Z')
                rotated=[rotation@v for v in verts]
                for lane in (-.08,0,.08):
                    for coordinate in coordinates:
                        offset=Vector((coordinate,lane,floor+.00002) if axis==0 else (lane,coordinate,floor+.00002))
                        probe=BVHTree.FromPolygons([v+offset for v in rotated],faces,all_triangles=True)
                        for kind,tree in (('render',render),('collision',collision)):
                            assert not probe.overlap(tree),(name,label,kind,axis,lane,coordinate,heading)
                        count+=1
    result=dict(asset=name,result='PASS',states=count,lanes_m=[-.08,0,.08],
        clips=['idle','walk_forward','run_forward'],capsule_m=[.64,1.72],
        scope='Authored unscaled Tensor and capsule against render and exported collision; library geometry')
    (folder/f'{name}_scale_report.json').write_text(json.dumps(result,indent=2))
    print(f'[{name}] Tensor traversal PASS: {count} states',flush=True)
    return result


if __name__=='__main__':
    names=sys.argv[sys.argv.index('--only')+1:] if '--only' in sys.argv else ['habitat_pod','container','container_long','hub']
    results=[audit(name) for name in names]
    (HERE.parents[1]/'target/architecture_dimensions/compact_traversal_report.json').write_text(json.dumps(results,indent=2))
