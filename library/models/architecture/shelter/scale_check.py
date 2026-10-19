"""Actual Tensor idle/walk/run plus standing-capsule three-approach audit.

Geometry verification in the library; no Godot physics playtest or integration.
Reusable authored-Tensor sampling and BVH helpers are the bunker workflow's.
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
LIBRARY=HERE.parents[2]
sys.path.insert(0,str(HERE))
import preview as studio
spec=importlib.util.spec_from_file_location('shelter_traversal_helpers',HERE.parent/'bunker/scale_check.py')
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)

def floor_height(tree,x,y):
    point,_,_,_=tree.ray_cast(Vector((x,y,.35)),Vector((0,0,-1)),1)
    return point.z if point is not None else 0

def plant(points,tree,offset):
    return max(floor_height(tree,p.x+offset.x,p.y+offset.y)-p.z for p in points if p.z<.35)+.00003

def main():
    studio.open_model();scene=bpy.context.scene
    rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.animation_data_clear()
    render_meshes=[o for o in scene.objects if o.type=='MESH' and o.name.startswith('SK_') and 'Regolith' not in o.name]
    rv,rt=helpers.geometry(render_meshes)
    floor=BVHTree.FromPolygons(rv,rt,all_triangles=True)
    rb=helpers.blockers(render_meshes)
    before=set(scene.objects);bpy.ops.import_scene.gltf(filepath=str(HERE/'shelter_col.glb'))
    imported=[o for o in scene.objects if o not in before]
    cr=next(o for o in imported if o.type=='ARMATURE');cr.animation_data_clear()
    cb=helpers.blockers([o for o in imported if o.type=='MESH' and o.name.startswith('SK_')])
    for obj in imported:obj.hide_render=True
    entrances={'front':(Vector((0,-1,0)),0),'left':(Vector((1,0,0)),-math.pi/2),
               'right':(Vector((-1,0,0)),math.pi/2)}
    cv,ct=helpers.capsule();tests=0
    for tag,(axis,heading) in entrances.items():
        lateral=Vector((-axis.y,axis.x,0))
        for lane in (-.20,0,.20):
            for step in range(29):
                offset=axis*(2.7-step*.1)+lateral*lane
                lift=plant(cv,floor,offset)
                probe=BVHTree.FromPolygons([p+offset+Vector((0,0,lift)) for p in cv],ct,all_triangles=True)
                for label,blocker in (('render',rb),('collision',cb)):
                    assert not probe.overlap(blocker),('capsule blocked',tag,lane,step,label)
                tests+=1
    tensor,meshes=helpers.import_tensor();clips={};preview_sample=None
    for clip_name in ('idle','walk_forward','run_forward'):
        before=set(scene.objects);family='common' if clip_name=='idle' else 'rifle'
        bpy.ops.import_scene.gltf(filepath=str(LIBRARY/'animations/target/tensor'/family/f'{clip_name}.glb'))
        objects=[o for o in scene.objects if o not in before]
        clip=next(o for o in objects if o.type=='ARMATURE')
        a,b=map(int,clip.animation_data.action.frame_range)
        frames=sorted({round(a+(b-a)*t) for t in (0,.25,.5,.75,1)})
        count=0
        for frame in frames:
            points,tris,pieces,foot_height=helpers.sample_tensor(tensor,meshes,clip,frame)
            if preview_sample is None:preview_sample=(pieces,foot_height)
            for tag,(axis,heading) in entrances.items():
                lateral=Vector((-axis.y,axis.x,0))
                for reverse in (0,math.pi):
                    turn=Matrix.Rotation(heading+reverse,3,'Z');rotated=[turn@p for p in points]
                    for lane in (-.15,0,.15):
                        for along in (2.70,2.30,2.08,1.90,1.50,.90,0):
                            offset=axis*along+lateral*lane;lift=plant(rotated,floor,offset)
                            probe=BVHTree.FromPolygons([p+offset+Vector((0,0,lift)) for p in rotated],tris,all_triangles=True)
                            for label,blocker in (('render',rb),('collision',cb)):
                                hits=probe.overlap(blocker)
                                if hits:
                                    bv,bt=helpers.BLOCKER_GEOMETRY[id(blocker)]
                                    print('blocked surfaces',[[list(bv[i]) for i in bt[j]] for _,j in hits[:8]],'lift',lift,flush=True)
                                assert not hits,('Tensor blocked',clip_name,frame,tag,lane,along,reverse,label)
                            count+=1
            print(f'[shelter] Tensor {clip_name} frame {frame}: all approaches PASS',flush=True)
        clips[clip_name]=dict(frames=frames,states=count)
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
    report=dict(result='PASS',capsule_states=tests,clips=clips,entrances=list(entrances),
        scope='render/collision geometry, actual authored Tensor and 0.32m radius / 1.72m standing capsule; no engine playtest')
    (HERE/'shelter_scale_report.json').write_text(json.dumps(report,indent=2))
    if '--no-render' in sys.argv:return
    pieces,foot_height=preview_sample
    for source,points in pieces:
        mesh=source.data.copy()
        for vertex,point in zip(mesh.vertices,points):vertex.co=point+Vector((0,-1.55,.12-foot_height))
        obj=bpy.data.objects.new('ScaleReference_'+source.name,mesh);scene.collection.objects.link(obj)
    studio.setup_render();cam=studio.create_camera();lights=studio.create_lights()
    studio.render_view(cam,lights,'front_left','tensor_scale')

if __name__=='__main__':main()
