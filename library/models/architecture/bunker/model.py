"""Walkable octagonal lunar bunker. Source generator, Blender 5.2 headless.
Manufactured shells and mechanically interlocked pressure door; library only.
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
sys.path.insert(0,str(HERE.parent))
import light_mounts

def fixture_mounts(rig,meshes):
    return light_mounts.install(rig,meshes,
        [('',(0,PLACEMENT_Y,2.8),(0,0,1))],
        [(tag,(0,PLACEMENT_Y,1.4),direction) for tag,direction in
            (('Left',(1,0,0)),('Right',(-1,0,0)),('Rear',(0,1,0)))])

import importlib.util
spec=importlib.util.spec_from_file_location('bunker_door_tools',MODELS/'architecture/container/model.py')
door=importlib.util.module_from_spec(spec);spec.loader.exec_module(door)
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
ROOT,PRI,SEC,FRM,JNT,EMI=common.ROOT,common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
NAME,TITLE='bunker','Bunker'
REG,GLASS='M_Regolith','M_Glass'
block,rod=common.block,common.rod
emit,seat,mach,transform,boxcut=door.emit,door.seat,door.mach,door.transform,door.boxcut
PX,PY=-.86,-3.54
PLACEMENT_Y=.30 # building is set north of pad centre to retain door swing clearance
PROFILE=[(3.30,0),(3.30,.16),(3.24,.23),(2.64,2.49),(2.61,2.60),(2.61,2.69),(2.37,3.29),(2.30,3.38)]

def outline(r,z):
    c=r*.42
    return [(-r+c,-r,z),(r-c,-r,z),(r,-r+c,z),(r,r-c,z),
            (r-c,r,z),(-r+c,r,z),(-r,r-c,z),(-r,-r+c,z)]

def shell(stations):return kit.loft_rings([outline(r,z) for r,z in stations])

def pressure_shell():
    """Integral architectural frame and recessed armour cells, shared edges.
    The border is the pressure wall itself; no bars hide under another part.
    """
    rings=[]
    for r,z in PROFILE:
        corners=list(map(Vector,outline(r,z)));row=[]
        for i,a in enumerate(corners):
            b=corners[(i+1)%8]
            n=Vector((b.y-a.y,a.x-b.x,0)).normalized()
            for u in (0,.055,.060,.940,.945):
                p=a.lerp(b,u)
                if .23<=z<=2.49 and u in (.060,.940):p-=n*.010
                row.append(p)
        rings.append(row)
    return kit.loft_rings(rings)

def inset_polygon(points,distance,z):
    """Exact 2D parallel-edge offset; constant rim width through chamfers."""
    pts=[Vector((p[0],p[1],0)) for p in points]
    lines=[]
    for a,b in zip(pts,pts[1:]+pts[:1]):
        edge=b-a;n=Vector((-edge.y,edge.x,0)).normalized()
        lines.append((a+n*distance,edge))
    def cross(a,b):return a.x*b.y-a.y*b.x
    result=[]
    for (a,e),(b,f) in zip(lines[-1:]+lines[:-1],lines):
        p=a+e*(cross(b-a,f)/cross(e,f));p.z=z;result.append(p)
    return result

def leafshape(w,z0,z1):
    return [(-w+.15,0,z0),(w-.15,0,z0),(w,0,z0+.15),(w,0,z1-.15),
            (w-.15,0,z1),(-w+.15,0,z1),(-w,0,z1-.15),(-w,0,z0+.15)]

def tunnel(w,z0,z1,y0,y1):
    return kit.prism_bm([(x,(y0+y1)/2,z) for x,_,z in leafshape(w,z0,z1)],y1-y0,(0,1,0))

def part(k,bm,mat,label,bone=ROOT):
    emit(k,bm,mat,label,bone)

def seated(k,bm,mat,label,bone=ROOT):
    seat(k,bm,mat,label,bone)

def body(k):
    # Closed pressure shell, floor and roof; cavity reaches all the way to the
    # vestibule. Same ring vertices define the sloped panel seating planes.
    base=pressure_shell()
    cavity=shell([(3.12,.12),(3.12,.22),(2.48,2.61),(2.22,3.20)])
    vestibule=kit.loft_rings([[(x,y,z) for x,_,z in leafshape(w,0,top)]
        for y,w,top in [(-3.40,.91,2.515),(-3.32,.98,2.55),(-2.53,.98,2.55),(-2.38,.98,2.55)]])
    base=mach(base,union=[vestibule])
    # Cavity and open entry are exact subtractive volumes, never black covers.
    def subtract(bm,tool):
        tool.verts.index_update()
        from types import SimpleNamespace
        p=SimpleNamespace(verts=[v.co.copy() for v in tool.verts],faces=[[v.index for v in f.verts] for f in tool.faces])
        result=common.trim_seats(bm,[p]);tool.free();return result
    base=subtract(base,cavity)
    base=subtract(base,tunnel(.675,.12,2.37,-3.6,-2.0))
    base=subtract(base,tunnel(.751,.10,2.445,-3.60,-3.31))
    # Upper belt: genuine through glazing in every octagonal face, flush
    # elastomer glazing seats, and isolated light pipes below each window.
    inlays=[]
    for i in range(8):
        points=outline(2.61,2.69);top=outline(2.37,3.29)
        a,b=Vector(points[i]),Vector(points[(i+1)%8]);c,d=Vector(top[i]),Vector(top[(i+1)%8])
        across=(b-a).normalized();up=(c-a).normalized();normal=across.cross(up).normalized()
        if normal.dot((a+b)/2)<0:normal=-normal
        def pt(u,v):return a.lerp(b,u).lerp(c.lerp(d,u),v)
        for u0,u1 in ((.10,.47),(.53,.90)):
            polygon=[pt(u0,.16),pt(u1,.16),pt(u1,.84),pt(u0,.84)]
            base=subtract(base,kit.prism_bm(polygon,.60,normal))
            # One pane fills the wall opening, with a small outer reveal.
            centre=sum(polygon,Vector())/4
            pane=[p+(centre-p).normalized()*.00002 for p in polygon]
            glass=kit.prism_bm([p-normal*.085 for p in pane],.14,normal)
            inlays.append((glass,GLASS,'recessed pressure glazing'))
        polygon=[pt(.08,.035),pt(.92,.035),pt(.92,.075),pt(.08,.075)]
        base=subtract(base,kit.prism_bm([p-normal*.008 for p in polygon],.022,normal))
        inlays.append((kit.prism_bm([p-normal*.009 for p in polygon],.020,normal),EMI,'flush upper service light'))
    # Colour changes are face assignments on the continuous formed shell.
    base.normal_update()
    assert all(e.is_manifold for e in base.edges), "pressure shell manifold"
    for f in base.faces:
        p=f.calc_center_median();n=f.normal
        f.material_index=kit.SLOTS.index(PRI if .23<p.z<2.49 and abs(n.z)<.6 else SEC)
        if .23<p.z<2.49:
            r=3.24-(p.z-.23)*.60/2.26
            corners=list(map(Vector,outline(r,p.z)))
            nearest=None
            for a,b in zip(corners,corners[1:]+corners[:1]):
                u=(p-a).dot(b-a)/(b-a).length_squared
                d=(p-a.lerp(b,max(0,min(1,u)))).length
                if nearest is None or d<nearest[0]:nearest=(d,u)
            if nearest[0]<.025 and (nearest[1]<.061 or nearest[1]>.939):
                f.material_index=kit.SLOTS.index(SEC)
        # The continuous entrance canopy is painted as one formed component,
        # including its chamfers; no accidental triangular grey colour wedges.
        if p.y<-2.35 and abs(p.x)<1.06 and .13<p.z<2.58:
            f.material_index=kit.SLOTS.index(PRI)
        if p.z<.13:f.material_index=kit.SLOTS.index(FRM)
    bmesh.ops.triangulate(base,faces=base.faces[:])
    mats=[f.material_index for f in base.faces]
    made=k.emit(base,ROOT,PRI,False,convex=False,exact=True)
    for f,m in zip(made,mats):f.material_index=m
    common.LABELS.append('fused pressure shell, vestibule, structural deck and crown')
    for bm,mat,label in inlays:part(k,bm,mat,label)
    for s in (-1,1):
        m=common.frame((s*1.18,-3.0,1.1),(0,-1,0),(0,0,1))
        with k.frame(m):
            pod=mach(common.loft([(.43,.64,.085,-.15),(.54,.60,.10,.10),(.43,.46,.075,.20)]),
                     boxes=[((0,0,.198),(.31,.10,.028))])
            seated(k,pod,SEC,'door service fairing and integral wall flange')
            part(k,block((-.153,-.048,.184),(.153,.048,.198)),FRM,'recessed service ventilation slot')
            for x in (-.145,.145):
                part(k,rod((x,.16,.20),(x,.16,.208),.013,6),JNT,'service fairing captive screw')
    # Sloped armour service shrouds: lofted machined casts, bolted mounting
    # lands trimmed to the true sloped shell. No overlay under a floating end.
    for i in (1,3,5,7):
        p0,p1=map(Vector,(outline(3.24,.23)[i],outline(3.24,.23)[(i+1)%8]))
        q0,q1=map(Vector,(outline(2.64,2.49)[i],outline(2.64,2.49)[(i+1)%8]))
        mid=(p0+p1)/2;upper=(q0+q1)/2
        n=(p1-p0).cross(upper-mid).normalized()
        if n.dot(mid)<0:n=-n
        inset=Vector((n.x,n.y,0)).normalized()*.010
        m=common.frame(mid.lerp(upper,.5)-inset+n*.00001,n,upper-mid)
        with k.frame(m):
            # Removable tapered armour cassette, machined perimeter bolt land,
            # inset pressure-backed face. All coordinates share one wall frame.
            shroud=common.loft([(1.17,1.86,.09,0),(1.17,1.86,.09,.035),(1.09,1.78,.07,.070)])
            for v in shroud.verts:v.co.x*=1-.18*(v.co.y/1.86+.5)
            outer=[Vector(p) for p in common.outline(1.09,1.78,.07,.07)]
            for p in outer:p.x*=1-.18*(p.y/1.86+.5)
            opening=inset_polygon(outer,.105,.0755)
            shroud=mach(shroud,subtract=[(opening,(0,0,1),.030)])
            part(k,shroud,SEC,'tapered removable armour cassette with integral mounting flange')
            panel=inset_polygon(opening,.00002,(.06052+.067)/2)
            part(k,kit.prism_bm(panel,.067-.06052,(0,0,1)),PRI,'recessed cassette pressure-backed face')
            # Screw centres track the tapered border, rather than a rectangle.
            for y in (-.795,.795):
                x_land=.545*(1-.18*(y/1.86+.5))-.055
                for x in (-x_land,x_land):
                    seated(k,rod((x,y,.060),(x,y,.075),.016,6),JNT,'cassette retained flange fastener')
    # Roof has a recessed bolted service hatch and a seated heat exchanger.
    seated(k,common.loft([(1.34,1.12,.12,3.34),(1.34,1.12,.12,3.405),(1.24,1.02,.09,3.43)]),SEC,'roof service hatch')
    for x in (-.50,.50):
        for y in (-.38,.38):part(k,rod((x,y,3.43),(x,y,3.438),.022,6),JNT,'roof hatch flange fastener')
    # Deck ramp: lower end on grade, upper end exactly at the sill.
    bm=kit.prism_bm([(0,-4.10,0),(0,-3.40,.12),(0,-3.40,0)],1.34,(1,0,0))
    bm=mach(bm,cuts=[((.47,-3.50,.02),(.47,-3.50,.23),.031,8)])
    seated(k,bm,SEC,'grade to threshold approach ramp')

def entrance(k):
    # Seal cartridge is open through its centre, flush in the machined seat.
    seal=mach(tunnel(.751,.10,2.445,-3.39,-3.31),subtract=[([(x,-3.35,z) for x,_,z in leafshape(.737,.114,2.431)],(0,1,0),.30)])
    part(k,seal,FRM,'pressure seal cartridge')
    leaf=kit.loft_rings([[(x,y,z) for x,_,z in leafshape(w,b,t)] for y,w,b,t in
        [(-3.385,.731,.127,2.425),(-3.405,.731,.127,2.425),(-3.475,.69,.167,2.385)]])
    leaf=mach(leaf,boxes=[((0,-3.48,1.2725),(1.10,.038,1.70))])
    part(k,leaf,SEC,'formed pressure door with recessed face','Door')
    # Faceted door skin is formed as one recessed cassette, with a machined
    # waist and upper/lower strengthening channels, rather than a flat slab.
    dm=common.frame((0,-3.46101,1.2725),(0,-1,0),(0,0,1))
    with k.frame(dm):
        skin=common.loft([(1.086,1.687,.12,0),(1.086,1.687,.12,.006),(1.02,1.62,.10,.011)])
        skin=mach(skin,boxes=[((0,.57,.012),(.70,.055,.008)),((0,-.57,.012),(.70,.055,.008))])
        part(k,skin,PRI,'formed recessed door skin with strengthening channels','Door')
    # Three knuckle pairs interleave with 1 mm axial separation. Coaxial pin
    # has 1 mm radial running clearance; integral lugs are fitted to their host.
    for z in (.47,1.2725,2.075):
        for a,b in ((z-.11,z-.045),(z+.045,z+.11)):
            # Every pad corner lands within the uninterrupted flat jamb,
            # outboard of the gasket but inboard of the vestibule chamfer.
            for x in (PX-.030,PX+.050):
                for zc in (a,b):
                    p=Vector((x,-3.40+PLACEMENT_Y,zc))
                    hit=k.parts[0].bvh.find_nearest(p)
                    assert hit[3]<1e-5 and abs(hit[1].y)>.999,('hinge foot must land wholly on flat',list(p),hit[3])
            sleeve=mach(rod((PX,PY,a),(PX,PY,b),.061,10),union=[block((PX-.030,PY,a),(PX+.050,-3.40,b))],cuts=[((PX,PY,a-.01),(PX,PY,b+.01),.024,10)])
            part(k,sleeve,SEC,'fixed hinge bearing and fully seated jamb lug')
        door_surface=next(p for p,label in zip(k.parts,common.LABELS) if label=='formed pressure door with recessed face')
        for x in (-.675,-.635):
            for zc in (z-.044,z+.044):
                hit=door_surface.bvh.find_nearest(Vector((x,-3.475+PLACEMENT_Y,zc)))
                assert hit[3]<1e-5 and abs(hit[1].y)>.999,('door hinge foot must land wholly on flat',x,zc,hit[3])
        knuckle=mach(rod((PX,PY,z-.044),(PX,PY,z+.044),.058,10),union=[block((PX,PY-.028,z-.044),(-.63,-3.46,z+.044))],cuts=[((PX,PY,z-.05),(PX,PY,z+.05),.024,10)])
        seated(k,knuckle,SEC,'door hinge tongue and rotating knuckle','Door')
        part(k,rod((PX,PY,z-.110),(PX,PY,z+.110),.021,10),JNT,'retained hinge axle')
        for zz in (z-.123,z+.110):part(k,rod((PX,PY,zz),(PX,PY,zz+.013),.035,10),JNT,'axle retaining cap')
    # Drive motor shares the hinge axis and bolts to the stationary jamb;
    # its output is the bottom hinge shaft, no impossible linear actuator.
    for x in (PX-.030,PX+.050):
        for zc in (.19,.347):
            hit=k.parts[0].bvh.find_nearest(Vector((x,-3.40+PLACEMENT_Y,zc)))
            assert hit[3]<1e-5 and abs(hit[1].y)>.999,('motor foot must land wholly on flat',x,zc,hit[3])
    motor=mach(rod((PX,PY,.19),(PX,PY,.347),.10,10),union=[block((PX-.030,PY,.19),(PX+.050,-3.40,.347))],cuts=[((PX,PY,.18),(PX,PY,.36),.024,10)])
    part(k,motor,FRM,'coaxial geared hinge drive')
    part(k,rod((PX,PY,.31),(PX,PY,.347),.021,10),JNT,'motor output shaft')
    # Opposed shoot bolts retract before swing; guide and cylinder are bored.
    for top in (True,False):
        bn='TopBolt' if top else 'BottomBolt';x,y=.47,-3.50
        a,b=(1.52,2.47) if top else (.065,1.00)
        z0,z1=(1.47,1.79) if top else (.755,1.075)
        housing=mach(rod((x,y,z0),(x,y,z1),.042,8),union=[block((x-.055,y,z0+.02),(x+.055,-3.455,z1-.02))],cuts=[((x,y,z0-.01),(x,y,z1+.01),.015,8)])
        seated(k,housing,FRM,'powered shoot bolt cylinder','Door')
        part(k,rod((x,y,a),(x,y,b),.014,8),JNT,'stainless captive shoot bolt',bn)
        gz=2.24 if top else .30
        guide=mach(rod((x,y,gz-.035),(x,y,gz+.035),.030,8),union=[block((x-.04,y,gz-.035),(x+.04,-3.455,gz+.035))],cuts=[((x,y,gz-.04),(x,y,gz+.04),.015,8)])
        seated(k,guide,SEC,'fitted shoot bolt guide','Door')
        # Receiver socket mounted forward of seal so bolt never crosses gasket.
        # Lower receiver stays below the sloping ramp at its forward rim.
        # Its 30 mm closed-bolt engagement remains in the bored socket.
        rz=2.46 if top else .075
        half=.025 if top else .020
        socket=mach(rod((x,y,rz-half),(x,y,rz+half),.03,8),union=[block((x-.043,y,rz-half),(x+.043,-3.32,rz+half))],cuts=[((x,y,rz-half-.005),(x,y,rz+half+.005),.015,8)])
        seated(k,socket,SEC,'jamb shoot bolt receiver')
    # Glove pull has two connected feet and a true opening.
    pull=mach(block((-.37,-3.59,1.15),(.18,-3.46,1.22)),boxes=[((-.095,-3.485,1.185),(.43,.10,.10))])
    seated(k,pull,JNT,'two-foot glove-clear pressure door pull','Door')
    # Entry bezel lights are separate flush pockets in seated shrouds.
    for s in (1,):
        m=common.frame((s*.845,-3.40,1.30),(0,-1,0),(0,0,1))
        with k.frame(m):
            bm=mach(common.loft([(.12,1.48,.018,-.012),(.12,1.48,.018,.02)]),boxes=[((0,0,.02),(.04,1.20,.014))])
            seated(k,bm,SEC,'entry status bezel')
            part(k,block((-.0198,-.5998,.013),(.0198,.5998,.02)),EMI,'flush entry status diffuser')

def ground(k):
    # Topology follows the actual square-octagon footing. Interior is a hole:
    # no terrain crosses the floor, foundation or entrance. Irregular outer
    # rings add regolith silhouette without intersecting the manufactured shell.
    bm=bmesh.new();rows=[]
    base=outline(3.30,0)
    points=[]
    for i in range(8):
        a,b=Vector(base[i]),Vector(base[(i+1)%8])
        points.extend(a.lerp(b,j/4) for j in range(4))
    for j,t in enumerate((0,.30,.65,1)):
        row=[]
        for i,p in enumerate(points):
            radius=1.05+.12*math.sin(i*1.73)+.12*math.cos(i*.77)
            v=p+p.normalized()*radius*t
            z=(0,.40,.18,0)[j]*(.8+.2*math.sin(i*.81))
            if p.y<0 and abs(v.x)<1.10:z=0
            row.append(bm.verts.new((v.x,v.y,z)))
        rows.append(row)
    for a,b in zip(rows,rows[1:]):
        for i in range(32):bm.faces.new((a[i],a[(i+1)%32],b[(i+1)%32],b[i]))
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:]);bmesh.ops.triangulate(bm,faces=bm.faces[:])
    k.emit(bm,ROOT,REG,False,convex=False,solid=False,exact=True,closed=False)
    common.LABELS.append('foundation fitted regolith apron with clear approach')

def interior(k):
    # Fixed utilities behind the usable room: a service cabinet and two
    # conduits with drilled saddle clamps and end glands on the pressure wall.
    seated(k,block((-.42,2.65,.65),(.42,2.93,1.15)),SEC,'rear wall service junction cabinet')
    for x in (-.60,.60):
        part(k,rod((x,2.43,.35),(x,2.43,2.35),.017,8),JNT,'fixed utility conduit')
        for z in (.35,1.35,2.35):
            clamp=mach(rod((x,2.43,z-.025),(x,2.43,z+.025),.033,8),
                union=[block((x-.042,2.43,z-.025),(x+.042,3.12-(z-.22)*.64/2.39+.02,z+.025))],
                cuts=[((x,2.43,z-.026),(x,2.43,z+.026),.017,8)])
            seated(k,clamp,FRM,'conduit saddle clamp and wall-seated foot')

def export_runtime(rig,objects,prepared=False):
    """Native prop exports with rigid clips and bone-parented attachment nodes."""
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
        bake_anim_force_startend_keying=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_materials='EXPORT')

def glazing_finish():
    mat=bpy.data.materials[GLASS]
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(0,0,0,1)
    bsdf.inputs['Metallic'].default_value=0
    bsdf.inputs['Roughness'].default_value=.15
    bsdf.inputs['Alpha'].default_value=.10
    bsdf.inputs['IOR'].default_value=1.46
    mat.diffuse_color=(0,0,0,.10)
    mat.surface_render_method='DITHERED'

def refresh_glazing():
    """Geometry-independent finish edit retains the verified rig and atlases."""
    bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    glazing_finish()
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    objects=[o for o in bpy.context.scene.objects if o.name.startswith('SK_')]
    markers,mount_info=fixture_mounts(rig,objects)
    export_runtime(rig,[*objects,*markers])
    report=json.loads((HERE/f'{NAME}_rig.json').read_text())
    report['glazing']=dict(material=GLASS,color=[0,0,0],opacity=.10)
    report['gizmos']=mount_info
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] black glazing, opacity 0.10; {len(markers)} fixture mounts; geometry and clips retained',flush=True)

def main():
    import perimeter_surface as surface
    if '--surface-only' in sys.argv:
        surface.refresh(HERE,NAME,kit,[],2.2,
            lambda rig,meshes,markers:export_runtime(rig,[*meshes,*markers],prepared=True))
        return
    if '--glazing-only' in sys.argv or '--mounts-only' in sys.argv:refresh_glazing();return
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.015,.62,.68),0,.34,2.0)
    kit.MATERIALS[REG]=((.27,.255,.235),0,.94,0)
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0)
    kit.SLOTS=list(kit.MATERIALS);kit.reset_scene();kit.build_materials()
    glazing_finish()
    # Use the same authored PBR set in native exports and runtime terrain.
    from lunar_material import install
    install(bpy.data.materials[REG])
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('Door',ROOT,'hinge',(PX,PY,1.2725),(0,0,1),(0,-1,0),(-105,0)),
        ('TopBolt','Door','slide',(.47,-3.50,1.52),(0,0,1),(0,0,1),(-.09,0)),
        ('BottomBolt','Door','slide',(.47,-3.50,1.0),(0,0,1),(0,0,1),(0,.09))]
    keys={'Door':[(0,0),(21,0),(81,-105),(96,-105)],'TopBolt':[(0,0),(15,-.09),(96,-.09)],'BottomBolt':[(0,0),(15,.09),(96,.09)]}
    kit.GROUPS=();kit.ANIMATIONS={'open':(False,'BEZIER',keys),'close':(False,'BEZIER',{bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in keys.items()})}
    kit.JOINT_SPECS=[(name,parent,kind,(p[0],p[1]+PLACEMENT_Y,p[2]),axis,flex,limits)
        for name,parent,kind,p,axis,flex,limits in kit.JOINT_SPECS]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    k.xf=Matrix.Translation((0,PLACEMENT_Y,0))
    body(k);entrance(k);interior(k)
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    pairs=common.exact_intersections(k)
    for p,label in zip(k.parts,common.LABELS):p.line=label
    kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    states.extend((f'sweep {a}',{'Door':-a,'TopBolt':-.09*dimensions.HEIGHT[NAME],'BottomBolt':.09*dimensions.HEIGHT[NAME]}) for a in range(0,106,3))
    for p,label in zip(k.parts,common.LABELS):p.line=label
    kit.check_motion(k,joints,states)
    # Whole motion envelope, not only the closed asset: all points must remain
    # within the 10 x 10 m placement square throughout both clips and sweeps.
    swept_lo=[5.,5.];swept_hi=[-5.,-5.]
    for _,state in states:
        matrices=kit.fk(joints,state)
        for part in k.parts:
            for p in part.verts:
                q=matrices[part.bone]@p
                for i in (0,1):
                    swept_lo[i]=min(swept_lo[i],q[i]);swept_hi[i]=max(swept_hi[i],q[i])
                assert -5<=q.x<=5 and -5<=q.y<=5,('10m motion envelope',part.line,list(q))
    ground(k)
    obj=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(obj,rig)
    sys.path.insert(0,str(MODELS/'architecture/lunar_dome'))
    from surface_audit import check_coplanar
    check_coplanar(obj)
    # Analytic visibility removal: ground-contact undersides and mutually
    # seated opposite faces only. Every interior face remains player-visible.
    bm=bmesh.new();bm.from_mesh(obj.data)
    hidden=[f for f in bm.faces if all(v.co.z<1e-6 for v in f.verts) and f.normal.z<-.5]
    bmesh.ops.delete(bm,geom=hidden,context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
    tris=kit.triangles(obj);assert tris<=5000,(tris,5000)
    lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    # Separate terrain node/material lets the eventual world material replace
    # dust independently of the building, preserving metre-based runtime UV0.
    terrain=obj.copy();terrain.data=obj.data.copy();terrain.name=surface.NAME
    bpy.context.scene.collection.objects.link(terrain)
    surface.annotate(terrain)
    for mesh,keep in ((obj,False),(terrain,True)):
        bm=bmesh.new();bm.from_mesh(mesh.data)
        discard=[f for f in bm.faces if (f.material_index==kit.SLOTS.index(REG))!=keep]
        bmesh.ops.delete(bm,geom=discard,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(mesh.data);bm.free()
    uv=terrain.data.uv_layers.new(name='TiledSurface')
    for loop in terrain.data.loops:
        p=terrain.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=(p.x/2,p.y/2)
    from material_uv import EFFECT_MATERIALS
    EFFECT_MATERIALS.add(REG)
    markers,mount_info=fixture_mounts(rig,[obj,terrain])
    export_runtime(rig,[obj,terrain,*markers])
    tris=sum(kit.triangles(o) for o in (obj,terrain));assert tris<=5000,(tris,5000)
    assert all(-5<=v.co.x<=5 and -5<=v.co.y<=5 for o in (obj,terrain) for v in o.data.vertices)
    rig['preview_poses']=json.dumps({'open':{'Door':{'rot':[-105,0,0]},'TopBolt':{'loc':[0,-.09,0]},'BottomBolt':{'loc':[0,.09,0]}}})
    bpy.context.scene['preview_actions']=json.dumps(['open','close'])
    bpy.context.scene['showcase_frame']=json.dumps(dict(lo=[-4.6,-4.6,0],hi=[4.6,4.6,3.45]))
    report=dict(name=NAME,triangles=tris,triangle_budget=5000,meshes={o.name:kit.triangles(o) for o in (obj,terrain)},bounds_m=dict(lo=lo,hi=hi),
        materials=kit.SLOTS,bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        passage_m=dict(width=1.35,height=2.25,threshold=.12,interior_height=3.08),
        ground_envelope_m=[10,10],
        swept_building_bounds_xy_m=dict(lo=swept_lo,hi=swept_hi),
        building_offset_y_m=PLACEMENT_Y,
        glazing=dict(material=GLASS,color=[0,0,0],opacity=.10),
        gizmos=mount_info,
        facade_layout=dict(construction='continuous pressure frame with recessed wall cells',
            border_fraction=.055,recess_m=.010,end_z_m=[.23,2.49]),
        checks=dict(exact_solid_pairs=pairs,connectivity=True,motion_states=len(states),coplanar=True),
        placement='floor centred; front -Y; library only; foundation-fitted regolith companion geometry',
        mechanics='Three interleaved coaxial hinges, geared hinge motor, opposed 90 mm captive shoot bolts; unlock before 105 degree outward swing.')
    surface.update_report(report,[obj,terrain],kit)
    dimensions.report(NAME,report,width=1.35,height=2.25,floors=[.12],ceilings=[3.20])
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; {len(k.parts)} authored parts',flush=True)

if __name__=='__main__':main()
