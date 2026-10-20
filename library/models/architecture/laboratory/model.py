"""Duplex industrial laboratory. Headless Blender 5.2; library-only source.

All dimensions, seams, hydraulic strokes and animations derive from this spec.
The pressure-door mechanism reuses the library's audited industrial door kit.
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
spec=importlib.util.spec_from_file_location('laboratory_door_kit',HERE.parent/'hangar/model.py')
door=importlib.util.module_from_spec(spec);spec.loader.exec_module(door)
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
ROOT,PRI,SEC,FRM,JNT,EMI=common.ROOT,common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
GLASS='M_Glass'
NAME,TITLE='laboratory','Laboratory'
BUDGET=15000
GROUND=.32
UPPER=4.32
STROKE=UPPER-GROUND
SHAFT=(-2.65,2.65,2.38,6.5)
FLOOR_OPENINGS=[((-1.52,2.38),(1.52,5.42)),((-2.65,5.40),(2.65,6.50))]
LIFT_Y=3.9
door.ENTRY_RESIZE=dimensions.entry_frame((0,door.ENTRY,door.DECK),2/4.6,(2.1/3.48)/dimensions.HEIGHT[NAME])
ENTRY_FRAME=Matrix.Translation((0,-6.90+door.ENTRY,GROUND-door.DECK))@Matrix.Diagonal((-1,-1,1,1))@door.ENTRY_RESIZE
RAMP_WIDTH=2*max(abs(x) for x,z in door.portal_offset(.59) if abs(z-door.DECK)<1e-7)*door.ENTRY_RESIZE[0][0]
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
        if label in ('formed continuous perimeter load belt','bored pipe saddle with wall foot','formed footing-to-crown structural rib'):
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

def shell(k):
    # One continuous pressure shell, including formed shoulders and crown.
    body=profile([(13.8,.65,GROUND),(13.8,.65,2.98),(13.4,.65,3.62),
                  (13.4,.65,6.98),(12.6,.65,7.94),(12.6,.65,8.22)])
    # Parallel inner/outer corner profiles retain real wall thickness on every
    # chamfer. A smaller inner chamfer can break through the narrowed storey.
    room=profile([(13.0,.65,GROUND-.01),(13.0,.65,6.98),(12.05,.65,7.70)])
    # A true hollow duplex room; the upper slab is fitted independently below.

    body=boolean_bm(body,room,'DIFFERENCE')
    bmesh.ops.triangulate(body,faces=body.faces[:])
    print('[laboratory] hollow shell',len(body.verts),len(body.faces),body.calc_volume(),flush=True)
    portal=[ENTRY_FRAME@Vector((x,-2.24,z)) for x,z in door.portal_offset(.59)]
    body=mach(body,subtract=[(portal,(0,1,0),1.2)])
    print('[laboratory] portal cut',len(body.verts),len(body.faces),flush=True)
    # Three panoramic observation bays: real through-shell windows, not black decals.
    windows=[]
    for side in ('front','left','right'):
        for t in (-3.5,0,3.5):
            m=common.frame((t,-6.7,5.53),(0,-1,0),(0,0,1)) if side=='front' else common.frame((6.7 if side=='left' else -6.7,t,5.53),(1 if side=='left' else -1,0,0),(0,0,1))
            windows.append((side,t,m))
    apertures=[([m@Vector(p) for p in common.outline(2.8,1.55,.14,0)],tuple(m.to_3x3()@Vector((0,0,1))),.8) for _,_,m in windows]
    body=mach(body,subtract=apertures)
    bmesh.ops.triangulate(body,faces=body.faces[:])
    body=mach(body,subtract=[([Vector((px+x,py,z)) for px,py,z in common.outline(2.352,4.502,.161,8.20)],(0,0,1),.20) for x in (-1.65,1.65)])
    print('[laboratory] observation cuts',len(body.verts),len(body.faces),flush=True)
    emit(k,body,PRI,'continuous hollow lofted pressure shell and crown')
    manufactured=k.bm.faces.layers.int.get('manufactured_part')
    for face in k.bm.faces:
        if face[manufactured]==len(k.parts)-1 and all(v.co.z>=7.70-1e-6 for v in face.verts):
            face.material_index=kit.SLOTS.index(SEC)
    deck=profile([(13.0,.65,4.08),(13.0,.65,UPPER)])
    deck=mach(deck,boxes=[cutbox((a[0],a[1],4.0),(b[0],b[1],4.5)) for a,b in FLOOR_OPENINGS])
    emit(k,deck,SEC,'load-bearing upper deck with rear cargo aperture')
    # Windows seat in retaining rims. Shared outlines prevent floating glazing.
    for side,t,m in windows:
        with k.frame(m):
            rim=common.ring(3.08,1.83,.20,2.78,1.53,.13,0,.085)
            seat(k,rim,SEC,f'{side} {t} machined observation bezel')
            glass=loft([(2.78,1.53,.13,.036),(2.78,1.53,.13,.044)])
            emit(k,glass,GLASS,f'{side} {t} seated observation glazing')
            for x in (-1.42,1.42):
                for y in (-.73,.73):emit(k,rod((x,y,.085),(x,y,.099),.025,6),JNT,'window retainer bolt')
    structural_frame(k)

def band(k,label,z0,z1,width):
    outer=profile([(width,.85,z0),(width,.85,z1)])
    def sw(z):
        if z<2.98:return 13.8
        if z<=6.98:return 13.4
        if z<7.94:return 13.4-(z-6.98)*.8/.96
        return 12.6
    levels=[z0-.01,z1+.01]
    for z in (6.98,7.94):
        if z0<z<z1:levels.append(z)
    inside=profile([(sw(z)+.001,.65,z) for z in sorted(levels)])
    outer=boolean_bm(outer,inside,'DIFFERENCE')
    bmesh.ops.triangulate(outer,faces=outer.faces[:])
    portal=[ENTRY_FRAME@Vector((x,-2.24,z)) for x,z in door.portal_offset(.59)]
    outer=mach(outer,subtract=[(portal,(0,1,0),1.8)])
    if label=='foundation load ring':
        outer=mach(outer,boxes=[cutbox((-RAMP_WIDTH/2,-7.51,-.01),(RAMP_WIDTH/2,-6.895,GROUND+.001))])
    emit(k,outer,SEC,label)

def structural_frame(k):
    # Three genuine load-transfer members, not decorative strips. The columns
    # stop at their horizontal seating planes, before the crown's chamfer.
    band(k,'foundation load ring',0,.56,14.7)
    band(k,'upper floor transfer ring',3.64,3.94,14.4)
    crown=profile([(14.4,.85,6.94),(14.4,.85,7.12),(13.1,.65,8.06),(13.1,.65,8.22)])
    void=profile([(13.401,.65,6.93),(13.401,.65,6.98),(12.601,.65,7.94),(12.601,.65,8.23)])
    crown=boolean_bm(crown,void,'DIFFERENCE')
    emit(k,crown,SEC,'lofted roof compression collar with planar column seats')
    interfaces=[('ground column',.56,3.64,-7.125,-6.95,'foundation load ring','upper floor transfer ring'),
                ('upper column',3.94,6.94,-6.95,-6.95,'upper floor transfer ring','lofted roof compression collar with planar column seats')]
    for side in range(4):
        with k.frame(Matrix.Rotation(side*math.pi/2,4,'Z')):
            for x in (-5.5,5.5):
                for label,lo,hi,yl,yh,lower,upper in interfaces:
                    rows=[]
                    stations=[(.92,.42,.055,lo,yl),(.92,.42,.055,lo+.07,yl),
                         (.68,.28,.035,lo+.07,yl)]
                    if label=='ground column':stations.append((.68,.28,.035,2.98,yl))
                    stations.extend([(.68,.28,.035,hi-.07,yh),
                         (.92,.42,.055,hi-.07,yh),(.92,.42,.055,hi,yh)])
                    for w,d,c,z,y in stations:
                        rows.append([(x+px,y+py,z) for px,py,_ in common.outline(w,d,c,0)])
                    beam=kit.loft_rings(rows)
                    # All four end-land corners must sit on horizontal load-ring
                    # flats; no end can overhang a slope or roof chamfer.
                    for host,y,z in ((lower,yl,lo),(upper,yh,hi)):
                        door.landing(k,host,[(x+dx,y+dy,z) for dx in (-.40,.40) for dy in (-.16,.16)],(0,0,1))
                    emit(k,beam,SEC,label+' machined column with integral end flanges')
                    for y,z,direction in ((yl,lo+.07,1),(yh,hi-.07,-1)):
                        for dx in (-.40,.40):
                            emit(k,rod((x+dx,y,z),(x+dx,y,z+direction*.016),.026,6),JNT,'column flange retained fastener on flat land')

def part_from(bm,label):
    bm.verts.ensure_lookup_table()
    for i,v in enumerate(bm.verts):v.index=i
    p=kit.Part(ROOT,label,[v.co.copy() for v in bm.verts],[tuple(v.index for v in f.verts) for f in bm.faces],False)
    bm.free();return p

def foundation(k):
    # Foundation includes the clear approach, with no raised door threshold.
    pad=profile([(13.8,.65,0),(13.8,.65,GROUND)])
    ramp=kit.prism_bm([(0,-7.5,0),(0,-6.9,0),(0,-6.9,GROUND)],RAMP_WIDTH,(1,0,0))
    pad=boolean_bm(pad,ramp,'UNION')
    pad=mach(pad,boxes=[cutbox((a[0],a[1],.08),(b[0],b[1],GROUND+.01)) for a,b in FLOOR_OPENINGS])
    emit(k,pad,SEC,'integral building floor slab and entrance ramp; no surrounding platform')

def inspection_outline(gap=0.0,z=0.0,width_scale=1.0):
    # Measure clearance after the front-panel narrowing and final height bake.
    # The diagonal's offset follows its transformed normal, like the flat edges.
    inverse_x=1.0/width_scale
    inverse_y=1.0/dimensions.HEIGHT[NAME]
    corner=.12+gap*(inverse_x+inverse_y-math.hypot(inverse_x,inverse_y))
    return common.outline(1.72+2*gap*inverse_x,.83+2*gap*inverse_y,corner,z)


def check_inspection_clearance(width_scale):
    from mathutils import Vector as V
    inner=[V((x*width_scale,y*dimensions.HEIGHT[NAME])) for x,y,_ in inspection_outline()]
    outer=[V((x*width_scale,y*dimensions.HEIGHT[NAME])) for x,y,_ in inspection_outline(.01,width_scale=width_scale)]
    for i in range(len(inner)):
        edge=inner[(i+1)%len(inner)]-inner[i]
        gap=abs(edge.cross(outer[i]-inner[i]))/edge.length
        assert abs(gap-.01)<1e-6,('inspection perimeter clearance',width_scale,i,gap)


def cladding(k):
    for side in range(4):
        rot=Matrix.Rotation(side*math.pi/2,4,'Z')
        # Broad lofted service shells with true recesses and flush light inserts.
        for x in (-3.5,3.5):
            check_inspection_clearance(.77 if side==0 else 1.0)
            panel_x=math.copysign(3.98,x) if side==0 else x
            m=rot@common.frame((panel_x,-6.90,1.74),(0,-1,0),(0,0,1))
            if side==0:m=m@Matrix.Diagonal((.77,1,1,1))
            with k.frame(m):
                casing=loft([(2.46,2.20,.18,0),(2.46,2.20,.18,.08),(2.25,1.98,.15,.19)])
                pockets=[((0,.58,.20),(1.70,.065,.05))]
                casing=mach(casing,boxes=pockets)
                if side!=2:
                    opening=[Vector(p)+Vector((0,-.28,0)) for p in inspection_outline(.01,.20,.77 if side==0 else 1.0)]
                    casing=mach(casing,subtract=[(opening,(0,0,1),.055)])
                seat(k,casing,PRI,'formed recessed service armour cassette')
                emit(k,block((-.845,.549,.175),(.845,.611,.19)),EMI,'flush service status strip')
                if side!=2:emit(k,offset(loft([(1.72,.83,.12,.1725),(1.64,.75,.10,.185)]),y=-.28),SEC,'fitted service inspection cover')
                for xx in (-.94,.94):
                    for yy in (-.84,.84):seat(k,rod((xx,yy,.19),(xx,yy,.204),.026,6),JNT,'cassette captive flange bolt')
    # Rear process banks occupy real wall land, away from the room and shaft.
    for s in (-1,1):
        m=common.frame((s*3.6,6.7,5.48),(0,1,0),(0,0,1))
        with k.frame(m):
            seat(k,loft([(2.30,2.20,.15,0),(2.24,2.14,.13,.16)]),FRM,'rear process-bank mounting skid')
            for x in (-.68,0,.68):
                # Shouldered canister with coaxial formed end caps; welded foot lands.
                can=kit.loft_rings([[(r*math.cos(i*math.tau/8),r*math.sin(i*math.tau/8),z) for i in range(8)] for r,z in ((.23,0),(.27,.12),(.27,1.39),(.23,1.52))])
                # Vessel end profiles share one exact axis and two bored saddles.

                transform(can,common.frame((x,-.76,.43),(0,1,0),(0,0,1)))
                seat(k,can,PRI,'formed process accumulator vessel')
                for y in (-.66,.66):
                    support=mach(block((x-.28,y-.07,.16),(x+.28,y+.07,.55)),cuts=[((x,y-.09,.43),(x,y+.09,.43),.275,8)])
                    seat(k,support,SEC,'bored accumulator saddle and skid foot')
    # Service pipes have gland-box ends and bored wall-mounted saddles.
    for s in (-1,1):
        x=s*7.02
        for y in (-3.7,3.7):
            m=common.frame((s*6.80,y,3.22),(s,0,0),(0,0,1))
            with k.frame(m):seat(k,loft([(.24,.26,.025,0),(.24,.26,.025,.26)]),FRM,'sealed utility termination box')
        emit(k,rod((x,-3.58,3.22),(x,3.58,3.22),.027,8),JNT,'terminated stainless utility pipe')
        for y in (-3.58,0,3.58):
            support=mach(rod((x,y-.055,3.22),(x,y+.055,3.22),.048,8),
                union=[block((min(s*6.80,x),y-.055,3.15),(max(s*6.80,x),y+.055,3.29))],
                cuts=[((x,y-.06,3.22),(x,y+.06,3.22),.027,8)])
            seat(k,support,SEC,'bored pipe saddle with wall foot')

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
        seat(k,head,SEC,'guide top bracket to rear bulkhead')
        for y in (5.55,6.26):seat(k,rod((x,y,.12),(x,y,.135),.035,6),JNT,'guide foundation anchor bolt')
        runner=mach(block((x-.25,5.58,.15),(x+.25,6.06,.55)),boxes=[cutbox((x-.131,5.679,.14),(x+.131,5.961,.56))])
        seat(k,runner,FRM,'C slide shoe embracing vertical guide','CargoLift')
        # Fixed shafts with enclosed powered nut carriages: no telescopic stages.
        cx=s*1.77;cy=6.16
        seat(k,block((cx-.22,cy-.22,.08),(cx+.22,cy+.22,.14)),SEC,'shaft foundation bearing pedestal')
        emit(k,rod((cx,cy,.14),(cx,cy,5.62),.08,12),JNT,'continuous fixed lift shaft')
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
    """Bolted inspection covers and a supported, terminated conduit."""
    for x in (-1.65,1.65):
        with k.frame(Matrix.Translation((x,0,8.10))):
            hatch=mach(loft([(2.35,4.50,.16,0),(2.35,4.50,.16,.065),(2.28,4.43,.14,.12)]),
                       subtract=[(common.outline(2.05,4.10,.12,.13),(0,0,1),.10)])
            emit(k,hatch,SEC,'formed roof inspection flange with machined cover ledge')
            emit(k,loft([(2.048,4.098,.119,.08),(2.00,4.05,.11,.10)]),SEC,'flush fitted roof inspection cover')
            for xx in (-1.08,1.08):
                for yy in (-1.84,1.84):seat(k,rod((xx,yy,.12),(xx,yy,.132),.025,6),JNT,'roof cover captive fastener')
    for y in (-2.95,2.95):
        emit(k,offset(loft([(.26,.30,.04,8.22),(.26,.30,.04,8.40)]),y=y),FRM,'roof conduit sealed gland junction')
    emit(k,rod((0,-2.80,8.38),(0,2.80,8.38),.025,8),FRM,'terminated roof data conduit')
    for y in (-1.4,1.4):
        saddle=mach(block((-.075,y-.045,8.22),(.075,y+.045,8.42)),
                    cuts=[((0,y-.06,8.38),(0,y+.06,8.38),.026,8)])
        emit(k,saddle,SEC,'bored roof conduit saddle with flat welded foot')

def joints_and_actions():
    specs=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    keys={}
    for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):
        specs.extend([(bn,ROOT,'hinge',tuple(ENTRY_FRAME@Vector((s*door.HX,door.HY,1.89))),(0,0,1),(0,1,0),(0,105) if s==1 else (-105,0)),
           (bn+'Bolt',bn,'slide',tuple(ENTRY_FRAME@Vector((s*.37,-2.42,2.4))),(0,0,1),(0,0,1),(-.12*door.ENTRY_RESIZE[2][2],0))])
        keys[bn]=[(0,0),(21,0),(81,s*105),(96,s*105)]
        keys[bn+'Bolt']=[(0,0),(15,-.12*door.ENTRY_RESIZE[2][2]),(96,-.12*door.ENTRY_RESIZE[2][2])]
    specs.append(('CargoLift',ROOT,'slide',(0,LIFT_Y,GROUND),(0,0,1),(0,0,1),(0,STROKE)))
    up={'CargoLift':[(0,0),(12,0),(84,STROKE),(96,STROKE)]}
    zero={bn:[(0,0),(96,0)] for bn,*_ in specs if bn!=ROOT}
    def complete(ks):return {**zero,**ks}
    kit.JOINT_SPECS=specs;kit.GROUPS=()
    kit.ANIMATIONS={'open':(False,'BEZIER',complete(keys)),
      'close':(False,'BEZIER',complete({bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in keys.items()})),
      'lift_up':(False,'BEZIER',complete(up)),
      'lift_down':(False,'BEZIER',complete({bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in up.items()}))}
    from door_actions import independent_leaves
    independent_leaves(kit.ANIMATIONS,keys)
    return kit.resolve_joints()

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
        surface.refresh(HERE,NAME,kit,xy(14.7,.85,0),4.3,
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
    foundation(k);shell(k);cladding(k);lift(k);roof_services(k)
    with k.frame(ENTRY_FRAME):
        door.entry(k)
        for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):door.doors(k,s,bn)
    with k.frame(Matrix.Translation((0,-6.90-door.ENTRY,GROUND-door.DECK))@door.ENTRY_RESIZE):door.entry(k)
    # Laboratory-specific stainless finish. Shared hangar geometry remains
    # unchanged; recolor only the two articulated leaf castings and inlays.
    layer=k.bm.verts.layers.deform.active
    for face in k.bm.faces:
        bone=k.groups[next(iter(face.verts[0][layer].keys()))]
        if bone in ('LeftDoor','RightDoor') and face.material_index in (kit.SLOTS.index(PRI),kit.SLOTS.index(SEC)):
            face.material_index=kit.SLOTS.index(JNT)
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
    bm=bmesh.new();bm.from_mesh(obj.data)
    layer=bm.faces.layers.int['manufactured_part']
    hidden=[f for f in bm.faces if all(abs(v.co.z-GROUND*dimensions.HEIGHT[NAME])<1e-6 for v in f.verts) and common.LABELS[f[layer]] not in ('integral building floor slab and entrance ramp; no surrounding platform','cargo deck and integral rear lift crosshead')]
    bmesh.ops.delete(bm,geom=hidden,context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
    check_coplanar(obj)
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if all(abs(v.co.z)<1e-6 for v in f.verts) and f.normal.z<-.5],context='FACES_ONLY')
    bm.to_mesh(obj.data);bm.free()
    bm=bmesh.new();bm.from_mesh(obj.data);layer=bm.faces.layers.int.get('manufactured_part')
    counts={}
    for f in bm.faces:
        label=common.LABELS[f[layer]];counts[label]=counts.get(label,0)+len(f.verts)-2
    bm.free()
    print('[laboratory] optimised part counts',sorted(counts.items(),key=lambda p:-p[1])[:18],flush=True)
    tris=kit.triangles(obj);print(f'[{NAME}] triangles {tris}',flush=True);assert tris<=BUDGET,(tris,BUDGET)
    meshes=split(obj)
    meshes.append(surface.create(rig,xy(14.7,.85,0),4.3,subdivisions=4))
    tris=sum(kit.triangles(o) for o in meshes);assert tris<=BUDGET
    pose_open={'LeftDoor':{'rot':[105,0,0]},'RightDoor':{'rot':[-105,0,0]},'LeftDoorBolt':{'loc':[0,-.12,0]},'RightDoorBolt':{'loc':[0,-.12,0]}}
    upper={'CargoLift':{'loc':[0,4,0]}}
    rig['preview_poses']=json.dumps({'open':pose_open,'lift_upper':{**pose_open,**upper}})
    scene=bpy.context.scene;scene['preview_actions']=json.dumps(['open','close','lift_up','lift_down'])
    scene['showcase_frame']=json.dumps(dict(lo=[-7.5,-7.5,0],hi=[7.5,7.5,8.42]))
    # Door export routine applies unique material atlases and native axis conventions.
    ceiling=[(level+tag,(x,y,z),(0,0,1)) for level,z in [('Ground',2.8),('Upper',6.5)]
             for tag,x,y in [('FrontLeft',-4,-3),('FrontRight',4,-3),('RearLeft',-4,3),('RearRight',4,3)]]
    wall=[('GroundLeft',(0,0,2.2),(1,0,0)),('GroundRight',(0,0,2.2),(-1,0,0)),
          ('UpperLeft',(0,0,6.6),(1,0,0)),('UpperRight',(0,0,6.6),(-1,0,0))]
    markers,gizmos=door.light_mounts.install(rig,meshes,ceiling,wall)
    door.HERE=HERE;door.NAME=NAME;door.export_runtime(rig,meshes+markers)
    hole_area=3.04*3.04+5.3*1.10-3.04*.02
    area=13.0**2-2*.65**2-hole_area
    assert area>=144
    report=dict(name=NAME,triangles=tris,triangle_budget=BUDGET,meshes={o.name:kit.triangles(o) for o in meshes},
        bounds_m=dict(lo=[min(v.co[i] for o in meshes for v in o.data.vertices) for i in range(3)],
                      hi=[max(v.co[i] for o in meshes for v in o.data.vertices) for i in range(3)]),materials=kit.SLOTS,
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},gizmos=gizmos,
        placement_envelope_m=[15,15],surrounding_platform=False,upper_floor_m=dict(width=13.0,depth=13.0,usable_area=area,elevation=UPPER),
        cargo_lift_m=dict(width=3,depth=3,travel=STROKE,lower=GROUND,upper=UPPER,center=[0,LIFT_Y]),
        passage_m=dict(width=4.6,height=3.48),
        trigger=dict(object='SK_LaboratoryLiftPlatformTrigger',bone='CargoLift',role='occupancy area; not a solid blocker'),
        checks=dict(exact_solid_pairs=pairs,connectivity=True,motion_states=len(states),coplanar=True,full_ground_sweep=True),
        placement='ground centre; front -Y; up +Z; library only; game integration deferred')
    surface.update_report(report,meshes,kit)
    dimensions.report(NAME,report,width=2.0,height=2.1/dimensions.HEIGHT[NAME],floors=[GROUND,UPPER],ceilings=[4.08,7.70],double=True)
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {tris} triangles; upper usable floor {area:.3f} m2',flush=True)

if __name__=='__main__':main()
