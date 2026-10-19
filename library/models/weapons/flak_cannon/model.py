"""Twin-muzzle flak cannon, library-only, with mechanical animations.

Run from library with Blender 5.2 --background --factory-startup --python this file.
The EMP module supplies the established mesh/rig/export/validation framework and
the exact grip, trigger, stock and socket dimensions. No EMP scene is loaded.
The forward shell and rotary loading mechanism are unique to this weapon.
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
    'M_Screen': 'Emissive',
    'M_Secondary': 'Diffuse',
}
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("flak_framework", HERE.parent / "emp_gun/model.py")
k = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = k
spec.loader.exec_module(k)
k.NAME, k.TITLE, k.HERE = "flak_cannon", "FlakCannon", HERE
# User-approved exception for this detailed weapon; cassette budget is unchanged.
k.TRI_BUDGET = 7500
k.BLEND_PATH = HERE / "flak_cannon.blend"
k.RIG_JSON_PATH = HERE / "flak_cannon_rig.json"
# Blender material inputs are scene-linear; authored paint is sRGB #d68c16.
def srgb_linear(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
k.MATERIALS[k.PRI] = (tuple(srgb_linear(v / 255) for v in (214, 140, 22)), 0.45, 0.29, 0.0)
k.MATERIALS[k.EMI] = ((1.0, 0.025, 0.015), 0.0, 0.35, 3.0)
SCREEN = "M_Screen"
k.SLOTS.append(SCREEN)
k.MATERIALS[SCREEN] = ((.2,.85,1.0),.0,.4,5.0)
k.MATERIALS[k.GLS] = ((.55,.75,.8),.0,.03,.0,.25)

PITCH_R, CHAMBER_R = 0.044, 0.0145
# Bootstrap pivots are replaced below by the final plate-edge clearance layout.
MUZZLE_Z = 0.345 - 0.60 * (0.345 - 0.175)
MUZZLE_SPACING = .050
# The loader is a separate index module; its transfer stage feeds the firing breeches.
ROTOR_Z = .226 + PITCH_R * math.sin(math.radians(60))
ROTOR = "LoadRotor"
LOCK, LOCK_TRAVEL = "IndexLock", 0.007
CENTRES = [(PITCH_R * math.cos(math.radians(a)), ROTOR_Z + PITCH_R * math.sin(math.radians(a)))
           for a in (0, 60, 120, 180, 240, 300)]
FIRING = [(-MUZZLE_SPACING/2,MUZZLE_Z),(MUZZLE_SPACING/2,MUZZLE_Z)]
k.JOINT_SPECS = [
    ("Root", None, "fixed", (0, 0, 0), k.UP, k.UP, None),
    (ROTOR, "Root", "hinge", (0, -0.08, ROTOR_Z), k.BACK, k.UP, (0, 120)),
    (LOCK, "Root", "slide", (0, -0.094, ROTOR_Z + 0.0605), k.UP, None, (0, LOCK_TRAVEL)),
    *[(f"Barrel{i}", "Root", "slide", (x, -0.308, z), k.BACK, None, (0, 0.01))
      for i, (x, z) in enumerate(FIRING, 1)],
    (k.TRIGGER, "Root", "hinge", k.TRIGGER_PIVOT, (1, 0, 0), k.DOWN, (0, k.TRIGGER_PULL)),
    (k.MAG, "Root", "slide", (0, k.POST[0], k.BATTERY[2][0]), k.DOWN, None, (0, k.MAG_TRAVEL)),
    (k.CATCH_BONE, "Root", "slide", (0, k.CATCH[0], k.CATCH[1]), k.LEFT, None, (0, k.CATCH_TRAVEL)),
]
k.PISTON_SPECS=[]
# In-place weapon clips, 30 fps. All interpolation is baked per frame.
k.ANIMATIONS={
    "idle":(True,"LINEAR",{k.TRIGGER:k.hold_keys(0,30)}),
    "fire":(False,"LINEAR",{
        k.TRIGGER:k.eased([(0,0),(2,k.TRIGGER_PULL),(6,k.TRIGGER_PULL),(9,0),(20,0)]),
        **{b:k.shaped([(0,0,"io"),(2,.010,"out"),(7,0,"io")],20) for b in ("Barrel1","Barrel2")},
        LOCK:k.eased([(0,0),(8,0),(10,LOCK_TRAVEL),(18,LOCK_TRAVEL),(20,0)]),
        ROTOR:k.eased([(0,0),(10,0),(18,120),(20,120)])}),
    "mag_release":(False,"LINEAR",{
        k.CATCH_BONE:k.eased([(0,0),(3,k.CATCH_TRAVEL),(14,k.CATCH_TRAVEL)]),
        k.MAG:k.shaped([(0,0,"io"),(3,0,"io"),(10,k.MAG_TRAVEL,"in")],14)}),
    "mag_insert":(False,"LINEAR",{
        k.MAG:k.shaped([(0,k.MAG_TRAVEL,"io"),(8,0,"io")],14),
        k.CATCH_BONE:k.eased([(0,k.CATCH_TRAVEL),(8,k.CATCH_TRAVEL),(11,0),(14,0)])})}

k.FK_TEST_STATE = {ROTOR: 60, LOCK: LOCK_TRAVEL, "Barrel1": 0.006, "Barrel2": 0.006, k.TRIGGER: 5, k.MAG: 0.01, k.CATCH_BONE: 0.004}
k.PREVIEW_STATES = {"indexed": {ROTOR: 120, LOCK: LOCK_TRAVEL}, "recoil": {"Barrel1": 0.01, "Barrel2": 0.01},
                    "mag_out": {k.MAG: k.MAG_TRAVEL, k.CATCH_BONE: k.CATCH_TRAVEL}}
k.PREVIEW_VIEWS = {"indexed": ["front_left"], "recoil": ["left"], "mag_out": ["front_left"]}
k.SHOWCASE = ["idle","fire","fire","fire","mag_release","mag_insert","idle"]

def sweep_states(joints):
    states = [(f"index {a}", {ROTOR: a, LOCK: LOCK_TRAVEL}) for a in range(0, 121, 5)]
    states += [(f"index unlock {i}", {LOCK: i * LOCK_TRAVEL / 5}) for i in range(6)]
    states += [(f"paired recoil {i}", {"Barrel1": i * 0.002, "Barrel2": i * 0.002}) for i in range(6)]
    states += [(f"trigger {a}", {k.TRIGGER: a}) for a in range(0, k.TRIGGER_PULL + 1, 2)]
    states += [(f"catch {i}", {k.CATCH_BONE: i * k.CATCH_TRAVEL / 4}) for i in range(5)]
    states += [(f"cassette {i}", {k.CATCH_BONE: k.CATCH_TRAVEL, k.MAG: i * k.MAG_TRAVEL / 10}) for i in range(11)]
    return states

k.sweep_states = sweep_states

# Preserve the EMP lower keel contact section, independently of the larger shell.
def section(y):
    if y <= -0.065:
        w, top = 0.079, 0.335
    elif y < 0.065:
        t = (y + 0.065) / 0.130
        w, top = 0.079 - 0.047 * t, 0.335 - 0.041 * t
    else:
        w, top = 0.032, 0.294
    # Continuous solid lower flange; its angled underside is the actual hand seat.
    # The lower bearing land continues across the service seam before tapering,
    # giving both clamp cams a full flat seat rather than a half-supported rim.
    lower_w = 0.079 if y <= -0.043 else (0.079 - 0.047 * min(1,(y+0.043)/0.108))
    right = k.keel_points(y) + [(0.032, 0.197), (lower_w, 0.205), (lower_w, 0.226),
                              (w, 0.232), (w, 0.259), (w, 0.265), (w, top - 0.020),
                              (w * 0.82, top - 0.004), (w * 0.60, top - 0.004), (w * 0.46, top + 0.010)]
    pts = right + [(-x, z) for x, z in reversed(right)]
    if y == -0.300:
        pts = [(x * (w - 0.002) / w, z + (0.247 - z) * 0.023) for x, z in pts]
    return [Vector((x, y, z)) for x, z in pts]

def inset_front_profile(margin=.004):
    # Clip the actual nose section at the cover interface, then offset its edges.
    # This keeps the service plate parallel to every casting chamfer and keel chord.
    pts = [(v.x,v.z) for v in section(-.300)]
    clipped=[]
    roof=.332
    for p,q in zip(pts,pts[1:]+pts[:1]):
        if p[1] <= roof: clipped.append(p)
        if (p[1] <= roof) != (q[1] <= roof):
            t=(roof-p[1])/(q[1]-p[1]);clipped.append((p[0]+t*(q[0]-p[0]),roof))
    def cross(a,b): return a[0]*b[1]-a[1]*b[0]
    clean=[]
    for p,q,r in zip(clipped[-1:]+clipped[:-1],clipped,clipped[1:]+clipped[:1]):
        if abs(cross((q[0]-p[0],q[1]-p[1]),(r[0]-q[0],r[1]-q[1])))>1e-9: clean.append(q)
    area=sum(cross(p,q) for p,q in zip(clean,clean[1:]+clean[:1]))
    side=1 if area>0 else -1
    lines=[]
    for p,q in zip(clean,clean[1:]+clean[:1]):
        d=Vector((q[0]-p[0],q[1]-p[1])).normalized()
        lines.append((Vector(p)+Vector((-d.y,d.x))*margin*side,d))
    # Short convex bevel edges can disappear at a deep inset. Remove redundant
    # offset lines instead of letting their reversed spans make crossed faces.
    while True:
        out=[];remove=None
        for i,(a,d0) in enumerate(lines):
            b,d1=lines[(i+1)%len(lines)]
            den=cross(d0,d1)
            if abs(den)<1e-8:
                n=Vector((-d0.y,d0.x))*side
                remove=i if (b-a).dot(n)>0 else (i+1)%len(lines)
                break
            out.append(a+d0*(cross(b-a,d1)/den))
        if remove is None:
            for i,(_,d) in enumerate(lines):
                if (out[i]-out[i-1]).dot(d)<-1e-8:
                    remove=i;break
        if remove is None: return [(p.x,p.y) for p in out]
        del lines[remove]
        assert len(lines)>=3,"Front plate inset exceeds the casting's available width"

NOSE_RECESS = inset_front_profile(.005)
plate_profile = inset_front_profile(.015)
PLATE_HALF_WIDTH = max(abs(x) for x,z in plate_profile)
PLATE_BOTTOM = min(z for x,z in plate_profile if abs(abs(x)-PLATE_HALF_WIDTH)<1e-6)
# Remove only the narrow tongue. Retain the broad face's sloped lower chords.
shoulder=min((p for p in plate_profile if p[0]>PLATE_HALF_WIDTH*.25
              and p[0]<PLATE_HALF_WIDTH*.5),key=lambda p:p[1])
PLATE_TONGUE_CUTOFF=shoulder[1]
BLAST_FACE=[p for p in plate_profile if p[1]>=PLATE_TONGUE_CUTOFF-1e-7]
# Actual offset of the two adjacent edges at each broad corner.
CORNER_CLEARANCE=.0075
bottom_slope=(PLATE_BOTTOM-shoulder[1])/(PLATE_HALF_WIDTH-shoulder[0])
top_corner=max(z for x,z in BLAST_FACE if abs(x-PLATE_HALF_WIDTH)<1e-6)
top_chamfer=min((p for p in BLAST_FACE if p[0]<PLATE_HALF_WIDTH-1e-6
                 and p[0]>PLATE_HALF_WIDTH*.8),key=lambda p:abs(p[1]-top_corner))
top_slope=(top_chamfer[1]-top_corner)/(top_chamfer[0]-PLATE_HALF_WIDTH)
screw_x=PLATE_HALF_WIDTH-CORNER_CLEARANCE
screw_bottom=PLATE_BOTTOM+bottom_slope*(screw_x-PLATE_HALF_WIDTH)+CORNER_CLEARANCE*math.sqrt(1+bottom_slope**2)
screw_top=top_corner+top_slope*(screw_x-PLATE_HALF_WIDTH)-CORNER_CLEARANCE*math.sqrt(1+top_slope**2)
PLATE_SCREWS=[(sx*screw_x,z) for sx in (-1,1) for z in (screw_bottom,screw_top)]
BARREL_MOUNT_R, PLATE_CLEARANCE = .023, .010
MUZZLE_SPACING=2*(PLATE_HALF_WIDTH-BARREL_MOUNT_R-PLATE_CLEARANCE)
MUZZLE_Z=PLATE_BOTTOM+bottom_slope*(MUZZLE_SPACING/2-PLATE_HALF_WIDTH)+(BARREL_MOUNT_R+PLATE_CLEARANCE)*math.sqrt(1+bottom_slope**2)
FIRING=[(-MUZZLE_SPACING/2,MUZZLE_Z),(MUZZLE_SPACING/2,MUZZLE_Z)]
for i,(x,z) in enumerate(FIRING,1):
    for j,entry in enumerate(k.JOINT_SPECS):
        if entry[0]==f"Barrel{i}":
            k.JOINT_SPECS[j]=(*entry[:3],(x,-.308,z),*entry[4:])


def build_shell(kit):
    cuts = [((0, -0.287, ROTOR_Z), (0, -0.071, ROTOR_Z), 0.065, 24),
            ((0, -0.094, 0.314), (0, -0.094, 0.351), 0.006, 8)]
    cuts += [((x, -0.320, z), (x, -0.276, z), 0.0183, 12) for x, z in FIRING]
    # Long viewing/cooling ports are actual through cuts, never glass.
    # A radiused/chamfered tooling profile, wholly within the shroud's side flat.
    def side_profile(y0,y1,z0,z1,c,x=0):
        return [(x,y,z) for y,z in [(y0+c,z0),(y1-c,z0),(y1,z0+c),(y1,z1-c),
                                  (y1-c,z1),(y0+c,z1),(y0,z1-c),(y0,z0+c)]]
    windows = [(side_profile(-.266,-.080,.237,.302,.007), (1,0,0), .20)]
    boxes = [((0, -0.177, 0.3485), (0.024, 0.140, 0.036))]
    # Paired feed wells and a transfer gallery connect the cassette to the lower
    # reload stations behind the rotor. The upper gallery clears the index motor.
    boxes += [((sx * 0.031, 0.014, 0.188), (0.012, 0.048, 0.076)) for sx in (-1, 1)]
    reload_z=ROTOR_Z+PITCH_R*math.sin(math.radians(60))
    boxes += [((0,.014,.220),(.078,.048,.012))]
    internal = [((sx*.022,.003,(.214+reload_z+.006)/2),(.012,.012,reload_z+.006-.214))
                for sx in (-1,1)]
    internal += [((0,(-.082+.005)/2,reload_z),(.060,.087,.012))]
    # Guard against machining a feed channel through the tapered outer roof.
    def inside_section(x,y,z):
        pts=[(v.x,v.z) for v in section(y)]
        hit=False
        for a,b in zip(pts,pts[1:]+pts[:1]):
            if (a[1]>z)!=(b[1]>z) and x < a[0]+(z-a[1])*(b[0]-a[0])/(b[1]-a[1]): hit=not hit
        return hit
    for centre,size in internal:
        for sx in (-1,1):
            for sy in (-1,1):
                for sz in (-1,1):
                    p=tuple(centre[i]+sign*size[i]/2 for i,sign in enumerate((sx,sy,sz)))
                    assert inside_section(*p),f"Feed channel escapes housing: {p}"
    boxes += internal
    # Machined exhaust slots through the rear receiver, clear of the hand web.
    boxes += [((sx * 0.032, y, 0.280), (0.012, 0.003, 0.013)) for sx in (-1, 1)
              for y in (0.106, 0.119, 0.132, 0.145, 0.158, 0.171)]
    nose_pocket = [([(x, -0.298, z) for x, z in NOSE_RECESS], k.BACK, 0.016)]
    skin = k.loft([-0.300, -0.297, -0.065, -0.043, 0.065, 0.215], section)
    # Independently closed body and upper cover castings. Each entire casting has one finish;
    # colour boundaries are assembly interfaces, never selected painted faces.
    # Flush butt interfaces: no open slit; real fasteners cross the joints.
    seam = 0.0
    region = lambda yz: ([(0,y,z) for y,z in yz],(1,0,0),1.0)
    lower = region([(-.4,0),(.4,0),(.4,.291-seam),(.065,.291-seam),
                    (-.065,.332-seam),(-.4,.332-seam)])
    cover = region([(-.4,.332+seam),(-.065,.332+seam),(.065,.291+seam),(.4,.291+seam),(.4,.5),(-.4,.5)])
    # Shroud bolts are recessed into blind counterbores, with continuous shanks.
    counterbores = [((sx*.0775,y,z),(sx*.084,y,z),.0038,8)
                   for sx in (-1,1) for y,z in ((-.282,.309),(-.076,.309),(-.282,.224),(-.083,.224))]
    # Receiver maintenance hatches seat in shallow machined pockets below the vents.
    pockets = [(side_profile(.080,.194,.214,.260,.005,x=sx*.032),(1,0,0),.003)
               for sx in (-1,1)]
    frame_pockets = [(side_profile(-.294,-.068,.214,.317,.004,x=sx*.079),(1,0,0),.004)
                     for sx in (-1,1)]
    # Outer chamfers are lofted into the casting. Fitted panels supply their own
    # edge bevels; redundant hidden bevel rings beneath them are omitted.
    for material, regions in [(k.PRI,[lower]),(k.MTL,[cover])]:
        k.carve(kit,skin.copy(),"Root",material,cuts=cuts+counterbores,boxes=boxes,
                subtract=nose_pocket+windows+pockets+frame_pockets,intersect=regions,
                bevel=0,bevel_normal=(1,0,0))
    skin.free()
    # Flush removable window frames: the four screws actually retain these plates.
    for sx in (-1,1):
        kit.plate(side_profile(-.294,-.068,.214,.317,.004,x=sx*.078),.002,(1,0,0),"Root",k.PRI,
                  subtract=windows,cuts=counterbores,bevel=.0006)
    kit.plate([(x,-.2925,z) for x,z in NOSE_RECESS],.005,k.BACK,"Root",k.SEC,
              holes=[[(x,-.2925,z) for x,z in BLAST_FACE]],bevel=.0004)
    kit.plate([(x, -0.292, z) for x, z in BLAST_FACE], 0.004, k.BACK, "Root", k.JNT,
              cuts=[((x, -0.303, z), (x, -0.285, z), 0.0183, 12) for x, z in FIRING]
                   +[((x,-.295,z),(x,-.2922,z),.0042,12) for x,z in PLATE_SCREWS], bevel=.0015)
    # Stationary shaft bridges the front web and rear bulkhead, with bearing seats.
    kit.cyl((0, -0.2927, ROTOR_Z), (0, -0.063, ROTOR_Z), 0.008, "Root", k.JNT, segs=12)
    for y in (-0.2905, -0.074):
        k.pipe(kit, (0, y - 0.003, ROTOR_Z), (0, y + 0.003, ROTOR_Z), 0.016, 0.008,
               "Root", k.BRZ, segs=12)
    # A coaxial geared index motor housed in the solid rear shoulder, not a decorative cap.
    kit.cyl((0, -0.070, ROTOR_Z), (0, -0.029, ROTOR_Z), 0.025, "Root", k.MTL, segs=12)
    for sx in (-1, 1):
        for y, z in ((-0.282, 0.309), (-0.076, 0.309), (-0.282, 0.224), (-0.083, 0.224)):
            k.bolt(kit, (sx * 0.0775, y, z), (sx, 0, 0), "Root", r=0.0025, head=0.0010)
    for sx in (-1,1):
        kit.plate(side_profile(.081,.193,.215,.259,.005,x=sx*.0313),.0014,(1,0,0),"Root",k.PRI,
                  bevel=.0005)
        for y in (.089,.185):
            k.bolt(kit,(sx*.032,y,.237),(sx,0,0),"Root",r=.0022,head=.0008)
    # Full-length screws carry the upper cover, through its assembly seam into
    # the receiver/shroud's blind threaded seats. Heads alone would not attach it.
    for y,x,roof in ((-.270,.029,.345),(-.107,.029,.345),(.170,.010,.304)):
        for sx in (-1,1):
            kit.cyl((sx*x,y,roof-.021),(sx*x,y,roof),0.0018,"Root",k.JNT,segs=6)
            k.bolt(kit,(sx*x,y,roof),k.UP,"Root",r=0.0028,head=0.0012)
    # Recessed light occupies a machined top pocket, with a dark bezel below it.
    kit.box((0, -0.177, 0.3370), (0.023, 0.139, 0.013), "Root", k.MTL)
    kit.box((0, -0.177, 0.3440), (0.010, 0.116, 0.001), "Root", k.EMI)
    # Four recessed fasteners, each with a machined conical chrome seat.
    # Their shanks cross the plate into the casting; no floating corner heads.
    for x,z in PLATE_SCREWS:
        k.revolve(kit,[(.0028,-.2922),(.0032,-.2938),(.0042,-.294),(.0042,-.2922)],
                  (x,0,z),k.BACK,(1,0,0),"Root",k.JNT,segs=12,loop=True)
        kit.cyl((x,-.285,z),(x,-.2932,z),.0018,"Root",k.JNT,segs=6)
        k.bolt(kit,(x,-.2932,z),k.FWD,"Root",r=.0026,mat=k.MTL,head=.0005)
    # Side cams retain the lower service assembly on its inset mounting land.
    for sx in (-1, 1):
        y, z = -0.065, 0.186
        k.revolve(kit, [(0.0035, sx*0.032), (0.010, sx*0.032), (0.010, sx*0.036),
                       (0.008, sx*0.038), (0.0035, sx*0.038)], (0,y,z), (1,0,0), (0,1,0),
                  "Root", k.FRM, segs=12, loop=True)
        k.bolt(kit, (sx*0.032,y,z), (sx,0,0), "Root", r=0.0035, mat=k.MTL, head=0.005)
    # Lock pin in an integral bored collar: pin withdraws before indexing.
    k.pipe(kit, (0,-0.094,0.328), (0,-0.094,0.343), 0.006, 0.0028, "Root", k.FRM, segs=8)
    kit.cyl((0,-0.094,ROTOR_Z+0.0605), (0,-0.094,0.335), 0.0025, LOCK, k.JNT, segs=8)


def build_display(kit):
    # Console is fastened to the rear ramp; its mounting foot follows that plane.
    y = .006
    z = .345 - .041 * (y+.065)/.130
    base = Vector((0,y,z))
    u = Vector((0,1,-.041/.130)).normalized()
    n = Vector((0,.041/.130,1)).normalized()
    x = Vector((1,0,0))
    def outline(w,h,c,offset):
        return [base+x*(a * (1 - 2 * .46 * (.047/.130) * u.y * b / w))+u*b+n*offset for a,b in
                [(-w/2+c,-h/2),(w/2-c,-h/2),(w/2,-h/2+c),(w/2,h/2-c),
                 (w/2-c,h/2),(-w/2+c,h/2),(-w/2,h/2-c),(-w/2,-h/2+c)]]
    kit.plate(outline(.045,.072,.004,.001),.004,n,"Root",k.MTL,
              subtract=[(outline(.036,.055,.002,.003),n,.002)],bevel=.0007)
    kit.plate(outline(.035,.054,.002,.0021),.0006,n,"Root",SCREEN)
    kit.plate(outline(.035,.054,.002,.00275),.0005,n,"Root",k.GLS)
    for b,half in [(-.030,.019),(.030,.011)]:
        for a in (-half,half):
            k.bolt(kit,base+x*a+u*b+n*.003,n,"Root",r=.0018,head=.0005)


def build_rotor(kit):
    # Two bored carrier spiders clamp six cartridge chambers around a common hub.
    for y0, y1 in ((-0.285, -0.278), (-0.090, -0.082)):
        bm = k.loft([y0, y1], lambda y: k.ring_xz(0, ROTOR_Z, 0.062, y, n=16))
        bores = [((x, y0 - 0.001, z), (x, y1 + 0.001, z), CHAMBER_R, 8) for x, z in CENTRES]
        bores.append(((0, y0 - 0.001, ROTOR_Z), (0, y1 + 0.001, ROTOR_Z), 0.014, 12))
        k.carve(kit, bm, ROTOR, k.FRM, cuts=bores)
    k.pipe(kit, (0, -0.284, ROTOR_Z), (0, -0.083, ROTOR_Z), 0.014, 0.0084, ROTOR, k.MTL, segs=12)
    for x, z in CENTRES:
        k.pipe(kit, (x, -0.282, z), (x, -0.085, z), CHAMBER_R, 0.0115, ROTOR, k.JNT, segs=8)
    # Stepped cartridge seats at the back of each larger expansion tube.
    for x,z in CENTRES:
        k.pipe(kit,(x,-.139,z),(x,-.085,z),.0115,.0059,ROTOR,k.MTL,segs=8)
    # Mid-span clamp: joins the tubes, clear of the shroud throughout rotation.
    bm = k.loft([-0.186, -0.179], lambda y: k.ring_xz(0, ROTOR_Z, 0.061, y, n=16))
    k.carve(kit, bm, ROTOR, k.MTL,
            cuts=[((x, -0.188, z), (x, -0.177, z), CHAMBER_R, 8) for x, z in CENTRES]
            + [((0, -0.188, ROTOR_Z), (0, -0.177, ROTOR_Z), 0.014, 12)])
    # Twelve notches, four per paired index. This is the lock track, not a
    # decorative gear pretending to mesh with an absent pinion.
    def lock_ring(y):
        return [Vector((r*math.cos(a), y, ROTOR_Z+r*math.sin(a)))
                for j in range(48) for r,a in [((0.061 if j%4 in (0,3) else 0.063), math.tau*j/48)]]
    k.carve(kit, k.loft([-0.098,-0.090],lock_ring), ROTOR, k.BRZ,
            cuts=[((0,-0.100,ROTOR_Z),(0,-0.088,ROTOR_Z),0.049,16)])

def build_barrels(kit):
    for i, (x, z) in enumerate(FIRING, 1):
        # Long stationary sleeves guide the sliding tube and couple to the firing chambers.
        k.pipe(kit, (x, -0.319, z), (x, -0.300, z), 0.021, 0.0183, "Root", k.MTL, segs=12)
        k.pipe(kit, (x,-0.308,z), (x,-0.300,z), 0.023, 0.021, "Root", k.FRM, segs=12)
        k.lathe(kit,[(.0184,-.300),(.0184,-.297),(.013,-.292),(.0115,-.2853),
                     (.0208,-.2853),(.0208,-.300)],"Root",k.FRM,segs=12,cx=x,cz=z,loop=True)
        # A closed, dark firing breech behind the two indexed chambers.
        kit.cyl((x,-.0815,z),(x,-.065,z),.017,"Root",k.MTL,segs=12)
        # One turned hollow barrel per muzzle, no buried decorative cylinder end caps.
        # Turned relief separates the muzzle crown from the sliding barrel.
        # Its inset lies inside the established outer/collider envelope.
        profile = [(0.013, -0.363), (0.019, -0.363), (0.020, -0.360),
                   (0.020, -0.356), (0.0188, -0.3555), (0.0188, -0.3535),
                   (0.020, -0.353), (0.020, -0.346),
                   (0.018, -0.343), (0.018, -0.308), (0.013, -0.308)]
        k.lathe(kit, profile, f"Barrel{i}", k.JNT, segs=12, cx=x, cz=z, loop=True)
        # A matte bore reads as a deep, heat-darkened cavity rather than a
        # chrome tube. Reuse the existing finish; no texture or material slot.
        group=kit.groups.index(f"Barrel{i}")
        for barrel_face in kit.bm.faces:
            if all(v[kit.deform].get(group,0)>0.99 for v in barrel_face.verts):
                if all(math.hypot(v.co.x-x,v.co.z-z)<=0.01301 for v in barrel_face.verts):
                    barrel_face.material_index=k.SLOTS.index(k.SEC)
        # User-requested visual bore occluder: one 2D matte-black disc, 1 cm in.
        ring=[kit.bm.verts.new((x+.013*math.cos(math.tau*j/12),-.353,
                               z+.013*math.sin(math.tau*j/12))) for j in range(12)]
        for v in ring: v[kit.deform][group]=1.0
        face=kit.bm.faces.new(ring)
        face.material_index=k.SLOTS.index(k.SEC)
        # This visual face deliberately has no physical Part/collision volume.

def build_pack(kit):
    # Same EMP dock envelope and lock post: a ballistic cassette with visible rounds.
    (b0, b1), w, (z0, z1) = k.BATTERY
    ym = (b0 + b1) / 2
    slots = [((sx * w, ym, 0.117), (0.010, 0.040, 0.025)) for sx in (-1, 1)]
    slots += [((sx * 0.031, 0.014, 0.124), (0.012, 0.048, 0.068)) for sx in (-1, 1)]
    outline = [(w, z0), (w, z1 - 0.003), (w - 0.003, z1), (-w + 0.003, z1), (-w, z1 - 0.003), (-w, z0)]
    kit.plate([(x, ym, z) for x, z in outline], b1 - b0, k.BACK, k.MAG, k.PRI, boxes=slots, bevel=.0010)
    kit.box((0, ym, 0.0775), (0.083, 0.059, 0.015), k.MAG, k.SEC, bevel=0.003)
    for sx in (-1, 1):
        for y in (-0.002, 0.014, 0.030):
            kit.cyl((sx * 0.031, y, 0.090), (sx * 0.031, y, 0.144), 0.0055, k.MAG, k.BRZ, segs=8)
    for x in (-0.012, 0.012):
        kit.box((x, -0.001, 0.1535), (0.0015, 0.010, 0.008), k.MAG, k.FRM)
    py, pr, top, (g0, g1), dep = k.POST
    k.revolve(kit, [(0, z1 - 0.001), (pr, z1 - 0.001), (pr, g0), (pr - dep, g0 + 0.0003),
                   (pr - dep, g1 - 0.0003), (pr, g1), (pr, top - 0.0012), (pr - 0.0012, top), (0, top)],
              (0, py, 0), k.UP, (1, 0, 0), k.MAG, k.JNT, segs=12)

def build_dock(kit):
    """Machine the EMP cross-bolt dock with two real ballistic feed openings."""
    # Reuse the exact lock, pocket and catch bores, adding feed cuts through the
    # dock ceiling using the same plate/carve operation (no overlapping dock).
    original = k.Kit.plate
    def feed_plate(self, outline, thickness, normal, bone, mat, **kw):
        boxes = list(kw.get("boxes", ()))
        boxes += [((sx * 0.031, 0.014, 0.160), (0.012, 0.048, 0.035)) for sx in (-1, 1)]
        kw["boxes"] = boxes
        return original(self, outline, thickness, normal, bone, mat, **kw)
    k.Kit.plate = feed_plate
    try:
        k.build_dock(kit)
    finally:
        k.Kit.plate = original

def build_gun(kit, pistons, joints):
    build_shell(kit)
    build_rotor(kit)
    build_display(kit)
    build_barrels(kit)
    k.build_grip(kit)
    k.build_trigger(kit)
    k.build_stock(kit)
    build_dock(kit)
    k.build_catch(kit)

def gizmo_specs():
    return [(f"Muzzle{i}", f"Barrel{i}", Vector((x, -0.373, z)), Vector(k.FWD), Vector(k.UP))
            for i, (x, z) in enumerate(FIRING, 1)] + [
        ("LoaderAxis", ROTOR, Vector((0, -0.08, ROTOR_Z)), Vector(k.FWD), Vector(k.UP))]

def write_metadata(ammo_frame, joints, pistons, tris, ammo_tris, size, dy):
    # Use the established hand contract without copying EMP-specific fire descriptions.
    vec = lambda v: [round(float(c), 6) for c in v]
    at = lambda v: Vector(v) + Vector((0, dy, 0))
    godot = lambda v: vec((v[0], v[2], -v[1]))
    hands = {}
    for side in ("Left", "Right"):
        wrist, x, y, z = k.hand_frame(side)
        curls, (mx, mz, tc) = k.GRIP_POSE[side]
        pose = {f"{side}{f}{seg}": [round(c * scale, 1), 0, 0] for f, c in curls.items()
                for seg, scale in (("Proximal", 1), ("Intermediate", 1.1), ("Distal", 0.8))}
        pose.update({f"{side}ThumbMetacarpal": [mx, 0, mz], f"{side}ThumbProximal": [tc, 0, 0], f"{side}ThumbDistal": [tc, 0, 0]})
        hands[f"{side}HandSocket"] = {"hand_bone": f"{side}Hand", "grips": "EMP-compatible forend" if side == "Left" else "EMP-compatible pistol grip",
            "wrist_blender": vec(at(wrist)), "wrist_godot": godot(at(wrist)), "grip_pose_deg": pose,
            **{f"bone_{axis}_{space}": fn(v) for axis, v in zip("xyz", (x, y, z)) for space, fn in (("blender", vec), ("godot", godot))}}
    data = {"name": k.NAME, "rest": "pair 240/300 degrees at the lower transfer station; trigger released; cassette seated",
        "space": "metres; Blender +Z up, muzzle -Y; origin bottom plane, centred along length; Godot (x,z,-y)",
        "materials": k.SLOTS, "size_m": {"wide": size.x, "long": size.y, "high": size.z, "max_wide_long_high": list(k.WEAPON_MAX)},
        "triangles": {"SK_FlakCannon": tris, "SM_FlakCannonAmmo": ammo_tris},
        "triangle_budgets": {"SK_FlakCannon":k.TRI_BUDGET,"SM_FlakCannonAmmo":k.AMMO_BUDGET},
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(at(j.pivot)), "axis": vec(j.axis), "range": j.limits} for j in joints.values()],
        "animations": {name:{"frames":[0,max(f for ks in keys.values() for f,v in ks)],
                             "fps":k.FPS,"loop":loop,"joints":sorted(keys)}
                       for name,(loop,interp,keys) in k.ANIMATIONS.items()},
        "pistons": [], "hand_sockets": hands,
        "assembly": {"parts": ["orange unibody shroud/receiver", "black upper cover", "recessed chrome blast plate with black bezel", "orange removable window frames", "orange receiver hatches", "rear-slope display console"],
                     "construction": "separately closed castings; uniform material per casting; flush butt interfaces crossed by full-length fastening shanks",
                     "clamp_cam": {"y_blender": -0.065+dy, "z_blender": 0.186, "seat": "inset lower service land"}},
        "ammo_hand_socket": k.ammo_socket_json((at(ammo_frame[0]), *ammo_frame[1:])),
        "gizmos": [{"name": n, "bone": b, "position": vec(at(p)), "forward": vec(f), "up": vec(u)} for n, b, p, f, u in gizmo_specs()],
        "mechanism": {"description": "six cartridge loading tubes indexed in three 120-degree steps; a transfer stage presents the indexed lower pair to two separate stationary firing breeches; each cartridge contains multiple flak fragments; paired discharge sends a fragment cluster through each muzzle",
            "load_path": "rear receiver routes cassette transfer to the upper chamber pair and retains extracted canisters; coaxial index drive turns the carrier on a stationary through-shaft in front/rear bearings",
            "index_deg": 120, "chambers": 6, "muzzles": 2, "recoil_m": 0.01,
            "muzzle_height_m": MUZZLE_Z, "front_mass_height_m": [0.175, 0.345], "muzzle_fraction_down_from_top": (.345-MUZZLE_Z)/(.345-.175), "muzzle_centre_spacing_m": MUZZLE_SPACING,
            "barrel_mount_plate_clearance_m": PLATE_CLEARANCE, "barrel_mount_radius_m": BARREL_MOUNT_R,
            "index_lock": {"bone": LOCK, "travel_m": LOCK_TRAVEL, "notches": 12, "notches_per_step": 4,
                           "sequence": "retract locating pin fully, index 120 degrees, seat pin in the next notch"},
            "note": "mechanical animation concept; internal transfer/extractor internals not detailed; gameplay spread, damage, ammunition count and timing remain undecided"},
        "ammo": {"bone": k.MAG, "pickup_file": "flak_cannon_ammo.glb", "axis": [0, 0, -1], "travel_m": k.MAG_TRAVEL},
        "validation": {"motion_sweep_states": len(k.sweep_states(joints)), "hand_reference": "emp_gun hand_frame and GRIP_POSE; no character clips generated"}}
    k.RIG_JSON_PATH.write_text(json.dumps(data, indent=2))

k.build_gun, k.build_pack, k.gizmo_specs, k.write_rig_json = build_gun, build_pack, gizmo_specs, write_metadata
# EMP marker creation contains EMP-specific locators; native exported empties suffice here.
k.build_preview_markers = lambda rig, dy: None

if __name__ == "__main__":
    if "--uv-only" in sys.argv:
        sys.path.insert(0,str(HERE.parents[1]))
        from material_uv import refresh_asset
        refresh_asset(HERE)
    else:
        k.main()
