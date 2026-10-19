"""Rigged solar tracker tower, metres, front -Y. Run in headless Blender 5.2.

Manufactured lofts and boolean unions; shared exact contact/overlap audits.
Powered azimuth/elevation; individual module hinges are manually indexed.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
    'M_Solar': 'Diffuse',
}
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
kit, ROOT = common.kit, common.ROOT
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
NAME, TITLE = 'solar_tower', 'SolarTower'
SOLAR = 'M_Solar'
BRZ = 'M_Bronze'
HEIGHT, PANEL_W, PANEL_H = 3.0, .78, .426
ROW_Z = [.90 + .46*i for i in range(5)]
block, rod, loft = common.block, common.rod, common.loft
AZIMUTH, ELEVATION = 'Azimuth', 'Elevation'
FIXED_LABELS = {'welded foundation frame, diagonal webs and mounting hub',
    'flush captive hex foundation fastener',
    'lofted sealed azimuth gearbox with fused front service pod',
    'flush gearbox inspection cover', 'azimuth bearing weather seal'}
AZIMUTH_LABELS = {'azimuth slew bearing core', 'exposed azimuth ring gear',
    'azimuth bearing retaining flange',
    'cast elevation clevis with coaxial machined bearing bores',
    'seated elevation thrust washer between mast and clevis'}
PANEL_FRAMES = []
SERVICE_STATIONS = [(.24,.20,.020,-.030),(.25,.20,.022,.030),(.21,.16,.017,.150)]


def emit(k,bm,mat,label):
    bone=ROOT if label in FIXED_LABELS else AZIMUTH if label in AZIMUTH_LABELS else ELEVATION
    old=common.ROOT
    common.ROOT=bone
    try:
        common.emit(k,bm,mat,label)
    finally:
        common.ROOT=old


def animation_specs():
    n=240
    track={AZIMUTH:[(f,8*math.sin(math.tau*f/n)) for f in range(n+1)],
           ELEVATION:[(f,3*math.sin(2*math.tau*f/n)) for f in range(n+1)]}
    def service(reverse):
        frames=[]
        for f in range(181):
            t=f/180;u=t*t*(3-2*t)
            frames.append((f,-65*(1-u if reverse else u)))
        return {AZIMUTH:[(f,0) for f in range(181)],ELEVATION:frames}
    return {'track':(True,'LINEAR',track),
            'service_lower':(False,'LINEAR',service(False)),
            'service_raise':(False,'LINEAR',service(True))}


def machine(bm, **kw):
    for mesh in [bm, *kw.get('union', [])]:
        bmesh.ops.recalc_face_normals(mesh, faces=mesh.faces[:])
    out = kit.machine(bm, **kw)
    bmesh.ops.remove_doubles(out, verts=out.verts[:], dist=0.000001)
    return out

def move(bm, at):
    for v in bm.verts:
        v.co += Vector(at)
    return bm


def transformed(bm, m):
    for v in bm.verts:
        v.co = m @ v.co
    return bm


def drum(stations, n=12):
    return kit.loft_rings([kit.ring_xy(0, 0, r, z, n) for z, r in stations])


def gear(radius, teeth, z0, z1, bore=0, phase=0):
    """Backlash-cut straight flanks, using the weapons' 20-degree tooth form."""
    module = 2*radius/teeth
    add, ded = module*.70,module*.85
    half = .42*math.tau*radius/teeth/2
    ring=[]
    for i in range(teeth):
        a=phase+i*math.tau/teeth
        for r,w in ((radius-ded,-half-ded*.364),
                    (radius+add,-half+add*.364),
                    (radius+add,half-add*.364),
                    (radius-ded,half+ded*.364)):
            ring.append((r*math.cos(a+w/r),r*math.sin(a+w/r)))
    bm=kit.loft_rings([[(x,y,z) for x,y in ring] for z in (z0,z1)])
    sides=8 if bore>.1 else 12
    return machine(bm,cuts=[((0,0,z0-.01),(0,0,z1+.01),bore/math.cos(math.pi/sides),sides)]) if bore else bm


def rect(w,h,z):
    return [(-w/2,-h/2,z),(w/2,-h/2,z),(w/2,h/2,z),(-w/2,h/2,z)]


def pipe(points,r=.005):
    """A closed swept line with mitred elbows and explicit seating ends."""
    pts=list(map(Vector,points)); rings=[]
    for i,p in enumerate(pts):
        axis=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        ref=Vector((0,0,1)) if abs(axis.z)<.9 else Vector((1,0,0))
        u=axis.cross(ref).normalized(); v=axis.cross(u)
        rings.append([p+r*(u*math.cos(j*math.tau/3)+v*math.sin(j*math.tau/3)) for j in range(3)])
    return kit.loft_rings(rings)


def cut(body, cutter):
    # Use the exact mesh, not an approximate rectangular bounding cutter.
    from types import SimpleNamespace
    bmesh.ops.recalc_face_normals(body, faces=body.faces[:])
    bmesh.ops.recalc_face_normals(cutter, faces=cutter.faces[:])
    cutter.verts.index_update()
    p = SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],
                        faces=[[v.index for v in f.verts] for f in cutter.faces])
    result = common.trim_seats(body, [p])
    cutter.free()
    bmesh.ops.remove_doubles(result, verts=result.verts[:], dist=0.000001)
    return result


def flush_screw(k, m, radius=.009):
    with k.frame(m):
        emit(k,rod((0,0,-.004),(0,0,0),radius-.0001,6), JNT,
             'flush captive hex foundation fastener')


def base(k):
    # Welded square foundation, crossed load webs and central bearing seat.
    foundation = common.ring(1.04,1.04,.025,.87,.87,.012,0,.065)
    webs = [rod((sx*.465,sy*.465,.037),(0,0,.037),.026,4)
            for sx in (-1,1) for sy in (-1,1)]
    foundation = machine(foundation, union=[*webs, drum([(0,.275),(.065,.275)])])
    screws = []
    for x in (-.477,.477):
        for y in (-.477,.477):
            m = common.frame((x,y,.065),(0,0,1),(0,1,0))
            screws.append(m)
    foundation = machine(foundation,cuts=[((x,y,.061),(x,y,.075),.012,6)
        for x in (-.477,.477) for y in (-.477,.477)])
    emit(k,foundation,SEC,'welded foundation frame, diagonal webs and mounting hub')
    for m in screws:
        flush_screw(k,m,.012)
    housing = drum([(.065,.275),(.085,.286),(.120,.286),(.145,.235),
                    (.325,.235),(.350,.255)],12)
    # A real service/gearbox fairing is fused to the round housing; its cover
    # fits in a cut seat. Azimuth teeth and wiring are inside this enclosure.
    service_frame = common.frame((0,-.20,.235),(0,-1,0),(0,0,1))
    service = transformed(loft(SERVICE_STATIONS),service_frame)
    housing = machine(housing,union=[service])
    cover_frame = common.frame((0,-.350,.235),(0,-1,0),(0,0,1))
    housing = cut(housing, transformed(loft([(.14,.11,.01,-.004),
                                           (.14,.11,.01,.030)]),cover_frame))
    emit(k,housing,PRI,'lofted sealed azimuth gearbox with fused front service pod')
    with k.frame(cover_frame):
        emit(k,loft([(.138,.108,.009,-.004),(.138,.108,.009,0)]),SEC,
             'flush gearbox inspection cover')
    emit(k,drum([(.350,.255),(.359,.255)]),FRM,'azimuth bearing weather seal')
    emit(k,drum([(.359,.180),(.377,.180)]),JNT,'azimuth slew bearing core')
    emit(k,gear(.242,12,.359,.377,.1803),BRZ,'exposed azimuth ring gear')
    emit(k,drum([(.377,.255),(.400,.210)]),JNT,'azimuth bearing retaining flange')
    # Monolithic cast fork; no cheek is buried in another exported solid.
    fork = drum([(.400,.210),(.430,.210),(.452,.17)],12)
    cheeks = [move(loft([(.062,.23,.017,.418),(.062,.23,.017,.625),
                         (.062,.18,.017,.715)]),(s*.205,0,0)) for s in (-1,1)]
    fork = machine(fork,union=cheeks,
        cuts=[((-.26,0,.635),(.26,0,.635),.0543,8)])
    emit(k,fork,SEC,'cast elevation clevis with coaxial machined bearing bores')
    emit(k,rod((-.236,0,.635),(.236,0,.635),.050,8),JNT,'retained elevation axle')
    for s in (-1,1):
        emit(k,rod((s*.236,0,.635),(s*.244,0,.635),.069,8),JNT,
             'axle retention end cap')
        emit(k,machine(rod((s*.16,0,.635),(s*.174,0,.635),.070,8),
            cuts=[((s*.15,0,.635),(s*.18,0,.635),.0543,8)]),JNT,
             'seated elevation thrust washer between mast and clevis')


def row_frame(i, x=0):
    # Shallow faceted bow: each flat module sits square on its own rear rail.
    angle = math.radians((i-2)*4)
    m = common.frame((x,-.135+.013*(i-2)**2,ROW_Z[i]),(0,-1,0),(0,0,1))
    return m @ Matrix.Rotation(angle,4,'X')


def mast(k):
    body = loft([(.32,.20,.025,.560),(.32,.20,.025,.745),
                 (.22,.20,.02,.785)])
    pieces = []
    for x in (-.09,.09):
        for y in (-.085,.085):
            pieces.append(rod((x,y,.730),(x,y,2.972),.017,4))
    for z in [.77,*[v+.22 for v in ROW_Z],2.98]:
        pieces.append(block((-.108,-.105,z-.014),(.108,.105,min(HEIGHT,z+.020))))
    diagonals = []
    # One diagonal per bay on each face; no crossing bars intersect arbitrarily.
    for i in range(5):
        za,zb = [.77,1.12,1.58,2.04,2.50,2.98][i:i+2]
        a,b = (-.09,.09) if i%2==0 else (.09,-.09)
        for y in ((-.085,) if i%2==0 else (.085,)):
            diagonals.append(rod((a,y,za),(b,y,zb),.011,4))
        # Fore/aft diagonal faces resist racking. The rigid welded collars
        # brace the narrow lateral faces without duplicating every diagonal.
    rails=[]
    for i in range(5):
        m = row_frame(i)
        rail=block((-.948,-.027,-.093),(.948,.027,-.0665))
        # One broad saddle distributes each rail's load to both mast chords.
        pads=[block((-.116,-.025,-.240),(.116,.025,-.075))]
        rails.append(transformed(machine(rail,union=pads),m))
    body = machine(body,union=pieces,
        cuts=[((-.18,0,.635),(.18,0,.635),.0502,8)])
    emit(k,body,PRI,'welded mast unibody with five continuous module rails and saddles')
    structural = [k.parts[-1]]
    for rail in rails:
        rail=common.trim_seats(rail,structural)
        rail=cut(rail,block((-.021,.105,.75),(.021,.140,2.98)))
        bmesh.ops.remove_doubles(rail,verts=rail.verts[:],dist=.000001)
        edges=[e for e in rail.edges if e.is_boundary]
        if edges:bmesh.ops.holes_fill(rail,edges=edges,sides=0)
        emit(k,rail,PRI,'welded row crossrail with fish-mouthed mast saddles')
        structural.append(k.parts[-1])
    braces = []
    for bm in diagonals:
        bm = common.trim_seats(bm, [*structural, *braces])
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=.000001)
        # Exact coplanar subtraction can leave an uncapped planar seat loop.
        boundary = [e for e in bm.edges if e.is_boundary]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
        emit(k,bm,PRI,"fish-mouthed welded diagonal brace")
        braces.append(k.parts[-1])
    # Rear electrical trunk is a closed conduit supported at both ends and at
    # every row. The module leads are hidden inside the structural crossrails.
    feed = block((-.021,.105,.75),(.021,.140,2.98))
    emit(k,feed,FRM,'rear protected DC cable trunk seated on mast collars')


def panels(k):
    for i in range(5):
        for s in (-1,1):
            m = row_frame(i,s*.54)
            PANEL_FRAMES.append(m)
            with k.frame(m):
                shell = loft([(PANEL_W-.014,PANEL_H-.014,.009,0),
                              (PANEL_W,PANEL_H,.009,.042)])
                opening = (PANEL_W-.030,PANEL_H-.030)
                # Backsheet-integral hinge barrel, with a real horizontal bore.
                boss=block((-.38,-.019,-.040),(.38,.019,.003))
                shell = machine(shell,union=[boss],subtract=[(
                    rect(*opening,.113),(0,0,1),.20)])
                shell = machine(shell,cuts=[((-.40,0,-.022),(.40,0,-.022),.0122,4)])
                emit(k,shell,PRI,f'row {i+1} module {s:+} lofted frame and sealed backsheet')
                emit(k,kit.loft_rings([rect(*opening,z) for z in (.013,.039)]),SOLAR,
                     'flush laminated photovoltaic cell plate')
                # Inner and outer bearing ears are one seated carrier casting.
                for x in (-.397,.397):
                    ear=block((x-.011,-.027,-.0665),(x+.011,.027,-.001))
                    ear=machine(ear,cuts=[((x-.02,0,-.022),(x+.02,0,-.022),.012,4)])
                    emit(k,ear,SEC,'module hinge bearing ear seated directly on crossrail')
                emit(k,rod((-.408,0,-.022),(.408,0,-.022),.012,4),JNT,'module continuous retained hinge axle')
                for x in (-.408,.408):
                    if x<0 and not (s==1 and i in (0,2,4)):
                        continue
                    emit(k,rod((x,0,-.022),(x+math.copysign(.003,x),0,-.022),.018,4),JNT,
                         'module axle hex retention cap')
                terminal=block((s*-.285-.030,.072,-.015),(s*-.285+.030,.117,0))
                emit(k,terminal,SEC,'sealed panel junction box seated on backsheet')


def services(k):
    # Five paired-row stages: their gears lie on the true X hinge axes.
    for i in range(5):
        m=row_frame(i)
        with k.frame(m):
            motor=block((-.065,-.115,-.095),(.065,-.035,-.067))
            # Mount flange rises square from the fixed row crossrail.
            saddle=block((-.060,-.040,-.095),(.060,.016,-.067))
            motor=machine(motor,union=[saddle])
            motor=common.trim_seats(transformed(motor,k.xf),k.parts)
            motor=transformed(motor,k.xf.inverted())
            bmesh.ops.remove_doubles(motor,verts=motor.verts[:],dist=.000001)
            edges=[e for e in motor.edges if e.is_boundary]
            if edges:bmesh.ops.holes_fill(motor,edges=edges,sides=0)
            if i==2:
                emit(k,motor,SEC,'central DC combiner enclosure and crossrail flange')
            else:
                motor.free()
            gm=common.frame((.119,0,-.022),(1,0,0),(0,1,0))
            if i in (0,2,4):
                with k.frame(gm):
                    emit(k,gear(.026,6,0,.010,phase=0),BRZ,'row hinge toothed indexing wheel')
                dog=block((.1205,-.035,-.040),(.143,-.020,-.017))
                dog=common.trim_seats(transformed(dog,k.xf),k.parts)
                dog=transformed(dog,k.xf.inverted())
                bmesh.ops.remove_doubles(dog,verts=dog.verts[:],dist=.000001)
                edges=[e for e in dog.edges if e.is_boundary]
                if edges:bmesh.ops.holes_fill(dog,edges=edges,sides=0)
                emit(k,dog,JNT,'seated indexing lock dog on hinge wheel')
            # Electrical leads enter the rear trunk's side, square to its flat.
        for s in (-1,1):
            pm=row_frame(i,s*.54)
            a=pm@Vector((s*-.285,.0945,-.015))
            first=pm@Vector((s*-.285,.0945,-.050))
            end=Vector((s*.021,.126,ROW_Z[i]+.0945))
            corner=Vector((s*.065,.126,end.z))
            routed=pipe([a,first,Vector((s*.16,.126,end.z)),corner,end],.004)
            routed=common.trim_seats(routed,k.parts)
            bmesh.ops.remove_doubles(routed,verts=routed.verts[:],dist=.000001)
            edges=[e for e in routed.edges if e.is_boundary]
            if edges:bmesh.ops.holes_fill(routed,edges=edges,sides=0)
            emit(k,routed,FRM,'panel DC lead with strain-relief loop to rear trunk')


def solar_material():
    """Baked cell/busbar pattern, not thousands of decorative mesh strips."""
    import numpy as np
    w,h = 768,384
    yy,xx = np.mgrid[0:h,0:w]
    cx,cy = xx%64,yy%64
    pixels = np.empty((h,w,4),dtype=np.float32)
    pixels[:,:,:3] = (.032,.060,.105)
    variation = ((xx//64+yy//64)%3)*.003
    pixels[:,:,:3] += variation[:,:,None]
    seam = (cx<2)|(cy<2)|(cx>61)|(cy>61)
    pixels[seam,:3] = (.15,.19,.23)
    fine = ((cx%8)==3)&~seam
    pixels[fine,:3] = (.10,.14,.19)
    bus = ((cx==21)|(cx==43))&~seam
    pixels[bus,:3] = (.36,.40,.43)
    pixels[:,:,3] = 1
    img = bpy.data.images.new('SolarTower_CellLaminate',width=w,height=h)
    img.pixels.foreach_set(pixels.ravel())
    img.filepath_raw = str(HERE/f'{NAME}_cells.png')
    img.file_format = 'PNG'; img.save(); img.pack()
    mat = bpy.data.materials[SOLAR]
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = img
    uv = mat.node_tree.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'SolarSurface'
    mat.node_tree.links.new(uv.outputs['UV'],tex.inputs['Vector'])
    bsdf = mat.node_tree.nodes['Principled BSDF']
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    bsdf.inputs['Coat Weight'].default_value = .35
    bsdf.inputs['Coat Roughness'].default_value = .18


def assign_solar_uv(body):
    uv = body.data.uv_layers.new(name='SolarSurface')
    for f in body.data.polygons:
        if body.data.materials[f.material_index].name != SOLAR:
            continue
        centre = sum((body.data.vertices[v].co for v in f.vertices),Vector())/len(f.vertices)
        m = min(PANEL_FRAMES,key=lambda m:(m.translation-centre).length_squared).inverted()
        for loop in f.loop_indices:
            p = m @ body.data.vertices[body.data.loops[loop].vertex_index].co
            uv.data[loop].uv = (p.x/(PANEL_W-.030)+.5,p.y/(PANEL_H-.030)+.5)


def export_runtime(rig,body):
    kit.select_only([rig,body])
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


def main():
    common.CORNER_STEPS = 1
    common.LABELS.clear(); PANEL_FRAMES.clear()
    kit.NAME,kit.TITLE = NAME,TITLE
    kit.MATERIALS.pop(EMI)
    kit.MATERIALS[SOLAR] = ((.032,.06,.105),.25,.29,0)
    kit.MATERIALS[BRZ] = ((.30,.20,.095),.8,.32,0)
    kit.SLOTS = list(kit.MATERIALS)
    kit.reset_scene(); kit.build_materials(); solar_material()
    kit.JOINT_SPECS = [(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        (AZIMUTH,ROOT,'hinge',(0,0,.359),(0,0,1),(0,-1,0),(-180,180)),
        (ELEVATION,AZIMUTH,'hinge',(0,0,.635),(1,0,0),(0,0,1),(-65,6))]
    kit.GROUPS=()
    kit.ANIMATIONS=animation_specs()
    joints = kit.resolve_joints(); rig = kit.build_rig(joints,[])
    k = kit.Kit(); base(k); mast(k); panels(k); services(k)
    pairs = common.exact_intersections(k)
    kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[])
    states=kit.action_states(actions,joints)
    states += [(f'azimuth_{a}',{AZIMUTH:a,ELEVATION:e})
               for a in range(-180,181,15) for e in (-65,-30,0,6)]
    kit.check_motion(k,joints,states)
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps([
        dict(label=label,vertices=[list(v) for v in p.verts])
        for label,p in zip(common.LABELS,k.parts)],indent=2))
    body = k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints)); kit.skin(body,rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
    kit.check_coplanar(body)
    tris = kit.triangles(body)
    lo = [min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in body.data.vertices) for i in range(3)]
    assert abs(lo[2])<1e-6 and abs(hi[2]-HEIGHT)<1e-6,(lo,hi)
    assign_solar_uv(body)
    if '--draft' not in sys.argv:
        assert tris<=5000,tris
        # Preserve the repeated physical cell pattern while also creating the
        # required unique per-material authoring atlas on UV1.
        import material_uv
        material_uv.EFFECT_MATERIALS.add(SOLAR)
        common.prepare_export([rig,body],HERE,NAME)
        export_runtime(rig,body)
    report = dict(name=NAME,static=False,animations={name:dict(frames=[0,int(action.frame_range[1])],
        fps=30,loop=kit.ANIMATIONS[name][0]) for name,action in actions.items()},units='metres',triangles=tris,
        triangle_budget=5000,bounds_m=dict(lo=lo,hi=hi),tensor_height_m=1.753,
        materials=list(kit.MATERIALS),bones=[dict(name=j.name,kind=j.kind,parent=j.parent) for j in joints.values()],
        joints=[dict(bone=j.name,type=j.kind,parent=j.parent,pivot=list(j.pivot),
                     axis=list(j.axis),range=list(j.limits) if j.limits else None) for j in joints.values()],
        placement='floor centre z=0; photovoltaic/front -Y; up +Z',
        panel_modules=10,module_dimensions_m=[PANEL_W,PANEL_H,.042],
        checks=dict(connected_parts=len(k.parts),exact_solid_pairs=pairs,
                    no_solid_intersections=True,coplanar=True,motion_states=len(states)))
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    rig['preview_poses'] = json.dumps({'service':{ELEVATION:{'rot':[-65,0,0]}},
        'tracking_limit':{AZIMUTH:{'rot':[8,0,0]},ELEVATION:{'rot':[6,0,0]}}})
    scene=bpy.context.scene
    scene['preview_actions']=json.dumps(['track','service_lower','service_raise'])
    scene['showcase_frame']=json.dumps(dict(lo=[-1.0,-.55,0],hi=[1.0,2.30,3.01]))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; {len(k.parts)} connected manufactured parts; {lo} .. {hi}',flush=True)


if __name__ == '__main__':
    main()
