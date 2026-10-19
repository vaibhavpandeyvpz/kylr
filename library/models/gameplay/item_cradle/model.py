"""Library-only floor cradle. Metres, front -Y; build with headless Blender 5.2.

Four integral hooked shells on retained geared hinge shafts. No turntable.
The circular plinth stands on the floor rather than requiring a cut-out.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
    'M_Wire': 'Diffuse',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cradle_framework', HERE.parent/'item_table/model.py')
f = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = f
spec.loader.exec_module(f)
f.NAME, f.TITLE, f.HERE = 'item_cradle', 'ItemCradle', HERE
f.TRI_BUDGET=5500  # Explicit user-approved exception for this functional prop.
f.BLEND_PATH, f.RIG_JSON_PATH = HERE/'item_cradle.blend', HERE/'item_cradle_rig.json'
f.MATERIALS['M_Emissive'] = ((0.12, 0.75, 0.85), 0., .4, 3.)
f.MATERIALS['M_Wire'] = ((.025,.03,.035),0.,.75,0.)
f.SLOTS.append('M_Wire')
TAGS = ('FrontLeft','RearLeft','RearRight','FrontRight')
ANGLES = (-45,45,135,225)
R, PZ, OPEN = .57, .27, 25.
# Uniform physical scale: the cardinal casting ribs reach exactly +/-0.5 m.
# The complete 25-degree opening sweep stays within the 1 x 1 m square tile.
FOOTPRINT=1.0
SCALE=(FOOTPRINT/2)/.81
HOOK_RISE=.033                        # exact .5 m delivered hook crown
NAMES = tuple('Clamp'+tag for tag in TAGS)
f.JOINT_SPECS = [('Root',None,'fixed',(0,0,0),f.UP,f.UP,None)]
for name,az in zip(NAMES,ANGLES):
    a=math.radians(az)
    f.JOINT_SPECS.append((name,'Root','hinge',f.polar(R,az,PZ),
                          (-math.sin(a),math.cos(a),0),f.UP,(0,OPEN)))
f.JOINT_SPECS.append(('ItemSocket','Root','fixed',(0,0,.40/SCALE),f.UP,f.UP,None))
f.JOINT_SPECS=[(name,parent,kind,tuple(SCALE*c for c in pivot),axis,d,limits)
               for name,parent,kind,pivot,axis,d,limits in f.JOINT_SPECS]
f.PISTON_SPECS=[]
f.GROUPS=(NAMES,)
f.ANIMATIONS={'open':(False,'BEZIER',{NAMES[0]:[(0,0),(36,OPEN)]}),
              'close':(False,'BEZIER',{NAMES[0]:[(0,OPEN),(42,0)]})}
f.PREVIEW_STATES={'open':{NAMES[0]:OPEN},'halfway':{NAMES[0]:OPEN/2}}
f.PREVIEW_VIEWS={'open':['front_left','top','front'],'halfway':['front_left']}
f.FK_TEST_STATE={NAMES[0]:17}
f.MOUNT_NAME, f.MOUNT = 'ItemMount', (0,0,.40)
f.GUN_UP=(0,0,1)
f.PREVIEW_FRAME={'lo':[-.525,-.525,0],'hi':[.525,.525,.525]}
f.SHOWCASE=['open','close','open','close']


def on_socket(obj,rig):
    bone=rig.data.bones['ItemSocket']
    obj.parent,obj.parent_type,obj.parent_bone=rig,'BONE','ItemSocket'
    obj.matrix_parent_inverse=(rig.matrix_world@bone.matrix_local@Matrix.Translation((0,bone.length,0))).inverted()
    forward,up=f.Vector((0,-1,0)),f.Vector((0,0,1))
    basis=Matrix((forward.cross(up),forward,up)).transposed().to_4x4()
    basis.translation=f.Vector(f.MOUNT)
    obj.matrix_basis=basis
    return obj


f.on_socket=on_socket

# The generic boolean helper's newly-created bevel faces default to slot zero.
# Preserve the shell's paint on those faces rather than drawing a white border.
framework_carve=f.carve
def carve(k,bm,bone,mat,**kwargs):
    old=set(k.bm.faces)
    framework_carve(k,bm,bone,mat,**kwargs)
    if mat!=f.PRI:
        for face in set(k.bm.faces)-old:
            if face.material_index==f.SLOTS.index(f.PRI):
                face.material_index=f.SLOTS.index(mat)
f.carve=carve


def deck(k):
    # Lofted structural housing. Service wells are actual cavities, not overlays.
    rings=[f.ring_xy(0,0,r,z,32) for r,z in ((.70,0),(.75,.035),(.75,.12),(.70,.195),(.68,.20))]
    bays=[]
    lights=[]
    side_cuts=[]
    ribs=[]
    seams=[]
    for az in (0,90,180,270):
        m=f.turned(az)
        bays.append(([m@v for v in map(f.Vector,f.rect(.13,.064,.196,ca=.40,chamfer=.015))],f.UP,.048))
    for az in range(0,360,45):
        m=f.turned(az)
        ribs.append(f.loft_rings([[m@f.Vector(p) for p in f.rect(hx,hy,z,ca=c,chamfer=.008)]
                      for hx,hy,z,c in ((.065,.063,0,.745),(.054,.057,.08,.735),(.040,.05,.195,.725))]))
        m=f.turned(az+22.5)
        for z in (.063,.097):
            side_cuts.append(([m@f.Vector(p) for p in ((.749,-.065,z-.008),(.749,.065,z-.008),
                               (.749,.065,z+.008),(.749,-.065,z+.008))],
                              m.to_3x3()@f.Vector((1,0,0)),.027))
        seams.append(([m@f.Vector(p) for p in ((.24,-.0015,.201),(.60,-.0015,.201),
                       (.60,.0015,.201),(.24,.0015,.201))],f.UP,.008))
    for az in range(0,360,45):
        a0,a1=az+10,az+35
        poly=[(r*math.cos(math.radians(a)),r*math.sin(math.radians(a)),.201)
              for r,seq in ((.634,range(a0,a1+1,5)),(.652,range(a1,a0-1,-5))) for a in seq]
        lights.append(poly)
    f.carve(k,f.loft_rings(rings),'Root',f.SEC,
            union=ribs,subtract=bays+side_cuts+seams+[(p,f.UP,.008) for p in lights])
    for poly in lights: k.prism([(x,y,.198) for x,y,z in poly],.002,f.UP,'Root',f.EMI,convex=False)
    # Raised central payload seat, with a gasket-backed inset and front chevron.
    f.carve(k,f.loft_rings([f.ring_xy(0,0,r,z,8) for r,z in ((.205,.20),(.225,.213),(.215,.23))]),
            'Root',f.SEC,subtract=[(f.ring_xy(0,0,.183,.231,8),f.UP,.008)])
    k.prism(f.ring_xy(0,0,.182,.229,8),.004,f.UP,'Root',f.FRM)
    for az in range(0,360,45):
        x,y,z=f.polar(.199,az,.230)
        k.cyl((x,y,.229),(x,y,.232),.005,'Root',f.JNT,segs=6)
    # Deck retention bolts sit wholly on the ribs' horizontal top flats.
    for az in range(0,360,45):
        with k.frame(f.turned(az)):
            k.cyl((.735,0,.194),(.735,0,.198),.012,'Root',f.JNT,segs=6)
    for az in (0,90,180,270):
        with k.frame(f.turned(az)):
            # Electronics wells: attached base, connectors, protected conduit and return gland.
            k.box((.40,0,.176),(.22,.104,.012),'Root',f.FRM)
            for x in (.32,.48):
                k.box((x,0,.184),(.034,.076,.012),'Root',f.JNT)
            k.tube([(.32,0,.190),(.32,0,.215),(.36,.027,.215),(.44,.027,.215),(.48,0,.215),(.48,0,.190)],
                   .005,'Root','M_Wire',sides=6)


def clamp(k,name,az):
    with k.frame(f.turned(az)):
        # Pedestal clevis with coaxial bored cheeks: 2 mm axial running gaps.
        k.box((R,0,.2095),(.16,.17,.019),'Root',f.FRM,bevel=.006)
        for s in (-1,1):
            y=s*.069
            f.carve(k,f.prism_bm([(R-.065,y,.215),(R+.065,y,.215),(R+.055,y,.292),
                                 (R+.032,y,.327),(R-.032,y,.327),(R-.055,y,.292)],.024,f.BACK),
                    'Root',f.SEC,cuts=[((R,y-.02,PZ),(R,y+.02,PZ),.019,12)])
            # Motor gearbox coaxial with shaft, captive caps at either end.
            k.cyl((R,s*.081,PZ),(R,s*.105,PZ),.045,'Root',f.FRM,segs=12)
            k.cyl((R,s*.105,PZ),(R,s*.109,PZ),.027,'Root',f.JNT,segs=12)
            # Four cover fasteners seated outside the central retained shaft.
            for a in (45,135,225,315):
                x=R+.035*math.cos(math.radians(a)); z=PZ+.035*math.sin(math.radians(a))
                k.cyl((x,s*.104,z),(x,s*.108,z),.0035,'Root',f.JNT,segs=6)
        # One tapered elbow-to-hook shell with boolean side pockets.
        profile=f.arc_xz(R,PZ,.046,180,360,8)+[(.665,.50),(.624,.714),(.586,.777),
                (.469,.777),(.449,.757),(.449,.72),(.475,.704),(.503,.718),
                (.559,.718),(.574,.683),(.594,.50),(R-.046,PZ)]
        profile=[(x,z+(HOOK_RISE if z>=.683 else 0)) for x,z in profile]
        pockets=[]
        for s in (-1,1):
            for z in (.525,.565,.605):
                # Centre each identical slot between the actual tapered edges.
                outer=.665+(.624-.665)*(z-.50)/(.714+HOOK_RISE-.50)
                inner=.594+(.574-.594)*(z-.50)/(.683+HOOK_RISE-.50)
                c=(outer+inner)/2
                pockets.append(([(x,s*.056,h) for x,h in ((c-.019+ .001,z-.007),(c+.019+.001,z-.007),
                                  (c+.019-.001,z+.007),(c-.019-.001,z+.007))],f.BACK,.010))
        f.carve(k,f.prism_bm([(x,0,z) for x,z in profile],.112,f.BACK),name,f.PRI,
                subtract=pockets,boxes=[((.527,0,.778+HOOK_RISE),(.05,.069,.012))],
                bevel=.003,flanks=[(f.BACK,.056),(f.BACK,-.056)])
        k.cyl((R,-.103,PZ),(R,.103,PZ),.017,name,f.JNT,segs=12)
        # Flush hook liner and recessed status lens, both anchored to the shell.
        k.box((.53,0,.7165+HOOK_RISE),(.039,.071,.003),name,f.FRM)
        for y in (-.022,.022):
            k.cyl((.53,y,.716+HOOK_RISE),(.53,y,.713+HOOK_RISE),.004,name,f.JNT,segs=6)
        k.box((.527,0,.774+HOOK_RISE),(.046,.065,.004),name,f.EMI)


# Keep projection axes stable for opposite 45-degree faces (float ties).
def check_coplanar(obj):
    """No z-fighting at rest: fail if two faces of different pieces of the final mesh lie in the
    same plane, face the same way and overlap (they would flicker against each other)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    piece, n_pieces = {}, 0
    for f in bm.faces:  # connected pieces
        if f in piece:
            continue
        stack, piece[f] = [f], n_pieces
        while stack:
            for e in stack.pop().edges:
                for g in e.link_faces:
                    if g not in piece:
                        piece[g] = n_pieces
                        stack.append(g)
        n_pieces += 1
    planes = {}
    for f in bm.faces:
        if f.calc_area() > 1e-7:
            n = f.normal
            planes.setdefault((round(n.x, 3), round(n.y, 3), round(n.z, 3), round(n.dot(f.verts[0].co), 4)), []).append(f)

    def flat(f):
        ax = max(range(3), key=lambda i: round(abs(f.normal[i]), 3))
        u, v = [i for i in range(3) if i != ax]
        return [(p.co[u], p.co[v]) for p in f.verts]

    def inside(pt, poly):
        x, y, c = pt[0], pt[1], False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
        return c

    def samples(poly):  # the centre and points pulled in from each corner, where inside the face
        cx, cy = sum(x for x, _ in poly) / len(poly), sum(y for _, y in poly) / len(poly)
        return [q for q in [(cx, cy)] + [(x + (cx - x) * 0.2, y + (cy - y) * 0.2) for x, y in poly] if inside(q, poly)]
    problems = []
    for faces in planes.values():
        for i, a in enumerate(faces):
            for b in faces[i + 1:]:
                if piece[a] != piece[b]:
                    pa, pb = flat(a), flat(b)
                    if any(inside(t, pb) for t in samples(pa)) or any(inside(t, pa) for t in samples(pb)):
                        c = a.calc_center_median()
                        problems.append(f"coplanar faces at {tuple(round(x, 3) for x in c)} ({obj.material_slots[a.material_index].name}"
                                        f" / {obj.material_slots[b.material_index].name})")
    bm.free()
    if problems:
        raise SystemExit(f"[{NAME}] z-fighting:\n  " + "\n  ".join(dict.fromkeys(problems)))



def main():
    f.reset_scene(); f.build_materials()
    joints=f.resolve_joints(); rig=f.build_rig(joints,[])
    f.check_rig_fk(rig,joints); actions=f.build_actions(rig,joints,[])
    k=f.Kit()
    with k.frame(Matrix.Scale(SCALE,4)):
        deck(k)
        for name,az in zip(NAMES,ANGLES): clamp(k,name,az)
    f.check_connectivity(k,joints,[]); f.check_joint_alignment(k,joints)
    states=f.action_states(actions,joints)
    states += [(f'full sweep {i}',{NAMES[0]:i}) for i in range(int(OPEN)+1)]
    for name in NAMES:
        states += [(f'{name} independent {i}',{name:i}) for i in range(int(OPEN)+1)]
    f.check_motion(k,joints,states)
    for tag,state in states:
        transforms=f.fk(joints,f.expand(state))
        for part in k.parts:
            for vertex in part.verts:
                point=transforms[part.bone]@vertex
                assert abs(point.x)<=FOOTPRINT/2+1e-5 and abs(point.y)<=FOOTPRINT/2+1e-5,(tag,'outside 1 m tile',point)
    for axis in (0,1):
        coordinates=[v[axis] for part in k.parts for v in part.verts]
        assert abs(min(coordinates)+FOOTPRINT/2)<1e-5
        assert abs(max(coordinates)-FOOTPRINT/2)<1e-5
    print(f'[item_cradle] connectivity, hinge alignment, {len(states)} motion states PASS')
    body=k.to_object('SK_ItemCradle',joints=f.rotary_joints(joints))
    # Reconnect boolean fragments along identical construction edges after the
    # hidden-face pass, within each rigid body only.
    bm=bmesh.new(); bm.from_mesh(body.data)
    weights=bm.verts.layers.deform.active
    for group in body.vertex_groups:
        verts=[v for v in bm.verts if group.index in v[weights]]
        bmesh.ops.remove_doubles(bm,verts=verts,dist=1e-6)
    bm.normal_update(); bm.to_mesh(body.data); bm.free(); body.data.update()
    check_coplanar(body); f.skin(body,rig)
    # Freestanding on an unbroken floor; there is no pit/cut-out below it.
    f.cull_unseen(body,rig,joints,[],states,(-1e-4,-1e-4),(1e-4,1e-4))
    sys.path.insert(0,str(HERE.parents[1]))
    from gameplay.dimensions import assert_authored_bounds
    assert_authored_bounds(HERE.name,[body])
    f.unwrap(body); tris=f.triangles(body)
    assert tris<=f.TRI_BUDGET, tris
    mount=f.build_weapon_mount(rig)
    f.export([rig,body,mount],f.NAME); f.constrain(rig,joints,[])
    data={'name':f.NAME,'triangles':tris,'triangle_budget':f.TRI_BUDGET,
          'budget_exception':'User-approved item_cradle ceiling of 5500 triangles; other props retain their default budget.',
          'materials':f.SLOTS,'front':'-Y','units':'m',
          'size_m':[FOOTPRINT,FOOTPRINT,(.777+HOOK_RISE)*SCALE],'outer_footprint_m':[FOOTPRINT,FOOTPRINT],'deck_diameter_m':1.5*SCALE,'tensor_height_m':1.753,'placement':'freestanding; origin on floor; no cutout; entire motion inside 1 x 1 m tile',
          'item_socket':{'mount':'ItemMount','bone':'ItemSocket','bottom_m':list(f.MOUNT)},
          'mechanics':f'Four {34*SCALE:.1f} mm retained shafts in bored pedestal clevises, coaxial geared electric drives; rigid hook shells.',
          'joints':[{'bone':j.name,'parent':j.parent,'type':j.kind,'pivot':list(j.pivot),'axis':list(j.axis),
                     'range':j.limits} for j in joints.values()],
          'animations':{name:{'fps':30,'loop':False,'frames':[0,int(a.frame_range[1])]} for name,a in actions.items()},
          'usage':'close holds; open releases. No platform rotation. ItemMount is fixed on the deck.',
          'validation':{'motion_states':len(states),'connectivity':'PASS','hinge_alignment':'PASS','motion_clearance':'PASS','1m_tile_envelope':'PASS'}}
    f.RIG_JSON_PATH.write_text(json.dumps(data,indent=2))
    rig['preview_poses']=json.dumps({tag:{name:{'rot':[v,0,0]} for name,v in f.expand(state).items()}
                                   for tag,state in f.PREVIEW_STATES.items()})
    rig['preview_pose_views']=json.dumps(f.PREVIEW_VIEWS)
    scene=bpy.context.scene
    scene['preview_actions']=json.dumps(f.SHOWCASE); scene['preview_frame']=json.dumps(f.PREVIEW_FRAME)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(f.BLEND_PATH),compress=True)
    print(f'[item_cradle] {tris} triangles; saved native, GLB, FBX and rig metadata')


if __name__=='__main__': main()
