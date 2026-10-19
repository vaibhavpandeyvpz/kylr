"""Thruster - a 5 m lift thruster for KYLR's floating platforms, modelled, rigged and animated
from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/environments/thruster/model.py

Produces, next to this script:
    thruster.blend             source scene, opened by preview.py and animate.py
    thruster.glb / .fbx        SK_Thruster (the thruster) and SK_ThrusterExhaust (the emissive lining of
                               the nozzle's bore, for the game's shader) skinned to RIG_Thruster, the
                               gizmos ExhaustOrigin and NozzleExit, and the actions idle and sweep
                               (looped) and vector_front / vector_back / vector_left / vector_right
    thruster_rig.json          the joints and their ranges, the actuators, the animations, the exhaust
                               surface and the gizmos

Design: a round thruster 5 m across that hangs under a floating platform, its top face bolted to the
platform's underside, the exhaust pointing down; many of them hold a map piece in the air. It is two
lofted unibodies (the weapons' language) on a Cardan gimbal. The body: a grey mounting flange, a grey
band of status lamps, and an off-white drum with four stainless steel propellant tanks sunk in pockets
on the diagonals, eight grey ribs under the lamps, slanted vents, grey doubler pods over the hangers, two hanger lugs fused under it at +-X and two channels up its sides at
+-Y for the pitch actuators. The engine (the nozzle): an off-white domed top and collar, then a titanium
bell with six ribs and a notched exit band, its bore lined with the exhaust surface (SK_ThrusterExhaust: its own mesh and
M_Exhaust slot, yellow and emissive in previews, for the game's flame shader).

Thrust vectoring: a matte black gimbal ring turns about X on trunnion pins in the hanger lugs (pitch),
and the nozzle turns about Y on trunnion pins in the ring's bosses (yaw), both axes crossing on the
thruster's axis. Four hydraulic actuators drive it: the pitch pair from clevises in the body's channels
down to lugs on the ring's top at +-Y, the yaw pair from lugs under the ring at +-X down to clevises
on the bell. Map-generic finish in Tensor's materials.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a rod leaves its
barrel, a hinge isn't coaxial with its bearings, anything collides through any animation frame or
across the gimbal's whole range, an actuator passes through anything, or the thruster leaves its
envelope (a 5 m round, 5 m deep).
Conventions: 1 unit = 1 m, Z up, front = -Y (its left is +X). The origin is at the centre of the top
mount face, which meets the platform's underside at z = 0; the thruster hangs below it. Rest pose = the
nozzle straight down.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Exhaust': 'Emissive',
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

NAME = "thruster"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # Thruster

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored by the kit)

RADIUS, DEPTH = 2.5, 5.0               # the envelope: 5 m across, hanging at most 5 m under the platform
N = 32                                 # sides of the round shells; their faces are centred on the axes
N_RING = 24                            # ...and of the gimbal ring
Z_P = -2.75                            # the gimbal's centre: both hinge axes cross here, on the thruster's axis
# The body's sections, top down (z, radius at the corners): the mounting flange (its top on the platform),
# its underside, a neck flaring out into the lamp band, a step in to the drum, and a chamfer down to its
# flat underside.
BODY = [(0.0, 2.50), (-0.10, 2.50), (-0.12, 2.46), (-0.12, 2.26), (-0.22, 2.36), (-0.44, 2.36), (-0.50, 2.30),
        (-1.88, 2.30), (-2.03, 2.15)]
Z_U = BODY[-1][0]                      # the body's flat underside
TANK = (2.16, 0.26, 0.12, -0.60, -1.76, 0.10)  # propellant tanks on the diagonals: axis radius, radius, neck radius, top, bottom, end height
POCKET = (0.34, 1.88)                  # the tanks' pockets: half-width, floor radius
CHANNEL = (0.075, 1.70, -1.08)         # the pitch actuators' channels at +-Y: half-width, inner wall radius, top z
HANGER = (1.965, 2.085, 0.20, 0.15)    # the hanger lugs at +-X: inner and outer |x|, half-width at the root, round end radius
BUSHING = (2.11, 0.10)                 # bronze bushing on each hanger's outer face: outer |x|, radius
RING = [(1.75, -0.10), (1.75, 0.10), (1.93, 0.10), (1.96, 0.07), (1.96, -0.07), (1.93, -0.10)]  # the gimbal ring's section: (radius, height over Z_P)
BOSS = (1.76, 1.955, 0.12)             # the ring's four trunnion bosses: from, to (radially), radius
TRUNNION_PIN = (0.05, 0.07, 0.02)      # trunnion pins: radius, nut radius, nut height
# The nozzle's section (radius, height over Z_P): outside from the domed top down the collar, the waist,
# the bell and the raised exit band; then the bore back up to the chamber's top (the injector face).
NOZZLE_OUT = [(1.30, 0.35), (1.50, 0.15), (1.50, -0.15), (1.36, -0.40), (1.36, -0.55), (1.68, -1.66), (1.76, -1.70),
              (1.76, -1.86)]
NOZZLE_IN = [(1.62, -1.86), (1.20, -0.62), (0.95, -0.28)]
NOZZLE_TRUNNION = (1.40, 1.73, 0.10)   # the nozzle's trunnions at +-Y: from, to (|y|), radius
RIB = (0.06, 0.045)                    # the bell's six ribs (on the diagonals and under the trunnions): width, standing proud
NOTCH = (0.06, 0.08, 1.70)             # the exit band's eight notches: half-width, height, floor radius
DRUM_RIB = (0.035, 0.045)              # the drum's eight grey ribs, under the lamps: half-width, standing proud
POD = (0.20, -1.12)                    # the grey doubler pods over the hangers at +-X: half-width, top z
ACT_R = 0.06                           # the actuators' barrel radius
PITCH_A, PITCH_B = (1.845, 1.55), (1.845, 0.23)    # pitch actuators at +-Y: (|y|, height over Z_P) of the barrel's and the rod's eyes
YAW_A, YAW_B = (1.845, -0.23), (1.78, -1.60)       # yaw actuators at +-X: (|x|, height over Z_P) of the barrel's and the rod's eyes
CHEEK = (0.066, 0.10, 0.085)           # clevis cheeks either side of an eye: inner and outer offset along the pin, round end radius
EYE_PIN = 0.018                        # the actuators' eye pins
TILT = 10.0                            # the gimbal's range, each axis, degrees
IDLE = (150, 2.0, 1.5)                 # idle: frames per loop, pitch and yaw amplitude (degrees)
SWEEP = 120                            # sweep: frames per loop over the whole range
PREVIEW_FRAME = {"lo": [-2.55, -2.55, -5.0], "hi": [2.55, 2.55, 0.02]}
# === END SPEC ===

GIMBAL, NOZZLE = "GimbalRing", "Nozzle"
PITCH = [("ActuatorFront", -1), ("ActuatorBack", 1)]     # at -Y (front) and +Y
YAW = [("ActuatorLeft", 1), ("ActuatorRight", -1)]       # at +X (the thruster's left) and -X
# The cull's level surface, far above and facing down: nothing of the thruster is hidden by the platform,
# so its top face stays (the thruster reads whole in previews and wherever a platform's edge shows it).
PLATFORM_FRAME = Matrix.Translation((0, 0, 50.0)) @ Matrix.Rotation(math.pi, 4, "X")
GROUPS = ()


def hatch(a, b, n):  # the pistons' coordinates are world coordinates here
    return Vector((a, b, n))


def joint_specs():
    x_bush = (HANGER[1] + BUSHING[0]) / 2
    y_boss = (BOSS[0] + BOSS[1]) / 2
    return [("Root", None, "fixed", (0, 0, 0), UP, UP, None),
            # pitch: the ring about +X, its pivot in the +X hanger's bushing; + swings the exhaust to the back (+Y)
            (GIMBAL, "Root", "hinge", (x_bush, 0, Z_P), (1, 0, 0), DOWN, (-TILT, TILT)),
            # yaw: the nozzle about +Y, its pivot in the ring's +Y boss; + swings the exhaust to the right (-X)
            (NOZZLE, GIMBAL, "hinge", (0, y_boss, Z_P), (0, 1, 0), DOWN, (-TILT, TILT))]


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space.
JOINT_SPECS = joint_specs()
# Actuators: (name, barrel's body, eye A, rod's body, eye B, radius); each spans one hinge.
PISTON_SPECS = ([(n, "Root", (0, s * PITCH_A[0], Z_P + PITCH_A[1]), GIMBAL, (0, s * PITCH_B[0], Z_P + PITCH_B[1]), ACT_R)
                 for n, s in PITCH] +
                [(n, GIMBAL, (s * YAW_A[0], 0, Z_P + YAW_A[1]), NOZZLE, (s * YAW_B[0], 0, Z_P + YAW_B[1]), ACT_R)
                 for n, s in YAW])
PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015
SLOT_GAP = 0.00125


def idle(f):
    """(pitch, yaw) on frame f of idle: station-keeping, a slow figure of eight a couple of degrees wide."""
    n, a, b = IDLE
    t = 2 * math.pi * f / n
    return a * math.sin(t), b * math.sin(2 * t)


def sweep(f):
    """(pitch, yaw) on frame f of sweep: a figure of eight over the gimbal's whole range, from and back to
    centre."""
    t = 2 * math.pi * f / SWEEP
    return TILT * math.sin(t), TILT * math.sin(2 * t)


def looped(n, fn):
    frames = [(f, fn(f)) for f in range(n + 1)]
    return {GIMBAL: [(f, p) for f, (p, _) in frames], NOZZLE: [(f, y) for f, (_, y) in frames]}


def pose(pitch=0.0, yaw=0.0):
    return {GIMBAL: [(0, pitch), (1, pitch)], NOZZLE: [(0, yaw), (1, yaw)]}


# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}. The loops key every
# frame; the vector poses are the gimbal at full deflection (for a blend space), named by where the
# exhaust swings: front is -Y, left is +X.
ANIMATIONS = {
    "idle": (True, "LINEAR", looped(IDLE[0], idle)),
    "sweep": (True, "LINEAR", looped(SWEEP, sweep)),
    "vector_front": (False, "LINEAR", pose(pitch=-TILT)),
    "vector_back": (False, "LINEAR", pose(pitch=TILT)),
    "vector_left": (False, "LINEAR", pose(yaw=-TILT)),
    "vector_right": (False, "LINEAR", pose(yaw=TILT)),
}
PREVIEW_STATES = {"vector_front": {GIMBAL: -TILT}, "vector_left": {NOZZLE: -TILT},
                  "vector_back_right": {GIMBAL: TILT, NOZZLE: TILT}}
PREVIEW_VIEWS = {"vector_front": ["right", "front_left"], "vector_left": ["front", "front_left"],
                 "vector_back_right": ["front_left", "rear_right", "bottom"]}
FK_TEST_STATE = {GIMBAL: 6.0, NOZZLE: -4.0}
SHOWCASE = ["idle", "sweep", "idle"]   # animate.py plays these in order

# slot: (base colour, metallic, roughness, emission strength). Map-generic, in Tensor's materials.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): the drum, the engine's top and collar
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): flange, lamp band, underside, barrels
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black: the gimbal ring, lugs, cheeks, eyes, every cut
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: tanks, pins, rods, nuts
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # the status lamps
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.22, 0.0),      # bushings, washers, the tanks' ends
    "M_Titanium": ((0.29, 0.29, 0.30), 1.0, 0.45, 0.0),   # matte titanium: the bell, the trunnion bosses
    "M_Exhaust": ((1.0, 0.6, 0.0), 0.0, 0.5, 1.2),         # the bore's lining: split off into its own mesh for the game's shader
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, TI, EXH = SLOTS

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


def cheeks(root, centre, place, normal, r=CHEEK[2]):
    """A clevis: two cheek plates either side of an eye, `place(u, v, w)` putting a point of the outline at
    offset w along the pin."""
    w0, w1, _ = CHEEK
    return [plate_bm(keyhole(root, centre, r), lambda u, v, s=s: place(u, v, s * (w0 + w1) / 2), w1 - w0, normal)
            for s in (1, -1)]


def radial(az, r, z):
    a = math.radians(az)
    return Vector((r * math.cos(a), r * math.sin(a), z))


# --------------------------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------------------------

def build_body(k):
    """The body: one lofted unibody (the flange, the lamp band, the drum, its flat underside) with the
    two hanger lugs fused under it at +-X, then machined: the tanks' pockets on the diagonals, the pitch
    actuators' channels up its sides at +-Y, and slanted vents over the hangers and the channels. The flange
    and the band grey, the drum off-white, the underside grey, the lugs and every cut matte black."""
    x0, x1, hw, r_end = HANGER
    hangers = [plate_bm(keyhole([(-hw, Z_U + 0.02), (hw, Z_U + 0.02)], (0, Z_P), r_end, 10),
                        lambda u, v, s=s: (s * (x0 + x1) / 2, u, v), x1 - x0, (1, 0, 0)) for s in (1, -1)]
    rf = flat(BODY[7][1])
    fins = []
    for az in (22.5 + 45 * i for i in range(8)):  # the drum's ribs, each under a lamp
        a = math.radians(az)
        w, proud = DRUM_RIB
        fins.append(slab_bm([tuple(radial(az, r, z)) for r, z in ((2.25, -0.47), (rf + proud, -0.47), (rf + proud, -1.80),
                                                                   (2.25, -1.80 - (rf + proud - 2.25)))], 2 * w,
                            (-math.sin(a), math.cos(a), 0)))
    pw, pz = POD
    for s in (1, -1):  # the doubler pods over the hangers: a chamfered top, a 45-degree foot
        fins.append(slab_bm([(s * x, 0, z) for x, z in ((2.25, pz), (rf + 0.01, pz), (rf + 0.05, pz - 0.04), (rf + 0.05, -1.80),
                                                        (2.25, -1.80 - (rf + 0.05 - 2.25)))], 2 * pw, (0, 1, 0)))
    shell = revolve([(r, z) for z, r in BODY])
    plain = BVHTree.FromBMesh(shell)   # the drum alone: what lies on it is its paint, what doesn't is fused on
    solid = boolean(shell, hangers + fins, "UNION")
    half, floor = POCKET
    _, _, _, top, bot, _ = TANK
    cutters = [rot_z(block_bm(((floor + 2.7) / 2, 0, (top + bot) / 2), (2.7 - floor, 2 * half, top - bot)), az)
               for az in (45, 135, 225, 315)]
    cw, cin, ctop = CHANNEL
    cutters += [block_bm((0, s * (cin + 2.7) / 2, (Z_U - 0.2 + ctop) / 2), (2 * cw, 2.7 - cin, ctop - Z_U + 0.2))
                for s in (1, -1)]
    for az, z0, z1 in ((0, -1.04, -0.64), (180, -1.04, -0.64), (90, -0.96, -0.62), (270, -0.96, -0.62)):
        a = math.radians(az)
        cutters += lean_slots(radial(az, rf, 0), (math.cos(a), math.sin(a), 0), (-math.sin(a), math.cos(a), 0), (0, 0, 1),
                              [-0.13 + 0.065 * i for i in range(4)], 0.035, z0, z1, 0.03, 0.02)

    def material(f, c, cut):
        if cut:
            return FRM
        if c.z < Z_U - 1e-4:
            return FRM                   # the hanger lugs
        if c.z > -0.445:
            return SEC                   # the flange, the neck and the lamp band
        if plain.find_nearest(c)[3] > 2e-4:
            return SEC                   # the ribs and the pods (off the drum's own surface; by radius, a flat face's
                                         # triangles away from its middle read as off it)
        if c.z < Z_U + 1e-4:
            return SEC                   # the underside
        return PRI

    machine(k, solid, cutters, "Root", material)


def build_tanks(k):
    """Four propellant tanks standing in the pockets, stainless steel with bronze ends, their end necks
    seated on the pockets' top and bottom faces."""
    ra, r, rn, top, bot, e = TANK
    for az in (45, 135, 225, 315):
        c = radial(az, ra, 0)
        rings = [circ(rr, z, 12, c.x, c.y) for rr, z in ((rn, top), (r, top - e), (r, bot + e), (rn, bot))]

        def material(f, cc, cut):
            return BRZ if cc.z > top - e + 1e-4 or cc.z < bot + e - 1e-4 else JNT
        machine(k, loft_bm(rings), [], "Root", material)


def build_flange_nuts(k):
    """Eight stainless steel nuts on the flange's underside (the bolts go up into the platform)."""
    for i in range(8):
        p = radial(45 * i, 2.41, 0)
        k.cyl((p.x, p.y, BODY[2][0] + 0.002), (p.x, p.y, BODY[2][0] - 0.026), 0.035, "Root", JNT, segs=6, solid=False)


def lamp(k, at, normal, bone, r=0.07):
    """A status lamp: a black bezel sunk 5 mm into a flat, a lit lens standing in it."""
    n = Vector(normal).normalized()
    at = Vector(at)
    k.cyl(at - n * 0.005, at + n * 0.025, r, bone, FRM, segs=8)
    k.cyl(at + n * 0.02, at + n * 0.03, r * 0.7, bone, EMI, segs=6)


def build_lamps(k):
    """Eight status lamps round the band, between the tanks and the hardpoints."""
    rf, z = flat(BODY[4][1]), (BODY[4][0] + BODY[5][0]) / 2
    for i in range(8):
        az = 22.5 + 45 * i
        lamp(k, radial(az, rf, z), radial(az, 1, 0), "Root")


def build_hanger_bearings(k):
    """A bronze bushing on each hanger lug's outer face, about the ring's trunnion."""
    for s in (1, -1):
        k.cyl((s * HANGER[1], 0, Z_P), (s * BUSHING[0], 0, Z_P), BUSHING[1], "Root", BRZ, segs=10)


def build_ring(k):
    """The gimbal ring: one matte black unibody (a chamfered box-section ring with the clevis cheeks of the
    pitch actuators fused on its top at +-Y and of the yaw actuators under it at +-X), four titanium trunnion
    bosses (the bearings of the nozzle's trunnions at +-Y), and its own stainless steel trunnion pins at +-X
    through the hanger lugs, nutted outside the bushings."""
    parts = []
    by, bh = PITCH_B
    for s in (1, -1):  # the pitch actuators' rod eyes, on pins along X
        parts += cheeks([(s * 1.775, 0.09), (s * 1.915, 0.09)], (s * by, bh), lambda u, v, w: (w, u, Z_P + v), (1, 0, 0))
    ax, ah = YAW_A
    for s in (1, -1):  # the yaw actuators' barrel eyes, on pins along Y
        parts += cheeks([(s * 1.775, -0.09), (s * 1.915, -0.09)], (s * ax, ah), lambda u, v, w: (u, w, Z_P + v), (0, 1, 0))
    machine(k, boolean(torus_bm(RING, Z_P, N_RING), parts, "UNION"), [], GIMBAL, lambda f, c, cut: FRM)
    b0, b1, br = BOSS
    pr, nr, nh = TRUNNION_PIN
    for s in (1, -1):
        k.cyl((s * b0, 0, Z_P), (s * b1, 0, Z_P), br, GIMBAL, TI, segs=12)
        k.cyl((0, s * b0, Z_P), (0, s * b1, Z_P), br, GIMBAL, TI, segs=12)
        k.cyl((s * 1.90, 0, Z_P), (s * BUSHING[0], 0, Z_P), pr, GIMBAL, JNT, segs=8)          # the trunnion pin (rotor)
        k.cyl((s * BUSHING[0], 0, Z_P), (s * (BUSHING[0] + nh), 0, Z_P), nr, GIMBAL, JNT, segs=6)  # ...and its nut
        k.cyl((-0.11, s * by, Z_P + bh), (0.11, s * by, Z_P + bh), EYE_PIN, GIMBAL, JNT, segs=6, solid=False)
        k.cyl((s * ax, -0.11, Z_P + ah), (s * ax, 0.11, Z_P + ah), EYE_PIN, GIMBAL, JNT, segs=6, solid=False)


def bell_r(h):
    """The bell's corner radius at height h over Z_P (between the waist and the exit)."""
    (r0, h0), (r1, h1) = NOZZLE_OUT[4], NOZZLE_OUT[5]
    return r0 + (r1 - r0) * (h - h0) / (h1 - h0)


def build_nozzle(k):
    """The engine: one unibody of revolution (the domed top, the collar, the waist, the bell and its lip,
    the bore up to the injector face) with its trunnions at +-Y, the yaw actuators' clevises at +-X and six
    ribs down the bell fused on, and eight notches cut in its exit band. Off-white top and collar, a titanium bell, black cheeks, lip and bore."""
    tr0, tr1, trr = NOZZLE_TRUNNION
    extra = [rod_bm((0, s * tr0, Z_P), (0, s * tr1, Z_P), trr, 12) for s in (1, -1)]
    bx, bh = YAW_B
    for s in (1, -1):
        extra += cheeks([(s * 1.55, -1.40), (s * 1.55, -1.80)], (s * bx, bh), lambda u, v, w: (u, w, Z_P + v), (0, 1, 0))
    w, proud = RIB
    (rw, hw), (re, he) = NOZZLE_OUT[4], NOZZLE_OUT[5]
    outline = [(rw - 0.06, hw - 0.01), (rw + proud, hw - 0.01), (re + proud, he), (re + proud, he - 0.04), (1.64, he - 0.04)]
    for az in (45, 90, 135, 225, 270, 315):
        a = math.radians(az)
        extra.append(slab_bm([tuple(radial(az, r, Z_P + h)) for r, h in outline], w, (-math.sin(a), math.cos(a), 0)))
    nw, nh, nr = NOTCH
    h_exit = NOZZLE_IN[0][1]
    notches = [rot_z(block_bm(((nr + 2.0) / 2, 0, Z_P + h_exit + nh / 2 - 0.02), (2.0 - nr, 2 * nw, nh + 0.04)), 22.5 + 45 * i)
               for i in range(8)]
    solid = revolve([(r, Z_P + h) for r, h in NOZZLE_OUT + NOZZLE_IN])
    solid = boolean(boolean(solid, extra, "UNION"), notches, "DIFFERENCE")
    w0, w1, _ = CHEEK

    def material(f, c, cut):
        h, rho = c.z - Z_P, math.hypot(c.x, c.y)
        if cut or (h < -1.70 and rho < NOTCH[2] + 0.02 and f.normal.z > -0.99):
            return FRM                       # (the notches, cut before machining, are found by position)
        if w0 - 0.01 < abs(c.y) < w1 + 0.005 and abs(c.x) > 1.5 and h < -1.3:
            return FRM                       # the clevis cheeks
        radial_out = (f.normal.x * c.x + f.normal.y * c.y) / max(rho, 1e-6)
        if h < NOZZLE_IN[0][1] + 1e-4 or (radial_out < -0.2 and h < -0.25) or (f.normal.z < -0.99 and rho < 1.0):
            return FRM                       # the lip, the bore and the injector face (all under the exhaust lining)
        return PRI if h > -0.40 else TI

    machine(k, solid, [], NOZZLE, material)


def build_nozzle_fittings(k):
    """The nozzle's stainless steel trunnion pins (rotors in the ring's bosses, nutted outside them), the
    yaw actuators' rod-eye pins through its clevises, and four lamps on the collar."""
    pr, nr, nh = TRUNNION_PIN
    bx, bh = YAW_B
    for s in (1, -1):
        k.cyl((0, s * 1.60, Z_P), (0, s * BOSS[1], Z_P), pr, NOZZLE, JNT, segs=8)
        k.cyl((0, s * BOSS[1], Z_P), (0, s * (BOSS[1] + nh), Z_P), nr, NOZZLE, JNT, segs=6)
        k.cyl((s * bx, -0.11, Z_P + bh), (s * bx, 0.11, Z_P + bh), EYE_PIN, NOZZLE, JNT, segs=6, solid=False)
    rf = flat(NOZZLE_OUT[1][0])
    for az in (45, 135, 225, 315):
        lamp(k, radial(az, rf, Z_P), radial(az, 1, 0), NOZZLE, r=0.05)


def liner_profile():
    """The exhaust lining's section (radius, height over Z_P): the bore's, 1 mm inside it (meeting it at the
    exit rim, so no gap opens there), then a shallow injector cone down to its apex on the axis."""
    (r0, h0), (r1, h1), (r2, h2) = NOZZLE_IN
    return [(r0, h0), (r1 - 0.001, h1), (r2 - 0.001, h2 - 0.001), (0.0, h2 - 0.05)]


def build_exhaust(k):
    """The exhaust lining: the bore's inner surface as an open cup on the nozzle, 1 mm in front of it,
    in M_Exhaust. It is split off into SK_ThrusterExhaust after the cull (its own mesh for the game's
    shader)."""
    prof = liner_profile()
    tmp = bmesh.new()
    rings = [[tmp.verts.new(p) for p in circ(r, Z_P + h)] for r, h in prof[:-1]]
    apex = tmp.verts.new((0, 0, Z_P + prof[-1][1]))
    for a, b in zip(rings, rings[1:]):
        for j in range(N):
            tmp.faces.new((a[j], a[(j + 1) % N], b[(j + 1) % N], b[j]))
    for j in range(N):
        tmp.faces.new((rings[-1][j], rings[-1][(j + 1) % N], apex))
    k.shell_centres.append(Vector((0, 0, Z_P - 1.0)))  # faces the bore's middle
    for f in k.emit(tmp, NOZZLE, EXH, False, convex=False, solid=False, closed=False):
        f[k.inward] = len(k.shell_centres)


def build_channel_pins(k):
    """The pitch actuators' barrel-eye pins across the channels' cheeks."""
    ay, ah = PITCH_A
    cw = CHANNEL[0]
    for s in (1, -1):
        c = Vector((0, s * ay, Z_P + ah))
        k.cyl(c - Vector((cw + 0.01, 0, 0)), c + Vector((cw + 0.01, 0, 0)), EYE_PIN, "Root", JNT, segs=6, solid=False)


def build_pistons(k, pistons, joints):
    """The actuators: a black eye, a grey barrel with a black gland collar at its mouth, a stainless steel
    rod and its eye, each eye on a pin parallel to the hinge it drives (the pins are built with the
    clevises)."""
    for p in pistons:
        d = (p.b - p.a).normalized()
        ax = joints[p.rod_parent].axis
        eye = p.radius * 1.15
        k.cyl(p.a - ax * p.radius, p.a + ax * p.radius, eye, p.cylinder, FRM, segs=8, solid=False)
        k.cyl(p.a + d * eye * 0.7, p.a + d * p.cyl_len, p.radius, p.cylinder, SEC, segs=10, solid=False)
        k.cyl(p.a + d * (p.cyl_len - 0.04), p.a + d * (p.cyl_len + 0.004), p.radius + 0.007, p.cylinder, FRM, segs=10,
              solid=False)
        k.cyl(p.b - d * eye * 0.7, p.b - d * p.rod_len, p.radius * 0.55, p.rod, JNT, segs=8, solid=False)
        k.cyl(p.b - ax * p.radius, p.b + ax * p.radius, eye * 0.85, p.rod, FRM, segs=8, solid=False)


def build_all(k, pistons, joints):
    build_body(k)
    build_tanks(k)
    build_flange_nuts(k)
    build_lamps(k)
    build_hanger_bearings(k)
    build_channel_pins(k)
    build_ring(k)
    build_nozzle(k)
    build_nozzle_fittings(k)
    build_exhaust(k)
    build_pistons(k, pistons, joints)


# --------------------------------------------------------------------------------------------
# The thruster's checks
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """The gimbal's whole range: a 9 x 9 grid over both axes (its corners included), on top of the
    animation frames."""
    steps = [-TILT + 2 * TILT * i / 8 for i in range(9)]
    return [(f"gimbal {p:+.1f} {y:+.1f}", {GIMBAL: p, NOZZLE: y}) for p in steps for y in steps]


def piston_mats(p, m):
    """World transforms of a piston's barrel and rod bodies in a state (world matrices m of the joints):
    each carried by its parent, then turned the least way to aim at the other eye (as the rig's damped
    tracks do)."""
    a1, b1 = m[p.cyl_parent] @ p.a, m[p.rod_parent] @ p.b
    d0 = (p.b - p.a).normalized()
    out = {}
    for bone, parent, at0, at1, aim in ((p.cylinder, p.cyl_parent, p.a, a1, b1 - a1), (p.rod, p.rod_parent, p.b, b1, a1 - b1)):
        rp = m[parent].to_3x3()
        rest = rp @ (d0 if bone == p.cylinder else -d0)
        turn = rest.rotation_difference(aim.normalized()).to_matrix()
        out[bone] = Matrix.Translation(at1) @ (turn @ rp).to_4x4() @ Matrix.Translation(-at0)
    for outer, stage in zip([p.cylinder] + p.stage_names, p.stage_names):
        out[stage] = out[p.cylinder]
    return out


def body_mats(joints, pistons, state):
    m = fk(joints, expand(state))
    for p in pistons:
        m.update(piston_mats(p, m))
    return m


def check_envelope(kit, joints, pistons, states):
    """The thruster stays inside its envelope in every state: within RADIUS of its axis, between the
    platform's underside (z = 0) and DEPTH under it, its top face on the platform."""
    problems = []
    ztop = max(v.z for p in all_parts(kit) for v in p.verts)
    if abs(ztop) > 1e-6:
        problems.append(f"highest point at z {ztop:.4f}, not on the platform's underside")
    lowest, rest_lowest = 0.0, min(v.z for p in all_parts(kit) for v in p.verts)
    for tag, state in [("rest", {})] + states:
        m = body_mats(joints, pistons, state)
        for part in all_parts(kit):
            vs = [m[part.bone] @ v for v in part.verts]
            lowest = min(lowest, min(v.z for v in vs))
            if any(math.hypot(v.x, v.y) > RADIUS + 1e-6 or v.z < -DEPTH - 1e-6 or v.z > 1e-6 for v in vs):
                problems.append(f"{part.bone} (line {part.line}) leaves the envelope at {tag}")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(dict.fromkeys(problems)))
    return rest_lowest, lowest


def check_actuators(kit, joints, pistons, states):
    """Every actuator, in every state, stands clear of every solid part of the fixed body, the ring and
    the nozzle (its barrel's radius and a few millimetres): the framework's piston check sweeps only the
    actuator's own hinge, this one the whole gimbal."""
    solid = [q for q in all_parts(kit) if q.solid and q.bone in joints]
    problems = []
    for tag, state in [("rest", {})] + states:
        m = fk(joints, expand(state))
        inv = {b: mm.inverted() for b, mm in m.items()}
        for p in pistons:
            a, b = m[p.cyl_parent] @ p.a, m[p.rod_parent] @ p.b
            span = b - a
            skip = (p.radius * 1.15 + 0.02) / span.length
            samples = [a + span * (i / 40) for i in range(41) if skip < i / 40 < 1 - skip]
            for q in solid:
                if any(q.hits(inv[q.bone] @ x, p.radius + 0.004) for x in samples):
                    problems.append(f"{p.name} hits {q.bone} (line {q.line}) at {tag}")
    if problems:
        raise SystemExit(f"[{NAME}] actuator clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


# --------------------------------------------------------------------------------------------
# The exhaust surface, gizmos, preview and export
# --------------------------------------------------------------------------------------------

def count_exhaust(obj):
    return sum(1 for p in obj.data.polygons if p.material_index == SLOTS.index(EXH))


def drop_bore(body):
    """Delete the nozzle's bore and injector face: SK_ThrusterExhaust lies 1 mm in front of every one of them
    (meeting them at the exit rim), so they never show, and they meet the rest only on sharp edges (the lip,
    the injector's corner), so no shading changes. The cull keeps them only because samples on the exit
    rim see past the lining where the two meet."""
    group = body.vertex_groups[NOZZLE].index
    stations = [(r, Z_P + h) for r, h in NOZZLE_IN]
    me = body.data

    def on_bore(i):
        v = me.vertices[i]
        r, z = math.hypot(v.co.x, v.co.y), v.co.z
        return (any(abs(r - rs) < 1e-4 and abs(z - zs) < 1e-4 for rs, zs in stations)
                and any(g.group == group for g in v.groups))
    bm = bmesh.new()
    bm.from_mesh(me)
    frm = SLOTS.index(FRM)
    dead = [f for f in bm.faces if f.material_index == frm and all(on_bore(v.index) for v in f.verts)]
    tris = sum(len(f.verts) - 2 for f in dead)
    bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    print(f"[{NAME}] bore behind the exhaust lining: {tris} tris dropped")


def split_exhaust(body):
    """Split the exhaust lining off the body into SK_ThrusterExhaust (its own mesh, skinned to the nozzle,
    one M_Exhaust slot), and drop that slot from the body. UVs: u 0..1 round the bore from +X toward +Y
    (counter-clockwise seen from above), v 0 at the exit rim up the wall to 1 at the injector's centre."""
    idx = SLOTS.index(EXH)
    drop_bore(body)
    ex = body.copy()
    ex.data = body.data.copy()
    ex.name, ex.data.name = f"SK_{TITLE}Exhaust", f"SK_{TITLE}Exhaust_Mesh"
    bpy.context.scene.collection.objects.link(ex)
    for obj, keep in ((body, lambda f: f.material_index != idx), (ex, lambda f: f.material_index == idx)):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f)], context="FACES_ONLY")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(obj.data)
        bm.free()
    body.data.materials.pop(index=idx)
    ex.data.materials.clear()
    ex.data.materials.append(bpy.data.materials[EXH])
    for poly in ex.data.polygons:
        poly.material_index = 0
    for vg in list(ex.vertex_groups):
        if vg.name != NOZZLE:
            ex.vertex_groups.remove(vg)
    mat = bpy.data.materials[EXH]
    mat.use_backface_culling = False
    prof = liner_profile()
    run = [0.0]
    for (r0, h0), (r1, h1) in zip(prof, prof[1:]):
        run.append(run[-1] + math.hypot(r1 - r0, h1 - h0))
    vs = {round(h, 4): s / run[-1] for (_, h), s in zip(prof, run)}
    me = ex.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        cos = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        us = [None if math.hypot(c.x, c.y) < 1e-5 else (math.atan2(c.y, c.x) / (2 * math.pi)) % 1.0 for c in cos]
        known = [u for u in us if u is not None]
        if max(known) - min(known) > 0.5:  # the face straddles the seam at +X
            us = [None if u is None else (u + 1.0 if u < 0.5 else u) for u in us]
            known = [u for u in us if u is not None]
        for li, c, u in zip(poly.loop_indices, cos, us):
            v = vs[min(vs, key=lambda h: abs(h - (c.z - Z_P)))]
            uv.data[li].uv = (sum(known) / len(known) if u is None else u, v)
    return ex


def place_on_bone(obj, rig, bone_name, m):
    """Parent obj to a bone and give it the world matrix m (at rest)."""
    bone = rig.data.bones[bone_name]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    obj.matrix_basis = m
    return obj


def gizmo_specs():
    """(name, bone, origin, forward, up): ExhaustOrigin midway up the bore on the axis, where the flame
    starts, and NozzleExit at the exit plane's centre; both point out along the exhaust (down at rest) with
    their up toward the thruster's front, and ride the nozzle's vectoring."""
    h_exit, h_top = NOZZLE_IN[0][1], NOZZLE_IN[-1][1]
    return [("ExhaustOrigin", NOZZLE, (0, 0, Z_P + (h_exit + h_top) / 2), DOWN, FWD),
            ("NozzleExit", NOZZLE, (0, 0, Z_P + h_exit), DOWN, FWD)]


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


def write_rig_json(joints, pistons, tris, exhaust_tris, depths):
    def vec(v):
        return [round(c, 4) for c in v]

    prof = liner_profile()
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, front -Y, left +X; the origin is the centre of the top mount face, which meets "
                 "the platform's underside at z = 0, and the thruster hangs below it. glTF/Godot: (x, z, -y). The "
                 "gimbal's joints turn about their bones' local X (degrees).",
        "rest": "the nozzle straight down (no vectoring)",
        "size_m": {"diameter": 2 * RADIUS, "depth_at_rest": round(-depths[0], 4),
                   "depth_at_full_vectoring": round(-depths[1], 4), "envelope_depth": DEPTH},
        "mount": {"face": "the top face (z = 0), bolted flat to the platform's underside, 5 m round",
                  "note": "place it so its origin lies on the underside, its axis vertical"},
        "gimbal": {"centre": vec((0, 0, Z_P)), "range_deg": [-TILT, TILT],
                   "pitch": f"{GIMBAL} about +X: + swings the exhaust to the back (+Y), - to the front (-Y)",
                   "yaw": f"{NOZZLE} about +Y (in the ring): + swings the exhaust to the right (-X), - to the left (+X)",
                   "note": "the thrust on the platform is opposite to where the exhaust swings"},
        "exhaust": {"object": f"SK_{TITLE}Exhaust", "material": EXH, "bone": NOZZLE,
                    "surface": "the nozzle's bore from the exit rim up to the injector face, facing into the bore "
                               "(double-sided)",
                    "profile_m": [{"radius": round(r, 4), "z": round(Z_P + h, 4)} for r, h in prof],
                    "uv": "u 0..1 round the bore from +X toward +Y (counter-clockwise seen from above), v 0 at the exit "
                          "rim up the wall to 1 at the injector's centre",
                    "triangles": exhaust_tris},
        "gizmos": [{"name": n, "bone": b, "origin": vec(o), "forward": vec(f), "up": vec(u),
                    "godot": "-Z along the exhaust (out of the nozzle), +Y toward the thruster's front"}
                   for n, b, o, f, u in gizmo_specs()],
        "materials_note": "map-generic finish in Tensor's materials (off-white and grey paint, matte black, stainless "
                          "steel, bronze, titanium): no team colours",
        "materials": [s for s in SLOTS if s != EXH],
        "triangles": tris,
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "pistons": [{"cylinder": p.cylinder, "rod": p.rod, "cylinder_parent": p.cyl_parent,
                     "rod_parent": p.rod_parent, "cylinder_aims_at": p.rod, "rod_aims_at": p.cylinder,
                     "stroke_m": [round(p.stroke[0], 4), round(p.stroke[1], 4)],
                     "cylinder_length_m": round(p.cyl_len, 4), "rod_length_m": round(p.rod_len, 4)}
                    for p in pistons],
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "usage": "Loop idle while the platform hovers. To steer, blend the vector_front / vector_back / vector_left / "
                 "vector_right poses (the gimbal at full deflection, named by where the exhaust swings; a 2D blend space "
                 "with the rest pose at its centre), or drive GimbalRing and Nozzle's local X rotation directly within "
                 "range_deg and aim each actuator's cylinder and rod bone at the other (as their rows say). sweep is a "
                 "full-range figure of eight for showcases. Put the flame shader on SK_ThrusterExhaust's M_Exhaust "
                 "surface and start the plume at ExhaustOrigin; both follow the nozzle.",
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
    build_all(kit, pistons, joints)
    states = action_states(actions, joints) + sweep_states(joints)
    depths = check_envelope(kit, joints, pistons, states)
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_piston_clearance(pistons, joints, kit.solids, all_parts(kit))
    check_actuators(kit, joints, pistons, states)
    check_motion(kit, joints, states)
    print(f"[{NAME}] checks passed ({len(states)} motion states); lowest point {depths[0]:.3f} m at rest, "
          f"{depths[1]:.3f} m vectoring")
    for p in pistons:
        print(f"[{NAME}] {p.name}: stroke {p.stroke[0]:.3f}..{p.stroke[1]:.3f} m, barrel {p.cyl_len:.3f} m, "
              f"rod {p.rod_len:.3f} m, overlap at full reach {p.overlap:.3f} m")

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    check_coplanar(body)
    skin(body, rig)
    lining = count_exhaust(body)
    if "--no-cull" not in sys.argv:
        cull_unseen(body, rig, joints, pistons, states, (-1e-4, -1e-4), (1e-4, 1e-4), PLATFORM_FRAME)
    if count_exhaust(body) != lining:
        raise SystemExit(f"[{NAME}] the cull removed exhaust faces ({lining} -> {count_exhaust(body)})")
    exhaust = split_exhaust(body)
    unwrap(body)
    tris, exhaust_tris = triangles(body), triangles(exhaust)
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET}); exhaust: {exhaust_tris} tris")
    if tris > TRI_BUDGET and "--no-cull" not in sys.argv:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")

    gizmos = build_gizmos(rig)
    export([rig, body, exhaust, *gizmos], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, pistons, tris, exhaust_tris, depths)

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
