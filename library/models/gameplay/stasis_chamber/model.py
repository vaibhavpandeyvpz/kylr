"""Opening-door stasis chamber: headless Blender 5.2, metres, front -Y.

The library's manufactured-solid helpers keep seats exact; solids are audited
before culling. Door open/close actions are exported; runtime integration remains separate.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import json
import math
from contextlib import contextmanager
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]/'environments'))
import light_common as common

kit, ROOT = common.kit, common.ROOT
NAME, TITLE = 'stasis_chamber', 'StasisChamber'
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
BRZ, GLASS = 'M_Bronze', 'M_Glass'
emit, block, rod, loft = common.emit, common.block, common.rod, common.loft
DECK, CEILING = .53, 2.33  # cavity floor and ceiling, rather than outer shell ends
FRONT = common.frame((0, -.60, 1.43), (0, -1, 0), (0, 0, 1))
# Each XZ section has the same 0.8 m flat along its bottom. The pedestal
# seats on that flat, rather than the shell's wider shoulder silhouette.
SHROUD_STATIONS=[(1.00,1.90,.10,-1.22),(1.06,1.90,.13,-1.16),
                  (1.06,1.90,.13,-.055),(1.00,1.90,.10,0)]
DOOR='Door'
HINGE=Vector((.55,-.65,1.43))
OPEN_ANGLE=120.0
@contextmanager
def bone(name):
    previous=common.ROOT;common.ROOT=name
    try:yield
    finally:common.ROOT=previous

BEZEL_DEPTH=.025
SEAT_X=SHROUD_STATIONS[-1][0]/2-SHROUD_STATIONS[-1][2]
SEAT_Y0,SEAT_Y1=FRONT.translation.y-BEZEL_DEPTH,FRONT.translation.y-SHROUD_STATIONS[0][3]
SEAT_Z=FRONT.translation.z-SHROUD_STATIONS[-1][1]/2
assert all(abs(w/2-c-SEAT_X)<1e-8 for w,h,c,d in SHROUD_STATIONS)


def move(bm, at):
    for v in bm.verts:
        v.co += Vector(at)
    return bm


def cast(k, stations, mat, label, at=(0, 0, 0), **cuts):
    emit(k, kit.machine(move(loft(stations), at), **cuts), mat, label)


def face(k, at, normal, w, h, depth, mat, label, **cuts):
    with k.frame(common.frame(at, normal, (0, 0, 1))):
        corner=min(.012,w*.20,h*.20)
        cast(k, [(w, h, corner, 0), (w, h, corner, depth)], mat, label, **cuts)


def base(k):
    cast(k, [(1.25, 1.50, .045, 0), (1.25, 1.50, .045, .026),
             (1.21, 1.46, .035, .065), (1.21, 1.46, .035, .075)], JNT,
         'foundation flange')
    for x in (-.545, .545):
        for y in (-.65, .65):
            common.bolt(k, x, y, .075, 'foundation bolt', .010)
    shell = loft([(.98, 1.24, .06, .075), (1.04, 1.28, .075, .115),
                  (1.04, 1.28, .075, .345), (.96, 1.24, .055, .42)])
    pockets = [((0, -.635, .245), (.49, .045, .22)),
               ((0, .635, .245), (.62, .045, .22))]
    pockets += [((s*.513, 0, .245), (.04, .54, .22)) for s in (-1, 1)]
    emit(k, kit.machine(shell, boxes=pockets), SEC, 'lofted pump and power cabinet')
    for y, n, w in ((-.6125, -1, .488), (.6125, 1, .618)):
        face(k, (0, y, .245), (0, n, 0), w, .218, .025, PRI,
             'seated service hatch', boxes=[((0, -.04, .026), (.23, .055, .018))])
        with k.frame(common.frame((0, y, .245), (0, n, 0), (0, 0, 1))):
            emit(k, block((-.114, -.066, .017), (.114, -.014, .021)), FRM,
                 'recessed service intake')
            for x in (-.18, .18):
                for z in (-.075, .075):
                    common.bolt(k, x, z, .025, 'hatch socket screw', .006)
    for s in (-1, 1):
        face(k, (s*.493, 0, .245), (s, 0, 0), .538, .218, .025, FRM,
             'seated heat exchanger grille',
             boxes=[((x, 0, .030), (.018, .15, .045)) for x in (-.18, -.12, -.06, 0, .06, .12, .18)])
    lower=common.outline(.96,1.24,.055,.42)
    # Eight distinct stations preserve the loft topology while the top
    # becomes a square-cornered rectangular butt seat under the shell.
    top=[(SEAT_X,.565,SEAT_Z),(SEAT_X,SEAT_Y1,SEAT_Z),
         (-SEAT_X,SEAT_Y1,SEAT_Z),(-SEAT_X,.565,SEAT_Z),
         (-SEAT_X,-.565,SEAT_Z),(-SEAT_X,SEAT_Y0,SEAT_Z),
         (SEAT_X,SEAT_Y0,SEAT_Z),(SEAT_X,-.565,SEAT_Z)]
    emit(k,kit.loft_rings([lower,top]),FRM,'load bearing chamber sill')


def enclosure(k):
    # XZ rounded/chamfered outlines lofted through depth. The cavity cut
    # leaves an 80 mm rear wall and a continuous structural perimeter.
    with k.frame(FRONT):
        shell = loft(SHROUD_STATIONS)
        cavity = common.outline(.82, 1.80, .085, -.56)
        shell = kit.machine(shell, subtract=[(cavity, (0, 0, 1), 1.16)],
                            boxes=[((s*.533,0,-.59),(.04,1.30,.44)) for s in (-1,1)])
        emit(k, shell, PRI, 'lofted pressure enclosure')
        with bone(DOOR):
            # Moving door: gasket seats against the cavity wall, bezel
            # surrounds it, glazing terminates exactly against the gasket.
            emit(k, common.ring(.820, 1.800, .085, .800, 1.780, .075, -.008, .015),
                 FRM, 'continuous pressure seal')
            bezel = common.ring(1.00,1.90,SHROUD_STATIONS[-1][2],.820,1.800,.085,0,BEZEL_DEPTH)
            emit(k, bezel, SEC, 'retained door bezel')
            emit(k, loft([(.800, 1.780, .075, -.006), (.800, 1.780, .075, .008)]),
                 GLASS, 'seated cyan viewing panel')
            for x in (-.455, .455):
                for z in (-.40, .40):
                    common.bolt(k, x, z, .025, 'bezel captive screw', .005)
            for z in (-.925,):
                emit(k, block((-.075, z-.008, .025), (.075, z+.008, .028)),
                     BRZ, 'seal inspection tab')
    # Two welded stationary bearing brackets carry a retained vertical pin.
    # A bored moving knuckle and welded leaf carry the door between them.
    for z in (.80,2.06):
        for end in (-1,1):
            zz=z+end*.055
            bracket=block((.505,-.672,zz-.015),(.575,-.540,zz+.015))
            bracket=kit.machine(bracket,cuts=[((HINGE.x,HINGE.y,zz-.015),(HINGE.x,HINGE.y,zz+.015),.0095,10)])
            bracket=common.trim_seats(bracket,[p for p,tag in zip(k.parts,common.LABELS) if tag=='lofted pressure enclosure'])
            emit(k,bracket,SEC,'hinge bearing foot')
        pin=rod((HINGE.x,HINGE.y,z-.070),(HINGE.x,HINGE.y,z+.070),.009,10)
        emit(k,pin,JNT,'retained hinge pin')
        for end in (-1,1):
            emit(k,rod((HINGE.x,HINGE.y,z+end*.070),(HINGE.x,HINGE.y,z+end*.075),.014,10),BRZ,'hinge pin retaining head')
        with bone(DOOR):
            knuckle=rod((HINGE.x,HINGE.y,z-.038),(HINGE.x,HINGE.y,z+.038),.017,12)
            leaf=block((.445,-.643,z-.026),(.550,-.625,z+.026))
            knuckle=kit.machine(knuckle,union=[leaf],cuts=[((HINGE.x,HINGE.y,z-.05),(HINGE.x,HINGE.y,z+.05),.0095,10)])
            emit(k,knuckle,JNT,'door hinge barrel and welded leaf')
            face(k,(-.458,-.625,z),(0,-1,0),.047,.115,.018,FRM,'door compression latch')
            face(k,(-.458,-.643,z),(0,-1,0),.027,.07,.006,JNT,'seated latch lever')



def pipe_mesh(points, radius=.018, sides=8):
    # Swept mitred tube with sealed ends. Ends are perpendicular to their
    # port seats; couplers and clamps are bored around the exact tube.
    pts = [Vector(p) for p in points]
    dirs = [(b-a).normalized() for a, b in zip(pts, pts[1:])]
    ref = Vector((1, 0, 0)) if abs(dirs[0].x)<.9 else Vector((0, 1, 0))
    normals = [(ref-dirs[0]*ref.dot(dirs[0])).normalized()]
    for a, b in zip(dirs, dirs[1:]):
        normals.append(a.rotation_difference(b)@normals[-1])
    import math
    rings = []
    for i, p in enumerate(pts):
        d = dirs[max(0, i-1)];n = normals[max(0, i-1)];u = d.cross(n)
        offsets = [(n*math.cos(j*2*math.pi/sides)+u*math.sin(j*2*math.pi/sides))*radius for j in range(sides)]
        if 0<i<len(pts)-1:
            bis = (dirs[i-1]+dirs[i]).normalized()
            offsets = [o-d*(o.dot(bis)/d.dot(bis)) for o in offsets]
        rings.append([p+o for o in offsets])
    return kit.loft_rings(rings)


def internals(k):
    # Interior machinery stays in the back 90 mm service bay, leaving the
    # central occupant volume unobstructed, unlike the busy concept image.
    face(k, (0, .30, 1.43), (0, -1, 0), .68, 1.62, .022, SEC,
         'rear thermal exchange plate')
    for z in (.70, 2.16):
        face(k, (0, .278, z), (0, -1, 0), .62, .12, .054, FRM,
             'coolant distribution manifold')
        for x in (-.10, .10):
            face(k, (x, .224, z), (0, -1, 0), .04, .022, .003, BRZ,
                 'manifold port marker')
    for s in (-1, 1):
        x=s*.255
        points=[(x,.224,.70),(x,.18,.70),(x+s*.025,.16,.76),
                (x+s*.025,.16,2.10),(x,.18,2.16),(x,.224,2.16)]
        emit(k, pipe_mesh(points,.016), JNT, 'rear coolant return tube')
        for z in (1.02, 1.84):
            bracket = block((x+s*.025-.028,.133,z-.025),
                            (x+s*.025+.028,.278,z+.025))
            bracket = kit.machine(bracket, cuts=[((x+s*.025,.16,z-.035),
                                                  (x+s*.025,.16,z+.035),.018,12)])
            emit(k, bracket, FRM, 'bored tube saddle clamp')
    for x in (-.13, .13):
        face(k, (x,.278,1.43), (0,-1,0), .065, .95, .020, FRM,
             'backplane instrumentation rail')
        for z in (1.02,1.40,1.78):
            face(k, (x,.258,z), (0,-1,0), .055,.060,.020,PRI,
                 'rail mounted sensor module',boxes=[((0,0,.020),(.032,.010,.004))])
            face(k, (x,.240,z), (0,-1,0), .030,.008,.002,EMI,
                 'sensor status lens')
    # Sidewall wash lights on broad interior flats.
    for s in (-1,1):
        face(k,(s*.410,.20,1.43),(-s,0,0),.18,.85,.016,FRM,
             'interior lighting channel')
        face(k,(s*.394,.20,1.43),(-s,0,0),.12,.81,.004,EMI,
             'sealed cyan light strip')


def crown(k):
    cast(k,[(.94,1.22,.06,2.38),(1.04,1.28,.075,2.41),
            (1.04,1.28,.075,2.50),(.92,1.18,.05,2.565)],SEC,
         'lofted condenser crown',at=(0,.01,0),
         boxes=[((0,-.622,2.465),(.36,.034,.070))])
    face(k,(0,-.605,2.465),(0,-1,0),.358,.068,.012,FRM,
         'crown ventilation grille',
         boxes=[((x,0,.012),(.012,.045,.028)) for x in (-.12,-.06,0,.06,.12)])
    for s in (-1,1):
        x=s*.32
        for y in (-.19,.23):
            emit(k,rod((x,y,2.565),(x,y,2.580),.032,10),FRM,'roof coolant gland')
        emit(k,pipe_mesh([(x,-.19,2.58),(x,-.19,2.63),(x,-.15,2.66),
                         (x,.19,2.66),(x,.23,2.63),(x,.23,2.58)],.019),
             JNT,'roof condenser bridge pipe')
    with bone(DOOR):
        face(k,(0,-.625,2.35),(0,-1,0),.25,.035,.005,FRM,'recessed status strip carrier',
             boxes=[((x,0,.005),(.024,.020,.004)) for x in (-.08,-.04,0,.04,.08)])
        for x in (-.08,-.04,0,.04,.08):
            face(k,(x,-.628,2.35),(0,-1,0),.022,.018,.002,EMI,'readiness indicator')



def service_sides(k):
    for s in (-1,1):
        face(k,(s*.513,-.01,1.43),(s,0,0),.438,1.298,.014,SEC,
             'recessed side service cassette',
             boxes=[((0,z,.016),(.20,.018,.014)) for z in (-.44,-.39,.39,.44)])
        # A clamped external stainless service line is a closed loop between
        # two side ports. The straight middle is guarded by two bored saddles.
        x=s*.527
        points=[(x,.09,.99),(s*.579,.09,.99),(s*.600,.09,1.02),
                (s*.600,.09,1.84),(s*.579,.09,1.87),(x,.09,1.87)]
        emit(k,pipe_mesh(points,.012),JNT,'side service loop')
        for z in (1.19,1.67):
            bracket=block((min(x,s*.615),.068,z-.016),(max(x,s*.615),.112,z+.016))
            bracket=kit.machine(bracket,cuts=[((s*.600,.09,z-.025),(s*.600,.09,z+.025),.014,12)])
            emit(k,bracket,FRM,'side loop retaining saddle')
        for z in (.85,2.01):
            with k.frame(common.frame((s*.527,-.01,z),(s,0,0),(0,0,1))):
                for x0 in (-.16,.16):common.bolt(k,x0,0,0,'side cassette screw',.006)
        # Front pull handle, both ends welded square onto bezel flats.
        points=[(s*.46,-.625,1.16),(s*.46,-.69,1.16),
                (s*.46,-.715,1.19),(s*.46,-.715,1.66),
                (s*.46,-.69,1.69),(s*.46,-.625,1.69)]
        with bone(DOOR):emit(k,pipe_mesh(points,.011),JNT,'door pull handle')


def split_glass(body, rig):
    glazing=body.copy();glazing.data=body.data.copy();glazing.name='SK_'+TITLE+'Glass'
    bpy.context.scene.collection.objects.link(glazing)
    index=kit.SLOTS.index(GLASS)
    for obj, keep in ((glazing,True),(body,False)):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if (f.material_index==index)!=keep],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free()
    glazing.data.materials.clear();glazing.data.materials.append(bpy.data.materials[GLASS])
    for p in glazing.data.polygons:p.material_index=0
    return glazing


def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.MATERIALS[BRZ]=((.72,.46,.2),1,.32,0)
    kit.MATERIALS[GLASS]=((.04,.52,.57),0,.16,0)
    kit.MATERIALS[EMI]=((.04,.72,.78),0,.35,2)
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS];bsdf=glass.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Alpha'].default_value=.18;bsdf.inputs['IOR'].default_value=1.46
    glass.diffuse_color=(*glass.diffuse_color[:3],.18)
    glass.surface_render_method='BLENDED';glass.use_backface_culling=True
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None),
                     (DOOR,ROOT,'hinge',tuple(HINGE),(0,0,1),(0,-1,0),(0,OPEN_ANGLE))]
    kit.GROUPS=()
    kit.ANIMATIONS={'open':(False,'BEZIER',{DOOR:[(0,0),(45,OPEN_ANGLE)]}),
                    'close':(False,'BEZIER',{DOOR:[(0,OPEN_ANGLE),(45,0)]})}
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    rig['preview_poses']=json.dumps({'half_open':{DOOR:{'rot':[60,0,0]}},'open':{DOOR:{'rot':[120,0,0]}}})
    rig['preview_pose_views']=json.dumps({'open':['front_left','front','rear_right']})
    k=kit.Kit()
    for fn in (base,enclosure,crown,service_sides):fn(k)
    # One micron numerical seating clearance avoids exact-Boolean slivers
    # on the large backplate; it is below the kit's contact tolerance.
    with k.frame(Matrix.Translation((0,.239999,0))):internals(k)
    seats={tag:[v for v in p.verts if abs(v.z-SEAT_Z)<2e-6]
           for p,tag in zip(k.parts,common.LABELS)
           if tag in ('load bearing chamber sill','lofted pressure enclosure','retained door bezel')}
    shell_seat=seats['lofted pressure enclosure']+seats['retained door bezel']
    sill_seat=seats['load bearing chamber sill']
    for axis in (0,1):
        assert abs(min(v[axis] for v in sill_seat)-min(v[axis] for v in shell_seat))<2e-6
        assert abs(max(v[axis] for v in sill_seat)-max(v[axis] for v in shell_seat))<2e-6
    assert all(abs(abs(v.x)-SEAT_X)<2e-6 for v in shell_seat)
    print(f'[{NAME}] shell/pedestal butt seat matches: {SEAT_X*2:.3f} x {SEAT_Y1-SEAT_Y0:.3f} m',flush=True)
    pairs=common.exact_intersections(k)
    pending=set(range(1,len(k.parts)));connected={0}
    while pending:
        found={i for i in pending if any(k.parts[i].touches(k.parts[j]) for j in connected)}
        if not found:
            raise AssertionError(('disconnected parts',[common.LABELS[i] for i in sorted(pending)]))
        connected.update(found);pending-=found
    kit.check_connectivity(k,joints,[])
    actions=kit.build_actions(rig,joints,[])
    states=[(f'door {i}',{DOOR:i}) for i in range(121)]+kit.action_states(actions,joints)
    kit.check_motion(k,joints,states)
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    glazing=split_glass(body,rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],states,(-.0001,-.0001),(.0001,.0001))
    kit.check_coplanar(body)
    player_mount=bpy.data.objects.new('PlayerMount',None)
    bpy.context.collection.objects.link(player_mount)
    player_mount.parent=rig;player_mount.parent_type='BONE';player_mount.parent_bone=ROOT
    bpy.context.view_layer.update()
    player_mount.matrix_world=Matrix.Translation((0,.02,DECK))
    objects=[rig,body,glazing,player_mount]
    tris=sum(kit.triangles(o) for o in (body,glazing));assert tris<=5000 or '--draft' in sys.argv,tris
    assert set(actions)=={'open','close'}
    points=[v.co for o in (body,glazing) for v in o.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    assert abs(lo[2])<1e-6
    assert all(abs(a-b)<1e-6 for a,b in zip((hi[1]-lo[1],hi[0]-lo[0]),(1.5,1.25))),('ground footprint',lo,hi)
    if '--draft' not in sys.argv:
        common.prepare_export(objects,HERE,NAME);kit.select_only(objects)
        bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
            object_types={'MESH','ARMATURE','EMPTY'},global_scale=1,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
            use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
            primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
            bake_anim=True,bake_anim_use_all_actions=True,bake_anim_use_all_bones=False,path_mode='COPY',embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
            use_selection=True,export_yup=True,export_apply=False,export_skins=True,
            export_def_bones=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,export_materials='EXPORT')
    report={'name':NAME,'static':False,'animations':{n:{'frames':[0,45],'fps':30,'loop':False} for n in actions},'triangles':tris,'triangle_budget':5000,
            'meshes':{o.name:kit.triangles(o) for o in (body,glazing)},
            'bounds_m':{'lo':lo,'hi':hi},'ground_lw_m':[1.5,1.25],'category':'gameplay','tensor_height_m':1.753,
            'occupant':{'deck_m':DECK,'ceiling_m':CEILING,'headroom_m':CEILING-DECK-1.753},
            'placement':'floor centre z=0; viewing panel front -Y, up +Z',
            'materials':sorted({o.data.materials[p.material_index].name for o in (body,glazing) for p in o.data.polygons}),
            'bones':[{'name':ROOT,'kind':'fixed','parent':None},{'name':DOOR,'kind':'hinge','parent':ROOT}],
            'joints':[{'bone':ROOT,'type':'fixed','parent':None,'pivot':[0,0,0],'range':None},
                      {'bone':DOOR,'type':'hinge','parent':ROOT,'pivot':list(HINGE),'axis':[0,0,1],'range':[0,OPEN_ANGLE]}],
            'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,
                      'no_solid_intersections':True,'coplanar':True,'shell_pedestal_seat':True,
                      'budget':tris<=5000,'door_motion':True}}
    from door_clearance import swept_bounds
    report['door_swept_bounds_m']=swept_bounds((body,glazing),HINGE,DOOR)
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    kit.constrain(rig,joints,[])
    bpy.context.scene.render.fps=30
    bpy.context.scene['preview_actions']=json.dumps(['open','close'])
    bpy.context.scene['preview_frame']=json.dumps({'lo':[-.625,-1.72,0],'hi':[1.25,.75,2.679]})
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} tris; {len(k.parts)} connected parts; bounds {lo} .. {hi}',flush=True)


if __name__=='__main__':main()
