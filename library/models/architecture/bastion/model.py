"""Duplex industrial bastion. Headless Blender 5.2; library-only source.

All dimensions, seams, joint travels and animations derive from this spec.
The single pressure door has Bastion-specific geometry and physical joint lands.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Regolith': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
MODELS=HERE.parents[1]
sys.path.insert(0,str(MODELS/'environments'))
import light_common as common
spec=importlib.util.spec_from_file_location('bastion_door_kit',HERE.parent/'hangar/model.py')
door=importlib.util.module_from_spec(spec);spec.loader.exec_module(door)
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
ROOT,PRI,SEC,FRM,JNT,EMI=common.ROOT,common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
GLASS='M_Glass'
NAME,TITLE='bastion','Bastion'
BUDGET=10000
GROUND=.32
UPPER=4.32
STROKE=UPPER-GROUND
SHAFT=(-2.65,2.65,2.38,6.5)
FLOOR_OPENINGS=[((-1.52,2.38),(1.52,5.42)),((-2.65,5.40),(2.65,6.50))]
LIFT_Y=3.9
ROOF_HALF=6.30
ROOF_GAP=(2*ROOF_HALF-2*3.20-1.75)/4
FRONT_LINE=-ROOF_HALF+ROOF_GAP
REAR_LINE=ROOF_HALF-ROOF_GAP
POD_X=ROOF_HALF-ROOF_GAP-1.60
POD_Y=FRONT_LINE+1.90
CONTROLLER_Y=FRONT_LINE+1.05
HEADER_X=-ROOF_HALF+ROOF_GAP+2.10
HEADER_Y=REAR_LINE-1.70
BONNET_X=ROOF_HALF-ROOF_GAP-1.35
BONNET_Y=REAR_LINE-1.35
ENTRY_WIDTH=2.0
ENTRY_TOP=3.22
RAMP_WIDTH=(ENTRY_WIDTH+.60)*.75  # Match the resized outer frame's feet.
HINGE=(1.12,-6.38,1.77)
ENTRY_RESIZE=dimensions.entry_frame((0,-6.50,GROUND),.75,(2.1/2.9)/dimensions.HEIGHT[NAME])
def portal_outline(margin=0):
    w=ENTRY_WIDTH/2+margin;t=ENTRY_TOP+margin;c=.24+margin*(2-math.sqrt(2))
    return [(-w,GROUND),(w,GROUND),(w,t-c),(w-c,t),(-w+c,t),(-w,t-c)]
def portal_prism(points,y0,y1):
    return kit.prism_bm([(x,(y0+y1)/2,z) for x,z in points],y1-y0,(0,1,0))
block,rod,loft=common.block,common.rod,common.loft
mach,transform=door.mach,door.transform
emit,seat=door.emit,door.seat
original_common_emit=common.emit
def tracked_emit(k,bm,mat,label):
    prior=set(k.bm.faces);original_common_emit(k,bm,mat,label)
    layer=k.bm.faces.layers.int.get('manufactured_part') or k.bm.faces.layers.int.new('manufactured_part')
    for f in set(k.bm.faces)-prior:f[layer]=len(k.parts)-1
common.emit=tracked_emit

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

def seat(k,bm,mat,label,bone=ROOT):
    """Exact machined mating surfaces; separate solids have no overlap."""
    old=k.xf;transform(bm,old);k.xf=Matrix.Identity(4)
    for pi,p in enumerate(k.parts):
        if p.bone!=bone:continue
        lo=[min(v.co[i] for v in bm.verts) for i in range(3)]
        hi=[max(v.co[i] for v in bm.verts) for i in range(3)]
        if any(min(hi[i],p.hi[i])-max(lo[i],p.lo[i])<2e-6 for i in range(3)):continue
        tool=bmesh.new();vs=[tool.verts.new(v) for v in p.verts]
        for f in p.faces:tool.faces.new([vs[i] for i in f])
        if label in ('formed continuous perimeter load belt','bored pipe saddle with wall foot','formed footing-to-crown structural rib','broad corner rib with integral foundation and transfer flanges'):
            bmesh.ops.recalc_face_normals(tool,faces=tool.faces[:]);tool.normal_update()
            for v in tool.verts:v.co+=v.normal*.0002
            bm=boolean_bm(bm,tool,'DIFFERENCE')
            tool=bmesh.new();vs=[tool.verts.new(v) for v in p.verts]
            for f in p.faces:tool.faces.new([vs[i] for i in f])
        bm=boolean_bm(bm,tool,'DIFFERENCE')
        assert bm.verts,('empty fitted part',label,common.LABELS[pi],list(p.lo),list(p.hi))
    bmesh.ops.dissolve_degenerate(bm,edges=bm.edges[:],dist=1e-7)
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    emit(k,bm,mat,label,bone);k.xf=old

def xy(w,c,z):return common.outline(w,w,c,z)

def profile(stations):return kit.loft_rings([xy(*s) for s in stations])

def cutbox(lo,hi):return (tuple((a+b)/2 for a,b in zip(lo,hi)),tuple(b-a for a,b in zip(lo,hi)))

def offset(bm,x=0,y=0,z=0):return transform(bm,Matrix.Translation((x,y,z)))

def full_land(k,label,points,normal):
    """Prove complete flange corners land on actual triangles using doubles.

    Blender's float BVH nearest-point calculation loses tens of microns on
    building-sized triangles. Barycentric projection avoids that cancellation.
    """
    host=next(p for p,t in zip(k.parts,common.LABELS) if t==label)
    def sub(a,b):return tuple(float(a[i])-float(b[i]) for i in range(3))
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    axis=tuple(Vector(normal).normalized())
    axis=tuple((k.xf.to_3x3().inverted().transposed()@Vector(axis)).normalized())
    for point in points:
        point=k.xf@Vector(point)
        found=False
        for face in host.faces:
            a,b,c=[host.verts[i] for i in face[:3]]
            u,v,q=sub(b,a),sub(c,a),sub(point,a)
            n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            length=math.sqrt(dot(n,n))
            if length<1e-10:continue
            n=tuple(x/length for x in n)
            if abs(dot(n,q))>1e-5 or abs(dot(n,axis))<.999:continue
            uu,uv,vv,uq,vq=dot(u,u),dot(u,v),dot(v,v),dot(u,q),dot(v,q)
            d=uu*vv-uv*uv
            if d<1e-15:continue
            s,t=(vv*uq-uv*vq)/d,(uu*vq-uv*uq)/d
            if s>=-1e-6 and t>=-1e-6 and s+t<=1+1e-6:found=True;break
        assert found,('unsupported flange corner',label,tuple(point))

def shell(k):
    # One continuous pressure shell, including formed shoulders and crown.
    body=profile([(13.8,1.4,GROUND),(13.8,1.4,2.98),(13.4,1.4,3.62),
                  (13.4,1.4,6.98),(12.6,1.4,7.94),(12.6,1.4,8.22)])
    # Parallel inner/outer corner profiles retain real wall thickness on every
    # chamfer. A smaller inner chamfer can break through the narrowed storey.
    room=profile([(13.0,1.4,GROUND-.01),(13.0,1.4,6.98),(12.05,1.4,7.70)])
    # A true hollow duplex room; the upper slab is fitted independently below.

    body=boolean_bm(body,room,'DIFFERENCE')
    bmesh.ops.triangulate(body,faces=body.faces[:])
    print('[bastion] hollow shell',len(body.verts),len(body.faces),body.calc_volume(),flush=True)
    portal=[ENTRY_RESIZE@Vector((x,-6.70,z)) for x,z in portal_outline(.30)]
    body=mach(body,subtract=[(portal,(0,1,0),1.2)])
    print('[bastion] portal cut',len(body.verts),len(body.faces),flush=True)
    # Front and side observation belts; the rear stays an uninterrupted
    # load-bearing pressure bulkhead for the lift machinery.
    windows=[]
    for side in (0,1,3):
        m=Matrix.Rotation(side*math.pi/2,4,'Z')@common.frame((0,-6.7,5.53),(0,-1,0),(0,0,1))
        windows.append(m)
    body=mach(body,subtract=[([m@Vector(p) for p in common.outline(10.30,1.60,.035,0)],tuple(m.to_3x3()@Vector((0,0,1))),.8) for m in windows])
    # Wall surrounds have one consistent finish. Black belongs to separate
    # manufactured armor and trim, never positional classification of walls.
    for z in (7.70,):
        bmesh.ops.bisect_plane(body,geom=[*body.verts,*body.edges,*body.faces],dist=1e-7,
                              plane_co=(0,0,z),plane_no=(0,0,1))
    emit(k,body,PRI,'continuous hollow bastion pressure shell')
    manufactured=k.bm.faces.layers.int.get('manufactured_part')
    for face in k.bm.faces:
        if face[manufactured]!=len(k.parts)-1:continue
        if all(v.co.z>=7.70-1e-6 for v in face.verts):face.material_index=kit.SLOTS.index(FRM)
        assert face.material_index==kit.SLOTS.index(FRM if min(v.co.z for v in face.verts)>=7.70-1e-6 else PRI)
    deck=profile([(13.0,1.4,4.08),(13.0,1.4,UPPER)])
    deck=mach(deck,boxes=[cutbox((a[0],a[1],4.0),(b[0],b[1],4.5)) for a,b in FLOOR_OPENINGS])
    emit(k,deck,SEC,'load-bearing upper deck with rear cargo aperture')
    for side,m in enumerate(windows):
        with k.frame(m):
            seat(k,common.ring(10.56,1.94,.045,10.30,1.60,.035,0,.085),SEC,'continuous recessed panoramic belt retainer')
            emit(k,loft([(10.30,1.60,.035,.036),(10.30,1.60,.035,.044)]),GLASS,'seated continuous bastion observation glazing')
            for x in (-1.717,1.717):
                emit(k,block((x-.045,-.97,.085),(x+.045,.97,.16)),SEC,'observation belt load mullion on upper and lower lands')
            for a,b in ((Vector((-5.08,-.85,.105)),Vector((-1.81,.85,.105))),(Vector((1.81,-.85,.105)),Vector((5.08,.85,.105)))):
                n=Vector((-(b-a).y,(b-a).x,0)).normalized()*.045
                emit(k,kit.prism_bm([a-n,b-n,b+n,a+n],.04,(0,0,1)),SEC,'diagonal glazing brace seated on both horizontal rails')

    structural_frame(k)

def band(k,label,z0,z1,width):
    outer=profile([(width,1.6,z0),(width,1.6,z1)])
    def sw(z):
        if z<2.98:return 13.8
        if z<=6.98:return 13.4
        if z<7.94:return 13.4-(z-6.98)*.8/.96
        return 12.6
    levels=[z0-.01,z1+.01]
    for z in (6.98,7.94):
        if z0<z<z1:levels.append(z)
    inside=profile([(sw(z)+.001,1.4,z) for z in sorted(levels)])
    outer=boolean_bm(outer,inside,'DIFFERENCE')
    bmesh.ops.triangulate(outer,faces=outer.faces[:])
    portal=[ENTRY_RESIZE@Vector((x,-6.70,z)) for x,z in portal_outline(.30)]
    outer=mach(outer,subtract=[(portal,(0,1,0),1.8)])
    if label=='foundation load ring':
        outer=mach(outer,boxes=[cutbox((-RAMP_WIDTH/2,-7.51,-.01),(RAMP_WIDTH/2,-6.895,GROUND+.001))])
    emit(k,outer,SEC,label)

def structural_frame(k):
    # Three genuine load-transfer members, not decorative strips. The columns
    # stop at their horizontal seating planes, before the crown's chamfer.
    band(k,'foundation load ring',0,.56,14.7)
    band(k,'upper floor transfer ring',3.64,3.94,14.4)
    crown=profile([(14.4,1.6,6.94),(14.4,1.6,7.12),(14.4-.3*1.3/.94,1.6-.3*.2/.94,7.42),(13.1,1.4,8.06),(13.1,1.4,8.22)])
    void=profile([(13.401,1.4,6.93),(13.401,1.4,6.98),(12.601,1.4,7.94),(12.601,1.4,8.23)])
    crown=boolean_bm(crown,void,'DIFFERENCE')
    for z in (7.12,7.42):
        bmesh.ops.bisect_plane(crown,geom=[*crown.verts,*crown.edges,*crown.faces],dist=1e-7,plane_co=(0,0,z),plane_no=(0,0,1))
    # Exact Boolean cuts can perturb the broad planar lands by a few microns.
    # Restore their design plane before fitting the removable crown cassettes.
    for v in crown.verts:
        if 7.12-1e-6<=v.co.z<=8.06+1e-6:
            r=7.2-(v.co.z-7.12)*.65/.94
            for axis in (0,1):
                if abs(abs(v.co[axis])-r)<.0001:v.co[axis]=math.copysign(r,v.co[axis])
    emit(k,crown,SEC,'lofted roof compression collar with planar column seats')
    layer=k.bm.faces.layers.int.get('manufactured_part')
    for f in k.bm.faces:
        if f[layer]!=len(k.parts)-1:continue
        if min(v.co.z for v in f.verts)>=7.42-1e-6:f.material_index=kit.SLOTS.index(FRM)
        elif min(v.co.z for v in f.verts)>=7.12-1e-6:f.material_index=kit.SLOTS.index(PRI)
    # Four broad corner armor ribs follow the chamfered pressure hull, ending
    # in full-width bolted load lands. No laboratory-style mid-face columns.
    for side in range(4):
        with k.frame(Matrix.Rotation(side*math.pi/2,4,'Z')):
            for label,z0,z1 in (('ground',.56,3.64),('upper',3.94,6.94)):
                rows=[]
                for z,w,d in ((z0,1.6,.46),(z0+.12,1.6,.46),(z0+.24,1.4,.30),(z1-.24,1.4,.30),(z1-.12,1.6,.46),(z1,1.6,.46)):
                    q=6.2 if label=='ground' and z<=2.98 else 6.2-(min(z,3.62)-2.98)*.2/.64 if label=='ground' else 6.0
                    m=Matrix.Translation((q,q,z))@Matrix.Rotation(-math.pi/4,4,'Z')
                    rows.append([m@Vector((x,y+d/2,0)) for x,y,_ in common.outline(w,d,.045,0)])
                seat(k,kit.loft_rings(rows),SEC,'broad corner rib with integral foundation and transfer flanges')
                for z in (z0+.06,z1-.06):
                    q=6.2 if label=='ground' and z<2.98 else 6.0
                    m=Matrix.Translation((q,q,z))@Matrix.Rotation(-math.pi/4,4,'Z')
                    for x in (-.31,.31):
                        seat(k,transform(rod((x,.46,0),(x,.478,0),.025,6),m),JNT,'corner rib captive flange stud')

def part_from(bm,label):
    bm.verts.ensure_lookup_table()
    for i,v in enumerate(bm.verts):v.index=i
    p=kit.Part(ROOT,label,[v.co.copy() for v in bm.verts],[tuple(v.index for v in f.verts) for f in bm.faces],False)
    bm.free();return p

def foundation(k):
    # Foundation includes the clear approach, with no raised door threshold.
    pad=profile([(13.8,1.4,0),(13.8,1.4,GROUND)])
    ramp=kit.prism_bm([(0,-7.5,0),(0,-6.9,0),(0,-6.9,GROUND)],RAMP_WIDTH,(1,0,0))
    pad=boolean_bm(pad,ramp,'UNION')
    pad=mach(pad,boxes=[cutbox((a[0],a[1],.08),(b[0],b[1],GROUND+.01)) for a,b in FLOOR_OPENINGS])
    emit(k,pad,SEC,'metallic foundation surface and integral clear entrance approach')

def lift(k):
    # Open flat 3 x 3 m deck. Its crosshead and yoke are integral understructure.
    platform=block((-1.5,2.4,.12),(1.5,5.4,GROUND))
    adds=[block((-2.12,5.40,.12),(2.12,5.90,.27)),
          block((-2.12,5.48,.26),(2.12,5.90,.55))]
    platform=mach(platform,union=adds,
                  boxes=[((x,LIFT_Y,GROUND),(.025,2.55,.012)) for x in (-1.2,-.6,0,.6,1.2)])
    emit(k,platform,SEC,'cargo deck and integral rear lift crosshead','CargoLift')
    # Two anchored guide rails; matching C-shaped slide blocks behind the deck.
    for s in (-1,1):
        x=s*2.36
        seat(k,block((x-.13,5.68,.08),(x+.13,5.96,5.8)),JNT,'continuous anchored cargo guide rail')
        foot=block((x-.30,5.48,.08),(x+.30,6.40,.12))
        seat(k,foot,SEC,'guide rail foundation flange')
        head=mach(block((x-.22,5.70,5.64),(x+.22,6.70,5.80)),
                  cuts=[((s*1.77,6.16,5.63),(s*1.77,6.16,5.81),.222,12)])
        full_land(k,'continuous hollow bastion pressure shell',
                  [(xx,6.50,zz) for xx in (x-.22,x+.22) for zz in (5.64,5.80)],(0,1,0))
        seat(k,head,SEC,'guide top bracket to rear bulkhead')
        for y in (5.55,6.26):seat(k,rod((x,y,.12),(x,y,.135),.035,6),JNT,'guide foundation anchor bolt')
        runner=mach(block((x-.25,5.58,.15),(x+.25,6.06,.55)),boxes=[cutbox((x-.131,5.679,.14),(x+.131,5.961,.56))])
        seat(k,runner,FRM,'C slide shoe embracing vertical guide','CargoLift')
        # Fixed shafts with enclosed powered nut carriages: no telescopic stages.
        cx=s*1.77;cy=6.16
        seat(k,block((cx-.22,cy-.22,.08),(cx+.22,cy+.22,.14)),SEC,'shaft foundation bearing pedestal')
        emit(k,rod((cx,cy,.14),(cx,cy,5.62),.08,12),JNT,'continuous fixed lift shaft')
        full_land(k,'continuous hollow bastion pressure shell',
                  [(xx,6.50,zz) for xx in (cx-.20,cx+.20) for zz in (5.62,5.76)],(0,1,0))
        seat(k,block((cx-.20,6.02,5.62),(cx+.20,6.70,5.76)),SEC,'shaft end bearing bracket to rear bulkhead')
        carriage=mach(block((cx-.18,5.90,.27),(cx+.18,6.38,.57)),
                   cuts=[((cx,cy,.26),(cx,cy,.58),.083,12)])
        seat(k,carriage,FRM,'enclosed powered nut carriage attached to crosshead','CargoLift')
        for dx in (-.14,.14):
            for dy in (-.14,.14):
                seat(k,rod((cx+dx,cy+dy,.14),(cx+dx,cy+dy,.155),.023,6),JNT,'shaft bearing foundation bolt')
    # Landing-edge guards flank the hole but leave the front landing unobstructed.
    for s in (-1,1):
        x=s*1.68
        guard=mach(block((x-.045,2.40,UPPER),(x+.045,5.30,UPPER+1.08)),
                   boxes=[((x,3.85,UPPER+.51),(.12,2.44,.85))])
        seat(k,guard,SEC,'upper landing welded side guard')

def roof_services(k):
    # Distinct stepped crown: forward beveled armor pods and a longitudinal
    # equipment shroud with flanged rear pressure-return headers.
    slope=(14.4-13.1)/2/(8.06-7.12)
    for side in range(4):
        for x in (-4.2,0,4.2):
            z=7.72;y=-(14.4/2-(z-7.12)*slope)
            rot=Matrix.Rotation(side*math.pi/2,4,'Z')
            m=rot@common.frame((x,y,z),(0,-1,slope),(0,slope,1))
            width=2.20 if x==0 else 1.40;height=.40
            # Every back corner lies on the uninterrupted sloped crown flat.
            full_land(k,'lofted roof compression collar with planar column seats',
                         [m@Vector((u,v,0)) for u in (-width/2+.06,width/2-.06) for v in (-height/2+.04,height/2-.04)],
                         tuple(m.to_3x3()@Vector((0,0,1))))
            # 2 micron assembly tolerance avoids rounded float coordinates
            # classifying a tangent interface as a solid penetration.
            m.translation+=m.to_3x3()@Vector((0,0,.000002))
            with k.frame(m):
                panel=mach(loft([(width,height,.04,0),(width-.08,height-.08,.025,.055)]),
                           boxes=[((0,0,.055),(width-.28,.15,.035))])
                seat(k,panel,SEC,'formed crown cassette with full flat seating back')
                seat(k,block((-(width-.284)/2,-.073,.037502),((width-.284)/2,.073,.049)),FRM if x==0 else EMI,'recessed crown ventilation back' if x==0 else 'flush crown navigation strip')
                if x==0:
                    for h in (-.050,0,.050):
                        emit(k,block((-(width-.28)/2,h-.008,.049),((width-.28)/2,h+.008,.055)),JNT,'crown grille blade seated between pocket sidewalls')
    for x in (-POD_X,POD_X):
        y=POD_Y
        housing=offset(loft([(3.20,3.80,.25,8.22),(3.20,3.80,.25,8.40),(2.78,3.38,.20,8.72)]),x=x,y=y)
        housing=mach(housing,boxes=[((x,y-1.90,8.31),(2.40,.12,.08))])
        emit(k,housing,FRM,'lofted forward roof armor pod with recessed signal aperture')
        seat(k,block((x-1.198,y-1.895,8.272),(x+1.198,y-1.84,8.348)),EMI,'recessed crown signal bar')
        bonnet=kit.loft_rings([[(x+r*math.cos(i*math.tau/10),y+r*math.sin(i*math.tau/10),z) for i in range(10)] for r,z in ((.72,8.72),(.72,8.84),(.53,9.12),(.38,9.19))])
        emit(k,bonnet,SEC,'sealed forward pressure bonnet on roof pod')
    with k.frame(Matrix.Translation((HEADER_X,HEADER_Y,8.22))):
        emit(k,loft([(4.2,3.4,.22,0),(4.2,3.4,.22,.12),(3.9,3.1,.16,.35)]),SEC,'rear header skid with continuous roof seating foot')
        for x in (-1.10,0,1.10):
            pts=[(x,-.80,.35),(x,-.80,1.18),(x,-.58,1.48),(x,.55,1.48),(x,.80,1.18),(x,.80,.35)]
            rings=[]
            for i,p in enumerate(pts):
                tangent=Vector(pts[min(i+1,len(pts)-1)])-Vector(pts[max(0,i-1)])
                basis=tangent.to_track_quat('Z','Y').to_matrix()
                rings.append([Vector(p)+basis@Vector((.18*math.cos(j*math.tau/8),.18*math.sin(j*math.tau/8),0)) for j in range(8)])
            emit(k,kit.loft_rings(rings),JNT,'formed flanged rear pressure return header')
            for y in (-.80,.80):
                seat(k,rod((x,y,.35),(x,y,.45),.29,8),FRM,'pressure header terminal flange on bolted skid')
                for dx in (-.23,.23):
                    emit(k,rod((x+dx,y,.45),(x+dx,y,.466),.022,6),JNT,'pressure header flange retained stud')
    x,y=BONNET_X,BONNET_Y
    emit(k,kit.loft_rings([[(x+r*math.cos(i*math.tau/12),y+r*math.sin(i*math.tau/12),z) for i in range(12)] for r,z in ((1.35,8.22),(1.35,8.37),(1.04,8.90),(.75,9.02))]),SEC,'large rear sealed extraction bonnet')
    with k.frame(Matrix.Translation((0,CONTROLLER_Y,8.22))):
        body=mach(loft([(1.75,2.1,.15,0),(1.75,2.1,.15,.40),(1.4,1.75,.12,.65)]),
                  boxes=[((0,-1.045,.19),(1.10,.12,.15))])
        emit(k,body,PRI,'roof telemetry enclosure seated directly on roof')
        brow=mach(block((-.548,-1.049,.117),(.548,-.985,.263)),
                  cuts=[((x,-1.06,.19),(x,-.98,.19),.063,8) for x in (-.27,.27)])
        emit(k,brow,FRM,'flush telemetry optical bezel with paired bored lens seats')
        for x in (-.27,.27):
            emit(k,rod((x,-1.04,.19),(x,-.985,.19),.062,8),EMI,'telemetry recessed optical lens')
        emit(k,rod((0,.55,.65),(0,.55,1.35),.035,6),JNT,'roof telemetry antenna seated in controller boss')
    # Bolted bonnets are closed pressure casings. Axial stiffening ribs are
    # machined against their curved shells, so both ends terminate flush.
    for x,y,r,z0,z1 in ((-POD_X,POD_Y,.72,8.84,9.12),(POD_X,POD_Y,.72,8.84,9.12),(BONNET_X,BONNET_Y,1.35-.10*.31/.53,8.47,8.90)):
        top=r-.19 if r<1 else 1.04
        for i in range(6):
            a=i*math.tau/6
            outward=Vector((math.cos(a),math.sin(a),0))
            lateral=Vector((-math.sin(a),math.cos(a),0))*.035
            q0=Vector((x,y,z0))+outward*r
            q1=Vector((x,y,z1))+outward*top
            bm=kit.loft_rings([[q-lateral-outward*.08,q+lateral-outward*.08,
                               q+lateral+outward*.045,q-lateral+outward*.045] for q in (q0,q1)])
            seat(k,bm,SEC,f'pressure bonnet machined radial stiffener {x} {i}')


def authored_entrance(k):
    outer=portal_outline(.30)
    inner=portal_outline()
    # Extend the cutter below the deck: the collar is an inverted U, no sill.
    clear=[(x,GROUND-.02 if abs(z-GROUND)<1e-6 else z) for x,z in inner]
    collar=kit.loft_rings([[(x,y,z) for x,z in portal_outline(d)]
                          for d,y in ((.30,-6.50),(.30,-6.98),(.22,-7.10))])
    collar=mach(collar,subtract=[([(x,-6.8,z) for x,z in clear],(0,1,0),1.0)])
    seat(k,collar,SEC,'single entrance formed pressure collar with full-depth planar jamb lands')
    leaf_outline=[(x-math.copysign(.008,x),z+.008 if z==GROUND else z-.008) for x,z in inner]
    leaf=portal_prism(leaf_outline,-6.53,-6.37)
    fm=common.frame((0,-6.53,1.76),(0,-1,0),(0,0,1))
    leaf=mach(leaf,union=[],subtract=[([fm@Vector(p) for p in common.outline(.86,2.05,.16,-.006)],tuple(fm.to_3x3()@Vector((0,0,1))),.052)])
    emit(k,leaf,JNT,'single full-height chamfered pressure-door casting','Door')
    with k.frame(fm):
        # 2 mm perimeter clearance; insert back lands on the machined pocket.
        emit(k,loft([(.856,2.046,.158,-.032),(.78,1.97,.14,-.018)]),JNT,'recessed full-height single door armor insert','Door')
        # Status window has its own through pocket in a separately bolted bezel.
        bezel=mach(loft([(.46,.15,.025,0),(.42,.11,.02,.026)]),boxes=[((0,0,.026),(.28,.038,.022))])
        transform(bezel,Matrix.Translation((0,1.23,0)))
        emit(k,bezel,SEC,'door status bezel on uninterrupted upper leaf land','Door')
        emit(k,block((-.138,1.212,.015),(.138,1.248,.024)),EMI,'flush single door status lens','Door')
        # Cast vertical pull, two integral feet. All backs on the leaf land.
        pull=mach(loft([(.14,.66,.035,0),(.14,.66,.035,.12),(.10,.62,.025,.14)]),
                  boxes=[((0,0,.045),(.18,.43,.15))])
        transform(pull,Matrix.Translation((-.65,-.03,0)))
        emit(k,pull,JNT,'glove-clear vertical pull with two integral mounting feet','Door')
        for z in (-.32,.26):
            emit(k,rod((-.65,z,.14),(-.65,z,.152),.021,6),JNT,'door pull retained mounting stud','Door')
    hx,hy,_=HINGE
    for z in (.82,1.77,2.72):
        # Full rectangles lie within x=1..1.3 and below the top chamfer.
        for a,b in ((z-.13,z-.042),(z+.042,z+.13)):
            full_land(k,'single entrance formed pressure collar with full-depth planar jamb lands',
                         [(x,-6.50,h) for x in (1.045,1.235) for h in (a,b)],(0,1,0))
            lug=mach(rod((hx,hy,a),(hx,hy,b),.065,8),
                     union=[block((1.045,-6.50,a),(1.235,hy,b))],
                     cuts=[((hx,hy,a-.01),(hx,hy,b+.01),.0254,8)])
            seat(k,lug,SEC,'fixed bored hinge fork seated completely on interior jamb flat')
        tongue=kit.loft_rings([[(x,y,h) for x,y in ((.80,-6.37),(hx,-6.37),(hx,-6.315),(.80,-6.315))] for h in (z-.041,z+.041)])
        tongue=mach(tongue,union=[rod((hx,hy,z-.041),(hx,hy,z+.041),.062,8)],
                    cuts=[((hx,hy,z-.05),(hx,hy,z+.05),.0272,8)])
        seat(k,tongue,SEC,'integral offset door tongue and bored moving hinge eye','Door')
        emit(k,rod((hx,hy,z-.13),(hx,hy,z+.13),.025,8),JNT,'retained cylindrical hinge axle')
        for a,b in ((z-.142,z-.13),(z+.13,z+.142)):
            emit(k,rod((hx,hy,a),(hx,hy,b),.039,8),JNT,'hinge axle flush retention cap')
    # A geared drive is coaxial with the middle hinge. Its full rear foot
    # lands on the jamb, independent of the visible external door chamfer.
    drive=mach(rod((hx,hy,1.38),(hx,hy,1.60),.095,8),
               union=[block((1.015,-6.50,1.38),(1.255,hy,1.60))],
               cuts=[((hx,hy,1.37),(hx,hy,1.61),.0254,8)])
    full_land(k,'single entrance formed pressure collar with full-depth planar jamb lands',
                 [(x,-6.50,z) for x in (1.015,1.255) for z in (1.38,1.60)],(0,1,0))
    seat(k,drive,FRM,'coaxial door reduction drive and full jamb mounting flange')
    emit(k,rod((hx,hy,1.60),(hx,hy,1.628),.025,8),JNT,'retained drive output shaft to middle knuckle')
    # Upper shoot bolt, with guide barrel on the leaf and bored header lug.
    bx,by=-.65,-6.29
    barrel=mach(rod((bx,by,2.64),(bx,by,2.97),.055,8),
                union=[block((bx-.07,-6.37,2.64),(bx+.07,by,2.97))],
                cuts=[((bx,by,2.63),(bx,by,2.98),.0214,8)])
    emit(k,barrel,FRM,'powered shoot-bolt barrel with integral leaf saddle','Door')
    emit(k,rod((bx,by,2.70),(bx,by,3.28),.021,8),JNT,'single captive upper locking bolt','Lock')
    receiver=mach(rod((bx,by,3.23),(bx,by,3.31),.049,8),
                 union=[block((bx-.07,-6.50,3.23),(bx+.07,by,3.31))],
                 cuts=[((bx,by,3.22),(bx,by,3.32),.0214,8)])
    seat(k,receiver,SEC,'bored upper locking receiver on header flat')

def entrance(k):
    with k.frame(ENTRY_RESIZE):authored_entrance(k)


def joints_and_actions():
    specs=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    specs.extend([('Door',ROOT,'hinge',ENTRY_RESIZE@Vector(HINGE),(0,0,1),(0,1,0),(-105,0)),
                  ('Lock','Door','slide',ENTRY_RESIZE@Vector((-.65,-6.29,2.7)),(0,0,1),(0,0,1),(-.12*ENTRY_RESIZE[2][2],0))])
    keys={'Door':[(0,0),(21,0),(81,-105),(96,-105)],'Lock':[(0,0),(15,-.12*ENTRY_RESIZE[2][2]),(96,-.12*ENTRY_RESIZE[2][2])]}
    specs.append(('CargoLift',ROOT,'slide',(0,LIFT_Y,GROUND),(0,0,1),(0,0,1),(0,STROKE)))
    up={'CargoLift':[(0,0),(12,0),(84,STROKE),(96,STROKE)]}
    zero={bn:[(0,0),(96,0)] for bn,*_ in specs if bn!=ROOT}
    def complete(ks):return {**zero,**ks}
    kit.JOINT_SPECS=specs;kit.GROUPS=()
    kit.ANIMATIONS={'open':(False,'BEZIER',complete(keys)),
      'close':(False,'BEZIER',complete({bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in keys.items()})),
      'lift_up':(False,'BEZIER',complete(up)),
      'lift_down':(False,'BEZIER',complete({bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in up.items()}))}
    return kit.resolve_joints()

def check_roof_layout(k):
    pods=[p for p,t in zip(k.parts,common.LABELS) if t=='lofted forward roof armor pod with recessed signal aperture']
    left,right=sorted(pods,key=lambda p:p.lo.x)
    centre=next(p for p,t in zip(k.parts,common.LABELS) if t=='roof telemetry enclosure seated directly on roof')
    header=next(p for p,t in zip(k.parts,common.LABELS) if t=='rear header skid with continuous roof seating foot')
    bonnet=next(p for p,t in zip(k.parts,common.LABELS) if t=='large rear sealed extraction bonnet')
    gaps=[left.lo.x+ROOF_HALF,centre.lo.x-left.hi.x,right.lo.x-centre.hi.x,ROOF_HALF-right.hi.x]
    assert all(abs(g-ROOF_GAP)<1e-5 for g in gaps),('unequal front row gaps',gaps)
    assert all(abs(p.lo.y-FRONT_LINE)<1e-5 for p in (left,centre,right)), 'front baseline'
    assert all(abs(p.hi.y-REAR_LINE)<1e-5 for p in (header,bonnet)), 'rear baseline'
    assert abs(header.lo.x+ROOF_HALF-ROOF_GAP)<1e-5 and abs(ROOF_HALF-bonnet.hi.x-ROOF_GAP)<1e-5
    assert abs(centre.lo.z-8.22)<1e-5 and not any(t=='continuous longitudinal roof equipment shroud' for t in common.LABELS)

def split(body):
    result=[]
    predicates=[('Shell',lambda b,m,y:b==ROOT and m==PRI),('FrameFront',lambda b,m,y:b==ROOT and m==SEC and y<=0),
       ('FrameRear',lambda b,m,y:b==ROOT and m==SEC and y>0),
       ('Services',lambda b,m,y:b==ROOT and m not in (PRI,SEC)),('Mechanisms',lambda b,m,y:b!=ROOT)]
    for tag,predicate in predicates:
        obj=body.copy();obj.data=body.data.copy();obj.name='SK_'+TITLE+tag;bpy.context.scene.collection.objects.link(obj)
        bm=bmesh.new();bm.from_mesh(obj.data);weights=bm.verts.layers.deform.active
        discard=[f for f in bm.faces if not predicate(obj.vertex_groups[next(iter(f.verts[0][weights].keys()))].name,obj.data.materials[f.material_index].name,f.calc_center_median().y)]
        bmesh.ops.delete(bm,geom=discard,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free();result.append(obj)
    data=body.data;bpy.data.objects.remove(body,do_unlink=True);bpy.data.meshes.remove(data)
    assert all(kit.triangles(o)<=5000 for o in result),{o.name:kit.triangles(o) for o in result}
    return result

def main():
    import perimeter_surface as surface
    common.CORNER_STEPS=1
    if '--surface-only' in sys.argv:
        door.HERE=HERE;door.NAME=NAME
        surface.refresh(HERE,NAME,kit,xy(14.7,1.6,0),4.3,
            lambda rig,meshes,markers:door.export_runtime(rig,[*meshes,*markers],prepared=True),subdivisions=4)
        return
    if '--exports-only' in sys.argv:
        bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
        report=json.loads((HERE/f'{NAME}_rig.json').read_text())
        kit.SLOTS=report['materials']
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        objects=[o for o in bpy.context.scene.objects if o.type in ('MESH','EMPTY')]
        door.HERE=HERE;door.NAME=NAME;door.export_runtime(rig,objects,prepared=True)
        return
    common.CORNER_STEPS=1;common.LABELS.clear();kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.015,.62,.68),0,.34,2)
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0);surface.configure(kit);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    bs=bpy.data.materials[GLASS].node_tree.nodes.get('Principled BSDF')
    bs.inputs['Alpha'].default_value=.10
    bpy.data.materials[GLASS].diffuse_color=(0,0,0,.10)
    bpy.data.materials[GLASS].surface_render_method='DITHERED'
    joints=joints_and_actions();rig=kit.build_rig(joints,[]);k=kit.Kit()
    foundation(k);shell(k);lift(k);roof_services(k)
    entrance(k)
    check_roof_layout(k)
    for p,label in zip(k.parts,common.LABELS):p.line=label
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps([dict(label=t,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces) for p,t in zip(k.parts,common.LABELS)]))
    pairs=common.exact_intersections(k)
    kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    kit.check_motion(k,joints,states)
    for _,state in states:
        matrices=kit.fk(joints,state)
        for p in k.parts:
            for v in p.verts:
                q=matrices[p.bone]@v
                assert abs(q.x)<=7.50001 and abs(q.y)<=7.50001 and q.z>=-.00001,('moving envelope',p.line,list(q))
    obj=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(obj,rig)
    sys.path.insert(0,str(MODELS/'architecture/lunar_dome'))
    from surface_audit import check_coplanar
    # Audit after part-count diagnostics below.
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if all(abs(v.co.z)<1e-6 for v in f.verts) and f.normal.z<-.5],context='FACES_ONLY')
    bm.to_mesh(obj.data);bm.free()
    bm=bmesh.new();bm.from_mesh(obj.data);layer=bm.faces.layers.int.get('manufactured_part')
    counts={}
    for f in bm.faces:
        label=common.LABELS[f[layer]];counts[label]=counts.get(label,0)+len(f.verts)-2
    bm.free()
    print('[bastion] optimised part counts',sorted(counts.items(),key=lambda p:-p[1])[:18],flush=True)
    check_coplanar(obj)
    tris=kit.triangles(obj);print(f'[{NAME}] triangles {tris}',flush=True);assert tris<=BUDGET,(tris,BUDGET)
    meshes=split(obj)
    meshes.append(surface.create(rig,xy(14.7,1.6,0),RAMP_WIDTH+.2,subdivisions=4))
    tris=sum(kit.triangles(o) for o in meshes);assert tris<=BUDGET
    pose_open={'Door':{'rot':[-105,0,0]},'Lock':{'loc':[0,-.12,0]}}
    upper={'CargoLift':{'loc':[0,4,0]}}
    rig['preview_poses']=json.dumps({'open':pose_open,'lift_upper':{**pose_open,**upper}})
    scene=bpy.context.scene;scene['preview_actions']=json.dumps(['open','close','lift_up','lift_down'])
    scene['showcase_frame']=json.dumps(dict(lo=[-7.5,-7.5,0],hi=[7.5,7.5,10.10]))
    # Door export routine applies unique material atlases and native axis conventions.
    ceiling=[(level+tag,(x,y,z),(0,0,1)) for level,z in [('Ground',2.8),('Upper',6.5)]
             for tag,x,y in [('FrontLeft',-3.2,-2.4),('FrontRight',3.2,-2.4),('RearLeft',-3.2,2.4),('RearRight',3.2,2.4)]]
    wall=[('GroundLeft',(0,0,2.2),(1,0,0)),('GroundRight',(0,0,2.2),(-1,0,0)),
          ('UpperLeft',(0,0,6.6),(1,0,0)),('UpperRight',(0,0,6.6),(-1,0,0))]
    markers,gizmos=door.light_mounts.install(rig,meshes,ceiling,wall)
    door.HERE=HERE;door.NAME=NAME;door.export_runtime(rig,meshes+markers)
    hole_area=3.04*3.04+5.3*1.10-3.04*.02
    area=13.0**2-2*1.4**2-hole_area
    assert area>=144
    report=dict(name=NAME,triangles=tris,triangle_budget=BUDGET,meshes={o.name:kit.triangles(o) for o in meshes},
        bounds_m=dict(lo=[min(v.co[i] for o in meshes for v in o.data.vertices) for i in range(3)],
                      hi=[max(v.co[i] for o in meshes for v in o.data.vertices) for i in range(3)]),materials=kit.SLOTS,
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},gizmos=gizmos,
        placement_envelope_m=[15,15],surrounding_platform=True,upper_floor_m=dict(width=13.0,depth=13.0,usable_area=area,elevation=UPPER),
        cargo_lift_m=dict(width=3,depth=3,travel=STROKE,lower=GROUND,upper=UPPER,center=[0,LIFT_Y]),
        passage_m=dict(width=ENTRY_WIDTH,height=ENTRY_TOP-GROUND,ramp_width=RAMP_WIDTH,single_leaf=True),
        roof_layout_m=dict(edge_margin=ROOF_GAP,front_row_gap=ROOF_GAP,front_baseline=FRONT_LINE,rear_baseline=REAR_LINE,controller_direct_roof=True),
        rear_bulkhead=dict(solid=True,inner_y=6.50,outer_y=6.70,lift_mounts_full_land=True),
        trigger=dict(object='SK_BastionLiftPlatformTrigger',bone='CargoLift',role='occupancy area; not a solid blocker'),
        checks=dict(exact_solid_pairs=pairs,connectivity=True,motion_states=len(states),coplanar=True,full_ground_sweep=True,full_hinge_and_crown_flange_lands=True,paint_boundaries_geometrically_split=True),
        placement='ground centre; front -Y; up +Z; library only; game integration deferred')
    surface.update_report(report,meshes,kit)
    dimensions.report(NAME,report,width=1.5,height=2.1/dimensions.HEIGHT[NAME],floors=[GROUND,UPPER],ceilings=[4.08,7.70])
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles; upper usable floor {area:.3f} m2',flush=True)

if __name__=='__main__':main()
