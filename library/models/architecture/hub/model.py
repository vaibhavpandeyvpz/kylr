"""6 m four-way lunar hub; procedural machined architecture, library only.

Run with Blender 5.2 headless from library/. Two-stage hydraulic lift doors
have distinct parallel storage lanes, hollow cylinders and guided crossheads.
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
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
MODELS=HERE.parents[1]
sys.path.insert(0,str(MODELS/'environments'))
sys.path.insert(0,str(HERE.parent))
import light_common as common
import perimeter_surface as surface
import light_mounts
import door_actions
import importlib.util
spec=importlib.util.spec_from_file_location('hub_tools',MODELS/'architecture/container/model.py')
tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(tools)
kit=common.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
ROOT,PRI,SEC,FRM,JNT,EMI=common.ROOT,common.PRI,common.SEC,common.FRM,common.JNT,common.EMI
NAME,TITLE='hub','Hub'
GLASS='M_Glass'
block,rod=common.block,common.rod
emit,seat,mach,transform,boxcut=tools.emit,tools.seat,tools.mach,tools.transform,tools.boxcut
SIDES={'Front':0,'Left':math.pi/2,'Rear':math.pi,'Right':-math.pi/2}
PROFILE=[(2.78,0),(2.78,.12),(2.72,.18),(2.50,.48),(2.50,2.48),
         (2.48,2.60),(1.43,3.94),(1.35,4.04)]

def controlled_bones(name,has_rear=False):
    if '_' not in name:return None
    tag=name.split('_')[-1].title()
    if tag not in SIDES:return None
    return {'Door'+tag+'Upper','Door'+tag+'Lower','Stage'+tag+'Left','Stage'+tag+'Right'}

door_actions.controlled_bones=controlled_bones

def rotation(angle):
    # Cardinal transforms are exact integers: float32 sin(pi) would create
    # tiny wedges and open Boolean seams on supposedly shared planar lands.
    c,s=((1,0),(0,1),(-1,0),(0,-1))[round(angle/(math.pi/2))%4]
    return Matrix(((c,-s,0,0),(s,c,0,0),(0,0,1,0),(0,0,0,1)))

def incline():
    return Matrix.Identity(4)

def outline(r,z):
    c=r*.42
    return [(-r+c,-r,z),(r-c,-r,z),(r,-r+c,z),(r,r-c,z),
            (r-c,r,z),(-r+c,r,z),(-r,r-c,z),(-r,-r+c,z)]

def shell(stations):return kit.loft_rings([outline(r,z) for r,z in stations])

def pressure_shell():
    rows=[]
    for r,z in PROFILE:
        pts=list(map(Vector,outline(r,z)));row=[]
        for a,b in zip(pts,pts[1:]+pts[:1]):
            n=Vector((b.y-a.y,a.x-b.x,0)).normalized()
            for u in (0,.075,.08,.92,.925):
                p=a.lerp(b,u)
                row.append(p)
        rows.append(row)
    return kit.loft_rings(rows)

def cut(bm,cutter):
    from types import SimpleNamespace
    cutter.verts.index_update()
    p=SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],faces=[[v.index for v in f.verts] for f in cutter.faces])
    cutter.free()
    return common.trim_seats(bm,[p])

def panel(w,z0,z1,y0,y1,bevel=.045):
    def loop(width,lo,hi,y):
        c=.07
        return [(-width+c,y,lo),(width-c,y,lo),(width,y,lo+c),(width,y,hi-c),
                (width-c,y,hi),(-width+c,y,hi),(-width,y,hi-c),(-width,y,lo+c)]
    return kit.loft_rings([loop(w-bevel,z0+bevel,z1-bevel,y0),loop(w,z0,z1,y0+bevel),
                           loop(w,z0,z1,y1-bevel),loop(w-bevel,z0+bevel,z1-bevel,y1)])

def body(k):
    base=shell(PROFILE)
    towers=[]
    for angle in SIDES.values():
        # Continuous cast pocket, joined to the pressure shell by broad lands.
        tower=common.loft([(2.34,.76,.10,0),(2.34,.76,.10,2.48),
                           (2.34,.76,.10,4.11),(2.30,.73,.08,4.34)])
        transform(tower,Matrix.Translation((0,-2.38,0)))
        towers.append(transform(tower,rotation(angle)@incline()))
        # The pocket itself joins the pressure wall. Extra rectangular contact
        # lands protruded as vertical strips beside the neighbouring panels;
        # retain the continuous cast junction without those proud edges.
        # Broad inboard roof tie is integral, entirely behind the front shroud.
        towers.append(transform(block((-.60,-2.05,3.80),(.60,-1.20,3.94)),rotation(angle)))
    base=mach(base,union=towers)
    base=cut(base,block((-5,-5,-3),(5,5,0)))
    base=cut(base,shell([(2.35,.12),(2.35,2.48),(1.28,3.84)]))
    for angle in SIDES.values():
        # Real through passage below; enclosed lane above, separate from room.
        base=cut(base,transform(block((-.75,-3.1,.12),(.75,-1.9,2.52)),rotation(angle)))
        # 4mm running clearance to the cylinder's forward envelope and a
        # continuous >=6mm skin at the front-side chamfer. The previous wide
        # rectangular cut broke through that chamfer as a visible pillar slit.
        base=cut(base,transform(block((-1.098,-2.719,.12),(1.098,-2.14,4.215)),rotation(angle)@incline()))
    inlays=[]
    # Four diagonal roof panes on exact roof seating planes.
    for i in (1,3,5,7):
        a,b=map(Vector,(outline(2.48,2.60)[i],outline(2.48,2.60)[(i+1)%8]))
        c,d=map(Vector,(outline(1.43,3.94)[i],outline(1.43,3.94)[(i+1)%8]))
        n=(b-a).cross(c-a).normalized()
        if n.dot(a)<0:n=-n
        def pt(u,v):return a.lerp(b,u).lerp(c.lerp(d,u),v)
        poly=[pt(.23,.20),pt(.77,.20),pt(.77,.74),pt(.23,.74)]
        base=cut(base,kit.prism_bm(poly,.60,n))
        # Glazing gasket/retainer shares the aperture boundary, no overlay.
        centre=sum(poly,Vector())/4
        inner=[p.lerp(centre,.10) for p in poly]
        ring=kit.prism_bm([p-n*.055 for p in poly],.11,n)
        ring=cut(ring,kit.prism_bm(inner,.4,n))
        inlays.append((ring,FRM,'roof window machined retainer'))
        inlays.append((kit.prism_bm([p-n*.06 for p in inner],.06,n),GLASS,'recessed pressure glass'))
    base.normal_update()
    assert all(e.is_manifold for e in base.edges),'pressure shell must remain closed after pocket cuts'
    for f in base.faces:
        p=f.calc_center_median();f.material_index=kit.SLOTS.index(PRI)
        # Whole manufacturing surfaces define finish boundaries; Boolean
        # fragments must not pick up grey merely from a centroid/axis test.
        zs=[v.co.z for v in f.verts]
        if max(zs)<=.18001 or min(zs)>=3.93999:
            f.material_index=kit.SLOTS.index(SEC)
    bmesh.ops.triangulate(base,faces=base.faces[:]);indices=[f.material_index for f in base.faces]
    made=k.emit(base,ROOT,PRI,False,convex=False,exact=True)
    for f,m in zip(made,indices):f.material_index=m
    common.LABELS.append('integral octagonal pressure shell, floor and four door storage towers')
    for bm,mat,label in inlays:seat(k,bm,mat,label)
    # Diagonal armour cells and service sockets, deliberately seated into shell.
    for i in (1,3,5,7):
        a,b=map(Vector,(outline(2.50,1.42)[i],outline(2.50,1.42)[(i+1)%8]))
        n=Vector((b.y-a.y,a.x-b.x,0)).normalized()
        m=common.frame((a+b)/2,n,(0,0,1))
        with k.frame(m):
            bm=common.loft([(1.34,1.56,.10,-.006),(1.34,1.56,.10,.025),
                            (1.24,1.46,.075,.075)])
            # The machined aperture and its plate share the same 70mm clipped
            # corners, rather than putting an octagonal insert in a square cut.
            bm=cut(bm,common.loft([(1.03,1.22,.07,.058),(1.03,1.22,.07,.10)]))
            seat(k,bm,PRI,'corner removable lofted armour cassette')
            emit(k,common.loft([(1.0299,1.2199,.06995,.058002),(1.0299,1.2199,.06995,.061)]),SEC,'recessed cassette service panel')
            for x in (-.54,.54):
                for y in (-.64,.64):
                    seat(k,rod((x,y,.060),(x,y,.077),.022,6),JNT,'captive cassette fastener on planar land')
            # Fixed hydraulic utility lines seated in saddles; every run has glands.
            for x in (-.70,.70):
                emit(k,rod((x,-.55,.050),(x,.55,.050),.018,8),JNT,'wall-seated hydraulic service conduit')
                for y in (-.55,.55):
                    foot=mach(block((x-.025,y-.033,0),(x+.025,y+.033,.075)),
                              cuts=[((x,y-.05,.050),(x,y+.05,.050),.018,8)])
                    emit(k,foot,FRM,'bored saddle and pressure feed gland')

def door(k,tag):
    upper,lower='Door'+tag+'Upper','Door'+tag+'Lower'
    # Solid panel bodies have machined recesses for lights and inspection glass.
    for bone,z0,z1,y0,y1 in ((lower,.14,1.30,-2.70,-2.58),(upper,1.32,2.48,-2.53,-2.41)):
        bm=panel(.74,z0,z1,y0,y1,.024)
        recess=(0,(y0+y1)/2,z0+.53)
        # Armour relief is removed, with an inset metallic access plate.
        bm=mach(bm,boxes=[((0,y0+.006,z0+.51),(1.22,.025,.72)),
                          ((0,y0+.006,z1-.12),(.50,.027,.030))])
        emit(k,bm,PRI,tag+' '+bone+' continuous chamfered blast slab',bone)
        emit(k,block((-.61,y0+.001,z0+.15),(.61,y0+.0185,z0+.87)),SEC,tag+' recessed blast-panel access plate',bone)
        emit(k,block((-.25,y0+.002,z1-.135),(.25,y0+.0195,z1-.105)),EMI,tag+' flush exterior amber status strip',bone)
        for x in (-.66,.66):
            for z in (z0+.17,z1-.17):
                emit(k,rod((x,y0-.006,z),(x,y0,z),.018,6),JNT,tag+' panel captive screw',bone)
        # Each crosshead is one weldment: panel tongue, actuator flange and
        # guide shoes. Its bores remove cylinder interiors, rather than hiding
        # rods inside blocks. The long vertical shoe runs in a fitted channel.
        for s in (-1,1):
            cy=-2.64 if bone==lower else -2.47
            zz=z0+.13
            tongue=block((min(s*.73,s*1.065),cy-.035,zz-.040),
                         (max(s*.73,s*1.065),cy+.035,zz+.040))
            tongue=mach(tongue,cuts=[((s*1.02,cy,zz-.10),(s*1.02,cy,zz+.10),.028 if bone==lower else .052,8)])
            seat(k,tongue,SEC,tag+' bolted crosshead and rod socket',bone)
            for sy in (-1,1):
                emit(k,block((min(s*.81,s*.895),cy+sy*.036-.001,zz-.035),
                             (max(s*.81,s*.895),cy+sy*.036+.001,zz+.035)),FRM,tag+' replaceable guide bearing shoe',bone)
            nut=mach(rod((s*1.02,cy,zz-.052),(s*1.02,cy,zz-.040),.046 if bone==lower else .065,8),
                     cuts=[((s*1.02,cy,zz-.06),(s*1.02,cy,zz),.028 if bone==lower else .052,8)])
            emit(k,nut,JNT,tag+' actuator crosshead retaining nut',bone)
    # Paired two-stage cylinders; each lane has its own cylinders. The outer
    # lane drives the lower leaf through an intermediate sleeve at half travel.
    for s in (-1,1):
        for lane,cy in (('Lower',-2.64),('Upper',-2.47)):
            bn=lower if lane=='Lower' else upper
            stage='Stage'+tag+('Left' if s>0 else 'Right') if lane=='Lower' else upper
            x=s*1.02
            fixed=mach(rod((x,cy,2.78),(x,cy,4.20),.075,8),
                cuts=[((x,cy,2.76),(x,cy,4.18),.054,8)])
            emit(k,fixed,SEC,tag+' fixed hydraulic cylinder with bored gland')
            emit(k,block((x-.068,cy-.065,4.20),(x+.068,cy+.065,4.215)),FRM,tag+' overhead cylinder mounting flange')
            # Intermediate stage moves 1.20 m and remains captive at both ends.
            if lane=='Lower':
                sleeve=mach(rod((x,cy,1.55),(x,cy,2.95),.052,8),
                    cuts=[((x,cy,1.53),(x,cy,2.93),.030,8)])
                emit(k,sleeve,JNT,tag+' hollow intermediate telescope sleeve',stage)
                # Parent Root guide holds this sleeve; connection is through
                # the gland's annular bearing rather than material intersection.
                emit(k,rod((x,cy,2.95),(x,cy,2.955),.054,8),FRM,tag+' intermediate piston bearing ring',stage)
                emit(k,rod((x,cy,.218),(x,cy,1.70),.028,8),JNT,tag+' lower hydraulic rod',bn)
            else:
                emit(k,rod((x,cy,1.398),(x,cy,2.95),.052,8),JNT,tag+' upper hydraulic rod',bn)
            # Machined guide covers, clear of rods and both moving slabs.
            rail=block((min(s*.795,s*.93),cy-.075,.12),(max(s*.795,s*.93),cy+.075,4.215))
            rail=mach(rail,boxes=[((s*.8625,cy,2.1),(.17,.074,3.8))])
            old=k.xf
            transform(rail,old)
            rail=cut(rail,block((-5,-5,-3),(5,5,.12)))
            k.xf=Matrix.Identity(4)
            emit(k,rail,FRM,tag+' full-height C-channel slide guide')
            k.xf=old
    # Flush header in the pocket's front plane; no interior lamps.
    seat(k,block((-.56,-2.763,2.525),(.56,-2.756,2.555)),EMI,tag+' exterior door header indicator')
def ramp(k,tag):
    # Approach ramp joins the deck exactly, bounded by foundation.
    ramp=kit.prism_bm([(0,-2.98,0),(0,-2.78,.12),(0,-2.78,0)],1.60,(1,0,0))
    emit(k,ramp,SEC,tag+' foundation-seated walk-in threshold ramp')

def export(rig,objects,prepared=False):
    for pb in rig.pose.bones:
        for c in list(pb.constraints):pb.constraints.remove(c)
    if not prepared:common.prepare_export([rig,*objects],HERE,NAME)
    door_actions.install_fbx_filter()
    kit.select_only([rig,*objects])
    bpy.ops.export_scene.fbx(filepath=str(HERE/'hub.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/'hub.glb'),export_format='GLB',use_selection=True,
        export_yup=True,export_apply=False,export_skins=True,export_def_bones=True,
        export_animations=True,export_animation_mode='ACTIONS',export_anim_single_armature=True,
        export_reset_pose_bones=True,export_force_sampling=True,export_materials='EXPORT')
    door_actions.isolate_glb(HERE/'hub.glb')

def make_surface(rig):
    contour=outline(2.78,0)
    terrain=surface.create(rig,contour,2.4,True,subdivisions=3)
    points=[]
    for a,b in zip(contour,contour[1:]+contour[:1]):
        points.extend(Vector(a).lerp(Vector(b),i/3) for i in range(3))
    for i,v in enumerate(terrain.data.vertices):
        p=points[i%len(points)]
        v.co.x=p.x+(v.co.x-p.x)*.15
        v.co.y=p.y+(v.co.y-p.y)*.15
        v.co.z*=.30
        if abs(v.co.x)<1.2 or abs(v.co.y)<1.2:v.co.z=0
    terrain.data.update()
    for f in terrain.data.polygons:
        if f.normal.z<0:f.flip()
    terrain.data.update()
    return terrain

def main():
    if '--surface-only' in sys.argv:
        bpy.ops.wm.open_mainfile(filepath=str(HERE/'hub.blend'))
        report=json.loads((HERE/'hub_rig.json').read_text())
        kit.NAME,kit.TITLE,kit.SLOTS=NAME,TITLE,list(report['materials'])
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        old=bpy.data.objects.get(surface.NAME);bpy.data.objects.remove(old,do_unlink=True)
        terrain=make_surface(rig)
        common.prepare_export([terrain],HERE,NAME)
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
        markers=[o for o in bpy.context.scene.objects if o.type=='EMPTY']
        export(rig,[*meshes,*markers],prepared=True)
        surface.update_report(report,meshes,kit)
        (HERE/'hub_rig.json').write_text(json.dumps(report,indent=2))
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'hub.blend'))
        print('[hub] narrow perimeter regenerated within 6m',flush=True)
        return
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((1,.38,.045),0,.34,3)
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0)
    surface.configure(kit);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS];bsdf=glass.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Alpha'].default_value=.10;glass.diffuse_color=(0,0,0,.10);glass.surface_render_method='DITHERED'
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    kit.GROUPS=();kit.ANIMATIONS={}
    for tag in SIDES:
        for name,travel in (('Door'+tag+'Upper',1.2),('Door'+tag+'Lower',2.4),('Stage'+tag+'Left',1.2),('Stage'+tag+'Right',1.2)):
            axis=rotation(SIDES[tag]).to_3x3()@incline().to_3x3()@Vector((0,0,1))
            kit.JOINT_SPECS.append((name,ROOT,'slide',(0,0,0),tuple(axis),(0,0,1),(0,travel)))
        keys={bn:[(0,0),(12,0),(84,v),(96,v)] for bn,v in
              (('Door'+tag+'Upper',1.2),('Door'+tag+'Lower',2.4),('Stage'+tag+'Left',1.2),('Stage'+tag+'Right',1.2))}
        kit.ANIMATIONS['open_'+tag.lower()]=(False,'BEZIER',keys)
        kit.ANIMATIONS['close_'+tag.lower()]=(False,'BEZIER',{bn:[(96-f,v) for f,v in reversed(ks)] for bn,ks in keys.items()})
    for action in ('open','close'):
        kit.ANIMATIONS[action]=(False,'BEZIER',{bn:ks for tag in SIDES
            for bn,ks in kit.ANIMATIONS[action+'_'+tag.lower()][2].items()})
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    body(k)
    for tag,angle in SIDES.items():
        with k.frame(rotation(angle)@incline()):door(k,tag)
        with k.frame(rotation(angle)):ramp(k,tag)
    for p,label in zip(k.parts,common.LABELS):p.line=label
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    if '--draft' in sys.argv:
        actions=kit.build_actions(rig,joints,[])
        obj=k.to_object('SK_HubDraft');kit.skin(obj,rig)
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'hub_draft.blend'))
        print(f'[hub] DRAFT {kit.triangles(obj)} triangles',flush=True)
        return
    pairs=common.exact_intersections(k)
    kit.check_connectivity(k,joints,[])
    if '--audit-rest' in sys.argv:
        print('[hub] REST AUDIT PASS',flush=True)
        return
    actions=kit.build_actions(rig,joints,[])
    states=kit.action_states(actions,joints)
    unique={tuple(sorted((bn,round(v,7)) for bn,v in state.items())):(tag,state) for tag,state in states}
    kit.check_motion(k,joints,list(unique.values()))
    obj=k.to_object('SK_HubStructure',joints=kit.rotary_joints(joints));kit.skin(obj,rig)
    # Split at material/role boundary, retaining <=5K triangles per mesh.
    doors=obj.copy();doors.data=obj.data.copy();doors.name='SK_HubDoors';bpy.context.scene.collection.objects.link(doors)
    for mesh,keep in ((obj,False),(doors,True)):
        bm=bmesh.new();bm.from_mesh(mesh.data)
        deform=bm.verts.layers.deform.active
        moving={g.index for g in mesh.vertex_groups if g.name!=ROOT}
        remove=[f for f in bm.faces if any(any(i in moving and w>.99 for i,w in v[deform].items()) for v in f.verts)!=keep]
        bmesh.ops.delete(bm,geom=remove,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        hidden=[f for f in bm.faces if all(v.co.z<1e-6 for v in f.verts) and f.normal.z<-.5]
        bmesh.ops.delete(bm,geom=hidden,context='FACES_ONLY');bm.to_mesh(mesh.data);bm.free()
        sys.path.insert(0,str(MODELS/'architecture/lunar_dome'))
        from surface_audit import check_coplanar
        check_coplanar(mesh)
    terrain=make_surface(rig)
    meshes=[obj,doors,terrain]
    assert all(kit.triangles(o)<=5000 for o in meshes),[(o.name,kit.triangles(o)) for o in meshes]
    assert sum(kit.triangles(o) for o in meshes)<=10000
    markers,mount_info=light_mounts.install(rig,[obj],
        [('',(0,0,2.8),(0,0,1))],
        [(tag,(0,0,1.5),(s,s,0)) for tag,s in (('NorthEast',1),('SouthWest',-1))])
    export(rig,[*meshes,*markers])
    poses={}
    for tag in SIDES:
        poses['open_'+tag.lower()]={bn:{'loc':[0,v,0]} for bn,v in
            (('Door'+tag+'Upper',1.2),('Door'+tag+'Lower',2.4),('Stage'+tag+'Left',1.2),('Stage'+tag+'Right',1.2))}
    poses['open_all']={bn:p for pose in poses.values() for bn,p in pose.items()}
    rig['preview_poses']=json.dumps(poses)
    bpy.context.scene['preview_actions']=json.dumps(['open_front','open_left','open_rear','open_right','close'])
    bpy.context.scene['showcase_frame']=json.dumps(dict(lo=[-3,-3,0],hi=[3,3,4.34]))
    report=dict(name=NAME,triangle_budget=10000,ground_envelope_m=[6,6],
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,parent=j.parent,type=j.kind,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        passage_m=dict(width=1.60,height=2.40,threshold=.12,interior_height=3.72),
        glazing=dict(material=GLASS,color=[0,0,0],opacity=.10),gizmos=mount_info,
        checks=dict(exact_solid_pairs=pairs,connectivity=True,motion_states=len(states),coplanar=True),
        mechanics='Four independently guided telescoping doors; upper travel 1.2m, lower 2.4m; double-acting two-stage hydraulic cylinders, separate storage depth lanes, 140mm minimum engagement; fixed overhead flanges and bored C-section guides.',
        placement='6x6m centred floor envelope including optional apron; front -Y; library only')
    surface.update_report(report,meshes,kit)
    dimensions.report(NAME,report,width=1.5,height=2.40,floors=[.12],ceilings=[3.84])
    (HERE/'hub_rig.json').write_text(json.dumps(report,indent=2))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'hub.blend'))
    print(f'[hub] PASS: {report["triangles"]} triangles; {len(k.parts)} manufactured parts',flush=True)

if __name__=='__main__':main()
