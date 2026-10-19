"""Three-sided lunar maintenance shelter, 5 x 5 m, library-only.

Blender 5.2 headless source. Formed shells have exact pocket seats; moving
service mechanisms have retained shafts, bored supports and swept clearance.
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
    'M_Status': 'Emissive',
    'M_Wire': 'Diffuse',
}
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
MODELS=HERE.parents[1]
sys.path.insert(0,str(MODELS/'environments'))
import light_common as common
sys.path.insert(0,str(MODELS/'architecture/container'))
import model as container_tools
sys.path.insert(0,str(HERE.parent))
import perimeter_surface as surface
import light_mounts
kit=common.kit
ROOT,PRI,SEC,FRM,JNT,EMI=common.ROOT,common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
NAME,TITLE='shelter','Shelter'
STATUS='M_Status'
GLASS,WIRE='M_Glass','M_Wire'
block,rod,loft=common.block,common.rod,common.loft
mach,emit,seat,xf,boxcut=container_tools.mach,container_tools.emit,container_tools.seat,container_tools.transform,container_tools.boxcut
PX,PY=-.29,1.91
INNER=[(-1.45,-.04),(-1.45,.60),(-1.18,1.86),(-.57,2.50),(1.24,2.50),(1.24,-.04)]

def yz(profile,x,thickness):
    return kit.prism_bm([(x,y,z) for y,z in profile],thickness,(1,0,0))

def subtract(bm,tool):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(tool,faces=tool.faces[:]);tool.verts.index_update()
    p=SimpleNamespace(verts=[v.co.copy() for v in tool.verts],faces=[[v.index for v in f.verts] for f in tool.faces])
    result=common.trim_seats(bm,[p]);tool.free();return result

def pocket(body,insert):
    """Use the insert's actual geometry as its machining tool: exact shared seat."""
    return subtract(body,insert.copy())

def shifted(bm,at):return xf(bm,Matrix.Translation(at))

def bevel(bm,width):
    bmesh.ops.bevel(bm,geom=bm.edges[:],offset=width,segments=1,
        affect='EDGES',clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    return bm

def screws(k,m,points,z,label,bone=ROOT):
    # Socket heads start at the mounting flat. No intersecting fake shanks.
    with k.frame(m):
        for x,y in points:
            head=mach(rod((x,y,z),(x,y,z+.008),.017,6),
                      cuts=[((x,y,z+.004),(x,y,z+.012),.007,4)])
            emit(k,head,JNT,label,bone)

def body(k):
    # Sloped deck edges are integral ramps, including both side approaches.
    deck=loft([(4.60,4.60,.32,0),(4.02,4.02,.23,.12)])
    # The arch, rear pier and canopy share ONE outside profile. A separate
    # chamfered rectangular roof would expose arch tips at its corner cuts.
    # Here there is no hidden overlap or ledge to disguise with a connector.
    exterior=[(-1.90,.11),(-1.90,.62),(-1.61,2.03),(-.83,2.96),
              (-.73,3.08),(1.77,3.08),(1.87,2.96),(1.87,.11)]
    building=bevel(yz(exterior,0,3.64),.022)
    building=mach(building,boxes=[boxcut((-1.40,-2.2,.12),(1.40,1.52,2.82))])
    for s in (-1,1):building=subtract(building,yz(INNER,s*1.61,.60))
    shell=mach(deck,union=[building])
    inserts=[]
    # Roof sheets are machined into the casting, with stepped perimeter lands.
    for x in (-.78,.78):
        panel=shifted(loft([(1.35,2.13,.08,3.015),(1.35,2.13,.08,3.08)]),(x,.50,0))
        shell=pocket(shell,panel);inserts.append((panel,PRI,'flush removable canopy armour'))
    # Outer arch armour follows the exact sloping frame, rather than bars laid
    # across one another. All face details live on the same planar side seats.
    side_faces=[]
    for s in (-1,1):
        # One top access panel per side; the side faces of both inclined arms
        # remain plain at the user's request. No continuous perimeter ribbon.
        for index,(a,b,w) in enumerate((((-.45,2.73),(.92,2.73),.27),)):
            a,b=Vector(a),Vector(b);centre=(a+b)/2;d=(b-a).normalized();h=(b-a).length
            m=common.frame((s*1.82,centre.x,centre.y),(s,0,0),(0,d.x,d.y))
            side_faces.append((m,h))
            # Back ends exactly on the cast flat; the machined front has its
            # own 18 mm thickness and a 10 mm perimeter chamfer.
            panel=loft([(w,h,.025,0),(w-.020,h-.020,.018,.018)])
            # Machined inset with an end land at each side; the small cyan
            # window is an operational telltale rather than a perimeter lamp.
            slot=loft([(.11,h*.46,.015,.004),(.11,h*.46,.015,.012)])
            panel=subtract(panel,loft([(.11,h*.46,.015,.004),(.11,h*.46,.015,.030)]))
            indicator=loft([(.064,.065,.008,.012),(.064,.065,.008,.016)])
            slot=pocket(slot,indicator)
            for bm in (panel,slot,indicator):xf(bm,m)
            inserts.extend(((panel,PRI,f'segment-specific flush machined arch panel {s} {index}'),
                            (slot,FRM,'recessed inspection pocket with machined end lands'),
                            (indicator,EMI,'short exterior arch status insert')))
        # Rear side access plate sits wholly on the vertical rear pillar flat.
        pod=xf(loft([(.42,1.08,.065,-.028),(.42,1.08,.065,0)]),
               common.frame((s*1.82,1.55,1.24),(s,0,0),(0,0,1)))
        shell=pocket(shell,pod);inserts.append((pod,PRI,'rear pier flush access panel'))
    # Front faces have their own seats derived from each segment's slope.
    # No fastener lies on a radius or an unsupported outside edge.
    front_faces=[]
    for x in (-1.61,1.61):
        for at,normal,up,h in (((x,-1.755,1.325),(0,-1,.29/1.41),(0,.29,1.41),1.15),
                              ((x,-1.22,2.495),(0,-.93,.78),(0,.78,.93),.80)):
            m=common.frame(at,normal,up);front_faces.append((m,h))
            plate=xf(loft([(.29,h,.025,-.018),(.29,h,.025,0)]),m)
            shell=subtract(shell,xf(loft([(.29,h,.025,-.018),(.29,h,.025,.010)]),m))
            # Physical recessed heat/inspection slot, dark insert flush at face.
            slot=xf(loft([(.09,h*.45,.008,-.010),(.09,h*.45,.008,0)]),m)
            plate=subtract(plate,xf(loft([(.09,h*.45,.008,-.010),(.09,h*.45,.008,.010)]),m))
            inserts.extend(((plate,PRI,'machined inclined front armour'),(slot,FRM,'flush front inspection recess')))
    # Genuine rear service hatch opening, closed by the rigged removable leaf.
    shell=mach(shell,boxes=[boxcut((-.273,1.67,1.025),(.273,2.02,1.935))])
    # Exterior rear cooling cartridges seat on machined bulkhead lands.
    for x in (-1.04,1.04):
        frame=common.frame((x,1.85,1.43),(0,1,0),(0,0,1))
        pod=xf(loft([(.69,.86,.08,0),(.69,.86,.08,.18),(.58,.75,.065,.23)]),frame)
        shell=mach(shell,union=[pod])
        shell=mach(shell,cuts=[((x,1.74,1.43),(x,2.12,1.43),.245,12)])
    # Deck traction is cut geometry, with flush dark inserts; no trip strips.
    for x in (-1.11,0,1.11):
        rail=block((x-.018,-1.74,.112),(x+.018,1.15,.12))
        shell=mach(shell,boxes=[boxcut((x-.018,-1.74,.112),(x+.018,1.15,.14))])
        inserts.append((rail,FRM,'flush deck traction channel'))
    shell.normal_update()
    bmesh.ops.remove_doubles(shell,verts=shell.verts[:],dist=1e-6)
    bmesh.ops.dissolve_degenerate(shell,dist=1e-7,edges=shell.edges[:])
    assert all(e.is_manifold for e in shell.edges),[(tuple(e.verts[0].co),tuple(e.verts[1].co),len(e.link_faces)) for e in shell.edges if not e.is_manifold][:20]
    emit(k,shell,SEC,'continuous cast load frame, ramps, rear bulkhead and canopy')
    for bm,mat,label in inserts:emit(k,bm,mat,label)
    for x in (-.78,.78):
        screws(k,Matrix.Identity(4),[(x+dx,.50+dy) for dx in (-.48,.48) for dy in (-.82,.82)],3.08,'canopy captive fastener')
    for s in (-1,1):
        m=common.frame((s*1.82,1.55,1.24),(s,0,0),(0,0,1))
        screws(k,m,[(x,y) for x in (-.13,.13) for y in (-.42,.42)],0,'rear pier panel captive screw')
        # Ground anchoring: bolt heads on unchamfered deck flats.
        screws(k,Matrix.Identity(4),[(s*1.62,y) for y in (-1.97,1.97)],.12,'foundation anchor cap')
    for m,h in front_faces:
        screws(k,m,[(0,-h*.39),(0,h*.39)],0,'inclined armour retained socket screw')
    for m,h in side_faces:
        screws(k,m,[(0,-h*.41),(0,h*.41)],.018,'side armour captive socket fastener')
    # Exterior header controller: cast flange and body are one formed shell;
    # bezel and amber telltale have actual inset pockets and bottom seats.
    # The controller face is vertical, with the indicator at its exact centre.
    # Its deep rear wedge is machined to the real inclined canopy support,
    # rather than placing the lamp on the upper roof bevel.
    m=common.frame((0,-.93,2.91),(0,-1,0),(0,0,1))
    housing=loft([(.88,.20,.024,-.25),(.88,.20,.024,.025),
                  (.74,.16,.020,.105),(.70,.14,.018,.12)])
    face=loft([(.48,.070,.014,.106),(.48,.070,.014,.120)])
    indicator=loft([(.21,.028,.008,.114),(.21,.028,.008,.120)])
    housing=pocket(housing,face);face=pocket(face,indicator)
    with k.frame(m):
        seat(k,housing,SEC,'formed exterior controller with machined mounting flange')
        emit(k,face,FRM,'flush controller bezel')
        emit(k,indicator,STATUS,'recessed amber exterior operational indicator')
    screws(k,m,[(-.29,0),(.29,0)],.12,'controller retained face fastener')

def cooling(k):
    for tag,x in (('Left',1.04),('Right',-1.04)):
        bn='CoolantRotor'+tag
        # Recessed motor attached to the cavity back; thrust shaft on same axis.
        emit(k,rod((x,1.74,1.43),(x,1.825,1.43),.087,12),FRM,'sealed cooling motor and bulkhead seat')
        emit(k,rod((x,1.825,1.43),(x,1.872,1.43),.028,8),JNT,'cooling motor retained shaft')
        hub=rod((x,1.872,1.43),(x,1.925,1.43),.070,12)
        blades=[]
        # A sealed coolant cartridge, not an atmospheric fan on an airless
        # lunar surface. Three vanes circulate the closed radiator circuit.
        for i in range(3):
            a=math.tau*i/3
            pts=[(.049,-.01),(.18,.055),(.216,.095),(.188,.125),(.057,.035)]
            poly=[(x+r*math.cos(a)-t*math.sin(a),1.900,1.43+r*math.sin(a)+t*math.cos(a)) for r,t in pts]
            blades.append(kit.prism_bm(poly,.022,(0,1,0)))
        emit(k,mach(hub,union=blades),JNT,'three-vane sealed coolant impeller',bn)
        emit(k,rod((x,2.027,1.43),(x,2.039,1.43),.245,12),GLASS,'flush sealed pump sight glass')
        # Fixed guard rim and spokes terminate on the real bored housing.
        rim=mach(rod((x,2.055,1.43),(x,2.074,1.43),.267,12),
                 cuts=[((x,2.04,1.43),(x,2.09,1.43),.231,12)])
        bars=[rod((x-.25,2.065,1.43),(x+.25,2.065,1.43),.011,4),
              rod((x,2.065,1.18),(x,2.065,1.68),.011,4)]
        # Trim the outside to the casting, keeping bore clearance intact.
        seat(k,mach(rim,union=bars),FRM,'seated integral impeller safety grille')

def service(k):
    # Leaf rests behind the rear wall plane; its outline matches the machined
    # opening with a 1 mm running reveal, never an overlaid fake panel.
    m=common.frame((0,1.895,1.48),(0,1,0),(0,0,1))
    leaf=xf(loft([(.544,.908,.035,-.038),(.544,.908,.035,.015)]),m)
    hatch_inset=xf(loft([(.38,.64,.030,.004),(.38,.64,.030,.015)]),m)
    leaf=pocket(leaf,hatch_inset)
    leaf=mach(leaf,cuts=[((PX,PY,a-.002),(PX,PY,b+.002),.047,12)
        for z in (1.17,1.79) for a,b in ((z-.075,z-.033),(z+.033,z+.075))])
    tongues=[mach(rod((PX,PY,z-.031),(PX,PY,z+.031),.030,8),
        union=[block((PX,1.875,z-.031),(-.23,1.91,z+.031))],
        cuts=[((PX,PY,z-.04),(PX,PY,z+.04),.0105,8)]) for z in (1.17,1.79)]
    leaf=mach(leaf,union=tongues)
    emit(k,leaf,SEC,'machined service leaf with flush reinforcement land','ServiceHatch')
    emit(k,hatch_inset,PRI,'service leaf seated face plate','ServiceHatch')
    # Two interleaved hinge pairs, axis on a flat vertical mounting land.
    for z in (1.17,1.79):
        for a,b in ((z-.075,z-.033),(z+.033,z+.075)):
            sleeve=mach(rod((PX,PY,a),(PX,PY,b),.032,8),
                union=[block((PX-.050,1.84,a),(PX,1.91,b))],
                cuts=[((PX,PY,a-.01),(PX,PY,b+.01),.010,8)])
            seat(k,sleeve,SEC,'fixed bored hinge fork on bulkhead flat')
        emit(k,rod((PX,PY,z-.082),(PX,PY,z+.082),.0095,8),JNT,'retained service hinge shaft')
        for h in (z-.088,z+.082):emit(k,rod((PX,PY,h),(PX,PY,h+.006),.017,8),JNT,'hinge shaft retaining cap')
    # Recessed latch pocket on the moving leaf; a flush cam release.
    with k.frame(m):
        seat(k,loft([(.08,.16,.012,.015),(.08,.16,.012,.03)]),JNT,'service latch housing','ServiceHatch')
    screws(k,m,[(x,y) for x in (-.19,.19) for y in (-.36,.36)],.015,'service hatch captive fastener','ServiceHatch')
    # Internal conduits sit on the rear wall, terminate in flange glands, and
    # are supported by bored saddles with an exact wall seat.
    for x in (-.72,.72):
        emit(k,rod((x,1.44,.30),(x,1.44,2.59),.020,8),JNT if x>0 else WIRE,
             'rear interior coolant conduit' if x>0 else 'clamped copper power bus')
        for z in (.30,1.47,2.59):
            clamp=mach(rod((x,1.44,z-.032),(x,1.44,z+.032),.039,8),
                union=[block((x-.044,1.44,z-.032),(x+.044,1.53,z+.032))],
                cuts=[((x,1.44,z-.045),(x,1.44,z+.045),.020,8)])
            seat(k,clamp,FRM,'bored conduit gland and bulkhead-seated saddle')

def terrain(rig):
    # Narrow skirt within the complete 5 m siting envelope. All three
    # approach lanes remain at ground level; raised drift only by rear corners.
    contour=common.outline(4.60,4.60,.32,0)
    points=[]
    for a,b in zip(contour,contour[1:]+contour[:1]):
        points.extend(Vector(a).lerp(Vector(b),i/3) for i in range(3))
    verts=[];faces=[];n=len(points)
    for row,t in enumerate((0,.45,1)):
        for i,p in enumerate(points):
            q=p+Vector((p.x,p.y,0)).normalized()*.20*t
            z=.070*(.8+.2*math.sin(i*1.9)) if row==1 else 0
            if p.y<1.65 or abs(p.x)<1.5:z=0
            verts.append((q.x,q.y,z))
    for row in range(2):
        for i in range(n):
            j=(i+1)%n
            faces.extend(((row*n+i,(row+1)*n+i,(row+1)*n+j),(row*n+i,(row+1)*n+j,row*n+j)))
    mesh=bpy.data.meshes.new(surface.NAME);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(surface.NAME,mesh);bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(bpy.data.materials[surface.MATERIAL])
    obj.vertex_groups.new(name=ROOT).add(list(range(len(verts))),1,'REPLACE');kit.skin(obj,rig)
    surface.annotate(obj)
    uv=mesh.uv_layers.new(name='TiledSurface')
    for loop in mesh.loops:
        p=mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(p.x/2,p.y/2)
    return obj

def export(rig,objects):
    for pb in rig.pose.bones:
        for c in list(pb.constraints):pb.constraints.remove(c)
    common.prepare_export([rig,*objects],HERE,NAME)
    kit.select_only([rig,*objects])
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,
        export_force_sampling=True,export_materials='EXPORT')

def main():
    common.CORNER_STEPS=1;common.LABELS.clear();kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.015,.62,.68),0,.34,2)
    kit.MATERIALS[STATUS]=((1,.38,.045),0,.34,2)
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0)
    kit.MATERIALS[WIRE]=((.72,.36,.18),1,.35,0)
    surface.configure(kit);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    from lunar_material import install
    install(bpy.data.materials[surface.MATERIAL])
    glass=bpy.data.materials[GLASS];bsdf=glass.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Alpha'].default_value=.10;glass.diffuse_color=(0,0,0,.10);glass.surface_render_method='DITHERED'
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('ServiceHatch',ROOT,'hinge',(PX,PY,1.48),(0,0,1),(1,0,0),(0,95))]
    for tag,x in (('Left',1.04),('Right',-1.04)):
        kit.JOINT_SPECS.append(('CoolantRotor'+tag,ROOT,'hinge',(x,1.90,1.43),(0,1,0),(0,0,1),(0,360)))
    kit.GROUPS=()
    keys={'ServiceHatch':[(0,0),(8,0),(60,95),(72,95)]}
    kit.ANIMATIONS={'circulate':(True,'LINEAR',{bn:[(f,f*3) for f in range(121)] for bn in ('CoolantRotorLeft','CoolantRotorRight')}),
        'service_open':(False,'BEZIER',keys),
        'service_close':(False,'BEZIER',{bn:[(72-f,v) for f,v in reversed(ks)] for bn,ks in keys.items()})}
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    body(k);cooling(k);service(k)
    for p,label in zip(k.parts,common.LABELS):p.line=label
    if '--draft' in sys.argv:
        kit.build_actions(rig,joints,[]);obj=k.to_object('SK_'+TITLE);kit.skin(obj,rig)
        bpy.context.scene['preview_frame']=json.dumps(dict(lo=[-2.5,-2.5,0],hi=[2.5,2.5,3.08]))
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'shelter.blend'));print('[shelter] DRAFT',flush=True);return
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    # All loop frames, plus simultaneous pump/hatch states.
    states.extend((f'circulate frame {f}',{'CoolantRotorLeft':f*3,'CoolantRotorRight':f*3}) for f in range(121))
    states.extend((f'combined {a}',{'ServiceHatch':a,'CoolantRotorLeft':a*3,'CoolantRotorRight':a*3}) for a in range(96))
    kit.check_motion(k,joints,states)
    for _,state in states:
        matrices=kit.fk(joints,state)
        for p in k.parts:
            for v in p.verts:
                q=matrices[p.bone]@v
                assert abs(q.x)<=2.5 and abs(q.y)<=2.5,('5m swept envelope',p.line,tuple(q))
    obj=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(obj,rig)
    # Long coplanar Boolean junctions can become almost collinear triangles
    # after the kit's weld pass. They have no rendered area and unstable
    # collision normals; remove them explicitly before UVs and delivery.
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=bm.faces[:])
    def triangle_area(face):
        a,b,c=[tuple(v.co) for v in face.verts]
        u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        return sum(x*x for x in cross)**.5*.5
    zero=[f for f in bm.faces if triangle_area(f)<1e-7]
    bmesh.ops.delete(bm,geom=zero,context='FACES_ONLY')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(obj.data);bm.free()
    sys.path.insert(0,str(MODELS/'architecture/lunar_dome'))
    from surface_audit import check_coplanar
    check_coplanar(obj)
    # Analytic ground-contact culling; every interior and service face remains.
    bm=bmesh.new();bm.from_mesh(obj.data)
    hidden=[f for f in bm.faces if all(v.co.z<1e-6 for v in f.verts) and f.normal.z<-.5]
    bmesh.ops.delete(bm,geom=hidden,context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
    apron=terrain(rig);meshes=[obj,apron]
    assert sum(kit.triangles(o) for o in meshes)<=5000,sum(kit.triangles(o) for o in meshes)
    from material_uv import EFFECT_MATERIALS
    EFFECT_MATERIALS.add(surface.MATERIAL)
    markers,mounts=light_mounts.install(rig,[obj],
        [('',(0,.50,2.4),(0,0,1))],
        [('',(0,0,1.8),(0,1,0))])
    export(rig,[*meshes,*markers])
    rig['preview_poses']=json.dumps({'service_open':{'ServiceHatch':{'rot':[95,0,0]}}})
    rig['preview_pose_views']=json.dumps({'service_open':['rear_right']})
    bpy.context.scene['preview_actions']=json.dumps(['circulate','service_open','service_close'])
    bpy.context.scene['preview_frame']=json.dumps(dict(lo=[-2.5,-2.5,0],hi=[2.5,2.5,3.08]))
    bpy.context.scene['showcase_frame']=bpy.context.scene['preview_frame']
    report=dict(name=NAME,triangle_budget=5000,ground_envelope_m=[5,5],
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=kit.ANIMATIONS[n][0]) for n,a in actions.items()},
        passage_m=dict(front_width=2.80,side_width=2.40,minimum_height=2.38,deck_height=.12,ramp_run=.29),
        gizmos=mounts,glazing=dict(material=GLASS,color=[0,0,0],opacity=.10),
        checks=dict(exact_solid_pairs=pairs,connectivity=True,motion_states=len(states),coplanar=True,degenerate_faces_removed=len(zero)),
        placement='5x5m including apron and all motion; front -Y; open front/left/right; library only',
        mechanics='continuous ramped load casting; separately seated machined armour; sealed radiator coolant cartridges with retained three-vane rotors and protected black 10% sight glasses; twin interleaved retained service hinges; bulkhead-seated coolant and copper power-bus glands')
    surface.update_report(report,meshes,kit)
    report['architecture_dimensions']=dict(door_type='open',rooms=[dict(floor_m=.12,ceiling_m=2.82,height_m=2.70)],measurement='Open canopy; floor top to highest roof underside; minimum approach headroom 2.38 m')
    (HERE/'shelter_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'shelter.blend'))
    print(f'[shelter] PASS {report["triangles"]} triangles; {len(k.parts)} parts',flush=True)

if __name__=='__main__':main()
