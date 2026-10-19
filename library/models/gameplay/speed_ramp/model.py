"""Powered twin-belt launch cartridge. Metres, +Z up, launch toward -Y.

The reinforced elastomer carriers flex between rigid tread stations. Each vertex
has one unit-weight influence; no steel component stretches. Station transforms
and the drums are baked from one travelled-distance coordinate, not independent
hand-keyed rotations. Source only: never edit the generated deliveries.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("speed_ramp_framework", HERE.parent / "jump_pad/model.py")
f = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = f
spec.loader.exec_module(f)
f.NAME, f.TITLE, f.HERE = "speed_ramp", "SpeedRamp", HERE
f.BLEND_PATH, f.RIG_JSON_PATH = HERE / "speed_ramp.blend", HERE / "speed_ramp_rig.json"
WIDTH, LENGTH, DEPTH = 3.0, 2.0, 0.31
DELIVERY_SCALE=.5                     # bake uniform scale into geometry, bones and clip translations
TARGET_LWH=(1.0,1.5,.75)
BUILD_SCALE=DELIVERY_SCALE             # public posing helpers operate on delivered native scenes
GROUND_OFFSET=DEPTH*DELIVERY_SCALE
BUILD_OFFSET=GROUND_OFFSET
FPS = 480  # Dense baked transforms keep the fast end-wrap interpolation accurate.
RADIUS, CARRIER, RIB = 0.13, 0.012, 0.021
SHROUD_RADIUS=.198
SERVICE_PANEL_Z=(.04,.32)
VENT_HALF_HEIGHT=.019
VENT_CENTERS=tuple(SERVICE_PANEL_Z[0]+VENT_HALF_HEIGHT+
                   (SERVICE_PANEL_Z[1]-SERVICE_PANEL_Z[0]-2*VENT_HALF_HEIGHT)*i/3
                   for i in range(4))
def envelope_height(angle):
    entry_z=-math.cos(angle)*(RADIUS+CARRIER/2+RIB)
    exit_z=entry_z+math.sin(angle)*(2*math.tau*RADIUS)
    crown=max(SHROUD_RADIUS*math.cos((math.pi/2+angle)*i/8-angle) for i in range(9))
    return DEPTH+exit_z+crown
lo,hi=math.radians(28),math.radians(60)
for _ in range(60):
    midpoint=(lo+hi)/2
    if envelope_height(midpoint)*DELIVERY_SCALE<TARGET_LWH[2]:lo=midpoint
    else:hi=midpoint
ANGLE=(lo+hi)/2                       # shorter footprint, steeper incline, circular drums retained
T = Vector((0, -math.cos(ANGLE), math.sin(ANGLE)))
N = Vector((0, math.sin(ANGLE), math.cos(ANGLE)))
X = Vector((1, 0, 0))
# Five drum revolutions per full belt circuit: both mechanisms close exactly.
RUN = 2*math.tau*RADIUS
ENTRY = Vector((0, .72, -N.z*(RADIUS+CARRIER/2+RIB)))
EXIT = ENTRY+T*RUN
PERIMETER = 2*RUN+math.tau*RADIUS
STATIONS = 24
PITCH = PERIMETER/STATIONS
LANES = (("Left", .57), ("Right", -.57))
BELT_HALF = .43
TOP = RADIUS+CARRIER/2+RIB
LAUNCH = EXIT+N*TOP
SHROUD_STATIONS=[(1.0,.015,1.32),(.78,((ENTRY+N*SHROUD_RADIUS).y-.78)*math.tan(ANGLE)+(ENTRY+N*SHROUD_RADIUS).z,1.41)]
for i in range(9):
    theta=(math.pi/2+ANGLE)*i/8
    p=EXIT+(N*math.cos(theta)+T*math.sin(theta))*SHROUD_RADIUS
    SHROUD_STATIONS.append((p.y,p.z,1.41))
SHROUD_STATIONS.append((-1.0,SHROUD_STATIONS[-1][1],1.41))
NOSE_Y=-.969                         # rear bulkhead inside the integral housing feet
f.JOINT_SPECS = [
    ("Root", None, "fixed", (0,0,0), f.UP, f.UP, None),
    ("Drive", "Root", "hinge", tuple(EXIT), tuple(X), tuple(T), None),
    ("Idler", "Root", "hinge", tuple(ENTRY), tuple(X), tuple(T), None),
]
for side,s in (("Left",1),("Right",-1)):
    f.JOINT_SPECS.append((side+"Service", "Root", "hinge", (s*1.31,-.20,.32),
                          (0,-s,0), (s,0,0), (0,35)))
f.PISTON_SPECS = []; f.GROUPS = (); f.FK_TEST_STATE = {"Drive":36,"LeftService":20}
f.PREVIEW_STATES = {"service":{"LeftService":35,"RightService":35}}
f.PREVIEW_VIEWS = {"service":["front_left","rear_right"]}
f.ANIMATIONS = {}


def loft(rings):
    bm=bmesh.new(); rows=[[bm.verts.new(p) for p in ring] for ring in rings]
    bm.faces.new(rows[0][::-1]); bm.faces.new(rows[-1])
    for a,b in zip(rows,rows[1:]):
        for i in range(len(a)):
            j=(i+1)%len(a); bm.faces.new((a[i],a[j],b[j],b[i]))
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:]); return bm


def point(x,u,h):
    return ENTRY+X*x+T*u+N*h


def track(s):
    """Closed tangent racetrack; increasing s travels forward on its upper run."""
    s %= PERIMETER
    if s<RUN: return ENTRY+T*s+N*RADIUS, T, N
    s-=RUN
    if s<math.pi*RADIUS:
        a=s/RADIUS; n=N*math.cos(a)+T*math.sin(a)
        return EXIT+n*RADIUS, T*math.cos(a)-N*math.sin(a), n
    s-=math.pi*RADIUS
    if s<RUN: return EXIT-T*s-N*RADIUS, -T, -N
    a=(s-RUN)/RADIUS; n=-N*math.cos(a)-T*math.sin(a)
    return ENTRY+n*RADIUS, -T*math.cos(a)+N*math.sin(a), n


def station_matrix(s,x):
    p,t,n=track(s)
    # local X across, local Y forward, local Z outward: right-handed.
    m=Matrix((X,t,-n)).transposed().to_4x4()
    m.translation=(p+X*x)*BUILD_SCALE+Vector((0,0,BUILD_OFFSET))
    return m


def bolt(k,p,axis,r=.009,bone="Root"):
    p,axis=Vector(p),Vector(axis)
    k.cyl(p,p+axis*.005,r,bone,f.JNT,segs=6)


def build_frame(k):
    # Steel slider beds take robot loads along the straight upper runs.
    for _,x in LANES:
        k.obox(point(x,0,RADIUS-CARRIER/2-.012),point(x,RUN,RADIUS-CARRIER/2-.012),
               .84,.022,tuple(N),"Root",f.JNT)
        s=1 if x>0 else -1
        for u in (.20,1.34):
            k.obox(point(s*1.02,u-.04,.106),point(s*1.02,u+.04,.106),.09,.020,N,"Root",f.JNT)
    # Structural transverse bulkheads join the two shells below the belt returns.
    for u in (.22,1.30):
        p=point(0,u,-TOP-.040);z=p.z
        k.box((0,p.y,(z-.31)/2),(2.18,.07,z+.31),"Root",f.FRM)
    for s in (-1,1):
        # Faceted loft, broad shoulders, narrowed entry. Integral housing feet seat directly on ground.
        rings=[]
        for y,top,w in SHROUD_STATIONS:
            # Tangent quarter-round shoulder, not a diagonal corner chamfer.
            r=.025
            section=[(1.026,-.31),(1.5,-.31),(w,-.28)]
            section += [(w-r+r*math.cos(i*math.pi/6),top-r+r*math.sin(i*math.pi/6)) for i in range(4)]
            section += [(1.12,top),(1.026,top-.075)]
            rings.append([(s*x,y,z) for x,z in section])
        cuts=[]
        # Vent bank shares the service pocket top/bottom edges; slots have equal gaps.
        def rectangle(y0,y1,z0,z1,x):
            return [(s*x,y0,z0),(s*x,y1,z0),(s*x,y1,z1),(s*x,y0,z1)]
        for z in VENT_CENTERS:
            cuts.append((rectangle(-.81,-.49,z-VENT_HALF_HEIGHT,z+VENT_HALF_HEIGHT,1.39),(1,0,0),.07))
        cuts.append((rectangle(-.41,.08,*SERVICE_PANEL_Z,1.30),(1,0,0),.50))
        cuts.append((rectangle(-.52,.25,-.246,-.200,1.385),(1,0,0),.12))
        # Continuous rail machined in the sloping shoulder, with square-ended lens.
        rail=[point(s*x,u,TOP+.032) for x,u in ((1.105,.10),(1.185,.10),(1.185,1.46),(1.105,1.46))]
        cuts.append((rail,N,.08))
        # Bearing bores: no rotor buried in an uncut shell.
        holes=[(tuple(c+X*s*.99),tuple(c+X*s*1.50),.048,12) for c in (ENTRY,EXIT)]
        holes.append((tuple(EXIT+X*s*1.284),tuple(EXIT+X*s*1.50),.100,12))
        f.carve(k,loft(rings),"Root",f.PRI,cuts=holes,subtract=cuts,
                bevel=.007,flanks=[((s,0,0),1.41)])
        # Lens is seated into the rail slot; root frame behind it is its support.
        k.prism([p-N*.031 for p in rail],.018,N,"Root",f.EMI)
        # Power controller: a lofted sealed enclosure behind the hinged cover.
        rings2=[]
        for x,hy,hz in ((1.08,.18,.105),(1.20,.205,.12),(1.30,.18,.105)):
            rings2.append([(s*x,-.16+y,.17+z) for y,z in
                           ((-hy,-hz),(hy,-hz),(hy,hz*.70),(hy*.80,hz),(-hy*.80,hz),(-hy,hz*.70))])
        f.carve(k,loft(rings2),"Root",f.SEC)
        k.box((s*1.065,-.16,.17),(.030,.30,.18),"Root",f.FRM)
        # Cover sits in its cut pocket, with its top edge carried by a retained hinge pin.
        bone=("Left" if s>0 else "Right")+"Service"
        poly=rectangle(-.405,.075,SERVICE_PANEL_Z[0]+.004,SERVICE_PANEL_Z[1]-.008,1.31)
        k.prism(poly,.016,X,bone,f.SEC)
        for y0,y1,b in ((-.44,-.415,"Root"),(-.399,.069,bone),(.085,.11,"Root")):
            k.cyl((s*1.31,y0,.32),(s*1.31,y1,.32),.018,b,f.FRM,segs=8)
        k.cyl((s*1.31,-.447,.32),(s*1.31,.117,.32),.007,"Root",f.JNT,segs=8)
        for y in (-.4275,.0975):
            k.box((s*1.27,y,.322),(.08,.025,.032),"Root",f.FRM)
        for y in (-.35,.02): bolt(k,(s*1.318,y,.074),(s,0,0),bone=bone)
        # Protected loom: square entries in terminal blocks, rounded mitred bends,
        # a gland at both ends and two bolted clips on the same fixed shell.
        k.box((s*1.28,.20,-.220),(.11,.09,.024),"Root",f.SEC)
        k.box((s*1.28,-.49,-.220),(.11,.07,.024),"Root",f.SEC)
        path=[(s*1.335,.20,-.220),(s*1.37,.20,-.220),(s*1.37,.16,-.220),
              (s*1.37,-.45,-.220),(s*1.37,-.49,-.220),(s*1.335,-.49,-.220)]
        k.tube(path,.008,"Root",f.FRM,sides=4)
        for y in (-.31,-.05):
            k.box((s*1.355,y,-.220),(.06,.025,.022),"Root",f.SEC,solid=False)
            bolt(k,(s*1.385,y,-.220),(s,0,0),.007)
    # Centre spine is a continuous formed steel bridge, seated on both crossheads.
    # Formed centre spine rolls over the launch drum as one closed nose guard.
    outside=[point(0,-.02,TOP-.0005),point(0,RUN,TOP-.0005)]
    inside=[point(0,-.02,TOP-.0355),point(0,RUN,TOP-.0355)]
    for i in range(1,7):
        n=N*math.cos(i*math.pi/6)+T*math.sin(i*math.pi/6)
        outside.append(EXIT+n*(TOP-.0005));inside.append(EXIT+n*(TOP-.0355))
    arrows=[]
    for u in (.36,.79,1.22):
        poly=[point(x,v,TOP-.0045) for x,v in ((-.065,u-.04),(0,u+.015),(.065,u-.04),
                                            (.065,u-.014),(0,u+.041),(-.065,u-.014))]
        arrows.append(poly)
    f.carve(k,f.prism_bm(outside+inside[::-1],.20,X),"Root",f.JNT,
            subtract=[(p,N,.020) for p in arrows])
    for poly in arrows:k.prism([p-N*.003 for p in poly],.014,N,"Root",f.SEC,convex=False)
    for u in (.26,1.27):
        p=point(0,u,TOP-.0355)
        rings=[[(x,p.y+y,-.31) for x,y in ((-.09,-.0325),(.09,-.0325),(.09,.0325),(-.09,.0325))],
               [(x,p.y+y,p.z-y*math.tan(ANGLE)) for x,y in ((-.09,-.0325),(.09,-.0325),(.09,.0325),(-.09,.0325))]]
        # Narrow integral crosshead links the spine support to both housing feet.
        crosshead=f.prism_bm([(x,p.y+y,-.30) for x,y in
                             ((-1.09,-.0325),(1.09,-.0325),(1.09,.0325),(-1.09,.0325))],.010,f.UP)
        f.carve(k,f.machine(loft(rings),union=[crosshead]),"Root",f.FRM)
    # Inset, non-emissive directional geometry on the spine; cut before inlay.
    # Separate nose crossmember joins both shells and supports the launch lip.
    y=NOSE_Y
    outline=[(-1.28,y,-.31),(1.28,y,-.31),(1.28,y,.41),(1.20,y,.45),(-1.20,y,.45),(-1.28,y,.41)]
    vents=[([(x-.10,y,.28),(x+.10,y,.28),(x+.10,y,.37),(x-.10,y,.37)],(0,1,0),.12)
           for x in (-.72,-.36,0,.36,.72)]
    f.carve(k,f.prism_bm(outline,.052,(0,1,0)),"Root",f.SEC,subtract=vents)


def build_drives(k):
    for c,bone in ((ENTRY,"Idler"),(EXIT,"Drive")):
        # One keyed through-shaft couples the two lanes. Retained axle terminates
        # inside bored bearing cartridges; separate annular stationary housings.
        shaft=1.360 if bone=="Drive" else 1.286
        k.cyl(c-X*shaft,c+X*shaft,.032,bone,f.JNT,segs=12)
        for s in (-1,1):
            # Flanged drum ends occupy the gap alongside, not the rubber's volume.
            for x0,x1 in ((.103,.138),(1.002,1.023)):
                k.cyl(c+X*s*x0,c+X*s*x1,.123,bone,f.SEC,segs=16)
            housings=[]
            for x0,x1 in ((1.027,1.12),(1.18,1.285)):
                outline=[tuple(c+X*s*((x0+x1)/2)+T*(.083*math.cos(i*math.tau/12))+N*(.083*math.sin(i*math.tau/12))) for i in range(12)]
                housings.append(f.prism_bm(outline,x1-x0,X))
                k.cyl(c+X*s*x0,c+X*s*x1,.0355,bone,f.JNT,segs=12)
            # Cast bearing pedestal is unioned before boring the whole assembly.
            foot=[(s*1.16,c.y+y,z) for y,z in ((-.07,-.31),(.07,-.31),(.07,c.z),(-.07,c.z))]
            housing=f.machine(housings[0],union=[housings[1],f.prism_bm(foot,.14,X)])
            f.carve(k,housing,"Root",f.FRM,
                    cuts=[(tuple(c+X*s*.99),tuple(c+X*s*1.31),.037,12)])
            # Stainless retaining ring has an axial running clearance from the cap.
            if bone=="Idler":
                k.cyl(c+X*s*1.286,c+X*s*1.30,.050,bone,f.JNT,segs=12)
                for a in (math.pi/4,5*math.pi/4):
                    bolt(k,c+X*s*1.285+T*(.065*math.cos(a))+N*(.065*math.sin(a)),X*s,.008)
            if bone=="Drive":
                # Recessed coaxial torque-motor cap; its bolts seat in real bores.
                mid=c+X*s*1.325
                ring=[mid+T*(.095*math.cos(i*math.tau/12))+N*(.095*math.sin(i*math.tau/12)) for i in range(12)]
                cuts=[(tuple(c+X*s*1.275),tuple(c+X*s*1.38),.037,12)]
                bolts=[]
                for a in (math.pi/4,3*math.pi/4,5*math.pi/4,7*math.pi/4):
                    p=c+X*s*1.360+T*(.073*math.cos(a))+N*(.073*math.sin(a))
                    cuts.append((tuple(p),tuple(p+X*s*.020),.010,6));bolts.append(p)
                f.carve(k,f.prism_bm(ring,.080,X),"Root",f.SEC,cuts=cuts)
                k.cyl(c+X*s*1.286,c+X*s*1.365,.0355,bone,f.JNT,segs=12)
                for p in bolts:bolt(k,p,X*s,.008)


def add_stations(rig):
    f.select_only([rig]); bpy.ops.object.mode_set(mode="EDIT")
    for side,x in LANES:
        for i in range(STATIONS):
            e=rig.data.edit_bones.new(f"{side}Tread{i:02}")
            m=station_matrix(i*PITCH,x)
            e.head=m.translation; e.tail=e.head+m.to_3x3()@Vector((0,.045,0))
            e.align_roll(m.to_3x3()@Vector((0,0,1)))
            e.parent=rig.data.edit_bones["Root"]
    bpy.ops.object.mode_set(mode="OBJECT")


def check_bearings(kit,joints):
    # The generic check samples the *empty bore* of an annular bearing. Check
    # the actual annulus instead, while retaining the generic hinge-cover test.
    f.check_joint_alignment(kit,{n:j for n,j in joints.items() if n not in ("Drive","Idler")})
    for bone,c in (("Drive",EXIT),("Idler",ENTRY)):
        assert joints[bone].axis.dot(X)>.99999
        assert any(b==bone and abs(ax.dot(X))>.99999 and
                   ((mid-c)-X*(mid-c).dot(X)).length<1e-6 for b,mid,ax,half in kit.axes)
        for s in (-1,1):
            for direction in (T,-T,N,-N):
                q=c+X*s*1.075+direction*.060
                assert any(p.bone=="Root" and p.buried(q) for p in kit.parts),"Bearing wall missing"
    print("[speed_ramp] bored bearing housings, coaxial journals and cover hinges PASS")


def build_belts(rig):
    # Closed carriers have one weighted cross-section per station. Rib underside
    # faces are omitted: that interface is vulcanised to the carrier, not visible.
    bm=bmesh.new(); deform=bm.verts.layers.deform.new()
    names=[]
    for side,x in LANES:
        stations=[]
        for i in range(STATIONS):
            name=f"{side}Tread{i:02}"; names.append(name); gi=len(names)-1
            p,t,n=track(i*PITCH); p+=X*x
            rows=[];rib=[]
            for u in (-PITCH*.32,PITCH*.32):
                row=[]
                for w,h in ((-.43,-.006),(.43,-.006),(.43,.006),(-.43,.006)):
                    v=bm.verts.new(p+X*w+t*u+n*h);v[deform][gi]=1.;row.append(v)
                rows.append(row)
                rib.append([row[3],row[2]]+[bm.verts.new(p+X*w+t*u+n*h) for w,h in
                            ((.405,.027),(-.405,.027))])
            for row2 in rib:
                for v in row2:v[deform][gi]=1.
            bm.faces.new(rib[0][::-1]);bm.faces.new(rib[1])
            for j in range(1,4):bm.faces.new((rib[0][j],rib[0][(j+1)%4],rib[1][(j+1)%4],rib[1][j]))
            # Carrier and rib share vertices: no buried duplicate contact faces.
            for j in (0,1,3):
                bm.faces.new((rows[0][j],rows[0][(j+1)%4],rows[1][(j+1)%4],rows[1][j]))
            stations.append(rows)
        for old,new in zip(stations,stations[1:]+stations[:1]):
            a,b=old[1],new[0]
            for j in range(4):bm.faces.new((a[j],a[(j+1)%4],b[(j+1)%4],b[j]))
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    mesh=bpy.data.meshes.new("SpeedRampBelts");bm.to_mesh(mesh);bm.free()
    o=bpy.data.objects.new("SK_SpeedRampBelts",mesh);bpy.context.scene.collection.objects.link(o)
    for name in names:o.vertex_groups.new(name=name)
    for slot in f.SLOTS:mesh.materials.append(bpy.data.materials[slot])
    for p in mesh.polygons:p.material_index=f.SLOTS.index(f.FRM)
    mesh.set_sharp_from_angle(angle=f.SHARP_ANGLE);f.skin(o,rig)
    return o


def pose_distance(rig,distance,cover=0):
    for name in ("Drive","Idler"):
        pb=rig.pose.bones[name];pb.rotation_mode="XYZ";pb.rotation_euler=(distance/RADIUS,0,0)
    for side,x in LANES:
        for i in range(STATIONS):
            pb=rig.pose.bones[f"{side}Tread{i:02}"]
            pb.rotation_mode="QUATERNION"
            pb.matrix_basis=rig.data.bones[pb.name].matrix_local.inverted()@station_matrix(i*PITCH+distance,x)
    for name in ("LeftService","RightService"):
        rig.pose.bones[name].rotation_euler[0]=math.radians(cover)
    bpy.context.view_layer.update()


def build_actions(rig):
    # Exact phase closure: an integer number of belt circuits AND drum turns.
    # Racetrack circumference generally is not an integer drum circumference;
    # loop pads by a full circuit and wrap rotor by its rotational symmetry.
    clips={"convey":(96*FPS//30,True,lambda t:PERIMETER*t,lambda t:0),
           "launch":(58*FPS//30,False,lambda t:3*PERIMETER*(t-math.sin(math.tau*t)/math.tau),lambda t:0),
           "service_open":(30*FPS//30,False,lambda t:0,lambda t:35*(3*t*t-2*t*t*t)),
           "service_close":(30*FPS//30,False,lambda t:0,lambda t:35*(1-3*t*t+2*t*t*t))}
    result={};rig.animation_data_create()
    for name,(frames,loop,travel,opening) in clips.items():
        action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data.action=action
        previous={}
        for frame in range(frames+1):
            pose_distance(rig,travel(frame/frames),opening(frame/frames))
            for pb in rig.pose.bones:
                if pb.name=="Root":continue
                if "Tread" in pb.name:
                    q=pb.rotation_quaternion.copy()
                    if pb.name in previous and q.dot(previous[pb.name])<0:q.negate()
                    pb.rotation_quaternion=q;previous[pb.name]=q.copy()
                pb.keyframe_insert("location",frame=frame)
                pb.keyframe_insert("rotation_quaternion" if "Tread" in pb.name else "rotation_euler",frame=frame)
        for fc in f.action_fcurves(action):
            for kp in fc.keyframe_points:kp.interpolation="LINEAR"
        action.use_cyclic=loop;result[name]=action;rig.animation_data.action=None
        track_=rig.animation_data.nla_tracks.new();track_.name=name;track_.strips.new(name,0,action);track_.mute=True
    pose_distance(rig,0);return result


def validate_belts(rig,body):
    # Check geometry at fractional-frame phases too: pad separation, lane/shell
    # running gaps and the rectangle. Rotor webs lie outside the carriers in X.
    deps=bpy.context.evaluated_depsgraph_get()
    minimum_gap=1
    for j in range(97):
        d=PERIMETER*j/96;pose_distance(rig,d)
        for i in range(STATIONS):
            p,t,n=track(i*PITCH+d);q,qt,qn=track((i+1)*PITCH+d)
            gap=(q-p).length-PITCH*.64
            minimum_gap=min(minimum_gap,gap)
            assert gap>.022,"Adjacent tread ribs collide"
        mesh=body.evaluated_get(deps).to_mesh()
        for v in mesh.vertices:
            assert abs(v.co.x)<1.001 and abs(v.co.y)<.94 and v.co.z>-.34,("belt outside cartridge",v.co)
        body.evaluated_get(deps).to_mesh_clear()
    pose_distance(rig,0)
    print(f"[speed_ramp] 97 belt phases; minimum rib gap {minimum_gap:.4f} m")
    return minimum_gap


def preview_floor():
    mat=bpy.data.materials.new("PRV_Floor")
    bs=mat.node_tree.nodes["Principled BSDF"];bs.inputs["Base Color"].default_value=(.26,.27,.28,1)
    bs.inputs["Roughness"].default_value=.8
    bm=f.prism_bm(f.rect(1.62,1.12,-.025),.05,f.UP)
    mesh=bpy.data.meshes.new("PRV_Floor_Mesh");bm.to_mesh(mesh);bm.free();mesh.materials.append(mat)
    bpy.context.scene.collection.objects.link(bpy.data.objects.new("PRV_Floor",mesh))


def cull_frame(body,rig,joints,states):
    # Remove the ground-contact underside before the room-visibility ray pass.
    bm=bmesh.new();bm.from_mesh(body.data)
    # Only the bottom contacts ground. The housing feet seat directly on it.
    dead=[face for face in bm.faces if all(abs(v.co.z+DEPTH)<1e-6 for v in face.verts)]
    bmesh.ops.delete(bm,geom=dead,context="FACES_ONLY")
    bm.to_mesh(body.data);bm.free()
    # Thin occluders lie strictly inside the opaque straight carrier in *every*
    # belt phase. They allow the static pass to remove its unseen slider beds.
    k=f.Kit()
    for _,x in LANES:k.obox(point(x,.16,RADIUS),point(x,RUN-.16,RADIUS),.86,.002,N,"Root",f.FRM)
    occ=k.to_object("CHECK_BeltOccluders")
    flag=occ.data.attributes.new("occlusion_only","INT","FACE")
    for v in flag.data:v.value=1
    body.data.attributes.new("occlusion_only","INT","FACE")
    f.select_only([body,occ]);bpy.context.view_layer.objects.active=body;bpy.ops.object.join()
    f.cull_unseen(body,rig,joints,[],states,(-1.5,-1),(1.5,1),frame=Matrix.Translation((0,0,-DEPTH)))
    bm=bmesh.new();bm.from_mesh(body.data);flag=bm.faces.layers.int.get("occlusion_only")
    bmesh.ops.delete(bm,geom=[face for face in bm.faces if face[flag]],context="FACES_ONLY")
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context="VERTS")
    bm.to_mesh(body.data);bm.free();body.data.attributes.remove(body.data.attributes["occlusion_only"])


def main():
    global BUILD_SCALE,BUILD_OFFSET
    BUILD_SCALE=1.0;BUILD_OFFSET=0.0
    draft="--draft" in sys.argv
    f.reset_scene();bpy.context.scene.render.fps=FPS
    f.build_materials();joints=f.resolve_joints();rig=f.build_rig(joints,[])
    f.check_rig_fk(rig,joints)
    kit=f.Kit();build_frame(kit);build_drives(kit)
    f.check_connectivity(kit,joints,[]);check_bearings(kit,joints)
    states=[("rest",{})]+[(f"service {i}",{"LeftService":i,"RightService":i}) for i in range(36)]
    states += [(f"drum {i}",{"Drive":i,"Idler":i}) for i in range(0,360,10)]
    f.check_motion(kit,joints,states)
    body=kit.to_object("SK_SpeedRamp",joints=f.rotary_joints(joints));f.skin(body,rig)
    # Ground-contact undersides are inaccessible, including shared support lands.
    bm=bmesh.new();bm.from_mesh(body.data)
    bmesh.ops.delete(bm,geom=[face for face in bm.faces if all(abs(v.co.z+DEPTH)<1e-6 for v in face.verts)],context="FACES_ONLY")
    bm.to_mesh(body.data);bm.free();f.check_coplanar(body)
    if not draft:
        cull_frame(body,rig,joints,states)
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/"speed_ramp_frame.blend"),compress=True)
    add_stations(rig);belts=build_belts(rig);gap=validate_belts(rig,belts)
    f.check_coplanar(belts)
    # Single render mesh preserves one unit-weight influence on every vertex.
    f.select_only([body,belts]);bpy.context.view_layer.objects.active=body;bpy.ops.object.join()
    actions=build_actions(rig);tris=f.triangles(body)
    scale=Matrix.Translation((0,0,GROUND_OFFSET)) @ Matrix.Scale(DELIVERY_SCALE,4)
    body.data.transform(scale);rig.data.transform(scale)
    for action in actions.values():
        for curve in f.action_fcurves(action):
            if curve.data_path.endswith('location'):
                for key in curve.keyframe_points:
                    key.co.y*=DELIVERY_SCALE
                    key.handle_left.y*=DELIVERY_SCALE;key.handle_right.y*=DELIVERY_SCALE
    BUILD_SCALE=DELIVERY_SCALE;BUILD_OFFSET=GROUND_OFFSET
    pose_distance(rig,0)
    p=[v.co for v in body.data.vertices]
    lwh=[max(v[i] for v in p)-min(v[i] for v in p) for i in (1,0,2)]
    assert all(abs(a-b)<1e-5 for a,b in zip(lwh,TARGET_LWH)),lwh
    if not draft:assert tris<=5000,f"Over budget: {tris}"
    marker=bpy.data.objects.new("LaunchOrigin",None);bpy.context.scene.collection.objects.link(marker)
    marker.location=LAUNCH*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET));marker.parent=rig
    if not draft:f.export([rig,body,marker],"speed_ramp")
    info={"name":"speed_ramp","triangles":tris,"materials":f.SLOTS,
          "space":"Blender +Z up, forward -Y; Godot (x,z,-y)",
          "authored_lwh_m":list(TARGET_LWH),"delivery_scale":DELIVERY_SCALE,
          "ground_offset_m":GROUND_OFFSET,"mounting_m":{"footprint":[WIDTH*DELIVERY_SCALE,LENGTH*DELIVERY_SCALE],"base_z":0.0,"underground_depth":0.0},
          "deck_profile_yz_m":[list(((ENTRY+N*TOP)*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET)))[1:]),list((LAUNCH*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET)))[1:])],
          "shroud_stations":[[y*DELIVERY_SCALE,z*DELIVERY_SCALE+GROUND_OFFSET,w*DELIVERY_SCALE] for y,z,w in SHROUD_STATIONS],
          "authoring_shroud_stations":SHROUD_STATIONS,"authoring_nose_y":NOSE_Y,
          "belt":{"station_count_per_lane":STATIONS,"lane_centers_x_m":[x*DELIVERY_SCALE for _,x in LANES],
                  "lane_width_m":.86*DELIVERY_SCALE,"radius_m":RADIUS*DELIVERY_SCALE,"perimeter_m":PERIMETER*DELIVERY_SCALE,
                  "pitch_m":PITCH*DELIVERY_SCALE,"minimum_rib_gap_m":gap*DELIVERY_SCALE,"entry":list(ENTRY*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET))),"exit":list(EXIT*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET))),
                  "axis":list(T),"normal":list(N),"surface_offset_m":TOP*DELIVERY_SCALE,
                  "carrier":"Reinforced elastomer flexes between rigid stations; moulded ribs remain rigid."},
          "joints":[{"bone":j.name,"parent":j.parent,"type":j.kind,"pivot":list(j.pivot*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET))),"axis":list(j.axis),"range":j.limits} for j in joints.values()],
          "animations":{n:{"frames":[0,int(a.frame_range[1])],"fps":FPS,"loop":n=="convey"} for n,a in actions.items()},
          "launch_design":{"implemented_in_game":False,"exit_angle_deg":math.degrees(ANGLE),
                           "exit_height_m":LAUNCH.z*DELIVERY_SCALE+GROUND_OFFSET,"launch_origin":list(LAUNCH*DELIVERY_SCALE+Vector((0,0,GROUND_OFFSET))),
                           "reference_gravity_m_s2":9.81,"peak_belt_speed_m_s":6*PERIMETER*DELIVERY_SCALE/(58/30),
                           "traction_assist":"Electromagnetic beds preload compatible metal soles; release at LaunchOrigin. Future gameplay contract.",
                           "note":"Driven traction conveyor accelerates along its straight incline. Runtime gravity, robot grip and impulse remain to be agreed."},
          "service":{"opening_degrees":35,"interlock":"Belts stopped before opening either cover."}}
    info['authoring_belt']={**info['belt'],'entry':list(ENTRY),'exit':list(EXIT),'surface_offset_m':TOP}
    speed=info['launch_design']['peak_belt_speed_m_s'];lip=info['launch_design']['exit_height_m']
    vertical=speed*math.sin(ANGLE)
    info['launch_design']['range_from_lip_m']=speed*math.cos(ANGLE)*(vertical+math.sqrt(vertical**2+2*9.81*lip))/9.81
    f.RIG_JSON_PATH.write_text(json.dumps(info,indent=2))
    f.constrain(rig,joints,[])
    rig["preview_poses"]=json.dumps({"service":{n:{"rot":[35,0,0]} for n in ("LeftService","RightService")}})
    rig["preview_pose_views"]=json.dumps(f.PREVIEW_VIEWS)
    scene=bpy.context.scene;scene.render.fps=FPS
    scene["preview_frame"]=json.dumps({"lo":[-.81,-.56,0],"hi":[.81,.56,.80]})
    scene["preview_actions"]=json.dumps(["convey","launch","service_open","service_close"])
    pose_distance(rig,0);preview_floor()
    bpy.data.objects['PRV_Floor'].data.transform(Matrix.Scale(DELIVERY_SCALE,4))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(f.BLEND_PATH),compress=True)
    print(f"[speed_ramp] {tris}/5000 triangles; {len(rig.data.bones)} bones; 4 baked clips")


def refresh_actions():
    """Rebake/export clips without changing a previously validated built mesh."""
    bpy.ops.wm.open_mainfile(filepath=str(f.BLEND_PATH))
    rig=bpy.data.objects["RIG_SpeedRamp"];body=bpy.data.objects["SK_SpeedRamp"]
    for track_ in list(rig.animation_data.nla_tracks):rig.animation_data.nla_tracks.remove(track_)
    rig.animation_data.action=None
    for action in list(bpy.data.actions):bpy.data.actions.remove(action)
    bpy.context.scene.render.fps=FPS;actions=build_actions(rig)
    f.export([rig,body,bpy.data.objects["LaunchOrigin"]],"speed_ramp")
    info=json.loads(f.RIG_JSON_PATH.read_text())
    info["animations"]={n:{"frames":[0,int(a.frame_range[1])],"fps":FPS,"loop":n=="convey"} for n,a in actions.items()}
    info["launch_design"].update(reference_gravity_m_s2=9.81,peak_belt_speed_m_s=6*PERIMETER*DELIVERY_SCALE/(58/30),
        traction_assist="Electromagnetic beds preload compatible metal soles; release at LaunchOrigin. Future gameplay contract.")
    f.RIG_JSON_PATH.write_text(json.dumps(info,indent=2));f.constrain(rig,f.resolve_joints(),[])
    pose_distance(rig,0);bpy.ops.wm.save_as_mainfile(filepath=str(f.BLEND_PATH),compress=True)


if __name__=="__main__":
    if "--animations-only" in sys.argv:refresh_actions()
    else:main()
