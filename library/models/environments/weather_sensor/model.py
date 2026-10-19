"""Industrial weather station, 2.5 m, front -Y; headless Blender 5.2.

Rigid permanently braced tripod; passive cup rotor and wind-direction vane.
Every separate manufactured insert is seated with an exact Boolean pocket.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import light_common as common
kit=common.kit
ROOT=common.ROOT
PRI,SEC,FRM,JNT,EMI=common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
NAME,TITLE='weather_sensor','WeatherSensor'
block,rod,loft=common.block,common.rod,common.loft

def transform(bm,m):
    for v in bm.verts:v.co=m@v.co
    return bm

def drum(stations,n=12):
    return kit.loft_rings([kit.ring_xy(0,0,r,z,n) for z,r in stations])

def closed_ring(rows):
    bm=bmesh.new();verts=[[bm.verts.new(p) for p in row] for row in rows]
    for a,b in zip(verts,verts[1:]+verts[:1]):
        for i in range(len(a)):
            j=(i+1)%len(a);bm.faces.new((a[i],a[j],b[j],b[i]))
    return bm

def emit(k,bm,mat,label,bone=ROOT):
    old=common.ROOT;common.ROOT=bone;old_xf=k.xf
    # Mirrored socket frames need normals recalculated AFTER reflection.
    transform(bm,old_xf);k.xf=Matrix.Identity(4)
    try:common.emit(k,bm,mat,label)
    finally:common.ROOT=old;k.xf=old_xf

def union(bm,items):
    for mesh in [bm,*items]:bmesh.ops.recalc_face_normals(mesh,faces=mesh.faces[:])
    out=kit.machine(bm,union=items)
    bmesh.ops.remove_doubles(out,verts=out.verts[:],dist=1e-6)
    edges=[e for e in out.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(out,edges=edges,sides=0)
    return out

def machine(bm,**kwargs):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    return kit.machine(bm,**kwargs)

def seat(k,bm,mat,label,bone=ROOT):
    # Fish-mouth pipe ends, brackets and service inserts to existing solids.
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    bm=common.trim_seats(bm,[p for p in k.parts if p.bone==bone])
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    emit(k,bm,mat,label,bone)

def pocket(k,body,m,w,h,label,mat=SEC):
    cutter=transform(loft([(w,h,.004,-.006),(w,h,.004,.008)]),m)
    cutter.verts.index_update()
    from types import SimpleNamespace
    p=SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],faces=[[v.index for v in f.verts] for f in cutter.faces])
    body=common.trim_seats(body,[p]);cutter.free()
    insert=transform(loft([(w-.0004,h-.0004,.0038,-.006),(w-.0004,h-.0004,.0038,0)]),m)
    return body,(insert,mat,label)

def bored(bm,at,r,y0,y1):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    out=kit.machine(bm,cuts=[((at[0],y0,at[2]),(at[0],y1,at[2]),r,6)])
    bmesh.ops.remove_doubles(out,verts=out.verts[:],dist=1e-7)
    return out

def link(a,b,r0,r1,width):
    """One machined tapered member, radiused eyes integral to its profile."""
    a,b=Vector(a),Vector(b);d=(b-a).normalized();s=Vector((-d.z,0,d.x))
    pts=[]
    for p,r,sign in ((a,r0,-1),(b,r1,1)):
        for i in range(5):
            t=math.pi*i/4
            q=p+s*(r*math.cos(t)*(-sign))+d*(r*math.sin(t)*sign)
            pts.append(tuple(q))
    bm=kit.prism_bm(pts,width,(0,1,0))
    return bm

def bearing_ring(at,y0,y1,outer,inner):
    # Polygon phase is shared with the pin and bore, so radial clearance is
    # meaningful on every facet instead of having teeth-like intersections.
    bm=drum([(y0,outer),(y1,outer)],6)
    bm=machine(bm,cuts=[((0,0,y0-.01),(0,0,y1+.01),inner,6)])
    m=Vector((0,1,0)).to_track_quat('Z','Y').to_matrix().to_4x4();m.translation=at
    return transform(bm,m)

def pin(k,p,half,r,label):
    emit(k,rod((p[0],-half,p[2]),(p[0],half,p[2]),r,6),JNT,label+' cross pin')
    for sign in (-1,1):
        emit(k,rod((p[0],sign*half,p[2]),(p[0],sign*(half+.004),p[2]),r*1.5,6),JNT,label+' flush retention cap')

def clevis(k,at,back,z0,z1,inner=.027,outer=.042,r=.008,label='clevis'):
    # U-shaped casting. Cheeks and their rear web are fused only where a
    # manufactured casting is continuous. The centre slot remains open.
    x,z=at[0],at[2]
    outline=[(back,-outer),(x+.025,-outer),(x+.025,-inner),
        (back+.018,-inner),(back+.018,inner),(x+.025,inner),
        (x+.025,outer),(back,outer)]
    body=kit.loft_rings([[(a,b,h) for a,b in outline] for h in (z0,z1)])
    body=bored(body,at,r+.0002,-outer-.01,outer+.01)
    emit(k,body,SEC,label+' bored clevis casting')

def tripod(k):
    # Separate sealed mast on a bolted flange; articulated members carry
    # loads through visible retained pins, never by intersecting the mast.
    flange=drum([(.320,.13),(.335,.13)],12)
    emit(k,flange,SEC,'mast socket mounting flange')
    emit(k,drum([(.335,.066),(2.40,.066)]),PRI,'sealed structural mast')
    for a in (0,math.tau/3,2*math.tau/3):
        x,y=.108*math.cos(a),.108*math.sin(a)
        emit(k,rod((x,y,.335),(x,y,.341),.008,6),JNT,'socket flange hex fastener')
    # Sleeve collars use a real bore and end on a planar shaft shoulder.
    for z in (.420,1.03):
        collar=machine(drum([(z-.038,.092),(z+.038,.092)],12),
            cuts=[((0,0,z-.05),(0,0,z+.05),.0662,12)])
        emit(k,collar,SEC,'tripod clamp sleeve')
    for i in range(3):
        angle=-math.pi/2+i*math.tau/3
        with k.frame(Matrix.Rotation(angle,4,'Z')):
            top=Vector((.15,0,1.03));bottom=Vector((.69,0,.058))
            # Mounting flange has its own curved mast seat; the clevis ends
            # square against its exposed radial face.
            mount=block((.074,-.048,.983),(.103,.048,1.077))
            mount=machine(mount,cuts=[((0,0,.97),(0,0,1.09),.092,12)])
            emit(k,mount,SEC,'upper clevis mast saddle')
            clevis(k,top,.103,.990,1.070,inner=.027,outer=.044,r=.009,label='leg shoulder')
            beam=link(top,bottom,.030,.023,.048)
            beam=bored(bored(beam,top,.0092,-.035,.035),bottom,.0072,-.035,.035)
            emit(k,beam,PRI,'tapered leg with bored end eyes')
            pin(k,top,.044,.009,'leg shoulder')
            # Stainless thrust washers fill the axial gap, ending 1 mm
            # short of the cheeks; they are not overlays on the painted eye.
            for y0,y1 in ((-.026,-.024),(.024,.026)):
                emit(k,bearing_ring((top.x,0,top.z),y0,y1,.023,.0092),JNT,'shoulder thrust washer')
            foot=loft([(.15,.12,.015,0),(.15,.12,.015,.016)])
            foot=transform(foot,Matrix.Translation((bottom.x,0,0)))
            emit(k,foot,SEC,'ground pad')
            clevis(k,bottom,.628,.016,.085,inner=.027,outer=.042,r=.007,label='ground pad ankle')
            pin(k,bottom,.042,.007,'ground pad ankle')
            # Brace joins a mast collar lug and a bolted saddle on the leg.
            inner=Vector((.136,0,.42));outer=top.lerp(bottom,.62)
            inner_mount=block((.078,-.033,.385),(.103,.033,.455))
            inner_mount=machine(inner_mount,cuts=[((0,0,.37),(0,0,.47),.092,12)])
            emit(k,inner_mount,SEC,'brace collar saddle')
            clevis(k,inner,.103,.397,.443,inner=.014,outer=.029,r=.005,label='brace mast anchor')
            # At the leg the clevis is on its inward radial face, with a
            # saddle fish-mouthed exactly to the member's profile.
            outer.x-=.060
            brace=link(inner,outer,.014,.014,.024)
            brace=bored(bored(brace,inner,.0052,-.035,.035),outer,.0052,-.035,.035)
            emit(k,brace,JNT,'locked diagonal brace with bored ends')
            pin(k,inner,.029,.005,'brace mast anchor')
            # Two cheeks run from the brace pivot to a seating block on the
            # leg; subtraction generates the actual inclined mating plane.
            x0,x1,web=outer.x-.018,outer.x+.075,outer.x+.022
            outline=[(x1,-.029),(x0,-.029),(x0,-.014),(web,-.014),
                (web,.014),(x0,.014),(x0,.029),(x1,.029)]
            saddle=kit.loft_rings([[(x,y,outer.z+z) for x,y in outline] for z in (-.022,.022)])
            saddle=bored(saddle,outer,.0052,-.04,.04)
            saddle=common.trim_seats(transform(saddle,k.xf),k.parts)
            emit(k,transform(saddle,k.xf.inverted()),SEC,'brace outer clevis and flush leg saddle')
            pin(k,outer,.029,.005,'brace leg anchor')

def base(k):
    body=loft([(.78,.70,.10,.035),(.86,.76,.10,.070),(.86,.76,.10,.245),(.73,.65,.085,.320)])
    inserts=[]
    for x in (-.235,.235):
        m=common.frame((x,-.38,.170),(0,-1,0),(0,0,1))
        body,ins=pocket(k,body,m,.145,.095,'flush base service panel');inserts.append(ins)
        m=common.frame((x,-.38,.240),(0,-1,0),(0,0,1))
        body,ins=pocket(k,body,m,.110,.010,'flush base status lamp',EMI);inserts.append(ins)
    # Recessed underside-facing ventilation slots on the rear service wall.
    body=machine(body,boxes=[((0,.380,.17),(.050,.040,.070))])
    emit(k,body,PRI,'lofted sealed battery and logger enclosure')
    for bm,mat,label in inserts:emit(k,bm,mat,label)
    tripod(k)

def mast_services(k):
    # Electronics pod has a continuous swept shoulder and flat instrument face.
    for z in (1.19,1.43):
        mount=union(drum([(z-.015,.088),(z+.015,.088)],12),[
            block((-.048,-.100,z-.014),(.048,-.073,z+.014))])
        mount=machine(mount,cuts=[((0,0,z-.025),(0,0,z+.025),.0662,12)])
        emit(k,mount,SEC,'logger split clamp and planar mounting pad')
    m=common.frame((0,-.100,1.31),(0,-1,0),(0,0,1))
    shell=transform(loft([(.16,.32,.024,0),(.22,.38,.030,.035),(.22,.38,.030,.115),(.18,.34,.022,.135)]),m)
    inserts=[]
    face=common.frame((0,-.235,1.31),(0,-1,0),(0,0,1))
    shell,ins=pocket(k,shell,face,.115,.19,'flush logger instrument face',FRM);inserts.append(ins)
    seat(k,shell,PRI,'lofted sealed data logger pod')
    for bm,mat,label in inserts:emit(k,bm,mat,label)
    for z in (1.27,1.36):
        seat(k,block((-.041,-.236,z-.002),(.041,-.235,z+.002)),EMI,'logger readout segment')
    # Radiation shield: ventilated downward overlapping louvers with a
    # continuous centre sensor stem. Not transparent cosmetic cylinders.
    collar=union(drum([(1.585,.088),(1.615,.088)],12),[
        block((.075,-.026,1.590),(.235,.026,1.615))])
    collar=machine(collar,cuts=[((0,0,1.57),(0,0,1.63),.0662,12)])
    emit(k,collar,SEC,'temperature probe clamp and flat mounting flange')
    emit(k,transform(drum([(1.615,.0232),(1.846,.0232)],6),Matrix.Translation((.205,0,0))),JNT,'temperature probe centre stem seated on flange')
    for z in (1.65,1.706,1.762,1.818):
        rows=[kit.ring_xy(.205,0,r,level,6) for level,r in
            ((z,.027),(z+.009,.080),(z+.022,.080),(z+.028,.058),
             (z+.028,.0234),(z,.0234))]
        emit(k,closed_ring(rows),PRI,'ventilated rain shedding radiation shield louver')
    # Rear trunk and supported service loop from base to upper instruments.
    emit(k,block((-.009,.104,.335),(.009,.118,2.40)),FRM,'rear sealed wiring conduit')
    for z in (.50,1.10,1.70,2.05):
        clamp=machine(block((-.020,.055,z-.008),(.020,.126,z+.008)),
            cuts=[((0,0,z-.02),(0,0,z+.02),.066,12)],
            boxes=[((0,.111,z),(.0184,.0144,.03))])
        emit(k,clamp,JNT,'bored conduit clamp with flush trunk seat')
    # Logger wiring passes internally through its sealed mast saddle.
    # Crossarm clamp, bolted rectangular beam sockets and upright sensor
    # flanges. Each beam terminates at a socket or flange mating plane.
    collar=machine(drum([(2.105,.096),(2.163,.096)],12),
        cuts=[((0,0,2.09),(0,0,2.18),.0662,12)],
        boxes=[((0,.075,2.134),(.018,.018,.080))])
    emit(k,collar,SEC,'instrument crossarm mast clamp')
    for s in (-1,1):
        with k.frame(Matrix.Scale(s,4,Vector((1,0,0)))):
            saddle=block((.075,-.033,2.108),(.115,.033,2.160))
            saddle=machine(saddle,cuts=[((0,0,2.09),(0,0,2.18),.096,12)])
            emit(k,saddle,SEC,'crossarm beam mounting socket')
            emit(k,block((.115,-.018,2.116),(.335,.018,2.150)),PRI,'crossarm rectangular beam')
            emit(k,block((.335,-.033,2.116),(.425,.033,2.150)),SEC,'instrument pedestal mounting flange')
            emit(k,rod((.390,0,2.150),(.390,0,2.30),.030,8),SEC,'instrument pedestal')
            for x,y in ((.345,-.023),(.415,.023)):
                emit(k,rod((x,y,2.150),(x,y,2.154),.004,6),JNT,'pedestal flange screw')
    for x in (-.39,.39):
        emit(k,rod((x,0,2.30),(x,0,2.318),.020,12),JNT,'instrument bearing spindle')
    emit(k,drum([(2.40,.066),(2.412,.085),(2.485,.10),(2.50,.075)],8),PRI,'sealed GNSS antenna radome')

def dish(k):
    m=common.frame((0,-.16,2.235),(0,-1,.28),(0,0,1))
    # Parabolic reflector has real wall thickness and a raised rolled rim.
    rings=[]
    for r in (.001,.12,.18,.23):
        rings.append(kit.ring_xy(0,0,r,r*r/.72,20))
    for r in (.23,.18,.12,.001):
        rings.append(kit.ring_xy(0,0,r,r*r/.72-.006,20))
    bm=union(kit.loft_rings(rings),[rod((0,0,-.025),(0,0,0),.035,8)])
    bm=transform(bm,m)
    emit(k,bm,PRI,'parabolic telemetry reflector with six millimetre wall')
    clamp=union(drum([(2.203,.095),(2.267,.095)],12),[
        block((-.036,-.110,2.207),(.036,-.075,2.263))])
    clamp=machine(clamp,cuts=[((0,0,2.19),(0,0,2.28),.0662,12)])
    seat(k,clamp,SEC,'telemetry dish mast clamp and flat mounting boss')
    saddle=transform(rod((0,0,-.055),(0,0,-.025),.026,8),m)
    seat(k,saddle,SEC,'reflector rear mast saddle')
    # Feed supported by a single offset strut, terminating on reflector rim.
    start=m@Vector((0,-.19,.19*.19/.72))
    mid=m@Vector((0,-.12,.18));end=m@Vector((0,0,.18))
    support=union(rod(start,mid,.006,6),[rod(mid,end,.006,6)])
    seat(k,support,JNT,'reflector supported offset feed arm')
    seat(k,transform(rod((0,0,.16),(0,0,.20),.016,8),m),FRM,'telemetry feed horn')

def instruments(k):
    for bone,x in (('Anemometer',-.39),('WindVane',.39)):
        bm=rod((x,0,2.318),(x,0,2.350),.034,12)
        if bone=='Anemometer':
            emit(k,bm,JNT,'cup rotor sealed bearing hub',bone)
            for i in range(3):
                a=i*math.tau/3
                cm=common.frame((x+.17*math.cos(a),.17*math.sin(a),2.335),(-math.sin(a),math.cos(a),0),(0,0,1))
                # Open hollow cups, formed hemisphere approximated by sections.
                cups=kit.loft_rings([kit.ring_xy(0,0,r,z,6) for z,r in
                    ((-.045,.004),(-.020,.043),(0,.047),(.002,.043),(-.019,.039),(-.039,.004))])
                seat(k,transform(cups,cm),PRI,'hollow wind anemometer cup',bone)
                # Strut seats on the cup's outside hemisphere; it never
                # continues into the open cup. Cut the strut to that shell.
                radial=Vector((math.cos(a),math.sin(a),0))
                normal=Vector((-math.sin(a),math.cos(a),0))
                end=Vector((x,0,2.335))+.127*radial-.020*normal
                seat(k,rod((x,0,2.335),end,.006,6),JNT,'rotor strut with flush outside cup seat',bone)
        else:
            emit(k,bm,SEC,'wind vane sealed bearing hub',bone)
            seat(k,rod((x,-.18,2.335),(x,.20,2.335),.006,6),JNT,'wind vane boom',bone)
            seat(k,block((x-.005,.105,2.29),(x+.005,.22,2.39)),SEC,'wind vane tail fin',bone)

def specs():
    return {'measure':(True,'LINEAR',{
        'Anemometer':[(f,f*6) for f in range(121)],
        'WindVane':[(f,25*math.sin(math.tau*f/120)) for f in range(121)]}),
        'gust':(True,'LINEAR',{
        'Anemometer':[(f,f*12) for f in range(91)],
        'WindVane':[(f,45*math.sin(math.tau*f/90)) for f in range(91)]})}

def details(k):
    # Radial grub locks secure the bored sleeves to the mast. Only the
    # external hex heads are modelled; their hidden threads remain internal.
    for z,r in ((.42,.092),(1.03,.092),(1.19,.088),(1.43,.088),(1.60,.088),(2.134,.096)):
        angle=math.pi*7/12
        n=Vector((math.cos(angle),math.sin(angle),0))
        at=n*(r*math.cos(math.pi/12))+Vector((0,0,z))
        m=common.frame(at,n,(0,0,1))
        emit(k,transform(rod((0,0,0),(0,0,.004),.005,6),m),JNT,'collar radial locking screw head seated on facet')
    for x in (-.075,.075):
        for z in (1.18,1.44):
            emit(k,rod((x,-.235,z),(x,-.239,z),.006,6),JNT,'logger cover captive hex screw')
    for x in (-.29,-.18,.18,.29):
        for z in (.140,.200):
            emit(k,rod((x,-.38,z),(x,-.384,z),.005,6),JNT,'base service panel captive hex screw')
    # Mitred flexible wiring loom; connector backs seat on the enclosure and
    # the mast's rear trunk. The loop gives service slack above the battery.
    pts=list(map(Vector,[(.19,.330,.20),(.19,.415,.20),(.19,.445,.25),
        (.15,.445,.36),(.05,.400,.43),(0,.20,.43),(0,.080,.43)]))
    rings=[]
    for i,p in enumerate(pts):
        axis=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        u=axis.cross(Vector((0,0,1))).normalized();v=axis.cross(u)
        rings.append([p+.007*(u*math.cos(j*math.tau/6)+v*math.sin(j*math.tau/6)) for j in range(6)])
    seat(k,kit.loft_rings(rings),FRM,'protected logger service cable loop')

def main():
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('Anemometer',ROOT,'hinge',(-.39,0,2.318),(0,0,1),(0,-1,0),(-1080,1080)),
        ('WindVane',ROOT,'hinge',(.39,0,2.318),(0,0,1),(0,-1,0),(-180,180))]
    kit.GROUPS=();kit.ANIMATIONS=specs()
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    base(k);mast_services(k);dish(k);instruments(k);details(k)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[])
    states=[(f'{name} frame {f}',{bone:dict(keys)[f] for bone,keys in spec[2].items()})
        for name,spec in kit.ANIMATIONS.items() for f in range(int(actions[name].frame_range[1])+1)]
    states += [(f'sweep {a}',{'Anemometer':a,'WindVane':a}) for a in range(-180,181,10)]
    kit.check_motion(k,joints,states)
    body=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(body,rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
    kit.check_coplanar(body);tris=kit.triangles(body)
    if '--draft' not in sys.argv:assert tris<=5000,tris
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    assert abs(lo[2])<1e-6 and abs(hi[2]-2.5)<1e-6,(lo,hi)
    if '--draft' not in sys.argv:
        common.prepare_export([rig,body],HERE,NAME)
        # Motion has been baked and verified; exporters require deform bones
        # without Blender-only limit constraints. Limits remain in the spec.
        for pb in rig.pose.bones:
            for constraint in list(pb.constraints):pb.constraints.remove(constraint)
        # Use the existing animated environment prop's runtime export settings.
        import importlib.util
        spec=importlib.util.spec_from_file_location('weather_export',HERE.parent/'solar_tower/model.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        mod.HERE,mod.NAME=HERE,NAME;mod.export_runtime(rig,body)
    report=dict(name=NAME,triangles=tris,triangle_budget=5000,bounds_m=dict(lo=lo,hi=hi),
        materials=list(kit.MATERIALS),tensor_height_m=1.753,
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=True) for n,a in actions.items()},
        joints=[dict(bone=j.name,type=j.kind,parent=j.parent,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        checks=dict(connected_parts=len(k.parts),exact_solid_pairs=pairs,motion_states=len(states),no_solid_intersections=True),
        placement='floor centre; front -Y; up +Z; library only')
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    rig['preview_poses']=json.dumps({'crosswind':{'Anemometer':{'rot':[60,0,0]},'WindVane':{'rot':[45,0,0]}},'reverse_wind':{'WindVane':{'rot':[180,0,0]}}})
    bpy.context.scene['preview_actions']=json.dumps(list(actions))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles, {len(k.parts)} connected parts',flush=True)

if __name__=='__main__':main()
