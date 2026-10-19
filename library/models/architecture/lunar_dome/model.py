"""6 x 6 m hemispherical lunar architecture with a real hinged entrance.

Reference: rib-and-ring glazed habitats (user photos 2-4), adapted to KYLR.
All panels share their seat boundaries: no rib overlays or stacked shells.
Rigid Root / Door / Lock mechanism; open/close clips; library only.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Rubber': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

HERE = Path(__file__).resolve().parent
NAME, TITLE = HERE.name, 'LunarDome'
MODELS = HERE.parents[1]
sys.path.insert(0, str(MODELS))
from material_uv import prepare_export
sys.path.insert(0,str(HERE.parent))
import dimensions
spec = importlib.util.spec_from_file_location('dome_prop_kit', MODELS/'gameplay/item_table/model.py')
kit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kit
spec.loader.exec_module(kit)
kit.NAME, kit.TITLE = NAME, TITLE
kit.MATERIALS.pop('M_Emissive')
kit.MATERIALS['M_Glass'] = ((.12,.22,.27),0.,.16,0.)
kit.MATERIALS['M_Rubber'] = ((.015,.017,.019),0.,.85,0.)
kit.SLOTS = list(kit.MATERIALS)
PRI, SEC, FRM, JNT = kit.PRI, kit.SEC, kit.FRM, kit.JNT
GLASS, ROOT = 'M_Glass', 'Root'
RUBBER='M_Rubber'
N = 20
PHI = (0., .40, .78, 1.15, 1.445)
R, H, Z = 2.92, 2.92, .18
WALL = .045
BUDGET = 5000
PX,PY=.590,-2.970
HINGES=(.43,1.82)
DOOR_FRONT,DOOR_BACK=-2.927,-2.885
LOCK_Y,LOCK_Z=-2.910,1.04
SWING=110
ENTRY=[(-2.94,.64,2.19),(-2.86,.70,2.25),(-2.25,.70,2.25),(-1.85,.58,2.16)]


def object_from_bm(bm, name, mat=None):
    if mat:
        for f in bm.faces: f.material_index=kit.SLOTS.index(mat)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cavity=bm.faces.layers.int.get('Cavity')
    if cavity:
        bmesh.ops.reverse_faces(bm,faces=[f for f in bm.faces if f[cavity]])
    bmesh.ops.triangulate(bm,faces=bm.faces[:])
    mesh=bpy.data.meshes.new(name+'Mesh')
    for slot in kit.SLOTS: mesh.materials.append(bpy.data.materials[slot])
    bm.to_mesh(mesh); bm.free()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def boolean(base, tool, operation):
    kit.select_only([base])
    mod=base.modifiers.new(operation,'BOOLEAN')
    mod.operation,mod.solver,mod.object=operation,'EXACT',tool
    mod.use_hole_tolerant=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bm=bmesh.new();bm.from_mesh(base.data)
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm,edges=bm.edges[:],dist=1e-7)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(base.data)
    assert all(e.is_manifold for e in bm.edges), (tool.name,'broken Boolean boundary')
    bm.free()
    mesh=tool.data
    bpy.data.objects.remove(tool,do_unlink=True)
    bpy.data.meshes.remove(mesh)


def ring(r,z):
    return [(r*math.cos(i*math.tau/N),r*math.sin(i*math.tau/N),z) for i in range(N)]


def profile_ring(profile, mat, name):
    bm=bmesh.new()
    rows=[[bm.verts.new(p) for p in ring(r,z)] for r,z in profile]
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(N):
            j=(i+1)%N
            bm.faces.new((a[i],a[j],b[j],b[i]))
    return object_from_bm(bm,name,mat)


def outline(w,bottom,top,c=.13):
    return [(-w+c,bottom),(w-c,bottom),(w,bottom+c),(w,top-c),
            (w-c,top),(-w+c,top),(-w,top-c),(-w,bottom+c)]


def tunnel(shape, y0, y1, mat, name):
    return object_from_bm(kit.prism_bm([(x,(y0+y1)/2,z) for x,z in shape],y1-y0,(0,1,0)),name,mat)


def canopy():
    """Lofted closed shell with integral ribs and flush gasket/glass seats.

    Each cell has nested bilinear loops, so boundaries lie on the same facet.
    Both sides use the same glass boundary. The pane is 29 mm thick, inset
    8 mm each side from the 45 mm frame; gasket bevels cover its edge.
    Shared cell vertices are welded before booleans, not overlapping strips.
    """
    bm=bmesh.new()
    cavity=bm.faces.layers.int.new('Cavity')
    def point(a,p,inside=False):
        r=(R-(WALL if inside else 0))*math.cos(p)
        return Vector((r*math.cos(a),r*math.sin(a),Z+(H-(WALL if inside else 0))*math.sin(p)))
    def inset(corners,u,v,depth,normal):
        def at(s,t):return corners[0].lerp(corners[1],s).lerp(corners[3].lerp(corners[2],s),t)-normal*depth
        return [at(u,v),at(1-u,v),at(1-u,1-v),at(u,1-v)]
    for i in range(N):
        a,b=i*math.tau/N,(i+1)*math.tau/N
        for p,q in zip(PHI,PHI[1:]):
            for inside in (False,True):
                corners=[point(a,p,inside),point(b,p,inside),point(b,q,inside),point(a,q,inside)]
                normal=(corners[1]-corners[0]).cross(corners[3]-corners[0]).normalized()
                if inside:normal=-normal
                width=min((corners[1]-corners[0]).length,(corners[2]-corners[3]).length)
                height=(corners[3]-corners[0]).length
                assert .036/width<.5 and .036/height<.5, (width,height)
                # 25 mm half rib, 11 mm gasket. Crown widens radial ribs.
                loops=[corners,inset(corners,.025/width,.025/height,0,normal),
                       inset(corners,.036/width,.036/height,.008,normal)]
                rows=[[bm.verts.new(v) for v in pts] for pts in loops]
                for ra,rb,mat in zip(rows,rows[1:],(PRI,FRM)):
                    for j in range(4):
                        f=bm.faces.new((ra[j],ra[(j+1)%4],rb[(j+1)%4],rb[j]))
                        f.material_index=kit.SLOTS.index(mat)
                        f[cavity]=int(inside)
                f=bm.faces.new(rows[-1]);f.material_index=kit.SLOTS.index(GLASS)
                f[cavity]=int(inside)
    bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
    # Loft the foundation, floor and crown directly from the canopy boundaries.
    # Shared ring vertices avoid coplanar Boolean intersections at glazing seats.
    def closest(p):return min(bm.verts,key=lambda v:(v.co-p).length_squared)
    for p,inside,profile,mat in [
        (PHI[0],False,[(2.97,.14),(3.,.10),(3.,0)],SEC),
        (PHI[0],True,[(2.76,.18),(2.76,.10)],SEC),
        (PHI[-1],False,[(.35,3.11),(.30,3.16)],PRI),
        (PHI[-1],True,[(.30,3.05)],PRI)]:
        prev=[closest(point(i*math.tau/N,p,inside)) for i in range(N)]
        for r,z in profile:
            row=[bm.verts.new(v) for v in ring(r,z)]
            for i in range(N):
                j=(i+1)%N
                f=bm.faces.new((prev[i],prev[j],row[j],row[i]))
                f.material_index=kit.SLOTS.index(mat)
                f[cavity]=int(inside)
            prev=row
        f=bm.faces.new(prev);f.material_index=kit.SLOTS.index(mat)
        f[cavity]=int(inside)
    assert all(e.is_manifold for e in bm.edges), 'canopy has open or multiple edges'
    return object_from_bm(bm,'_Canopy')


def manufactured_body():
    body=canopy()
    # Remove the circular floor/collar crescent before adding the vestibule.
    # Its own loft supplies the threshold; the dome floor never projects ahead
    # of that footprint or through its chamfered lower corners.
    boolean(body,object_from_bm(block((-.716,-3.2,-.02),(.716,-2.86,.181)),
        '_FoundationDoorNotch',SEC),'DIFFERENCE')
    # A lofted chamfered vestibule, fused into the curved pressure shell.
    stations=[]
    for y,w,top in ENTRY:
        stations.append([(x,y,z) for x,z in outline(w,0,top)])
    hood=object_from_bm(kit.loft_rings(stations),'_Entrance',PRI)
    boolean(body,hood,'UNION')
    corridor=tunnel(outline(.51,.10,2.04,.12),-3.2,-1.70,FRM,'_CorridorCut')
    boolean(body,corridor,'DIFFERENCE')
    # Machined hatch counterbore, wider than the clear passage, stops at its seat.
    recess=tunnel(outline(.57,.095,2.105,.13),-3.1,-2.875,FRM,'_DoorSeatCut')
    boolean(body,recess,'DIFFERENCE')
    # Blind strike hood closes the front of the latch crossing. It is fused
    # into the free-side jamb, with 2 mm clearance from the seated leaf and
    # a clear bolt passage. No bolt end is exposed outside the rim.
    hood=object_from_bm(block((-.590,DOOR_FRONT,LOCK_Z-.025),
                              (-.550,LOCK_Y-.010,LOCK_Z+.025)), '_StrikeHood',FRM)
    boolean(body,hood,'UNION')
    for z in HINGES:
        for a,b in ((z-.10,z-.041),(z+.041,z+.10)):
            sleeve=object_from_bm(hinge_sleeve(a,b,False),'_FixedKnuckle',SEC)
            boolean(body,sleeve,'UNION')
    receiver=object_from_bm(block((-.66,LOCK_Y-.013,LOCK_Z-.013),(-.54,LOCK_Y+.013,LOCK_Z+.013)),'_LockReceiver',JNT)
    boolean(body,receiver,'DIFFERENCE')
    return body


def build_door(k):
    # Rear face seal on a proper rabbet; the free edge has a swept clearance.
    seal=tunnel(outline(.57,.095,2.105,.13),DOOR_BACK,-2.875,RUBBER,'_Seal')
    cut=tunnel(outline(.51,.10,2.04,.12),-3.1,-2.80,FRM,'_SealCut')
    boolean(seal,cut,'DIFFERENCE')
    emit_object(k,seal)
    leaf=tunnel(outline(.548,.111,2.089,.13),DOOR_FRONT,DOOR_BACK,PRI,'_Door')
    for z in HINGES:
        sleeve=object_from_bm(hinge_sleeve(z-.040,z+.040,True),'_MovingKnuckle',SEC)
        boolean(leaf,sleeve,'UNION')
    # Guided shoot bolt retracts completely before any hinge rotation.
    guide=object_from_bm(block((-.66,LOCK_Y-.010,LOCK_Z-.010),(-.24,LOCK_Y+.010,LOCK_Z+.010)),'_BoltGuide',FRM)
    boolean(leaf,guide,'DIFFERENCE')
    # Inboard thumb grip, at hand height on the free side of the leaf. The
    # pocket accommodates the entire 75 mm stroke and leaves a 148 mm edge land.
    slot=object_from_bm(block((-.40,DOOR_FRONT-.01,LOCK_Z-.050),(-.26,LOCK_Y,LOCK_Z+.050)),'_HandlePocket',FRM)
    boolean(leaf,slot,'DIFFERENCE')
    # Recessed inspection pane; no overlaid black/glass squares.
    win=outline(.15,1.34,1.64,.035)
    boolean(leaf,tunnel(win,-3.05,-2.80,FRM,'_WindowCut'),'DIFFERENCE')
    emit_object(k,leaf,'Door')
    for z in HINGES:
        k.axes.append(('Door',Vector((PX,PY,z)),Vector((0,0,1)),.040))
    glass=tunnel(win,DOOR_FRONT+.002,DOOR_BACK-.004,GLASS,'_DoorOptic')
    emit_object(k,glass,'Door')
    for z in HINGES:
        k.cyl((PX,PY,z-.106),(PX,PY,z+.106),.010,ROOT,JNT,segs=8)
        for a,b in ((z-.111,z-.106),(z+.106,z+.111)):
            k.cyl((PX,PY,a),(PX,PY,b),.016,ROOT,JNT,segs=6)
    bolt=object_from_bm(block((-.610,LOCK_Y-.009,LOCK_Z-.009),
                              (-.340,LOCK_Y+.009,LOCK_Z+.009)),'_ShootBolt',JNT)
    grip=object_from_bm(block((-.385,DOOR_FRONT+.002,LOCK_Z-.035),
                              (-.355,LOCK_Y+.009,LOCK_Z+.035)),'_ThumbGrip',JNT)
    boolean(bolt,grip,'UNION')
    emit_object(k,bolt,'Lock')


def shroud_seal(body):
    """Silicone joint follows the actual shroud/spherical-shell intersection.

    A 14 mm expanded shroud minus its exact original loft defines the joint
    land. Intersect it with the finished dome, then cut that same pocket from
    the structural body. This seats the seal at the top and both sides of the
    sphere cut, with shared boundaries and no laid-over or floating trim.
    """
    rim=body.copy();rim.data=body.data.copy()
    bpy.context.scene.collection.objects.link(rim)
    def loft(extra,name):
        rows=[[(x,y,z) for x,z in outline(w+extra,0,top+extra)] for y,w,top in ENTRY]
        return object_from_bm(kit.loft_rings(rows),name,RUBBER)
    pocket=loft(.014,'_SiliconeJointSeat')
    # A 0.1 mm retaining land avoids tangent/coplanar Boolean surfaces at
    # the original loft while keeping the seated joint visually continuous.
    boolean(pocket,loft(.0001,'_ShroudSealInner'),'DIFFERENCE')
    # The three-sided seal terminates on the foundation shoulder.
    boolean(pocket,object_from_bm(block((-1,-3.2,-.02),(1,-1.7,.181)),
        '_SealFootTermination',RUBBER),'DIFFERENCE')
    cutter=pocket.copy();cutter.data=pocket.data.copy()
    bpy.context.scene.collection.objects.link(cutter)
    boolean(rim,cutter,'INTERSECT')
    for face in rim.data.polygons:face.material_index=kit.SLOTS.index(RUBBER)
    boolean(body,pocket,'DIFFERENCE')
    return rim


def block(lo,hi):
    bm=bmesh.new();bmesh.ops.create_cube(bm,size=1)
    for v in bm.verts:
        v.co=Vector([(lo[i]+hi[i])/2+v.co[i]*(hi[i]-lo[i]) for i in range(3)])
    return bm


def hinge_sleeve(a,b,moving):
    """Bored extruded D-section; its neck and bore have shared end-ring vertices."""
    if moving:
        outer=[(PX+.024,PY),(PX+.024,PY+.020),(PX+.012,-2.905),
               (.530,-2.905),(.530,PY+.012),(PX-.017,PY-.017),
               (PX,PY-.024),(PX+.017,PY-.017)]
    else:
        outer=[(PX+.026,PY),(.620,-2.920),(PX,-2.920),
               (.570,-2.920),(PX-.026,PY),(PX-.018384,PY-.018384),
               (PX,PY-.026),(PX+.018384,PY-.018384)]
    inner=[(PX+.011*math.cos(i*math.tau/8),PY+.011*math.sin(i*math.tau/8)) for i in range(8)]
    bm=bmesh.new()
    ob,ib,ot,it=[[bm.verts.new((x,y,z)) for x,y in points] for z in (a,b) for points in (outer,inner)]
    for i in range(8):
        j=(i+1)%8
        for face in ((ob[i],ob[j],ot[j],ot[i]),(ib[j],ib[i],it[i],it[j]),
                     (ob[j],ob[i],ib[i],ib[j]),(ot[i],ot[j],it[j],it[i])):
            bm.faces.new(face)
    return bm


def cylinder(a,b,r,n):
    bm=bmesh.new()
    bmesh.ops.create_cone(bm,cap_ends=True,segments=n,radius1=r,radius2=r,depth=(Vector(b)-Vector(a)).length)
    rot=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_matrix()
    for v in bm.verts:v.co=rot@v.co+(Vector(a)+Vector(b))/2
    return bm


def emit_object(k,obj,bone=ROOT):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=bm.faces[:])
    # Blender booleans retain face slots because all operands use the same palette.
    mats=[f.material_index for f in bm.faces]
    made=k.emit(bm,bone,PRI,False,convex=False,exact=True)
    for f,m in zip(made,mats):f.material_index=m
    mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)


def check_part_clearance(k,quiet=False,cross_bone_only=False):
    """Reject interpenetrating manufactured parts; mating surfaces may touch.

    Surface points are tested against both parity rays of the existing exact
    part audit, including recessed seats and blind bores, before hidden-face
    removal. A 10 micrometre tolerance accommodates Blender's float vertices.
    """
    for i,a in enumerate(k.parts):
        for b in k.parts[i+1:]:
            if cross_bone_only and a.bone==b.bone:continue
            if any(a.hi[j]<b.lo[j]-1e-5 or b.hi[j]<a.lo[j]-1e-5 for j in range(3)):continue
            for source,target in ((a,b),(b,a)):
                pts=list(source.verts)
                for f in source.faces:
                    c=sum((source.verts[v] for v in f),Vector())/len(f)
                    pts.append(c)
                    pts.extend(c.lerp(source.verts[v],.8) for v in f)
                for p in pts:
                    if any(p[j]<target.lo[j] or p[j]>target.hi[j] for j in range(3)):continue
                    distance=target.bvh.find_nearest(p)[3]
                    assert distance is not None
                    if distance>1e-5 and target.inside(p):
                        raise AssertionError(('part penetration',i,source.line,target.line,tuple(p),distance))
    if not quiet:print(f'[{NAME}] all {len(k.parts)} parts: connectivity and sampled exact clearance passed',flush=True)


def export(objects,stem):
    if not stem.endswith('_col'):prepare_export(objects,HERE,stem)
    else:
        # Keep each convex island's corners shared through native exports.
        for obj in objects:
            if obj.type=='MESH':
                for face in obj.data.polygons:face.use_smooth=True
    rig=next(o for o in objects if o.type=='ARMATURE')
    # All hinge/slide keys are baked by the kit; export has no runtime constraints.
    for bone in rig.pose.bones:
        for constraint in list(bone.constraints):bone.constraints.remove(constraint)
    kit.select_only(objects)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{stem}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_skins=True,export_animations=True,
        export_animation_mode='ACTIONS',export_anim_single_armature=True,
        export_reset_pose_bones=True,export_force_sampling=True,export_extras=True,
        export_materials='NONE' if stem.endswith('_col') else 'EXPORT')
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{stem}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1.,apply_unit_scale=True,apply_scale_options='FBX_SCALE_ALL',
        axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,mesh_smooth_type='OFF',
        add_leaf_bones=False,primary_bone_axis='Y',secondary_bone_axis='X',
        use_armature_deform_only=True,bake_anim=True,bake_anim_simplify_factor=0,
        bake_anim_use_all_bones=False,bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,use_custom_props=True,path_mode='COPY',embed_textures=True)


def main():
    if '--collision-exports-only' in sys.argv:
        bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}_col.blend'))
        objects=[o for o in bpy.context.scene.objects if o.type=='ARMATURE' or (o.type=='MESH' and o.name.startswith('SK_') and 'Col' in o.name)]
        export(objects,NAME+'_col')
        return
    kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS]
    bsdf=glass.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Alpha'].default_value=.32
    bsdf.inputs['IOR'].default_value=1.46
    glass.diffuse_color=(*glass.diffuse_color[:3],.32)
    glass.surface_render_method='DITHERED'
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('Door',ROOT,'hinge',(PX,PY,HINGES[0]),(0,0,1),(0,-1,0),(0,SWING)),
        ('Lock','Door','slide',(-.50,LOCK_Y,LOCK_Z),(1,0,0),(0,0,1),(0,.075))]
    opening={'Lock':[(0,0),(12,.075),(72,.075)],'Door':[(0,0),(18,0),(66,SWING),(72,SWING)]}
    closing={b:[(72-f,v) for f,v in reversed(keys)] for b,keys in opening.items()}
    kit.ANIMATIONS={'open':(False,'BEZIER',opening),'close':(False,'BEZIER',closing)}
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    k=kit.Kit()
    body=manufactured_body();rim=shroud_seal(body)
    emit_object(k,body);emit_object(k,rim);build_door(k)
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    resize=dimensions.matrix(NAME)
    k.axes=[(bone,resize@mid,axis,half*dimensions.HEIGHT[NAME]) for bone,mid,axis,half in k.axes]
    kit.check_connectivity(k,joints,[])
    kit.check_joint_alignment(k,joints)
    check_part_clearance(k)
    actions=kit.build_actions(rig,joints,[])
    states=kit.action_states(actions,joints)
    states += [(f'sweep {a}',{'Door':a,'Lock':.075}) for a in range(SWING+1)]
    kit.check_motion(k,joints,states)
    # Re-test seated bodies too: shared motion audit intentionally skips contacts.
    original=k.parts
    tested=set()
    for tag,state in states:
        signature=tuple(sorted((b,round(v,7)) for b,v in state.items()))
        if signature in tested:continue
        tested.add(signature)
        matrices=kit.fk(joints,state)
        k.parts=[p.moved(matrices[p.bone]) for p in original]
        check_part_clearance(k,quiet=True,cross_bone_only=True)
    k.parts=original
    print(f'[{NAME}] seated interfaces: {len(tested)} distinct motion states pass exact sampled clearance',flush=True)
    obj=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(obj,rig)
    obj['glazing_is_pressure_ceiling']=True
    sys.path.insert(0,str(HERE))
    from surface_audit import check_coplanar
    check_coplanar(obj)
    # Analytic static visibility cull: only the ground-contact face is hidden.
    # A ray cull treating glazing as opaque would incorrectly delete the interior.
    bm=bmesh.new();bm.from_mesh(obj.data)
    buried=[f for f in bm.faces if all(v.co.z<1e-6 for v in f.verts)]
    bmesh.ops.delete(bm,geom=buried,context='FACES_ONLY')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(obj.data);bm.free()
    lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    assert all(abs(a-b)<1e-5 for a,b in zip(lo,dimensions.point(NAME,(-3,PY-.026,0)))),lo
    assert all(abs(a-b)<1e-5 for a,b in zip(hi,dimensions.point(NAME,(3,3,3.16)))),hi
    tris=kit.triangles(obj)
    assert tris<=BUDGET,(tris,BUDGET)
    rig['preview_poses']=json.dumps({'open':{'Door':{'rot':[SWING,0,0]},'Lock':{'loc':[0,.075*dimensions.HEIGHT[NAME],0]}}})
    bpy.context.scene['preview_actions']=json.dumps(['open','close'])
    bpy.context.scene['showcase_frame']=json.dumps({'lo':[-3,-4.2,0],'hi':[3,3,3.16]})
    import light_mounts
    markers,fixture_info=light_mounts.install_default(rig,[obj],NAME)
    export([obj,rig,*markers],NAME)
    report={'name':NAME,'static':False,'animations':['open','close'],'triangles':tris,'triangle_budget':BUDGET,
        'bounds_m':{'lo':lo,'hi':hi},'materials':kit.SLOTS,'authored_parts':len(k.parts),
        'bones':[dict(name=j.name,parent=j.parent,kind=j.kind,head=list(j.pivot),axis=list(j.axis),limits=j.limits) for j in joints.values()],
        'placement':'floor-centred; front -Y; footprint includes entrance',
        'mechanics':'20 radial ribs; hemispherical canopy; integrated vestibule; two bored three-knuckle hinges; retracting shoot bolt',
        'interfaces':{'frame_depth_mm':45,'pane_depth_mm':29,'pane_recess_mm':8,
            'gasket_width_mm':11,'hinge_radial_clearance_mm':1,'hinge_axial_clearance_mm':1,
            'floor_notch_front_y_m':-2.86,'shroud_silicone_joint_width_mm':14,
            'silicone_joint_seated':True},
        'hemisphere':dict(radius_m=R*dimensions.PLAN[NAME],vertical_radius_m=H*dimensions.HEIGHT[NAME],centre_z_m=Z*dimensions.HEIGHT[NAME],uniform_scale_required=True),
        'passage_m':dict(width=1.02,height=1.94,threshold=.10,interior_height=2.95),
        'checks':{'connectivity':True,'sampled_part_clearance':True,'hinge_alignment':True,'motion_states':len(states),'boolean_manifold':True,'envelope':True,'budget':True},
        'visibility':'Ground underside removed analytically; booleans remove internal union faces; glazing-visible interior retained.'}
    dimensions.report(NAME,report,width=1.02,height=1.94,floors=[.10],ceilings=[3.05])
    report['gizmos']=fixture_info
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; hemisphere; hinged open/close',flush=True)


if __name__=='__main__':main()
