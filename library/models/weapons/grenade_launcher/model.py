"""Single-bore grenade launcher: lathed receiver and detachable circular drum.
Scripted Blender 5.2 source; library-only, metres, forward -Y.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Metallic',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Metal': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Diffuse',
}
import importlib.util,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('grenade_framework',HERE.parent/'rocket_launcher/model.py')
k=importlib.util.module_from_spec(spec);sys.modules[spec.name]=k;spec.loader.exec_module(k)
k.NAME,k.TITLE,k.HERE='grenade_launcher','GrenadeLauncher',HERE
k.BLEND_PATH=HERE/'grenade_launcher.blend';k.RIG_JSON_PATH=HERE/'grenade_launcher_rig.json'
PRIMARY_HEX='#746b5a'
_srgb=[int(PRIMARY_HEX[i:i+2],16)/255 for i in (1,3,5)]
_linear=tuple(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in _srgb)
k.MATERIALS[k.PRI]=(_linear,.25,.55,0)
k.MATERIALS[k.FRM]=((.29,.29,.30),1,.5,0)
k.AXIS_Z=.2;k.TUBES=['Barrel'];k.TUBE_AZ=(90,);k.TUBE_RC=0
k.ROCKET='LoadedGrenade';k.ROCKET_L=.082;k.ROCKET_R=.016;k.BAND_R=.017
k.SEAT_Y=-.123;k.LAUNCH_TRAVEL=.135;k.FINS=[]
k.ROCKET_SPEC={'TITLE':'GrenadeLauncherRocket','JOINT_SPECS':[('GrenadeBody',None,'fixed',(0,0,0),k.UP,k.UP,None)],'PISTON_SPECS':[],'ANIMATIONS':{},'PREVIEW_STATES':{},'FK_TEST_STATE':{}}
k.GRIP_G=(0,.1464,.0865);k.TRIGGER_PIVOT=(0,.0869,.138)
k.GUARD_FRONT=(.0549,.0629);k.GUARD_BOTTOM=(.0815,.007,.0864)
k.TRIGGER_BLOCK=((.0629,.1044),.1305);k.BELLY_REAR=.159
k.MAG_Y=(-.108,.008);k.MAG_W=.080;k.MAG_TOP=.220;k.MAG_TRAVEL=.015
k.LATCH_PIVOT=(0,-.121,.150)
k.GRIP_ALONG['Left']=.072
k.GRIP_POSE['Left']=({'Index':10,'Middle':19,'Ring':24,'Little':27},(24,25,16))
k.JOINT_SPECS=[('Root',None,'fixed',(0,0,0),k.UP,k.UP,None),
 ('Barrel','Root','slide',(0,-.15,.2),k.BACK,None,(0,.01)),
 (k.ROCKET,'Barrel','slide',(0,k.SEAT_Y,.2),k.FWD,None,(0,k.LAUNCH_TRAVEL)),
 ('FeedRam','Root','slide',(0,.055,.2),k.BACK,None,(0,.153)),
 (k.TRIGGER,'Root','hinge',k.TRIGGER_PIVOT,(1,0,0),k.DOWN,(0,k.TRIGGER_PULL)),
 (k.MAG,'Root','slide',(0,-.05,.22),k.DOWN,None,(0,k.MAG_TRAVEL)),
 (k.LATCH,'Root','hinge',k.LATCH_PIVOT,(-1,0,0),k.DOWN,(0,k.LATCH_OPEN))]
k.ANIMATIONS={'idle':(True,'LINEAR',{k.TRIGGER:[(0,0),(60,0)]}),
 'fire':(False,'LINEAR',{k.TRIGGER:k.eased([(0,0),(2,k.TRIGGER_PULL),(8,k.TRIGGER_PULL),(12,0),(32,0)]),
 k.ROCKET:[(0,0),(2,0),(3,.02),(4,k.LAUNCH_TRAVEL),(5,0)],'Barrel':k.recoil_keys(2,32),
 'FeedRam':k.eased([(0,0),(4,0),(12,.153),(22,.153),(30,0),(32,0)])}),
 'cycle':(False,'LINEAR',{'FeedRam':k.eased([(0,0),(8,.153),(20,.153),(32,0)])}),
 'mag_release':k.ANIMATIONS['mag_release'],'mag_insert':k.ANIMATIONS['mag_insert']}
k.HIDE_KEYS={'fire':{k.ROCKET:[(0,1),(4,0)]}}
k.ANIMATIONS['mag_release'][2]['FeedRam']=k.eased([(0,0),(5,.153),(12,.153)])
k.ANIMATIONS['mag_insert'][2]['FeedRam']=k.eased([(0,.153),(8,.153),(12,0)])
k.PREVIEW_STATES={'recoil':{'Barrel':.01,'FeedRam':.153},'breech_open':{'FeedRam':.153},'mag_out':{k.MAG:.015,k.LATCH:k.LATCH_OPEN,'FeedRam':.153}}
k.PREVIEW_VIEWS={x:['front_left','right'] for x in k.PREVIEW_STATES}
k.FK_TEST_STATE={'Barrel':.01,'FeedRam':.02,k.ROCKET:.03,k.TRIGGER:6,k.MAG:.01,k.LATCH:20}
k.SHOWCASE=list(k.ANIMATIONS)
def expand(st):
    # Locked short recoil carries the pusher with the loaded barrel. During
    # feeding and reload the independent actuator withdraws it farther.
    out=dict(st)
    if 'Barrel' in out:out.setdefault('FeedRam',out['Barrel'])
    return out
k.expand=expand
original_hand_frame=k.hand_frame

def axial(kit,profile,bone,mat,segs=24,centre=(0,0,.2)):
    k.revolve(kit,profile,centre,k.BACK,(1,0,0),bone,mat,segs,loop=True)

def support_section(y):
    # A short lathed bearing has a machined palm flat below it.
    w=.041;low=.127;rb=.016
    arc=[(w-rb+rb*math.cos(math.radians(a)),low+rb+rb*math.sin(math.radians(a))) for a in (270,310,360)]
    top=[(w,.182),(w-.008,.19)]
    return [(x,y,z) for x,z in top+[(-x,z) for x,z in reversed(top)]+[(-x,z) for x,z in reversed(arc)]+arc]

def hand_frame(side):
    if side=='Right':return original_hand_frame(side)
    n=Vector((math.sin(math.radians(20)),0,-math.cos(math.radians(20))));z=-n
    y0=Vector((-math.sin(math.radians(50)),-math.cos(math.radians(50)),0));y=(y0-z*y0.dot(z)).normalized();x=y.cross(z)
    pts=pack_support_section(-.04);contact=(Vector(pts[-3])+Vector(pts[-2]))/2
    return contact-z*k.PALM[3]-y*.072,x,y,z
k.hand_frame=hand_frame


def union_mesh(*meshes):
    """Exact union of the bearing ring and palm saddle into one casting."""
    objs=[]
    for i,bm in enumerate(meshes):
        me=bpy.data.meshes.new(f'_trunnion_{i}');bm.to_mesh(me);bm.free()
        ob=bpy.data.objects.new(me.name,me);bpy.context.scene.collection.objects.link(ob);objs.append(ob)
    base=objs[0]
    for ob in objs[1:]:
        mod=base.modifiers.new('integral saddle','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=ob
    bm=bmesh.new();bm.from_object(base,bpy.context.evaluated_depsgraph_get())
    for ob in objs:
        me=ob.data;bpy.data.objects.remove(ob);bpy.data.meshes.remove(me)
    return bm

def pressure_union(kit,az,yy):
    """Recessed flat seat, steel flange, hex compression nut, inserted tube."""
    n=k.radial(az);c=Vector((0,yy,.2))
    k.revolve(kit,[(.0026,.050),(.008,.050),(.008,.055),(.006,.059),(.006,.062),(.0026,.062)],
        c,n,k.BACK,'Root',k.JNT,6,loop=True)
    kit.cyl(c+n*.060,c+n*.066,.0055,'Root',k.BRZ,segs=6)
    return c+n*.064,c+n*.076

def build_gun(kit,pistons,joints):
    # Turned receiver in the primary finish, with a curved saddle for the drum.
    bm=lathe_mesh([(.046,-.145),(.054,-.145),(.054,.032),(.050,.047),(.050,.145),(.042,.184),(.021,.184),(.021,.012),(.046,.012)],24,0,.2)
    seats=[]
    for az in (60,120):
        n=k.radial(az)
        for yy in (-.132,.135):
            c=Vector((0,yy,.2));seats.append((c+n*.050,c+n*.080,.009,8))
    k.carve(kit,bm,'Root',k.PRI,cuts=[((0,-.114,.14),(0,.012,.14),.081,24)]+seats,
            boxes=[((sx*.028,.015,.182),(.012,.016,.086)) for sx in (-1,1)])
    # Two rear tangs slide on concealed vertical ways, retained for 15 mm.
    for sx in (-1,1):
        kit.obox((sx*.028,.023,.139),(sx*.028,.023,.215),.012,.006,(0,1,0),'Root',k.FRM)
    # Integral trunnion and palm saddle: fused casting, then one machined bore.
    collar=lathe_mesh([(.0435,-.203),(.0475,-.203),(.050,-.193),(.050,-.166),(.054,-.159),(.054,-.147),(.0385,-.147),(.0385,-.171),(.0435,-.178)],24,0,.2)
    trunnion=union_mesh(collar,k.loft([-.206,-.196,-.156],support_section))
    k.carve(kit,trunnion,'Root',k.FRM,
        cuts=[((0,-.212,.2),(0,-.171,.2),.0435,24),((0,-.175,.2),(0,-.141,.2),.0385,24)],
        bevel_normal=k.BACK)
    # Compressible seam seals the butt joint; it stays inside the flange diameter.
    axial(kit,[(.0455,-.1473),(.0535,-.1473),(.0535,-.1447),(.0455,-.1447)],'Root',k.SEC)
    for xx in (-.018,.018):k.bolt(kit,(xx,-.206,.142),k.FWD,'Root',r=.002,head=.0012)
    # Turned stainless pressure tube and a perforated thermal jacket. The
    # integral end shoulders tie them together without drilling the pressure bore.
    pressure=lathe_mesh([(.023,-.280),(.041,-.280),(.046,-.275),(.046,-.268),
        (.042,-.263),(.031,-.262),(.031,-.190),(.037,-.184),(.037,-.123),
        (.0175,-.123),(.0175,-.270),(.019,-.277)],20,0,.2)
    jacket=lathe_mesh([(.034,-.263),(.041,-.263),(.043,-.258),(.043,-.251),
        (.0395,-.249),(.0395,-.246),(.042,-.244),(.042,-.203),(.039,-.197),
        (.039,-.187),(.034,-.183),(.034,-.187)],20,0,.2)
    vents=[]
    for az in range(0,360,60):
        for yy in (-.236,-.215):
            n=k.radial(az);c=Vector((0,yy,.2))
            vents.append((c+n*.0325,c+n*.050,.0035,8))
    k.carve(kit,union_mesh(pressure,jacket),'Barrel',k.JNT,cuts=vents)
    grenade_body(kit,(0,k.SEAT_Y,.2),k.ROCKET,6)
    # Rear steel pressure spine and compact open shoulder brace.
    axial(kit,[(.021,.048),(.032,.048),(.032,.179),(.027,.191),(.021,.191)],'Root',k.SEC,16)
    kit.obox((0,.178,.236),(0,.270,.236),.026,.018,k.UP,'Root',k.FRM,bevel=.003)
    kit.obox((0,.177,.166),(0,.270,.153),.020,.015,k.UP,'Root',k.MTL,bevel=.002)
    kit.plate(k.octagon_xz(.023,.140,.258,.006,.005,.276),.008,k.BACK,'Root',k.SEC,cuts=[((0,.268,.2),(0,.284,.2),.004,8)])
    axial(kit,[(.0035,.185),(.024,.185),(.024,.191),(.010,.198),(.010,.270),(.0035,.270)],'Root',k.FRM,12)
    # The grip flange seats against the turned receiver's underside.
    kit.obox((0,.11,.162),(0,.178,.162),.045,.012,k.UP,'Root',k.FRM,bevel=.002)
    k.build_grip(kit);k.build_trigger(kit)
    # Feed piston is coaxial with the bore, exposed behind its hollow rear gland.
    axial(kit,[(.0035,.123),(.015,.123),(.017,.145),(.022,.174),(.0035,.174)],'Root',k.FRM,12)
    kit.cyl((0,-.124,.2),(0,.123,.2),.003,'FeedRam',k.JNT,segs=8)
    kit.cyl((0,-.127,.2),(0,-.124,.2),.015,'FeedRam',k.SEC,segs=12)
    # Radial compression fittings meet machined receiver seats squarely.
    for sx,az in ((1,60),(-1,120)):
        p0,p1=pressure_union(kit,az,-.132);p5,p4=pressure_union(kit,az,.135)
        routed_line(kit,[p0,p1,(sx*.052,-.108,.273),(sx*.052,.111,.273),p4,p5],.0022,k.BRZ)
        for yy in (.05,.14):kit.cyl((sx*.038,yy,.176),(sx*.052,yy,.176),.004,'Root',k.FRM,segs=8)
        routed_line(kit,[(sx*.052,.05,.176),(sx*.058,.05,.176),(sx*.061,.07,.185),
            (sx*.061,.12,.185),(sx*.058,.14,.176),(sx*.052,.14,.176)],.0016,k.SEC)
    # Side display bolted to a flat boss on the circular receiver, no text.
    kit.obox((.048,.055,.211),(.048,.143,.211),.018,.035,k.UP,'Root',k.FRM,bevel=.003)
    outline=k.rounded([(.059,.194),(.139,.194),(.139,.230),(.059,.230)],[.005]*4,n=1)
    kit.plate([(.061,y,z) for y,z in outline],.008,(1,0,0),'Root',k.SEC,boxes=[((.064,.099,.212),(.006,.068,.026))])
    kit.span((.061,.066,.200),(.062,.132,.224),'Root',k.EMI)
    kit.span((.062,.066,.200),(.0625,.132,.224),'Root',k.GLS)
    for y in (.061,.137):k.bolt(kit,(.065,y,.212),(1,0,0),'Root',r=.0015,head=.001)
    # Through-pinned cam catch engages the drum's front retaining shoulder.
    for sx in (-1,1):kit.cyl((sx*.015,-.121,.138),(sx*.015,-.121,.163),.007,'Root',k.FRM,segs=8)
    kit.cyl((-.022,-.121,.150),(.022,-.121,.150),.003,'Root',k.JNT,segs=8)
    kit.cyl((-.0095,-.121,.150),(.0095,-.121,.150),.0033,k.LATCH,k.FRM,segs=8)
    kit.plate([(0,-.124,.150),(0,-.124,.124),(0,-.115,.116),(0,-.110,.125),(0,-.116,.134),(0,-.116,.150)],.020,(1,0,0),k.LATCH,k.FRM)
k.build_gun=build_gun

PACK_Z=.14;PACK_R=.080

def pack_support_section(y):
    pts=support_section(y)
    # Match the original lightning-style palm angle under the round drum.
    return [(x,yy,z-.079) for x,yy,z in pts]

def build_ammo(kit):
    # Closed axis-aligned circular cassette, real inspection bores and six rounds.
    c=(0,0,PACK_Z)
    case=lathe_mesh([(.077,-.105),(.080,-.105),(.080,.005),(.077,.005)],24,0,PACK_Z)
    foot=k.loft([-.103,.003],pack_support_section)
    k.carve(kit,union_mesh(case,foot),k.MAG,k.PRI,
        cuts=[((0,-.115,PACK_Z),(0,.015,PACK_Z),.077,24)])
    holes=[]
    for i in range(6):
        a=math.radians(90+60*i);x=.060*math.cos(a);z=PACK_Z+.060*math.sin(a)
        holes.append(((x,-.115,z),(x,.014,z),.0185,8))
    for yy,th in ((-.105,.006),(.005,.006)):
        kit.plate(k.ring_xz(0,PACK_Z,.077,yy,24),th,k.BACK,k.MAG,k.PRI,cuts=holes)
    # Rotor's central hub, radial web and pockets remain behind the casing.
    kit.cyl((0,-.102,PACK_Z),(0,.002,PACK_Z),.014,k.MAG,k.FRM,segs=12)
    for i in range(6):
        a=math.radians(90+60*i);x=.060*math.cos(a);z=PACK_Z+.060*math.sin(a)
        # Only ogive and sealed tail show through the drum's inspection bores;
        # its hidden guide bands belong to the separately authored projectile.
        if i!=0:k.lathe(kit,[(0,-.014),(.016,-.014),(.016,-.074),(.011,-.087),(.005,-.094),(0,-.096)],k.MAG,k.MTL,6,x,z)
        if i!=0:kit.cyl((x,-.020,z),(x,-.010,z),.017,k.MAG,k.FRM,segs=6)
    # The palm flat is integral to the drum shell; its cavity clears the rounds.
    for yy,n in ((-.108,k.FWD),(.008,k.BACK)):
        k.bolt(kit,(0,yy,PACK_Z),n,k.MAG,r=.005,head=.002)
    for sx in (-1,1):
        kit.obox((sx*.028,.014,.155),(sx*.028,.014,.215),.010,.010,(0,1,0),k.MAG,k.FRM)
k.build_ammo=build_ammo

# Magazine has a flat retained surface for a wide reload grip.
def gizmo_specs():
    return [('Muzzle1','Barrel',Vector((0,-.290,.2)),Vector(k.FWD),Vector(k.UP)),
       ('Backblast','Root',Vector((0,.15,.25)),Vector(k.UP),Vector(k.FWD)),
       ('ShellEject','Root',Vector((-.051,.05,.2)),Vector((-1,0,0)),Vector(k.UP))]
k.gizmo_specs=gizmo_specs
k.rocket_gizmo_specs=lambda:[('Warhead','GrenadeBody',Vector((0,-.083,0)),Vector(k.FWD),Vector(k.UP))]
k.build_rocket=lambda kit:grenade_body(kit,(0,0,0),'GrenadeBody',12)
k.rocket_sweeps=lambda:[]
k.build_preview_markers=lambda rig:None
k.sweep_states=lambda joints:[(f'{n} sweep {i}',{n:lo+(hi-lo)*i/10,k.LATCH:k.LATCH_OPEN,'FeedRam':.153} if n==k.MAG else {n:lo+(hi-lo)*i/10}) for n,j in joints.items() if j.limits for lo,hi in [j.limits] for i in range(11)]
def grenade_body(kit,tail,bone,segs=10):
    """Short caseless grenade: sealed tail, bourrelet bands, ogive fuze cap."""
    x,y,z=tail
    profile=[(0,y),(.012,y),(.016,y-.004),(.016,y-.054),(.015,y-.060),(.011,y-.073),(.005,y-.080),(0,y-.082)]
    k.lathe(kit,profile,bone,k.MTL,segs,x,z)
    for a,b in ((.007,.012),(.049,.054)):
        kit.cyl((x,y-a,z),(x,y-b,z),.017,bone,k.BRZ,segs=segs)
    k.lathe(kit,[(.0151,y-.060),(.0112,y-.073),(.0051,y-.080),(0,y-.082)],bone,k.PRI,segs,x,z)

k.rocket_body=grenade_body

def routed_line(kit,points,r,mat):
    """Mitred six-sided pipe; its explicitly authored unions provide the feet."""
    pts=[Vector(p) for p in k.fillet(points,.003,n=1)]
    bm=bmesh.new(); rings=[]; sides=6
    dirs=[(b-a).normalized() for a,b in zip(pts,pts[1:])]
    ref=Vector((0,0,1)) if abs(dirs[0].z)<.9 else Vector((1,0,0))
    normal=(ref-dirs[0]*ref.dot(dirs[0])).normalized()
    for i,p in enumerate(pts):
        di=dirs[max(0,i-1)]
        if i>1: normal=dirs[i-2].rotation_difference(di)@normal
        tangent=di.cross(normal)
        offsets=[r*(normal*math.cos(j*math.tau/sides)+tangent*math.sin(j*math.tau/sides)) for j in range(sides)]
        if 0<i<len(pts)-1:
            bis=(di+dirs[i]).normalized()
            offsets=[o-di*(o.dot(bis)/di.dot(bis)) for o in offsets]
        rings.append([bm.verts.new(p+o) for o in offsets])
    for aa,bb in zip(rings,rings[1:]):
        for j in range(sides):bm.faces.new((aa[j],aa[(j+1)%sides],bb[(j+1)%sides],bb[j]))
    bm.faces.new(rings[0][::-1]);bm.faces.new(rings[-1])
    kit.tubes.append(('Root',pts,r));kit.emit(bm,'Root',mat,False,convex=False,solid=False)


def lathe_mesh(profile,segs,x,z):
    tmp=k.Kit();k.lathe(tmp,profile,'Root',k.PRI,segs,x,z,loop=True);return tmp.bm
def export(objects,stem):
    if not stem.endswith('_rocket'):
        for o in objects:
            if o.type=='ARMATURE':
                for p in o.pose.bones:
                    for c in list(p.constraints):p.constraints.remove(c)
                for fc in list(o.animation_data.drivers if o.animation_data else []):o.animation_data.drivers.remove(fc)
        k.prepare_export(objects,HERE,stem)
        k.select_only(objects)
        bpy.ops.export_scene.fbx(filepath=str(HERE/f'{stem}.fbx'),use_selection=True,
            object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
            bake_space_transform=False,use_mesh_modifiers=False,mesh_smooth_type='OFF',
            add_leaf_bones=False,primary_bone_axis='Y',secondary_bone_axis='X',
            use_armature_deform_only=True,bake_anim=True,bake_anim_use_all_bones=False,
            bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,
            bake_anim_force_startend_keying=True,bake_anim_simplify_factor=0,
            path_mode='COPY',embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(HERE/f'{stem}.glb'),export_format='GLB',use_selection=True,
            export_yup=True,export_apply=False,export_skins=True,export_def_bones=True,
            export_animations=True,export_animation_mode='ACTIONS',export_anim_single_armature=True,
            export_reset_pose_bones=True,export_force_sampling=True,export_optimize_animation_size=True,
            export_optimize_animation_keep_anim_armature=False,export_anim_slide_to_zero=True,export_materials='EXPORT')
        return
    k.prepare_export(objects,HERE,stem)
    k.select_only(objects)
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{stem}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        add_leaf_bones=False,use_armature_deform_only=True,bake_anim=False,
        mesh_smooth_type='OFF',path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{stem}.glb'),export_format='GLB',use_selection=True,
        export_yup=True,export_skins=True,export_animations=False,export_materials='EXPORT')
    bpy.data.libraries.write(str(HERE/'grenade_launcher_grenade.blend'),set(objects),fake_user=True)
    import shutil
    for ext in ('glb','fbx'): shutil.copy2(HERE/f'{stem}.{ext}',HERE/f'grenade_launcher_grenade.{ext}')
k.export=export


original_pickup=k.export_pickup
def export_pickup(ammo):
    # The standalone drum's origin sits on its underside, unlike its mounted mesh.
    for v in ammo.data.vertices:v.co.z-=.048
    P=original_pickup(ammo)
    for v in ammo.data.vertices:v.co.z+=.048
    return P@Matrix.Translation((0,0,-.048))
k.export_pickup=export_pickup


def check_hands(kit):
    # The support palm grips the cassette's machined flat. Include both rigid
    # bodies in the rest-pose checks; the firing palm still grips the receiver.
    parts=[p for p in k.all_parts(kit) if p.bone in ('Root',k.MAG,'Barrel')]
    for side in ('Left','Right'):
        wrist,x,y,z=hand_frame(side);(a0,a1),hw,ht=k.PALM[:2],k.PALM[2],k.PALM[3]
        inner=[wrist+y*(a0+(a1-a0)*i/8)+x*(hw*(2*j/6-1))+z*ht*(2*l/4-1)*.98 for i in range(9) for j in range(7) for l in range(5)]
        face=[wrist+y*(a0+(a1-a0)*i/8)+x*(hw*(2*j/6-1))+z*ht for i in range(9) for j in range(7)]
        hit=[p.line for p in parts if any(p.buried(q) for q in inner)]
        if hit:raise SystemExit(f'{side} palm sinks into parts {hit}')
        gap=min(p.bvh.find_nearest(q)[3] for p in parts for q in face)
        if gap>.0015:raise SystemExit(f'{side} palm is {gap*1000:.1f} mm off its grip')

def machined_normals(body):
    # Axial shoulder faces stay optically planar beside the smooth turned walls.
    group=body.vertex_groups['Barrel'].index
    for face in body.data.polygons:
        if abs(face.normal.y)>.9999 and all(any(g.group==group for g in body.data.vertices[i].groups) for i in face.vertices):
            face.use_smooth=False

def main():
    k.reset_scene();k.build_materials()
    joints=k.resolve_joints();pistons=k.resolve_pistons(joints);k.check_states(joints)
    rig=k.build_rig(joints,pistons);k.check_rig_fk(rig,joints)
    actions=k.build_actions(rig,joints,pistons);k.add_hide_keys(rig,actions)
    kit=k.Kit();build_gun(kit,pistons,joints);build_ammo(kit)
    size=k.check_envelope(kit);k.check_connectivity(kit,joints,pistons);k.check_joint_alignment(kit,joints)
    check_hands(kit);ammo_frame=k.check_ammo_socket(kit,joints)
    states=k.action_states(actions,joints)+k.sweep_states(joints);k.check_motion(kit,joints,states)
    print(f'[{k.NAME}] checks passed ({len(states)} motion states); single-barrel pressure system, no gear train',flush=True)
    gun,pack=k.Kit(),k.Kit();build_gun(gun,pistons,joints);build_ammo(pack)
    body=gun.to_object('SK_GrenadeLauncher',joints=k.rotary_joints(joints));ammo=pack.to_object('SK_GrenadeLauncherAmmo')
    tris=k.finish(body,rig,joints,5000,states);atr=k.finish(ammo,rig,joints,1500,[])
    machined_normals(body)
    gizmos=k.build_gizmos(rig,gizmo_specs(),ammo_frame=ammo_frame)
    wrist,x,y,z=hand_frame('Left');lm=Matrix((x,-z,y)).transposed().to_4x4();lm.translation=wrist
    k.place_on_bone(bpy.data.objects['LeftHandSocket'],rig,k.MAG,lm)
    P=export_pickup(ammo);mounts=k.build_mounts(rig,P)
    export([rig,body,*gizmos,*mounts],k.NAME);bpy.data.objects.remove(ammo)
    k.constrain(rig,joints,pistons);gren,grig,ginfo=k.build_projectile()
    k.write_rig_json(ammo_frame,joints,tris,atr,0,size,(ginfo,gren));d=json.loads(k.RIG_JSON_PATH.read_text())
    d.pop('gear',None);d['rest']='Single barrel home, breech closed, circular six-round drum latched.'
    d['space']='Metres. Blender +Z up, muzzle -Y, origin on grip bottom at the weapon length centre. glTF/Godot (x,z,-y); muzzle +Z. Hinge local X in degrees; slide local Y in metres.'
    d['primary_srgb']=PRIMARY_HEX
    d['size_m']['barrel_axis_height']=d['size_m'].pop('drum_axis_height')
    d['fire'].update({'launch_frame':4,'spawn_frame':4,'index_deg':0,'note':'Single bore; 10 mm recoil over 30 frames. Feed piston remains closed through firing, withdraws 153 mm after frame 4, then returns to battery. Spawn ballistic grenade at frame 4. Circular cassette uses a spring follower; no rotating barrel carrier.'})
    d['gizmos']['muzzle_note']='Muzzle1 is 10 mm ahead of the single barrel and rides its recoil slide.'
    d['gizmos']['backblast_note']='Legacy marker name for the receiver pressure purge; the ballistic grenade has no motor.'
    d['gizmos']['shell_ejection']={'name':'ShellEject','bone':'Root','note':'Service/purge location; caseless grenades have no brass case to eject.'}
    d['ammo'].update({'rockets':5,'rounds':5,'capacity':6,'note':'Separate cylindrical six-station spring drum, five rounds retained and the sixth chambered; release the cam catch then slide down 15 mm before detachment.'})
    d['rocket'].update({'animations':{},'origin':'sealed tail centre; unpowered ballistic grenade','gizmo_note':'Warhead marks the grenade nose. This ballistic projectile has no motor or exhaust emitter.'})
    d['grenade']={**d['rocket'],'file':'grenade_launcher_grenade.glb'}
    d['hand_sockets']['LeftHandSocket']['grips']='machined flat beneath circular drum'
    d['hand_sockets']['LeftHandSocket']['bone']=k.MAG
    d['usage']='Library-only. idle, fire, cycle, mag_release, mag_insert. No game integration.'
    k.RIG_JSON_PATH.write_text(json.dumps(d,indent=2));k.add_mounts_json(P)
    rig['preview_poses']=json.dumps({s:{j:({'rot':[v,0,0]} if joints[j].kind=='hinge' else {'loc':[0,v,0]}) for j,v in st.items()} for s,st in k.PREVIEW_STATES.items()})
    rig['preview_pose_views']=json.dumps(k.PREVIEW_VIEWS)
    bpy.context.scene['preview_actions']=json.dumps(k.SHOWCASE)
    bpy.context.scene['preview_solo']=json.dumps({'grenade':{'objects':[gren.name],'views':['front_left','right','back']},
        'ammo':{'objects':['SM_GrenadeLauncherAmmo'],'views':['front_left','right','front']}})
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(k.BLEND_PATH),compress=True)
if __name__=='__main__':main()
