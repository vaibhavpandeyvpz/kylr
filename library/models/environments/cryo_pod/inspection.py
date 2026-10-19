"""Static pod reference-angle, Tensor scale and supine fit inspection.
Comparison-only Tensor uses the authored idle frame; nothing is exported.
"""
import json,sys,math
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview

def evaluated(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    pts=[ev.matrix_world@v.co for v in mesh.vertices]
    faces=[tuple(p.vertices) for p in mesh.polygons];ev.to_mesh_clear()
    return pts,faces

def main():
    render='--fit-only' not in sys.argv
    preview.open_model();preview.setup_render()
    preview.VIEWS['hero']=((1,-1,.75),'PERSP',(1600,1200))
    cam=preview.create_camera();lights=preview.create_lights()
    if render:preview.render_view(cam,lights,'hero')
    tensor=HERE.parents[1]/'characters/tensor/tensor.blend'
    idle=HERE.parents[2]/'animations/target/blend/tensor/common/idle.blend'
    with bpy.data.libraries.load(str(tensor),link=False) as (src,dst):
        dst.objects=[n for n in ('RIG_Tensor','SK_Tensor','SK_TensorHeadProjector') if n in src.objects]
    objs=list(dst.objects);assert len(objs)==3
    for obj in objs:
        bpy.context.scene.collection.objects.link(obj);obj.hide_render=False;obj.hide_set(False)
    rig=next(o for o in objs if o.type=='ARMATURE')
    with bpy.data.libraries.load(str(idle),link=False) as (src,dst):dst.actions=list(src.actions)
    action=dst.actions[0];rig.animation_data_create();rig.animation_data.action=action
    bpy.context.scene.frame_set(int(action.frame_range[0]))
    meshes=[o for o in objs if o.type=='MESH']
    rig.location.x=1.30
    preview.VIEWS['scale']=((1,-1,.30),'PERSP',(1920,1080))
    if render:preview.render_view(cam,lights,'scale')
    rig.animation_data_clear()
    for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    # Rest-length reclining posture: arms at sides, within Tensor's limits.
    for side,sign in (('Left',1),('Right',-1)):
        pb=rig.pose.bones[side+'UpperArm'];pb.rotation_mode='XYZ'
        pb.rotation_euler.z=math.radians(-85*sign)
    rig.matrix_world=Matrix.Rotation(math.pi,4,'Z')@Matrix.Rotation(-math.pi/2,4,'X')
    bpy.context.view_layer.update()
    pts=[v for o in meshes for v in evaluated(o)[0]]
    rig.location.y=-(min(v.y for v in pts)+max(v.y for v in pts))/2
    rig.location.z=.46-min(v.z for v in pts)
    bpy.context.view_layer.update()
    points=[v for o in meshes for v in evaluated(o)[0]]
    print('TENSOR RECLINED BOUNDS',[[min(v[i] for v in points),max(v[i] for v in points)] for i in range(3)],flush=True)
    assert max(abs(v.x) for v in points)<.40,'Tensor wider than pressure cavity'
    assert max(abs(v.y) for v in points)<1.08,'Tensor longer than pressure cavity'
    patient=[]
    for obj in meshes:
        verts,faces=evaluated(obj);patient.append((obj.name,verts,faces,BVHTree.FromPolygons(verts,faces)))
    nearest=100
    for obj in (bpy.data.objects['SK_CryoPod'],bpy.data.objects['SK_CryoPodGlass']):
        verts,faces=evaluated(obj)
        faces=[f for f in faces if not all(abs(verts[i].z-.46)<1e-5 for i in f)]
        solid=BVHTree.FromPolygons(verts,faces)
        for name,pv,pf,bvh in patient:
            overlaps=solid.overlap(bvh)
            assert not overlaps,('patient intersection',obj.name,name,[tuple(sum((pv[i] for i in pf[b]),Vector())/len(pf[b])) for _,b in overlaps[:5]])
            nearest=min(nearest,min(solid.find_nearest(v)[3] for v in pv if v.z>.465))
    preview.VIEWS['occupied']=((1,-1,.9),'PERSP',(1600,1200))
    preview.VIEWS['occupied_top']=((0,0,1),'ORTHO',(1024,1024))
    if render:
        preview.render_view(cam,lights,'occupied');preview.render_view(cam,lights,'occupied_top')
    report=json.loads((HERE/'cryo_pod_rig.json').read_text())
    report['checks']['tensor_supine_fit']={'source':'Tensor rest skeleton with arms lowered 85 degrees, rigidly reclined; comparison only',
        'intersections':0,'minimum_non_deck_clearance_m':nearest,
        'bounds_m':{'lo':[min(v[i] for v in points) for i in range(3)],'hi':[max(v[i] for v in points) for i in range(3)]}}
    (HERE/'cryo_pod_rig.json').write_text(json.dumps(report,indent=2))
    print(f'[cryo_pod] actual Tensor supine fit PASS; {nearest*1000:.1f} mm minimum non-deck clearance',flush=True)
if __name__=='__main__':main()
