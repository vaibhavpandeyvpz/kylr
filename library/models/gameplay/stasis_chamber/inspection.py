"""Reference-angle beauty, actual Tensor comparison and occupant fit check."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview


def evaluated(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=ev.to_mesh()
    vertices=[ev.matrix_world@v.co for v in mesh.vertices]
    faces=[tuple(p.vertices) for p in mesh.polygons]
    ev.to_mesh_clear()
    return vertices,faces


def main():
    render='--fit-only' not in sys.argv
    preview.open_model();preview.setup_render()
    preview.VIEWS['hero']=((1,-1,.45),'PERSP',(1280,1280))
    cam=preview.create_camera();lights=preview.create_lights()
    if render:preview.render_view(cam,lights,'hero')
    if render:
        # Inspect the physical butt joint from the same rear direction as
        # the user's detail reference, independent of whole-model framing.
        scene=bpy.context.scene
        scene['preview_frame']=json.dumps({'lo':[-.60,-.80,.30],'hi':[.60,.80,.72]})
        preview.VIEWS['seat']=((0,1,0),'ORTHO',(1280,512))
        preview.render_view(cam,lights,'seat')
        del scene['preview_frame']
        scene['preview_frame']=json.dumps({'lo':[.42,-.75,.70],'hi':[.62,-.52,.90]})
        door=bpy.data.objects['RIG_StasisChamber'].pose.bones['Door']
        import math
        door.rotation_euler.x=math.radians(60)
        bpy.context.view_layer.update()
        preview.VIEWS['hinge_detail']=((1,-1,.4),'PERSP',(1024,1024))
        preview.render_view(cam,lights,'hinge_detail')
        door.rotation_euler.x=0;bpy.context.view_layer.update()
        del scene['preview_frame']
    tensor=HERE.parents[1]/'characters/tensor/tensor.blend'
    idle=HERE.parents[2]/'animations/target/blend/tensor/common/idle.blend'
    with bpy.data.libraries.load(str(tensor),link=False) as (src,dst):
        dst.objects=[n for n in ('RIG_Tensor','SK_Tensor','SK_TensorHeadProjector') if n in src.objects]
    objects=list(dst.objects);assert len(objects)==3
    for obj in objects:
        bpy.context.scene.collection.objects.link(obj)
        obj.hide_render=False;obj.hide_set(False)
    rig=next(o for o in objects if o.type=='ARMATURE')
    with bpy.data.libraries.load(str(idle),link=False) as (src,dst):
        dst.actions=list(src.actions)
    action=dst.actions[0]
    rig.animation_data_create();rig.animation_data.action=action
    scene=bpy.context.scene;scene.frame_set(int(action.frame_range[0]))
    meshes=[o for o in objects if o.type=='MESH']
    vertices=[v for o in meshes for v in evaluated(o)[0]]
    print('Tensor idle bounds',[[min(v[i] for v in vertices),max(v[i] for v in vertices)] for i in range(3)],flush=True)
    rig.location.x=1.30
    preview.VIEWS['scale']=((0,-1,.12),'ORTHO',(1920,1080))
    if render:preview.render_view(cam,lights,'scale')
    # Position Tensor on the internal sill, facing the viewing panel.
    rig.location=(0,.02,.53);bpy.context.view_layer.update()
    solid=bpy.data.objects['SK_StasisChamber'];verts,faces=evaluated(solid)
    # Exclude only the horizontal support surface from surface-intersection
    # tests; feet are checked against its height separately on every frame.
    faces=[f for f in faces if not all(abs(verts[i].z-.53)<1e-5 for i in f)]
    chamber=BVHTree.FromPolygons(verts,faces)
    clashes=[];nearest=100
    for frame in range(int(action.frame_range[0]),int(action.frame_range[1])+1):
        scene.frame_set(frame)
        sole=min(v.z for obj in meshes for v in evaluated(obj)[0])
        assert sole>=.53-1e-5,('foot penetrates deck',frame,sole)
        for obj in meshes:
            verts,faces=evaluated(obj)
            assert all(v.y>=-.594+.01 for v in verts),('glass clearance',frame,obj.name)
            # Coplanar sole/sill contact is the intended support, not a clash.
            faces=[f for f in faces if max(verts[i].z for i in f)>.5301]
            patient=BVHTree.FromPolygons(verts,faces)
            overlaps=chamber.overlap(patient)
            if overlaps:
                clashes.append((frame,obj.name))
                if len(clashes)<3:
                    print('Clash samples',[tuple(sum((verts[i] for i in faces[b]),Vector())/len(faces[b])) for _,b in overlaps[:8]],flush=True)
            # Floor contact is intentional; inspect body vertices above ankles.
            nearest=min(nearest,min(chamber.find_nearest(v)[3] for v in verts if v.z>.58))
    assert not clashes,('Tensor intersects chamber',clashes[:10])
    assert nearest>=.01,nearest
    scene.frame_set(int(action.frame_range[0]))
    preview.VIEWS['occupied']=((0,-1,.08),'ORTHO',(1280,1280))
    if render:preview.render_view(cam,lights,'occupied')
    report=json.loads((HERE/'stasis_chamber_rig.json').read_text())
    report['checks']['tensor_idle_fit']={'frames':list(map(int,action.frame_range)),
        'position_m':[0,.02,.53],'minimum_clearance_above_ankles_m':nearest,'intersections':0}
    (HERE/'stasis_chamber_rig.json').write_text(json.dumps(report,indent=2))
    print(f'[stasis_chamber] Tensor idle fit PASS: {nearest*1000:.1f} mm above-ankle clearance',flush=True)


if __name__=='__main__':main()
