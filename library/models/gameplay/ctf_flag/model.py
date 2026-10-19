"""CTF flag - KYLR's capture-the-flag flag: carried on a player's back, standing on its own tripod
on the ground, modelled, rigged and animated from script.

Run headless from the repo root (after Tensor's model.py: the carry is fitted to his back):
    blender --background --factory-startup --python models/gameplay/ctf_flag/model.py

Produces, next to this script:
    ctf_flag.blend             source scene, opened by preview.py and animate.py
    ctf_flag.glb / .fbx        SK_CtfFlag (the flag unit) and SK_CtfFlagCloth (the cloth, its own emissive
                               M_Flag slot for the team colour) skinned to RIG_CtfFlag, the gizmos
                               GroundMount and BackMount, and the actions stow, deploy, wave and flutter
    ctf_flag_rig.json          the joints and their ranges, the cloth's bones and weights, the mounts (and
                               where BackMount goes on Tensor), the animations and the gizmos

Design: one lofted unibody spine (the weapons' language, the environment props' materials): a grey hub
with three clevis slots, a slim grey shaft, an off-white core with lit strips down its side flats and
slanted vents in its front, a grey upper shaft, an off-white collar and a lit beacon on top. Fused into
it: a D-grip on its back, two cloth arms carrying the luff rod, and a hook on its front at mid-height.

Ground mount: a tripod. Three grey legs turn on stainless pins in the hub's clevis slots, each driven by
a titanium hinge motor on one cheek (a nut on a boss on the other); folded (`stow`) they lie up along
the shaft, deployed (`deploy`, the rest pose) their rubber pads stand flat on the ground.
Back mount: the hook drops over the grab handle on Tensor's power pack (its pocket bears on the bar)
and a stainless latch, hinged on a bronze bushing in the hook, swings shut under the bar.
Cloth: its own mesh (SK_CtfFlagCloth, emissive M_Flag: the game tints it with the team's colour), a sheet
flying from a sleeve round the luff rod. The rod turns in bronze bushings in the arms' eyes (Swivel, the
flag weathervaning), and the sheet hangs on four rows of five-bone hinge chains about the vertical
(Cloth<row>_<seg>), every hinge limited; the sheet is skinned smoothly across them (up to four
influences a vertex: the one deforming mesh here), the sleeve rigidly to the rod. `wave` (standing in a
breeze) and `flutter` (carried at a run) are travelling waves from the luff to the fly.

Every rigid part is weighted 1.0 to one bone. The build fails if a part floats, a hinge isn't coaxial
with its bearings, anything collides through any animation frame or across the joints' ranges, the flag
rises over 1.25 m or goes under the ground, the carried flag touches Tensor anywhere but the hook on his
handle, the cloth meets a part or Tensor or stretches, or a joint leaves its limits.
Conventions: 1 unit = 1 m, Z up, front = -Y (its left is +X; the cloth flies to its back, +Y). The origin
is on the ground under the spine, between the feet (GroundMount). Rest pose = standing, legs deployed,
latch open, cloth flat.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Flag': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
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

NAME = "ctf_flag"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # CtfFlag
TENSOR_BLEND = HERE.parents[1] / "characters" / "tensor" / "tensor.blend"
TENSOR_RIG = TENSOR_BLEND.with_name("tensor_rig.json")   # its FlagMount gizmo: where BackMount goes

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
CLOTH_BUDGET = 1_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored by the kit)

HEIGHT = 1.25                          # nothing rises above this in any state (HEIGHT_DEPLOYED)
N = 12                                 # sides of the round parts' default
# The spine's sections, bottom up: (z, flat distance, chamfer, depth scale): chamfered hexagons, a flat
# facing each leg (azimuths 90, 210, 330) and the front and back, corners at +-X; the core is deeper front
# to back (its y scaled). The pole is 5 cm across at its widest (user; the core and its pods), its bottom
# 0.25 m off the ground on the deployed legs: the hub, the shaft, the core flaring out of it and tapering
# into the upper shaft, and the collar.
SPINE = [(0.250, 0.010, 0.002, 1.0), (0.262, 0.018, 0.004, 1.0), (0.275, 0.021, 0.004, 1.0),
         (0.310, 0.021, 0.004, 1.0), (0.330, 0.016, 0.003, 1.0), (0.655, 0.016, 0.003, 1.0),
         (0.700, 0.0205, 0.004, 1.2), (0.990, 0.0205, 0.004, 1.2), (1.030, 0.014, 0.003, 1.0),
         (1.190, 0.014, 0.003, 1.0), (1.198, 0.018, 0.004, 1.0), (1.228, 0.018, 0.004, 1.0)]
SHAFT, CORE_I, UPPER = 5, 6, 8         # SPINE indices: the shaft's top, the core's bottom, the upper shaft's bottom
CORE = (0.0205, 1.2, 0.700, 0.990)     # the core's flat distance, depth scale and its full height (from, to)
BEACON = [(1.228, 0.015, 0.003, 1.0), (1.2495, 0.008, 0.002, 1.0)]  # the lit beacon on the collar's top
POD = (0.013, 0.760, 0.960, 0.006, 0.025)  # the core's side pods at +-X: half-depth, z from, to, chamfer, outer face |x|
CELL = (0.006, 0.790, 0.930, 0.003)    # the lit cell window in each pod: half-width, z from, to, pocket depth
RING = (0.500, 0.510, 0.002)           # the lit ring round the shaft: z from, to, groove depth
STOW_LENGTH, HEIGHT_DEPLOYED = 1.0, 1.25  # (user) the flag with its legs folded, and standing on them
POLE_W = 0.05                          # (user) the pole's width at its widest
LEG_AZ = {"LegBack": 90, "LegFrontLeft": 330, "LegFrontRight": 210}  # the cloth flies over the back leg
PIVOT_R, PIVOT_Z = 0.036, 0.290        # the legs' hinge axes (in lugs outside the pole): radius from its axis, height
FOOT_R, ANKLE_Z = 0.25, 0.022          # deployed: the feet's reach from the axis, the ankle's height
PAD = (0.016, 0.008)                   # rubber foot pads: radius, thickness (their soles on the ground)
KNUCKLE = (0.0085, 0.007)              # each leg's knuckle: radius, half-width along its pin
LUG = (0.008, 0.005, 0.010, 0.012, 0.016)  # the hub's clevis lugs: cheeks' inner offset along the pin, thickness,
                                       # round end radius; their root's radius and half-height (buried in the hub)
LEG_SECTION = ((0.014, 0.017), (0.011, 0.012))  # a leg's section (along its pin, across) at the knuckle, at the foot
MOTOR = (0.013, 0.028, 0.008)          # the hinge motors on the + cheeks' outer faces: from, to (along the pin), radius
PIN = (0.0185, 0.020, 0.003)           # the legs' pins: from (-pin side), to (into the motor), radius
NUT = (0.0035, 0.005)                  # the pins' nuts on the - cheeks' outer faces: height, radius
BAR = (-0.046, 0.750, 0.0095)          # the hook's pocket: its axis (y, z; where Tensor's handle bar lies:
                                       # BackMount, the flag's centre) and radius
HOOK_W = 0.018                         # the hook's half-width (it fits between the handle's uprights)
LATCH_P, LATCH_R = (BAR[0] + 0.019, BAR[1] - 0.022), 0.0325  # the latch's pivot (y, z) and its crossbar's radius about it
LATCH_CLOSE = 90.0                     # the latch shut (degrees)
ROD = (0.045, 0.004)                   # the luff rod: y, radius
ARM_Z = ((0.845, 0.860), (1.199, 1.214))  # the cloth arms' bottom and top faces: lower, upper arm
BUSH_R = 0.0075                        # the rod's bronze bushings in the arms' eyes
CLOTH = (0.051, 0.50, 0.8645, 1.1945)  # the sheet: its luff (y), fly length, bottom and top edges (z)
SLEEVE_R = 0.0065                      # the cloth's sleeve round the rod
ROWS, SEGS = 4, 6                      # cloth chains (rows, bottom to top) and the bones in each
GRID = (18, 8)                         # the sheet's quads along the fly and up
CLOTH_LIMIT, SWIVEL_LIMIT = 35.0, 40.0
WAVE = (90, 2, 28.0, 10.0)             # wave: frames per loop, waves per loop, amplitude at the fly (deg), swivel sway
FLUTTER = (30, 2, 34.0, 3.0)           # flutter (carried at a run): the same
WAVE_K, ROW_LAG = 2 * math.pi * 0.65, 0.45 # the wave's phase across the fly and from the top row to the bottom (rad)
STRETCH = 0.08                         # the sheet's edges may not stretch or shrink more than this
PREVIEW_FRAME = {"lo": [-0.27, -0.27, 0.0], "hi": [0.27, 0.57, 1.25]}
# === END SPEC ===

LATCH, SWIVEL = "Latch", "Swivel"
LEGS = list(LEG_AZ)
PHI = math.degrees(math.atan2(FOOT_R - PIVOT_R, PIVOT_Z - ANKLE_Z))   # deployed: a leg's angle from straight down
LEG_L = math.hypot(FOOT_R - PIVOT_R, PIVOT_Z - ANKLE_Z)              # pivot to ankle
FOLD = round(180.0 - PHI, 3)                                         # folded: straight up along the shaft
STOWED = {**{leg: FOLD for leg in LEGS}, LATCH: LATCH_CLOSE}
# The cull's level surface, far above and facing down: the flag is carried and dropped anywhere, so nothing
# of it is hidden by the ground (its soles show when it is carried).
PLATFORM_FRAME = Matrix.Translation((0, 0, 50.0)) @ Matrix.Rotation(math.pi, 4, "X")
GROUPS = ()


def hatch(a, b, n):  # (the framework's pistons; this prop has none)
    return Vector((a, b, n))


def leg_axes(az):
    """A leg's frame: radial u, hinge axis a (u x Z: + folds the foot out and up), deployed direction d
    (pivot to ankle), e = a x d (up and out, across the leg), and its pivot P."""
    u = Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0))
    z = Vector((0.0, 0.0, 1.0))
    a = u.cross(z)
    p = math.radians(PHI)
    d = u * math.sin(p) - z * math.cos(p)
    return u, a, d, a.cross(d), u * PIVOT_R + z * PIVOT_Z


def cloth_name(r, j):
    return f"Cloth{r}_{j}"


def cloth_row_z(r):
    return CLOTH[2] + (CLOTH[3] - CLOTH[2]) * r / (ROWS - 1)


def cloth_joint_y(j):
    return CLOTH[0] + CLOTH[1] * j / SEGS


CLOTH_BONES = [cloth_name(r, j) for r in range(ROWS) for j in range(SEGS)]


def joint_specs():
    specs = [("Root", None, "fixed", (0, 0, 0), UP, UP, None)]
    for name, az in LEG_AZ.items():  # 0 = deployed, FOLD = folded up along the shaft
        _, a, d, _, p = leg_axes(az)
        specs.append((name, "Root", "hinge", tuple(p), tuple(a), tuple(d), (0.0, FOLD)))
    # the latch about -X: 0 hangs open, + swings it forward (-Y) under the bar
    specs.append((LATCH, "Root", "hinge", (0, *LATCH_P), (-1, 0, 0), DOWN, (0.0, LATCH_CLOSE)))
    # the luff rod about +Z, its pivot in the upper arm's bushing: + turns the fly toward -X
    specs.append((SWIVEL, "Root", "hinge", (0, ROD[0], sum(ARM_Z[1]) / 2), UP, BACK, (-SWIVEL_LIMIT, SWIVEL_LIMIT)))
    for r in range(ROWS):  # each row a chain from the sleeve to the fly, hinged about +Z
        for j in range(SEGS):
            specs.append((cloth_name(r, j), SWIVEL if j == 0 else cloth_name(r, j - 1), "hinge",
                          (0, cloth_joint_y(j), cloth_row_z(r)), UP, BACK, (-CLOTH_LIMIT, CLOTH_LIMIT)))
    return specs


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space.
JOINT_SPECS = joint_specs()
PISTON_SPECS = []                      # the legs turn on hinge motors, the latch by its own motor
PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015


def cloth_loop(spec):
    """Keys for a looping cloth animation: a travelling wave from the luff to the fly (the absolute angle of
    segment j in row r is A(s) sin(phase - k s - lag), s its middle along the fly, A growing toward the fly,
    the top row leading), each hinge keyed with its segment's angle less the one before it; the swivel sways
    once a loop."""
    n, waves, amp, sway = spec
    keys = {SWIVEL: [], **{b: [] for b in CLOTH_BONES}}
    for f in range(n + 1):
        ph = 2 * math.pi * waves * f / n
        keys[SWIVEL].append((f, round(sway * math.sin(2 * math.pi * f / n), 5)))
        for r in range(ROWS):
            prev = 0.0
            for j in range(SEGS):
                s = (j + 0.5) / SEGS
                alpha = amp * (0.3 + 0.7 * s) * math.sin(ph - WAVE_K * s - ROW_LAG * (ROWS - 1 - r) / (ROWS - 1))
                keys[cloth_name(r, j)].append((f, round(alpha - prev, 5)))
                prev = alpha
    return keys


def frame_of(keys, f):
    """A joint state from animation keys at frame f (keys on every frame)."""
    return {j: dict(ks)[f] for j, ks in keys.items()}


# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}. stow (picked up): the
# legs fold, then the latch shuts; deploy (dropped): the latch opens, then the legs swing down and stand.
ANIMATIONS = {
    "stow": (False, "BEZIER", {**{leg: [(0, 0.0), (18, FOLD)] for leg in LEGS},
                               LATCH: [(0, 0.0), (16, 0.0), (24, LATCH_CLOSE)]}),
    "deploy": (False, "BEZIER", {LATCH: [(0, LATCH_CLOSE), (8, 0.0)],
                                 **{leg: [(0, FOLD), (4, FOLD), (22, 0.0)] for leg in LEGS}}),
    "wave": (True, "LINEAR", cloth_loop(WAVE)),
    "flutter": (True, "LINEAR", cloth_loop(FLUTTER)),
}
PREVIEW_STATES = {"stowed": dict(STOWED), "folding": {leg: FOLD / 2 for leg in LEGS},
                  "wave": frame_of(ANIMATIONS["wave"][2], 22),
                  "flutter": {**STOWED, **frame_of(ANIMATIONS["flutter"][2], 7)}}
PREVIEW_VIEWS = {"stowed": ["front_left", "right", "front"], "folding": ["front_left"],
                 "wave": ["front_left", "right", "top"], "flutter": ["front_left", "rear_right"]}
FK_TEST_STATE = {"LegBack": 40.0, "LegFrontLeft": 100.0, LATCH: 30.0, SWIVEL: 10.0, "Cloth1_2": 12.0, "Cloth2_0": -8.0}
SHOWCASE = ["wave", "wave", "stow", "flutter", "flutter", "flutter", "flutter", "deploy", "wave", "wave"]

# slot: (base colour, metallic, roughness, emission strength). The environment props' finish in Tensor's
# materials; M_Flag (the cloth) is emissive and the game tints it with the team's colour.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): the core, the collar
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): hub, shafts, legs, hook, arms
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black: the grip, the pads, every cut
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: pins, nuts, the luff rod, the latch
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # the cell windows, the shaft's ring and the beacon
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.22, 0.0),      # bushings, the motors' end caps
    "M_Titanium": ((0.29, 0.29, 0.30), 1.0, 0.45, 0.0),   # matte titanium: the hinge motors
    "M_Flag": ((0.82, 0.82, 0.80), 0.0, 0.6, 0.8),        # the cloth: emissive, the team's colour in play
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, TI, FLAG = SLOTS

# The framework below (kinematics, pistons, mesh kit, checks, rig, actions, export) is the
# item table's and weapon holder's generic code (the thruster's copy), unchanged.


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

    def flat(f):
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
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
    """A closed solid of revolution about the Z axis through (radius, z) stations, the first and
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
    """Turn a bmesh about the Z axis."""
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


def hex_ring(z, f, c, sy=1.0):
    """A chamfered hexagon at height z: flats at distance f facing azimuths 30 + 60k (the legs, the front and
    the back), each corner (at 60k, +-X among them) cut back c along both edges, then its y scaled by sy;
    12 points, counter-clockwise."""
    rc = f / math.cos(math.pi / 6)
    corners = [Vector((rc * math.cos(math.radians(60 * i)), rc * math.sin(math.radians(60 * i)), 0.0)) for i in range(6)]
    pts = []
    for i in range(6):
        q = corners[i]
        for other in (corners[i - 1], corners[(i + 1) % 6]):
            v = q + (other - q).normalized() * c
            pts.append((v.x, v.y * sy, z))
    return pts


# --------------------------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------------------------

def hook_profile():
    """The hook's side profile (y, z): an arm out of the core's front over the bar, a J down behind it, the
    pocket's round top (BAR) bearing on the bar, and the wall back to the core (the latch hinges in it); the
    pocket opens downward between the J and the wall."""
    by, bz, r = BAR
    arc = [(by + r * math.cos(math.radians(a)), bz + r * math.sin(math.radians(a))) for a in range(180, -1, -15)]
    root = -CORE[0] * CORE[1] + 0.010                  # buried in the core
    return ([(root, bz + 0.040), (by - 0.0095, bz + 0.040), (by - 0.0175, bz + 0.032), (by - 0.0175, bz - 0.012),
             (by - 0.0135, bz - 0.016), (by - r, bz - 0.012)] + arc + [(by + r, bz - 0.030), (root, bz - 0.030)])


GRIP_OUT = [(0.012, 0.700), (0.070, 0.705), (0.082, 0.717), (0.082, 0.818), (0.070, 0.830), (0.012, 0.832)]
GRIP_IN = [(0.0215, 0.722), (0.062, 0.722), (0.066, 0.726), (0.066, 0.808), (0.062, 0.812), (0.0215, 0.812)]
GRIP_W = 0.018


def pod_outline():
    """A side pod's outline (y, z): an elongated octagon."""
    hy, z0, z1, ch, _ = POD
    return [(-hy + ch, z0), (hy - ch, z0), (hy, z0 + ch), (hy, z1 - ch), (hy - ch, z1), (-hy + ch, z1), (-hy, z1 - ch),
            (-hy, z0 + ch)]


def hex_band(f0, f1, z0, z1):
    """A chamfered-hexagon annulus round the shaft (its sections, scaled) between flats f0 and f1, from z0 to z1."""
    f, c = SPINE[SHAFT][1], SPINE[SHAFT][2]
    outer = loft_bm([hex_ring(z0, f1, c * f1 / f), hex_ring(z1, f1, c * f1 / f)])
    inner = loft_bm([hex_ring(z0 - 0.01, f0, c * f0 / f), hex_ring(z1 + 0.01, f0, c * f0 / f)])
    return boolean(outer, [inner], "DIFFERENCE")


def build_spine(k):
    """The flag's unibody: the spine lofted through its chamfered-hexagon sections, with the hook, the D-grip,
    the cloth arms, the core's side pods and the legs' clevis lugs fused in, then machined: the grip's opening,
    a groove round the shaft for the lit ring, a pocket in each pod for its lit cell and slanted vents in the
    core's front and back. The hub and shafts grey, the core and collar off-white, the pods, hook, lugs and
    arms grey, the grip and every cut matte black."""
    # The core's tapers change its depth, so their quads are not flat: the loft is triangulated first, so the
    # loft, the fused solid and the machined one share their triangles (the faces are told apart by distance).
    width = 2 * max([abs(q[i]) for sec in SPINE for q in hex_ring(*sec) for i in (0, 1)] + [POD[4]])
    if width > POLE_W + 1e-9:  # (user) the pole, its pods included, is at most 5 cm across
        raise SystemExit(f"[{NAME}] the pole is {1000 * width:.1f} mm across (over {1000 * POLE_W:.0f} mm)")
    solid = loft_bm([hex_ring(*sec) for sec in SPINE])
    bmesh.ops.triangulate(solid, faces=solid.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    fused = [(slab_bm([(0, y, z) for y, z in hook_profile()], 2 * HOOK_W, (1, 0, 0)), SEC),   # the hook
             (slab_bm([(0, y, z) for y, z in GRIP_OUT], GRIP_W, (1, 0, 0)), FRM)]             # the grip (rubber)
    xp = POD[4]
    fused += [(slab_bm([(s * xp / 2, y, z) for y, z in pod_outline()], xp, (1, 0, 0)), SEC) for s in (1, -1)]
    for (z0, z1), root in zip(ARM_Z, (0.012, 0.008)):  # the cloth arms, round about the rod's bushings
        fused.append((plate_bm(keyhole([(-0.010, root), (0.010, root)], (0, ROD[0]), 0.012, 12),
                               lambda u, v, z=(z0 + z1) / 2: (u, v, z), z1 - z0, (0, 0, 1)), SEC))
    w0, th, r_end, r_root, h_root = LUG
    for az in LEG_AZ.values():  # each leg's clevis: two cheeks, round about the pivot, rooted in the hub
        u, a, _, _, p = leg_axes(az)
        for sgn in (1, -1):
            fused.append((plate_bm(keyhole([(r_root, PIVOT_Z - h_root), (r_root, PIVOT_Z + h_root)], (PIVOT_R, PIVOT_Z),
                                           r_end, 12),
                                   lambda rr, z, sgn=sgn: tuple(u * rr + a * (sgn * (w0 + th / 2)) + Vector((0, 0, z))),
                                   th, tuple(a)), SEC))
    # each face takes the colour of the surface it lies on (the loft's by height, a fused part's its own), not of
    # where it is: by position, a pod's or an arm's faces next to the core and the collar read as theirs
    spine = BVHTree.FromBMesh(solid)
    sources = [(BVHTree.FromBMesh(bm), mat) for bm, mat in fused]
    solid = boolean(solid, [bm for bm, _ in fused], "UNION")
    cutters = [slab_bm([(0, y, z) for y, z in GRIP_IN], 0.05, (1, 0, 0))]
    f_sh = SPINE[SHAFT][1]
    cutters.append(hex_band(f_sh - RING[2], f_sh + 0.02, RING[0], RING[1]))
    hc, z0c, z1c, dc = CELL
    cutters += [block_bm((s * xp, 0, (z0c + z1c) / 2), (2 * dc, 2 * hc, z1c - z0c)) for s in (1, -1)]
    front = CORE[0] * CORE[1]
    for s, starts in ((-1, [0.805 + 0.016 * i for i in range(5)] + [0.895 + 0.016 * i for i in range(5)]),
                      (1, [0.872 + 0.016 * i for i in range(5)])):   # the front's vents over the hook, the back's over the arm
        cutters += lean_slots((0, s * front, 0), (0, s, 0), (0, 0, 1), (1, 0, 0), starts, 0.007, -0.006, 0.006,
                              0.004, 0.003)

    def material(f, c, cut):
        if cut:
            return FRM
        if spine.find_nearest(c)[3] > 2e-4:  # on a fused part: the nearest one's colour
            return min(((bvh.find_nearest(c)[3], mat) for bvh, mat in sources), key=lambda e: e[0])[1]
        if c.z < SPINE[SHAFT][0] + 5e-4 or SPINE[UPPER][0] + 5e-4 < c.z < SPINE[UPPER + 1][0] + 5e-4:
            return SEC                   # the hub, the shaft and the upper shaft; the tapers into the core and
                                         # the collar are theirs
        return PRI                       # the core and the collar

    machine(k, solid, cutters, "Root", material)
    machine(k, loft_bm([hex_ring(*sec) for sec in BEACON]), [], "Root", lambda f, c, cut: EMI)
    # the lit ring in its groove (its face 1 mm under the shaft's flats, 0.5 mm into the groove's floor), the
    # lit cells in the pods' pockets (1 mm under the faces), a bolt on each pod's face over and under its cell
    machine(k, hex_band(f_sh - RING[2] - 0.0005, f_sh - 0.001, RING[0] + 0.0005, RING[1] - 0.0005), [], "Root",
            lambda f, c, cut: EMI)
    for s in (1, -1):
        k.box((s * (xp - dc + 0.00075), 0, (z0c + z1c) / 2), (0.0025, 2 * hc - 0.002, z1c - z0c - 0.002), "Root", EMI)
        for z in (z0c - 0.012, z1c + 0.012):
            bolt(k, (s * xp, 0.0, z), (s, 0, 0), "Root", r=0.003)


def build_hub_fittings(k):
    """At each leg's hinge: the titanium hinge motor on the + cheek's outer face (its bronze end cap outside),
    coaxial with the pin (the motor's housing is the bearing; the pin and knuckle turn in it)."""
    for az in LEG_AZ.values():
        _, a, _, _, p = leg_axes(az)
        k.cyl(p + a * MOTOR[0], p + a * MOTOR[1], MOTOR[2], "Root", TI, segs=12)
        k.cyl(p + a * (MOTOR[1] - 0.001), p + a * (MOTOR[1] + 0.002), MOTOR[2] * 0.6, "Root", BRZ, segs=10)


def leg_ring(p, a, d, e, s, w, t, ch):
    """A leg's chamfered section at s along it: w along the pin, t across."""
    pts = [(w / 2, t / 2 - ch), (w / 2 - ch, t / 2), (-w / 2 + ch, t / 2), (-w / 2, t / 2 - ch), (-w / 2, -t / 2 + ch),
           (-w / 2 + ch, -t / 2), (w / 2 - ch, -t / 2), (w / 2, -t / 2 + ch)]
    c = p + d * s
    return [tuple(c + a * x + e * y) for x, y in pts]


def build_legs(k):
    """Each leg: one grey unibody (a knuckle round its pin, a tapering shaft with a groove down its outer
    face, and an ankle standing on the pad), a black rubber pad whose sole is on the ground when deployed,
    and its stainless pin through the lug's cheeks into the motor, nutted on the other cheek."""
    (w0, t0), (w1, t1) = LEG_SECTION
    for name, az in LEG_AZ.items():
        _, a, d, e, p = leg_axes(az)
        shaft = loft_bm([leg_ring(p, a, d, e, 0.0, w0, t0, 0.0025), leg_ring(p, a, d, e, 0.05, w0, t0, 0.0025),
                         leg_ring(p, a, d, e, LEG_L, w1, t1, 0.002)])
        t = p + d * LEG_L
        extra = [rod_bm(p - a * KNUCKLE[1], p + a * KNUCKLE[1], KNUCKLE[0], 12),
                 rod_bm((t.x, t.y, PAD[1] - 0.001), (t.x, t.y, t.z + 0.006), 0.009, 10)]
        solid = boolean(shaft, extra, "UNION")

        def thick(s):
            return t0 if s < 0.05 else t0 + (t1 - t0) * (s - 0.05) / (LEG_L - 0.05)
        s0, s1 = 0.055, LEG_L - 0.03
        groove = slab_bm([tuple(p + d * s + a * x + e * (thick(s) / 2)) for s, x in ((s0, -0.0025), (s1, -0.0025),
                                                                                    (s1, 0.0025), (s0, 0.0025))],
                         0.004, tuple(e))
        machine(k, solid, [groove], name, lambda f, c, cut: FRM if cut else SEC)
        k.cyl((t.x, t.y, 0.0), (t.x, t.y, PAD[1]), PAD[0], name, FRM, segs=10)
        k.cyl(p - a * PIN[0], p + a * PIN[1], PIN[2], name, JNT, segs=8)                 # the pin (rotor)
        nut0 = LUG[0] + LUG[1] + 0.0005                                                  # 0.5 mm off the - cheek (it turns)
        k.cyl(p - a * nut0, p - a * (nut0 + NUT[0]), NUT[1], name, JNT, segs=6)          # ...and its nut


def build_latch(k):
    """The latch (authored open, hanging): two stainless side plates outside the hook's faces, round about the
    pivot, joined by a crossbar that closes under the J; its pin through the bronze bushing in the hook's wall."""
    yp, zp = LATCH_P
    outline = hull2d([(yp + 0.0065 * math.cos(math.radians(a)), zp + 0.0065 * math.sin(math.radians(a))) for a in range(0, 360, 45)]
                     + [(yp + 0.004 * math.cos(math.radians(a)), zp - LATCH_R + 0.004 * math.sin(math.radians(a)))
                        for a in range(0, 360, 45)])
    x0, th = HOOK_W + 0.0015, 0.006                  # the plates 1 mm clear of the bushing's ends
    plates = [plate_bm(outline, lambda u, v, x=s * (x0 + th / 2): (x, u, v), th, (1, 0, 0)) for s in (1, -1)]
    solid = boolean(plates[0], [plates[1], block_bm((0, yp, zp - LATCH_R), (2 * (x0 + th), 0.008, 0.008))], "UNION")
    machine(k, solid, [], LATCH, lambda f, c, cut: JNT)
    k.cyl((-(x0 + th + 0.002), yp, zp), (x0 + th + 0.002, yp, zp), 0.0032, LATCH, JNT, segs=8)
    k.cyl((-HOOK_W - 0.0005, yp, zp), (HOOK_W + 0.0005, yp, zp), 0.0055, "Root", BRZ, segs=10)


def build_swivel(k):
    """The luff rod (stainless, the swivel's rotor) through bronze bushings in the arms' eyes, its ends
    showing."""
    y, r = ROD
    k.cyl((0, y, ARM_Z[0][0] - 0.002), (0, y, ARM_Z[1][1] + 0.002), r, SWIVEL, JNT, segs=8)
    for z0, z1 in ARM_Z:
        k.cyl((0, y, z0 - 0.001), (0, y, z1 + 0.001), BUSH_R, "Root", BRZ, segs=12)


def build_all(k, pistons, joints):
    build_spine(k)
    build_hub_fittings(k)
    build_legs(k)
    build_latch(k)
    build_swivel(k)


# --------------------------------------------------------------------------------------------
# The cloth
# --------------------------------------------------------------------------------------------

def cloth_weights(y, z):
    """A sheet vertex's weights: linear between the two rows it lies between, and between the two segments
    whose middles it lies between (a vertex on a hinge moves alike with both), so the sheet bends smoothly."""
    y0, fly, zb, zt = CLOTH
    fz = (z - zb) / (zt - zb) * (ROWS - 1)
    r0 = min(int(fz), ROWS - 2)
    tz = fz - r0
    seg = fly / SEGS
    mids = [y0 + seg * (j + 0.5) for j in range(SEGS)]
    if y <= mids[0]:
        cols = [(0, 1.0)]
    elif y >= mids[-1]:
        cols = [(SEGS - 1, 1.0)]
    else:
        j = min(int((y - mids[0]) / seg), SEGS - 2)
        tc = (y - mids[j]) / seg
        cols = [(j, 1 - tc), (j + 1, tc)]
    w = {}
    for r, wr in ((r0, 1 - tz), (r0 + 1, tz)):
        for j, wc in cols:
            if wr * wc > 1e-6:
                w[cloth_name(r, j)] = wr * wc
    return w


def build_cloth(rig):
    """SK_CtfFlagCloth: the sheet (a grid in the YZ plane, flying from the luff to the fly, skinned smoothly to
    the cloth chains) and its sleeve round the luff rod (rigid on the swivel), one emissive M_Flag slot, double-
    sided. UVs: u 0 at the luff to 1 at the fly, v 0 at the bottom edge to 1 at the top; the sleeve on u = 0.
    Returns the object, the rest vertices and weights, and the sheet's edges (for the checks)."""
    y0, fly, zb, zt = CLOTH
    nu, nv = GRID
    bm = bmesh.new()
    deform = bm.verts.layers.deform.verify()
    uvl = bm.loops.layers.uv.new("UVMap")
    groups = [SWIVEL] + CLOTH_BONES
    gi = {g: i for i, g in enumerate(groups)}
    uv, weights, grid = {}, [], []
    for i in range(nu + 1):
        col = []
        for j in range(nv + 1):
            y, z = y0 + fly * i / nu, zb + (zt - zb) * j / nv
            v = bm.verts.new((0.0, y, z))
            w = cloth_weights(y, z)
            for b, x in w.items():
                v[deform][gi[b]] = x
            uv[v] = (i / nu, j / nv)
            weights.append(w)
            col.append(v)
        grid.append(col)
    edges = []
    for i in range(nu + 1):
        for j in range(nv + 1):
            a = i * (nv + 1) + j
            if i < nu:
                edges.append((a, a + nv + 1))
            if j < nv:
                edges.append((a, a + 1))
    for i in range(nu):
        for j in range(nv):
            f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            for loop in f.loops:
                loop[uvl].uv = uv[loop.vert]
    n_sleeve = 8
    rings = []
    for z in (zb, zt):
        ring = []
        for s in range(n_sleeve):
            ang = 2 * math.pi * (s + 0.5) / n_sleeve
            v = bm.verts.new((SLEEVE_R * math.cos(ang), ROD[0] + SLEEVE_R * math.sin(ang), z))
            v[deform][gi[SWIVEL]] = 1.0
            weights.append({SWIVEL: 1.0})
            uv[v] = (0.0, (z - zb) / (zt - zb))
            ring.append(v)
        rings.append(ring)
    for s in range(n_sleeve):
        t = (s + 1) % n_sleeve
        f = bm.faces.new((rings[0][s], rings[0][t], rings[1][t], rings[1][s]))
        for loop in f.loops:
            loop[uvl].uv = uv[loop.vert]
    rest = [v.co.copy() for v in bm.verts]
    mesh = bpy.data.meshes.new(f"SK_{TITLE}Cloth_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"SK_{TITLE}Cloth", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for g in groups:
        obj.vertex_groups.new(name=g)
    mat = bpy.data.materials[FLAG]
    mat.use_backface_culling = False
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    skin(obj, rig)
    return obj, rest, weights, edges


def cloth_states():
    """The cloth's states for its checks: every frame of wave (standing) and flutter (stowed, as carried), and
    every sixth frame with the swivel at its limits."""
    out = []
    for name, rigid in (("wave", {}), ("flutter", STOWED)):
        keys = ANIMATIONS[name][2]
        n = max(f for ks in keys.values() for f, _ in ks)
        out += [(f"{name} frame {f}", {**rigid, **frame_of(keys, f)}) for f in range(n + 1)]
    return out + [(f"{tag}, swivel {s:+.0f}", {**st, SWIVEL: s}) for tag, st in out[::6]
                  for s in (-SWIVEL_LIMIT, SWIVEL_LIMIT)]


def deform(joints, state, rest, weights):
    m = fk(joints, expand(state))
    return [sum(((m[b] @ v) * w for b, w in wt.items()), Vector()) for v, wt in zip(rest, weights)]


def check_cloth(kit, joints, rest, weights, edges, tensor_bvh, carry):
    """In every cloth state: no vertex of the cloth comes within 2 mm of a rigid part (the luff rod aside:
    the sleeve rides it), rises over HEIGHT, or (stowed, on Tensor's back) comes within 1 cm of him; and no
    edge of the sheet stretches or shrinks by more than STRETCH."""
    parts = [p for p in all_parts(kit) if p.bone != SWIVEL]
    rest_len = [(rest[a] - rest[b]).length for a, b in edges]
    problems, worst, nearest = [], 0.0, 1.0
    for tag, state in cloth_states():
        m = fk(joints, expand(state))
        inv = {b: mm.inverted() for b, mm in m.items()}
        pts = deform(joints, state, rest, weights)
        for i, p in enumerate(pts):
            if p.z > HEIGHT + 1e-6:
                problems.append(f"cloth vertex {i} over {HEIGHT} m at {tag}")
            for q in parts:  # (a hit confirmed by distance or by two rays: one parity ray can graze an edge)
                lp = inv[q.bone] @ p
                if q.hits(lp, 0.002) and (q.bvh.find_nearest(lp)[3] < 0.002 or q.buried(lp)):
                    problems.append(f"cloth vertex {i} meets {q.bone} (line {q.line}) at {tag}")
                    break
            if state.get(LATCH) == LATCH_CLOSE:
                d = tensor_bvh.find_nearest(carry @ p)[3]
                nearest = min(nearest, d)
                if d < 0.01:
                    problems.append(f"cloth vertex {i} within 1 cm of Tensor at {tag}")
        for (a, b), l0 in zip(edges, rest_len):
            worst = max(worst, abs((pts[a] - pts[b]).length / l0 - 1))
    if worst > STRETCH:
        problems.append(f"the sheet stretches {100 * worst:.1f}% (over {100 * STRETCH:.0f}%)")
    if problems:
        raise SystemExit(f"[{NAME}] cloth check failed:\n  " + "\n  ".join(list(dict.fromkeys(problems))[:40]))
    return worst, nearest


# --------------------------------------------------------------------------------------------
# The flag's checks
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """The legs over their whole range with the latch open, half and shut, and the swivel at its limits."""
    out = []
    for i in range(9):
        v = FOLD * i / 8
        out += [(f"legs {v:.0f} latch {x:.0f}", {**{leg: v for leg in LEGS}, LATCH: x})
                for x in (0.0, LATCH_CLOSE / 2, LATCH_CLOSE)]
    return out + [(f"swivel {s:+.0f}", {SWIVEL: s}) for s in (-SWIVEL_LIMIT, SWIVEL_LIMIT)]


def check_envelope(kit, joints, states):
    """Standing, the pads' soles are on the ground (z = 0); in every state nothing goes under the ground or
    rises over HEIGHT; stowed (legs folded), the flag is no longer than STOW_LENGTH."""
    problems = []
    low = min(v.z for p in all_parts(kit) for v in p.verts)
    if abs(low) > 1e-6:
        problems.append(f"lowest point at z {low:.4f}: the soles are not on the ground")
    top = 0.0
    for tag, state in [("rest", {})] + states:
        m = fk(joints, expand(state))
        for part in all_parts(kit):
            zs = [(m[part.bone] @ v).z for v in part.verts]
            top = max(top, max(zs))
            if min(zs) < -1e-6 or max(zs) > HEIGHT + 1e-6:
                problems.append(f"{part.bone} (line {part.line}) leaves 0..{HEIGHT} m at {tag}")
    m = fk(joints, expand(STOWED))
    zs = [(m[p.bone] @ v).z for p in all_parts(kit) for v in p.verts]
    length = max(zs) - min(zs)
    if length > STOW_LENGTH + 1e-6:
        problems.append(f"stowed, the flag is {length:.4f} m long (over {STOW_LENGTH} m)")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(dict.fromkeys(problems)))
    return top, length


def gizmo_matrix(origin, fwd, up):
    """A gizmo's frame: its local +Y forward, +Z up (in glTF / Godot -Z forward, +Y up)."""
    fwd, up = Vector(fwd), Vector(up)
    m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
    m.translation = origin
    return m


def load_tensor():
    """Tensor as built (models/characters/tensor): his body's and default head's world-space vertices and faces
    at rest (he is rigid and authored at rest), for the carry checks, and his FlagMount gizmo (tensor_rig.json).
    Returns them and the carry: the flag's transform on his back, BackMount matched to FlagMount, exactly as
    the game attaches it."""
    if not TENSOR_BLEND.exists() or not TENSOR_RIG.exists():
        raise SystemExit(f"[{NAME}] {TENSOR_BLEND} not found - run Tensor's model.py first (the carry is fitted to him)")
    mount = next((g for g in json.loads(TENSOR_RIG.read_text()).get("gizmos", []) if g["name"] == "FlagMount"), None)
    if mount is None:
        raise SystemExit(f"[{NAME}] {TENSOR_RIG} has no FlagMount gizmo - rebuild Tensor")
    back = next(g for g in gizmo_specs() if g[0] == "BackMount")
    carry = gizmo_matrix(mount["origin"], mount["forward"], mount["up"]) @ gizmo_matrix(*back[2:]).inverted()
    names = ["SK_Tensor", "SK_TensorHeadProjector"]
    with bpy.data.libraries.load(str(TENSOR_BLEND), link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    verts, polys = [], []
    for obj in dst.objects:
        base = len(verts)
        verts += [obj.matrix_basis @ v.co for v in obj.data.vertices]
        polys += [[base + i for i in p.vertices] for p in obj.data.polygons]
    if len(dst.objects) != len(names):
        raise SystemExit(f"[{NAME}] {TENSOR_BLEND} lacks {names}")
    return verts, polys, carry, mount


def in_hook(v):
    """Is a point (the flag's own frame) in the hook and latch, the only parts that may meet Tensor?"""
    return v.y < -CORE[0] * CORE[1] + 0.004 and BAR[1] - 0.07 < v.z < BAR[1] + 0.05


def check_carry(kit, joints, tensor_bvh, carry):
    """Stowed on Tensor's back (BackMount on his FlagMount, the handle bar's axis): nothing of the flag enters
    him; the hook's pocket bears on the bar (within 3 mm of it along its top); the hook and latch keep 0.5 mm
    from him and everything else 5 mm."""
    m = fk(joints, expand(STOWED))
    problems, clear = [], 1.0
    for part in all_parts(kit):
        mm = carry @ m[part.bone]
        if part.moved(mm).bvh.overlap(tensor_bvh):
            problems.append(f"{part.bone} (line {part.line}) enters Tensor")
        for v in part.verts:
            lv = m[part.bone] @ v
            d = tensor_bvh.find_nearest(carry @ lv)[3]
            need = 0.0005 if in_hook(lv) else 0.005
            if not in_hook(lv):
                clear = min(clear, d)
            if d < need:
                problems.append(f"{part.bone} (line {part.line}) within {1000 * need:.1f} mm of Tensor "
                                f"at {tuple(round(c, 3) for c in lv)}")
                break
    by, bz, r = BAR
    bearing = max(tensor_bvh.find_nearest(carry @ Vector((x, by, bz + r)))[3] for x in (-0.015, 0.0, 0.015))
    if bearing > 0.003:
        problems.append(f"the hook's pocket is {1000 * bearing:.1f} mm off the handle bar")
    if problems:
        raise SystemExit(f"[{NAME}] carry check failed:\n  " + "\n  ".join(dict.fromkeys(problems)))
    return bearing, clear


# --------------------------------------------------------------------------------------------
# Gizmos, rig data, main
# --------------------------------------------------------------------------------------------

def place_on_bone(obj, rig, bone_name, m):
    """Parent obj to a bone and give it the world matrix m (at rest)."""
    bone = rig.data.bones[bone_name]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    obj.matrix_basis = m
    return obj


def gizmo_specs():
    """(name, bone, origin, forward, up): GroundMount on the ground under the spine (where the flag stands),
    BackMount at mid-height on the hook's pocket axis (where Tensor's handle bar lies when carried); both face
    the flag's front, up its spine."""
    return [("GroundMount", "Root", (0.0, 0.0, 0.0), FWD, UP),
            ("BackMount", "Root", (0.0, BAR[0], BAR[1]), FWD, UP)]


def build_gizmos(rig):
    objs = []
    for name, bone, origin, fwd, up in gizmo_specs():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type, e.empty_display_size = "ARROWS", 0.1
        bpy.context.scene.collection.objects.link(e)
        fwd, up = Vector(fwd), Vector(up)
        m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
        m.translation = origin
        objs.append(place_on_bone(e, rig, bone, m))
    return objs


def write_rig_json(joints, tris, cloth_tris, top, length, stretch, bearing, flag_mount):
    def vec(v):
        return [round(c, 4) for c in v]

    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, front -Y, left +X; the origin is on the ground under the spine (GroundMount). "
                 "glTF/Godot: (x, z, -y). Hinges turn about their bones' local X (degrees).",
        "rest": "standing: legs deployed, latch open, cloth flat",
        "size_m": {"height_standing": round(top, 4), "length_stowed": round(length, 4), "limits": [HEIGHT, STOW_LENGTH],
                   "pole_width_max": POLE_W, "foot_reach": FOOT_R, "pole_bottom_standing": SPINE[0][0],
                   "cloth": {"fly": CLOTH[1], "height": round(CLOTH[3] - CLOTH[2], 4)}},
        "mounts": {
            "ground": {"gizmo": "GroundMount", "note": "stand the flag with GroundMount on the ground (its legs "
                       "deployed: play deploy, or the rest pose); its three pads' soles are at its origin's height"},
            "back": {"gizmo": "BackMount", "note": "play stow, then match BackMount to the carrier's FlagMount "
                     "(position and axes; attach under a BoneAttachment3D on his UpperChest): the hook's pocket sits on "
                     "the grab handle bar on Tensor's power pack and the latch shuts under it; the flag keeps his "
                     "orientation (its front toward his back, the cloth flying behind him)",
                     "tensor": {"gizmo": "FlagMount", "bone": flag_mount["bone"], "origin_rest_m": flag_mount["origin"],
                                "hook_to_bar_gap_m": round(bearing, 4)}}},
        "gizmos": [{"name": n, "bone": b, "origin": vec(o), "forward": vec(f), "up": vec(u),
                    "godot": "-Z toward the flag's front, +Y up its spine"} for n, b, o, f, u in gizmo_specs()],
        "cloth": {"object": f"SK_{TITLE}Cloth", "material": FLAG, "triangles": cloth_tris,
                  "shader": "emissive; tint it with the team's colour in game (double-sided)",
                  "uv": "u 0 at the luff (the rod) to 1 at the fly, v 0 at the bottom edge to 1 at the top; the sleeve "
                        "round the rod on u = 0",
                  "skinning": "the sheet is smooth-skinned (up to 4 bone influences a vertex, bilinear across the rows "
                              "and segments); the sleeve rigid on Swivel",
                  "bones": {"rows": ROWS, "segments": SEGS, "names": "Cloth<row>_<segment>, row 0 at the bottom edge, "
                            "segment 0 at the luff", "hinge": "about +Z (vertical); + turns toward -X",
                            "limits_deg": [-CLOTH_LIMIT, CLOTH_LIMIT]},
                  "max_stretch": round(stretch, 4)},
        "team_tinted": [FLAG, EMI],
        "materials_note": "the environment props' finish in Tensor's materials (off-white and grey paint, matte black, "
                          "stainless steel, bronze, titanium); M_Flag (the cloth) and M_Emissive (the strips and "
                          "the beacon) are the ones to tint per team",
        "materials": [s for s in SLOTS if s != FLAG],
        "triangles": tris,
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "usage": "Standing (at its base or dropped): loop wave. Picked up: play stow (the legs fold, the latch "
                 "shuts), attach BackMount to the carrier and loop flutter. Dropped: detach, stand it on the ground "
                 "at GroundMount and play deploy, then loop wave. The cloth animations key only the Swivel and "
                 "Cloth bones and stow/deploy only the legs and the latch, so they layer.",
    }
    RIG_JSON_PATH.write_text(json.dumps(data, indent=2))


def main():
    *tensor, carry, flag_mount = load_tensor()
    reset_scene()
    build_materials()
    joints = resolve_joints()
    rigid = {n: j for n, j in joints.items() if n not in CLOTH_BONES}
    pistons = resolve_pistons(joints)
    check_states(joints)
    rig = build_rig(joints, pistons)
    check_rig_fk(rig, joints)
    actions = build_actions(rig, joints, pistons)

    kit = Kit()
    build_all(kit, pistons, rigid)
    states = action_states(actions, rigid) + sweep_states(rigid)
    top, length = check_envelope(kit, rigid, states)
    check_connectivity(kit, rigid, pistons)
    check_joint_alignment(kit, rigid)
    check_motion(kit, rigid, states)
    tensor_bvh = BVHTree.FromPolygons(*tensor)
    bearing, clear = check_carry(kit, rigid, tensor_bvh, carry)
    print(f"[{NAME}] checks passed ({len(states)} motion states); {top:.3f} m tall standing, {length:.3f} m stowed; "
          f"legs fold {FOLD:.1f} deg "
          f"(deployed {PHI:.1f} deg out); carried: hook {1000 * bearing:.1f} mm over the bar, the rest "
          f"{1000 * clear:.1f} mm clear of Tensor")

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(rigid))
    check_coplanar(body)
    skin(body, rig)
    if "--no-cull" not in sys.argv:
        cull_unseen(body, rig, rigid, pistons, states, (-1e-4, -1e-4), (1e-4, 1e-4), PLATFORM_FRAME)
    body.data.materials.pop(index=SLOTS.index(FLAG))
    unwrap(body)
    cloth, rest, weights, edges = build_cloth(rig)
    stretch, near = check_cloth(kit, joints, rest, weights, edges, tensor_bvh, carry)
    tris, cloth_tris = triangles(body), triangles(cloth)
    print(f"[{NAME}] cloth: {len(cloth_states())} states clear, stretch {100 * stretch:.2f}%, carried "
          f"{1000 * near:.0f} mm from Tensor")
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET}); cloth: {cloth_tris} tris (budget {CLOTH_BUDGET})")
    if tris > TRI_BUDGET and "--no-cull" not in sys.argv:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")
    if cloth_tris > CLOTH_BUDGET:
        raise SystemExit(f"[{NAME}] cloth over its triangle budget: {cloth_tris}")

    gizmos = build_gizmos(rig)
    export([rig, body, cloth, *gizmos], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, tris, cloth_tris, top, length, stretch, bearing, flag_mount)

    def pose_entry(jname, v):
        return {"rot": [v, 0, 0]} if joints[jname].kind == "hinge" else {"loc": [0, v, 0]}

    rig["preview_poses"] = json.dumps({s: {j: pose_entry(j, v) for j, v in expand(st).items()}
                                       for s, st in PREVIEW_STATES.items()})
    rig["preview_pose_views"] = json.dumps(PREVIEW_VIEWS)
    scene = bpy.context.scene
    scene["preview_actions"] = json.dumps(SHOWCASE)
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
