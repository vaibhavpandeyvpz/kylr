"""Static industrial luminaires in the KYLR prop language; headless Blender 5.2.

The fixture frame has +Z through the diffuser, +X across and +Y up its face.
All mating surfaces derive from the same outlines; unions are manufacturing
unibodies, never overlapping exported objects. No animation is authored.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bmesh
import bpy
from mathutils import Matrix, Vector

MODELS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODELS))
from material_uv import prepare_export

spec = importlib.util.spec_from_file_location('light_prop_kit', MODELS/'gameplay/item_table/model.py')
kit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kit
spec.loader.exec_module(kit)
ROOT = 'Root'
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
LENS = 'M_Light'
LABELS = []
CORNER_STEPS = 3


def outline(w, h, c, z):
    """Faceted rounded rectangle, full dimensions in metres."""
    x, y = w/2, h/2
    points = []
    for cx, cy, start in ((x-c,y-c,0),(-x+c,y-c,90),(-x+c,-y+c,180),(x-c,-y+c,270)):
        for i in range(CORNER_STEPS+1):
            a = math.radians(start+i*90/CORNER_STEPS)
            points.append((cx+c*math.cos(a),cy+c*math.sin(a),z))
    return points


def loft(stations):
    return kit.loft_rings([outline(*s) for s in stations])


def block(lo, hi):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    a, b = Vector(lo), Vector(hi)
    for v in bm.verts:
        v.co = (a+b)/2 + Vector(v.co[i]*(b[i]-a[i]) for i in range(3))
    return bm


def rod(a, b, r, n=12):
    a, b = Vector(a), Vector(b)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r, radius2=r, depth=(b-a).length)
    rotation = (b-a).to_track_quat('Z','Y').to_matrix()
    for v in bm.verts:
        v.co = rotation@v.co + (a+b)/2
    return bm


def emit(k, bm, mat, tag):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Exact triangulation is essential for concave boolean parts in the BVH.
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    if not all(e.is_manifold for e in bm.edges):
        raise AssertionError(f'{tag}: manufactured part is not closed/manifold')
    k.emit(bm, ROOT, mat, False, convex=False, exact=True)
    LABELS.append(tag)


def trim_seats(bm, parts):
    """Fish-mouth a welded support against the actual mating surfaces."""
    def temp(mesh):
        data=bpy.data.meshes.new('_seat')
        if isinstance(mesh,bmesh.types.BMesh):mesh.to_mesh(data);mesh.free()
        else:data.from_pydata(mesh.verts,[],mesh.faces)
        obj=bpy.data.objects.new('_seat',data)
        bpy.context.scene.collection.objects.link(obj)
        return obj
    obj=temp(bm);tools=[temp(p) for p in parts]
    for other in tools:
        mod=obj.modifiers.new('weld seat','BOOLEAN')
        mod.operation,mod.solver,mod.object='DIFFERENCE','EXACT',other
    result=bmesh.new();result.from_object(obj,bpy.context.evaluated_depsgraph_get())
    for other in [obj,*tools]:
        data=other.data;bpy.data.objects.remove(other);bpy.data.meshes.remove(data)
    return result


def ring(w, h, c, iw, ih, ic, z0, z1):
    bm = bmesh.new()
    rows = [[bm.verts.new(p) for p in outline(*s)] for s in
            ((w,h,c,z0),(w,h,c,z1),(iw,ih,ic,z1),(iw,ih,ic,z0))]
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(len(a)):
            j=(i+1)%len(a)
            bm.faces.new((a[i],a[j],b[j],b[i]))
    return bm


def frame(at, forward, face_up):
    n = Vector(forward).normalized()
    v = Vector(face_up)
    v = (v-n*v.dot(n)).normalized()
    u = v.cross(n).normalized()
    m = Matrix((u,v,n)).transposed().to_4x4()
    m.translation = at
    return m


def bolt(k, x, y, z, tag, r=.0045):
    """Flush hex socket cap; no fake shank intersecting the housing."""
    bm = rod((x,y,z),(x,y,z+.0025),r,8)
    bm = kit.machine(bm,cuts=[((x,y,z+.0011),(x,y,z+.004),r*.48,6)])
    emit(k,bm,JNT,tag)


def fixture(k, w, h, depth, tag, flood=False):
    """Lofted die-cast back, removable bezel, gasket and seated opal lens."""
    c = min(h*.23,.055)
    ow, oh, oc = w-.038, h-.038, max(.008,c-.019)
    iw, ih, ic = ow-.008, oh-.008, max(.005,oc-.004)
    seat = depth-.029
    split = depth-.014
    # Continuous taper and swept shoulders, unlike a stack of chamfered boxes.
    body = loft([(w-.020,h-.020,c-.008,0),(w-.008,h-.008,c-.003,.012),
                 (w,h,c,depth*.6),(w,h,c,split)])
    # prism_bm is centred; the recess starts precisely on the seating plane.
    body = kit.machine(body,union=([rod((s*(w/2-.024),0,.020),(s*(w/2+.008),0,.020),.018)
                                   for s in (-1,1)] if flood else []),
                       subtract=[(outline(ow,oh,oc,seat+.10),(0,0,1),.20)],
                       cuts=([((s*(w/2-.028),0,.020),(s*(w/2+.028),0,.020),.006,12)
                              for s in (-1,1)] if flood else []))
    emit(k,body,PRI,tag+' casting')
    bezel=ring(w,h,c,ow,oh,oc,split,depth)
    strips=[]
    if not flood:
        for x in ((-.38,.38) if w>1 else (0,)):
            for y in (-h/2+.009,h/2-.009):
                length=.18 if w>1 else .22
                strips.append(((x,y,depth+.004),(length,.004,.012)))
        bezel=kit.machine(bezel,boxes=strips)
    emit(k,bezel,PRI,tag+' bezel')
    for centre,size in strips:
        x,y,_=centre;length=size[0]
        emit(k,block((x-length/2,y-.002,depth-.002),(x+length/2,y+.002,depth)),EMI,tag+' flush indicator')
    emit(k,ring(ow,oh,oc,iw,ih,ic,seat,depth-.008),FRM,tag+' gasket')
    emit(k,loft([(iw,ih,ic,seat),(iw,ih,ic,depth-.008)]),LENS,tag+' diffuser')
    for s in (-1,1):
        for t in (-1,1):
            if flood and s!=t:
                continue
            bolt(k,s*(w/2-.011),t*(h/2-c*.66),depth,tag+' bezel screw')
    if flood:
        # Cooling fins are fused into the casting, extending back from its rear
        # plane, not independent strips buried through the exterior shell.
        fins=[block((x-.003,-h*.31,-.018),(x+.003,h*.31,.003))
              for x in (-.075,-.025,.025,.075)]
        # One connected heatsink with flat backplate, seated on the rear face.
        heatsink=kit.machine(block((-.115,-h*.35,-.003),(.115,h*.35,0)),union=fins)
        # Fins stop at the backplate's exposed plane to avoid housing intrusion.
        heatsink=kit.machine(heatsink,boxes=[((0,0,.05),(.4,.4,.1))])
        emit(k,heatsink,SEC,tag+' heatsink')
    return (0,0,depth-.008), (w,h,depth)


def batten(k, beams):
    # Origin on the ceiling, body entirely below it. Two cast mounting feet.
    m=frame((0,0,-.020),(0,0,-1),(0,-1,0))
    with k.frame(m):
        for x in (-.40,.40):
            foot=kit.machine(loft([(.09,.24,.009,-.020),(.09,.24,.009,-.014)]),
                             union=[loft([(.065,.10,.009,-.015),(.065,.10,.009,0)])])
            for v in foot.verts:v.co.x+=x
            foot=kit.machine(foot,cuts=[((x,y,-.025),(x,y,-.012),.0032,12) for y in (-.105,.105)])
            emit(k,foot,SEC,'ceiling saddle')
            for y in (-.105,.105):bolt(k,x,y,-.014,'ceiling mounting screw')
        p,_=fixture(k,1.20,.18,.080,'batten')
    beams.append(('LightProjection',m@Vector(p),(0,0,-1),(0,-1,0),70,8))


def sconce(k, beams):
    m=frame((0,-.014,0),(0,-1,0),(0,0,1))
    with k.frame(m):
        emit(k,loft([(.43,.30,.035,-.014),(.43,.30,.035,-.009),(.416,.286,.031,0)]),SEC,'wall backplate')
        p,_=fixture(k,.40,.27,.100,'sconce')
        # One welded guard. Four feet end exactly at the front bezel plane.
        cage=ring(.40,.27,.05,.376,.246,.038,.127,.139)
        additions=[]
        for y in (-.080,-.030,.080):
            additions.append(block((-.195,y-.005,.127),(.195,y+.005,.139)))
        for x in (-.115,.115):
            additions.append(block((x-.006,-.125,.127),(x+.006,.125,.139)))
        for x in (-.185,.185):
            for y in (-.072,.072):
                additions.append(block((x-.006,y-.009,.100),(x+.006,y+.009,.132)))
        cage=kit.machine(cage,union=additions)
        emit(k,cage,SEC,'welded impact guard')
    beams.append(('LightProjection',m@Vector(p),(0,-1,0),(0,0,1),80,6))


def pole(k, beams):
    # 4.2 m class service mast, rooted at its floor flange. Fixed head aiming.
    base=loft([(.40,.40,.075,0),(.40,.40,.075,.022),(.37,.37,.065,.034)])
    gussets=[]
    for a in (0,90,180,270):
        g=kit.prism_bm([(.045,-.008,.034),(.157,-.008,.034),(.060,-.008,.26)],.016,(0,1,0))
        rot=Matrix.Rotation(math.radians(a),3,'Z')
        for v in g.verts:v.co=rot@v.co
        gussets.append(g)
    def shaft_radius(z):return .061+(z-.36)*(.046-.061)/(3.77-.36)
    stations=[(.034,.076),(.27,.076),(.36,.061)]
    for z in (1.10,2.60):
        stations.extend([(z-.02,shaft_radius(z-.02)),(z,.072),
                         (z+.055,.072),(z+.075,shaft_radius(z+.075))])
    stations.extend([(3.77,.046),(3.84,.046)])
    mast=kit.loft_rings([kit.ring_xy(0,0,r,z,12) for z,r in stations])
    # Flush status inlays on a real shaft facet, following its exact taper.
    nxy=Vector((math.sin(math.pi/12),-math.cos(math.pi/12),0))
    normal=nxy+Vector((0,0,(.061-.046)/(3.77-.36)*math.cos(math.pi/12)))
    status_frames=[];status_cutters=[]
    for z in (.65,1.90,3.45):
        at=nxy*(shaft_radius(z)*math.cos(math.pi/12))+Vector((0,0,z))
        m=frame(at,normal,(0,0,1));status_frames.append(m)
        cutter=loft([(.014,.18,.003,-.002),(.014,.18,.003,.010)])
        for v in cutter.verts:v.co=m@v.co
        status_cutters.append(cutter)
    # Mast and foot ribs are the one cast/fabricated structure above the flange.
    mast=kit.machine(mast,union=gussets)
    # The slots are subtractive pockets; only their opal inserts are emissive.
    for cutter in status_cutters:
        cutter.verts.index_update()
        part=SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],
                             faces=[[v.index for v in f.verts] for f in cutter.faces])
        mast=trim_seats(mast,[part]);cutter.free()
    emit(k,mast,PRI,'mast and foot gussets')
    # Paint the integral coupling bands grey without any overlay geometry.
    for face in k.bm.faces:
        z=face.calc_center_median().z
        if any(level<=z<=level+.055 for level in (1.10,2.60)):
            face.material_index=kit.SLOTS.index(SEC)
    for m in status_frames:
        with k.frame(m):emit(k,loft([(.014,.18,.003,-.002),(.014,.18,.003,0)]),EMI,'flush mast indicator')
    emit(k,base,SEC,'anchor flange')
    for x in (-.14,.14):
        for y in (-.14,.14):
            bolt(k,x,y,.034,'foundation anchor',.009)
    arm=loft([(2.65,.105,.025,3.80),(2.65,.105,.025,3.86),(2.60,.09,.02,3.885)])
    arm=kit.machine(arm,union=[block((-1.20,.032,3.82),(1.20,.120,3.86))],
                    cuts=[((0,0,3.78),(0,0,3.91),.046,12)])
    emit(k,arm,SEC,'head crossarm')
    # Clamp sleeve above the crossarm seats on the mast end and arm top.
    emit(k,rod((0,0,3.84),(0,0,3.885),.045,12),JNT,'mast end plug')
    for index,(x,z,drop) in enumerate(((-1.08,4.075,.38),(-.43,4.075,.55),
                                      (.43,4.075,.55),(1.08,4.075,.38),
                                      (-.84,3.55,.72),(.84,3.55,.72)),1):
        forward=Vector((math.copysign(.16,x),-1,-drop)).normalized()
        m=frame((x,-.008,z),forward,(0,0,1))
        with k.frame(m):
            p,_=fixture(k,.32,.26,.085,'head '+str(index),True)
        # Head's adjustment axis is its face-horizontal X, with bored cast ears.
        # A continuous U-shaped yoke behind the head. Clear of the heatsink.
        with k.frame(m):
            yoke=block((-.185,-.012,-.110),(.185,.012,-.090))
            additions=[block((s*.178-.007,-.012,-.105),(s*.178+.007,.024,.033)) for s in (-1,1)]
            yoke=kit.machine(yoke,union=additions,cuts=[((-.20,0,.020),(.20,0,.020),.006,12)])
            emit(k,yoke,SEC,'head '+str(index)+' yoke')
            # Shaft only in the empty bored region; capped at yoke's outer faces.
            for s in (-1,1):
                emit(k,rod((s*.133,0,.020),(s*.185,0,.020),.006,12),JNT,'retained trunnion')
                emit(k,rod((s*.185,0,.020),(s*.189,0,.020),.010,8),JNT,'trunnion lock cap')
        # Crossarm to the yoke's rear centre: square welded support, hidden feed.
        anchor=m@Vector((0,0,-.110))
        start=Vector((x,.100,3.86 if z>3.8 else 3.82))
        # Oblique support ends are trimmed at the arm and the yoke seating plane.
        direction=(anchor-start).normalized()
        support=rod(start-direction*.008,anchor+direction*.008,.012,8)
        # Trim fish-mouth weld seats to the real arm and bracket surfaces.
        support=trim_seats(support,[p for p,label in zip(k.parts,LABELS)
                                   if label in ('head crossarm',f'head {index} yoke')])
        emit(k,support,JNT,'head '+str(index)+' support')
        beams.append((f'LightProjection{index:02}',m@Vector(p),forward,m.to_3x3()@Vector((0,1,0)),45,24))


def exact_intersections(k):
    """Independent exact Boolean solid-volume audit before visibility culling.

    Contact is allowed; overlapping solid interiors beyond 10 mm3 are rejected
    (float precision at 4 m causes sub-micron coplanar intersection slivers).
    Rotated trunnions and seat surfaces therefore get checked in real geometry.
    """
    objects=[]
    for i,p in enumerate(k.parts):
        mesh=bpy.data.meshes.new('_audit')
        mesh.from_pydata(p.verts,[],p.faces)
        obj=bpy.data.objects.new('_audit',mesh)
        bpy.context.scene.collection.objects.link(obj)
        objects.append(obj)
    checked=0
    try:
        for i,a in enumerate(k.parts):
            for j,b in enumerate(k.parts[:i]):
                if any(min(a.hi[d],b.hi[d])-max(a.lo[d],b.lo[d])<2e-6 for d in range(3)):
                    continue
                mod=objects[i].modifiers.new('intersection audit','BOOLEAN')
                mod.operation,mod.solver,mod.object='INTERSECT','EXACT',objects[j]
                bm=bmesh.new();bm.from_object(objects[i],bpy.context.evaluated_depsgraph_get())
                volume=abs(bm.calc_volume());bm.free();objects[i].modifiers.remove(mod)
                checked+=1
                assert volume<1e-8,(LABELS[i],LABELS[j],volume)
    finally:
        for obj in objects:
            mesh=obj.data;bpy.data.objects.remove(obj);bpy.data.meshes.remove(mesh)
    print(f'[{kit.NAME}] {checked} solid intersection pairs checked',flush=True)
    return checked


def gizmos(rig, beams):
    result=[]
    for name,at,fwd,up,cone,reach in beams:
        fwd,up=Vector(fwd),Vector(up)
        m=Matrix((fwd.cross(up),fwd,up)).transposed().to_4x4();m.translation=at
        obj=bpy.data.objects.new(name,None)
        obj.empty_display_type='ARROWS';obj.empty_display_size=.10
        bpy.context.scene.collection.objects.link(obj)
        obj.parent=rig;obj.matrix_world=m
        result.append(obj)
    return result


def build(folder):
    global CORNER_STEPS
    folder=Path(folder);name=folder.name;title=''.join(s.title() for s in name.split('_'))
    kit.NAME,kit.TITLE=name,title
    CORNER_STEPS=1 if name=='pole_light' else 3
    kit.MATERIALS[LENS]=((.86,.94,1.0),0,.27,3.0)
    # Reference turquoise service indicators; structural finishes remain native.
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5)
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit();beams=[]
    rig['preview_poses']=json.dumps({})
    LABELS.clear()
    {'batten_light':batten,'sconce_light':sconce,'pole_light':pole}[name](k,beams)
    pairs=exact_intersections(k)
    kit.check_connectivity(k,joints,[])
    print(f'[{name}] {len(k.parts)} connected manufactured parts',flush=True)
    obj=k.to_object('SK_'+title);kit.skin(obj,rig)
    if '--draft' not in sys.argv:
        # Sconce is a surface-mounted wall prop; batten hangs under the ceiling.
        placement=(frame((0,0,0),(0,-1,0),(0,0,1)) if name=='sconce_light' else
                   frame((0,0,0),(0,0,-1),(0,-1,0)) if name=='batten_light' else Matrix.Identity(4))
        kit.cull_unseen(obj,rig,joints,[],[('fixed',{})],(-.0001,-.0001),(.0001,.0001),placement)
    kit.check_coplanar(obj)
    tris=kit.triangles(obj);assert tris<=5000,(name,tris)
    emitters=gizmos(rig,beams)
    lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    assert not bpy.data.actions
    if '--draft' not in sys.argv:
        prepare_export([rig,obj,*emitters],folder,name)
        kit.select_only([rig,obj,*emitters])
        bpy.ops.export_scene.fbx(filepath=str(folder/f'{name}.fbx'),use_selection=True,
            object_types={'MESH','ARMATURE','EMPTY'},global_scale=1.,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
            use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
            primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
            bake_anim=False,path_mode='COPY',embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(folder/f'{name}.glb'),export_format='GLB',
            use_selection=True,export_yup=True,export_apply=False,export_skins=True,
            export_def_bones=True,export_animations=False,export_materials='EXPORT')
    report={'name':name,'static':True,'animations':[],'triangles':tris,'triangle_budget':5000,
            'meshes':{'SK_'+title:tris},'materials':[m.name for m in obj.data.materials if any(p.material_index==list(obj.data.materials).index(m) for p in obj.data.polygons)],
            'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,
            'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
            'gizmos':[{'name':n,'bone':ROOT,'origin':list(at),'forward':list(f),'up':list(u),
                       'cone_half_angle_deg':cone,'range_m':reach,'godot':'-Z points along projection'} for n,at,f,u,cone,reach in beams],
            'checks':{'connected_parts':len(LABELS),'exact_solid_pairs':pairs,'no_solid_intersections':True,
                      'coplanar':True,'budget':True,'no_actions':True},
            'placement':{'batten_light':'ceiling centre z=0, emitter down -Z',
                         'sconce_light':'wall centre y=0, emitter outward -Y',
                         'pole_light':'floor flange centre z=0; front -Y'}[name]}
    (folder/f'{name}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/f'{name}.blend'))
    print(f'[{name}] PASS: {tris} triangles; bounds {lo} .. {hi}; {len(beams)} projections',flush=True)
