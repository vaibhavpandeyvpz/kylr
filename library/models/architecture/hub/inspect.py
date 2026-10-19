"""Standing traversal audit and interior/mechanism review renders."""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import dimensions
sys.path.insert(0,str(HERE))
import preview

def tree(objects):
    verts=[];faces=[];deps=bpy.context.evaluated_depsgraph_get()
    for o in objects:
        evaluated=o.evaluated_get(deps);mesh=evaluated.to_mesh();offset=len(verts)
        verts.extend(o.matrix_world@v.co for v in mesh.vertices)
        faces.extend(tuple(offset+i for i in p.vertices) for p in mesh.polygons)
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts,faces)

def main():
    preview.open_model();preview.setup_render()
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    for t in rig.animation_data.nla_tracks:t.mute=True
    rig.animation_data.action=bpy.data.actions['open'];bpy.context.scene.frame_set(96)
    building=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in ('SK_HubStructure','SK_HubDoors')]
    bvh=tree(building)
    checks=0;minimum=None
    # A 0.60m standing clearance body taller than Tensor (1.753m); verify two
    # complete orthogonal crossing routes, including each threshold.
    for axis in (0,1):
        for step in range(55):
            coordinate=-2.70+.10*step
            for u in (-.30,0,.30):
                for v in (-.30,0,.30):
                    p=Vector((coordinate+v,u,0) if axis==0 else (u,coordinate+v,0))
                    floor=bvh.ray_cast(p+Vector((0,0,2)),Vector((0,0,-1)),3)[0]
                    feet=floor.z if floor else 0
                    hit,normal,face,distance=bvh.ray_cast(Vector((p.x,p.y,feet+.03)),Vector((0,0,1)),1.85)
                    assert hit is None,('standing passage obstruction',axis,step,tuple(p),tuple(hit))
                    ceiling=bvh.ray_cast(Vector((p.x,p.y,feet+.03)),Vector((0,0,1)),5)[0]
                    if ceiling:minimum=min(minimum if minimum else 99,ceiling.z-feet)
                    checks+=1
    result=dict(passed=True,standing_height_m=1.88,body_width_m=.60,
                route_samples=checks,minimum_overhead_m=minimum,
                routes=['front-rear','left-right'],footprint_m=[6,6])
    (HERE/'hub_traversal_report.json').write_text(json.dumps(result,indent=2))
    if '--no-render' in sys.argv:
        print(f'[hub] traversal PASS: {checks} standing samples, minimum overhead {minimum:.3f}m',flush=True)
        return
    cam=preview.create_camera();lights=preview.create_lights()
    # Exterior with all doors open, then an eye-level room view and closeup of
    # the guide/cylinder channel. Studio lights are preview-only.
    preview.render_view(cam,lights,'front_left','walkable')
    scene=bpy.context.scene
    for name,at,target,lens in (
        ('interior',(0,-2.65,1.66),(0,.4,1.74),22),
        ('mechanism',(.66,-2.16,2.10),(.94,-2.54,2.85),32)):
        cam.data.type='PERSP';cam.data.lens=lens;cam.data.clip_start=.01
        at=dimensions.point(HERE.name,at);target=dimensions.point(HERE.name,target)
        cam.location=at;cam.rotation_euler=(Vector(target)-Vector(at)).to_track_quat('-Z','Y').to_euler()
        scene.render.resolution_x,scene.render.resolution_y=1280,720
        scene.render.filepath=str(HERE/f'hub_{name}.png')
        bpy.ops.render.render(write_still=True)
    print(f'[hub] traversal PASS: {checks} standing samples, 1.88m x .60m; minimum overhead {minimum:.3f}m',flush=True)

if __name__=='__main__':main()
