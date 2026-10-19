"""Unscaled Tensor and standing-capsule audit against render and collision exports.

Uses the bunker audit's character sampling helpers; tests both directions at
the 100 mm threshold, vestibule and interior. This is library geometric QA.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('architecture_scale_helpers',HERE.parent/'bunker/scale_check.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
h.HERE=HERE
h.studio.HERE=HERE
h.studio.NAME=HERE.name
h.studio.BLEND_PATH=HERE/'lunar_dome.blend'

def support(points,y,triangles):
    height=max((.10 if y+p.y>=-2.94 else 0)-p.z for p in points)
    for t in triangles:
        for ai,bi in zip(t,t[1:]+t[:1]):
            a,b=points[ai],points[bi]
            if min(a.z,b.z)>.3 or abs(a.y-b.y)<1e-8:continue
            s=(-2.94-y-a.y)/(b.y-a.y)
            if 0<s<1:height=max(height,.10-a.z-(b.z-a.z)*s)
    return height+.00002

def test(points,tris,blockers,x,y,heading=0):
    rotation=Matrix.Rotation(heading,3,'Z')
    points=[rotation@p for p in points]
    lift=support(points,y,tris)
    placed=[p+Vector((x,y,lift)) for p in points]
    probe=BVHTree.FromPolygons(placed,tris,all_triangles=True)
    for label,blocker in blockers:
        overlaps=probe.overlap(blocker)
        if overlaps:
            v,t=h.BLOCKER_GEOMETRY[id(blocker)]
            print('blocking surfaces',[[list(v[i]) for i in t[j]] for _,j in overlaps[:4]],flush=True)
        assert not overlaps,(label,x,y,heading,overlaps[:5])

def main():
    h.studio.open_model();scene=bpy.context.scene
    dome=next(o for o in scene.objects if o.type=='ARMATURE')
    dome.animation_data_clear()
    h.studio.apply_pose(dome,json.loads(dome['preview_poses'])['open'])
    bpy.context.view_layer.update()
    blockers=[('render',h.blockers([o for o in scene.objects if o.type=='MESH' and o.name.startswith('SK_')]))]
    before=set(scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(HERE/'lunar_dome_col.glb'))
    imported=[o for o in scene.objects if o not in before]
    rig=next(o for o in imported if o.type=='ARMATURE');rig.animation_data_clear()
    for pb in rig.pose.bones:
        source=dome.pose.bones[pb.name]
        deformation=dome.matrix_world@source.matrix@source.bone.matrix_local.inverted()@dome.matrix_world.inverted()
        pb.matrix=rig.matrix_world.inverted()@deformation@rig.matrix_world@pb.bone.matrix_local
    bpy.context.view_layer.update()
    blockers.append(('collision',h.blockers([o for o in imported if o.type=='MESH' and o.name.startswith('SK_')])))
    for o in imported:o.hide_render=True
    tensor,meshes=h.import_tensor()
    report={'door_width_m':1.02,'door_height_m':1.94,'interior_height_m':2.95,
        'tensor_height_m':1.753,'capsule_radius_m':.32,'capsule_height_m':1.72,
        'threshold_m':.10,'lanes_m':[0],'capsule_lanes_m':[-.05,0,.05],
        'clips':{},'scope':'centered Tensor traversal; library geometry; engine integration deferred'}
    verts,tris=h.capsule();tests=0
    for x in report['capsule_lanes_m']:
        for step in range(48):
            test(verts,tris,blockers,x,-3.6+step*.1);tests+=1
    report['capsule_states']=tests
    preview=None
    for clip_name in ('idle','walk_forward','run_forward'):
        before=set(scene.objects);family='common' if clip_name=='idle' else 'rifle'
        bpy.ops.import_scene.gltf(filepath=str(h.LIBRARY/'animations/target/tensor'/family/f'{clip_name}.glb'))
        objects=[o for o in scene.objects if o not in before]
        clip=next(o for o in objects if o.type=='ARMATURE')
        mismatch=max(((clip.matrix_world@clip.data.bones[b.name].matrix_local).translation-(tensor.matrix_world@b.matrix_local).translation).length for b in tensor.data.bones)
        assert mismatch<.001,('Tensor bind mismatch',mismatch)
        lo,hi=map(int,clip.animation_data.action.frame_range);stats={'states':0,'frames':[],'max_height_m':0}
        for frame in range(lo,hi+1,max(1,(hi-lo)//12)):
            verts,tris,pieces,floor=h.sample_tensor(tensor,meshes,clip,frame)
            if preview is None:preview=(pieces,floor)
            stats['frames'].append(frame);stats['max_height_m']=max(stats['max_height_m'],max(p.z for p in verts))
            for heading in (0,math.pi):
                for x in report['lanes_m']:
                    for y in (-3.6,-3.2,-3,-2.85,-2.6,-2.3,-2,-1,0,1):
                        try:test(verts,tris,blockers,x,y,heading)
                        except AssertionError as error:raise AssertionError((clip_name,frame,error.args)) from error
                        stats['states']+=1
        report['clips'][clip_name]=stats
        for o in objects:bpy.data.objects.remove(o,do_unlink=True)
    report['result']='PASS'
    out=HERE/'target';out.mkdir(exist_ok=True)
    (out/'lunar_dome_scale_report.json').write_text(json.dumps(report,indent=2))
    print('[lunar_dome] Tensor and capsule traversal PASS',json.dumps(report),flush=True)
    if '--no-render' not in sys.argv:render(preview)

def render(sample):
    scene=bpy.context.scene;pieces,floor=sample
    for source,points in pieces:
        mesh=source.data.copy()
        for v,p in zip(mesh.vertices,points):v.co=Matrix.Rotation(math.pi,3,'Z')@(p-Vector((0,0,floor)))+Vector((0,-2.75,.10))
        scene.collection.objects.link(bpy.data.objects.new('ScaleReference_'+source.name,mesh))
    h.studio.setup_render();cam=h.studio.create_camera();lights=h.studio.create_lights()
    cam.data.type='PERSP';cam.data.lens=45;cam.location=(-3.7,-8.4,3.3)
    cam.rotation_euler=(Vector((0,-2.4,1.2))-cam.location).to_track_quat('-Z','Y').to_euler()
    h.studio.aim_lights(lights,cam)
    scene.render.resolution_x=1600;scene.render.resolution_y=1100
    scene.render.filepath=str(HERE/'lunar_dome_tensor_entry.png');bpy.ops.render.render(write_still=True)

if __name__=='__main__':main()
