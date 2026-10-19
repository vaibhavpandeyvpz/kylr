"""Grounded pulse turret; library only, headless Blender 5.2, metres, front -Y.

Manufactured shells, captured trunnions and sealed rotary drives. Armed and unarmed poses.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
    'M_Wire': 'Diffuse',
}
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'environments'))
import light_common as common
f=common.kit
ROOT,YAW,PITCH,BARREL='Root','Yaw','Elevation','Barrel'
PRI,SEC,FRM,JNT,EMI=common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
WIRE,BRZ='M_Wire','M_Bronze'
NAME,TITLE='pulse_gun','PulseGun'
BUDGET=7500
GUN_RISE=.006                         # receiver crown reaches exact .6 m at rest
PIVOT=Vector((0,.04,.49+GUN_RISE))
AXIS_Z=.505+GUN_RISE
MUZZLE=(0,-.435,AXIS_Z)
ROOT_SEAT_CLEARANCES=[]

def xf(bm,m):
    for v in bm.verts:v.co=m@v.co
    return bm

def mach(bm,**kw):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    return f.machine(bm,**kw)

def emit(k,bm,mat,label,bone=ROOT):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    bmesh.ops.dissolve_limit(bm,angle_limit=1e-5,verts=bm.verts[:],edges=bm.edges[:],use_dissolve_boundaries=False)
    old=common.ROOT;common.ROOT=bone
    try:
        common.emit(k,bm,mat,label)
        k.parts[-1].line=label
    finally:common.ROOT=old

def drum(rows,n=24):
    return f.loft_rings([f.ring_xy(0,0,r,z,n) for z,r in rows])

def ring_profile(profile,n=24):
    rows=[f.ring_xy(0,0,r,z,n) for z,r in profile]
    bm=bmesh.new();vs=[[bm.verts.new(p) for p in row] for row in rows]
    for a,b in zip(vs,vs[1:]+vs[:1]):
        for i in range(n):j=(i+1)%n;bm.faces.new((a[i],a[j],b[j],b[i]))
    return bm

def annulus(z0,z1,outer,inner,n=24):
    return ring_profile(((z0,outer),(z1,outer),(z1,inner),(z0,inner)),n)

def axis_frame(origin,axis):
    m=Vector(axis).to_track_quat('Z','Y').to_matrix().to_4x4();m.translation=origin
    return m

def bolt(k,at,axis,label,bone=ROOT,r=.006):
    m=axis_frame(at,axis)
    bm=mach(common.rod((0,0,0),(0,0,.004),r,6),cuts=[((0,0,.0015),(0,0,.006),r*.45,6 if r>.006 else 4)])
    emit(k,xf(bm,m),JNT,label,bone)

def sector(profile,centre,span=40,n=4):
    """Closed swept radial casting: all skins and end faces share the same stations."""
    bm=bmesh.new()
    rows=[]
    for z,r in profile:
        rows.append([bm.verts.new((r*math.cos(math.radians(centre-span/2+span*i/n)),
                                   r*math.sin(math.radians(centre-span/2+span*i/n)),z)) for i in range(n+1)])
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(n):bm.faces.new((a[i],a[i+1],b[i+1],b[i]))
    bm.faces.new(tuple(row[0] for row in reversed(rows)))
    bm.faces.new(tuple(row[-1] for row in rows))
    return bm

def pipe(k,points,r,mat,label,bone=ROOT):
    pts=f.fillet(points,r*2.5,n=1);rings=[]
    n=6
    previous=None;u=None
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized()
        if previous is None:
            seed=Vector((0,0,1))
            if abs(tangent.dot(seed))>.95:seed=Vector((1,0,0))
            u=tangent.cross(seed).normalized()
        else:
            # Parallel transport keeps the section oriented through vertical
            # bends; tangent x world-Z collapses on vertical straight sections.
            u=previous.rotation_difference(tangent)@u
            u=(u-tangent*u.dot(tangent)).normalized()
        v=tangent.cross(u).normalized();previous=tangent
        row=[p+r*(u*math.cos(j*math.tau/n)+v*math.sin(j*math.tau/n)) for j in range(n)]
        assert all(abs((q-p).length-r)<1e-7 for q in row)
        rings.append(row)
    emit(k,f.loft_rings(rings),mat,label,bone)

def foundation(k):
    # A machined perimeter chassis, with swept retaining bridges fused into its rim.
    frame=drum([(0,.49),(.012,.5),(.034,.5),(.048,.478)],32)
    bridges=[]
    for a in range(0,360,90):
        rows=[]
        for z,w,h,c,r in [(.024,.054,.048,.011,.457),(.052,.054,.048,.011,.454),
                          (.092,.054,.048,.011,.440),(.141,.054,.048,.011,.420),
                          (.186,.054,.048,.011,.388),(.214,.054,.048,.011,.356)]:
            rows.append([(r+y,x,z) for x,y,_ in common.outline(w,h,c,z)])
        bridges.append(xf(f.loft_rings(rows),Matrix.Rotation(math.radians(a),4,'Z')))
    frame=mach(frame,union=bridges)
    emit(k,frame,SEC,'unibody perimeter chassis with swept armour bridges')
    emit(k,drum([(.048,.3425),(.15,.3425),(.19,.308)],16),FRM,'annular stationary power housing')
    outer=lambda z:.447+(.431-.447)*(z-.061)/.082
    for i,a in enumerate([45+90*i for i in range(4)]):
        cover=sector([(.048,.444),(.061,.447),(.143,.431),(.191,.377),(.191,.348),(.048,.348)],a,80,6)
        if True:
            # Flared buttress grows out of the curved casing, as one cast component.
            tooling=mesh_part(cover.copy())
            casing=f.Part(ROOT,'uncut quadrant casing',[Vector(v) for v in tooling.verts],tooling.faces,False,exact=True)
            rows=[]
            for z,w,h,c,r in [(.080,.088,.074,.016,.392),(.198,.074,.064,.014,.397),
                              (.240,.060,.052,.012,.403),(.370,.060,.052,.012,.403),
                              (.385,.052,.044,.010,.403)]:
                rows.append([(r+y,x,z) for x,y,_ in common.outline(w,h,c,z)])
            rotation=Matrix.Rotation(math.radians(a),4,'Z')
            seat=[rotation@Vector(v) for v in rows[0]]
            assert all(casing.buried(v) for v in seat),'unsupported guard root'
            clearance=min(casing.bvh.find_nearest(v)[3] for v in seat)
            assert clearance>.002,('guard root embedding',clearance)
            ROOT_SEAT_CLEARANCES.append(clearance)
            cover=mach(cover,union=[xf(f.loft_rings(rows),rotation)])
        # Sector gaps follow the full width of the cast retaining bridges.
        # Actual inset in the front facet, with a mechanically retained blank indicator.
        n=Vector((math.cos(math.radians(a)),math.sin(math.radians(a)),0))
        face=common.frame(n*.430+Vector((0,0,.117)),n,Vector((0,0,1)))
        cover=mach(cover,subtract=[([face@Vector(v) for v in common.outline(.135,.018,.004,0)],n,.034)])
        emit(k,cover,PRI,'lofted quadrant armour with integral protective buttress')
        emit(k,xf(common.loft([(.1338,.0168,.0034,-.017),(.1338,.0168,.0034,-.009)]),face),FRM,'sealed power indicator backing')
        emit(k,xf(common.loft([(.127,.011,.002,-.009),(.127,.011,.002,-.006)]),face),EMI,'blank recessed sector power indicator')
        # Indicator backplane seats in the machined recess; its perimeter remains behind the shell.
        for t in (0,):
            at=n*.462+Vector((0,0,.048))
            bolt(k,at,(0,0,1),'foundation anchoring screw',r=.0045)
        if True:
            fn=n
            ff=common.frame(n*.429+Vector((0,0,.300)),fn,(0,0,1))
            # The shallow slot is machined into the flat front land of the loft.
            # A separate flush, unlit insert defines the detachable impact strip.
            land=xf(common.loft([(.014,.058,.002,-.004),(.014,.058,.002,.001)]),ff)
            land=common.trim_seats(land,[p for p in k.parts if p.bone==ROOT])
            emit(k,land,SEC,'formed buttress wear strip seated to casting')
    # Visible slew cartridge: the buried power train is deliberately not authored.
    emit(k,annulus(.19,.197,.292,.2766,16),BRZ,'slew bearing exposed cartridge flange')
    emit(k,drum([(.19,.271),(.205,.271),(.213,.261)],16),JNT,'slew thrust rotor',YAW)
    deck=drum([(.213,.261),(.218,.33),(.223,.33)],16)
    lugs=[common.block((-.05,-.305,.1972),(.05,-.255,.202))]
    lugs += [common.block((s*.026-.006,-.300,.1972),(s*.026+.006,-.260,.252)) for s in (-1,1)]
    deck=mach(deck,union=lugs,boxes=[((0,-.275,.240),(.040,.090,.065))],
              cuts=[((-.060,-.280,.223),(.060,-.280,.223),.0088,8)])
    deck=common.trim_seats(deck,[q for q in k.parts if q.bone==YAW])
    emit(k,deck,SEC,'flared yoke deck with machined actuator pivot pocket',YAW)
    # Four external conduits, compression ends seated into the curved shells.
    for a in (45,135,225,315):
        def at(t,r):return Vector((r*math.cos(math.radians(t)),r*math.sin(math.radians(t)),.080))
        pts=[at(a-12,.444),at(a-12,.463),*[at(a+t,.463) for t in (0,)],at(a+12,.463),at(a+12,.444)]
        pipe(k,pts,.0042,JNT,'formed external coolant conduit')
        for t in (a-12,a+12):
            n=Vector((math.cos(math.radians(t)),math.sin(math.radians(t)),0))
            gland=xf(annulus(0,.018,.009,.00495,6),axis_frame(at(t,.435),n))
            gland=common.trim_seats(gland,[p for p in k.parts if p.bone==ROOT and 'quadrant armour' in str(p.line)])
            emit(k,gland,SEC,'bored conduit compression coupling')

def cradle(k):
    # Same construction as weapon_holder / item_cradle: one profiled casting,
    # carved bores and relief, then a consistent bevel around its flat flanks.
    yc,zc=PIVOT.y,PIVOT.z
    for sign in (-1,1):
        xc=sign*.16;half=.038;head_r=.066
        right=[(yc-.120,.223),(yc+.120,.223),(yc+.120,.245),
               (yc+.090,.275),(yc+.046,.340),(yc+.046,.408)]
        crown=[(yc+head_r*math.cos(math.radians(t)),zc+head_r*math.sin(math.radians(t)))
               for t in range(-60,241,30)]
        left=[(yc-.046,.408),(yc-.046,.340),(yc-.090,.275),(yc-.120,.245)]
        profile=[(xc,y,z) for y,z in right+crown+left]
        web=[(xc,yc+y,.354+z) for y,z,_ in common.outline(.046,.090,.008,0)]
        seats=[((xc,y,.240),(xc,y,.285),.007,8) for y in (yc-.094,yc+.094)]
        old=set(k.bm.faces)
        f.carve(k,f.prism_bm(profile,half*2,(1,0,0)),YAW,SEC,inner=SEC,
                cuts=[((xc-.055,yc,zc),(xc+.055,yc,zc),.046,8),*seats],
                subtract=[(web,(1,0,0),.14)],bevel=.003,
                flanks=[((1,0,0),xc-half),((1,0,0),xc+half)])
        for face in set(k.bm.faces)-old:face.material_index=f.SLOTS.index(SEC)
        label='single-profile machined yoke, centred web and radiused bearing crown'
        k.parts[-1].line=label;common.LABELS.append(label)
        for y in (yc-.094,yc+.094):bolt(k,(xc,y,.240),(0,0,1),'recessed foot fastener on centred bolt line',YAW,r=.004)
        m=axis_frame(PIVOT,(sign,0,0))
        emit(k,xf(annulus(.122,.198,.0458,.0379,8),m),BRZ,'flush elevation journal cartridge',YAW)
        emit(k,xf(ring_profile([(.198,.062),(.206,.062),(.214,.054),(.214,.0379),(.198,.0379)],12),m),PRI,'coaxial bearing cover on full flat crown land',YAW)
        emit(k,xf(drum([(.199,.0348),(.215,.0348),(.219,.029)],12),m),JNT,'journal retaining spindle cap',PITCH)
        for angle in (45,135,225,315):
            t=math.radians(angle)
            bolt(k,m@Vector((.047*math.cos(t),.047*math.sin(t),.214)),(sign,0,0),'bearing cover captive screw',YAW,r=.003)
    emit(k,xf(drum([(-.199,.0348),(-.115,.0348),(-.111,.055),(.111,.055),(.115,.0348),(.199,.0348)],12),axis_frame(PIVOT,(1,0,0))),JNT,'captured shouldered elevation spindle',PITCH)

def gun(k):
    z=AXIS_Z
    receiver=xf(drum([(0,.057),(.012,.073),(.05,.080),(.24,.080),(.27,.067)],12),axis_frame((0,.25,z),(0,-1,0)))
    pad=common.block((.046,.111,z-.033),(.084,.220,z+.033))
    receiver=mach(receiver,union=[pad],cuts=[((-.13,PIVOT.y,PIVOT.z),(.13,PIVOT.y,PIVOT.z),.0552,12)],
                  boxes=[((.09,.165,z),(.036,.087,.046))])
    emit(k,receiver,SEC,'cylindrical pulse breech with integral console land',PITCH)
    face=common.frame((.072,.165,z),(1,0,0),(0,0,1))
    emit(k,xf(common.loft([(.0866,.0456,.003,0),(.0866,.0456,.003,.003)]),face),FRM,'display recessed gasket and backplate',PITCH)
    emit(k,xf(common.ring(.0866,.0456,.003,.068,.032,.002,.003,.010),face),JNT,'machined removable display bezel',PITCH)
    emit(k,xf(common.loft([(.0676,.0316,.0018,.003),(.0676,.0316,.0018,.010)]),face),EMI,'blank emissive side console',PITCH)
    for y in (-.038,.038):bolt(k,face@Vector((y,0,.010)),(1,0,0),'console socket screw',PITCH,r=.0024)
    # Formed accelerator shell, a true hollow tapered cylinder with milled through vents.
    m=axis_frame((0,-.02,z),(0,-1,0))
    shroud=xf(ring_profile([(0,.069),(.023,.089),(.060,.089),(.270,.078),(.350,.066),
                           (.350,.053),(.270,.062),(.060,.073),(.023,.073),(0,.053)],12),m)
    tools=[];steps=common.CORNER_STEPS;common.CORNER_STEPS=2
    for t in (45,135,225,315):
        n=Vector((math.cos(math.radians(t)),0,math.sin(math.radians(t))))
        for d in (.095,.147,.199,.251):
            cm=common.frame(Vector((0,-.02-d,z))+n*.076,n,(0,1,0))
            tools.append(mesh_part(xf(common.loft([(.050,.027,.009,-.04),(.050,.027,.009,.035)]),cm)))
    common.CORNER_STEPS=steps
    shroud=common.trim_seats(shroud,tools)
    shroud=mach(shroud,boxes=[((s*.093,-.209,z),(.046,.199,.020)) for s in (-1,1)])
    emit(k,shroud,PRI,'lofted accelerator shell with sixteen radiused cooling windows',PITCH)
    for s in (-1,1):
        emit(k,common.block((min(s*.070,s*.073),-.3075,z-.0097),(max(s*.070,s*.073),-.1105,z+.0097)),EMI,'flush accelerator energy rail',PITCH)
    emit(k,xf(ring_profile([(0,.053),(.023,.073),(.025,.073),(.025,.0302),(0,.0302)],12),m),FRM,'rear tapered accelerator guide bush',PITCH)
    emit(k,xf(ring_profile([(0,.0558125),(.025,.053),(.025,.0302),(0,.0302)],12),axis_frame((0,-.345,z),(0,-1,0))),FRM,'front tapered accelerator guide bush',PITCH)
    # Recoiling core and integral waveguide nose are distinct from stationary armour.
    core=[(0,.033),(.012,.033),(.018,.029),(.130,.029),(.130,.043),(.143,.043),(.143,.038),
          (.220,.038),(.220,.043),(.228,.043),(.228,.038),(.305,.038),(.305,.043),(.313,.043),
          (.313,.038),(.372,.038),(.372,.029),(.385,.029),(.385,.018),(0,.018)]
    emit(k,xf(ring_profile(core,8),axis_frame(MUZZLE,(0,1,0))),JNT,'unibody bored pulse waveguide with integral induction cooling fins',BARREL)
    muzzle=xf(ring_profile([(0,.066),(.015,.073),(.060,.073),(.065,.065),(.065,.035),(0,.053)],16),axis_frame((0,-.37,z),(0,-1,0)))
    muzzle=mach(muzzle,boxes=[((0,-.430,z),(.18,.062,.034)),((0,-.392,z+.068),(.039,.025,.054)),((0,-.392,z-.068),(.039,.025,.054))])
    emit(k,muzzle,SEC,'forked muzzle armour with upper and lower machined cooling windows',PITCH)
    # Rear removable heat exchanger: integral fins, flat machined connection face.
    heat=common.rod((0,.25,z),(0,.272,z),.032,16)
    fins=[common.block((x-.002,.270,z-.022),(x+.002,.282,z+.022)) for x in (-.020,0,.020)]
    heat=mach(heat,union=fins)
    emit(k,heat,FRM,'rear breech heat exchanger with integral fins',PITCH)
    for s in (-1,1):
        # Two gland bosses share their actual broad rear seating plane.
        for h in (-.032,.032):
            boss=xf(annulus(0,.016,.010,.00495,6),axis_frame((s*.032,.25,z+h),(0,1,0)))
            emit(k,boss,SEC,'rear coolant bored compression boss',PITCH)
        pts=[(s*.032,.25,z-.032),(s*.032,.278,z-.032),(s*.069,.278,z-.032),(s*.069,.329,z-.032),
             (s*.069,.329,z+.032),(s*.069,.278,z+.032),(s*.032,.278,z+.032),(s*.032,.25,z+.032)]
        pipe(k,pts,.0042,WIRE if s<0 else JNT,'gland-terminated breech coolant loop',PITCH)

def mesh_part(bm):
    """Closed exact tooling mesh accepted by the shared seat Boolean helper."""
    from types import SimpleNamespace
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:]);bmesh.ops.triangulate(bm,faces=bm.faces[:])
    bm.verts.ensure_lookup_table();out=SimpleNamespace(verts=[tuple(v.co) for v in bm.verts],faces=[tuple(v.index for v in p.verts) for p in bm.faces]);bm.free()
    return out

def resolve_actuator(joints):
    a,b=Vector((0,-.280,.223)),Vector((0,-.105,.385+GUN_RISE))
    distances=[(f.fk(joints,{PITCH:e})[PITCH]@b-a).length for e in range(61)]
    p=f.PistonDef('Elevator',YAW,a,PITCH,b,.018)
    p.stroke=min(distances),max(distances);p.rest=(b-a).length
    p.cyl_len=p.stroke[0]*.89;p.rod_len=p.stroke[0]*.85;p.overlap=p.cyl_len+p.rod_len-p.stroke[1]
    assert p.overlap>.035
    return [p]

def actuator(k,p):
    a,b=p.a,p.b;d=(b-a).normalized()
    for at,bone,base,top in ((b,PITCH,.449+GUN_RISE,.457+GUN_RISE),):
        # Clevis cheeks are welded to a broad flange; bored pin passes through both.
        mount=common.block((-.05,at.y-.025,base),(.05,at.y+.025,base+.008))
        ear_low=base if bone==YAW else .363+GUN_RISE
        for s in (-1,1):mount=mach(mount,union=[common.block((s*.026-.006,at.y-.020,ear_low),(s*.026+.006,at.y+.020,top))])
        mount=mach(mount,cuts=[((-.05,at.y,at.z),(.05,at.y,at.z),.0088,8)])
        near=[q for q in k.parts if q.bone==bone and all(q.lo[i]<max(v.co[i] for v in mount.verts) and q.hi[i]>min(v.co[i] for v in mount.verts) for i in range(3))]
        mount=common.trim_seats(mount,near)
        assert len(mount.verts),('empty actuator mount',bone)
        emit(k,mount,SEC,'actuator machined fork and seating flange',bone)
        emit(k,common.rod(at+Vector((-.038,0,0)),at+Vector((.038,0,0)),.008,8),JNT,'captured hydraulic clevis pin',bone)
    emit(k,common.rod(a+Vector((-.038,0,0)),a+Vector((.038,0,0)),.008,8),JNT,'captured deck hydraulic clevis pin',YAW)
    cyl=common.rod(a+d*.013,a+d*p.cyl_len,.018,8)
    cyl=mach(cyl,union=[common.rod(a+Vector((-.0197,0,0)),a+Vector((.0197,0,0)),.019,8)],
             cuts=[(a+Vector((-.025,0,0)),a+Vector((.025,0,0)),.0088,8),(a+d*.032,a+d*(p.cyl_len+.001),.0098,8)])
    emit(k,cyl,JNT,'machined metal hydraulic cylinder with integral pinned eye',p.cylinder)
    emit(k,xf(annulus(p.cyl_len-.012,p.cyl_len,.0198,.0182,8),axis_frame(a,d)),SEC,'cylinder rod gland retaining ring',p.cylinder)
    rod=common.rod(b-d*.012,b-d*p.rod_len,.009,8)
    rod=mach(rod,union=[common.rod(b+Vector((-.0197,0,0)),b+Vector((.0197,0,0)),.018,8)],
             cuts=[(b+Vector((-.025,0,0)),b+Vector((.025,0,0)),.0088,8)])
    emit(k,rod,JNT,'hydraulic piston rod with integral bored eye',p.rod)

def marker(rig,name,bone,at):
    obj=bpy.data.objects.new(name,None);obj.empty_display_type='ARROWS';obj.empty_display_size=.045
    bpy.context.scene.collection.objects.link(obj)
    obj.parent,obj.parent_type,obj.parent_bone=rig,'BONE',bone
    b=rig.data.bones[bone]
    obj.matrix_parent_inverse=(rig.matrix_world@b.matrix_local@Matrix.Translation((0,b.length,0))).inverted()
    forward,up=Vector((0,-1,0)),Vector((0,0,1))
    basis=Matrix((forward.cross(up),forward,up)).transposed().to_4x4()
    basis.translation=at
    obj.matrix_basis=basis
    return obj

def check_coplanar(obj):
    """Exact shared-plane test, including diagonal surfaces with tied dominant axes."""
    bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.triangulate(bm,faces=bm.faces[:])
    pieces={};number=0
    for face in bm.faces:
        if face in pieces:continue
        todo=[face];pieces[face]=number
        while todo:
            for edge in todo.pop().edges:
                for other in edge.link_faces:
                    if other not in pieces:pieces[other]=number;todo.append(other)
        number+=1
    planes={}
    for face in bm.faces:
        if face.calc_area()>1e-10:
            n=face.normal;planes.setdefault((*[round(x,3) for x in n],round(n.dot(face.verts[0].co),4)),[]).append(face)
    def clip(subject,cut):
        area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(cut,cut[1:]+cut[:1]));sign=1 if area>0 else -1
        for a,b in zip(cut,cut[1:]+cut[:1]):
            def dist(p):return sign*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
            result=[]
            for p,q in zip(subject,subject[1:]+subject[:1]):
                dp,dq=dist(p),dist(q)
                if dp>=0:result.append(p)
                if (dp>0)!=(dq>0) and abs(dp-dq)>1e-20:
                    t=dp/(dp-dq);result.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
            subject=result
            if not subject:break
        return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(subject,subject[1:]+subject[:1])))/2
    checked=0
    for faces in planes.values():
        for i,a in enumerate(faces):
            for b in faces[:i]:
                if pieces[a]==pieces[b] or a.normal.dot(b.normal)<1-1e-7:continue
                if max(abs(a.normal.dot(v.co-a.verts[0].co)) for v in b.verts)>2e-6:continue
                axis=max(range(3),key=lambda d:abs(a.normal[d]));uv=[d for d in range(3) if d!=axis]
                pa,pb=[[(v.co[uv[0]],v.co[uv[1]]) for v in face.verts] for face in (a,b)]
                overlap=clip(pa,pb);checked+=1
                assert overlap<1e-8,('coplanar overlap',tuple(a.calc_center_median()),overlap,[tuple(v.co) for v in a.verts],[tuple(v.co) for v in b.verts])
    bm.free();return checked

def check_manufacturing(k):
    """Drawing datums tested against the actual carved meshes, not just bone axes."""
    yokes=[p for p in k.parts if 'single-profile machined yoke' in str(p.line)]
    assert len(yokes)==2
    symmetry=0.0
    for p in yokes:
        assert abs((p.lo.y+p.hi.y)/2-PIVOT.y)<1e-5
        assert abs((p.hi.x-p.lo.x)-.076)<1e-5
        for v in p.verts:
            reflected=Vector((v.x,2*PIVOT.y-v.y,v.z))
            symmetry=max(symmetry,p.bvh.find_nearest(reflected)[3])
    assert symmetry<2e-5,('yoke contour symmetry',symmetry)
    mirror=max(yokes[1].bvh.find_nearest(Vector((-v.x,v.y,v.z)))[3] for v in yokes[0].verts)
    assert mirror<2e-5,('paired yoke symmetry',mirror)
    covers=[p for p in k.parts if 'coaxial bearing cover' in str(p.line)]
    journals=[p for p in k.parts if 'flush elevation journal' in str(p.line)]
    seating=0.0
    for p in covers:
        for v in p.verts:
            if abs(abs(v.x)-.198)<1e-5:
                seating=max(seating,min(q.bvh.find_nearest(v)[3] for q in yokes+journals))
    assert seating<2e-5,('unsupported cover back face',seating)
    return dict(yoke_contour_symmetry_error_m=symmetry,paired_yoke_error_m=mirror,
                bearing_cover_seating_error_m=seating,yoke_thickness_m=.076,
                shared_y_datum_m=float(PIVOT.y),bridge_width_m=.054,
                guard_roots_fully_embedded=True,minimum_guard_root_clearance_m=min(ROOT_SEAT_CLEARANCES))

def main():
    common.CORNER_STEPS=1;common.LABELS.clear();ROOT_SEAT_CLEARANCES.clear()
    f.NAME,f.TITLE=NAME,TITLE
    f.MATERIALS[EMI]=((.08,.65,.85),0,.35,3)
    f.MATERIALS[WIRE]=((.025,.03,.035),0,.65,0)
    f.MATERIALS[BRZ]=((.30,.20,.095),.8,.32,0)
    f.SLOTS=list(f.MATERIALS)
    f.reset_scene();f.build_materials()
    f.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),f.UP,f.UP,None),
        (YAW,ROOT,'hinge',(0,0,.20),(0,0,1),(0,-1,0),(-180,180)),
        (PITCH,YAW,'hinge',tuple(PIVOT),(-1,0,0),(0,0,1),(0,60)),
        (BARREL,PITCH,'slide',MUZZLE,(0,1,0),None,(0,.01))]
    f.GROUPS=()
    f.ANIMATIONS={name:(False,'CONSTANT',{YAW:[(1,0),(31,0)],PITCH:[(1,angle),(31,angle)],BARREL:[(1,0),(31,0)]})
                  for name,angle in (('armed',15),('unarmed',60))}
    f.ANIMATIONS['aim']=(False,'LINEAR',{YAW:[(1,0),(61,0)],PITCH:[(1,0),(61,60)],BARREL:[(1,0),(61,0)]})
    joints=f.resolve_joints();pistons=resolve_actuator(joints);rig=f.build_rig(joints,pistons);k=f.Kit()
    bpy.context.scene.render.fps=30
    actions=f.build_actions(rig,joints,pistons)
    foundation(k);cradle(k);gun(k);actuator(k,pistons[0])
    if '--concept' in sys.argv:
        body=k.to_object('SK_'+TITLE,joints=f.rotary_joints(joints));f.skin(body,rig)
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
        print(f'CONCEPT ONLY: {f.triangles(body)} triangles; NOT validated',flush=True)
        return
    (HERE/'pulse_gun_collision_source_report.json').write_text(json.dumps([dict(bone=p.bone,label=str(p.line),vertices=[list(v) for v in p.verts],faces=p.faces) for p in k.parts]))
    manufacturing=check_manufacturing(k)
    pairs=common.exact_intersections(k);f.check_connectivity(k,joints,pistons)
    f.check_piston_clearance(pistons,joints,k.solids,k.parts)
    states=[(f'yaw {a} elevation {e} recoil {r}',{YAW:a,PITCH:e,BARREL:r})
        for a in range(-180,181,15) for e in range(0,61,5) for r in (0,.01)]
    states+=f.action_states(actions,joints)
    f.check_motion(k,joints,states)
    for tag,st in states:
        mats=f.fk(joints,st)
        for part in k.parts:
            for v in part.verts:
                if part.bone not in mats:continue
                q=mats[part.bone]@v
                assert abs(q.x)<=.50001 and abs(q.y)<=.50001 and q.z>=-1e-6,(tag,tuple(q))
    body=k.to_object('SK_'+TITLE,joints=f.rotary_joints(joints));f.skin(body,rig)
    if '--no-cull' not in sys.argv and '--draft' not in sys.argv:f.cull_unseen(body,rig,joints,pistons,states,(-.0001,-.0001),(.0001,.0001))
    coplanar_pairs=check_coplanar(body);tris=f.triangles(body)
    if '--no-cull' not in sys.argv and '--draft' not in sys.argv:assert tris<=BUDGET,tris
    gizmos=[marker(rig,'GroundMount',ROOT,(0,0,0)),marker(rig,'Muzzle',BARREL,MUZZLE),
            marker(rig,'AimOrigin',PITCH,tuple(PIVOT)),marker(rig,'DisplayMount',PITCH,(.084,.165,AXIS_Z))]
    poses={'armed':{PITCH:{'rot':[15,0,0]}},'unarmed':{PITCH:{'rot':[60,0,0]}},
        'elevation_30':{PITCH:{'rot':[30,0,0]}},
        'reverse':{YAW:{'rot':[180,0,0]},PITCH:{'rot':[60,0,0]}},'recoil':{BARREL:{'loc':[0,.01,0]}}}
    rig['preview_poses']=json.dumps(poses)
    rig['preview_pose_views']=json.dumps({'armed':['front_left','left'],'unarmed':['front_left','left'],'recoil':['left']})
    bpy.context.scene['preview_actions']=json.dumps(['armed','unarmed'])
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    if '--draft' in sys.argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
        print(f'[{NAME}] DRAFT {tris} triangles; {len(k.parts)} manufactured parts',flush=True)
        return
    sys.path.insert(0,str(HERE.parents[1]))
    from gameplay.dimensions import assert_authored_bounds
    assert_authored_bounds(HERE.name,[body])
    f.HERE=HERE;f.export([rig,body,*gizmos],NAME)
    report=dict(name=NAME,triangles=tris,triangle_budget=BUDGET,bounds_m=dict(lo=lo,hi=hi),
        materials=list(f.MATERIALS),animations=[dict(name=name,duration_s=1,loop=False,elevation_deg=angle)
                      for name,angle in (('armed',15),('unarmed',60))]+[dict(name='aim',duration_s=2,loop=False,elevation_deg=[0,60])],parts=common.LABELS,
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        pistons=[dict(name=p.name,cylinder=p.cylinder,rod=p.rod,parent_a=p.cyl_parent,parent_b=p.rod_parent,
                      a=list(p.a),b=list(p.b),stroke_m=p.stroke,cylinder_length_m=p.cyl_len,rod_length_m=p.rod_len,minimum_overlap_m=p.overlap) for p in pistons],
        bones=[dict(name=b.name,parent=b.parent.name if b.parent else None,
                    head=list(b.head_local),tail=list(b.tail_local),euler_order='XYZ') for b in rig.data.bones],
        gizmos=[dict(name=g.name,bone=g.parent_bone,origin=list(g.matrix_basis.translation),
                     forward=list(g.matrix_basis.to_3x3()@Vector((0,1,0))),
                     up=list(g.matrix_basis.to_3x3()@Vector((0,0,1))),
                     godot='local -Z forward, local +Y up') for g in gizmos],
        manufacturing_checks=manufacturing,
        checks=dict(solid_pairs=pairs,coplanar_pairs=coplanar_pairs,connected_parts=len(k.parts),motion_states=len(states),footprint_m=[1,1],no_solid_intersections=True),
        placement='ground-centred origin; front -Y; full yaw; elevation 0..60 degrees; library only')
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    f.constrain(rig,joints,pistons,drive=False)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles; {len(k.parts)} parts; {len(states)} sweep states',flush=True)

if __name__=='__main__':main()


















