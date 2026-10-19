"""Machined jump-access habitat; Blender 5.2, metres, front -Y. Library only."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import sys,json,math,importlib.util
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'environments'))
import light_common as common
sys.path.insert(0,str(HERE.parent))
import container.model as cargo
import weather_sensor.model as weather
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
ROOT='Root'
PRI,SEC,FRM,JNT,EMI=common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
GLASS='M_Glass'
NAME,TITLE='habitat_pod','HabitatPod'
TRI_BUDGET=7500  # User-approved detail budget; habitat pod remains library-only.
block,rod,loft=common.block,common.rod,common.loft
emit,mach,seat,xf=cargo.emit,cargo.mach,cargo.seat,cargo.transform
PX,PY=-.68,-1.84
LANDING_X,LANDING_Y,LANDING_Z=.88,.70,.25
LANDING_FLANGE_HALF=(.11,.145)
BODY_RISE=.20
LANDING_FOOT_X=1.70

def section(w,low,high,c,y):
    return [(x,y,z) for x,z in [(-w/2+c,low),(w/2-c,low),(w/2,low+c),
        (w/2,high-c),(w/2-c,high),(-w/2+c,high),(-w/2,high-c),(-w/2,low+c)]]

def passage(w,low,high,c,y0,y1):
    return kit.loft_rings([section(w,low,high,c,y) for y in (y0,y1)])

def bolt(k,p,n,label,bone=ROOT,r=.014):
    p,n=Vector(p),Vector(n)
    emit(k,rod(p,p+n*.009,r,6),JNT,label,bone)

def shell(k):
    body=kit.loft_rings([section(w,l,h,c,y) for y,w,l,h,c in
        [(-1.70,2.90,.40,3.05,.65),(-1.38,3.34,.38,3.25,.75),
         (-.95,3.50,.38,3.32,.75),(.95,3.50,.38,3.32,.75),
         (1.38,3.34,.38,3.25,.75),(1.65,2.90,.40,3.05,.65)]])
    # A continuous pressure shell, with solid floor and a genuine cabin cavity.
    cavity=passage(3.16,.55,2.96,.54,-1.48,1.46)
    body=common.trim_seats(body,[])
    body=mach(body,subtract=[(section(1.20,.55,2.66,.13,-1.75),(0,1,0),.65)])
    body=cargo.common.trim_seats(body,[part(cavity)])
    # Flat side-window seats: the openings cut entirely through the wall.
    for s in (-1,1):
        m=common.frame((s*1.75,0,2.13),(s,0,0),(0,0,1))
        cutter=xf(loft([(1.14,.50,.06,-.24),(1.14,.50,.06,.07)]),m)
        body=common.trim_seats(body,[part(cutter)])
    # Shallow machined expansion joints follow the actual lofted perimeter.
    for y in (-.90,.90):
        rows=[section(4,-.2,3.8,.75,y+d) for d in (-.009,.009)]
        rows += [section(3.488,.386,3.314,.744,y+d) for d in (.009,-.009)]
        cutter=bmesh.new();vs=[[cutter.verts.new(p) for p in row] for row in rows]
        for a,b in zip(vs,vs[1:]+vs[:1]):
            for i in range(8):cutter.faces.new((a[i],a[(i+1)%8],b[(i+1)%8],b[i]))
        bmesh.ops.recalc_face_normals(cutter,faces=cutter.faces[:])
        body=common.trim_seats(body,[part(cutter)])
    for s in (-1,1):
        body=mach(body,boxes=[cargo.boxcut((min(s*1.72,s*1.79),-.40,1.23),(max(s*1.72,s*1.79),.40,1.59))])
    body=mach(body,boxes=[cargo.boxcut((-.46,-.64,3.29),(.46,.64,3.35))])
    emit(k,body,PRI,'lofted hollow pressure casting and integral floor')
    cap=loft([(.919,1.279,.045,3.2905),(.919,1.279,.045,3.32)])
    emit(k,cap,SEC,'flush crown service mounting plate')
    # Jamb seats directly on the flat front bulkhead, behind the outer chamfer.
    m=common.frame((0,-1.70,1.605),(0,-1,0),(0,0,1))
    jamb=xf(common.ring(1.47,2.35,.19,1.20,2.11,.13,0,.068),m)
    emit(k,jamb,SEC,'continuous machined entrance jamb')
    gasket=xf(common.ring(1.222,2.132,.14,1.204,2.114,.13,.068,.073),m)
    emit(k,gasket,FRM,'captured entrance seal')
    for x in (-.65,.65):
        for z in (.70,2.51):bolt(k,(x,-1.768,z),(0,-1,0),'jamb captive fastener')
    for s in (-1,1):
        m=common.frame((s*1.75,0,2.13),(s,0,0),(0,0,1))
        bezel=xf(common.ring(1.14,.50,.06,1.04,.40,.04,-.025,.012),m)
        emit(k,bezel,SEC,'window rebated bolted bezel')
        seal=xf(common.ring(1.04,.40,.04,1.02,.38,.032,-.025,-.020),m)
        emit(k,seal,FRM,'window captured elastomer seal')
        glass=xf(loft([(1.02,.38,.032,-.020),(1.02,.38,.032,-.010)]),m)
        emit(k,glass,GLASS,'black glazing ten percent opacity')
        for y in (-.53,.53):bolt(k,(s*1.762,y,2.13),(s,0,0),'window bezel fastener')
        m=common.frame((s*1.72,0,1.41),(s,0,0),(0,0,1))
        panel=xf(loft([(.799,.359,.025,.0005),(.799,.359,.025,.025),(.789,.349,.021,.030)]),m)
        emit(k,panel,SEC,'flush seated removable side service panel')

def part(bm):
    from types import SimpleNamespace
    bm.verts.index_update()
    p=SimpleNamespace(verts=[v.co.copy() for v in bm.verts],faces=[[v.index for v in f.verts] for f in bm.faces])
    bm.free();return p

def door(k):
    m=common.frame((0,-1.77,1.605),(0,-1,0),(0,0,1))
    leaf=xf(loft([(1.188,2.098,.125,-.065),(1.188,2.098,.125,-.008),
                  (1.144,2.054,.105,.025)]),m)
    # Recessed face field and central lock seat are cut, not overlays.
    field_frame=common.frame((0,-1.780,1.61),(0,-1,0),(0,0,1))
    field_cut=xf(loft([(.88,1.56,.0625,0),(.88,1.56,.0625,.060)]),field_frame)
    leaf=common.trim_seats(leaf,[part(field_cut)])
    emit(k,leaf,PRI,'formed pressure door with recessed face','Door')
    panel=xf(loft([(.87,1.55,.060,0),(.87,1.55,.060,.002)]),
             field_frame)
    ribs=[block((-.33,-1.800,z-.018),(.33,-1.780,z+.018)) for z in (.96,2.26)]
    emit(k,mach(panel,union=ribs),SEC,'seated door reinforcement with integral pressed ribs','Door')
    for x in (-.385,.385):
        for z in (.91,2.31):bolt(k,(x,-1.782,z),(0,-1,0),'door reinforcement captive fastener','Door',.010)
    # One welded pull casting: square mounting feet, two arms and a return bar.
    grip=block((.20,-1.91,1.27),(.25,-1.895,1.66))
    grip=mach(grip,union=[block((.20,-1.895,z-.025),(.25,-1.779,z+.025)) for z in (1.295,1.635)])
    seat(k,grip,JNT,'door pull with two integral flush mounting feet','Door')
    for z in (.82,2.39):
        # Stationary fork lands on the jamb's unchamfered vertical strip.
        for a,b in ((z-.084,z-.038),(z+.038,z+.084)):
            sleeve=mach(rod((PX,PY,a),(PX,PY,b),.038,6),
                union=[block((PX-.025,PY,a),(-.605,-1.735,b))],
                cuts=[((PX,PY,a-.01),(PX,PY,b+.01),.0163,6)])
            seat(k,sleeve,SEC,'stationary hinge fork with flat jamb seat')
        moving=mach(rod((PX,PY,z-.037),(PX,PY,z+.037),.036,6),
            union=[block((PX,PY,z-.037),(-.53,-1.774,z+.037))],
            cuts=[((PX,PY,z-.05),(PX,PY,z+.05),.0163,6)])
        seat(k,moving,SEC,'door hinge tongue and bored knuckle','Door')
        emit(k,rod((PX,PY,z-.084),(PX,PY,z+.084),.014,6),JNT,'retained hinge pin')
        for zz in (z-.089,z+.084):
            emit(k,rod((PX,PY,zz),(PX,PY,zz+.005),.021,6),JNT,'hinge flush retaining cap')
    # Vertical captive shoot bolt withdraws from the header before rotation.
    x,y=.46,-1.829
    housing=mach(rod((x,y,2.03),(x,y,2.34),.033,6),
        union=[block((x-.04,y,2.06),(x+.04,-1.765,2.31))],
        cuts=[((x,y,2.00),(x,y,2.40),.0122,6)])
    seat(k,housing,FRM,'lock actuator barrel with fitted mounting saddle','Door')
    emit(k,rod((x,y,2.16),(x,y,2.735),.012,6),JNT,'captive stainless header bolt','Lock')
    socket=mach(rod((x,y,2.67),(x,y,2.75),.025,6),
        union=[block((x-.032,y,2.67),(x+.032,-1.70,2.75))],
        cuts=[((x,y,2.66),(x,y,2.76),.0122,6)])
    seat(k,socket,SEC,'header lock receiver with bored support')
    # Status insert occupies an exact pocket on the jamb, never cabin lighting.
    seat(k,block((.638,-1.785,1.56),(.684,-1.768,1.65)),FRM,'external lock reader housing')
    emit(k,block((.645,-1.789,1.575),(.677,-1.785,1.635)),EMI,'external access status lens')

def landing(k):
    for s in (-1,1):
        for y in (-LANDING_Y,LANDING_Y):
            a=Vector((s*LANDING_X,y,LANDING_Z+BODY_RISE));b=Vector((s*LANDING_FOOT_X,y,.085))
            # Entire flange footprint is on the central planar belly, strictly
            # inside both the transverse and longitudinal chamfer boundaries.
            hx,hy=LANDING_FLANGE_HALF
            assert abs(a.x)+hx<1.0 and abs(y)+hy<.90
            emit(k,block((a.x-hx,y-hy,.36+BODY_RISE),(a.x+hx,y+hy,.38+BODY_RISE)),SEC,
                 'landing flange fully seated on planar belly')
            for dx in (-.084,.084):
                for dy in (-.116,.116):
                    bolt(k,(a.x+dx,y+dy,.36+BODY_RISE),(0,0,-1),'landing flange captive hex fastener')
            # Bored beam eyes captured between U-shaped casting cheeks.
            beam=weather.link(a,b,.08,.055,.096)
            d=(b-a).normalized();n=Vector((-d.z,0,d.x))
            p0,p1=a+d*.27,b-d*.20
            # A through-milled lightening bay leaves two continuous load rails
            # between the broad end eyes, with clipped pocket ends.
            poly=[p0+n*.011,p0+d*.02+n*.023,p1-d*.02+n*.023,p1+n*.011,
                  p1-n*.011,p1-d*.02-n*.023,p0+d*.02-n*.023,p0-n*.011]
            beam=mach(beam,subtract=[([tuple(p) for p in poly],(0,1,0),.12)])
            beam=weather.bored(weather.bored(beam,a,.0252,y-.09,y+.09),b,.0192,y-.09,y+.09)
            lock=a+Vector((s*.055,0,-.015))
            beam=weather.bored(beam,lock,.0082,y-.09,y+.09)
            emit(k,beam,SEC,'machined landing strut with integral bored eyes')
            for p,r,width in ((a,.025,.080),(b,.019,.070)):
                emit(k,rod((p.x,y-width,p.z),(p.x,y+width,p.z),r,6),JNT,'landing cross pin')
                for sign in (-1,1):
                    emit(k,rod((p.x,y+sign*width,p.z),(p.x,y+sign*(width+.006),p.z),r*1.4,6),JNT,'landing pin retaining cap')
            foot=xf(loft([(.38,.30,.04,0),(.38,.30,.04,.025)]),Matrix.Translation((b.x,y,0)))
            cheeks=[]
            for cy in (y-.060,y+.060):
                cheeks.append(block((b.x-.065,cy-.010,.025),(b.x+.065,cy+.010,.125)))
            foot=mach(foot,union=cheeks,cuts=[((b.x,y-.09,b.z),(b.x,y+.09,b.z),.0192,6)])
            emit(k,foot,SEC,'ground bearing pad with integral bored clevis')
            # Fork web ends on the flange's lower plane; its entire contact
            # patch is contained by the flange, with 20 mm eye clearance.
            lug=mach(block((a.x-.09,y-.082,.35+BODY_RISE),(a.x+.09,y+.082,.36+BODY_RISE)),
                union=[block((a.x-.09,cy-.014,.15+BODY_RISE),(a.x+.09,cy+.014,.35+BODY_RISE)) for cy in (y-.063,y+.063)],
                cuts=[((a.x,y-.10,a.z),(a.x,y+.10,a.z),.0252,6)])
            lug=weather.bored(lug,lock,.0082,y-.10,y+.10)
            emit(k,lug,SEC,'body landing hardpoint bored clevis')
            emit(k,rod((lock.x,y-.080,lock.z),(lock.x,y+.080,lock.z),.008,6),JNT,'off-axis positive landing lock pin')
            for sign in (-1,1):
                emit(k,rod((lock.x,y+sign*.080,lock.z),(lock.x,y+sign*.086,lock.z),.012,6),JNT,'landing lock pin retaining cap')
            if y<0:landing_hydraulic(k,a,b,d)

def landing_hydraulic(k,a,b,d):
    # Outboard hydraulic brace: two bored forks, cylinder eye and rod eye.
    # Positive lock pins above carry the parked load; hydraulics are stationary.
    A=a+Vector((.03 if a.x>0 else -.03,.12,.035))
    B=a+d*.74+Vector((0,.12,0));axis=(B-A).normalized()
    for p,upper in ((A,True),(B,False)):
        if upper:
            web=block((p.x-.046,p.y-.029,.35+BODY_RISE),(p.x+.046,p.y+.025,.36+BODY_RISE))
        else:
            web=block((p.x-.045,a.y+.047,p.z-.058),(p.x+.045,p.y+.025,p.z-.040))
        cheeks=[block((p.x-.045,p.y+cy-.007,p.z-.040),
                      (p.x+.045,p.y+cy+.007,.35+BODY_RISE if upper else p.z+.040)) for cy in (-.019,.019)]
        fork=mach(web,union=cheeks,cuts=[((p.x,p.y-.06,p.z),(p.x,p.y+.06,p.z),.0122,6)])
        seat(k,fork,SEC,'hydraulic brace supported bored fork')
        emit(k,rod((p.x,p.y-.026,p.z),(p.x,p.y+.026,p.z),.012,6),JNT,'hydraulic brace cross pin')
        for sign in (-1,1):
            emit(k,rod((p.x,p.y+sign*.026,p.z),(p.x,p.y+sign*.030,p.z),.017,6),JNT,'hydraulic pin retaining cap')
    def eye(p,neck0,neck1,radius):
        length=(neck1-neck0).length
        neck=xf(loft([(.030,.020,.002,0),(.030,.020,.002,length)]),
                common.frame(neck0,(neck1-neck0).normalized(),(0,1,0)))
        bm=mach(rod(p-Vector((0,.010,0)),p+Vector((0,.010,0)),.035,6),
            union=[neck],
            cuts=[(p-Vector((0,.05,0)),p+Vector((0,.05,0)),.0122,6)])
        return bm
    casing=mach(rod(A+axis*.065,A+axis*.42,.038,6),
        union=[eye(A,A,A+axis*.08,.022)])
    emit(k,casing,SEC,'hydraulic cylinder barrel with integral bored eye')
    emit(k,rod(A+axis*.42,A+axis*.45,.043,8),JNT,'hydraulic rod gland and wiper collar')
    rodend=mach(rod(A+axis*.45,B-axis*.065,.015,8),
        union=[eye(B,B-axis*.08,B,.022)])
    emit(k,rodend,JNT,'exposed stainless piston rod with bored end eye')
    C=A+axis*.19
    seat(k,rod(C+Vector((0,.030,0)),C+Vector((0,.060,0)),.013,6),
         JNT,'hydraulic barrel charge-port coupling')
    G=Vector((a.x-.040 if a.x>0 else a.x+.040,a.y+.120,.36+BODY_RISE))
    emit(k,rod(G,G-Vector((0,0,.045)),.014,6),JNT,'hydraulic belly bulkhead union')
    route=[G-Vector((0,0,.045)),G-Vector((0,0,.080)),G+Vector((0,.10,-.080)),
           Vector((C.x,G.y+.10,C.z)),C+Vector((0,.060,0))]
    emit(k,sweep_tube(rounded_route(route,.012),.008),FRM,'hydraulic charge hose between supported couplings')

def sweep_tube(points,r,segments=6):
    """Closed constant-section hose, with transported section frames."""
    pts=list(map(Vector,points));rings=[];u=None
    for i,p in enumerate(pts):
        axis=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        if u is None or (u-axis*u.dot(axis)).length<1e-5:
            ref=min((Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))),key=lambda a:abs(a.dot(axis)))
            u=axis.cross(ref).normalized()
        else:u=(u-axis*u.dot(axis)).normalized()
        v=axis.cross(u)
        rings.append([p+r*(u*math.cos(j*math.tau/segments)+v*math.sin(j*math.tau/segments)) for j in range(segments)])
    return kit.loft_rings(rings)

def rounded_route(points,radius=.035):
    """Fillet each route corner; straights end tangent to the bend."""
    pts=list(map(Vector,points));out=[pts[0]]
    for a,b,c in zip(pts,pts[1:],pts[2:]):
        incoming=(b-a).normalized();outgoing=(c-b).normalized()
        angle=incoming.angle(outgoing)
        if angle<.01:out.append(b);continue
        trim=min(radius*math.tan(angle/2),(b-a).length*.4,(c-b).length*.4)
        rr=trim/math.tan(angle/2)
        start=b-incoming*trim;end=b+outgoing*trim
        normal=incoming.cross(outgoing).normalized()
        center=start+normal.cross(incoming)*rr
        radial=start-center
        for i in range(3):out.append(center+Matrix.Rotation(angle*i/2,3,normal)@radial)
        assert (out[-1]-end).length<1e-5
    out.append(pts[-1]);return out

def cassette(k,m,w,h,depth,label):
    """One flanged casting, removable bezel and monolithic ribbed collector."""
    iw,ih=w-.28,h-.24
    body=loft([(w,h,.030,0),(w,h,.030,.018),
        (w-.10,h-.10,.035,.018),(w-.10,h-.10,.035,depth-.030),
        (w-.12,h-.12,.025,depth-.012)])
    cutter=loft([(iw,ih,.015,.055),(iw,ih,.015,depth+.02)])
    body=common.trim_seats(body,[part(cutter)])
    emit(k,xf(body,m),SEC,label+' flanged recessed casting')
    emit(k,xf(common.ring(w-.12,h-.12,.025,iw,ih,.015,depth-.012,depth),m),PRI,label+' removable machined bezel')
    collector=loft([(iw-.001,ih-.001,.014,.055),(iw-.001,ih-.001,.014,.061)])
    fins=[]
    for i in range(7):
        u=-(iw-.08)/2+i*(iw-.08)/6
        fins.append(block((u-.010,-ih/2+.018,.061),(u+.010,ih/2-.018,depth-.022)))
    emit(k,xf(mach(collector,union=fins),m),JNT,label+' integral finned metal collector')
    n=m.to_3x3()@Vector((0,0,1))
    for u in (-w/2+.035,w/2-.035):
        for v in (-h/2+.035,h/2-.035):
            bolt(k,m@Vector((u,v,.018)),n,label+' flange fastener',r=.009)

def service_details(k):
    cassette(k,Matrix.Translation((0,0,3.32)),.84,1.14,.15,'crown air-treatment unit')
    for s in (-1,1):
        m=common.frame((s*1.75,0,1.41),(s,0,0),(0,0,1))
        cassette(k,m,1.04,.52,.16,'side thermal processor')
        for y in (-.67,.67):
            for z in (1.30,1.78):
                emit(k,rod((s*1.75,y,z),(s*1.79,y,z),.036,6),SEC,'coolant bulkhead connector flange')
                emit(k,rod((s*1.79,y,z),(s*1.83,y,z),.030,6),JNT,'coolant union hex coupling')
            pts=[(s*1.83,y,1.30),(s*1.94,y,1.30),(s*1.94,y,1.78),(s*1.83,y,1.78)]
            emit(k,sweep_tube(rounded_route(pts),.022),JNT,'formed coolant line with tangent-radius elbows')
            lo=(min(s*1.75,s*1.98),y-.045,1.515);hi=(max(s*1.75,s*1.98),y+.045,1.565)
            saddle=mach(block(lo,hi),cuts=[((s*1.94,y,1.50),(s*1.94,y,1.58),.0257,6)])
            emit(k,saddle,SEC,'coolant line bored standoff clamp')
            for dy in (-.036,.036):
                bolt(k,(s*1.98,y+dy,1.54),(s,0,0),'coolant clamp retaining fastener',r=.006)
        # Electrical service loop sits behind the coolant lines, on separate
        # side-facing and bulkhead glands; no cable spans the door hinge.
        emit(k,rod((s*1.80,.47,1.49),(s*1.80,.53,1.49),.024,6),FRM,'processor side cable strain relief')
        emit(k,rod((s*1.75,.77,1.78),(s*1.81,.77,1.78),.025,6),FRM,'sealed bulkhead power connector')
        pts=[(s*1.80,.53,1.49),(s*1.80,.77,1.49),(s*1.80,.77,1.70),
             (s*1.90,.77,1.78),(s*1.81,.77,1.78)]
        emit(k,sweep_tube(rounded_route(pts,.025),.013),FRM,'protected electrical service loop')

def services(k):
    # Rear-mounted heat exchanger: a flanged housing with genuine fin slots.
    m=common.frame((0,1.65,1.91),(0,1,0),(0,0,1))
    housing=xf(loft([(1.10,.91,.06,0),(1.10,.91,.06,.055),(.99,.80,.04,.10)]),m)
    cuts=[cargo.boxcut((x-.023,1.68,1.60),(x+.023,1.80,2.22)) for x in (-.36,-.24,-.12,0,.12,.24,.36)]
    emit(k,mach(housing,boxes=cuts),SEC,'rear thermal service cassette with machined cooling slots')
    for x in (-.43,.43):
        for z in (1.60,2.22):bolt(k,(x,1.75,z),(0,1,0),'service cassette flange fastener')
    # Stainless coolant pipes between true connector faces, with supported elbows.
    for x in (-.64,.64):
        for z in (1.54,2.28):
            seat(k,rod((x,1.63,z),(x,1.73,z),.044,6),SEC,'coolant bulkhead gland')
        points=[(x,1.73,1.54),(x,1.83,1.54),(x,1.83,2.28),(x,1.73,2.28)]
        pieces=[rod(a,b,.018,6) for a,b in zip(points,points[1:])]
        pipe=mach(pieces[0],union=pieces[1:])
        emit(k,pipe,JNT,'continuous welded return pipe between gland faces')

def export_runtime(rig,meshes,markers):
    for pb in rig.pose.bones:
        for c in list(pb.constraints):pb.constraints.remove(c)
    common.prepare_export([rig,*meshes,*markers],HERE,NAME)
    kit.select_only([rig,*meshes,*markers])
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_materials='EXPORT')

def cull_with_transparent_windows(body,rig,joints,states):
    # Glass must not occlude rays from cabin faces. Separate it for the generic
    # visibility pass, retain its closed thickness, then rejoin the rigid mesh.
    kit.select_only([body]);bpy.context.view_layer.objects.active=body
    for p in body.data.polygons:
        p.select=body.data.materials[p.material_index].name==GLASS
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    glazing=next(o for o in bpy.context.selected_objects if o!=body and o.type=='MESH')
    kit.cull_unseen(body,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
    kit.select_only([body,glazing]);bpy.context.view_layer.objects.active=body
    bpy.ops.object.join()
    body.data.set_sharp_from_angle(angle=kit.SHARP_ANGLE)

def main():
    global HERE
    if '--output' in sys.argv:
        HERE=Path(sys.argv[sys.argv.index('--output')+1]);HERE.mkdir(parents=True,exist_ok=True)
    if '--collision-exports-only' in sys.argv:
        bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}_col.blend'))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_') and 'Col' in o.name]
        cargo.HERE=HERE;cargo.export_runtime(rig,meshes,NAME+'_col');return
    if '--exports-only' in sys.argv:
        bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        export_runtime(rig,[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')],
            [o for o in bpy.context.scene.objects if o.type=='EMPTY'])
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'));return
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5)
    kit.MATERIALS[GLASS]=((0,0,0),0,.18,0)
    kit.SLOTS=list(kit.MATERIALS);kit.GROUPS=()
    kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS];bs=glass.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Alpha'].default_value=.10;glass.diffuse_color=(0,0,0,.10)
    glass.surface_render_method='DITHERED'
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('Door',ROOT,'hinge',(PX,PY,1.605+BODY_RISE),(0,0,1),(0,-1,0),(-105,0)),
        ('Lock','Door','slide',(.46,-1.829,2.16+BODY_RISE),(0,0,1),(0,0,1),(-.10,0))]
    keys={'Door':[(0,0),(21,0),(81,-105),(96,-105)],'Lock':[(0,0),(15,-.10),(96,-.10)]}
    kit.ANIMATIONS={'open':(False,'BEZIER',keys),'close':(False,'BEZIER',{b:[(96-f,v) for f,v in reversed(ks)] for b,ks in keys.items()})}
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    shell(k);door(k);services(k);service_details(k)
    # Raise the complete rigid cabin; rebuild the gear against its new hardpoints.
    lift=Matrix.Translation((0,0,BODY_RISE))
    for vertex in k.bm.verts:vertex.co=lift@vertex.co
    k.parts=[p.moved(lift) for p in k.parts]
    landing(k)
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    states += [(f'sweep {a}',{'Door':-a,'Lock':-.10*dimensions.HEIGHT[NAME]}) for a in range(106)]

    kit.check_motion(k,joints,states)
    source=[dict(label=label,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces) for p,label in zip(k.parts,common.LABELS)]
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps(source))
    body=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(body,rig)
    if '--no-cull' not in sys.argv:
        cull_with_transparent_windows(body,rig,joints,states)
    kit.check_coplanar(body);tris=kit.triangles(body)
    if '--no-cull' not in sys.argv:assert tris<=TRI_BUDGET,tris
    markers=[];gizmos=[]
    for name,at in [('PlayerMount',(0,0,.55+BODY_RISE))]:
        ob=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(ob)
        ob.parent=rig;ob.parent_type='BONE';ob.parent_bone=ROOT
        at=dimensions.point(NAME,at)
        ob.matrix_world=Matrix.Translation(at);markers.append(ob);gizmos.append(dict(name=name,bone=ROOT,position_m=list(at)))
    import light_mounts
    fixtures,fixture_info=light_mounts.install_default(rig,[body],NAME)
    markers.extend(fixtures);gizmos.extend(fixture_info)
    export_runtime(rig,[body],markers)
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    report=dict(name=NAME,triangles=tris,triangle_budget=TRI_BUDGET,meshes={body.name:tris},materials=sorted({body.data.materials[p.material_index].name for p in body.data.polygons}),bounds_m=dict(lo=lo,hi=hi),
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        joints=[dict(bone=j.name,type=j.kind,parent=j.parent,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        gizmos=gizmos,tensor_height_m=1.753,deck_height_m=.55+BODY_RISE,clear_door_m=[1.20,2.11],
        checks=dict(connected_parts=len(k.parts),exact_solid_pairs=pairs,motion_states=len(states)),placement='front -Y, up Z, ground origin; library only')
    dimensions.report(NAME,report,width=1.20,height=2.11,floors=[.55+BODY_RISE],ceilings=[2.96+BODY_RISE])
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    rig['preview_poses']=json.dumps({'open':{'Door':{'rot':[-105,0,0]},'Lock':{'loc':[0,-.10,0]}},'unlocked':{'Lock':{'loc':[0,-.10,0]}}})
    bpy.context.scene['preview_actions']=json.dumps(['open','close'])
    bpy.context.scene['showcase_frame']=json.dumps(dict(lo=[-2.1,-3.1,0],hi=[2.1,1.9,3.52]))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles',flush=True)

if __name__=='__main__':main()
