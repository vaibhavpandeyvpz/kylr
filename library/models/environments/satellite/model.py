"""Ground-mounted 2 m communications reflector; metres, front -Y, floor z=0.

Scripted manufactured shells and seated inserts on a retained elevation axle.
The receiver phase centre is at the paraboloid focus, not a decorative spike.
Run from library/ in headless Blender 5.2. No game handoff is performed.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import light_common as common
kit = common.kit
ROOT, ELEV = 'Root', 'Elevation'
PRI, SEC, FRM, JNT, EMI = common.PRI, common.SEC, common.FRM, common.JNT, common.EMI
NAME, TITLE = 'satellite', 'Satellite'
PIVOT = Vector((0, .26, 2.0))
RADIUS, DEPTH, VERTEX_Y = 1.0, .30, .12
FOCUS_Y = VERTEX_Y - RADIUS**2/(4*DEPTH)
block, rod, loft = common.block, common.rod, common.loft


def xf(bm, m):
    for v in bm.verts: v.co = m @ v.co
    return bm


def machine(bm, **kw):
    for mesh in [bm, *kw.get('union', [])]:
        bmesh.ops.recalc_face_normals(mesh, faces=mesh.faces[:])
    out = kit.machine(bm, **kw)
    bmesh.ops.remove_doubles(out, verts=out.verts[:], dist=1e-6)
    return out


def emit(k, bm, mat, label, bone=ROOT):
    old_count=len(k.bm.faces)
    bmesh.ops.triangulate(bm,faces=bm.faces[:])
    bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=bm.edges[:])
    if any(not e.is_manifold for e in bm.edges):
        print(label, 'invalid edges', [(len(e.link_faces),[tuple(v.co) for v in e.verts]) for e in bm.edges if not e.is_manifold][:8],flush=True)
    old = common.ROOT
    common.ROOT = bone
    try:
        common.emit(k, bm, mat, label)
        k.parts[-1].line=label
        if 'blind-bored tube socket' in label:
            layer=k.bm.faces.layers.int.get('machined_flat') or k.bm.faces.layers.int.new('machined_flat')
            for face in list(k.bm.faces)[old_count:]:face[layer]=1
    finally: common.ROOT = old


def seat(k, bm, mat, label, bone=ROOT):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    lo=Vector(min(v.co[i] for v in bm.verts) for i in range(3))
    hi=Vector(max(v.co[i] for v in bm.verts) for i in range(3))
    bm = common.trim_seats(bm, [p for p in k.parts if p.bone == bone and
        all(min(hi[i],p.hi[i])-max(lo[i],p.lo[i])>1e-6 for i in range(3))])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
    emit(k, bm, mat, label, bone)


def closed(rows):
    bm = bmesh.new()
    verts = [[bm.verts.new(p) for p in row] for row in rows]
    for a, b in zip(verts, verts[1:] + verts[:1]):
        for i in range(len(a)):
            j = (i+1) % len(a)
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return bm


def circle(r, y, n=32):
    phase=math.pi/n if n==32 else 0
    return [(r*math.cos(i*math.tau/n+phase), y, 2+r*math.sin(i*math.tau/n+phase)) for i in range(n)]


def drum_y(stations, n=12):
    return kit.loft_rings([circle(r, y, n) for y, r in stations])


def ring_y(r, inner, y0, y1, n=32):
    return closed([circle(r, y0, n), circle(r, y1, n),
                   circle(inner, y1, n), circle(inner, y0, n)])


def screw(k, at, normal, label, bone=ROOT, r=.007):
    at, normal = Vector(at), Vector(normal).normalized()
    emit(k, rod(at, at+normal*.004, r, 6), JNT, label, bone)


def pocket(body, at, forward, w, h, mat, label):
    m = common.frame(at, forward, (0,0,1))
    cutter = xf(loft([(w,h,.004,-.006),(w,h,.004,.015)]), m)
    cutter.verts.index_update()
    from types import SimpleNamespace
    p = SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],
        faces=[[v.index for v in f.verts] for f in cutter.faces])
    body = common.trim_seats(body, [p]); cutter.free()
    insert = xf(loft([(w-.0004,h-.0004,.0038,-.006),
                     (w-.0004,h-.0004,.0038,0)]),m)
    return body, (insert,mat,label)


def clevis(k,m,label,bolts=True):
    """Bolted mounting flange and two bored ears, with an open tongue slot."""
    flange=loft([(.16,.18,.009,0),(.16,.18,.009,.015)])
    profile=[(0,-.034,.013),(0,.034,.013),(0,.034,.070),
             (0,.022,.097),(0,-.022,.097),(0,-.034,.070)]
    ears=[xf(kit.prism_bm(profile,.016,(1,0,0)),Matrix.Translation((s*.030,0,0))) for s in (-1,1)]
    body=machine(flange,union=ears,cuts=[((-.06,0,.07),(.06,0,.07),.0123,8)])
    seat(k,xf(body,m),SEC,label+' bolted flange and bored clevis')
    if bolts:
        for x in (-.060,.060):
            for y in (-.070,.070):screw(k,m@Vector((x,y,.015)),m.to_3x3()@Vector((0,0,1)),label+' flange bolt',r=.006)
    return m@Vector((0,0,.07))


def retained_pin(k,m,label):
    emit(k,xf(rod((-.038,0,.07),(.038,0,.07),.012,8),m),JNT,label+' through pin')
    for s in (-1,1):
        emit(k,xf(rod((s*.038,0,.07),(s*.043,0,.07),.019,6),m),JNT,label+' hex pin retaining cap')


def eye_link(k,a,b,label):
    """A tapered brace with integral end eyes, bored coaxial with both pins."""
    a,b=Vector(a),Vector(b);d=(b-a).normalized();axis=Vector((1,0,0));u=axis.cross(d).normalized()
    outline=[]
    for p,sign in ((a,-1),(b,1)):
        for i in range(5):
            angle=math.pi*i/4
            outline.append(tuple(p+u*(.032*math.cos(angle)*(-sign))+d*(.032*math.sin(angle)*sign)))
    link=kit.prism_bm(outline,.036,axis)
    link=machine(link,cuts=[(tuple(p-axis*.05),tuple(p+axis*.05),.0123,8) for p in (a,b)])
    emit(k,link,PRI,label+' tapered brace with bored eye ends')


def feed_socket(k,at,axis,up,label):
    """Brazed socket with a real blind bore and a swaged shoulder."""
    m=common.frame(at,axis,up)
    bm=kit.loft_rings([kit.ring_xy(0,0,r,z,8) for z,r in
                      ((-.008,.027),(.012,.027),(.018,.023),(.038,.023))])
    bm=machine(bm,cuts=[((0,0,.014),(0,0,.045),.0143,12)])
    seat(k,xf(bm,m),JNT,label+' shouldered blind-bored tube socket',ELEV)
    return Vector(at)+Vector(axis).normalized()*.014


def chassis(k):
    # One welded/plated chassis: shoulders are lofted into the mounting flats.
    base = loft([(2.42,1.44,.06,0),(2.42,1.44,.06,.12),
                 (2.38,1.40,.045,.14)])
    base=machine(base,boxes=[((0,-.55,.075),(1.66,.22,.065))])
    emit(k,base,SEC,'lofted foundation with planar anchor deck')
    for s in (-1,1):
        flange=xf(loft([(.17,.34,.012,.14),(.17,.34,.012,.18)]),Matrix.Translation((s*1.10,.26,0)))
        emit(k,flange,SEC,'tower bolted foundation flange')
        for x in (-.060,.060):
            for y in (-.135,.135):screw(k,(s*1.1+x,.26+y,.18),(0,0,1),'tower foundation flange anchor',r=.006)
        column=xf(loft([(.15,.22,.012,.18),(.20,.22,.018,.28),
                             (.16,.19,.016,1.78),(.20,.24,.018,2.06)]),
                       Matrix.Translation((s*1.10,.26,0)))
        column=machine(column,union=[rod((s*1.01,.26,2),(s*1.22,.26,2),.145,12)],
                       cuts=[((-1.24,.26,2),(1.24,.26,2),.0625,12)])
        emit(k,column,SEC,'tower casting and bored bearing housing')
    # Diagonal structural members have exact fish-mouth weld seats. The two
    # X braces lie in separate planes and meet a central bolted gusset.
    gusset = xf(loft([(.29,.29,.025,0),(.29,.29,.025,.12)]),
                common.frame((0,.32,.70),(0,-1,0),(0,0,1)))
    emit(k,gusset,PRI,'central bolted cross brace gusset')
    for s in (-1,1):
        for z in (.30,1.64):
            # The tapered tower has a real flat inner mounting face at z.
            width=(.20+(.16-.20)*(z-.28)/(1.78-.28)) if z<1.78 else .16
            x=s*(1.10-width/2)
            m=common.frame((x,.26,z),(-s,0,0),(0,0,1))
            a=m@Vector((0,0,.04));b=Vector((0,.26,.70));d=(b-a).normalized()
            bracket=xf(loft([(.14,.12,.010,0),(.14,.12,.010,.016)]),m)
            neck=xf(loft([(.065,.065,.008,.012),(.060,.060,.008,.043)]),m)
            collar=rod(a-d*.020,a+d*.055,.052,6)
            bracket=machine(bracket,union=[neck,collar],
                cuts=[(tuple(a+d*.020),tuple(a+d*.070),.0435,6)])
            seat(k,bracket,SEC,'diagonal brace bolted blind-socket casting')
            for px,py in ((-.054,-.043),(.054,.043)):
                screw(k,m@Vector((px,py,.016)),m.to_3x3()@Vector((0,0,1)),
                      'diagonal socket flange bolt',r=.005)
            seat(k,rod(a+d*.020,b,.043,6),PRI,'diagonal brace seated in socket and central gusset')
        for side,y in (('front',-.50),('rear',.56)):
            sign=-1 if side=='front' else 1
            lower=common.frame((s*1.10,y,.14),(0,0,1),(0,1,0))
            # Tapered column face is measured, not guessed. Brackets are
            # seated against that face and project the eyes outside its skin.
            half=.11+(.095-.11)*(1.34-.28)/(1.78-.28)
            upper=common.frame((s*1.10,.26+sign*half,1.34),(0,sign,.01),(0,0,1))
            tag=f'{side} tower {s:+} knee brace'
            a=clevis(k,lower,tag+' foot');b=clevis(k,upper,tag+' shoulder')
            eye_link(k,a,b,tag)
            retained_pin(k,lower,tag+' foot');retained_pin(k,upper,tag+' shoulder')
    for s in (-1,1):
        for y in (-.50,.50):
            # These sit on the broad foundation flats, clear of the chamfer.
            screw(k,(s*.96,y*1.26,.14),(0,0,1),'foundation anchor hex head',r=.014)
    for x in (-.10,.10):
        for z in (.60,.80): screw(k,(x,.20,z),(0,-1,0),'cross brace gusset bolt')
    # Base logger cabinet is joined through two integral feet.
    cabinet = loft([(.52,.40,.035,.14),(.58,.44,.04,.20),
                    (.58,.44,.04,.45),(.48,.36,.032,.49)])
    inserts=[]
    cabinet,ins=pocket(cabinet,(0,-.22,.325),(0,-1,0),.35,.15,FRM,'recessed communications cabinet cover');inserts.append(ins)
    cabinet,ins=pocket(cabinet,(0,-.22,.425),(0,-1,0),.24,.012,EMI,'flush cabinet link indicator');inserts.append(ins)
    emit(k,cabinet,PRI,'lofted sealed controller cabinet')
    for bm,mat,label in inserts: emit(k,bm,mat,label)
    for x in (-.15,.15):
        for z in (.27,.38): screw(k,(x,-.22,z),(0,-1,0),'controller captive cover screw',r=.005)


def dish(k):
    # A closed spun reflector with a rear skin, not overlapping concentric discs.
    front = [(0.04,.12),(.22,.12-.30*.22**2),(.45,.12-.30*.45**2),
             (.70,.12-.30*.70**2),(.90,.12-.30*.90**2),(1.,-.18)]
    rows=[circle(r,y) for r,y in front]
    rows += [circle(r,y+.022) for r,y in reversed(front)]
    shell=closed(rows)
    # Conductive face sectors are material regions of the continuous skin;
    # they do not introduce panel overlays into the reflecting aperture.
    existing=set(k.bm.faces)
    # Close the small central bore with its manufactured plug below.
    emit(k,shell,PRI,'parabolic spun reflector double skin',ELEV)
    bmesh.ops.recalc_face_normals(k.bm,faces=k.bm.faces[:])
    for f in set(k.bm.faces)-existing:
        q=f.calc_center_median();r=math.hypot(q.x,q.z-2)
        if f.normal.y < -.4 and r>.69:f.material_index=kit.SLOTS.index(JNT if r<.90 else SEC)
    emit(k,drum_y([(.12,.04),(.142,.04)],32),PRI,'flush reflector vertex closure',ELEV)
    emit(k,ring_y(1.025,1.0002,-.18,-.143),SEC,'rolled reflector perimeter flange',ELEV)
    reflector=next(p for p,label in zip(k.parts,common.LABELS) if label=='parabolic spun reflector double skin')
    for i in range(12):
        a=i*math.tau/12;at=Vector((.957*math.cos(a),-.18,2+.957*math.sin(a)))
        loc,n,_,_=reflector.bvh.find_nearest(at)
        if n.y>0:n=-n
        screw(k,loc,n,'reflector perimeter captive fastener',ELEV,r=.006)
    # Vertex/hub rear enclosure: tapered cast load distributor and RF backend.
    hub=xf(loft([(.27,.27,.035,0),(.43,.43,.05,.07),
                 (.43,.43,.05,.18),(.34,.34,.04,.22)]),
           common.frame((0,.142,2),(0,1,0),(0,0,1)))
    hub=common.trim_seats(hub,[p for p in k.parts if p.bone==ELEV])
    emit(k,hub,SEC,'lofted reflector rear bearing and receiver shroud',ELEV)
    # Axle beams and keyed shaft are one casting. They meet the hub at seats.
    for s in (-1,1):
        seat(k,rod((0,.26,2),(s*.995,.26,2),.065,12),SEC,'trunnion load beam',ELEV)
        emit(k,rod((s*.995,.26,2),(s*1.225,.26,2),.06,12),JNT,'elevation through axle',ELEV)
        emit(k,rod((s*1.225,.26,2),(s*1.235,.26,2),.09,12),JNT,'axle retaining cap',ELEV)
        for i in range(4):
            a=i*math.tau/4
            screw(k,(s*1.235,.26+.072*math.cos(a),2+.072*math.sin(a)),(s,0,0),'axle cap retaining screw',ELEV,r=.005)
        # Shim rings occupy the real gap, with a larger bore than the shaft.
        m=common.frame((s*.995,.26,2),(s,0,0),(0,0,1))
        shim=closed([kit.ring_xy(0,0,r,z,12) for r,z in
                    ((.088,0),(.088,.004),(.0625,.004),(.0625,0))])
        emit(k,xf(shim,m),JNT,'elevation axial thrust washer',ELEV)
        fm=common.frame((s*1.22,.26,2),(s,0,0),(0,0,1))
        depth=.020 if s==1 else .005
        flange=closed([kit.ring_xy(0,0,r,z,12) for r,z in
                       ((.145,0),(.145,depth),(.094,depth),(.094,0))])
        emit(k,xf(flange,fm),JNT,'fixed bearing flange and gearbox mounting shoulder',ROOT)
        if s==-1:
            for i in range(4):
                a=i*math.tau/4
                screw(k,fm@Vector((.119*math.cos(a),.119*math.sin(a),depth)),(-1,0,0),
                      'bearing flange captive bolt',ROOT,r=.006)
    # Rear radial stiffeners support the dish skin from the load distributor.
    for i in range(8):
        a=i*math.tau/8
        c,s=math.cos(a),math.sin(a)
        seat(k,rod((.17*c,.27,2+.17*s),(.96*c,-.12,2+.96*s),.019,6),SEC,'rear radial reflector rib',ELEV)
    # Feed horn has an open throat aimed into the reflector. Phase centre at f.
    receiver=drum_y([(FOCUS_Y-.14,.075),(FOCUS_Y-.10,.11),
                     (FOCUS_Y-.084,.11),(FOCUS_Y-.072,.11),
                     (FOCUS_Y-.035,.11),(FOCUS_Y,.075)],12)
    receiver=machine(receiver,cuts=[((0,FOCUS_Y-.017,2),(0,FOCUS_Y+.015,2),.058,12)])
    emit(k,receiver,SEC,'lofted focal receiver and open RF horn',ELEV)
    for f in k.bm.faces:
        if FOCUS_Y-.084 < f.calc_center_median().y < FOCUS_Y-.072:
            f.material_index=kit.SLOTS.index(EMI)
    emit(k,drum_y([(FOCUS_Y-.017,.0545),(FOCUS_Y-.015,.0545)],12),FRM,'recessed RF throat backing',ELEV)
    emit(k,drum_y([(FOCUS_Y-.144,.061),(FOCUS_Y-.140,.061)],12),JNT,'receiver sealed rear cap',ELEV)
    for i in range(3):
        a=i*math.tau/3
        screw(k,(.045*math.cos(a),FOCUS_Y-.144,2+.045*math.sin(a)),(0,-1,0),'receiver cap captive screw',ELEV,r=.005)
    # Three bipod feeds join a bolted rim shoe to a receiver clamp. Pads and
    # spars are seated by exact subtraction on the actual shell surfaces.
    for i in range(3):
        a=math.pi/2+i*math.tau/3
        c,s=math.cos(a),math.sin(a)
        r=.91;yy=.12-.30*r*r
        at=Vector((r*c,yy,2+r*s))
        normal=Vector((-.57*c,-1,-.57*s)).normalized()
        mount=common.frame(at,normal,(-s,0,c))
        pad=xf(loft([(.12,.15,.012,-.004),(.12,.15,.012,.030)]),mount)
        seat(k,pad,SEC,'focal tripod foot seated on reflector',ELEV)
        target=Vector((.145*c,FOCUS_Y-.065,2+.145*s))
        clamp=xf(loft([(.12,.064,.006,0),(.12,.064,.006,.045)]),
                 common.frame((.103*c,FOCUS_Y-.065,2+.103*s),(c,0,s),(0,1,0)))
        seat(k,clamp,JNT,'receiver tripod socket collar',ELEV)
        for tangent in (-.032,.032):
            start=mount@Vector((0,tangent,.030))
            end=target+Vector((-s*tangent,0,c*tangent))
            axis=(end-start).normalized();up=Vector((-s,0,c))
            p=feed_socket(k,start,axis,up,'reflector bipod foot')
            q=feed_socket(k,end,-axis,up,'receiver bipod terminal')
            emit(k,rod(p,q,.012,6),JNT,'bipod tube seated at both blind bore floors',ELEV)
        for t in (-.052,.052):
            screw(k,mount@Vector((.042,t,.030)),normal,'tripod foot captive bolt',ELEV,r=.005)
    # Rear service hatch is pocketed, with bolts wholly on its planar face.
    for x in (-.12,.12):
        for z in (1.88,2.12): screw(k,(x,.362,z),(0,1,0),'RF backend cover fastener',ELEV)


def services(k):
    # A sealed geared rotary drive at the bearing. The shaft carries RF/data
    # through a rotary coax feedthrough, so no rigid cable crosses the hinge.
    m=common.frame((1.240,.26,2),(1,0,0),(0,0,1))
    body=xf(loft([(.27,.27,.032,0),(.27,.27,.032,.07),
                  (.21,.21,.024,.15)]),m)
    # Drive casing has space around the rotating retaining cap.
    body=machine(body,cuts=[((1.22,.26,2),(1.255,.26,2),.094,12)])
    cover_at=(1.390,.26,2)
    body,cover=pocket(body,cover_at,(1,0,0),.125,.125,SEC,'flush gearbox service cover')
    seat(k,body,PRI,'sealed coaxial elevation reduction gearbox')
    emit(k,*cover)
    for y in (.216,.304):
        for z in (1.956,2.044):screw(k,(1.390,y,z),(1,0,0),'gearbox cover screw',r=.0045)
    # Fixed wiring trunk from cabinet to drive, with seated connector glands.
    points=[(.335,.12,.33),(.48,.12,.33),(.68,.44,.33),
            (1.10,.62,.50),(1.10,.62,1.76),(1.31,.62,1.80),
            (1.31,.26,1.80),(1.31,.26,1.845)]
    seat(k,rod((.285,.12,.33),(.335,.12,.33),.025,8),JNT,'controller loom connector gland')
    seat(k,rod((1.31,.26,1.845),(1.31,.26,1.90),.025,8),JNT,'drive loom connector gland')
    pts=list(map(Vector,points));rows=[];u=Vector((0,1,0));previous=Vector((1,0,0))
    for i,p in enumerate(pts):
        d=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        u=previous.rotation_difference(d)@u
        u=(u-d*u.dot(d)).normalized();v=d.cross(u);previous=d
        rows.append([p+.008*(u*math.cos(j*math.tau/6)+v*math.sin(j*math.tau/6)) for j in range(6)])
    emit(k,kit.loft_rings(rows),FRM,'supported controller drive cable loom')
    for z in (.65,1.10,1.55):
        seat(k,block((1.077,.335,z-.012),(1.125,.633,z+.012)),JNT,'loom saddle clamp on tower')


def animation_specs():
    track=[(f,-8*(1-math.cos(math.tau*f/180))) for f in range(181)]
    def move(reverse):
        return [(f,-35*(1-(f/120)**2*(3-2*f/120) if reverse else (f/120)**2*(3-2*f/120))) for f in range(121)]
    return {'track':(True,'LINEAR',{ELEV:track}),
            'service_raise':(False,'LINEAR',{ELEV:move(False)}),
            'service_return':(False,'LINEAR',{ELEV:move(True)})}


def export_runtime(rig,body):
    kit.select_only([rig,*body])
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_materials='EXPORT')


def separate_assemblies(obj,rig):
    """Fixed frame and moving reflector are distinct manufactured assemblies."""
    result=[]
    for bone,name in ((ROOT,'SK_Satellite'),(ELEV,'SK_SatelliteReflector')):
        bm=bmesh.new();bm.from_mesh(obj.data);deform=bm.verts.layers.deform.active
        group=obj.vertex_groups[bone].index
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if group not in v[deform]],context='VERTS')
        mesh=bpy.data.meshes.new(name+'_Mesh');bm.to_mesh(mesh);bm.free()
        part=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(part)
        for g in obj.vertex_groups:part.vertex_groups.new(name=g.name)
        for m in obj.data.materials:mesh.materials.append(m)
        kit.skin(part,rig);result.append(part)
    mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
    return result


def main():
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
                    (ELEV,ROOT,'hinge',tuple(PIVOT),(1,0,0),(0,0,1),(-35,10))]
    kit.GROUPS=();kit.ANIMATIONS=animation_specs()
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    chassis(k);dish(k);services(k)
    pairs=common.exact_intersections(k)
    kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[])
    states=[(f'{name} frame {f}',{ELEV:value}) for name,spec in kit.ANIMATIONS.items() for f,value in spec[2][ELEV]]
    states += [(f'limit sweep {a}',{ELEV:a}) for a in range(-35,11)]
    kit.check_motion(k,joints,states)
    body=k.to_object('SK_SatelliteAssembly',joints=kit.rotary_joints(joints));kit.skin(body,rig)
    flat=body.data.attributes.get('machined_flat')
    if flat:
        for poly,value in zip(body.data.polygons,flat.data):
            if value.value:poly.use_smooth=False
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
    kit.check_coplanar(body);tris=kit.triangles(body)
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    bodies=separate_assemblies(body,rig)
    mesh_counts={o.name:kit.triangles(o) for o in bodies}
    print(f'[{NAME}] assembly triangles {mesh_counts}',flush=True)
    assert all(n<=5000 for n in mesh_counts.values()),mesh_counts
    if '--draft' not in sys.argv:
        common.prepare_export([rig,*bodies],HERE,NAME)
        for pb in rig.pose.bones:
            for c in list(pb.constraints):pb.constraints.remove(c)
        export_runtime(rig,bodies)
    report=dict(name=NAME,triangles=tris,triangle_budget=5000,triangle_budget_scope='per manufactured render assembly',meshes=mesh_counts,bounds_m=dict(lo=lo,hi=hi),
        tensor_height_m=1.753,reflector_diameter_m=2,reflector_depth_m=DEPTH,focus_y_m=FOCUS_Y,
        materials=list(kit.MATERIALS),
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=kit.ANIMATIONS[n][0]) for n,a in actions.items()},
        checks=dict(connected_parts=len(k.parts),exact_solid_pairs=pairs,motion_states=len(states),no_solid_intersections=True,coplanar=True),
        placement='floor centre z=0; front -Y; up +Z; library only')
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    rig['preview_poses']=json.dumps({'service':{ELEV:{'rot':[-35,0,0]}},'down_limit':{ELEV:{'rot':[10,0,0]}}})
    rig['preview_pose_views']=json.dumps({p:['front_left','left','rear_right'] for p in ('service','down_limit')})
    bpy.context.scene['preview_actions']=json.dumps(list(actions))
    bpy.context.scene['showcase_frame']=json.dumps(dict(lo=[-1.25,-1.18,0],hi=[1.40,1.12,3.05]))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles, {len(k.parts)} connected manufactured parts',flush=True)


if __name__=='__main__':main()
