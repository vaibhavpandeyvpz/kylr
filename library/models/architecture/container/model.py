"""Short industrial cargo container; metres, front -Y, floor-centred origin.
Scripted formed shells and fitted hardware, with interlocked shoot-bolt doors.
Library only. Blender 5.2, launched headless from library/.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import json
import math
import sys
from types import SimpleNamespace
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'environments'))
import light_common as common
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
import light_mounts
ROOT=common.ROOT
PRI,SEC,FRM,JNT,EMI=common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
NAME,TITLE='container','Container'
W,D,H=2.438,2.991/dimensions.PLAN[NAME],2.591
DOUBLE_END=True
PX,PY=1.079,-1.468
block,rod,loft=common.block,common.rod,common.loft

def transform(bm,m):
    for v in bm.verts:v.co=m@v.co
    return bm

def emit(k,bm,mat,label,bone=ROOT):
    old=common.ROOT;common.ROOT=bone
    try:common.emit(k,bm,mat,label)
    finally:common.ROOT=old

def mach(bm,**kw):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    return kit.machine(bm,**kw)

def seat(k,bm,mat,label,bone=ROOT):
    old_xf=k.xf
    transform(bm,old_xf);k.xf=Matrix.Identity(4)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    bm=common.trim_seats(bm,[p for p in k.parts if p.bone==bone])
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=bm.edges[:])
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    emit(k,bm,mat,label,bone)
    k.xf=old_xf

def boxcut(lo,hi):
    return (tuple((a+b)/2 for a,b in zip(lo,hi)),tuple(b-a for a,b in zip(lo,hi)))

def frame(k):
    # One load-bearing casting: corner towers, four headers and structural floor.
    shell=loft([(W,D,.018,0),(W,D,.018,.045),
                (W-.028,D-.028,.016,.073),(W-.028,D-.028,.016,H-.073),
                (W,D,.018,H-.045),(W,D,.018,H)])
    half=D/2;inner=half-.1405;panel=half-.1955
    cuts=[boxcut((-1.079,-inner,.18),(1.079,inner,2.411)),
          boxcut((-1.079,-half-.10,.18),(1.079,-inner+.025,2.411)),
          boxcut((-1.4,-panel,.27),(-1.07,panel,2.321)),
          boxcut((1.07,-panel,.27),(1.4,panel,2.321)),
          boxcut((-1.01,inner-.025,.27),(1.01,half+.10,2.321)),
          boxcut((-1.01,-panel,2.40),(1.01,panel,2.8))]
    if DOUBLE_END:cuts.append(boxcut((-1.079,inner-.025,.18),(1.079,half+.10,2.411)))
    # Open lifting sockets in all eight corners, with genuinely recessed bottoms.
    for x in (-1.143,1.143):
        for y in (-half+.0745,half-.0745):
            for z in (.040,H-.04):
                ya,yb=(-half-.035,-half+.0985) if y<0 else (half-.0985,half+.035)
                cuts.append(boxcut((x-.027,ya,z-.022),(x+.027,yb,z+.022)))
            cuts.append(boxcut((x-.032,y-.028,H-.062),(x+.032,y+.028,H+.01)))
    bores=[]
    for end in ((-1,1) if DOUBLE_END else (-1,)):
        hy=end*(half-.0275);by=end*(half-.0345)
        for s in (-1,1):
            bores.append(((s*PX,hy,.30),(s*PX,hy,2.29),.034,8))
            for z0,z1 in ((.10,.22),(2.37,2.49)):
                bores.append(((s*.34,by,z0),(s*.34,by,z1),.012,8))
            for z0,z1 in ((.118,.162),(2.428,2.472)):
                bores.append(((s*.34,by,z0),(s*.34,by,z1),.018,8))
    shell=mach(shell,boxes=cuts,cuts=bores)
    emit(k,shell,SEC,'continuous load frame and integral cargo deck')
    # Upper/lower panels sit exactly in the frame windows. Each is a folded
    # sheet with real thickness; ribs are bends in the shell, not buried sticks.
    def corrugated(length,depth,n):
        out=[]
        for i in range(n):
            a=-length/2+length*i/n;b=a+length/n
            for t,v in ((0,0),(.16,0),(.32,depth),(.68,depth),(.84,0),(1,0)):
                p=(a+(b-a)*t,v)
                if not out or p!=out[-1]:out.append(p)
        return out
    profile=corrugated(D-.391,.035,18 if DOUBLE_END else 9)
    for s in (-1,1):
        poly=[(s*(1.125+v),y,1.2955) for y,v in profile]
        poly += [(s*(1.117+v),y,1.2955) for y,v in reversed(profile)]
        bm=kit.prism_bm(poly,2.051,(0,0,1))
        seat(k,bm,PRI,'formed side wall with continuous strengthening flutes')
    p=corrugated(2.02,.035,7)
    poly=[(x,D/2-.1055+v,1.2955) for x,v in p]+[(x,D/2-.1135+v,1.2955) for x,v in reversed(p)]
    if not DOUBLE_END:seat(k,kit.prism_bm(poly,2.051,(0,0,1)),PRI,'formed rear bulkhead')
    # Crown roof folds run fore/aft and drain to the outside of the top rail.
    poly=[(x,0,2.49+v) for x,v in p]+[(x,0,2.482+v) for x,v in reversed(p)]
    seat(k,kit.prism_bm(poly,D-.391,(0,1,0)),PRI,'formed load roof')
    # Continuous deck inlay, flush with the sill, seated rather than overlaying.
    # Shallow geometric traction channels are cut into the upper floor.
    for x in (-.86,-.43,0,.43,.86):
        emit(k,block((x-.014,-panel,.18),(x+.014,panel,.184)),FRM,'cargo deck traction rail')

def hinges(k,s,bone):
    x=s*PX
    # Stationary sleeves plus moving knuckles interleave on one continuous pin.
    for z in (.45,1.2955,2.14):
        stationary=[]
        for a,b in ((z-.088,z-.040),(z+.040,z+.088)):
            sleeve=rod((x,PY,a),(x,PY,b),.032,8)
            pad=block((min(x,s*1.13),PY,a),(max(x,s*1.13),-1.39,b))
            sleeve=mach(sleeve,union=[pad],cuts=[((x,PY,a-.001),(x,PY,b+.001),.012,8)])
            seat(k,sleeve,SEC,'hinge fork with machined coaxial bearing',ROOT)
        knuckle=rod((x,PY,z-.039),(x,PY,z+.039),.030,8)
        tab=block((min(x,s*1.005),PY,z-.039),(max(x,s*1.005),-1.39,z+.039))
        knuckle=mach(knuckle,union=[tab],cuts=[((x,PY,z-.05),(x,PY,z+.05),.012,8)])
        seat(k,knuckle,SEC,'moving hinge tongue and bored knuckle',bone)
        emit(k,rod((x,PY,z-.097),(x,PY,z+.097),.011,8),JNT,'retained hinge through pin')
        for zz in (z-.102,z+.097):
            emit(k,rod((x,PY,zz),(x,PY,zz+.005),.019,8),JNT,'hinge pin retaining cap')

def doors(k,s,bone):
    m=common.frame((s*.53,-1.424,1.2955),(0,-1,0),(0,0,1))
    # Broad lofted unibody leaf: bevel transitions, recessed cargo face and ribs.
    bm=transform(loft([(1.048,2.187,.024,-.062),
                      (1.048,2.187,.024,-.010),(1.014,2.153,.018,0)]),m)
    cuts=[]
    for z in (.72,1.80):
        cuts.append(boxcut((s*.53-.40,-1.45,z-.31),(s*.53+.40,-1.403,z+.31)))
    bm=mach(bm,boxes=cuts)
    emit(k,bm,PRI,'lofted cargo door with recessed strengthening bays',bone)
    # Mechanical stiffener flat across the middle; welded ends land on the leaf.
    seat(k,block((s*.53-.425,-1.434,1.19),(s*.53+.425,-1.412,1.40)),SEC,'door crossmember and actuator mounting flat',bone)
    hinges(k,s,bone)
    x=s*.34;y=-1.461
    # Twin opposing captive linear bolts, 70 mm retract, guided at both ends.
    for top in (True,False):
        tag='Top' if top else 'Bottom';bn=bone+tag+'Bolt'
        z0,z1=(1.38,1.67) if top else (.921,1.211)
        housing=rod((x,y,z0),(x,y,z1),.031,8)
        housing=mach(housing,cuts=[((x,y,z0-.01),(x,y,z1+.01),.012,8)])
        foot=block((x-.044,y, z0+.025),(x+.044,-1.424,z1-.025))
        seat(k,mach(housing,union=[foot],cuts=[((x,y,z0-.01),(x,y,z1+.01),.012,8)]),FRM,'shoot bolt cylinder and fitted mounting saddle',bone)
        a,b=(1.53,2.445) if top else (.146,1.061)
        emit(k,rod((x,y,a),(x,y,b),.012,8),JNT,'captive stainless shoot bolt',bn)
        gz=2.19 if top else .401
        guide=mach(rod((x,y,gz-.027),(x,y,gz+.027),.024,8),
                   union=[block((x-.030,y,gz-.027),(x+.030,-1.424,gz+.027))],
                   cuts=[((x,y,gz-.03),(x,y,gz+.03),.012,8)])
        seat(k,guide,SEC,'bolt guide bush with attached saddle',bone)
        rz=2.45 if top else .14
        socket=mach(rod((x,y,rz-.022),(x,y,rz+.022),.018,8),
                    cuts=[((x,y,rz-.024),(x,y,rz+.024),.012,8)])
        emit(k,socket,JNT,'fully recessed receiver bush inside header or sill')
    # Horizontal glove-sized pull on the reinforcement's uninterrupted flat,
    # outboard of the bolt cylinders. 168 mm free grip, 70 mm hand clearance.
    # The bridge and mounting feet are one lofted casting, with a true opening.
    hm=common.frame((s*.69,-1.434,1.2955),(0,-1,0),(0,0,1))
    handle=transform(loft([(.220,.044,.008,0),(.220,.044,.008,.085),
                           (.208,.038,.006,.098)]),hm)
    handle=mach(handle,boxes=[boxcut((s*.69-.084,-1.504,1.25),
                                    (s*.69+.084,-1.420,1.34))])
    seat(k,handle,JNT,'horizontal glove-clear pull with two reinforced feet',bone)
    for dx in (-.097,.097):
        seat(k,rod((s*.69+dx,-1.528,1.2955),(s*.69+dx,-1.536,1.2955),.006,6),FRM,'pull mounting captive socket head',bone)
    for x0 in (s*.11,s*.93):
        for z in (.27,2.32):
            emit(k,rod((x0,-1.424,z),(x0,-1.430,z),.008,6),JNT,'door captive hex fastener',bone)

def services(k):
    # Small powered-lock junction cabinet in the left fixed jamb, with a
    # flush diffuser in a true cut pocket and guarded fixed cable to the header.
    m=common.frame((1.151,-1.478,1.73),(0,-1,0),(0,0,1))
    bm=transform(loft([(.100,.340,.008,-.012),(.100,.340,.008,.008),(.084,.324,.006,.014)]),m)
    cutter=transform(block((-.026,.105,.007),(.026,.125,.020)),m)
    cutter.verts.index_update()
    tool=SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],faces=[[v.index for v in f.verts] for f in cutter.faces])
    bm=common.trim_seats(bm,[tool]);cutter.free()
    seat(k,bm,FRM,'fixed-jamb lock junction cabinet')
    emit(k,transform(block((-.0258,.1052,.007),(.0258,.1248,.014)),m),EMI,'flush lock status diffuser')
    for z in (1.60,1.86):
        emit(k,rod((1.151,-1.492,z),(1.151,-1.495,z),.006,6),JNT,'junction cabinet captive screw')
    # Protected conduit runs along the jamb. Both ends have socket glands;
    # clamps support the run instead of leaving a floating decorative wire.
    x,y=1.151,-1.507
    seat(k,rod((x,y,1.90),(x,y,2.43),.009,6),FRM,'protected fixed lock power conduit')
    for z in (1.91,2.08,2.42):
        collar=mach(rod((x,y,z-.012),(x,y,z+.012),.016,6),
                    union=[block((x-.021,y,z-.012),(x+.021,-1.41,z+.012))],
                    cuts=[((x,y,z-.014),(x,y,z+.014),.009,6)])
        seat(k,collar,SEC,'power conduit socket gland or retaining clamp')

def specs():
    def sequence(prefix='',reverse=False):
        keys={}
        for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):
            bn=prefix+bn
            keys[bn]=[(0,0),(21,0),(81,s*105),(96,s*105)]
            keys[bn+'TopBolt']=[(0,0),(15,-.070),(96,-.070)]
            keys[bn+'BottomBolt']=[(0,0),(15,.070),(96,.070)]
        if reverse:keys={b:[(96-f,v) for f,v in reversed(ks)] for b,ks in keys.items()}
        return (False,'BEZIER',keys)
    if DOUBLE_END:
        return {'front_open':sequence(),'rear_open':sequence('Rear'),
                'rear_close':sequence('Rear',True),'front_close':sequence('',True)}
    return {'open':sequence(),'close':sequence('',True)}

def ends():
    shift=(D-2.991)/2
    front=Matrix.Translation((0,-shift,0))
    half_turn=Matrix.Diagonal((-1.0,-1.0,1.0,1.0))
    return [('',front)]+([('Rear',half_turn@front)] if DOUBLE_END else [])

def split_modules(body):
    """Long container: separate structural and two door assembly meshes.
    All remain on one rigid rig; each exported mesh retains the 5K cap.
    """
    if not DOUBLE_END:return [body]
    objects=[]
    for label,predicate,material_test in (
            ('Structure',lambda n:n==ROOT,lambda i:i!=kit.SLOTS.index(PRI)),
            ('FormedShell',lambda n:n==ROOT,lambda i:i==kit.SLOTS.index(PRI)),
            ('FrontDoors',lambda n:n!=ROOT and not n.startswith('Rear'),lambda i:True),
            ('RearDoors',lambda n:n.startswith('Rear'),lambda i:True)):
        obj=body.copy();obj.data=body.data.copy();obj.name='SK_'+TITLE+label
        bpy.context.scene.collection.objects.link(obj)
        bm=bmesh.new();bm.from_mesh(obj.data);weights=bm.verts.layers.deform.active
        keep={g.index for g in obj.vertex_groups if predicate(g.name)}
        discard=[f for f in bm.faces if not material_test(f.material_index) or
                 not all(any(g in keep for g in v[weights].keys()) for v in f.verts)]
        bmesh.ops.delete(bm,geom=discard,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free();objects.append(obj)
    old=body.data;bpy.data.objects.remove(body,do_unlink=True);bpy.data.meshes.remove(old)
    return objects

def export_runtime(rig,meshes,stem):
    # Preserve all baked samples: FBX's default simplifier can drift during
    # the stationary unlock interval and break the mechanical interlock.
    for pb in rig.pose.bones:
        for c in list(pb.constraints):pb.constraints.remove(c)
    if not stem.endswith('_col'):common.prepare_export([rig,*meshes],HERE,stem)
    kit.select_only([rig,*meshes])
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{stem}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{stem}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_materials='EXPORT')

def refresh_exports():
    for suffix in (('_col',) if '--collision-exports-only' in sys.argv else ('','_col')):
        path=HERE/f'{NAME}{suffix}.blend'
        if not path.exists():continue
        bpy.ops.wm.open_mainfile(filepath=str(path))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and
                o.name.startswith('SK_') and ('Col' in o.name if suffix else 'Col' not in o.name)]
        export_runtime(rig,meshes,NAME+suffix)

def main():
    if '--exports-only' in sys.argv or '--collision-exports-only' in sys.argv:refresh_exports();return
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    for prefix,m in ends():
        for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):
            bn=prefix+bn
            kit.JOINT_SPECS.append((bn,ROOT,'hinge',m@Vector((s*PX,PY,1.2955)),(0,0,1),m.to_3x3()@Vector((0,-1,0)), (0,105) if s==1 else (-105,0)))
            for tag,z,limits in (('Top',1.53,(-.070,0)),('Bottom',1.061,(0,.070))):
                kit.JOINT_SPECS.append((bn+tag+'Bolt',bn,'slide',m@Vector((s*.34,-1.461,z)),(0,0,1),(0,0,1),limits))
    kit.GROUPS=();kit.ANIMATIONS=specs()
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    frame(k)
    for prefix,m in ends():
        with k.frame(m):
            for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):doors(k,s,prefix+bn)
            services(k)
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    # Independently sweep each leaf and both together with bolts withdrawn.
    for prefix,_ in ends():
        for a in range(0,106,5):
            for left,right in ((a,0),(0,-a),(a,-a)):
                states.append((f'{prefix} sweep {left} {right}',{prefix+bn:v for bn,v in dict(LeftDoor=left,RightDoor=right,
                    LeftDoorTopBolt=-.07*dimensions.HEIGHT[NAME],LeftDoorBottomBolt=.07*dimensions.HEIGHT[NAME],RightDoorTopBolt=-.07*dimensions.HEIGHT[NAME],RightDoorBottomBolt=.07*dimensions.HEIGHT[NAME]).items()}))
    for _,state in states[::15]:
        kit.reset_pose(rig)
        for bn,v in state.items():kit.set_joint(rig,joints[bn],v)
        bpy.context.view_layer.update()
        for bn,expected in kit.fk(joints,state).items():
            pb=rig.pose.bones[bn];actual=pb.matrix@pb.bone.matrix_local.inverted()
            assert max(abs(actual[i][j]-expected[i][j]) for i in range(4) for j in range(4))<1e-5,bn
    kit.reset_pose(rig);kit.check_motion(k,joints,states)
    source=[dict(label=label,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces)
            for p,label in zip(k.parts,common.LABELS)]
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps(source))
    body=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(body,rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
        # Keep a generated checkpoint of the expensive visibility pass so an
        # export-only repair never loses the validated culled geometry.
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}_culled.blend'))
    if '--draft' not in sys.argv:kit.check_coplanar(body)
    tris=kit.triangles(body)
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    modules=split_modules(body)
    counts={o.name:kit.triangles(o) for o in modules}
    markers,fixture_info=light_mounts.install_default(rig,modules,NAME)
    if '--draft' not in sys.argv:
        assert all(t<=5000 for t in counts.values()),counts
        export_runtime(rig,[*modules,*markers],NAME)
    report=dict(name=NAME,triangles=tris,meshes=counts,triangle_budget_per_mesh=5000,bounds_m=dict(lo=lo,hi=hi),
        materials=list(kit.MATERIALS),tensor_height_m=1.753,dimensions_m=dict(width=W,depth=D,height=H),
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        joints=[dict(bone=j.name,type=j.kind,parent=j.parent,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        checks=dict(connected_parts=len(k.parts),exact_solid_pairs=pairs,motion_states=len(states),no_solid_intersections=True),
        placement='floor centre; front -Y; up +Z; library only',
        mechanics='Captive powered opposing shoot bolts retract 70 mm before twin leaves swing 105 degrees outward. Three interleaved pinned hinges per leaf. Formed 8 mm wall/roof panels in structural casting.')
    dimensions.report(NAME,report,width=2.158,height=2.231,floors=[.18],ceilings=[2.517],double=True)
    report['gizmos']=fixture_info
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    open_pose={prefix+bn:{'rot':[s*105,0,0]} for prefix,_ in ends() for s,bn in ((1,'LeftDoor'),(-1,'RightDoor'))}
    open_pose.update({prefix+bn+tag+'Bolt':{'loc':[0,v,0]} for prefix,_ in ends() for bn in ('LeftDoor','RightDoor') for tag,v in (('Top',-.07),('Bottom',.07))})
    rig['preview_poses']=json.dumps({'open':open_pose,
        'unlocked':{bn+tag+'Bolt':{'loc':[0,v,0]} for bn in ('LeftDoor','RightDoor') for tag,v in (('Top',-.07),('Bottom',.07))}})
    bpy.context.scene['preview_actions']=json.dumps(list(actions))
    bpy.context.scene['showcase_frame']=json.dumps(dict(lo=[-2.1,-D/2-1.2,0],hi=[2.1,D/2+(1.2 if DOUBLE_END else 0),H]))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles, {len(k.parts)} connected parts',flush=True)

if __name__=='__main__':main()
