"""Build a 5 m square modular bridge; independent guardrails and canopy."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'platform'))
from platform_common import common,kit,export
import bridge_mechanics as mechanics

NAME='bridge'
TITLE='Bridge5X5'
DECK='SK_Bridge5X5Deck'
LEFT='SK_Bridge5X5RailingLeft'
RIGHT='SK_Bridge5X5RailingRight'
COVER='SK_Bridge5X5Cover'
FRAME_LEFT='SK_Bridge5X5SideFrameLeft'
FRAME_RIGHT='SK_Bridge5X5SideFrameRight'
def support_profile(y):
    return [(y-.09,1.09),(y+.09,1.09),(y+.09,2.865),(y-.09,2.865)]


def roof_section(side):
    if side<0:return [(-2.5,2.84),(0,2.84),(0,2.94),(-2.5,2.94)]
    return [(0,2.84),(2.5,2.84),(2.5,2.94),(0,2.94)]


def make_part(rig,name,k,optional=False):
    obj=k.to_object(name);kit.skin(obj,rig);kit.check_coplanar(obj)
    obj['optional']=optional
    obj['collision_mesh']=name+'Col'
    return obj


def build(map_detail=False):
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[common.EMI]=((.025,.55,.62),0,.35,1.5)
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[('Root',None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    rig['preview_poses']='{}'
    meshes=[];k=kit.Kit()
    panels=[(a,b,c,e) for a,c in ((-2.34,-.16),(.16,2.34))
                      for b,e in ((-4.84,-2.66),(-2.34,-.16))]
    cuts=[(((a+c)/2,(b+e)/2,-.02),(c-a,e-b,.08)) for a,b,c,e in panels]
    bays=[((x,y,-.77),(1.9,1.9,.22)) for x in (-1.25,1.25) for y in (-3.75,-1.25)]
    vents=[((s*2.475,y,-.4),(.1,1.15,.26)) for s in (-1,1) for y in (-3.75,-1.25)]
    common.emit(k,kit.machine(common.block((-2.5,-5,-.8),(2.5,0,0)),boxes=cuts+([] if map_detail else bays+vents)),
                common.SEC,'continuous closed bridge deck casting')
    for a,b,c,e in panels:
        traction=[(((a+c)/2,b+(e-b)*t,-.001),(c-a-.42,.028,.020)) for t in (.28,.5,.72)]
        bolts=[(a+.14,b+.14),(c-.14,e-.14)]
        panel=kit.machine(common.block((a+.025,b+.025,-.06),(c-.025,e-.025,0)),
            boxes=[] if map_detail else traction,cuts=[] if map_detail else [((x,y,-.0025),(x,y,.01),.022,8) for x,y in bolts])
        common.emit(k,panel,common.PRI,'replaceable flush traction panel')
        for x,y in ([] if map_detail else bolts):common.bolt(k,x,y,-.0025,'flush captive fastener',r=.022)
    for at,size in ([] if map_detail else vents):
        s=1 if at[0]>0 else -1
        common.emit(k,common.block((s*2.4325-.0075,at[1]-.563,-.518),
                                  (s*2.4325+.0075,at[1]+.563,-.282)),common.FRM,'seated side vent backing')
        for z in (-.472,-.4,-.328):
            common.emit(k,common.block((s*2.45-.010,at[1]-.53,z-.01),
                                      (s*2.45+.010,at[1]+.53,z+.01)),common.PRI,'recessed cooling fin')
    for at,size in ([] if map_detail else bays):
        matrix=Matrix.Rotation(math.pi/4,4,'Z');matrix.translation=(at[0],at[1],-.69)
        with k.frame(matrix):
            common.emit(k,common.block((-1.10,-.025,-.03),(1.10,.025,.03)),common.JNT,'seated diagonal belly tie')
    # No baked thruster or decorative sand: the bridge is a clear connector.
    kit.check_connectivity(k,joints,[])
    meshes.append(make_part(rig,DECK,k))
    for sign,name in ((-1,FRAME_LEFT),(1,FRAME_RIGHT)):
        k=kit.Kit();mechanics.side_frame(k,sign,map_detail=map_detail)
        kit.check_connectivity(k,joints,[])
        meshes.append(make_part(rig,name,k,True))
    for sign,name in ((-1,LEFT),(1,RIGHT)):
        k=kit.Kit();mechanics.guard(k,sign,map_detail=map_detail)
        kit.check_connectivity(k,joints,[])
        meshes.append(make_part(rig,name,k,True))
    k=kit.Kit();mechanics.canopy(k,support_profile,map_detail=map_detail)
    kit.check_connectivity(k,joints,[])
    meshes.append(make_part(rig,COVER,k,True))
    gizmos=[];metadata=[]
    for tag,at,angle in (('BridgeSocketRear',(0,0,0),0),('BridgeSocketFront',(0,-5,0),math.pi)):
        matrix=Matrix.Rotation(angle,4,'Z');matrix.translation=at
        obj=bpy.data.objects.new(tag,None);bpy.context.scene.collection.objects.link(obj)
        obj.parent=rig;obj.matrix_world=matrix;obj.empty_display_type='ARROWS';obj.empty_display_size=.6
        obj['attachment_kind']='bridge_socket';obj['purpose']='Align to platform BridgePlug; level 5 m span'
        gizmos.append(obj);metadata.append(dict(name=tag,attachment_kind='bridge_socket',origin=list(at),
                                               matrix_world=[list(row) for row in matrix]))
    for sign,side in ((-1,'Left'),(1,'Right')):
        tag='SconceLightMount'+side;at=(sign*2.5,-2.5,-.4)
        matrix=Matrix.Rotation(sign*math.pi/2,4,'Z');matrix.translation=at
        obj=bpy.data.objects.new(tag,None);bpy.context.scene.collection.objects.link(obj)
        obj.parent=rig;obj.matrix_world=matrix;obj.empty_display_type='ARROWS';obj.empty_display_size=.4
        obj['attachment']='sconce_light';obj['purpose']='Authored wall sconce centred on bridge side fascia'
        gizmos.append(obj);metadata.append(dict(name=tag,bone='Root',attachment='sconce_light',origin=list(at),
                                               matrix_world=[list(row) for row in matrix]))
    matrix=Matrix.Rotation(math.pi/2,4,'Z');matrix.translation=(0,-2.5,2.84)
    obj=bpy.data.objects.new('BattenLightMount',None);bpy.context.scene.collection.objects.link(obj)
    obj.parent=rig;obj.matrix_world=matrix;obj.empty_display_type='ARROWS';obj.empty_display_size=.4
    obj['attachment']='batten_light';obj['required_mesh']=COVER
    obj['purpose']='Underside ceiling batten; long axis front to back; enabled with roof'
    gizmos.append(obj);metadata.append(dict(name=obj.name,bone='Root',attachment='batten_light',
        required_mesh=COVER,origin=list(matrix.translation),matrix_world=[list(row) for row in matrix]))
    total=sum(kit.triangles(o) for o in meshes)
    assert total<=5000,(total,5000)
    common.prepare_export([rig,*meshes,*gizmos],HERE,NAME)
    export([rig,*meshes,*gizmos],HERE/NAME)
    report=dict(name=NAME,static=True,animations=[],triangle_budget=5000,triangles=total,
        meshes={o.name:kit.triangles(o) for o in meshes},bones=[dict(name='Root',kind='fixed',parent=None)],
        size_m=[5,5],depth_m=.8,placement='Rear docking edge at origin; span along -Y; deck z=0',
        bounds_m=dict(lo=[min(v.co[i] for obj in meshes for v in obj.data.vertices) for i in range(3)],
                      hi=[max(v.co[i] for obj in meshes for v in obj.data.vertices) for i in range(3)]),gizmos=metadata,
        options={LEFT:dict(collider=LEFT+'Col',default=True),RIGHT:dict(collider=RIGHT+'Col',default=True),
                 COVER:dict(collider=COVER+'Col',default=True),
                 FRAME_LEFT:dict(collider=FRAME_LEFT+'Col',default=True,enabled_if_any=[LEFT,COVER]),
                 FRAME_RIGHT:dict(collider=FRAME_RIGHT+'Col',default=True,enabled_if_any=[RIGHT,COVER])},
        clearance=dict(walkway_width_m=4.516,guardrail_height_m=1.12,minimum_headroom_m=2.84),
        materials=sorted({o.data.materials[p.material_index].name for o in meshes for p in o.data.polygons}),
        checks=dict(connectivity=True,coplanar=True,budget=True))
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {total} triangles',flush=True)


if __name__=='__main__':build()
