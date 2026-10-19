"""Machined lunar lodge, 15 x 15 m foundation, front -Y. Library only.

The proven cistern pressure-door cartridge is shared; the square lodge shell,
windows, compression roof and service equipment are authored here.
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
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
spec=importlib.util.spec_from_file_location('lodge_pressure_tools',HERE.parent/'cistern/model.py')
cs=importlib.util.module_from_spec(spec);spec.loader.exec_module(cs)
common,kit=cs.common,cs.kit
sys.path.insert(0,str(HERE.parent))
import dimensions
import perimeter_surface as surface
import light_mounts
NAME,TITLE='lodge','Lodge'
BUDGET=10000
ROOT,PRI,SEC,FRM,JNT,EMI=cs.ROOT,cs.PRI,cs.SEC,cs.FRM,cs.JNT,cs.EMI
GLASS='M_Glass'
block,rod,emit,seat,mach,xf=cs.block,cs.rod,cs.emit,cs.seat,cs.mach,cs.xf
cs.HERE,cs.NAME,cs.TITLE,cs.BUDGET=HERE,NAME,TITLE,BUDGET
FLOOR,CEILING=.10,3.10
WINDOW_WIDTH=1.30
MULLION_WIDTH=.22
BAY_WIDTH=4.0-MULLION_WIDTH
WINDOW_GAP=(BAY_WIDTH-2*WINDOW_WIDTH)/3
WINDOW_OFFSET=(WINDOW_WIDTH+WINDOW_GAP)/2

def fastener(k,at,normal,label,bone=ROOT,r=.021):
    """Low-profile external hex drive, flat face on its manufactured seat."""
    p=Vector(at);n=Vector(normal).normalized()
    emit(k,rod(p,p+n*.012,r,6),JNT,label,bone)

cs.fastener=fastener

def annulus(r,inner,a,b,n=6):
    # Closed collar is lofted directly; four coaxial sections share vertices.
    a,b=Vector(a),Vector(b);axis=(b-a).normalized()
    bm=cs.revolve([(r,0),(r,(b-a).length),(inner,(b-a).length),(inner,0)],n)
    m=axis.to_track_quat('Z','Y').to_matrix().to_4x4();m.translation=a
    return xf(bm,m)

def contour(r,z=0,c=.80):
    return common.outline(2*r,2*r,c,z)

def shell(stations):
    return kit.loft_rings([contour(r,z,c) for r,z,c in stations])

def surface_contour():
    points=contour(7.5);out=[]
    for a,b in zip(points,points[1:]+points[:1]):
        out.append(a)
        if abs(a[1])>7.49 and abs(b[1])>7.49:
            out.extend((x,a[1],0) for x in ((1.4,0,-1.4) if a[0]>b[0] else (-1.4,0,1.4)))
    return out

def trim(base,tool):
    base.normal_update();tool.normal_update()
    bmesh.ops.triangulate(base,faces=base.faces[:])
    return cs.boolean_bm(base,tool,'DIFFERENCE')

def check_mount_lands(k):
    """Every hinge support pad is wholly on an unchamfered host face."""
    tested=0
    for rear in (False,True):
        sign=-1 if rear else 1
        bezel=next(p for p,label in zip(k.parts,common.LABELS)
                   if label=='machined door surround and seal land' and (p.lo.y>0)==rear)
        leaf=next(p for p,label in zip(k.parts,common.LABELS)
                  if label=='lofted pressure leaf with recessed face and lock tunnel' and (p.lo.y>0)==rear)
        for z in (.43,1.45,2.48):
            for x in (-1.19,-1.06):
                for dz in (-.09,-.052,.052,.09):
                    dimensions.require_land(bezel,Matrix.Diagonal((sign,sign,1,1))@cs.PRESSURE_FRAME@Vector((x,-7.38,z+dz)),(0,1,0))
                    tested+=1
            for x in (-.935,-.915):
                for dz in (-.03,.03):
                    dimensions.require_land(leaf,Matrix.Diagonal((sign,sign,1,1))@cs.PRESSURE_FRAME@Vector((x,-7.295,z+dz)),(0,1,0))
                    tested+=1
    return tested

def architecture(k):
    # Square footprint with an actual room cavity. A formed lower skirt carries
    # the wall, and both vestibules are welded into this continuous shell.
    deck=shell([(7.5,0,.85),(7.5,.10,.85)])
    for sign in (-1,1):
        cut=kit.prism_bm([(0,sign*7.60,-1/60),(0,sign*6.90,.10),
                         (0,sign*6.90,.30),(0,sign*7.60,.30)],1.68,(1,0,0))
        deck=trim(deck,cut)
    emit(k,deck,SEC,'continuous grade-bearing deck with twin flush approach ramps')
    base=shell([(7.40,.10,.85),(7.40,.22,.85),(6.95,.75,.72),
                (6.85,.80,.70),(6.85,2.95,.70)])
    cavity=shell([(6.50,.099,.60),(6.50,3.20,.60)])
    hood=kit.loft_rings([[(x,y,z) for x,z in cs.outline(w,.10,h)]
        for y,w,h in ((-7.30,1.27,3.02),(-7.15,1.34,3.10),
                      (-6.65,1.30,3.10),(-6.35,1.14,2.95))])
    for h in (hood,xf(hood.copy(),Matrix.Rotation(math.pi,4,'Z'))):
        bmesh.ops.triangulate(base,faces=base.faces[:])
        base=cs.boolean_bm(base,h,'UNION')
    base=trim(base,cavity)
    for y in (-6.95,6.95):base=trim(base,cs.entry_passage(1.,.10,2.80,y-1.3,y+1.3))
    base=cs.pressure_ports(base)
    # Two narrow through-windows per bay. Three equal gaps span the clear bay:
    # mullion-to-window, window-to-window and window-to-mullion.
    inlays=[]
    for sign in (-1,1):
        for y in (centre+offset for centre in (-4.,0.,4.) for offset in (-WINDOW_OFFSET,WINDOW_OFFSET)):
            m=common.frame((sign*6.85,y,1.86),(sign,0,0),(0,0,1))
            opening=xf(common.loft([(WINDOW_WIDTH,.91,.11,-.50),(WINDOW_WIDTH,.91,.11,.05)]),m)
            base=trim(base,opening)
            gasket=common.ring(WINDOW_WIDTH-.0004,.9096,.1098,WINDOW_WIDTH-.14,.77,.075,-.35,-.020)
            glass=common.loft([(WINDOW_WIDTH-.1404,.7696,.0748,-.080),(WINDOW_WIDTH-.1404,.7696,.0748,-.0202)])
            inlays.extend(((xf(gasket,m),FRM,'flush continuous window gasket'),
                           (xf(glass,m),GLASS,'black ten-percent-opaque pressure glazing')))
    # Material boundaries belong to the shell; no overlapping facade tiles.
    bmesh.ops.recalc_face_normals(base,faces=base.faces[:])
    for f in base.faces:
        p=f.calc_center_median()
        interior=abs(f.normal.z)<.50 and f.normal.dot(Vector((p.x,p.y,0)))<-.20
        f.material_index=kit.SLOTS.index(PRI if interior or p.z>.80 else SEC)
    bmesh.ops.triangulate(base,faces=base.faces[:]);mats=[f.material_index for f in base.faces]
    made=k.emit(base,ROOT,PRI,False,convex=False,exact=True)
    layer=k.bm.faces.layers.int.get('delivery_module') or k.bm.faces.layers.int.new('delivery_module')
    for f,mat in zip(made,mats):f.material_index=mat;f[layer]=1
    common.LABELS.append('continuous formed skirt, pressure wall and twin welded vestibules')
    for bm,mat,label in inlays:emit(k,bm,mat,label)
    # Structural mullions end square on the skirt shoulder and eave. Their
    # integral foot and head are seated against the actual shell, not chamfers.
    for s in (-1,1):
        for y in (-6.,-2.,2.,6.):
            m=common.frame((s*6.85,y,1.87),(s,0,0),(0,0,1))
            with k.frame(m):
                beam=common.loft([(.14,2.14,.025,0),(.22,2.14,.025,.055),(.17,2.04,.02,.085)])
                emit(k,beam,FRM,'wall mullion with integral square bearing lands')
                for z in (-.94,.94):cs.fastener(k,(0,z,.085),(0,0,1),'mullion end fastener',r=.019)
    # Front/rear pressure-shell walls remain clean; external X gussets and
    # their fasteners were removed at the user's request.

def roof(k):
    cs.MODULE=2
    # Closed pressure roof with a constant 3.1 m soffit; hollow lofted shoulder
    # bridges the wall to a flat equipment roof. All sections share topology.
    bm=bmesh.new();rows=[[bm.verts.new(p) for p in contour(r,z,c)] for r,z,c in
        ((6.85,2.95,.70),(7.10,3.00,.85),(7.10,3.16,.85),(6.92,3.28,.80),
         (6.42,3.93,.65),(6.32,4.02,.62),(6.32,4.14,.62),(5.98,4.14,.55),
         (5.98,3.98,.55),(6.32,3.98,.62),(6.32,3.93,.62),(6.50,3.10,.60),
         (6.50,2.95,.60))]
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(len(a)):bm.faces.new((a[i],a[(i+1)%len(a)],b[(i+1)%len(a)],b[i]))
    seat(k,bm,PRI,'lofted compression crown and formed sealed eave')
    layer=k.bm.faces.layers.int['delivery_module']
    for face in k.bm.faces:
        if face[layer]==2:
            z=face.calc_center_median().z
            if 2.99<z<3.161 or 4.019<z:face.material_index=kit.SLOTS.index(FRM)
    emit(k,shell([(6.50,3.10,.60),(6.32,3.93,.62),(6.32,3.98,.62)]),SEC,'continuous walkable-room pressure ceiling and roof deck')
    # Compression bands use the crown's own faces, with no duplicate overlays.
    # Smooth formed shoulder; the user requested removal of all slope ribs.
    # Continuous deck: the user requested removal of the central plate assembly.
    for x,y,w,h in ((-3.75,-3.7,1.8,1.6),(3.75,-3.7,1.8,1.6),
                    (-3.75,3.4,1.8,1.6),(3.75,3.4,1.8,1.6)):
        equipment(k,x,y,w,h)
    cs.MODULE=1

def equipment(k,x,y,w,h):
    with k.frame(Matrix.Translation((x,y,0))):
        flange=common.loft([(w+.18,h+.18,.13,3.98),(w+.18,h+.18,.13,4.04)])
        emit(k,flange,FRM,'equipment bolted flat roof mounting flange')
        pod=common.loft([(w,h,.16,4.04),(w,h,.16,4.43),(w-.18,h-.18,.13,4.61)])
        pod=mach(pod,boxes=[((0,-h/2,4.32),(w-.46,.065,.30)),((0,0,4.62),(w-.48,h-.48,.12))])
        emit(k,pod,PRI,'lofted sealed thermal and power equipment shroud')
        emit(k,block((-(w-.46)/2,-h/2+.0002,4.17),((w-.46)/2,-h/2+.0323,4.47)),FRM,'recessed equipment intake cartridge')
        for z in (4.24,4.40):
            seat(k,block((-(w-.50)/2,-h/2-.012,z-.012),((w-.50)/2,-h/2+.032,z+.012)),SEC,'supported intake louvre')
        emit(k,common.loft([(w-.4804,h-.4804,.07,4.5602),(w-.4804,h-.4804,.07,4.595)]),FRM,'flush top service grille')
        for xx in (-(w+.18)/2+.105,(w+.18)/2-.105):
            for yy in (-(h+.18)/2+.105,(h+.18)/2-.105):
                # The complete 21 mm head lies inside the outer diagonal land
                # and outside the pod's larger corner chamfer, not on an edge.
                outer_clear=((w+.18)/2-abs(xx)+(h+.18)/2-abs(yy)-.13)/math.sqrt(2)
                inner_clear=(.16-(w/2-abs(xx)+h/2-abs(yy)))/math.sqrt(2)
                assert min(outer_clear,inner_clear,.105)>.021+.005,('roof bolt full-head land',xx,yy)
                cs.fastener(k,(xx,yy,4.04),(0,0,1),'equipment mounting flange bolt',r=.021)
        # Indicator has a genuine milled pocket with a non-coplanar lens.
        m=common.frame((w/2,0,4.33),(1,0,0),(0,0,1))
        with k.frame(m):
            bezel=mach(common.loft([(.22,.10,.015,0),(.22,.10,.015,.024)]),
                       boxes=[((0,0,.026),(.16,.045,.014))])
            emit(k,bezel,FRM,'seated equipment status bezel')
            emit(k,block((-.0798,-.0223,.0192),(.0798,.0223,.024)),EMI,'flush cyan equipment status lens')
    # Terminated U-shaped roof conduit. Every end is normal to a gland flange;
    # bored collars attach it to the flat roof every 0.75 m along the run.
    points=[(x+w/2,y+.40,4.28),(x+w/2+.18,y+.40,4.28),
            (x+w/2+.26,y+.40,4.20),(x+w/2+.26,y+.40,4.12),
            (x+w/2+.26,y+.30,4.12),(x+w/2+.26,y-.80,4.12),
            (x+w/2+.26,y-.90,4.12),(x+w/2+.26,y-.98,4.08),
            (x+w/2+.26,y-.98,4.015),(x+w/2+.26,y-.98,3.98)]
    seat(k,cs.pipe(points,.028,6),JNT,'terminated swept roof service conduit')
    for yy in (y-.65,y+.20):
        xx=x+w/2+.26
        # Analytic foot has the same two bottom facets as the hexagonal collar.
        # Both ends contact over their whole width, rather than at a point.
        collar=annulus(.051,.033,(xx,yy-.025,4.12),(xx,yy+.025,4.12))
        emit(k,collar,SEC,'bored roof conduit clamp')
        # For a six-sided ring the lowest pair of vertices make a level land.
        low=4.12-.051*math.sqrt(3)/2
        foot=block((xx-.0255,yy-.025,3.98),(xx+.0255,yy+.025,low))
        emit(k,foot,SEC,'square-ended roof clamp pedestal with full collar contact')
    for p,n in ((points[0],(1,0,0)),(points[-1],(0,0,1))):
        p=Vector(p);n=Vector(n)
        flange=annulus(.062,.033,p,p+n*.028)
        emit(k,flange,FRM,'roof conduit terminated gland flange')

def main():
    common.CORNER_STEPS=1;common.LABELS.clear();kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5)
    kit.MATERIALS[GLASS]=((0,0,0),0,.15,0);surface.configure(kit)
    kit.SLOTS=list(kit.MATERIALS);kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS];node=glass.node_tree.nodes.get('Principled BSDF')
    node.inputs['Alpha'].default_value=.10;glass.diffuse_color=(0,0,0,.10)
    glass.surface_render_method='BLENDED';glass.use_backface_culling=True
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
        ('Door',ROOT,'hinge',(cs.PX,cs.PY,1.45),(0,0,1),(0,-1,0),(-110,0)),
        ('Lock','Door','slide',(.90,-7.235,1.45),(1,0,0),(1,0,0),(-.18,0)),
        ('RearDoor',ROOT,'hinge',(-cs.PX,-cs.PY,1.45),(0,0,1),(0,1,0),(-110,0)),
        ('RearLock','RearDoor','slide',(-.90,7.235,1.45),(-1,0,0),(-1,0,0),(-.18,0))]
    cs.resize_door_specs()
    kit.GROUPS=();kit.ANIMATIONS=dimensions.scale_tracks(cs.specs(),{'Lock':.75,'RearLock':.75})
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    cs.MODULE=1;architecture(k);roof(k)
    cs.MODULE=3;cs.door(k);cs.REAR_DOOR=True
    with k.frame(Matrix.Rotation(math.pi,4,'Z')):cs.door(k)
    cs.REAR_DOOR=False
    for p,label in zip(k.parts,common.LABELS):p.line=label
    land_samples=check_mount_lands(k)
    rig=dimensions.bake(NAME,kit,k,joints,rig)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[]);states=kit.action_states(actions,joints)
    states.extend((f'front sweep {a}',{'Door':-a,'Lock':-.18*.75}) for a in range(111))
    states.extend((f'rear sweep {a}',{'RearDoor':-a,'RearLock':-.18*.75}) for a in range(111))
    kit.check_motion(k,joints,states);kit.reset_pose(rig)
    source=[dict(label=l,bone=p.bone,vertices=[list(v) for v in p.verts],triangles=p.faces) for p,l in zip(k.parts,common.LABELS)]
    (HERE/f'{NAME}_source_report.json').write_text(json.dumps(source))
    body=k.to_object('SK_'+TITLE,joints=kit.rotary_joints(joints));kit.skin(body,rig)
    bm=bmesh.new();bm.from_mesh(body.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if all(v.co.z<1e-6 for v in f.verts) and f.normal.z<-.5],context='FACES_ONLY')
    bm.to_mesh(body.data);bm.free()
    sys.path.insert(0,str(HERE.parents[1]/'architecture/lunar_dome'))
    from surface_audit import check_coplanar
    check_coplanar(body)
    assert all(abs(v.co.x)<=7.50001 and abs(v.co.y)<=7.50001 for v in body.data.vertices)
    meshes=cs.split_modules(body)
    meshes.append(surface.create(rig,surface_contour(),3.6,rear_entrance=True))
    counts={o.name:kit.triangles(o) for o in meshes}
    assert all(n<=5000 for n in counts.values()),counts
    assert sum(counts.values())<=BUDGET,counts
    markers,mount_info=light_mounts.install(rig,meshes,
        [(tag,(x,y,2.7),(0,0,1)) for tag,x,y in (('FrontLeft',-3,-3),('FrontRight',3,-3),('RearLeft',-3,3),('RearRight',3,3))],
        [(tag,(0,y,2.55),direction) for tag,y,direction in (('Left',0,(1,0,0)),('Right',0,(-1,0,0)))])
    if '--draft' not in sys.argv:cs.export_runtime(rig,meshes,markers)
    report=dict(name=NAME,triangle_budget=BUDGET,triangle_budget_per_mesh=5000,
        dimensions_m=dict(width=15,depth=15,height=4.61),materials=[],
        bones=[dict(name=j.name,parent=j.parent,kind=j.kind) for j in joints.values()],
        joints=[dict(bone=j.name,type=j.kind,parent=j.parent,pivot=list(j.pivot),axis=list(j.axis),range=j.limits) for j in joints.values()],
        animations={n:dict(frames=list(a.frame_range),fps=30,loop=False) for n,a in actions.items()},
        checks=dict(connected_parts=len(k.parts),hinge_land_samples=land_samples,exact_solid_pairs=pairs,motion_states=len(states),coplanar=True,interior_retained=True),
        gizmos=mount_info,glazing=dict(material=GLASS,color=[0,0,0],opacity=.10),
        windows=dict(per_side=6,per_bay=2,width_m=WINDOW_WIDTH,height_m=.91,clear_bay_width_m=BAY_WIDTH,equal_gap_m=WINDOW_GAP,offset_from_bay_centre_m=WINDOW_OFFSET),
        entrance=dict(width_m=2.,height_m=2.70,floor_m=FLOOR,ceiling_m=CEILING,door_swing_deg=110),
        placement='15 x 15 m fixed square foundation; front -Y; origin at grade; optional apron separate; library only',
        mechanics='Three retained interleaved hinges per entrance; coaxial geared drive; captive enclosed shoot bolt retracts 180 mm before 110 degree outward swing. Bolted roof equipment, bored pipe clamps, seated glands and structural window mullions. Front/rear gussets, slope ribs and central roof plate omitted at user request.')
    surface.update_report(report,meshes,kit)
    dimensions.report(NAME,report,width=1.5,height=2.70,floors=[FLOOR],ceilings=[CEILING])
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    rig['preview_poses']=json.dumps({'unlocked':{'Lock':{'loc':[0,-.18,0]}},
        'open':{'Door':{'rot':[-110,0,0]},'Lock':{'loc':[0,-.18,0]}},
        'rear_open':{'RearDoor':{'rot':[-110,0,0]},'RearLock':{'loc':[0,-.18,0]}},
        'both_open':{'Door':{'rot':[-110,0,0]},'Lock':{'loc':[0,-.18,0]},'RearDoor':{'rot':[-110,0,0]},'RearLock':{'loc':[0,-.18,0]}}})
    rig['preview_pose_views']=json.dumps({'rear_open':['rear_right'],'both_open':['front_left','rear_right']})
    bpy.context.scene['preview_actions']=json.dumps(['open_front','open_rear','close_front','close_rear'])
    bpy.context.scene['preview_frame']=json.dumps(dict(lo=[-8.4,-8.4,0],hi=[8.4,8.4,4.61]))
    dimensions.preview(NAME,rig,joints)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS {report["triangles"]} triangles; {len(k.parts)} manufactured parts',flush=True)

if __name__=='__main__':main()
