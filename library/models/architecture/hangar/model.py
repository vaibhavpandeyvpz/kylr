"""Lofted walkable pressure hangar; headless Blender 5.2, library only."""

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
spec=importlib.util.spec_from_file_location('hangar_tools',MODELS/'architecture/container/model.py')
tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(tools)
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
sys.path.insert(0,str(HERE.parent))
import light_mounts
ROOT,PRI,SEC,FRM,JNT,EMI=common.ROOT,common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
GLASS='M_Glass'
NAME,TITLE='hangar','Hangar'
TRIANGLE_BUDGET=10000 # Explicit user-approved architectural exception.
block,rod=common.block,common.rod
mach,transform=tools.mach,tools.transform
FRONT,REAR,DECK=-4.90,5.10,.15
ENTRY=-2.15
ENTRY_RESIZE=dimensions.entry_frame((0,ENTRY,DECK),2/4.6,(2.1/3.48)/dimensions.HEIGHT[NAME])
ENTRY_FRAME=Matrix.Translation((0,FRONT+ENTRY,0))@Matrix.Diagonal((-1,-1,1,1))@ENTRY_RESIZE
HX,HY=2.48,-2.47
DOOR_BACK=-2.204

def profile(w,b,t,c):
    return [(-w+c,b),(w-c,b),(w,b+c),(w,t-c),(w-c,t),(-w+c,t),(-w,t-c),(-w,b+c)]

def prism(points,y0,y1):
    return kit.prism_bm([(x,(y0+y1)/2,z) for x,z in points],y1-y0,(0,1,0))

OUTER=[(-4.25,DECK),(4.25,DECK),(4.50,.40),(4.50,3.50),(3.60,4.40),(-3.60,4.40),(-4.50,3.50),(-4.50,.40)]
INNER=[(-4.04,.09),(4.04,.09),(4.29,.34),(4.29,3.33),(3.44,4.18),(-3.44,4.18),(-4.29,3.33),(-4.29,.34)]
PORTAL=profile(2.30,DECK,3.63,.58)

def portal_offset(distance):
    """Parallel offset of all opening edges, clipped only by the pad plane."""
    points=profile(2.30+distance,DECK-distance,3.63+distance,
        .58+distance*(2-math.sqrt(2)))
    clipped=[]
    for a,b in zip(points,points[1:]+points[:1]):
        if a[1]>=DECK:clipped.append(a)
        if (a[1]<DECK)!=(b[1]<DECK):
            t=(DECK-a[1])/(b[1]-a[1])
            clipped.append((a[0]+t*(b[0]-a[0]),DECK))
    # Keep the original lower-left-first vertex convention for lofting.
    start=min(range(len(clipped)),key=lambda i:(clipped[i][1],clipped[i][0]))
    return clipped[start:]+clipped[:start]

def collar_blank():
    return kit.loft_rings([[(x,y,z) for x,z in portal_offset(d)]
        for d,y in ((.59,ENTRY),(.59,-2.24),(.44,-2.31))])

def check_frame_offsets():
    for thickness in (.276,.30,.44,.59):
        points=portal_offset(thickness)
        for a,b in zip(points,points[1:]+points[:1]):
            if abs(a[1]-DECK)<1e-8 and abs(b[1]-DECK)<1e-8:continue
            mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
            distances=[((v[0]-u[0])*(mid[1]-u[1])-(v[1]-u[1])*(mid[0]-u[0]))/math.dist(u,v)
                for u,v in zip(PORTAL,PORTAL[1:]+PORTAL[:1])]
            assert abs(min(distances)+thickness)<1e-6,('inconsistent entry frame thickness',thickness,a,b)

def bay_frames():
    for bay,y in enumerate((-3.18,.085,3.36)):
        for face in (2,3,4,5,6):
            a,b=Vector((OUTER[face][0],0,OUTER[face][1])),Vector((OUTER[(face+1)%8][0],0,OUTER[(face+1)%8][1]))
            across=(b-a).normalized();normal=Vector((across.z,0,-across.x))
            mid=(a+b)/2;mid.y=y
            if face in (2,6):mid.z=2.47
            yield bay,face,common.frame(mid,normal,(0,1,0)),1.86 if face in (2,6) else (b-a).length-.20

def glazing_finish():
    mat=bpy.data.materials[GLASS];bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(0,0,0,1)
    bsdf.inputs['Metallic'].default_value=0;bsdf.inputs['Roughness'].default_value=.15
    bsdf.inputs['Alpha'].default_value=.10;bsdf.inputs['IOR'].default_value=1.46
    mat.diffuse_color=(0,0,0,.10);mat.surface_render_method='DITHERED'

def emit(k,bm,mat,label,bone=ROOT):tools.emit(k,bm,mat,label,bone)
def seat(k,bm,mat,label,bone=ROOT):tools.seat(k,bm,mat,label,bone)

def landing(k,label,points,normal):
    """Every flange corner must land on the named host's uninterrupted flat."""
    host=next(p for p,t in zip(k.parts,common.LABELS) if t==label)
    axis=(k.xf.to_3x3()@Vector(normal)).normalized()
    for point in points:
        point=k.xf@Vector(point)
        hit=host.bvh.find_nearest(Vector(point))
        assert hit[3]<1e-5 and abs(hit[1].dot(axis))>.999,('unsupported or chamfered flange',label,point,hit[3],list(hit[1]))

def floor_info():
    # Actual horizontal section through the inner lower wall chamfer, at deck
    # height; the exterior deck and solid jambs are excluded from room area.
    half_width=INNER[1][0]+(DECK-INNER[1][1])*(INNER[2][0]-INNER[1][0])/(INNER[2][1]-INNER[1][1])
    width=2*half_width;depth=REAR-FRONT-.44
    vestibule=2*PORTAL[1][0]*(FRONT+.22-(ENTRY_FRAME@Vector((0,DOOR_BACK,0))).y)
    return dict(main_chamber_clear_floor_m=dict(width=width,depth=depth,area=width*depth),
        entrance_recess_floor_area_m2=vestibule,closed_room_floor_area_m2=width*depth+vestibule)

def pressure_shell(k):
    bm=kit.loft_rings([[(x,y,z) for x,z in p] for y,p in
        [(FRONT,OUTER),(FRONT+.10,OUTER),(REAR-.10,OUTER),(REAR,OUTER)]])
    bm=mach(bm,subtract=[([(x,(FRONT+.22+REAR-.22)/2,z) for x,z in INNER],(0,1,0),REAR-FRONT-.44),
                        ([ENTRY_FRAME@Vector((x,ENTRY,z)) for x,z in portal_offset(.59)],(0,1,0),.70)])
    collar=collar_blank()
    transform(collar,ENTRY_FRAME);collar.verts.ensure_lookup_table()
    for i,v in enumerate(collar.verts):v.index=i
    cutter=kit.Part(ROOT,'matched collar seat',[v.co.copy() for v in collar.verts],
        [tuple(v.index for v in f.verts) for f in collar.faces],False)
    collar.free();bm=common.trim_seats(bm,[cutter])
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=bm.edges[:])
    boundary=[e for e in bm.edges if e.is_boundary]
    if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
    windows=[]
    for _,face,m,width in bay_frames():
        if face==4:continue
        # Through-wall aperture follows the glazing perimeter, with a 2 mm
        # parallel running clearance; opaque shell faces cannot cover it.
        points=[m@Vector((x,y,-.12)) for x,y,_ in common.outline(width-.28,2.49,.045+.002*(2-math.sqrt(2)),0)]
        windows.append((points,tuple(m.to_3x3()@Vector((0,0,1))),.65))
    bm=mach(bm,subtract=windows)
    prior_faces=set(k.bm.faces)
    emit(k,bm,SEC,'continuous lofted pressure walls, crown and rear bulkhead')
    k.bm.normal_update()
    # Shared casting, painted by surface: broad vertical walls are off-white;
    # the crown and lower chamfers stay grey. Structural ribs remain separate
    # grey castings, so the wall finish never washes out the framing.
    for face in k.bm.faces:
        if face not in prior_faces and abs(face.normal.z)<.35:
            face.material_index=kit.SLOTS.index(PRI)
    # Repeated external ribs wrap the shell as single formed structures. The
    # underside is machined against the actual pressure section, not buried.
    ribouter=[(-4.34,DECK),(4.34,DECK),(4.66,.47),(4.66,3.55),(3.65,4.56),(-3.65,4.56),(-4.66,3.55),(-4.66,.47)]
    for i,y in enumerate((FRONT+.13,-1.58,1.75,REAR-.13)):
        rib=prism(ribouter,y-.11,y+.11)
        rib=mach(rib,subtract=[([(x,y,z) for x,z in OUTER],(0,1,0),.30)],
                 cuts=[((s*4.63,y-.15,z),(s*4.63,y+.15,z),.036,8) for s in (-1,1) for z in (.55,.80)])
        emit(k,rib,SEC,f'wraparound structural rib {i+1}')
    # A cassette sits on each vertical flank and each roof slope in each bay.
    # Flat mounting back; lofted border with a machined recessed panel seat.
    for bay,face,m,width in bay_frames():
            m.translation+=m.to_3x3()@Vector((0,0,.000002))
            with k.frame(m):
                cassette=common.loft([(width,2.80,.08,0),(width-.10,2.70,.06,.085)])
                if face==4:
                    cassette=mach(cassette,subtract=[(common.outline(width-.28,2.49,.045+.002*(2-math.sqrt(2)),.085),(0,0,1),.040)])
                else:
                    # The glass perimeter seats directly in its retaining rim;
                    # the wider through-shell aperture stays behind that rim.
                    cassette=mach(cassette,subtract=[(common.outline(width-.284,2.486,.045,.04),(0,0,1),.14)])
                emit(k,cassette,SEC,f'bay {bay} face {face} formed armour rim')
                panel=common.loft([(width-.284,2.486,.045,.06502),(width-.284,2.486,.045,.074)])
                if face==4:
                    panel=mach(panel,boxes=[((x,y,.074),(1.05,.055,.011)) for x in (-1.56,1.56) for y in (-.22,0,.22)])
                emit(k,panel,SEC if face==4 else GLASS,f'bay {bay} face {face} recessed armour plate' if face==4 else f'bay {bay} face {face} black glazing')
                if face==4:
                    for x in (-1.56,1.56):
                        for yy in (-.22,0,.22):
                            emit(k,block((x-.522,yy-.026,.06852),(x+.522,yy+.026,.071)),FRM,'recessed roof heat exchanger channel')
                # Two retained hex heads on uninterrupted end flange flats.
                for yy in (-1.31,1.31):
                    emit(k,rod((0,yy,.085),(0,yy,.098),.026,6),JNT,'armour flange captive bolt')
    # Rear access cassette has its own flat perimeter and recessed white face.
    m=common.frame((0,REAR,2.18),(0,1,0),(0,0,1))
    with k.frame(m):
        hatch=mach(common.loft([(2.80,2.60,.26,0),(2.80,2.60,.26,.04),(2.68,2.48,.22,.08)]),
                   subtract=[(common.outline(2.34,2.14,.20+.002*(2-math.sqrt(2)),.08),(0,0,1),.045)])
        emit(k,hatch,SEC,'rear inspection hatch bolted perimeter')
        emit(k,common.loft([(2.336,2.136,.20,.05752),(2.336,2.136,.20,.066)]),PRI,'rear inspection cover')
        for x in (-1.25,1.25):
            for y in (-1.0,1.0):emit(k,rod((x,y,.08),(x,y,.094),.028,6),JNT,'rear hatch captive bolt')

def entry(k):
    # Stepped octagonal pressure collar, flush bottom ends seated on the deck.
    bm=collar_blank()
    bm=mach(bm,subtract=[([(x,-2.24,z) for x,z in PORTAL],(0,1,0),.50)])
    p1=portal_offset(.30);p2=portal_offset(.276)
    # No sill across the walking lane: open both guide profiles below the deck.
    p2=[(x-math.copysign(.02,x),z-.02) if abs(z-DECK)<1e-6 else (x,z) for x,z in p2]
    ring=mach(prism(p1,-2.310,-2.302),subtract=[([(x,-2.306,z) for x,z in p2],(0,1,0),.03)])
    ring.verts.ensure_lookup_table()
    for i,v in enumerate(ring.verts):v.index=i
    cut=kit.Part(ROOT,'entry light guide recess',[v.co.copy() for v in ring.verts],
        [tuple(v.index for v in f.verts) for f in ring.faces],False)
    bm=common.trim_seats(bm,[cut])
    seat(k,bm,SEC,'lofted octagonal entry collar with fitted jambs')
    # A continuous cyan conduit fills its own octagonal groove; no overlaid
    # ring. Shape derived from the same offset profiles at the collar face.
    seat(k,ring,EMI,'seated octagonal entry light guide')

def half_leaf(s,inset=0):
    # Centre seam is a real 40 mm running gap, clearing the offset hinge arc.
    # Chamfered silhouette follows
    # the octagonal opening; both lower and upper diagonal corners remain.
    q=[(.020,.18),(1.72,.18),(2.28,.74),(2.28,3.05),(1.72,3.61),(.020,3.61)]
    return [(s*x,z) for x,z in q]

def doors(k,s,bone):
    leaf=kit.loft_rings([[(x,y,z) for x,z in half_leaf(s)] for y in (DOOR_BACK,-2.25,-2.33)])
    # Two separately recessed pressure cassettes. Wide centre and perimeter
    # lands provide genuine hinge/lock mounting surfaces.
    # Parallel offset of the plate's eight-edge outline: 5 mm clearance on
    # every straight and 45-degree face, including each chamfered corner.
    pocket_corner=.17+.005*(2-math.sqrt(2))
    pockets=[([(s*1.06+x,y,z+yy) for x,yy,_ in common.outline(1.58,.97,pocket_corner,0)],
        (0,1,0),.052) for y in (-2.337,DOOR_BACK+.007) for z in (1.05,2.64)]
    leaf=mach(leaf,subtract=pockets)
    emit(k,leaf,SEC,'formed octagonal door leaf' if s==1 else 'right formed octagonal door leaf',bone)
    with k.frame(common.frame((s*1.06,DOOR_BACK-.019,1.845),(0,1,0),(0,0,1))):
        for y in (-.795,.795):
            p=common.loft([(1.57,.96,.17,.00005),(1.48,.87,.17-.045*(2-math.sqrt(2)),.016)])
            for v in p.verts:v.co.y+=y
            emit(k,p,PRI,'recessed exterior door armour',bone)
    m=common.frame((s*1.06,-2.311,1.845),(0,-1,0),(0,0,1))
    with k.frame(m):
        for y in (-.795,.795):
            p=common.loft([(1.57,.96,.17,.00005),(1.48,.87,.17-.045*(2-math.sqrt(2)),.016)])
            for v in p.verts:v.co.y+=y
            emit(k,p,PRI,'recessed faceted door armour',bone)
        # No external actuator pretending to work: stiffening waist is part
        # of the door casting; its fittings terminate on that flat.
        for x in (-.55,.55):
            for y in (-1.49,1.49):emit(k,rod((x,y,.019),(x,y,.030),.028,6),JNT,'door retained fastener',bone)
    # Interleaved sleeves, a moving tongue, running-clearance pin and caps.
    for z in (.81,1.89,2.97):
        x=s*HX
        for a,b in ((z-.135,z-.056),(z+.056,z+.135)):
            # The complete flange lands between the portal and light channel,
            # inside the jamb flat even at the lowest diagonal corner.
            pad=block((min(s*2.36,s*2.53),HY,a),(max(s*2.36,s*2.53),-2.31,b))
            landing(k,'lofted octagonal entry collar with fitted jambs',
                [(s*xx,-2.31,zz) for xx in (2.36,2.53) for zz in (a,b)],(0,-1,0))
            bm=mach(rod((x,HY,a),(x,HY,b),.090,8),union=[pad],
                    cuts=[((x,HY,a-.01),(x,HY,b+.01),.037,10)])
            seat(k,bm,SEC,'fixed hinge fork with jamb flange')
        tab=block((min(x,s*2.07),HY-.037,z-.055),(max(x,s*2.07),-2.33,z+.055))
        landing(k,'formed octagonal door leaf' if s==1 else 'right formed octagonal door leaf',
            [(s*xx,-2.33,zz) for xx in (2.07,2.14) for zz in (z-.055,z+.055)],(0,-1,0))
        bm=mach(rod((x,HY,z-.055),(x,HY,z+.055),.085,8),union=[tab],
                cuts=[((x,HY,z-.07),(x,HY,z+.07),.037,10)])
        seat(k,bm,SEC,'moving bored knuckle and door tongue',bone)
        emit(k,rod((x,HY,z-.135),(x,HY,z+.135),.035,10),JNT,'retained hinge through pin')
        for zz in (z-.150,z+.135):emit(k,rod((x,HY,zz),(x,HY,zz+.015),.056,8),JNT,'hinge axle retaining cap')
    x=s*HX
    landing(k,'lofted octagonal entry collar with fitted jambs',
        [(s*xx,-2.31,zz) for xx in (2.36,2.53) for zz in (1.30,1.55)],(0,-1,0))
    bm=mach(rod((x,HY,1.30),(x,HY,1.55),.14,8),
            union=[block((min(s*2.36,s*2.53),HY,1.30),(max(s*2.36,s*2.53),-2.31,1.55))],
            cuts=[((x,HY,1.29),(x,HY,1.56),.037,10)])
    seat(k,bm,FRM,'coaxial sealed reduction drive and jamb foot')
    emit(k,rod((x,HY,1.55),(x,HY,1.74),.035,10),JNT,'hinge motor output coupling')
    # One powered shoot bolt per door, upper receiver above the walking route.
    bx=s*.37;by=-2.42
    bm=mach(rod((bx,by,2.24),(bx,by,2.59),.064,8),
            union=[block((bx-.085,by,2.27),(bx+.085,-2.30,2.56))],
            cuts=[((bx,by,2.23),(bx,by,2.60),.026,8)])
    seat(k,bm,FRM,'powered shoot bolt cylinder with door saddle',bone)
    emit(k,rod((bx,by,2.40),(bx,by,3.70),.025,8),JNT,'captive upper shoot bolt',bone+'Bolt')
    bm=mach(rod((bx,by,3.33),(bx,by,3.41),.050,8),
            union=[block((bx-.066,by,3.33),(bx+.066,-2.30,3.41))],
            cuts=[((bx,by,3.32),(bx,by,3.42),.026,8)])
    seat(k,bm,SEC,'shoot bolt guide bush and leaf flange',bone)
    receiver=mach(rod((bx,by,3.64),(bx,by,3.74),.048,8),
        union=[block((bx-.065,by,3.64),(bx+.065,-2.25,3.74))],
        cuts=[((bx,by,3.63),(bx,by,3.75),.026,8)])
    seat(k,receiver,SEC,'shoot bolt receiver and header lug')
    # Glove-clear pull is a single cast bridge, bolted through its two feet.
    hm=common.frame((s*.95,-2.33,1.85),(0,-1,0),(0,0,1))
    bm=transform(common.loft([(.54,.11,.02,0),(.54,.11,.02,.13),(.50,.085,.018,.15)]),hm)
    bm=mach(bm,boxes=[((s*.95,-2.38,1.85),(.38,.16,.20))])
    seat(k,bm,JNT,'two-foot glove-clear cast pull',bone)

def services(k):
    # Side utility bus: two horizontal pipes in each uninterrupted lower wall
    # flat. Glands join short bulkhead-mounted distribution boxes at the ends.
    for s in (-1,1):
        for z in (.55,.80):
            x=s*4.63
            for y in (-4.43,4.63):
                m=common.frame((s*4.50,y,z),(s,0,0),(0,0,1))
                with k.frame(m):
                    emit(k,common.loft([(.27,.24,.04,0),(.27,.24,.04,.10),(.27,.24,.035,.14)]),FRM,'utility bulkhead junction and gland seat')
            emit(k,rod((x,-4.295,z),(x,4.495,z),.035,8),JNT,'terminated external utility pipe')
            for y in (-4.29,4.49):
                bm=mach(rod((x,y-.045,z),(x,y+.045,z),.062,8),
                    union=[block((min(x,s*4.50),y-.045,z-.071),(max(x,s*4.50),y+.045,z+.071))],
                    cuts=[((x,y-.06,z),(x,y+.06,z),.036,8)])
                seat(k,bm,SEC,'bulkhead pipe socket gland')
            for y in (-2.43,.1,2.63):
                bm=mach(rod((x,y-.045,z),(x,y+.045,z),.056,6),
                    union=[block((min(x,s*4.50),y-.045,z-.067),(max(x,s*4.50),y+.045,z+.067))],
                    cuts=[((x,y-.06,z),(x,y+.06,z),.036,8)])
                seat(k,bm,SEC,'bored pipe saddle with shell foot')
        # Ventilation cabinet seats on wall; no pipes pass through the armour.
        m=common.frame((s*4.50,.10,1.20),(s,0,0),(0,0,1))
        with k.frame(m):
            cabinet=mach(common.loft([(.93,.43,.08,0),(.93,.43,.08,.15),(.84,.35,.055,.19)]),
                boxes=[((0,0,.19),(.68,.19,.025))])
            seat(k,cabinet,SEC,'side service cabinet integral bolted flange')
            emit(k,block((-.337,-.092,.1775),(.337,.092,.18)),FRM,'recessed ventilation dark back')
            for x in (-.25,-.125,0,.125,.25):emit(k,block((x-.018,-.09,.18),(x+.018,.09,.189)),JNT,'service ventilation louvre')
    # Fixed entry control boxes with recessed status lenses.
    for s in (-1,1):
        m=ENTRY_FRAME@common.frame((s*2.68,-2.31,2.27),(0,-1,0),(0,0,1))
        with k.frame(m):
            box=mach(common.loft([(.24,.50,.04,0),(.24,.50,.04,.07),(.20,.46,.035,.09)]),boxes=[((0,.10,.09),(.07,.19,.025))])
            seat(k,box,FRM,'entry control cabinet seated in jamb')
            emit(k,block((-.034,.006,.0775),(.034,.194,.089)),EMI,'flush entry status lens')

def platform(k):
    bm=block((-4.5,-5.08,0),(4.5,REAR,DECK))
    ramp_width=2*max(abs(x) for x,z in portal_offset(.59) if abs(z-DECK)<1e-7)*ENTRY_RESIZE[0][0]
    wedge=kit.prism_bm([(0,-5.50,0),(0,-5.08,0),(0,-5.08,DECK)],ramp_width,(1,0,0))
    bm=mach(bm,union=[wedge])
    emit(k,bm,SEC,'regular integral floor and local entrance ramp; no surrounding metal platform')

def export_runtime(rig,objects,prepared=False):
    from door_actions import install_fbx_filter
    install_fbx_filter()
    for pb in rig.pose.bones:
        for c in list(pb.constraints):pb.constraints.remove(c)
    if not prepared:common.prepare_export([rig,*objects],HERE,NAME)
    kit.select_only([rig,*objects])
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=False,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_materials='EXPORT')
    from door_actions import isolate_glb
    isolate_glb(HERE/f'{NAME}.glb')

def split_assemblies(body):
    """One rig, separate architecture, fixed hardware and articulated leaves."""
    result=[]
    for label,predicate in (
        ('ArchitectureFront',lambda b,m,y:b==ROOT and m==SEC and y<=0),
        ('ArchitectureRear',lambda b,m,y:b==ROOT and m==SEC and y>0),
        ('CladdingAndServices',lambda b,m,y:b==ROOT and m!=SEC),
        ('Doors',lambda b,m,y:b!=ROOT)):
        obj=body.copy();obj.data=body.data.copy();obj.name='SK_'+TITLE+label
        bpy.context.scene.collection.objects.link(obj)
        bm=bmesh.new();bm.from_mesh(obj.data);weights=bm.verts.layers.deform.active
        discard=[]
        for f in bm.faces:
            b=obj.vertex_groups[next(iter(f.verts[0][weights].keys()))].name
            if not predicate(b,obj.data.materials[f.material_index].name,f.calc_center_median().y):discard.append(f)
        bmesh.ops.delete(bm,geom=discard,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free();result.append(obj)
    old=body.data;bpy.data.objects.remove(body,do_unlink=True);bpy.data.meshes.remove(old)
    assert all(kit.triangles(o)<=5000 for o in result),{o.name:kit.triangles(o) for o in result}
    return result

def refresh_exports():
    kit.NAME,kit.TITLE=NAME,TITLE
    bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    report=json.loads((HERE/f'{NAME}_rig.json').read_text())
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0);kit.SLOTS=list(kit.MATERIALS)
    report.update(floor_info())
    report['passage_m']=dict(width=2.0,height=2.1,threshold=DECK*dimensions.HEIGHT[NAME])
    report['exterior_shell_m']=dict(width=9,depth=10)
    report.pop('platform_m',None)
    report['surrounding_platform']=False
    report['floor_slab_m']=dict(width=9,depth=10.18,height=DECK,ramp_width=2*max(abs(x) for x,z in portal_offset(.59) if abs(z-DECK)<1e-7)*ENTRY_RESIZE[0][0],ramp_run=.42)
    if '--metadata-only' in sys.argv:
        (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
        print(f'[{NAME}] floor section: {floor_info()}',flush=True)
        return
    if '--draft' not in sys.argv:
        assert report['triangles']<=TRIANGLE_BUDGET,(report['triangles'],TRIANGLE_BUDGET)
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
    if len(meshes)==1:meshes=split_assemblies(meshes[0])
    mounts=[o for o in bpy.context.scene.objects if o.type=='EMPTY' and o.name.startswith(('BattenLightMount','SconceLightMount'))]
    export_runtime(rig,[*meshes,*mounts],prepared=True)
    report['meshes']={o.name:kit.triangles(o) for o in meshes}
    report['triangle_budget']=TRIANGLE_BUDGET
    report['budget_passed']=report['triangles']<=TRIANGLE_BUDGET
    report['delivery_status']='validated' if report['budget_passed'] else 'draft; total-budget exception awaiting user decision'
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))

def main():
    import perimeter_surface as surface
    outline=[(-4.5,-5.08,0),(4.5,-5.08,0),(4.5,REAR,0),(-4.5,REAR,0)]
    if '--surface-only' in sys.argv:
        surface.refresh(HERE,NAME,kit,outline,3.6,
            lambda rig,meshes,markers:export_runtime(rig,[*meshes,*markers],prepared=True),subdivisions=8)
        return
    if '--exports-only' in sys.argv or '--metadata-only' in sys.argv:refresh_exports();return
    if '--profile' in sys.argv:
        import faulthandler
        faulthandler.dump_traceback_later(30,repeat=True)
    common.CORNER_STEPS=1;common.LABELS.clear()
    check_frame_offsets()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.015,.62,.68),0,.34,2.0)
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0);surface.configure(kit);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials();glazing_finish()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    keys={}
    for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):
        kit.JOINT_SPECS.extend([(bn,ROOT,'hinge',tuple(ENTRY_FRAME@Vector((s*HX,HY,1.89))),(0,0,1),(0,1,0),(0,105) if s==1 else (-105,0)),
            (bn+'Bolt',bn,'slide',tuple(ENTRY_FRAME@Vector((s*.37,-2.42,2.40))),(0,0,1),(0,0,1),(-.12*ENTRY_RESIZE[2][2],0))])
        keys[bn]=[(0,0),(21,0),(81,s*105),(96,s*105)]
        keys[bn+'Bolt']=[(0,0),(15,-.12*ENTRY_RESIZE[2][2]),(96,-.12*ENTRY_RESIZE[2][2])]
    kit.GROUPS=();kit.ANIMATIONS={'open':(False,'BEZIER',keys),'close':(False,'BEZIER',{bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in keys.items()})}
    from door_actions import independent_leaves
    independent_leaves(kit.ANIMATIONS,keys)
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    platform(k);pressure_shell(k)
    with k.frame(ENTRY_FRAME):
        entry(k)
        for s,bn in ((1,'LeftDoor'),(-1,'RightDoor')):doors(k,s,bn)
    services(k)
    # Independent exterior dress collar seats on the real front bulkhead;
    # the interior collar carries the inward-swinging mechanical hardware.
    first=len(common.LABELS)
    with k.frame(Matrix.Translation((0,FRONT-ENTRY,0))@ENTRY_RESIZE):entry(k)
    for i in range(first,len(common.LABELS)):common.LABELS[i]='exterior '+common.LABELS[i]
    for p,label in zip(k.parts,common.LABELS):p.line=label
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps([dict(label=t,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces) for p,t in zip(k.parts,common.LABELS)]))
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    print(f'[{NAME}] connectivity and full flange landings PASS',flush=True)
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    for a in range(0,106,3):
        for l,r in ((a,0),(0,-a),(a,-a)):
            states.append((f'sweep {l},{r}',{'LeftDoor':l,'RightDoor':r,'LeftDoorBolt':-.12*ENTRY_RESIZE[2][2]*dimensions.HEIGHT[NAME],'RightDoorBolt':-.12*ENTRY_RESIZE[2][2]*dimensions.HEIGHT[NAME]}))
    kit.check_motion(k,joints,states)
    print(f'[{NAME}] {len(states)} motion states PASS',flush=True)
    for _,state in states[::17]:
        kit.reset_pose(rig)
        for bn,v in state.items():kit.set_joint(rig,joints[bn],v)
        bpy.context.view_layer.update()
        for bn,wanted in kit.fk(joints,state).items():
            pb=rig.pose.bones[bn];actual=pb.matrix@pb.bone.matrix_local.inverted()
            assert max(abs(actual[i][j]-wanted[i][j]) for i in range(4) for j in range(4))<1e-5,('rig FK',bn)
    kit.reset_pose(rig)
    for _,state in states:
        matrices=kit.fk(joints,state)
        for p in k.parts:
            for v in p.verts:
                q=matrices[p.bone]@v
                assert -5.00001<=q.x<=5.00001 and -5.50001<=q.y<=5.50001,('ground motion envelope',p.line,list(q))
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps([dict(label=t,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces) for p,t in zip(k.parts,common.LABELS)]))
    print(f'[{NAME}] converting checked geometry',flush=True)
    obj=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(obj,rig)
    sys.path.insert(0,str(MODELS/'architecture/lunar_dome'))
    from surface_audit import check_coplanar
    check_coplanar(obj)
    if '--ray-cull' in sys.argv:
        print(f'[{NAME}] optional full ray visibility pass',flush=True)
        kit.cull_unseen(obj,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
    # Only floor-contact undersides are invisible in every animation state.
    bm=bmesh.new();bm.from_mesh(obj.data)
    hidden=[f for f in bm.faces if all(abs(v.co.z)<1e-6 for v in f.verts) and f.normal.z<-.5]
    bmesh.ops.delete(bm,geom=hidden,context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
    tris=kit.triangles(obj)
    print(f'[{NAME}] pre-export triangles {tris}',flush=True)
    mounts,mount_info=light_mounts.install(rig,[obj],
        [(tag,(0,y,2.8),(0,0,1)) for tag,y in (('Front',-2.2),('Rear',2.4))],
        [(tag,(0,y,2.20),(s,0,0)) for tag,s,y in
            (('LeftFront',1,-1.8),('LeftRear',1,1.75),('RightFront',-1,-1.8),('RightRear',-1,1.75))])
    if '--draft' not in sys.argv:
        assert tris<=TRIANGLE_BUDGET,(tris,TRIANGLE_BUDGET)
    lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    rig['preview_poses']=json.dumps({'open':{'LeftDoor':{'rot':[105,0,0]},'RightDoor':{'rot':[-105,0,0]},'LeftDoorBolt':{'loc':[0,-.12,0]},'RightDoorBolt':{'loc':[0,-.12,0]}},
        'unlocked':{'LeftDoorBolt':{'loc':[0,-.12,0]},'RightDoorBolt':{'loc':[0,-.12,0]}}})
    bpy.context.scene['preview_actions']=json.dumps(['open','close'])
    bpy.context.scene['showcase_frame']=json.dumps(dict(lo=[-5,-5.5,0],hi=[5,5.5,4.56]))
    meshes=split_assemblies(obj) if '--draft' not in sys.argv else [obj]
    meshes.append(surface.create(rig,outline,3.6,subdivisions=8))
    tris=sum(kit.triangles(o) for o in meshes);assert tris<=TRIANGLE_BUDGET
    if '--draft' not in sys.argv:export_runtime(rig,[*meshes,*mounts])
    report=dict(name=NAME,triangles=tris,triangle_budget=TRIANGLE_BUDGET,meshes={o.name:kit.triangles(o) for o in meshes},bounds_m=dict(lo=lo,hi=hi),materials=kit.SLOTS,
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        ground_envelope_m=[10,11],passage_m=dict(width=4.6,height=3.63-DECK,threshold=DECK),
        exterior_shell_m=dict(width=9,depth=10),surrounding_platform=False,
        floor_slab_m=dict(width=9,depth=10.18,height=DECK,ramp_width=2*max(abs(x) for x,z in portal_offset(.59) if abs(z-DECK)<1e-7)*ENTRY_RESIZE[0][0],ramp_run=.42),
        glazing=dict(material=GLASS,color=[0,0,0],opacity=.10),
        finishes=dict(walls=PRI,roof=SEC,framing=SEC,windows=GLASS),
        entry_frame_m=dict(face_thickness=.44,base_thickness=.59,guide_width=.024,parallel_offsets=True),
        gizmos=mount_info,
        checks=dict(exact_solid_pairs=pairs,connectivity=True,motion_states=len(states),coplanar=True,full_ground_sweep=True),
        placement='ground centre; front -Y; up +Z; library only')
    report.update(floor_info())
    report['optional_surface']=surface.metadata()
    surface.update_report(report,meshes,kit)
    report['budget_passed']=tris<=TRIANGLE_BUDGET
    report['delivery_status']='validated' if report['budget_passed'] else 'over budget'
    dimensions.report(NAME,report,width=2.0,height=2.1/dimensions.HEIGHT[NAME],floors=[DECK],ceilings=[4.18],double=True)
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] {"DRAFT" if "--draft" in sys.argv else "PASS"} {tris} triangles; {len(k.parts)} manufactured parts',flush=True)

if __name__=='__main__':main()
