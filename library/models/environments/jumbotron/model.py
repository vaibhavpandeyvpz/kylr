"""Jumbotron - a 10 m floating screen and lighting rig for the middle of KYLR's maps, modelled, rigged
and animated from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/environments/jumbotron/model.py

Produces, next to this script:
    jumbotron.blend            source scene, opened by preview.py and animate.py
    jumbotron.glb / .fbx       SK_Jumbotron (the rig), SK_JumbotronScreen (its four displays) and
                               SK_JumbotronMarquee (its two marquee rings), skinned to RIG_Jumbotron; the gizmos
                               Spot<Position>Beam (one per spotlight, on its head); the actions hover (looped),
                               spin_up, spin_down, lights_on, flood, show (looped) and lights_off
    jumbotron_rig.json         the joints and their ranges, the spotlights (their aim at every zone of the map,
                               cone and range), the rotors, the displays' and marquees' UVs and the gizmos

Design: a quad-rotor lifting rig 10 m square that hovers 25 m over the middle of the arena. In the middle, one
lofted unibody (the weapons' language): an off-white fuselage drum with slanted vents and a beacon on top, a
wide grey ring round its foot carrying the upper marquee, a box under it with a display recessed in each of its
four faces, a narrow lower marquee ring under the box and a round belly pan. Four lofted arms run out on the
diagonals to the motor pods, each at the centre of a ducted rotor (the duct fused to the arm and two more spokes,
a Y over the rotor like a cinewhoop's guard); a titanium motor can under each pod drives a five-bladed rotor in the
duct. Twelve moving-head spotlights light the arena: eight round the belly pan and four under the ducts' outer
corners. Each is a pan stage (a titanium pan motor in the mount, a stainless rotor boss, a matte black yoke with a
titanium tilt motor) and a tilting head (an off-white can with a black bezel round its
lens), so it can aim anywhere under the rig. The displays and marquees are their own meshes, white and emissive
(the game puts its textures there). Map-generic finish in Tensor's materials.

Lighting: the map is 25 x 75 m, its long axis on the rig's Y (front-back); it is tiled into 2 x 6 zones of 12.5 m
and each spot is given the zone it reaches best (least tilt, an exact assignment). flood aims every spot at the
middle of its zone; _rig.json gives each its cone (the half-angle that takes in its zone's corners, with overlap)
and range, for the game's SpotLight3D on its Spot<Position>Beam gizmo.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a hinge isn't coaxial with its
bearing, anything collides through any animation frame or across the joints' ranges, two spots' swept volumes
meet, a spot's beam in flood hits the rig, or anything leaves the 10 x 10 m envelope.
Conventions: 1 unit = 1 m, Z up, front = -Y (its left is +X). The origin is at the centre of the belly pan's flat
underside (z = 0), on the rig's axis: in play it hovers there 25 m over the floor; the spots hang below it. Rest
pose = the rotors stopped, every spot's head straight down.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Lamp': 'Emissive',
    'M_Marquee': 'Emissive',
    'M_Primary': 'Metallic',
    'M_Screen': 'Emissive',
    'M_Secondary': 'Metallic',
    'M_Titanium': 'Metallic',
}

import json
import math
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

NAME = "jumbotron"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # Jumbotron

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored by the kit)

HALF = 5.0                             # the envelope: 10 x 10 m in plan (|x|, |y| <= 5 in every state)
HOVER = 25.0                           # the belly's height over the arena floor in play
ARENA = (25.0, 75.0)                   # the map the spots light: across X, along Y (the rig's front-back)
ZONES = (2, 6)                         # ...tiled in zones, one spot each: across, along
CONE_MARGIN = 4.0                      # degrees each spot's cone takes in past its zone's corners (overlap)
N = 24                                 # sides of the round shells; a face is centred on each axis and diagonal
N_DUCT = 16                            # ...of the ducts
N_POD = 8                              # ...of the motor pods and their cans
# The belly pan and the lower marquee ring (radius at the corners, z), bottom up: the pan's flat underside (the
# spots' mount), its chamfer, wall and roof, a chamfer into the marquee band, and the band, up into the box's
# underside (its top buried in the box).
LOWER = [(1.85, 0.0), (1.95, 0.08), (1.95, 0.20), (1.62, 0.30), (1.55, 0.34), (1.55, 0.80)]
LOWER_BAND = 4                         # the band from LOWER[4] up to the box (BOX's bottom) is the lower marquee
BOX = (1.85, 0.25, 0.78, 2.72, 0.04)   # the display box: half-width, corner chamfer, bottom, top, edge chamfer
SCREEN = (3.10, 1.744, 0.04)           # each face's display: width, height (16:9), recess
# The fuselage and the upper marquee ring, bottom up: the ring's underside over the box, its lower lip, a chamfer
# into the band, the band, the upper lip, its roof, the drum (where the arms root) and its shoulder to the flat top.
HUB = [(2.50, 2.70), (2.55, 2.75), (2.55, 2.86), (2.48, 2.90), (2.48, 3.36), (2.55, 3.40), (2.55, 3.46), (1.55, 3.60),
       (1.55, 4.02), (1.30, 4.22)]
HUB_BAND = 3                           # the band from HUB[3] to HUB[4] is the upper marquee
DRUM = (1.55, 3.60, 4.02)              # the drum: corner radius, bottom, top
VENTS = (3.68, 3.94, 0.045, 0.035, 0.02)  # slanted vents on the drum between the arms: bottom, top, width, lean, depth
BEACON = (0.14, 0.09)                  # the beacon on top: bezel and lens radius
DUCT_C = 3.40                          # the ducts' centres at (+-DUCT_C, +-DUCT_C)
# A duct's section (radius from its centre, z), round: the bore, the inlet lip, the outer wall, the bottom.
DUCT = [(1.45, 2.95), (1.45, 3.60), (1.53, 3.72), (1.60, 3.64), (1.60, 2.95)]
# The arms, from inside the drum out to the pod at the duct's centre: (distance from the axis, width, height, z).
ARM = [(1.20, 0.62, 0.42, 3.80), (2.90, 0.46, 0.32, 3.76), (DUCT_C * math.sqrt(2), 0.34, 0.24, 3.74)]
SPOKE = (0.16, 3.64, 3.80, 0.28, 1.57, 3.665)  # the pod's two other spokes: width, bottom, top, from, to, end top z
POD = [(0.18, 3.98), (0.34, 3.88), (0.34, 3.50), (0.28, 3.46)]  # the motor pod (radius, z), top down
MOTOR = (0.27, 3.28, 3.47)             # the motor can under it: radius, bottom, top (sunk into the pod)
PAD = (0.34, 2.88, 1.525)              # the corner spots' pads under the ducts: side, bottom z, distance out
SHAFT = (0.05, 3.20, 3.30)             # each rotor's shaft: radius, bottom, top (in the can)
SPINNER = [(0.20, 3.23), (0.20, 3.07), (0.08, 3.00)]  # the rotor's spinner (radius, z), top down
BLADES = 5
BLADE = [(0.15, 0.16, 0.035, 28.0), (1.38, 0.26, 0.02, 12.0)]  # root and tip: radius, chord, thickness, pitch
BLADE_Z = 3.14
SPOT_R = 1.55                          # the belly spots' circle
# A spotlight, from the flat it hangs from (z down from it): the pan motor (radius, sunk, bottom), the rotor boss
# (radius, top, bottom), the yoke (half-width outside and inside, top, bar's underside, arms' ends, depth), the
# tilt centre, and the head's section (along the beam from the tilt centre, radius at the corners).
SPOT_BASE = (0.16, 0.01, 0.12)
SPOT_BOSS = (0.125, 0.115, 0.18)
YOKE = (0.375, 0.3125, 0.17, 0.235, 0.80, 0.20)
SPOT_C = 0.70
TILT_MOTOR = (0.37, 0.45, 0.08)        # on the +axis arm: from, to (along the tilt axis), radius
AXLE = (0.35, 0.0375)                  # the head's axle: half-length, radius
HEAD = [(-0.30, 0.1875), (0.20, 0.25), (0.306, 0.281)]  # a tapered can, the last band its bezel, then the lens
PAN, TILT = 270.0, 80.0                # the spots' ranges (degrees either way)
SPIN = 30.0                            # rotor speed hovering, degrees per frame (150 rpm at 30 fps)
HOVER_LOOP = 60                        # hover: frames per loop (5 turns)
SPIN_RAMP = 96                         # spin_up / spin_down: frames (4 turns each)
AIM = 45                               # lights_on / lights_off: frames
SHOW = (240, 3.5, 2.5)                 # show: frames per loop, the aim's figure of eight (across, along), metres
PREVIEW_FRAME = {"lo": [-5.05, -5.05, -1.15], "hi": [5.05, 5.05, 4.35]}
# === END SPEC ===

# The cull's level surface, far above and facing down: the rig floats, so nothing of it is hidden by a surface.
PLATFORM_FRAME = Matrix.Translation((0, 0, 50.0)) @ Matrix.Rotation(math.pi, 4, "X")
GROUPS = ()
AZ_NAMES = {0: "Left", 45: "BackLeft", 90: "Back", 135: "BackRight", 180: "Right", 225: "FrontRight", 270: "Front",
            315: "FrontLeft"}
DIAGONALS = (45, 135, 225, 315)
# Rotor spin (+ counter-clockwise from above): the diagonal pairs turn the same way, so their torques cancel.
ROTOR_SPIN = {45: -1, 135: 1, 225: -1, 315: 1}


def hatch(a, b, n):  # the pistons' coordinates are world coordinates here (there are none)
    return Vector((a, b, n))


def radial_dir(az):
    a = math.radians(az)
    return Vector((math.cos(a), math.sin(a), 0.0))


def duct_centre(az):
    d = radial_dir(az)
    return Vector((math.copysign(DUCT_C, d.x), math.copysign(DUCT_C, d.y), 0.0))


@dataclass
class Spot:
    """A moving-head spotlight: hangs from the flat at `mount`, its head swinging out along `out` at + tilt."""
    name: str
    mount: Vector
    out: Vector

    @property
    def axis(self):            # the tilt axis: + tilt swings the beam out
        return -UP_V.cross(self.out)

    @property
    def pan_pivot(self):
        return self.mount - Vector((0, 0, SPOT_BASE[2]))

    @property
    def centre(self):          # the tilt centre, on the pan axis: the beam passes through it
        return self.mount - Vector((0, 0, SPOT_C))

    @property
    def tilt_pivot(self):      # the tilt joint's pivot, in its motor on the yoke's arm
        return self.centre + self.axis * (TILT_MOTOR[0] + TILT_MOTOR[1]) / 2

    @property
    def pan(self):
        return f"{self.name}Pan"

    @property
    def tilt(self):
        return f"{self.name}Tilt"

    @property
    def gizmo(self):
        return f"{self.name}Beam"


UP_V = Vector(UP)
SPOTS = ([Spot(f"Spot{AZ_NAMES[az]}", radial_dir(az) * SPOT_R, radial_dir(az)) for az in range(0, 360, 45)] +
         [Spot(f"SpotDuct{AZ_NAMES[az]}", duct_centre(az) + radial_dir(az) * PAD[2] + Vector((0, 0, PAD[1])), radial_dir(az))
          for az in DIAGONALS])
ROTORS = [(f"Rotor{AZ_NAMES[az]}", az) for az in DIAGONALS]


def beam(spot, pan, tilt):
    """The spot's beam direction at (pan, tilt) degrees."""
    out = Matrix.Rotation(math.radians(pan), 3, "Z") @ spot.out
    t = math.radians(tilt)
    return Vector((0, 0, -math.cos(t))) + out * math.sin(t)


def aim(spot, target, near=None):
    """(pan, tilt) pointing the spot's beam at a floor point: the solution nearest `near` (a previous pose,
    for continuous motion), or the one with the least pan."""
    d = Vector(target) - spot.centre
    tilt = math.degrees(math.atan2(d.xy.length, -d.z))
    pan = math.degrees(math.atan2(d.y, d.x) - math.atan2(spot.out.y, spot.out.x))
    pan = (pan + 180.0) % 360.0 - 180.0
    options = [(pan + k * 360.0, tilt) for k in (-1, 0, 1)] + [(pan + 180.0 + k * 360.0, -tilt) for k in (-2, -1, 0)]
    options = [o for o in options if abs(o[0]) <= PAN + 1e-9]
    if near is None:
        return min(options, key=lambda o: abs(o[0]))
    return min(options, key=lambda o: (o[0] - near[0]) ** 2 + (o[1] - near[1]) ** 2)


def zones():
    """The map's zones: (name, centre, corners) on the floor, HOVER under the belly."""
    nx, ny = ZONES
    wx, wy = ARENA[0] / nx, ARENA[1] / ny
    out = []
    for iy in range(ny):
        for ix in range(nx):
            x0, y0 = -ARENA[0] / 2 + ix * wx, -ARENA[1] / 2 + iy * wy
            corners = [Vector((x, y, -HOVER)) for x, y in ((x0, y0), (x0 + wx, y0), (x0 + wx, y0 + wy), (x0, y0 + wy))]
            out.append((f"x{ix}y{iy}", sum(corners, Vector()) / 4, corners))
    return out


def assign(cost):
    """The assignment of rows to columns with the least total cost (Kuhn-Munkres): res[row] = column."""
    n, inf = len(cost), float("inf")
    u, v, p, way = [0.0] * (n + 1), [0.0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [inf] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], inf, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    res = [0] * n
    for j in range(1, n + 1):
        res[p[j] - 1] = j - 1
    return res


def plan_lighting():
    """Each spot's zone (the exact assignment with the least total squared tilt), its flood aim at the zone's
    middle, and the cone (half-angle, range) that takes in the zone's corners."""
    zs = zones()
    if len(zs) != len(SPOTS):
        raise SystemExit(f"[{NAME}] {len(SPOTS)} spots for {len(zs)} zones")
    cost = [[aim(s, c)[1] ** 2 for _, c, _ in zs] for s in SPOTS]
    plan = {}
    for s, zi in zip(SPOTS, assign(cost)):
        zname, c, corners = zs[zi]
        pan, tilt = aim(s, c)
        axis = (c - s.centre).normalized()
        half = max(math.degrees(axis.angle((q - s.centre).normalized())) for q in corners) + CONE_MARGIN
        reach = max((q - s.centre).length for q in corners)
        plan[s.name] = {"zone": zname, "target": c, "corners": corners, "pan": pan, "tilt": tilt,
                        "half_angle": half, "range": reach * 1.15}
    return plan


LIGHTING = plan_lighting()


def show_path(i, f):
    """Spot i's aim point on frame f of show: a figure of eight through its zone's middle (so the loop starts and
    ends on flood), mirrored on alternate spots."""
    n, ax, ay = SHOW
    t = 2 * math.pi * f / n
    s = 1 if i % 2 == 0 else -1
    return LIGHTING[SPOTS[i].name]["target"] + Vector((s * ax * math.sin(t), ay * math.sin(2 * t), 0))


def joint_specs():
    specs = [("Root", None, "fixed", (0, 0, 0), UP, UP, None)]
    for name, az in ROTORS:  # the rotors about their motor's axis, the pivot at the can's underside
        c = duct_centre(az)
        specs.append((name, "Root", "hinge", (c.x, c.y, MOTOR[1]), UP, radial_dir(az), None))
    for s in SPOTS:  # pan about the vertical (+ counter-clockwise from above), tilt about the yoke's arms (+ out)
        specs.append((s.pan, "Root", "hinge", s.pan_pivot, UP, s.out, (-PAN, PAN)))
        specs.append((s.tilt, s.pan, "hinge", s.tilt_pivot, s.axis, DOWN, (-TILT, TILT)))
    return specs


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space.
JOINT_SPECS = joint_specs()
PISTON_SPECS = []                      # direct drives: the rotors on their motors, the spots on their pan and tilt motors
PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015
SLOT_GAP = 0.00125


def rotor_keys(frames, angle):
    """Every rotor keyed on every frame: `angle(f)` degrees, each in its own sense."""
    return {name: [(f, ROTOR_SPIN[az] * angle(f)) for f in range(frames + 1)] for name, az in ROTORS}


def spot_keys(frames, pose):
    """Every spot keyed on every frame: `pose(i, f)` -> (pan, tilt)."""
    keys = {}
    for i, s in enumerate(SPOTS):
        poses = [pose(i, f) for f in range(frames + 1)]
        keys[s.pan] = [(f, p) for f, (p, _) in enumerate(poses)]
        keys[s.tilt] = [(f, t) for f, (_, t) in enumerate(poses)]
    return keys


def flood(i):
    plan = LIGHTING[SPOTS[i].name]
    return plan["pan"], plan["tilt"]


def ease(f, n):
    return (1 - math.cos(math.pi * f / n)) / 2


def show_keys():
    """The show loop's aims, every frame, each spot's solution continuing from the one before."""
    n = SHOW[0]
    keys = {}
    for i, s in enumerate(SPOTS):
        poses = [flood(i)]
        for f in range(1, n + 1):
            poses.append(aim(s, show_path(i, f), near=poses[-1]))
        keys[s.pan] = [(f, p) for f, (p, _) in enumerate(poses)]
        keys[s.tilt] = [(f, t) for f, (_, t) in enumerate(poses)]
    return keys


# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}. Every motion keys every
# frame (the spins end on whole turns); the rotors and the spots are keyed in separate actions, so they layer.
ANIMATIONS = {
    "hover": (True, "LINEAR", rotor_keys(HOVER_LOOP, lambda f: SPIN * f)),
    "spin_up": (False, "LINEAR", rotor_keys(SPIN_RAMP, lambda f: SPIN * f * f / (2 * SPIN_RAMP))),
    "spin_down": (False, "LINEAR", rotor_keys(SPIN_RAMP, lambda f: SPIN * (f - f * f / (2 * SPIN_RAMP)))),
    "lights_on": (False, "LINEAR", spot_keys(AIM, lambda i, f: tuple(v * ease(f, AIM) for v in flood(i)))),
    "flood": (False, "LINEAR", spot_keys(1, lambda i, f: flood(i))),
    "show": (True, "LINEAR", show_keys()),
    "lights_off": (False, "LINEAR", spot_keys(AIM, lambda i, f: tuple(v * (1 - ease(f, AIM)) for v in flood(i)))),
}
PREVIEW_STATES = {
    "flood": {j: v for i in range(len(SPOTS)) for j, v in zip((SPOTS[i].pan, SPOTS[i].tilt), flood(i))},
    "show": {j: ks[SHOW[0] // 8][1] for j, ks in ANIMATIONS["show"][2].items()},
    "reach": {**{s.pan: 45.0 for s in SPOTS}, **{s.tilt: TILT for s in SPOTS}, **{n: 36.0 for n, _ in ROTORS}},
}
PREVIEW_VIEWS = {"flood": ["front_left", "front", "bottom"], "show": ["front_left", "rear_right"],
                 "reach": ["front_left", "right"]}
FK_TEST_STATE = {"RotorFrontLeft": 33.0, "SpotLeftPan": 40.0, "SpotLeftTilt": -30.0, "SpotDuctFrontLeftPan": -70.0,
                 "SpotDuctFrontLeftTilt": 55.0}
SHOWCASE = ["lights_on", "show", "lights_off"]   # animate.py plays these in order...
SHOWCASE_UNDER = ["hover"]                       # ...over this loop, repeated the whole way

# slot: (base colour, metallic, roughness, emission strength). Map-generic, in Tensor's materials.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): drum, arms, pods, box, heads
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): the rings, the duct walls, blades
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black: yokes, bezels, the bores, every cut
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: shafts, spinners, rotor bosses, axles
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # the beacon
    "M_Titanium": ((0.29, 0.29, 0.30), 1.0, 0.45, 0.0),   # matte titanium: motor cans, pan and tilt motors
    "M_Lamp": ((1.0, 0.95, 0.85), 0.0, 0.3, 8.0),          # the spots' lenses: warm white
    "M_Screen": ((1.0, 1.0, 1.0), 0.0, 0.4, 2.5),          # the displays: split off into their own mesh
    "M_Marquee": ((1.0, 1.0, 1.0), 0.0, 0.4, 2.5),         # the marquee bands: split off into their own mesh
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, TI, LMP, SCR, MRQ = SLOTS

# The framework below (kinematics, pistons, mesh kit, checks, rig, actions, export) is the
# item table's and weapon holder's generic code, unchanged.


# --------------------------------------------------------------------------------------------
# Resolved joints and forward kinematics
# --------------------------------------------------------------------------------------------

def mirror_name(name):
    """The other side's bone name."""
    for mine, other in (SIDES, SIDES[::-1]):
        if name.startswith(mine):
            return other + name[len(mine):]
    return name


def mirror_vec(v):
    return Vector((-v[0], v[1], v[2]))


@dataclass
class Joint:
    name: str
    parent: str | None
    kind: str
    pivot: Vector
    axis: Vector
    dir: Vector
    limits: tuple | None

    def local(self, value):
        """Transform of this joint's value, about its rest pivot / along its rest axis."""
        if self.kind == "hinge":
            r = Matrix.Rotation(math.radians(value), 4, self.axis)
            return Matrix.Translation(self.pivot) @ r @ Matrix.Translation(-self.pivot)
        if self.kind == "slide":
            return Matrix.Translation(self.axis * value)
        return Matrix.Identity(4)


def resolve_joints():
    joints = {}
    for name, parent, kind, pivot, axis, d, limits in JOINT_SPECS:
        axis = Vector(axis).normalized()
        d = axis.copy() if kind == "slide" else Vector(d).normalized()
        if kind == "hinge" and abs(d.dot(axis)) > 1e-6:
            raise SystemExit(f"[{NAME}] {name}: bone direction must be square to the hinge axis")
        joints[name] = Joint(name, parent, kind, Vector(pivot), axis, d, limits)
    return joints


def descendants(joints, root):
    out = {root}
    for j in joints.values():  # parents are listed before children
        if j.parent in out:
            out.add(j.name)
    return out


def fk(joints, state):
    """World transform of every joint's rigid body for a state {joint: value}."""
    m = {}
    for j in joints.values():
        base = m[j.parent] if j.parent else Matrix.Identity(4)
        m[j.name] = base @ j.local(state.get(j.name, 0.0))
    return m


# --------------------------------------------------------------------------------------------
# Pistons
# --------------------------------------------------------------------------------------------

@dataclass
class PistonDef:
    """A piston across one hinge: barrel on the parent (end A), rod on the child (end B). With
    `stages`, a telescope: that many nested stage tubes between barrel and rod, each extending an
    equal share of the stroke."""
    name: str
    cyl_parent: str
    a: Vector
    rod_parent: str
    b: Vector
    radius: float
    stroke: tuple = (0.0, 0.0)
    cyl_len: float = 0.0
    rod_len: float = 0.0
    overlap: float = 0.0
    stages: int = 0          # telescopic stages between barrel and rod
    rest: float = 0.0        # A-B distance at rest
    STAGGER = 0.01           # (telescopes) each tube's base sits this much further out, collapsed
    STEP = 0.15              # (telescopes) each tube is this fraction of the barrel radius thinner

    @property
    def stage_names(self):
        return [f"{self.name}Stage{i + 1}" for i in range(self.stages)]

    def shift(self, i, d):
        """(Telescopes) how far tube i (0 = barrel, stages + 1 = rod) has its base out from the
        barrel's, at A-B distance d."""
        return i * self.STAGGER + i * (d - self.stroke[0]) / (self.stages + 1)

    @property
    def cylinder(self):
        return f"{self.name}Cylinder"

    @property
    def rod(self):
        return f"{self.name}Rod"

    @property
    def anchor_a(self):
        return f"{self.name}AnchorA"

    @property
    def anchor_b(self):
        return f"{self.name}AnchorB"


def resolve_pistons(joints):
    """Sweep the hinge each piston spans through its limits to size barrel and rod."""
    pistons = []
    for spec in PISTON_SPECS:
        name, cyl_parent, a, rod_parent, b, radius = spec[:6]
        stages = spec[6] if len(spec) > 6 else 0
        a, b = hatch(*a), hatch(*b)
        joint = joints[rod_parent]
        if joint.parent != cyl_parent or joint.kind != "hinge":
            raise SystemExit(f"[{NAME}] {name}: must span a single hinge")
        lo, hi = joint.limits
        dists = [((joint.local(lo + (hi - lo) * i / 60)) @ b - a).length for i in range(61)]
        dmin, dmax = min(dists), max(dists)
        if stages:  # every tube as long as fits between the eyes collapsed; each joint's overlap at full reach
            cyl_len = rod_len = dmin - 1.4 * radius * 1.15 - (stages + 1) * PistonDef.STAGGER
            overlap = cyl_len - PistonDef.STAGGER - (dmax - dmin) / (stages + 1)
        else:
            cyl_len = rod_len = 0.85 * dmin
            overlap = cyl_len + rod_len - dmax
        if overlap < PISTON_MIN_OVERLAP:
            raise SystemExit(f"[{NAME}] {name}: stroke too long for its mounts; move A/B" +
                             (" or add stages" if stages else ""))
        pistons.append(PistonDef(name, cyl_parent, a, rod_parent, b, radius, (dmin, dmax), cyl_len, rod_len, overlap,
                                 stages, (b - a).length))
    return pistons


# --------------------------------------------------------------------------------------------
# Mesh kit: rigid parts accumulated into one bmesh, each weighted 1.0 to one bone
# --------------------------------------------------------------------------------------------

@dataclass
class Solid:
    """Collision volume of a box or cylinder part, for piston clearance."""
    bone: str
    kind: str
    center: Vector
    rot: Matrix
    half: Vector

    def contains(self, center, rot, p, margin):
        q = rot.transposed() @ (p - center)
        if self.kind == "box":
            return all(abs(q[i]) < self.half[i] + margin for i in range(3))
        return abs(q.z) < self.half.z + margin and q.x * q.x + q.y * q.y < (self.half.x + margin) ** 2


def build_line():
    f = sys._getframe(1)
    while f:
        if f.f_code.co_name.startswith("build_"):
            return f.f_lineno
        f = f.f_back
    return 0


class Part:
    """Exact geometry of one rigid part, for connectivity, alignment and clearance checks."""

    def __init__(self, bone, line, verts, faces, convex, solid=True, exact=False, closed=True):
        self.bone, self.line, self.verts, self.faces, self.convex = bone, line, verts, faces, convex
        self.solid, self.exact, self.closed = solid, exact, closed
        self.bvh = BVHTree.FromPolygons(verts, faces)
        self.lo = Vector(min(v[i] for v in verts) for i in range(3))
        self.hi = Vector(max(v[i] for v in verts) for i in range(3))
        if min(self.hi[i] - self.lo[i] for i in range(3)) < 1e-4:
            raise ValueError(f"degenerate (zero-thickness) part on {bone} at line {line}")
        c = sum(verts, Vector()) / len(verts)
        self.planes = []
        for f in faces:
            a, b, d = (verts[i] for i in f[:3])
            n = (b - a).cross(d - a)
            if n.length > 1e-12:
                n.normalize()
                self.planes.append((n if n.dot(a - c) > 0 else -n, a))

    def moved(self, m):
        return Part(self.bone, self.line, [m @ v for v in self.verts], self.faces, self.convex,
                    self.solid, self.exact, self.closed)

    def hits(self, p, margin):
        """Exact test: is point p inside this part or within `margin` of its surface?"""
        if any(p[i] < self.lo[i] - margin or p[i] > self.hi[i] + margin for i in range(3)):
            return False
        dist = self.bvh.find_nearest(p)[3]
        if dist is not None and dist < margin:
            return True
        if not self.closed:
            return False
        crossings, origin, ray = 0, p.copy(), Vector((0.0123, 0.0071, 1.0)).normalized()
        while crossings < 64:
            hit = self.bvh.ray_cast(origin, ray)[0]
            if hit is None:
                break
            crossings += 1
            origin = hit + ray * 1e-5
        return crossings % 2 == 1

    def inside(self, p, tol=0.0):
        return self.convex and all(n.dot(p - a) <= tol for n, a in self.planes)

    def buried(self, p):
        if not self.closed or any(p[i] <= self.lo[i] or p[i] >= self.hi[i] for i in range(3)):
            return False
        if self.convex:
            return all(n.dot(p - a) < 0 for n, a in self.planes)
        for ray in (Vector((0.0123, 0.0071, 1.0)).normalized(), Vector((0.61, -0.37, -0.7)).normalized()):
            crossings, origin = 0, p.copy()
            while crossings < 64:
                hit = self.bvh.ray_cast(origin, ray)[0]
                if hit is None:
                    break
                crossings += 1
                origin = hit + ray * 1e-5
            if crossings % 2 == 0:
                return False
        return True

    def touches(self, other, tol=0.0015):
        if any(self.lo[i] > other.hi[i] + tol or other.lo[i] > self.hi[i] + tol for i in range(3)):
            return False
        if self.bvh.overlap(other.bvh):
            return True
        for a, b in ((self, other), (other, self)):
            for v in a.verts:
                dist = b.bvh.find_nearest(v)[3]
                if (dist is not None and dist <= tol) or b.inside(v):
                    return True
        return False


class Kit:
    def __init__(self, detail=1.0):
        self.bm = bmesh.new()
        self.deform = self.bm.verts.layers.deform.verify()
        self.groups = []
        self.solids = []
        self.tubes = []
        self.parts = []         # left-side and centre parts
        self.mirror_parts = []  # the mirrored copies of Left* parts, on their Right* bones
        self.axes = []          # (bone, mid, axis, half length) of every cylinder
        self.bearings = []      # (bone, mid, axis, half length, inscribed radius) of true cylinders
        self.detail = detail
        self.xf = Matrix.Identity(4)  # local -> world for the parts being built (see frame())
        self.inward = self.bm.faces.layers.int.new("inward")  # open shells: n = which centre they face
        self.shell_centres = []

    @contextmanager
    def frame(self, m):
        """Build the enclosed parts in a local frame (hatch coordinates, a door's open offset)."""
        old = self.xf
        self.xf = old @ m
        try:
            yield
        finally:
            self.xf = old

    def segs(self, n, r=None):
        floor = 4 if r is not None and r < 0.01 and self.detail <= 1 else 6
        return max(floor, round(n * self.detail))

    def emit(self, tmp, bone, mat, mirror, convex=True, solid=True, exact=False, closed=True):
        for v in tmp.verts:
            v.co = self.xf @ v.co
        tmp.verts.index_update()
        faces = [[v.index for v in f.verts] for f in tmp.faces]
        line = build_line()
        self.parts.append(Part(bone, line, [v.co.copy() for v in tmp.verts], faces, convex, solid, exact, closed))
        made = []
        if mirror:
            copy = Part(mirror_name(bone), line, [mirror_vec(v.co) for v in tmp.verts],
                        [f[::-1] for f in faces], convex, solid, exact)
            (self.mirror_parts if bone.startswith("Left") else self.parts).append(copy)
        for flip in ((False, True) if mirror else (False,)):
            name = mirror_name(bone) if flip else bone
            if name not in self.groups:
                self.groups.append(name)
            group, mat_index = self.groups.index(name), SLOTS.index(mat)
            vmap = {}
            for v in tmp.verts:
                nv = self.bm.verts.new(mirror_vec(v.co) if flip else v.co.copy())
                nv[self.deform][group] = 1.0
                vmap[v] = nv
            for f in tmp.faces:
                verts = [vmap[v] for v in f.verts]
                if flip:
                    verts.reverse()
                face = self.bm.faces.new(verts)
                face.material_index = mat_index
                made.append(face)
        tmp.free()
        return made

    def obox(self, p0, p1, w, h, up, bone, mat, bevel=0.0, mirror=False, solid=True):
        """Straight box from p0 to p1; `h` along `up`, `w` across."""
        p0, p1 = Vector(p0), Vector(p1)
        length = (p1 - p0).length
        L = (p1 - p0) / length
        U = Vector(up)
        if abs(U.normalized().dot(L)) > 0.99:
            raise ValueError(f"obox 'up' {tuple(up)} is parallel to its length (line {build_line()})")
        U = (U - L * U.dot(L)).normalized()
        W = U.cross(L)
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            v.co = Vector((v.co.x * w, v.co.y * h, v.co.z * length))
        if bevel > 0 and (self.detail > 1 or min(w, h, length) >= 0.02):
            b = min(bevel, 0.4 * min(w, h, length))
            bmesh.ops.bevel(tmp, geom=tmp.verts[:] + tmp.edges[:], offset=b, offset_type="OFFSET",
                            segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
        rot, center = Matrix((W, U, L)).transposed(), (p0 + p1) / 2
        for v in tmp.verts:
            v.co = rot @ v.co + center
        if solid:
            self.solids.append(Solid(bone, "box", self.xf @ center, self.xf.to_3x3() @ rot,
                                     Vector((w / 2, h / 2, length / 2))))
        self.emit(tmp, bone, mat, mirror, solid=solid)

    def box(self, center, size, bone, mat, **kw):
        c, hz = Vector(center), Vector((0, 0, size[2] / 2))
        self.obox(c - hz, c + hz, size[0], size[1], BACK, bone, mat, **kw)

    def span(self, lo, hi, bone, mat, **kw):
        """Axis-aligned box between two corners."""
        lo, hi = Vector(lo), Vector(hi)
        self.box((lo + hi) / 2, hi - lo, bone, mat, **kw)

    def cyl(self, p0, p1, r, bone, mat, segs=8, r1=None, mirror=False, solid=True):
        p0, p1 = Vector(p0), Vector(p1)
        tmp = bmesh.new()
        n = self.segs(segs, max(r, r1 or r))
        bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=False, segments=n,
                              radius1=r, radius2=r if r1 is None else r1, depth=(p1 - p0).length)
        rot, mid = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix(), (p0 + p1) / 2
        for v in tmp.verts:
            v.co = rot @ v.co + mid
        wmid, wax = self.xf @ mid, (self.xf.to_3x3() @ (p1 - p0)).normalized()
        half = (p1 - p0).length / 2
        if solid:
            rmax = max(r, r if r1 is None else r1)
            self.solids.append(Solid(bone, "cyl", wmid, self.xf.to_3x3() @ rot, Vector((rmax, rmax, half))))
        self.axes.append((bone, wmid, wax, half))
        if mirror:
            self.axes.append((mirror_name(bone), mirror_vec(wmid), mirror_vec(wax), half))
        if r1 is None:
            self.bearings.append((bone, wmid, wax, half, r * math.cos(math.pi / n)))
            if mirror and not bone.startswith("Left"):
                self.bearings.append((bone, mirror_vec(wmid), mirror_vec(wax), half, r * math.cos(math.pi / n)))
        self.emit(tmp, bone, mat, mirror, solid=solid)

    def shell(self, lo, hi, bone, mat):
        """Open box between two corners, its top (+z) face left off: one quad per side, facing in
        (a pit's walls and floor, seen only from inside). It has no inside for the checks."""
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        lo, hi = Vector(lo), Vector(hi)
        for v in tmp.verts:
            v.co = Vector(lo[i] if v.co[i] < 0 else hi[i] for i in range(3))
        tmp.normal_update()
        bmesh.ops.delete(tmp, geom=[f for f in tmp.faces if f.normal.z > 0.5], context="FACES_ONLY")
        self.shell_centres.append(self.xf @ ((lo + hi) / 2))
        for f in self.emit(tmp, bone, mat, False, convex=False, solid=False, closed=False):
            f[self.inward] = len(self.shell_centres)

    def prism(self, points, thickness, normal, bone, mat, mirror=False, convex=True):
        n = Vector(normal).normalized() * (thickness / 2)
        tmp = bmesh.new()
        bot = [tmp.verts.new(Vector(p) - n) for p in points]
        top = [tmp.verts.new(Vector(p) + n) for p in points]
        tmp.faces.new(top)
        tmp.faces.new(bot[::-1])
        for i in range(len(points)):
            j = (i + 1) % len(points)
            tmp.faces.new((bot[i], bot[j], top[j], top[i]))
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])
        self.emit(tmp, bone, mat, mirror, convex=convex, exact=True)

    def plate(self, outline, thickness, normal, bone, mat, holes=(), cuts=(), boxes=(), intersect=(),
              subtract=(), mirror=False):
        """Flat plate with exact boolean cuts. `holes`: polygons cut straight through; `cuts`: (p0, p1,
        r[, sides]) cylinders; `boxes`: (center, size) blocks for pockets and grooves; `intersect`:
        (points, normal, thickness) profiles the plate is intersected with first (a solid carved from
        two views); `subtract`: (points, normal, thickness) profiles cut away (inclined pockets, slots)."""
        n0 = Vector(normal).normalized()

        def temp(bm, name):
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            bm.free()
            obj = bpy.data.objects.new(name, mesh)
            bpy.context.scene.collection.objects.link(obj)
            return obj

        def slab(points, th, nrm=None):
            n = n0 if nrm is None else Vector(nrm).normalized()
            bm = bmesh.new()
            bot = [bm.verts.new(Vector(q) - n * th / 2) for q in points]
            top = [bm.verts.new(Vector(q) + n * th / 2) for q in points]
            bm.faces.new(top)
            bm.faces.new(bot[::-1])
            for i in range(len(points)):
                j = (i + 1) % len(points)
                bm.faces.new((bot[i], bot[j], top[j], top[i]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            return temp(bm, "_slab")

        def rod(p0, p1, r, segs=16):
            p0, p1 = Vector(p0), Vector(p1)
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=(p1 - p0).length)
            rot = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix()
            for v in bm.verts:
                v.co = rot @ v.co + (p0 + p1) / 2
            return temp(bm, "_rod")

        def block(center, size):
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            for v in bm.verts:
                v.co = Vector(center) + Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
            return temp(bm, "_block")

        base = slab(outline, thickness)
        shapers = [slab(pts, th, nrm) for pts, nrm, th in intersect]
        for shaper in shapers:
            mod = base.modifiers.new("shape", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", shaper
        cutters = ([slab(h, thickness * 3) for h in holes] + [rod(*c) for c in cuts]
                   + [block(*b) for b in boxes] + [slab(pts, th, nrm) for pts, nrm, th in subtract])
        for cutter in cutters:
            mod = base.modifiers.new("cut", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
        tmp = bmesh.new()
        tmp.from_object(base, bpy.context.evaluated_depsgraph_get())
        for obj in (base, *shapers, *cutters):
            mesh = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(mesh)
        convex = not (holes or cuts or boxes or intersect or subtract)
        self.emit(tmp, bone, mat, mirror, convex=convex, exact=True)

    def tube(self, points, r, bone, mat, sides=6, mirror=False, foot_segs=6):
        """Swept line along a polyline (hydraulic lines, looms). Each end sits on a mounting surface,
        its end segment square to it, with a flange foot (a gland) there."""
        pts = [Vector(p) for p in points]
        sides = self.segs(sides)
        tmp = bmesh.new()
        dirs = [(b - a).normalized() for a, b in zip(pts, pts[1:])]
        ref = Vector((0, 0, 1)) if abs(dirs[0].z) < 0.9 else Vector((1, 0, 0))
        normals = [(ref - dirs[0] * ref.dot(dirs[0])).normalized()]
        for d0, d1 in zip(dirs, dirs[1:]):
            normals.append(d0.rotation_difference(d1) @ normals[-1])
        rings = []
        for i, p in enumerate(pts):
            d_in, n = (dirs[i - 1], normals[i - 1]) if i > 0 else (dirs[0], normals[0])
            b = d_in.cross(n)
            offsets = [(n * math.cos(a) + b * math.sin(a)) * r for a in (2 * math.pi * j / sides for j in range(sides))]
            if 0 < i < len(pts) - 1:  # true mitre on the bisector plane
                t = (dirs[i - 1] + dirs[i]).normalized()
                offsets = [o - d_in * (o.dot(t) / d_in.dot(t)) for o in offsets]
            rings.append([tmp.verts.new(p + o) for o in offsets])
        for r0, r1 in zip(rings, rings[1:]):
            for j in range(sides):
                tmp.faces.new((r0[j], r0[(j + 1) % sides], r1[(j + 1) % sides], r1[j]))
        tmp.faces.new(rings[0][::-1])
        tmp.faces.new(rings[-1])
        self.tubes.append((bone, [self.xf @ q for q in pts], r))
        if mirror and bone.startswith("Left"):
            self.tubes.append((mirror_name(bone), [mirror_vec(self.xf @ q) for q in pts], r))
        self.emit(tmp, bone, mat, mirror, convex=False, solid=False)
        for end, nxt in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            t = (nxt - end).normalized()
            self.cyl(end - t * 0.001, end + t * 0.005, r * 1.9, bone, FRM, segs=foot_segs, mirror=mirror, solid=False)

    def optimise(self, eps=2e-4, joints=()):
        """Lossless triangle reduction, run after the checks (see ../docs/library/MODELLING.md): cull faces that
        lie wholly inside one other part of the same bone (or inside a coaxial true cylinder across a
        single-axis joint), keeping every face that feeds a kept neighbour's smooth normal, then
        dissolve boolean leftovers on flat faces."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        before = sum(len(f.verts) - 2 for f in self.bm.faces)
        by_bone = {}
        for part in self.parts + self.mirror_parts:
            by_bone.setdefault(part.bone, []).append(part)
        coax = {}
        for child, axis, pivot, parent in joints:
            for a, b in ((child, parent), (parent, child)):
                for bone, mid, ax, half, r_in in self.bearings:
                    off = pivot - mid
                    if bone == b and abs(ax.dot(axis)) > 0.9999 and (off - ax * off.dot(ax)).length < 1e-4:
                        coax.setdefault(a, []).append((mid, ax, half, r_in))
        dead = []
        for f in self.bm.faces:
            weights = f.verts[0][self.deform]
            bone = self.groups[next(iter(weights.keys()))]
            parts = by_bone.get(bone)
            if not parts:
                continue
            c = f.calc_center_median()
            ring = [v.co.lerp(c, 0.01) for v in f.verts]
            corners = [q + f.normal * eps for q in ring]
            edges = [a.lerp(b, t) + f.normal * eps for a, b in zip(ring, ring[1:] + ring[:1])
                     for t in (0.2, 0.4, 0.6, 0.8)] + [c + f.normal * eps]
            lo = Vector(min(q[i] for q in corners) for i in range(3))
            hi = Vector(max(q[i] for q in corners) for i in range(3))
            for part in parts:
                if any(lo[i] < part.lo[i] or hi[i] > part.hi[i] for i in range(3)):
                    continue
                if all(part.buried(q) for q in corners) and (part.convex or all(part.buried(q) for q in edges)):
                    dead.append(f)
                    break
            else:
                for mid, ax, half, r_in in coax.get(bone, ()):
                    def within(q):
                        d = q - mid
                        t = d.dot(ax)
                        return abs(t) < half - 1e-5 and (d - ax * t).length < r_in - 1e-5
                    if all(within(q) for q in corners):
                        dead.append(f)
                        break
        dead, changed = set(dead), True
        while changed:
            changed = False
            for f in list(dead):
                if any(g is not f and g not in dead and 0.0087 < f.normal.angle(g.normal, 0.0) < SHARP_ANGLE
                       for e in f.edges for g in e.link_faces):
                    dead.discard(f)
                    changed = True
        dead = list(dead)
        bmesh.ops.delete(self.bm, geom=dead, context="FACES_ONLY")
        bmesh.ops.delete(self.bm, geom=[v for v in self.bm.verts if not v.link_faces], context="VERTS")
        bmesh.ops.dissolve_limit(self.bm, angle_limit=math.radians(0.5), use_dissolve_boundaries=False,
                                 verts=self.bm.verts[:], edges=self.bm.edges[:], delimit={"MATERIAL"})
        after = sum(len(f.verts) - 2 for f in self.bm.faces)
        return len(dead), before, after

    def to_object(self, name, joints=()):
        culled, before, after = self.optimise(joints=joints)
        print(f"[{NAME}] {name}: {before} -> {after} tris ({culled} hidden faces culled)")
        # optimise() wound every closed part outward before culling; recalculating again here would flip
        # open fragments left by the cull (an inlay's top alone), so the winding is kept as it is
        for f in self.bm.faces:  # open shells face their centre
            if f[self.inward] and f.normal.dot(self.shell_centres[f[self.inward] - 1] - f.calc_center_median()) < 0:
                f.normal_flip()
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        self.bm.to_mesh(mesh)
        self.bm.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        for g in self.groups:
            obj.vertex_groups.new(name=g)
        for slot in SLOTS:
            mesh.materials.append(bpy.data.materials[slot])
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.set_sharp_from_angle(angle=SHARP_ANGLE)
        return obj


def ring_xy(cx, cy, r, z, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), z) for i in range(n)]


def rect(ha, hb, n, ca=0.0, cb=0.0, chamfer=0.0):
    """Rectangle (optionally chamfered) in an a-b plane at height n."""
    c = chamfer
    pts = [(ha, hb - c), (ha - c, hb), (-ha + c, hb), (-ha, hb - c), (-ha, -hb + c), (-ha + c, -hb),
           (ha - c, -hb), (ha, -hb + c)] if c else [(ha, hb), (-ha, hb), (-ha, -hb), (ha, -hb)]
    return [(ca + a, cb + b, n) for a, b in pts]


def build_pistons(k, pistons, joints):
    """Barrel and rod each end in an eye on a pin parallel to the driven hinge axis."""
    for p in pistons:
        d = (p.b - p.a).normalized()
        ax = joints[p.rod_parent].axis
        eye = p.radius * 1.15
        k.cyl(p.a - ax * p.radius, p.a + ax * p.radius, eye, p.cylinder, FRM, segs=6, solid=False)
        if p.stages:  # telescope: barrel, stages and rod nested, each tube's base shifted out along A-B
            tubes = [p.cylinder] + p.stage_names + [p.rod]
            for i, bone in enumerate(tubes):
                r, base = p.radius * (1 - i * p.STEP), p.a + d * (eye * 0.7 + p.shift(i, p.rest))
                k.cyl(base, base + d * p.cyl_len, r, bone, SEC if i == 0 else JNT, segs=10 if i == 0 else 8, solid=False)
                if i < len(tubes) - 1:  # gland collar where the next tube comes out, just short of the tube's end
                    k.cyl(base + d * (p.cyl_len - 0.03), base + d * (p.cyl_len - 0.002), r + 0.005, bone, FRM, segs=10,
                          solid=False)
        else:
            k.cyl(p.a + d * eye * 0.7, p.a + d * p.cyl_len, p.radius, p.cylinder, SEC, solid=False)
            k.cyl(p.b - d * eye * 0.7, p.b - d * p.rod_len, p.radius * 0.55, p.rod, JNT, segs=6, solid=False)
        k.cyl(p.b - ax * p.radius, p.b + ax * p.radius, eye * 0.85, p.rod, FRM, segs=6, solid=False)
        for bone, pin in ((p.cyl_parent, p.a), (p.rod_parent, p.b)):
            k.cyl(pin - ax * (p.radius + 0.008), pin + ax * (p.radius + 0.008), 0.005, bone, JNT, segs=6,
                  solid=False)


# --------------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------------

def all_parts(kit):
    return kit.parts + kit.mirror_parts


def check_connectivity(kit, joints, pistons):
    """Every part touches the rest of its own rigid body, and every body touches its parent."""
    parent = {j.name: j.parent for j in joints.values()}
    for p in pistons:
        parent[p.cylinder], parent[p.rod] = p.cyl_parent, p.rod_parent
        for outer, stage in zip([p.cylinder] + p.stage_names, p.stage_names):
            parent[stage] = outer  # each telescope stage rides in the tube outside it
    by_bone = {}
    for part in all_parts(kit):
        by_bone.setdefault(part.bone, []).append(part)
    problems = []
    for bone, parts in by_bone.items():
        root = list(range(len(parts)))

        def find(i):
            while root[i] != i:
                root[i] = root[root[i]]
                i = root[i]
            return i

        for i in range(len(parts)):
            for j in range(i + 1, len(parts)):
                if find(i) != find(j) and parts[i].touches(parts[j]):
                    root[find(i)] = find(j)
        groups = {}
        for i, part in enumerate(parts):
            groups.setdefault(find(i), []).append(part.line)
        if len(groups) > 1:
            main = max(groups.values(), key=len)
            for lines in groups.values():
                if lines is not main:
                    problems.append(f"{bone}: part(s) from line {sorted(set(lines))} float free of the rest")
        anc = parent.get(bone)
        while anc and anc not in by_bone:
            anc = parent.get(anc)
        if anc and not any(a.touches(b) for a in parts for b in by_bone[anc]):
            problems.append(f"{bone}: nothing touches its parent {anc}")
    for bone, pts, r in kit.tubes:  # between its ends a line stands clear of its own body
        length = sum((b - a).length for a, b in zip(pts, pts[1:]))
        run = 0.0
        for a, b in zip(pts, pts[1:]):
            n = max(1, int((b - a).length / 0.005))
            for i in range(n):
                q, at = a.lerp(b, i / n), run + (b - a).length * i / n
                if min(at, length - at) < r + 0.02:
                    continue  # the gland and its fillet
                hit = next((part for part in by_bone.get(bone, []) if part.solid
                            and (part.inside(q) or part.bvh.find_nearest(q)[3] < r * 0.9)), None)
                if hit:
                    problems.append(f"{bone}: line passes into the body (line {hit.line}) at {tuple(round(c, 3) for c in q)}")
                    break
            run += (b - a).length
        for end, nxt in ((pts[0], pts[1]), (pts[-1], pts[-2])):  # each end on a surface, square to it
            t = (nxt - end).normalized()
            best = None
            for q in by_bone.get(bone, []):
                if q.solid:
                    loc, normal, _, dist = q.bvh.find_nearest(end)
                    if dist is not None and (best is None or dist < best[0]):
                        best = (dist, normal)
            if best is None or best[0] > 0.0025:
                problems.append(f"{bone}: line end {tuple(round(c, 3) for c in end)} is not on a mounting surface")
            elif abs(best[1].normalized().dot(t)) < 0.95:
                problems.append(f"{bone}: line end {tuple(round(c, 3) for c in end)} meets its surface at an angle")
    for p in pistons:
        outer = (p.stage_names or [p.cylinder])[-1]
        if not any(a.touches(b) for a in by_bone.get(p.rod, []) for b in by_bone.get(outer, [])):
            problems.append(f"{p.name}: rod is not inside its barrel")
    if problems:
        raise SystemExit(f"[{NAME}] connectivity failed:\n  " + "\n  ".join(problems))


def rotary_joints(joints):
    """(joint, axis, pivot, parent) for every hinge."""
    return [(j.name, j.axis, j.pivot, j.parent) for j in joints.values() if j.kind == "hinge"]


def check_joint_alignment(kit, joints):
    """Hinges: a rotor on the moving body coaxial with the axis and centred on it, and a bearing on
    the parent the axis passes through. Slides: at every point of the travel the moving body still
    bears on its parent's guide (bore on column, tongue in slot)."""
    problems = []
    parts = all_parts(kit)
    for name, axis, pivot, parent in rotary_joints(joints):
        rotor = any(bone == name and abs(ax.dot(axis)) > 0.999
                    and ((pivot - mid) - ax * (pivot - mid).dot(ax)).length < 0.002
                    for bone, mid, ax, half in kit.axes)
        line = [pivot + axis * (0.01 * i) for i in range(-10, 11)]
        bearing = any(part.bone == parent and any(part.inside(q) for q in line) for part in parts)
        if not rotor:
            problems.append(f"{name}: no rotor coaxial with its axis {tuple(round(c, 3) for c in axis)}")
        if not bearing:
            problems.append(f"{name}: its axis passes through no part of {parent}")
    for j in joints.values():
        if j.kind != "slide":
            continue
        moving = [p for p in parts if p.bone == j.name]
        guide = [p for p in parts if p.bone == j.parent]
        lo, hi = j.limits
        for i in range(21):
            v = lo + (hi - lo) * i / 20
            m = j.local(v)
            if not any(p.moved(m).touches(g) for p in moving for g in guide):
                problems.append(f"{j.name}: leaves its guide at {v:.3f} m")
                break
    if problems:
        raise SystemExit(f"[{NAME}] joint alignment failed:\n  " + "\n  ".join(problems))


def check_piston_clearance(pistons, joints, solids, parts):
    """Sweep each piston's hinge: the piston must keep a moment arm about the hinge and never pass
    through a solid or machined part of its parent or of the moving chain."""
    problems = []
    machined = [q for q in parts if q.exact and q.solid]
    for p in pistons:
        joint = joints[p.rod_parent]
        moving = descendants(joints, p.rod_parent)
        lo, hi = joint.limits
        arms = []
        for i in range(31):
            angle = lo + (hi - lo) * i / 30
            m = joint.local(angle)
            rot = m.to_3x3()
            b = m @ p.b
            span = b - p.a
            arms.append(((joint.pivot - p.a).cross(span.normalized())).dot(joint.axis))
            end_skip = (p.radius + 0.02) / span.length
            samples = [p.a + span * (k / 24) for k in range(25) if end_skip < k / 24 < 1 - end_skip]
            for s in solids:
                if s.bone in moving:
                    center, srot = m @ s.center, rot @ s.rot
                elif s.bone == p.cyl_parent:
                    center, srot = s.center, s.rot
                else:
                    continue
                if any(s.contains(center, srot, q, p.radius) for q in samples):
                    problems.append(f"{p.name} at {angle:.0f} deg hits {s.bone} {s.kind} "
                                    f"@ {tuple(round(c, 3) for c in s.center)}")
                    break
            inv = m.inverted()
            for q in machined:
                if q.bone in moving and any(q.hits(inv @ x, p.radius) for x in samples):
                    problems.append(f"{p.name} at {angle:.0f} deg hits {q.bone} (line {q.line})")
                elif q.bone == p.cyl_parent and any(q.hits(x, p.radius) for x in samples):
                    problems.append(f"{p.name} at {angle:.0f} deg hits {q.bone} (line {q.line})")
        if min(arms) * max(arms) <= 0 or min(abs(a) for a in arms) < PISTON_MIN_ARM:
            problems.append(f"{p.name} crosses its hinge axis: moment arm {min(arms):.3f}..{max(arms):.3f} m")
    if problems:
        raise SystemExit(f"[{NAME}] piston clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


def check_motion(kit, joints, states):
    """Place every rigid body for each state (every animation frame, plus sweeps over the joint
    ranges) and fail if a part hits a part of another body it doesn't already touch at rest.
    Piston bones are covered by check_piston_clearance."""
    parts = [p for p in all_parts(kit) if p.bone in joints]
    n = len(parts)

    def overlap_box(a_lo, a_hi, b_lo, b_hi):
        return all(a_lo[i] <= b_hi[i] and b_lo[i] <= a_hi[i] for i in range(3))

    seated = set()
    for i in range(n):
        for j in range(i + 1, n):
            if parts[i].bone != parts[j].bone and overlap_box(parts[i].lo, parts[i].hi, parts[j].lo, parts[j].hi) \
                    and parts[i].touches(parts[j], tol=0.0):
                seated.add((i, j))
    problems = []
    for tag, state in states:
        m = fk(joints, expand(state))
        moved = {}

        def place(i):
            if i not in moved:
                mm = m[parts[i].bone]
                moved[i] = parts[i] if mm == Matrix.Identity(4) else parts[i].moved(mm)
            return moved[i]

        # Cheap bounds first: transform each part's box corners.
        bounds = []
        for p in parts:
            mm = m[p.bone]
            cs = [mm @ Vector((x, y, z)) for x in (p.lo.x, p.hi.x) for y in (p.lo.y, p.hi.y) for z in (p.lo.z, p.hi.z)]
            bounds.append((Vector(min(c[k] for c in cs) for k in range(3)), Vector(max(c[k] for c in cs) for k in range(3))))
        for i in range(n):
            for j in range(i + 1, n):
                a, b = parts[i], parts[j]
                if a.bone == b.bone or (i, j) in seated or m[a.bone] == m[b.bone]:
                    continue
                if not overlap_box(*bounds[i], *bounds[j]):
                    continue
                if place(i).touches(place(j), tol=0.0):
                    problems.append(f"{a.bone} (line {a.line}) hits {b.bone} (line {b.line}) at {tag}")
    if problems:
        raise SystemExit(f"[{NAME}] motion clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


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

    def flat(f, key):
        # One projection per plane (from its rounded normal): a face's own normal can tie between two
        # axes (a 45-degree face) and pick the other one, so two faces far apart would compare in
        # different coordinates and seem to overlap.
        ax = max(range(3), key=lambda i: abs(key[i]))
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
    for key, faces in planes.items():
        for i, a in enumerate(faces):
            for b in faces[i + 1:]:
                if piece[a] != piece[b]:
                    pa, pb = flat(a, key), flat(b, key)
                    if any(inside(t, pb) for t in samples(pa)) or any(inside(t, pa) for t in samples(pb)):
                        c = a.calc_center_median()
                        problems.append(f"coplanar faces at {tuple(round(x, 3) for x in c)} ({obj.material_slots[a.material_index].name}"
                                        f" / {obj.material_slots[b.material_index].name})")
    bm.free()
    if problems:
        raise SystemExit(f"[{NAME}] z-fighting:\n  " + "\n  ".join(dict.fromkeys(problems)))


def check_footprint(kit, lo, hi, levels, frame=Matrix.Identity(4)):
    """A prop set into a cut-out fills it exactly (ground props: square outside corners, for
    placement). In the cut-out's frame (a, b across it, n out of the surface): at rest nothing
    reaches outside its rectangle lo..hi (a, b), and the fixed body has a vertex at each of its four
    corners at every level n listed (the surface and the frame's bottom), so no outside corner is
    chamfered or rounded."""
    inv = frame.inverted()
    problems = []
    fixed = []
    for part in all_parts(kit):
        local = [inv @ v for v in part.verts]
        if any(v[i] < lo[i] - 1e-6 or v[i] > hi[i] + 1e-6 for v in local for i in range(2)):
            problems.append(f"{part.bone} (line {part.line}) reaches outside the cut-out")
        if part.bone == "Root":
            fixed += local
    for n in levels:
        for a in (lo[0], hi[0]):
            for b in (lo[1], hi[1]):
                if not any((v - Vector((a, b, n))).length < 1e-5 for v in fixed):
                    problems.append(f"outside corner ({a:.3f}, {b:.3f}, {n:.3f}) is not square")
    if problems:
        raise SystemExit(f"[{NAME}] footprint failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


def check_states(joints):
    """Every animation key and preview state lies inside the joint limits."""
    problems = []
    named = [(f"{a} f{f}", {j: v}) for a, (_, _, keys) in ANIMATIONS.items() for j, ks in keys.items() for f, v in ks]
    named += list(PREVIEW_STATES.items())
    for tag, state in named:
        for j, v in state.items():
            lim = joints[j].limits
            if lim is not None and not lim[0] - 1e-9 <= v <= lim[1] + 1e-9:
                problems.append(f"{tag}: {j} {v} outside {lim}")
    if problems:
        raise SystemExit(f"[{NAME}] states out of range:\n  " + "\n  ".join(problems))


# --------------------------------------------------------------------------------------------
# Scene, materials, rig, animations
# --------------------------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS


def build_materials():
    for slot, (color, metallic, roughness, emission) in MATERIALS.items():
        mat = bpy.data.materials.new(slot)
        if mat.node_tree is None:
            mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission:
            bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission
        mat.diffuse_color = (*color, 1.0)


def select_only(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def build_rig(joints, pistons):
    arm = bpy.data.armatures.new(f"RIG_{TITLE}")
    rig = bpy.data.objects.new(f"RIG_{TITLE}", arm)
    bpy.context.scene.collection.objects.link(rig)
    select_only([rig])
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones

    def add(name, head, tail, parent, roll_to=None, deform=True):
        e = eb.new(name)
        e.head, e.tail = head, tail
        if roll_to is not None:
            e.align_roll(roll_to)
        e.use_deform = deform
        if parent:
            e.parent = eb[parent]

    for j in joints.values():
        if j.kind == "slide":  # local Y = the slide axis; any roll
            ref = Vector((0, 0, 1)) if abs(j.axis.z) < 0.9 else Vector((1, 0, 0))
            add(j.name, j.pivot, j.pivot + j.dir * 0.1, j.parent, ref - j.axis * ref.dot(j.axis))
        else:  # local X = the hinge axis: Z = axis x Y
            add(j.name, j.pivot, j.pivot + j.dir * 0.1, j.parent, j.axis.cross(j.dir))
    for p in pistons:
        d = (p.b - p.a).normalized()
        add(p.cylinder, p.a, p.a + d * p.cyl_len, p.cyl_parent)
        add(p.rod, p.b, p.b - d * p.rod_len, p.rod_parent)
        for stage in p.stage_names:  # telescope stages ride the barrel's axis
            add(stage, p.a, p.a + d * p.cyl_len, p.cylinder)
        add(p.anchor_a, p.a, p.a + Vector((0, 0, 0.02)), p.cyl_parent, deform=False)
        add(p.anchor_b, p.b, p.b + Vector((0, 0, 0.02)), p.rod_parent, deform=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    constrain(rig, joints, pistons, drive=False)  # stage drivers only after the actions are baked
    return rig


def constrain(rig, joints, pistons, drive=True):
    """Channel locks, joint limits and piston aims on the live rig; with `drive`, drivers that slide
    each telescope stage its share of the A-B distance's change from rest."""
    for j in joints.values():
        pb = rig.pose.bones[j.name]
        pb.rotation_mode = "XYZ"
        if j.kind == "fixed":
            if j.parent:
                pb.lock_location = pb.lock_rotation = (True, True, True)
            continue
        pb.lock_rotation = (j.kind != "hinge", True, True)
        pb.lock_location = tuple(j.kind != "slide" or i != 1 for i in range(3))
        if j.limits is None:
            continue
        c = pb.constraints.new("LIMIT_ROTATION" if j.kind == "hinge" else "LIMIT_LOCATION")
        c.owner_space = "LOCAL"
        lo, hi = j.limits
        if j.kind == "hinge":
            c.use_limit_x, c.min_x, c.max_x = True, math.radians(lo), math.radians(hi)
        else:
            c.use_min_y, c.use_max_y, c.min_y, c.max_y = True, True, lo, hi
    for p in pistons:
        for bone, target in ((p.cylinder, p.anchor_b), (p.rod, p.anchor_a)):
            c = rig.pose.bones[bone].constraints.new("DAMPED_TRACK")
            c.target, c.subtarget, c.track_axis = rig, target, "TRACK_Y"
        for i, stage in enumerate(p.stage_names if drive else [], 1):
            drv = rig.pose.bones[stage].driver_add("location", 1).driver
            drv.type = "SCRIPTED"
            var = drv.variables.new()
            var.name, var.type = "d", "LOC_DIFF"
            for t, bone in zip(var.targets, (p.anchor_a, p.anchor_b)):
                t.id, t.bone_target = rig, bone
            drv.expression = f"(d - {p.rest:.6f}) * {i / (p.stages + 1):.6f}"


def set_joint(rig, joint, value):
    pb = rig.pose.bones[joint.name]
    if joint.kind == "hinge":
        pb.rotation_euler[0] = math.radians(value)
    elif joint.kind == "slide":
        pb.location[1] = value


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)


def check_rig_fk(rig, joints):
    """The live rig must move each body exactly as the checks' kinematics do (axes and signs)."""
    states = [FK_TEST_STATE] + list(PREVIEW_STATES.values())
    worst = 0.0
    for state in states:
        state = expand(state)
        reset_pose(rig)
        for name, v in state.items():
            set_joint(rig, joints[name], v)
        bpy.context.view_layer.update()
        m = fk(joints, state)
        for j in joints.values():
            live = rig.pose.bones[j.name].matrix
            want = m[j.name] @ rig.data.bones[j.name].matrix_local
            worst = max(worst, max(abs(live[r][c] - want[r][c]) for r in range(4) for c in range(4)))
    reset_pose(rig)
    bpy.context.view_layer.update()
    if worst > 1e-4:
        raise SystemExit(f"[{NAME}] rig does not match the joint kinematics (error {worst:.2e})")


def action_fcurves(action):
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    return [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


def bake_pistons(rig, action, pistons):
    """Key each piston bone's constraint-driven rotation on every frame of the action, so the
    exported animation carries the pistons without the aim constraints. Telescope stages are keyed
    along the barrel: each its share of the A-B distance's change from rest."""
    scene = bpy.context.scene
    f0, f1 = (int(v) for v in action.frame_range)
    samples, slides = [], []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        for p in pistons:
            for bone in (p.cylinder, p.rod):
                pb = rig.pose.bones[bone]
                local = rig.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL")
                samples.append((f, pb, local.to_quaternion()))
            dist = (rig.pose.bones[p.anchor_b].head - rig.pose.bones[p.anchor_a].head).length
            for i, stage in enumerate(p.stage_names, 1):
                slides.append((f, rig.pose.bones[stage], (dist - p.rest) * i / (p.stages + 1)))
    for f, pb, q in samples:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = q
        pb.keyframe_insert("rotation_quaternion", frame=f)
    for f, pb, v in slides:
        pb.location[1] = v
        pb.keyframe_insert("location", index=1, frame=f)


def build_actions(rig, joints, pistons):
    """One action per animation, each on its own muted NLA track so every one is exported."""
    rig.animation_data_create()
    actions = {}
    for name, (loop, interp, keys) in ANIMATIONS.items():
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        rig.animation_data.action = action
        for jname, ks in expand(keys).items():
            joint, pb = joints[jname], rig.pose.bones[jname]
            for frame, value in ks:
                set_joint(rig, joint, value)
                if joint.kind == "hinge":
                    pb.keyframe_insert("rotation_euler", index=0, frame=frame)
                else:
                    pb.keyframe_insert("location", index=1, frame=frame)
        for fc in action_fcurves(action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp
            fc.update()
        moving = [p for p in pistons if p.rod_parent in expand(keys)]
        if moving:
            bake_pistons(rig, action, moving)
        action.use_cyclic = loop
        actions[name] = action
        rig.animation_data.action = None
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 0, action)
        track.mute = True
        reset_pose(rig)
    return actions


def action_states(actions, joints):
    """Every frame of every action as a joint state, read back from the real f-curves."""
    by_bone = {j.name: j for j in joints.values()}
    states = []
    for name, action in actions.items():
        curves = []
        for fc in action_fcurves(action):
            bone = fc.data_path.split('"')[1]
            if bone in by_bone:  # joints only; baked piston keys are checked by check_piston_clearance
                curves.append((bone, fc))
        f0, f1 = (int(v) for v in action.frame_range)
        step = 3 if ANIMATIONS[name][0] else 1
        for f in range(f0, f1 + 1, step):
            state = {}
            for bone, fc in curves:
                v = fc.evaluate(f)
                state[bone] = math.degrees(v) if by_bone[bone].kind == "hinge" else v
            states.append((f"{name} frame {f}", state))
    return states


def skin(obj, rig):
    obj.parent = rig
    obj.modifiers.new("Armature", "ARMATURE").object = rig


def unwrap(obj):
    # Final UVs are packed across every exported part, grouped by native
    # material, once geometry and effect-mesh splits are complete.
    pass


def pose_state(rig, joints, pistons, state):
    """Pose the live rig in a joint state: the joints set, the pistons aimed by their constraints and
    each telescope stage slid its share (as the baked actions do)."""
    reset_pose(rig)
    for name, v in expand(state).items():
        set_joint(rig, joints[name], v)
    bpy.context.view_layer.update()
    staged = [p for p in pistons if p.stages]
    for p in staged:
        dist = (rig.pose.bones[p.anchor_b].head - rig.pose.bones[p.anchor_a].head).length
        for i, stage in enumerate(p.stage_names, 1):
            rig.pose.bones[stage].location[1] = (dist - p.rest) * i / (p.stages + 1)
    if staged:
        bpy.context.view_layer.update()


def cull_unseen(obj, rig, joints, pistons, states, lo, hi, frame=Matrix.Identity(4)):
    """Delete the faces no player can ever see. The prop is posed in every state (every animation frame
    and the joint sweeps, so a face uncovered by any motion or combination counts) and, from points
    spread over each face (about every 2 cm, and every 1 cm just inside its edges), rays go out in
    every direction on either side of it, with fans of extra rays close to the frame's axes (a
    narrow slit, such as a moving plate's running gap, is only seen through along them).
    The level's surface round the cut-out (lo..hi in the cut-out's frame, n out of the surface) is in
    the scene. A ray shows the face if it reaches air a viewer can be in, however low: it flies off
    out of the surface (up, for a floor prop), or it lands on the level's surface from the room side
    before meeting the prop. Rays into the ground (or the wall), or onto the surface from behind, show
    nothing. A face no ray ever shows goes, unless it shares a smooth-shaded corner with a face that
    is seen: then it feeds that face's normal and stays, so the shading doesn't change."""
    import numpy as np
    me = obj.data
    polys = [tuple(p.vertices) for p in me.polygons]
    rest = np.array([v.co[:] for v in me.vertices])
    up = (frame.to_3x3() @ Vector((0, 0, 1))).normalized()
    base = frame.translation.copy()
    n_dirs = 320
    sphere = []
    for i in range(n_dirs):  # a Fibonacci sphere
        z = 1 - 2 * (i + 0.5) / n_dirs
        a = i * math.pi * (3 - math.sqrt(5))
        rr = math.sqrt(1 - z * z)
        sphere.append(Vector((rr * math.cos(a), rr * math.sin(a), z)))
    ax = [(frame.to_3x3() @ Vector(v)).normalized() for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]
    for deg in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0):  # and fans round the frame's axes, where the slits are:
        t = math.radians(deg)                         # straight out of the surface and just off it...
        sphere += [up * math.cos(t) + a * math.sin(t) for a in (ax if deg else ax[:1])]
        if deg:                                       # ...and along it, just lifted off
            sphere += [a * math.cos(t) + up * math.sin(t) for a in ax]
    sphere_np = np.array([d[:] for d in sphere])
    sphere_up = sphere_np @ np.array(up[:])
    far = 200.0
    surface = [(-far, hi[1], far, far), (-far, -far, far, lo[1]), (-far, lo[1], lo[0], hi[1]), (hi[0], lo[1], far, hi[1])]
    occ_verts, occ_faces = [], []
    for a0, b0, a1, b1 in surface:  # the level's surface round the cut-out
        k = len(rest) + len(occ_verts)
        occ_verts += [frame @ Vector(p) for p in ((a0, b0, 0), (a1, b0, 0), (a1, b1, 0), (a0, b1, 0))]
        occ_faces.append((k, k + 1, k + 2, k + 3))

    def weights(pts):
        """Sample points over a face as weights on its corners: the centre, each corner and edge middle
        pulled a quarter of the way in, and a grid over each fan triangle about every 2 cm."""
        k = len(pts)
        c = np.full(k, 1.0 / k)
        cen = c @ pts
        rows = [c]
        for i in range(k):
            corner, mid = np.zeros(k), np.zeros(k)
            corner[i] = 1.0
            mid[i] = mid[(i + 1) % k] = 0.5
            rows += [corner * 0.75 + c * 0.25, mid * 0.75 + c * 0.25]
        for i in range(k):
            j = (i + 1) % k
            area = np.linalg.norm(np.cross(pts[i] - cen, pts[j] - cen)) / 2
            n = min(12, int(math.sqrt(area) / 0.02))
            for u in range(n):
                for v in range(n - u):
                    wi, wj = (u + 1 / 3) / n, (v + 1 / 3) / n
                    w = c * (1 - wi - wj)
                    w[i] += wi
                    w[j] += wj
                    rows.append(w)
        for i in range(k):  # and every centimetre along each edge, 0.3 mm in (a slit shows only an edge strip)
            j = (i + 1) % k
            m = min(60, max(1, int(np.linalg.norm(pts[j] - pts[i]) / 0.01)))
            for q in range(m):
                t = (q + 0.5) / m
                e = np.zeros(k)
                e[i], e[j] = 1 - t, t
                gap = np.linalg.norm(cen - e @ pts)
                s = min(0.5, 0.0003 / gap) if gap > 1e-9 else 0.0
                rows.append(e * (1 - s) + c * s)
        return np.array(rows)

    def escapes(bvh, pts, n, n_prop, level=True, hits=None):
        """Does any ray from these points, on either side of normal n (the exported materials are
        double-sided), reach viewer air? Polygons from n_prop on in bvh are the level's surface.
        Without `level` (a body alone), any ray that meets nothing gets out. With `hits` (a set), the
        bodies the rays meet are collected (the level's surface counts as the fixed root)."""
        cos = sphere_np @ n
        for side in (1, -1):
            idx = np.nonzero(cos * side > 0.01)[0]
            off = n * (1e-4 * side)
            for p in pts if len(idx) else ():
                o = Vector(p + off)
                above = (o - base).dot(up) > 0
                for i in idx:
                    loc, _, fi, _ = bvh.ray_cast(o, sphere[i])
                    if loc is None:
                        if not level or sphere_up[i] > 0 or above:
                            return True
                    elif level and fi >= n_prop and sphere_up[i] < 0:
                        return True
                    elif hits is not None:
                        hits.add(root if fi >= n_prop else bone_of[fi])
        return False

    group_names = [g.name for g in obj.vertex_groups]
    bone_of = [group_names[me.vertices[p[0]].groups[0].group] for p in polys]
    static = {j.name for j in joints.values() if j.kind == "fixed" and j.parent is None}
    for j in joints.values():  # fixed joints on a fixed parent never move either
        if j.kind == "fixed" and j.parent in static:
            static.add(j.name)
    rest_n = np.array([p.normal[:] for p in me.polygons])
    root = next(j.name for j in joints.values() if j.parent is None)

    def placement(f, mats):
        """Where the bodies hiding face f sit relative to its own body, and which way the room is from
        it: while this is unchanged, every ray from the face meets the same geometry."""
        inv = mats[bone_of[f]].inverted()
        key = [round(x, 5) for b in sorted(blockers[f] | {bone_of[f]}) for row in (inv @ mats[b])[:3] for x in row]
        return tuple(key + [round(x, 4) for x in inv.to_3x3() @ up])

    samples = [weights(rest[list(p)]) for p in polys]
    pending = set(range(len(polys)))
    sealed = set()
    blockers, tried = {}, {}
    tested = 0
    names = sorted(joints)
    scale = {n: 90.0 if joints[n].kind == "hinge" else max(max(abs(v) for v in joints[n].limits or (1,)), 1e-3)
             for n in names}

    def pose_vec(st):
        e = expand(st)
        return np.array([e.get(n, 0.0) / scale[n] for n in names])

    vecs = [pose_vec(st) for _, st in states]
    order, gap = [], [np.linalg.norm(v) for v in vecs]
    while len(order) < len(vecs):  # the most different pose next: a face that shows at all shows early
        i = max((k for k in range(len(vecs)) if gap[k] >= 0), key=lambda k: gap[k])
        order.append(i)
        gap[i] = -1.0
        for k in range(len(vecs)):
            if gap[k] >= 0:
                gap[k] = min(gap[k], np.linalg.norm(vecs[k] - vecs[i]))
    for step, (tag, state) in enumerate([("rest", {})] + [states[i] for i in order]):
        if step == 1:
            # After the rest pose: a face whose every ray is stopped by its own rigid body alone (plus
            # the level's surface, for the bodies that never move) stays hidden however anything moves,
            # so only the faces hidden by other bodies go on to be tested in every state.
            by_bone = {}
            for f in pending:
                by_bone.setdefault(bone_of[f], []).append(f)
            for bone, faces in by_bone.items():
                own = [polys[i] for i in range(len(polys)) if bone_of[i] == bone]
                fixed = bone in static
                bvh = BVHTree.FromPolygons([Vector(v) for v in rest] + (occ_verts if fixed else []),
                                           own + (occ_faces if fixed else []))
                for f in faces:
                    if not escapes(bvh, samples[f] @ rest[list(polys[f])], rest_n[f], len(own), fixed):
                        sealed.add(f)
            pending -= sealed
            for f in pending:  # the bodies that hide what is left, and the rest placement already tried
                blockers[f] = set()
                escapes(rest_bvh, samples[f] @ rest[list(polys[f])], rest_n[f], len(polys), hits=blockers[f])
                tried[f] = {placement(f, rest_mats)}
        if not pending:
            break
        pose_state(rig, joints, pistons, state)
        mats = {b: rig.matrix_world @ rig.pose.bones[b].matrix @ rig.data.bones[b].matrix_local.inverted()
                for b in group_names}
        todo = []
        for f in pending:  # skip a face whose blockers sit as in a state it was already tried in
            if step:
                key = placement(f, mats)
                if key in tried[f]:
                    continue
                tried[f].add(key)
            todo.append(f)
        if not todo:
            continue
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        m = ev.to_mesh()
        co = np.empty(len(m.vertices) * 3)
        m.vertices.foreach_get("co", co)
        nrm = np.empty(len(m.polygons) * 3)
        m.polygons.foreach_get("normal", nrm)
        ev.to_mesh_clear()
        co, nrm = co.reshape(-1, 3), nrm.reshape(-1, 3)
        world = obj.matrix_world
        if world != Matrix.Identity(4):
            co = np.array([(world @ Vector(v))[:] for v in co])
            nrm = np.array([(world.to_3x3() @ Vector(v)).normalized()[:] for v in nrm])
        bvh = BVHTree.FromPolygons([Vector(v) for v in co] + occ_verts, polys + occ_faces)
        if not step:
            rest_bvh, rest_mats = bvh, mats
        for f in todo:
            tested += 1
            if escapes(bvh, samples[f] @ co[list(polys[f])], nrm[f], len(polys)):
                pending.discard(f)
    reset_pose(rig)
    bpy.context.view_layer.update()
    pending |= sealed

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    before = sum(len(f.verts) - 2 for f in bm.faces)
    keep = set()
    for f in bm.faces:  # an unseen face in a seen face's smooth fan feeds its corner normals: keep it
        if f.index in pending or not f.smooth:
            continue
        for v in f.verts:
            fan, stack = {f}, [f]
            while stack:
                g = stack.pop()
                for e in g.edges:
                    if v in e.verts and e.smooth:
                        for h in e.link_faces:
                            if h not in fan and h.smooth:
                                fan.add(h)
                                stack.append(h)
            keep |= {h.index for h in fan}
    dead = [f for f in bm.faces if f.index in pending and f.index not in keep]
    bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    after = sum(len(f.verts) - 2 for f in bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    print(f"[{NAME}] unseen faces: {before} -> {after} tris ({len(dead)} faces never visible culled, "
          f"{len(pending) - len(dead)} kept for smooth normals; {len(states)} states, {len(sealed)} sealed in their own body, "
          f"{len(blockers)} hidden by others, {tested} face tests)")


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def export(objects, stem):
    """Standard export settings, except that this asset exports its actions (props carry their own
    animations): each action is a separate glTF animation / FBX take. The rig's constraints are
    removed first, and the telescope stages' drivers (the caller restores both): joint limits are
    data in _rig.json and the pistons are baked into the actions."""
    for o in objects:
        if o.type == "ARMATURE":
            for pb in o.pose.bones:
                for c in list(pb.constraints):
                    pb.constraints.remove(c)
            for fc in list(o.animation_data.drivers if o.animation_data else []):
                o.animation_data.drivers.remove(fc)
    prepare_export(objects, HERE, stem)
    select_only(objects)
    bpy.ops.export_scene.fbx(
        filepath=str(HERE / f"{stem}.fbx"), use_selection=True, object_types={"MESH", "ARMATURE", "EMPTY"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False, use_mesh_modifiers=False,
        mesh_smooth_type="OFF", add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        use_armature_deform_only=True, bake_anim=True, bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False, bake_anim_use_all_actions=True, bake_anim_force_startend_keying=True,
        path_mode="COPY", embed_textures=True)
    bpy.ops.export_scene.gltf(
        filepath=str(HERE / f"{stem}.glb"), export_format="GLB", use_selection=True, export_yup=True,
        export_apply=False, export_skins=True, export_def_bones=True, export_animations=True,
        export_animation_mode="ACTIONS", export_anim_single_armature=True, export_reset_pose_bones=True,
        export_force_sampling=True, export_optimize_animation_size=True,
        export_optimize_animation_keep_anim_armature=False, export_anim_slide_to_zero=True,
        export_materials="EXPORT")



# --------------------------------------------------------------------------------------------
# The weapons' additions: tessellated parts, exact booleans on solids, lofts
# --------------------------------------------------------------------------------------------

from mathutils.geometry import tessellate_polygon

_part_init = Part.__init__


def _part_init_tessellated(self, bone, line, verts, faces, convex, solid=True, exact=False, closed=True):
    """Part with its faces ear-clipped into triangles before the BVH is built: a BVH fans an n-gon
    from its first corner, so a concave face (the header's face round its bores) would claim the holes
    and report contacts that are not there."""
    tris = []
    for f in faces:
        if len(f) <= 3:
            tris.append(tuple(f))
        else:
            tris += [(f[a], f[b], f[c]) for a, b, c in tessellate_polygon([[verts[i] for i in f]])]
    _part_init(self, bone, line, verts, tris, convex, solid, exact, closed)


Part.__init__ = _part_init_tessellated


def expand(state):
    """A joint state (or animation keys) as it is: nothing here is coupled."""
    return dict(state)


def _temp(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def slab_bm(points, th, normal):
    """A prism: the polygon `points` extruded th along `normal`, centred on it."""
    n = Vector(normal).normalized()
    bm = bmesh.new()
    bot = [bm.verts.new(Vector(q) - n * th / 2) for q in points]
    top = [bm.verts.new(Vector(q) + n * th / 2) for q in points]
    bm.faces.new(top)
    bm.faces.new(bot[::-1])
    for i in range(len(points)):
        j = (i + 1) % len(points)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rod_bm(p0, p1, r, segs=16):
    p0, p1 = Vector(p0), Vector(p1)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r,
                          depth=(p1 - p0).length)
    rot = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix()
    for v in bm.verts:
        v.co = rot @ v.co + (p0 + p1) / 2
    return bm


def block_bm(center, size):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    return bm


def loft_bm(rings):
    """A closed solid through rings of points (the same count in each), capped at both ends."""
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    bm.faces.new(vs[0][::-1])
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def boolean(base, tools, op):
    """`base` combined with each of `tools` in turn by an exact boolean ('UNION', 'DIFFERENCE',
    'INTERSECT'); returns a new bmesh (the inputs are consumed)."""
    obj = _temp(base, "_base")
    objs = [_temp(t, "_tool") for t in tools]
    for o in objs:
        mod = obj.modifiers.new("b", "BOOLEAN")
        mod.operation, mod.solver, mod.object = op, "EXACT", o
    out = bmesh.new()
    out.from_object(obj, bpy.context.evaluated_depsgraph_get())
    for o in (obj, *objs):
        mesh = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(mesh)
    return out


def machine(k, solid, cutters, bone, material):
    """A solid machined by exact booleans: every cutter taken away, then each face coloured by
    `material(face, point, cut)` (a point on the face), where `cut` is True for the faces the cutters made (inside the uncut
    solid's surface), and emitted as one part."""
    ref = solid.copy()
    bvh = BVHTree.FromBMesh(ref)
    out = boolean(solid, cutters, "DIFFERENCE") if cutters else solid
    out.normal_update()
    mats = []
    for f in out.faces:  # judged at its triangles' centres: a ring-shaped face's median lies in its hole
        pts = [v.co for v in f.verts]
        tris = [(pts[a] + pts[b] + pts[c]) / 3 for a, b, c in tessellate_polygon([pts])] or [f.calc_center_median()]
        dist, c = min(((bvh.find_nearest(q)[3], q) for q in tris), key=lambda e: e[0])
        mats.append(material(f, c, dist > 2e-4))
    ref.free()
    made = k.emit(out, bone, PRI, False, convex=False, exact=True)
    for f, m in zip(made, mats):
        f.material_index = SLOTS.index(m)


def bolt(k, at, normal, bone, r=0.005, mat=JNT, head=0.003):
    """A bolt head standing `head` proud of the surface at `at`, its shank sunk 2 mm in."""
    n = Vector(normal).normalized()
    k.cyl(Vector(at) - n * 0.002, Vector(at) + n * head, r, bone, mat, segs=6, solid=False)


def lean_slots(plane, normal, along, up, starts, width, lo, hi, lean, depth):
    """Slanted vent slots cut `depth` into a flat face: each a parallelogram, `width` wide along
    `along` from each start, from `lo` to `hi` along `up`, its top shifted `lean` along `along`."""
    o, a, u = Vector(plane), Vector(along), Vector(up)
    out = []
    for s in starts:
        pts = [o + a * s + u * lo, o + a * (s + width) + u * lo, o + a * (s + width + lean) + u * hi,
               o + a * (s + lean) + u * hi]
        out.append(slab_bm([tuple(p) for p in pts], 2 * depth, normal))
    return out


# --------------------------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------------------------

def circ(r, z, n=N, cx=0.0, cy=0.0):
    """A round section: n corners at radius r, turned half a side so a face is centred on each axis."""
    return [(cx + r * math.cos((i + 0.5) * 2 * math.pi / n), cy + r * math.sin((i + 0.5) * 2 * math.pi / n), z)
            for i in range(n)]


def flat(r, n=N):
    """The distance from the axis to the middle of a face of a round section with corners at r."""
    return r * math.cos(math.pi / n)


def revolve(profile, n=N):
    """A closed solid of revolution about the thruster's axis through (radius, z) stations, the first and
    last capped."""
    return loft_bm([circ(r, z, n) for r, z in profile])


def torus_bm(section, z0, n=N):
    """A closed ring about the axis: the (radius, height) section swept round at height z0."""
    bm = bmesh.new()
    rings = [[bm.verts.new((r * math.cos(a), r * math.sin(a), z0 + h)) for r, h in section]
             for a in ((i + 0.5) * 2 * math.pi / n for i in range(n))]
    m = len(section)
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rot_z(bm, deg):
    """Turn a bmesh about the thruster's axis."""
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(deg), 3, "Z"))
    return bm


def hull2d(points):
    """The convex hull of 2D points, counter-clockwise."""
    pts = sorted(set((round(x, 7), round(y, 7)) for x, y in points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def keyhole(root, centre, r, n=8):
    """A lug's outline: its root edge (two points, buried in what it grows out of) and a round end of
    radius r about its pin, as one convex plate."""
    return hull2d(list(root) + [(centre[0] + r * math.cos(2 * math.pi * i / n), centre[1] + r * math.sin(2 * math.pi * i / n))
                                for i in range(n)])


def plate_bm(outline, place, thickness, normal):
    """A convex plate: a 2D outline placed in 3D by `place(u, v)` (its mid-plane) and thickened along normal."""
    return slab_bm([place(u, v) for u, v in outline], thickness, normal)



def radial(az, r, z):
    a = math.radians(az)
    return Vector((r * math.cos(a), r * math.sin(a), z))


# --------------------------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------------------------

def seg_dist(p, seg):
    """The distance from a 2D point to a segment."""
    (x0, y0), (x1, y1) = seg
    dx, dy = x1 - x0, y1 - y0
    t = max(0.0, min(1.0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / max(dx * dx + dy * dy, 1e-12)))
    return math.hypot(p[0] - x0 - t * dx, p[1] - y0 - t * dy)


def section_fn(profile, mats, n, centre=(0.0, 0.0), closed=False, caps=(None, None)):
    """The material of a face of a round shell (a revolved or swept section of n sides about `centre`), by the
    section's segment it lies on: `mats` per segment, `caps` for the first and last station's end faces."""
    segs = list(zip(profile, profile[1:])) + ([(profile[-1], profile[0])] if closed else [])
    step = 2 * math.pi / n

    def fn(f, c):
        dx, dy = c.x - centre[0], c.y - centre[1]
        az = round(math.atan2(dy, dx) / step) * step    # the face's middle: faces are centred on multiples of step
        rho = (dx * math.cos(az) + dy * math.sin(az)) / math.cos(math.pi / n)
        for (r, z), mat in zip((profile[0], profile[-1]), caps):
            if mat and abs(f.normal.z) > 0.99 and abs(c.z - z) < 1e-4 and rho < r + 1e-4:
                return mat
        return mats[min(range(len(segs)), key=lambda i: seg_dist((rho, c.z), segs[i]))]
    return fn


def shell_ring(profile, n, centre):
    """A closed round shell through (radius, z) stations about a vertical axis at `centre`, capped at both ends."""
    return loft_bm([circ(r, z, n, centre[0], centre[1]) for r, z in profile])


def arm_bm(az):
    """An arm on the diagonal `az`: lofted from inside the drum out to the pod through keeled sections (a flat top,
    the sides chamfered in to a narrower bottom)."""
    d = radial_dir(az)
    lat = UP_V.cross(d)
    rings = []
    for dist, w, h, z in ARM:
        sec = [(w / 2, h / 2), (w / 2, -h / 6), (w / 4, -h / 2), (-w / 4, -h / 2), (-w / 2, -h / 6), (-w / 2, h / 2)]
        rings.append([tuple(d * dist + lat * x + Vector((0, 0, z + y))) for x, y in sec])
    return loft_bm(rings)


def spoke_bm(centre, az):
    """A spoke from the pod out over the duct's lip, its end dipping onto the lip (a side profile along it)."""
    d = radial_dir(az)
    w, zb, zt, s0, s1, zend = SPOKE
    prof = [(s0, zb), (s1, zb), (s1, zend), (s1 - 0.27, zt), (s0, zt)]
    return slab_bm([tuple(centre + d * s + Vector((0, 0, z))) for s, z in prof], w, UP_V.cross(d))


def pad_bm(az):
    """A corner spot's mount block under a duct's outer corner, its top sunk 1 cm into the duct's bottom."""
    c, d = duct_centre(az), radial_dir(az)
    lat = UP_V.cross(d)
    h, zb, out = PAD
    zt = DUCT[0][1] + 0.01
    mid = c + d * out + Vector((0, 0, (zb + zt) / 2))
    pts = [tuple(mid + d * a * h / 2 + lat * b * h / 2) for a, b in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    return slab_bm(pts, zt - zb, UP)


def box_bm():
    """The display box: an octagon in plan (the square's corners chamfered), its top and bottom edges chamfered."""
    h, c, z0, z1, e = BOX
    h0, c0 = h - e, c - e * (2 - math.sqrt(2))
    return loft_bm([rect(h0, h0, z0, chamfer=c0), rect(h, h, z0 + e, chamfer=c), rect(h, h, z1 - e, chamfer=c),
                    rect(h0, h0, z1, chamfer=c0)])


def build_body(k):
    """The rig's body: one lofted unibody, every shell fused by exact unions (the belly pan and lower marquee
    ring, the display box, the fuselage with the upper marquee ring, the four arms, the ducts with their pods and
    spokes, the corner spots' pads), then machined: a display recess in each face of the box and slanted vents in
    the drum between the arms. Off-white drum, arms, pods, duct lips, box and belly; grey rings, lips and duct walls; the
    bores and every cut matte black; the marquee bands and the displays' faces in their own slots (split off)."""
    prims = []

    def add(bm, fn):
        prims.append((bm.copy(), fn))
        return bm

    lower = add(revolve(LOWER), section_fn(LOWER, [PRI, PRI, SEC, SEC, MRQ], N, caps=(PRI, SEC)))
    hub = add(revolve(HUB), section_fn(HUB, [SEC, SEC, SEC, MRQ, SEC, SEC, SEC, PRI, PRI], N, caps=(SEC, PRI)))
    tools = [add(box_bm(), lambda f, c: PRI), hub]
    for az in DIAGONALS:
        c = duct_centre(az)
        tools.append(add(arm_bm(az), lambda f, c: PRI))
        duct = torus_bm(DUCT, 0.0, N_DUCT)
        bmesh.ops.translate(duct, verts=duct.verts[:], vec=c)
        tools.append(add(duct, section_fn(DUCT, [FRM, PRI, PRI, SEC, SEC], N_DUCT, (c.x, c.y), closed=True)))
        tools.append(add(shell_ring(POD, N_POD, c), section_fn(POD, [PRI, PRI, SEC], N_POD, (c.x, c.y), caps=(PRI, SEC))))
        for turn in (120, -120):  # the Y over the rotor: the arm and these two spokes
            tools.append(add(spoke_bm(c, az + 180 + turn), lambda f, c: PRI))
        tools.append(add(pad_bm(az), lambda f, c: SEC))
    solid = boolean(lower, tools, "UNION")
    w, h, depth = SCREEN
    zc = (BOX[2] + BOX[3]) / 2
    floor = BOX[0] - depth
    cutters = []
    for az in (0, 90, 180, 270):
        n = radial_dir(az)
        size = (0.14, w, h) if az % 180 == 0 else (w, 0.14, h)
        cutters.append(block_bm(tuple(n * (floor + 0.07) + Vector((0, 0, zc))), size))
        vw, lean, pitch = VENTS[2], VENTS[3], 0.10
        cutters += lean_slots(radial(az, flat(DRUM[0]), 0), n, UP_V.cross(n), (0, 0, 1),
                              [-(vw + lean) / 2 + pitch * (i - 1) for i in range(3)], vw, VENTS[0], VENTS[1], lean,
                              VENTS[4])
    trees = [(BVHTree.FromBMesh(bm), fn) for bm, fn in prims]

    def material(f, c, cut):
        if cut:
            n = f.normal
            if (abs(n.z) < 0.01 and max(abs(n.x), abs(n.y)) > 0.999 and abs(n.dot(c) - floor) < 1e-4
                    and abs(c.z - zc) < h / 2):
                return SCR
            return FRM
        dist, fn = min(((tree.find_nearest(c)[3], fn) for tree, fn in trees), key=lambda e: e[0])
        return fn(f, c) if dist < 1e-3 else PRI

    machine(k, solid, cutters, "Root", material)
    for bm, _ in prims:
        bm.free()


def build_fittings(k):
    """The motor cans under the pods (titanium, sunk into them) and the beacon on the fuselage's top."""
    r, z0, z1 = MOTOR
    for az in DIAGONALS:
        c = duct_centre(az)
        k.cyl((c.x, c.y, z0), (c.x, c.y, z1), r, "Root", TI, segs=N_POD)
    top = HUB[-1][1]
    k.cyl((0, 0, top - 0.005), (0, 0, top + 0.04), BEACON[0], "Root", FRM, segs=8)
    k.cyl((0, 0, top + 0.03), (0, 0, top + 0.06), BEACON[1], "Root", EMI, segs=8)


def build_rotors(k):
    """Each rotor: a stainless shaft up into the motor can, a stainless spinner, and five twisted grey blades with
    their roots seated in it, each blade's leading edge raised in its sense of turning so it drives air down through
    the duct."""
    for name, az in ROTORS:
        c, spin = duct_centre(az), ROTOR_SPIN[az]
        r, z0, z1 = SHAFT
        k.cyl((c.x, c.y, z0), (c.x, c.y, z1), r, name, JNT, segs=6)
        machine(k, loft_bm([circ(rr, z, 8, c.x, c.y) for rr, z in SPINNER]), [], name, lambda f, cc, cut: JNT)
        for i in range(BLADES):
            e = radial_dir(az + 360.0 * i / BLADES)
            t = UP_V.cross(e) * spin
            rings = []
            for rr, chord, th, pitch in BLADE:
                p = math.radians(pitch)
                lead = t * math.cos(p) + UP_V * math.sin(p)
                side = -t * math.sin(p) + UP_V * math.cos(p)
                mid = c + e * rr + Vector((0, 0, BLADE_Z))
                rings.append([tuple(mid + lead * chord / 2), tuple(mid + side * th / 2), tuple(mid - lead * chord / 2),
                              tuple(mid - side * th / 2)])
            machine(k, loft_bm(rings), [], name, lambda f, cc, cut: SEC)


def build_spot(k, s):
    """A moving-head spotlight: the pan motor (titanium) sunk into its mount; the pan stage (a stainless rotor
    boss sunk into the motor, a matte black yoke, a titanium tilt motor on one arm, the axle's bearing in the
    other); the head (a stainless axle through both arms, an off-white can with a black bezel round its lens)."""
    m, a, out = s.mount, s.axis, s.out
    down = Vector(DOWN)
    r, sunk, bot = SPOT_BASE
    k.cyl(m + UP_V * sunk, m + down * bot, r, "Root", TI, segs=6)
    r, top, bot = SPOT_BOSS
    k.cyl(m + down * top, m + down * bot, r, s.pan, JNT, segs=6)
    wo, wi, top, bar, end, depth = YOKE
    outline = [(-wo, top), (wo, top), (wo, end), (wi, end), (wi, bar), (-wi, bar), (-wi, end), (-wo, end)]
    k.prism([tuple(m + a * u + down * z) for u, z in outline], depth, out, s.pan, FRM, convex=False)
    c = s.centre
    u0, u1, r = TILT_MOTOR
    k.cyl(c + a * u0, c + a * u1, r, s.pan, TI, segs=6)
    half, r = AXLE
    k.cyl(c - a * half, c + a * half, r, s.tilt, JNT, segs=6)
    rings = []
    for along, rr in HEAD:
        rings.append([tuple(c + down * along + (a * math.cos(q) + out * math.sin(q)) * rr)
                      for q in ((i + 0.5) * math.pi / 4 for i in range(8))])
    lens, bezel = HEAD[-1][0], HEAD[-2][0]

    def material(f, cc, cut):
        along = (cc - c).dot(down)
        if f.normal.dot(down) > 0.99 and along > lens - 1e-4:
            return LMP
        return FRM if along > bezel + 1e-4 else PRI
    machine(k, loft_bm(rings), [], s.tilt, material)


def build_all(k):
    build_body(k)
    build_fittings(k)
    build_rotors(k)
    for s in SPOTS:
        build_spot(k, s)


# --------------------------------------------------------------------------------------------
# The jumbotron's checks
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """The rotors through a blade's pitch, and every spot over its range (pan x tilt, all together; neighbours
    are kept apart by check_spot_spacing), on top of the animation frames."""
    rotors = [(f"rotors {a}", {n: float(a) for n, _ in ROTORS}) for a in range(0, 72, 6)]
    spots = [(f"spots pan {p} tilt {t}", {**{s.pan: float(p) for s in SPOTS}, **{s.tilt: float(t) for s in SPOTS}})
             for p in range(-180, 180, 45) for t in range(-80, 81, 20)]
    return rotors + spots


def cull_states():
    """The cull's states: the spots over their range and in flood and show, the rotors at two angles (the other
    bodies never hide one another: the spots hang clear of everything)."""
    out = [("flood", PREVIEW_STATES["flood"]), ("show", PREVIEW_STATES["show"])]
    for p in (-135, -45, 45, 135):
        for t in (-80, 0, 80):
            out.append((f"pan {p} tilt {t}", {**{s.pan: float(p) for s in SPOTS}, **{s.tilt: float(t) for s in SPOTS},
                                              **{n: 36.0 * (t == 0) for n, _ in ROTORS}}))
    return out


def check_envelope(kit, joints, states):
    """The rig stays inside its 10 x 10 m square in plan in every state; returns the lowest and highest points
    at rest and over every state."""
    problems = []
    rest = [v for p in all_parts(kit) for v in p.verts]
    zr = (min(v.z for v in rest), max(v.z for v in rest))
    lo, hi = zr
    for tag, state in [("rest", {})] + states:
        m = fk(joints, expand(state))
        for part in all_parts(kit):
            vs = [m[part.bone] @ v for v in part.verts]
            lo, hi = min(lo, min(v.z for v in vs)), max(hi, max(v.z for v in vs))
            if any(abs(v.x) > HALF + 1e-6 or abs(v.y) > HALF + 1e-6 for v in vs):
                problems.append(f"{part.bone} (line {part.line}) leaves the 10 x 10 m envelope at {tag}")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(dict.fromkeys(problems)))
    return zr, (lo, hi)


def spot_reach(kit, joints, s):
    """How far a spot's moving parts reach from its pan axis, and down, over its whole tilt range."""
    axis = s.pan_pivot.xy
    tj = joints[s.tilt]
    reach, low = 0.0, 0.0
    for t in range(-80, 81, 5):
        m = tj.local(float(t))
        for part in all_parts(kit):
            if part.bone == s.pan or part.bone == s.tilt:
                for v in part.verts:
                    w = m @ v if part.bone == s.tilt else v
                    reach, low = max(reach, (w.xy - axis).length), min(low, w.z)
    return reach, low


def check_spot_spacing(kit, joints):
    """A spot pans a full turn and more, so its moving parts sweep a round volume about its pan axis; no two
    spots' volumes may meet (then no combination of their motions can make them collide)."""
    reach = {s.name: spot_reach(kit, joints, s) for s in SPOTS}
    problems, gaps = [], []
    for i, a in enumerate(SPOTS):
        for b in SPOTS[i + 1:]:
            if abs(a.mount.z - b.mount.z) > 1.0:
                continue  # the belly's and the ducts' spots hang metres apart in height
            gap = (a.pan_pivot.xy - b.pan_pivot.xy).length - reach[a.name][0] - reach[b.name][0]
            gaps.append(gap)
            if gap < 0.02:
                problems.append(f"{a.name} and {b.name}: swept volumes {gap:.3f} m apart")
    if problems:
        raise SystemExit(f"[{NAME}] spot spacing failed:\n  " + "\n  ".join(problems))
    return max(r for r, _ in reach.values()), min(gaps)


def lens(s):
    return s.centre + Vector(DOWN) * HEAD[-1][0]


def check_lighting(kit, joints):
    """flood as the joints place it: every spot's beam points at its zone's middle (through the tilt centre), and
    the beam's axis leaves the rig without meeting any part. Returns how much of each cone's rim (16 rays) is
    clear of the rig."""
    state = PREVIEW_STATES["flood"]
    m = fk(joints, expand(state))
    verts, faces = [], []
    for part in all_parts(kit):
        k0 = len(verts)
        verts += [m[part.bone] @ v for v in part.verts]
        faces += [tuple(k0 + i for i in f) for f in part.faces]
    tree = BVHTree.FromPolygons(verts, faces)
    problems, rims = [], {}
    for s in SPOTS:
        plan = LIGHTING[s.name]
        mm = m[s.tilt]
        d = (mm.to_3x3() @ Vector(DOWN)).normalized()
        want = (plan["target"] - mm @ s.centre).normalized()
        if d.angle(want) > math.radians(0.01) or (mm @ s.centre - s.centre).length > 1e-6:
            problems.append(f"{s.name}: flood points {math.degrees(d.angle(want)):.3f} deg off its zone")
        start = mm @ lens(s) + d * 0.002
        if tree.ray_cast(start, d)[0] is not None:
            problems.append(f"{s.name}: its beam hits the rig in flood")
        side = d.orthogonal().normalized()
        half = math.radians(plan["half_angle"])
        clear = 0
        for i in range(16):
            ray = Matrix.Rotation(2 * math.pi * i / 16, 3, d) @ (Matrix.Rotation(half, 3, side) @ d)
            clear += tree.ray_cast(start, ray)[0] is None
        rims[s.name] = clear / 16
    if problems:
        raise SystemExit(f"[{NAME}] lighting failed:\n  " + "\n  ".join(problems))
    return rims


def aim_rates():
    """The fastest pan and tilt of any spot in the show loop, degrees per frame."""
    keys = ANIMATIONS["show"][2]
    return max(abs(b[1] - a[1]) for n, ks in keys.items() for a, b in zip(ks, ks[1:]))


# --------------------------------------------------------------------------------------------
# The displays and marquees, gizmos, preview and export
# --------------------------------------------------------------------------------------------

def split_off(body, slot, name):
    """A copy of the body keeping only the faces in `slot` (their own mesh, one slot, on Root)."""
    obj = body.copy()
    obj.data = body.data.copy()
    obj.name, obj.data.name = f"SK_{TITLE}{name}", f"SK_{TITLE}{name}_Mesh"
    bpy.context.scene.collection.objects.link(obj)
    idx = SLOTS.index(slot)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != idx], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.materials.clear()
    obj.data.materials.append(bpy.data.materials[slot])
    for poly in obj.data.polygons:
        poly.material_index = 0
    for vg in list(obj.vertex_groups):
        if vg.name != "Root":
            obj.vertex_groups.remove(vg)
    bpy.data.materials[slot].use_backface_culling = False
    return obj


def screen_uvs(obj):
    """Each display 0..1 across its face: u from its left to its right as a viewer in front of it sees it, v up."""
    w, h, _ = SCREEN
    zc = (BOX[2] + BOX[3]) / 2
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        right = (-poly.normal).cross(UP_V)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.dot(right) / w + 0.5, (co.z - zc) / h + 0.5)


def marquee_uvs(obj):
    """Each marquee band: u 0..1 once round from +X toward +Y (counter-clockwise from above: text reads left to right
    to a viewer outside it), v 0 at the band's bottom to 1 at its top."""
    bands = [(LOWER[LOWER_BAND][1], BOX[2]), (HUB[HUB_BAND][1], HUB[HUB_BAND + 1][1])]
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        cos = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        z0, z1 = min(bands, key=lambda b: abs((b[0] + b[1]) / 2 - sum(c.z for c in cos) / len(cos)))
        us = [(math.atan2(c.y, c.x) / (2 * math.pi)) % 1.0 for c in cos]
        if max(us) - min(us) > 0.5:  # the face straddles the seam at +X
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, c, u in zip(poly.loop_indices, cos, us):
            uv.data[li].uv = (u, (c.z - z0) / (z1 - z0))


def split_displays(body):
    """The displays and the marquee bands leave the body as their own meshes, and their slots leave it."""
    counts = {slot: sum(1 for p in body.data.polygons if p.material_index == SLOTS.index(slot)) for slot in (SCR, MRQ)}
    screen, marquee = split_off(body, SCR, "Screen"), split_off(body, MRQ, "Marquee")
    screen_uvs(screen)
    marquee_uvs(marquee)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in (SLOTS.index(SCR), SLOTS.index(MRQ))],
                     context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    for slot in (MRQ, SCR):  # the last two slots: no face's index changes
        body.data.materials.pop(index=SLOTS.index(slot))
    return screen, marquee, counts


def display_counts(obj):
    return {slot: sum(1 for p in obj.data.polygons if p.material_index == SLOTS.index(slot)) for slot in (SCR, MRQ)}


def place_on_bone(obj, rig, bone_name, m):
    """Parent obj to a bone and give it the world matrix m (at rest)."""
    bone = rig.data.bones[bone_name]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    obj.matrix_basis = m
    return obj


def gizmo_specs():
    """(name, bone, origin, forward, up): Spot<Position>Beam at the middle of each spot's lens, pointing along its
    beam (down at rest), its up toward the side the head tilts to at + tilt; each rides its head."""
    return [(s.gizmo, s.tilt, tuple(lens(s)), DOWN, tuple(s.out)) for s in SPOTS]


def build_gizmos(rig):
    objs = []
    for name, bone, origin, fwd, up in gizmo_specs():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type, e.empty_display_size = "SINGLE_ARROW", 0.5
        bpy.context.scene.collection.objects.link(e)
        fwd, up = Vector(fwd), Vector(up)
        m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
        m.translation = origin
        objs.append(place_on_bone(e, rig, bone, m))
    return objs


def write_rig_json(joints, tris, screen_tris, marquee_tris, heights, rims):
    def vec(v):
        return [round(c, 4) for c in v]

    zc = (BOX[2] + BOX[3]) / 2
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, front -Y, left +X; the origin is the centre of the belly pan's flat underside, "
                 "on the rig's axis. glTF/Godot: (x, z, -y). The joints turn about their bones' local X (degrees).",
        "rest": "the rotors stopped, every spot's head straight down (pan and tilt 0)",
        "placement": {"hover_height_m": HOVER, "note": f"place the origin {HOVER:g} m over the middle of the arena, the rig's "
                      "axis vertical and its Y along the map's long axis; the spots' zones and flood aims assume that "
                      "height and map"},
        "size_m": {"plan": [2 * HALF, 2 * HALF], "top": round(heights[0][1], 4), "lowest_at_rest": round(heights[0][0], 4),
                   "lowest_in_any_state": round(heights[1][0], 4)},
        "arena_m": {"size": list(ARENA), "long_axis": "the rig's Y (front-back)", "floor_z": -HOVER,
                    "zones": list(ZONES)},
        "spots": [{"name": s.name, "pan_bone": s.pan, "tilt_bone": s.tilt, "gizmo": s.gizmo,
                   "pan_pivot": vec(s.pan_pivot), "tilt_centre": vec(s.centre), "tilt_axis": vec(s.axis),
                   "zone": LIGHTING[s.name]["zone"], "target": vec(LIGHTING[s.name]["target"]),
                   "flood_deg": {"pan": round(LIGHTING[s.name]["pan"], 3), "tilt": round(LIGHTING[s.name]["tilt"], 3)},
                   "cone_half_angle_deg": round(LIGHTING[s.name]["half_angle"], 2),
                   "range_m": round(LIGHTING[s.name]["range"], 2), "rim_clear_of_rig": rims[s.name]}
                  for s in SPOTS],
        "spot_rule": "pan about +Z (+ counter-clockwise from above), tilt about the tilt axis (+ swings the beam out, away "
                     "from the rig's axis); beam = -Z cos(tilt) + Rz(pan)(out) sin(tilt), from the tilt centre",
        "rotors": [{"bone": n, "centre": vec(duct_centre(az)), "spin": "counter-clockwise" if ROTOR_SPIN[az] > 0 else
                    "clockwise", "hover_deg_per_s": SPIN * FPS * ROTOR_SPIN[az]} for n, az in ROTORS],
        "screens": {"object": f"SK_{TITLE}Screen", "material": SCR, "triangles": screen_tris,
                    "faces": "one on each face of the box (+X, +Y, -X, -Y), each "
                             f"{SCREEN[0]} x {SCREEN[1]} m (16:9), centred at z {zc:g}",
                    "uv": "each display 0..1: u from its left to its right as seen from in front of it, v up (the same "
                          "image on all four; tell them apart by their normals)"},
        "marquees": {"object": f"SK_{TITLE}Marquee", "material": MRQ, "triangles": marquee_tris,
                     "bands": [{"ring": "lower", "radius_m": round(flat(LOWER[LOWER_BAND][0]), 4),
                                "z": [LOWER[LOWER_BAND][1], BOX[2]]},
                               {"ring": "upper", "radius_m": round(flat(HUB[HUB_BAND][0]), 4),
                                "z": [HUB[HUB_BAND][1], HUB[HUB_BAND + 1][1]]}],
                     "uv": "each band u 0..1 once round from +X toward +Y (counter-clockwise from above: scroll u to run "
                           "text round it), v 0 at its bottom to 1 at its top; tile u for the band's length"},
        "gizmos": [{"name": n, "bone": b, "origin": vec(o), "forward": vec(f), "up": vec(u),
                    "godot": "-Z along the beam: a SpotLight3D under it with no transform shines where the head points"}
                   for n, b, o, f, u in gizmo_specs()],
        "materials_note": "map-generic finish in Tensor's materials (off-white and grey paint, matte black, stainless "
                          "steel, titanium), a warm white lamp for the lenses: no team colours; M_Screen and "
                          "M_Marquee (white, emissive) are for the game's textures",
        "materials": [s for s in SLOTS if s not in (SCR, MRQ)],
        "triangles": tris,
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "usage": "Play spin_up, then loop hover while the rig flies (spin_down to land it: the rotors only). The spots "
                 "layer on top: lights_on swings them from rest to flood (every zone of the map lit), flood holds it, "
                 "show loops a sweep that starts and ends on flood, lights_off returns them to rest. Or drive each "
                 "spot's pan and tilt directly within range (aim with spot_rule). Put a SpotLight3D on each "
                 "Spot<Position>Beam gizmo with its cone_half_angle_deg as spot_angle and range_m as its range. The "
                 "displays and marquees take the game's textures on M_Screen and M_Marquee.",
    }
    RIG_JSON_PATH.write_text(json.dumps(data, indent=2))


def main():
    reset_scene()
    build_materials()
    joints = resolve_joints()
    pistons = resolve_pistons(joints)
    check_states(joints)
    rig = build_rig(joints, pistons)
    check_rig_fk(rig, joints)
    actions = build_actions(rig, joints, pistons)

    kit = Kit()
    build_all(kit)
    states = action_states(actions, joints) + sweep_states(joints)
    heights = check_envelope(kit, joints, states)
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    reach, gap = check_spot_spacing(kit, joints)
    rims = check_lighting(kit, joints)
    check_motion(kit, joints, states)
    print(f"[{NAME}] checks passed ({len(states)} motion states); from z {heights[0][0]:.3f} to {heights[0][1]:.3f} m at "
          f"rest, lowest {heights[1][0]:.3f} m; spots reach {reach:.3f} m from their pan axes, {gap:.3f} m apart at "
          f"the closest; show pans at most {aim_rates():.2f} deg/frame")
    for s in SPOTS:
        p = LIGHTING[s.name]
        print(f"[{NAME}] {s.name}: zone {p['zone']}, flood pan {p['pan']:.1f} tilt {p['tilt']:.1f}, cone "
              f"{p['half_angle']:.1f} deg, range {p['range']:.1f} m, rim {rims[s.name]:.0%} clear")

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    check_coplanar(body)
    skin(body, rig)
    before = display_counts(body)
    if "--no-cull" not in sys.argv:
        cull_unseen(body, rig, joints, pistons, cull_states(), (-1e-4, -1e-4), (1e-4, 1e-4), PLATFORM_FRAME)
    if display_counts(body) != before:
        raise SystemExit(f"[{NAME}] the cull removed display faces ({before} -> {display_counts(body)})")
    screen, marquee, _ = split_displays(body)
    unwrap(body)
    tris, screen_tris, marquee_tris = triangles(body), triangles(screen), triangles(marquee)
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET}); screens: {screen_tris} tris; marquees: {marquee_tris} tris")
    if tris > TRI_BUDGET and "--no-cull" not in sys.argv:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")

    gizmos = build_gizmos(rig)
    export([rig, body, screen, marquee, *gizmos], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, tris, screen_tris, marquee_tris, heights, rims)

    def pose_entry(jname, v):
        return {"rot": [v, 0, 0]} if joints[jname].kind == "hinge" else {"loc": [0, v, 0]}

    rig["preview_poses"] = json.dumps({s: {j: pose_entry(j, v) for j, v in expand(st).items()}
                                       for s, st in PREVIEW_STATES.items()})
    rig["preview_pose_views"] = json.dumps(PREVIEW_VIEWS)
    scene = bpy.context.scene
    scene["preview_actions"] = json.dumps(SHOWCASE)
    scene["preview_under"] = json.dumps(SHOWCASE_UNDER)
    scene["preview_frame"] = json.dumps(PREVIEW_FRAME)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)
    print(f"[{NAME}] saved {BLEND_PATH}")
    print(f"[{NAME}] exported {NAME}.glb/.fbx, {RIG_JSON_PATH.name}")


if __name__ == "__main__":
    import sys
    if '--uv-only' in sys.argv:
        sys.path.insert(0, str(HERE.parents[1]))
        from material_uv import refresh_asset
        refresh_asset(HERE)
    else:
        main()
