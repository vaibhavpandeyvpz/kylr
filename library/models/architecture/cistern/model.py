"""15 m lunar cistern: walk-in maintenance chamber over a sealed reservoir.
Scripted manufacturing geometry, metres, front -Y. Library only.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Regolith': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'environments'))
import light_common as common
sys.path.insert(0,str(HERE.parent))
import light_mounts

def fixture_mounts(rig,meshes):
    return light_mounts.install(rig,meshes,
        [(tag,(x,y,2.7),(0,0,1)) for tag,x,y in
            (('North',0,4.1),('East',4.1,0),('South',0,-4.1),('West',-4.1,0))],
        [(tag,(0,0,2.0),direction) for tag,direction in
            (('North',(0,1,0)),('East',(1,0,0)),('West',(-1,0,0))) if tag!='North']+
        [('North',(2,0,2.0),(0,1,0))])

def refresh_mounts():
    bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
    markers,mount_info=fixture_mounts(rig,meshes)
    export_runtime(rig,meshes,markers)
    report=json.loads((HERE/f'{NAME}_rig.json').read_text());report['gizmos']=mount_info
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
ROOT=common.ROOT
PRI,SEC,FRM,JNT,EMI=common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
REG=PRI
NAME,TITLE='cistern','Cistern'
MODULE=1
REAR_DOOR=False
BUDGET=12000  # User-approved ceiling for the walkable 15 m architecture asset.
N=40
R,INNER=6.85,6.50
FLOOR,CEILING=.10,3.10
PX,PY=-1.04,-7.41
PRESSURE_FRAME=dimensions.entry_frame((0,-7.30,.10),.75)
block,rod=common.block,common.rod

def emit(k,bm,mat,label,bone=ROOT):
    if REAR_DOOR and bone in ('Door','Lock'):bone='Rear'+bone
    before=set(k.bm.faces)
    old=common.ROOT;common.ROOT=bone
    try:common.emit(k,bm,mat,label)
    finally:common.ROOT=old
    layer=k.bm.faces.layers.int.get('delivery_module') or k.bm.faces.layers.int.new('delivery_module')
    module=2 if MODULE==1 and ('crown' in label or 'central reservoir inspection cover' in label) else MODULE
    for f in set(k.bm.faces)-before:f[layer]=module

def mach(bm,**kw):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    return kit.machine(bm,**kw)

def xf(bm,m):
    for v in bm.verts:v.co=m@v.co
    return bm

def seat(k,bm,mat,label,bone=ROOT):
    if REAR_DOOR and bone in ('Door','Lock'):bone='Rear'+bone
    bm=xf(bm,k.xf);old=k.xf;k.xf=Matrix.Identity(4)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    for p in k.parts:
        if p.bone!=bone:continue
        lo=[min(v.co[i] for v in bm.verts) for i in range(3)]
        hi=[max(v.co[i] for v in bm.verts) for i in range(3)]
        if any(min(hi[i],p.hi[i])-max(lo[i],p.lo[i])<2e-6 for i in range(3)):continue
        tool=bmesh.new();vs=[tool.verts.new(v) for v in p.verts]
        for f in p.faces:tool.faces.new([vs[i] for i in f])
        # Cutter offset supplies a real 0.2 mm manufacturing clearance.
        bmesh.ops.recalc_face_normals(tool,faces=tool.faces[:]);tool.normal_update()
        for v in tool.verts:v.co+=v.normal*.0002
        bm=boolean_bm(bm,tool,'DIFFERENCE')
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm,edges=bm.edges[:],dist=1e-7)
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    emit(k,bm,mat,label,bone);k.xf=old

def revolve(profile,n=None):
    n=n or N
    bm=bmesh.new()
    rows=[[bm.verts.new((r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),z)) for i in range(n)] for r,z in profile]
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(n):bm.faces.new((a[i],a[(i+1)%n],b[(i+1)%n],b[i]))
    return bm

def roof_shell():
    # Directly loft narrow V expansion joints. Shared vertices, no repeated
    # Boolean triangulation across the broad planar roof.
    angles=sorted(set([i*math.tau/N for i in range(N)]+[(i*math.tau/8+s*.002)%math.tau for i in range(8) for s in (-1,1)]))
    profile=[(7.02,2.95),(7.15,3.06),(7.15,3.20),(6.98,3.34),
             (1.12,3.34),(1.12,3.14),(1.00,3.14),(1.00,3.10),(INNER,3.10),(INNER,2.95)]
    bm=bmesh.new();rows=[]
    for r,z in profile:
        rows.append([bm.verts.new((r*math.cos(a),r*math.sin(a),z-(.018 if z==3.34 and abs(a/(math.tau/8)-round(a/(math.tau/8)))<1e-6 else 0))) for a in angles])
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(len(angles)):bm.faces.new((a[i],a[(i+1)%len(angles)],b[(i+1)%len(angles)],b[i]))
    return bm,angles

def fastener(k,at,normal,label,bone=ROOT,r=.021):
    # Socket head lands on the mating flat; captive threaded shank is internal.
    p=Vector(at);n=Vector(normal).normalized()
    bm=rod(p,p+n*.012,r,6)
    bm=mach(bm,cuts=[(p+n*.006,p+n*.016,r*.46,6)])
    emit(k,bm,JNT,label,bone)

def roof_hardware(k):
    global MODULE
    old=MODULE;MODULE=2
    for i in range(8):
        a=i*math.tau/8
        m=Matrix.Translation((6.30*math.cos(a),6.30*math.sin(a),0))@Matrix.Rotation(a,4,'Z')
        with k.frame(m):
            plate=common.loft([(.44,.34,.04,3.34),(.44,.34,.04,3.385),(.39,.29,.025,3.41)])
            emit(k,plate,FRM,'bolted roof seam retention bridge')
            for x in (0,):
                for y in (-.087,.087):fastener(k,(x,y,3.41),(0,0,1),'roof bridge socket fastener')
    for i in range(8):
        a=(i+.5)*math.tau/8
        fastener(k,(1.07*math.cos(a),1.07*math.sin(a),3.32),(0,0,1),'inspection cover captive fastener')
    MODULE=old

def outline(w,lo,hi,c=.16):
    return [(-w+c,lo),(w-c,lo),(w,lo+c),(w,hi-c),(w-c,hi),(-w+c,hi),(-w,hi-c),(-w,lo+c)]

def pressure_ports(bm):
    # Transform the complete bore, retaining the bolt's elliptical section
    # after cartridge resizing; scaling only its radius would block the bolt.
    from types import SimpleNamespace
    cutters=[]
    for sign in (-1,1):
        turn=Matrix.Diagonal((sign,sign,1,1))
        for a,b,r,n in (((.99,-7.235,1.45),(1.20,-7.235,1.45),.026,8),
                        ((PX,PY,.14),(PX,PY,.33),.025,10)):
            tool=xf(rod(a,b,r,n),turn@PRESSURE_FRAME)
            tool.verts.index_update()
            cutters.append(SimpleNamespace(verts=[v.co.copy() for v in tool.verts],faces=[[v.index for v in f.verts] for f in tool.faces]))
            tool.free()
    return common.trim_seats(bm,cutters)

def entry_outline(w,lo,hi,c=.16):
    return [(x*.75,z) for x,z in outline(w,lo,hi,c)]

def entry_passage(w,lo,hi,y0,y1,c=.16):
    return kit.prism_bm([(x,(y0+y1)/2,z) for x,z in entry_outline(w,lo,hi,c)],y1-y0,(0,1,0))

def passage(w,lo,hi,y0,y1,c=.16):
    return kit.prism_bm([(x,(y0+y1)/2,z) for x,z in outline(w,lo,hi,c)],y1-y0,(0,1,0))

def pressure_wall():
    """Continuous machined pressure shell; no decorative tile-grid geometry."""
    wall=revolve([(R,.45),(R,2.95),(INNER,2.95),(INNER,.45)])
    # Cardinal side centres lie on facet junctions. Machine two shallow flat
    # seats between the buttresses so a complete sconce backplate rests on wall.
    for sign in (-1,1):
        x0,x1=sorted((sign*(R-.04),sign*(R+.10)))
        wall=boolean_bm(wall,block((x0,-.40,1.30),(x1,.40,2.10)),'DIFFERENCE')
    return wall

def architecture(k):
    # Ground-contact footing and sealed reservoir lid form the maintenance deck.
    deck=rod((0,0,0),(0,0,FLOOR),7.5,N)
    rampcut=kit.prism_bm([(0,-7.60,-1/60),(0,-6.90,.10),(0,-6.90,.30),(0,-7.60,.30)],1.68,(1,0,0))
    rear_ramp=kit.prism_bm([(0,7.60,-1/60),(0,6.90,.10),(0,6.90,.30),(0,7.60,.30)],1.68,(1,0,0))
    deck=boolean_bm(deck,rampcut,'DIFFERENCE')
    bmesh.ops.triangulate(deck,faces=deck.faces[:])
    deck=boolean_bm(deck,rear_ramp,'DIFFERENCE')
    emit(k,deck,SEC,'ground-bearing reservoir foundation and continuous walkable deck')
    collar=revolve([(7.16,.10),(7.16,.27),(7.02,.45),(INNER,.45),(INNER,.10)])
    collar=mach(collar,subtract=[([(x,y,z) for x,z in entry_outline(1.0,.10,2.8)],(0,1,0),3) for y in (-7,7)])
    body=pressure_wall()
    hood=kit.loft_rings([[(x,y,z) for x,z in outline(w,.10,h)] for y,w,h in
        ((-7.30,1.27,3.02),(-7.15,1.34,3.10),(-6.55,1.30,3.10),(-6.25,1.14,2.95))])
    rear_hood=xf(hood.copy(),Matrix.Rotation(math.pi,4,'Z'))
    # The vestibule is a formed pressure-shell continuation, fused before cutting.
    buttresses=[]
    for i in range(8):
        poly=[(6.58,0,.10),(7.38,0,.10),(7.38,0,.32),(7.06,0,1.03),(6.98,0,2.95),(6.60,0,2.95)]
        buttresses.append(xf(kit.prism_bm(poly,.46,(0,1,0)),Matrix.Rotation((i+.5)*math.tau/8,4,'Z')))
    for formed_part in (hood,rear_hood,collar,*buttresses):
        bmesh.ops.triangulate(body,faces=body.faces[:])
        body=boolean_bm(body,formed_part,'UNION')
    bmesh.ops.triangulate(body,faces=body.faces[:])
    body=mach(body,subtract=[([(x,y,z) for x,z in entry_outline(1.0,.10,2.80)],(0,1,0),2.5) for y in (-6.95,6.95)],
        cuts=[])
    body=pressure_ports(body)
    emit(k,body,REG,'continuous machined pressure wall and fused walk-through vestibule')
    for f in k.bm.faces:
        if f.material_index==kit.SLOTS.index(REG) and f.calc_center_median().z<.451:f.material_index=kit.SLOTS.index(SEC)
    roof,angles=roof_shell()
    seat(k,roof,SEC,'lofted crown and segmented sealed roof')
    # Cover uses the exact angular boundary of the roof, with a 0.1 mm seal gap.
    bm=bmesh.new();rows=[[bm.verts.new((1.1199*math.cos(a),1.1199*math.sin(a),z)) for a in angles] for z in (3.14,3.32)]
    for i in range(len(angles)):bm.faces.new((rows[0][i],rows[0][(i+1)%len(angles)],rows[1][(i+1)%len(angles)],rows[1][i]))
    bm.faces.new(rows[0]);bm.faces.new(rows[1]);emit(k,bm,SEC,'seated central reservoir inspection cover')
    # Eight monolithic buttresses, formed from a tapered side profile.
    for i in range(8):
        a=(i+.5)*math.tau/8
        m=Matrix.Rotation(a,4,'Z')
        strap=kit.prism_bm([(7.31,0,.45),(7.44,0,.45),(7.16,0,1.05),(7.07,0,2.91),(6.98,0,2.91),(7.06,0,1.05)],.28,(0,1,0))
        seat(k,xf(strap,m),SEC,'fitted buttress protection strap')
        with k.frame(m):
            fastener(k,(7.356,0,.63),(1,0,.28/.60),'lower buttress strap retaining fastener',r=.025)
            fastener(k,(7.08016129,0,2.70),(1,0,.09/1.86),'upper buttress strap retaining fastener',r=.025)
        clamp=xf(common.loft([(.62,.82,.07,2.95),(.60,.80,.06,3.12),(.54,.72,.05,3.38)]),Matrix.Translation((6.88*math.cos(a),6.88*math.sin(a),0))@m)
        seat(k,clamp,SEC,'roof compression lug seated into crown')
        with k.frame(Matrix.Translation((6.88*math.cos(a),6.88*math.sin(a),0))@m):
            fastener(k,(-.18,0,3.38),(0,0,1),'compression lug retaining fastener',r=.025)
            fastener(k,(.18,0,3.38),(0,0,1),'compression lug retaining fastener',r=.025)
    roof_hardware(k)
    # No step: a solid wedge from lunar grade to the 100 mm deck.
    # Ramp is carved into the continuous deck; no overlapping ramp insert.

def boolean_bm(base,tool,op):
    def obj(bm):
        bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
        mesh=bpy.data.meshes.new('_manufacture');bm.to_mesh(mesh);bm.free()
        o=bpy.data.objects.new('_manufacture',mesh);bpy.context.scene.collection.objects.link(o);return o
    a,b=obj(base),obj(tool);mod=a.modifiers.new('manufactured interface','BOOLEAN')
    mod.operation,mod.solver,mod.object=op,'EXACT',b
    bm=bmesh.new();bm.from_object(a,bpy.context.evaluated_depsgraph_get())
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    for o in (a,b):
        mesh=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.meshes.remove(mesh)
    return bm

def authored_door(k):
    # Pressure seat and gasket are rings, leaving the walk-through unobstructed.
    bezel=passage(1.21,.10,3.00,-7.38,-7.30,.18)
    bezel=boolean_bm(bezel,passage(1.0,.10,2.80,-7.5,-7.1),'DIFFERENCE')
    bezel=mach(bezel,cuts=[((.99,-7.235,1.45),(1.20,-7.235,1.45),.026,8)])
    motor=rod((PX,PY,.15),(PX,PY,.32),.080,12)
    bezel=mach(bezel,union=[motor],cuts=[((PX,PY,.14),(PX,PY,.33),.025,10)])
    bezel=mach(bezel,cuts=[((PX,PY,z-.041),(PX,PY,z+.041),.0665,10) for z in (.43,1.45,2.48)])
    bezel=mach(bezel,boxes=[((-1.035,-7.35,z),(.15,.122,.082)) for z in (.43,1.45,2.48)])
    bezel=mach(bezel,cuts=[((PX,PY,zz-.001),(PX,PY,zz+.009),.041,8) for z in (.43,1.45,2.48) for zz in (z-.118,z+.11)])
    seat(k,bezel,SEC,'machined door surround and seal land')
    seal=passage(1.0,.10,2.80,-7.26,-7.22)
    seal=boolean_bm(seal,passage(.970,.131,2.769,-7.4,-7.1),'DIFFERENCE')
    seal=mach(seal,cuts=[((.94,-7.235,1.45),(1.02,-7.235,1.45),.026,8)])
    # Three-sided weather seal: no raised sill across the walking floor.
    seal=mach(seal,boxes=[((0,-7.24,.10),(2.2,.30,.07))])
    seat(k,seal,FRM,'continuous recessed pressure gasket')
    leaf=kit.loft_rings([[(x,y,z) for x,z in outline(w,lo,hi,.16)] for y,w,lo,hi in
        ((-7.295,.965,.136,2.764),(-7.26,.969,.132,2.768),(-7.18,.950,.151,2.749))])
    leaf=mach(leaf,boxes=[((.03,-7.31,1.5),(1.42,.07,1.80))],
        cuts=[((.53,-7.235,1.45),(1.08,-7.235,1.45),.026,8),((PX,PY,.14),(PX,PY,.33),.081,12)])
    emit(k,leaf,PRI,'lofted pressure leaf with recessed face and lock tunnel','Door')
    # A face inlay seats at the exact bottom of the machined recess.
    panel=mach(block((-.68,-7.280,.60),(.74,-7.275,2.40)),cuts=[((.53,-7.235,1.45),(1.08,-7.235,1.45),.026,8)])
    seat(k,panel,SEC,'recessed door stiffening panel','Door')
    # Three interleaved hinges on a common retained vertical shaft.
    for z in (.43,1.45,2.48):
        for lo,hi in ((z-.10,z-.042),(z+.042,z+.10)):
            lug=rod((PX,PY,lo),(PX,PY,hi),.068,10)
            lug=mach(lug,union=[block((PX-.16,PY,lo),(PX,-7.30,hi))],cuts=[((PX,PY,lo-.01),(PX,PY,hi+.01),.025,10)])
            seat(k,lug,SEC,'fixed bored hinge clevis')
        tongue=rod((PX,PY,z-.04),(PX,PY,z+.04),.062,10)
        tab=kit.prism_bm([(xx,yy,z) for xx,yy in ((PX,PY),(-.90,PY),(-.90,-7.275),(-.95,-7.275),(-.98,-7.301),(PX,-7.301))],.08,(0,0,1))
        tongue=mach(tongue,union=[tab],cuts=[((PX,PY,z-.05),(PX,PY,z+.05),.026,10)])
        seat(k,tongue,SEC,'moving bored hinge tongue','Door')
        emit(k,rod((PX,PY,z-.11),(PX,PY,z+.11),.024,10),JNT,'retained hinge pin')
        for zz in (z-.118,z+.11):emit(k,rod((PX,PY,zz),(PX,PY,zz+.008),.040,8),JNT,'hinge pin end retainer')
    # Captive shoot bolt: retracts before hinge rotation and extends after closure.
    # Receiver bore is machined directly in the integral jamb casting.
    emit(k,rod((.72,-7.235,1.45),(1.08,-7.235,1.45),.025,8),JNT,'captive powered shoot bolt','Lock')
    # Geared hinge drive attaches below the lowest knuckle, with a bored shaft.
    emit(k,rod((PX,PY,.16),(PX,PY,.312),.024,10),JNT,'drive output shaft into lower hinge pin')
    # Recessed cyan status strips in the surround, integral seat boundaries.
    for x in (-1.10,1.10):
        # Fish-mouth indicator housing to the actual vestibule surface.
        for lo,hi in ((.75,1.22),(1.68,2.26)):
            housing=block((x-.045,-7.44,lo),(x+.045,-7.38,hi))
            housing=mach(housing,boxes=[((x,-7.445,(lo+hi)/2),(.034,.06,hi-lo-.08))])
            emit(k,housing,SEC,'machined indicator housing')
            emit(k,block((x-.017,-7.420,lo+.04),(x+.017,-7.415,hi-.04)),EMI,'flush cyan jamb status lens')
    pad=block((.64,-7.35,1.00),(.89,-7.295,1.25))
    pad=mach(pad,boxes=[((.765,-7.36,1.125),(.14,.035,.14))])
    seat(k,pad,FRM,'door control recessed bezel','Door')
    emit(k,block((.695,-7.3475,1.055),(.835,-7.3425,1.195)),EMI,'sealed control lens','Door')
    for x in (-.57,.61):
        for z in (.73,2.26):fastener(k,(x,-7.280,z),(0,-1,0),'door stiffener captive fastener','Door',.019)
    for z in (1.40,1.84):
        seat(k,block((.26,-7.34,z-.06),(.41,-7.275,z+.06)),FRM,'manual handle bolted foot','Door')
        fastener(k,(.28,-7.34,z),(0,-1,0),'handle mounting fastener','Door',.012)
    handle=pipe([(.35,-7.34,1.40),(.35,-7.43,1.40),(.35,-7.46,1.44),(.35,-7.46,1.80),(.35,-7.43,1.84),(.35,-7.34,1.84)],.023,8)
    emit(k,handle,JNT,'terminated manual door pull handle','Door')

def door(k):
    with k.frame(PRESSURE_FRAME):authored_door(k)


def services(k):
    # Pump/valve skid sits on the deck left of the door. Connections are terminated
    # by flanges in wall sockets; clamps have bored collars and fish-mouth seats.
    x,y=-2.00,-6.85
    # A distinct machined plate sits clear of the buttress, fitted to the wall.
    plate=block((-2.53,-6.70,.60),(-1.48,-6.10,2.14))
    plate=mach(plate,cuts=[((x,y,.59),(x,y,1.26),.181,12),((x,y,1.249),(x,y,1.313),.231,12)])
    seat(k,plate,SEC,'wall-fitted service mounting plate clear of buttress')
    for xx in (-2.46,-1.56):
        for zz in (.68,2.06):fastener(k,(xx,-6.70,zz),(0,-1,0),'service plate anchor fastener',r=.016)
    base=common.loft([(.70,.50,.055,.10),(.70,.50,.055,.38),(.60,.42,.045,.46)])
    seat(k,xf(base,Matrix.Translation((x,y,0))),FRM,'deck-mounted service pump plinth')
    emit(k,rod((x,y,.46),(x,y,1.25),.18,12),FRM,'sealed transfer pump body')
    emit(k,rod((x,y,1.25),(x,y,1.30),.23,12),JNT,'pump bolted top flange')
    for i in range(4):
        a=(i+.5)*math.tau/4
        fastener(k,(x+.195*math.cos(a),y+.195*math.sin(a),1.30),(0,0,1),'pump flange socket fastener',r=.017)
    # Swept pipe elbow, exact tube geometry; no overlapping straight cylinders.
    pts=[(x,y,1.30),(x,y,1.58),(x-.04,y,1.68),(x-.14,y,1.72),
         (x-.26,y,1.72),(x-.36,y,1.68),(x-.40,y,1.58),(x-.40,y,.30)]
    tube=pipe(pts,.065,8)
    seat(k,tube,JNT,'swept service return pipe with supported elbow ends')
    seat(k,rod((x-.40,y,.10),(x-.40,y,.30),.10,10),SEC,'reservoir return deck flange')
    # Backplate takes pipe clamps and visible instrument ports.
    for xx,zz in ((x-.40,.70),(x-.40,1.40),(x,1.40)):
        clamp=rod((xx,y,zz-.035),(xx,y,zz+.035),.10,8)
        clamp=mach(clamp,union=[block((xx-.12,y,zz-.035),(xx+.12,-6.70,zz+.035))],cuts=[((xx,y,zz-.04),(xx,y,zz+.04),.065,8)])
        seat(k,clamp,FRM,'bored pipe support collar on service backplate')
    # Round pressure instrument bolted to the backplate; sealed cyan face.
    seat(k,rod((x-.30,-6.94,1.94),(x-.30,-6.70,1.94),.14,12),FRM,'pressure transmitter and panel socket')
    emit(k,rod((x-.30,-6.946,1.94),(x-.30,-6.94,1.94),.10,12),EMI,'pressure transmitter sealed lens')
    # Grounded, terminated power conduit held by glands; no wire across the door.
    for lo,hi in ((.46,.53),(1.765,1.835)):
        gland=rod((x+.23,-6.93,lo),(x+.23,-6.93,hi),.04,6)
        supports=[block((x+.18,-6.93,lo),(x+.28,-6.70,hi))] if lo>1 else []
        gland=mach(gland,union=supports,cuts=[((x+.23,-6.93,lo-.01),(x+.23,-6.93,hi+.01),.019,6)])
        seat(k,gland,SEC,'conduit terminal gland seated to skid or backplate')
    emit(k,rod((x+.23,-6.93,.46),(x+.23,-6.93,1.80),.018,6),FRM,'terminated service power conduit')

def pipe(points,r,n):
    # Parallel transport avoids the roll flips of independent tracking quats.
    # Every section retains the same circular radius and vertex correspondence.
    pts=list(map(Vector,points));rings=[];previous=None;basis=None
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized()
        if previous is None:
            seed=Vector((1,0,0)) if abs(tangent.x)<.8 else Vector((0,1,0))
            basis=(seed-tangent*seed.dot(tangent)).normalized()
        else:
            basis=previous.rotation_difference(tangent)@basis
            basis=(basis-tangent*basis.dot(tangent)).normalized()
        other=tangent.cross(basis).normalized()
        rings.append([p+r*(basis*math.cos(j*math.tau/n)+other*math.sin(j*math.tau/n)) for j in range(n)])
        previous=tangent
    return kit.loft_rings(rings)

def specs():
    keys={'Door':[(0,0),(21,0),(81,-110),(96,-110)],'Lock':[(0,0),(15,-.18),(96,-.18)]}
    reverse=lambda data:{b:[(96-f,v) for f,v in reversed(ks)] for b,ks in data.items()}
    rear={'Rear'+b:frames for b,frames in keys.items()}
    both={**keys,**rear}
    return {'open':(False,'BEZIER',keys),'close':(False,'BEZIER',reverse(keys)),
        'open_front':(False,'BEZIER',keys),'close_front':(False,'BEZIER',reverse(keys)),
        'open_rear':(False,'BEZIER',rear),'close_rear':(False,'BEZIER',reverse(rear)),
        'open_both':(False,'BEZIER',both),'close_both':(False,'BEZIER',reverse(both))}

def split_modules(body):
    result=[]
    for num,label in ((1,'Structure'),(2,'Roof'),(3,'FrontMechanisms'),(3,'RearMechanisms')):
        obj=body.copy();obj.data=body.data.copy();obj.name='SK_'+TITLE+label
        bpy.context.scene.collection.objects.link(obj)
        bm=bmesh.new();bm.from_mesh(obj.data);layer=bm.faces.layers.int['delivery_module']
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f[layer]!=num or
            (num==3 and ((label=='FrontMechanisms' and f.calc_center_median().y>0) or
                         (label=='RearMechanisms' and f.calc_center_median().y<=0)))],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free();result.append(obj)
    mesh=body.data;bpy.data.objects.remove(body,do_unlink=True);bpy.data.meshes.remove(mesh)
    return result

def export_runtime(rig,meshes,markers,prepared=False):
    from door_actions import install_fbx_filter,isolate_glb
    install_fbx_filter()
    for pb in rig.pose.bones:
        for c in list(pb.constraints):pb.constraints.remove(c)
    if not prepared:common.prepare_export([rig,*meshes,*markers],HERE,NAME)
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
    isolate_glb(HERE/f'{NAME}.glb')

def resize_door_specs():
    revised=[]
    for name,parent,kind,pivot,axis,d,limits in kit.JOINT_SPECS:
        if name!=ROOT:
            turn=Matrix.Diagonal((-1,-1,1,1)) if name.startswith('Rear') else Matrix.Identity(4)
            pivot=turn@PRESSURE_FRAME@turn@Vector(pivot)
            if kind=='slide':limits=tuple(v*.75 for v in limits)
        revised.append((name,parent,kind,pivot,axis,d,limits))
    kit.JOINT_SPECS=revised


def main():
    global MODULE,REAR_DOOR
    import perimeter_surface as surface
    contour=[(7.5*math.cos(i*math.tau/N),7.5*math.sin(i*math.tau/N),0) for i in range(N)]
    if '--surface-only' in sys.argv:
        surface.refresh(HERE,NAME,kit,contour,2.2,
            lambda rig,meshes,markers:export_runtime(rig,meshes,markers,prepared=True),rear_entrance=True)
        return
    if '--mounts-only' in sys.argv:refresh_mounts();return
    common.CORNER_STEPS=1;common.LABELS.clear();kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5);surface.configure(kit);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('Door',ROOT,'hinge',(PX,PY,1.45),(0,0,1),(0,-1,0),(-110,0)),
        ('Lock','Door','slide',(.90,-7.235,1.45),(1,0,0),(1,0,0),(-.18,0)),
        ('RearDoor',ROOT,'hinge',(-PX,-PY,1.45),(0,0,1),(0,1,0),(-110,0)),
        ('RearLock','RearDoor','slide',(-.90,7.235,1.45),(-1,0,0),(-1,0,0),(-.18,0))]
    resize_door_specs()
    kit.GROUPS=();kit.ANIMATIONS=specs()
    kit.ANIMATIONS=dimensions.scale_tracks(kit.ANIMATIONS,{'Lock':.75,'RearLock':.75})
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    MODULE=1;architecture(k)
    MODULE=3;door(k)
    REAR_DOOR=True
    with k.frame(Matrix.Rotation(math.pi,4,'Z')):door(k)
    REAR_DOOR=False
    # Place the entire skid in the bay between doorway and buttress. Its face
    # follows the perimeter tangent; moving only the plate would break mounts.
    service_angle=math.radians(-105)
    service_origin=Vector((6.96*math.cos(service_angle),6.96*math.sin(service_angle),0))
    service_frame=(Matrix.Translation(service_origin)
        @Matrix.Rotation(service_angle+math.pi/2,4,'Z')
        @Matrix.Translation((2.00,6.70,0)))
    with k.frame(service_frame):services(k)
    for p,label in zip(k.parts,common.LABELS):p.line=label
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    states.extend((f'swing {a}',{'Door':-a,'Lock':-.18*.75}) for a in range(111))
    states.extend((f'rear swing {a}',{'RearDoor':-a,'RearLock':-.18*.75}) for a in range(111))
    kit.check_motion(k,joints,states);kit.reset_pose(rig)
    source=[dict(label=l,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces) for p,l in zip(k.parts,common.LABELS)]
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps(source))
    body=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(body,rig)
    # Walk-in architecture: retain every player-visible interior face. As in
    # bunker, analytic culling removes only ground undersides; Kit already
    # removes mutually seated hidden faces. External-ray culling is unsuitable
    # for a complete occupied room and would unnecessarily discard its liner.
    bm=bmesh.new();bm.from_mesh(body.data)
    hidden=[f for f in bm.faces if all(v.co.z<1e-6 for v in f.verts) and f.normal.z<-.5]
    bmesh.ops.delete(bm,geom=hidden,context='FACES_ONLY');bm.to_mesh(body.data);bm.free()
    sys.path.insert(0,str(HERE.parents[1]/'architecture/lunar_dome'))
    from surface_audit import check_coplanar
    check_coplanar(body)
    tris=kit.triangles(body)
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    assert max(abs(v.co.x) for v in body.data.vertices)<=7.50001
    assert max(abs(v.co.y) for v in body.data.vertices)<=7.50001
    used=sorted({body.data.materials[p.material_index].name for p in body.data.polygons})
    meshes=split_modules(body);counts={o.name:kit.triangles(o) for o in meshes}
    meshes.append(surface.create(rig,contour,2.2,rear_entrance=True))
    counts={o.name:kit.triangles(o) for o in meshes};tris=sum(counts.values())
    used=sorted(set(used+[surface.MATERIAL]))
    assert all(n<=5000 for n in counts.values()),counts
    markers,mount_info=fixture_mounts(rig,meshes)
    if '--draft' not in sys.argv or '--review-export' in sys.argv:
        if '--review-export' not in sys.argv:
            assert tris<=BUDGET,(tris,BUDGET,'Detailed architecture budget requires user approval')
        export_runtime(rig,meshes,markers)
    report=dict(name=NAME,triangles=tris,meshes=counts,triangle_budget=BUDGET,triangle_budget_per_mesh=5000,
        budget_status='approved' if tris<=BUDGET else 'review_only_pending_budget_exception',
        bounds_m=dict(lo=lo,hi=hi),dimensions_m=dict(width=15,depth=15,height=hi[2]-lo[2]),materials=used,
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,type=j.kind,parent=j.parent,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        checks=dict(connected_parts=len(k.parts),exact_solid_pairs=pairs,motion_states=len(states),coplanar=True,interior_retained=True),
        gizmos=mount_info,
        entrance=dict(width_m=2.0,height_m=2.70,floor_m=FLOOR,ceiling_m=CEILING,door_swing_deg=110),
        placement='15 m circular grade-contact foundation; origin at ground centre; front -Y; library only',
        mechanics='Maintenance chamber over sealed below-deck water reservoir. Continuous machined pressure wall, formed roof, eight buttresses. Tangent-aligned service skid at -105 degrees. Three retained pinned hinges; geared hinge motor; enclosed 180 mm captive shoot bolt retracts before opening.')
    surface.update_report(report,meshes,kit)
    dimensions.report(NAME,report,width=1.5,height=2.70,floors=[FLOOR],ceilings=[3.14])
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    rig['preview_poses']=json.dumps({'unlocked':{'Lock':{'loc':[0,-.18,0]}},'open':{'Door':{'rot':[-110,0,0]},'Lock':{'loc':[0,-.18,0]}},
        'rear_open':{'RearDoor':{'rot':[-110,0,0]},'RearLock':{'loc':[0,-.18,0]}},
        'both_open':{'Door':{'rot':[-110,0,0]},'Lock':{'loc':[0,-.18,0]},'RearDoor':{'rot':[-110,0,0]},'RearLock':{'loc':[0,-.18,0]}}})
    bpy.context.scene['preview_actions']=json.dumps(list(actions))
    bpy.context.scene['preview_frame']=json.dumps(dict(lo=[-7.5,-7.5,0],hi=[7.5,7.5,3.4]))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles, {len(k.parts)} connected manufactured parts',flush=True)

if __name__=='__main__':main()
