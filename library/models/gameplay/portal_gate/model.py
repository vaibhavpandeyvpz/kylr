"""Portal gate - a walk-through teleport gate for KYLR, modelled, rigged and animated from
script.

Run headless from the repo root:
    blender --background --factory-startup --python models/gameplay/portal_gate/model.py

Produces, next to this script:
    portal_gate.blend          source scene (the gate plus a preview-only floor slab), opened by
                               preview.py and animate.py
    portal_gate.glb / .fbx     SK_PortalGate (the gate) and SK_PortalGateField (the field: one
                               double-sided rectangle for the game's shaders) skinned to
                               RIG_PortalGate, the gizmos SpawnFront, SpawnBack and FieldCenter,
                               and the actions activate, active (looped) and deactivate
    portal_gate_rig.json       the joints and their ranges, the animations, the field and the gizmos

Design: a thin freestanding gate 1.5 m wide, 0.1 m across and 2 m tall, symmetric left to right
and front to back, so it is walked through either way; its opening is 1.25 m wide and 1.85 m high
(Tensor, 1.753 m, clears it). The frame is one lofted unibody (the weapons' language): two towers (a
grey plinth, a slimmer column carrying a raised grey pod on its outer face, a tower head with a sloped
roof beside the header), the header between them and a prouder crown over its middle, fused, then
machined with exact booleans: a black channel down each inner face, a bore through the crown for each
flywheel, grooves for the lit strips, slanted vents, and a recessed grab handle in each pod.
Between the towers a grey threshold plate, ramped front and back, carries stainless steel tread bars.
The field floats in the opening with a 1 inch gap to the frame all round (user), its side edges
straddled by the emitters' clips: the rail mounts and the carriages.

Mechanics: down each inner channel two tubular linear motors (stainless steel rods between bolted
mounts, one each side of the field) carry the emitter carriages, each with a lit lens facing across
the opening; while the portal is active they sweep the field's height and back. In the crown a pair
of counter-rotating flywheels (discs in through-bores, seen through bearing spiders on both faces)
spin up on activate, run on active and spin down on deactivate. Map-generic finish in Tensor's
materials.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a carriage
leaves its rod, a flywheel isn't coaxial with its bearings, anything collides through any animation
frame or across the joints' ranges, the gate leaves its envelope or anything stands in the passage.
Conventions: 1 unit = 1 m, Z up, the floor is z = 0 with the origin at the field's foot, front = -Y
(the gate is the same from behind). Rest pose = inactive (carriages parked at the bottom).
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Portal': 'Emissive',
    'M_PortalStatus': 'Emissive',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
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

NAME = "portal_gate"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # PortalGate

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored by the kit)

HALF_W, HALF_D, HEIGHT = 0.75, 0.05, 2.0    # the envelope: 1.5 m wide, 0.1 m across, 2 m tall
OPEN_X = 0.625                         # the opening's half-width: 1.25 m between the pillars
# The pillars' sections up their height: (z, inner |x|, outer |x|, half-depth, outer and inner corner
# chamfers). A grey plinth, a band in to the slimmer column, a flare out to the tower head beside the
# header, and its roof.
PILLAR = [(0.0, 0.625, 0.75, 0.05, 0.012, 0.008), (0.20, 0.625, 0.75, 0.05, 0.012, 0.008),
          (0.225, 0.625, 0.725, 0.04, 0.012, 0.008), (1.80, 0.625, 0.725, 0.04, 0.012, 0.008),
          (1.825, 0.625, 0.75, 0.05, 0.012, 0.008), (1.96, 0.625, 0.75, 0.05, 0.012, 0.008),
          (2.0, 0.65, 0.73, 0.038, 0.008, 0.006)]
POD = (0.705, 0.026, 0.40, 1.65, 0.004)  # the raised grey pod on each column's outer face: from |x|, half-width, z, chamfer
HEADER = (1.85, 0.04, 0.008, 0.012, 1.95, 0.66)  # header between the towers: underside z, half-depth, chamfers, top, |x| end
CROWN = (0.046, 0.40, 0.35)            # the crown fused over its middle: half-depth, its ramps from |x| 0.40 up to 0.35
CHANNEL = (0.01, 0.028, 0.24, 1.76)    # the recessed channel down each inner face: depth, half-width, z
THRESHOLD = (0.02, 0.015)             # threshold plate: height, front and back ramp
FIELD_GAP = 0.0254                     # the field's gap to the frame all round (user: 1 inch)
RAIL = (0.024, 0.018, 0.005, 0.25, 1.75)  # emitter rails: axis off the channel floor, |y|, rod radius, mounts' outer ends z
MOUNT = (0.048, 0.009, 0.03)           # rail mounts (the field's lower and upper clips): depth off the floor, half-width, height
CARRIAGE = (0.044, 0.009, 0.10, 0.012)  # emitter carriages (clips sweeping the field's edge): depth, half-width, height, gap to the mounts at the ends
FLYWHEEL = (0.22, 1.925, 0.042, 0.037, 0.028)  # flywheels: |x|, axis z, bore radius, drum radius, drum half-length
SPIDER = (0.034, 0.042)                # the bearing spiders' |y| span, inside the crown's faces
LOOP = 120                             # active: frames per loop (the carriages sweep up and back once)
TURNS = 4                              # flywheel turns per active loop
RAMP = 60                              # activate / deactivate: frames of the flywheels' spin up / down (one turn)
SPAWN = 0.6                            # the spawn gizmos: this far in front of and behind the field
PASSAGE = [(0.56, 0.03, 1.76), (0.45, 0.03, 1.83)]  # kept clear: (half-width, from z, to z) boxes through the opening
PREVIEW_FRAME = {"lo": [-0.78, -0.07, 0.0], "hi": [0.78, 0.07, 2.01]}
# === END SPEC ===

XI, XO = OPEN_X, HALF_W                     # a pillar's inner and outer faces (|x|)
XF = XI + CHANNEL[0]                        # the inner channel's floor (|x|)
PLINTH_H = PILLAR[1][0]
COLUMN_D, COLUMN_XO = PILLAR[2][3], PILLAR[2][2]
RAIL_X = XF - RAIL[0]                       # the rods' axes (|x|)
CARRIAGE_Z0 = RAIL[3] + MOUNT[2] + CARRIAGE[3]            # a parked carriage's bottom
CARRIAGE_ZC = CARRIAGE_Z0 + CARRIAGE[2] / 2               # ...and centre
TRAVEL = round(RAIL[4] - MOUNT[2] - CARRIAGE[3] - CARRIAGE[2] - CARRIAGE_Z0, 4)  # up to the top mount's gap
FIELD = (XI - FIELD_GAP, THRESHOLD[0] + FIELD_GAP, HEADER[0] - FIELD_GAP)  # half-width, bottom, top
OMEGA = 360.0 * TURNS / LOOP                # flywheel speed while active, degrees per frame
CARRIAGES = [f"Carriage{side}{end}" for side in SIDES for end in ("Front", "Back")]
FLYWHEELS = [f"Flywheel{side}" for side in SIDES]
GROUPS = ()


def side_signs(name):
    """(sx, sy) of a carriage or flywheel: its side (+X is the gate's left) and end (-Y is the front)."""
    return (1 if "Left" in name else -1), (-1 if "Front" in name else 1)


def hatch(a, b, n):  # the pistons' coordinates are world coordinates here
    return Vector((a, b, n))


def joint_specs():
    specs = [("Root", None, "fixed", (0, 0, 0), UP, UP, None)]
    for name in CARRIAGES:  # slides along +Z (positive = up) from parked at the bottom
        sx, sy = side_signs(name)
        specs.append((name, "Root", "slide", (sx * RAIL_X, sy * RAIL[1], CARRIAGE_ZC), UP, None, (0, TRAVEL)))
    for name in FLYWHEELS:  # hinges about Y, counter-rotating (mirrored axes); pivots at the bearing hubs
        sx, _ = side_signs(name)
        specs.append((name, "Root", "hinge", (sx * FLYWHEEL[0], sum(SPIDER) / 2, FLYWHEEL[1]), (0, sx, 0), UP, None))
    return specs


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space. The flywheels spin
# freely (no limits).
JOINT_SPECS = joint_specs()
PISTON_SPECS = []
PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015
SLOT_GAP = 0.00125


def spin_up(f):
    """Flywheel angle on frame f of activate: its speed rising linearly to OMEGA over RAMP frames
    (one whole turn)."""
    return 0.5 * OMEGA * f * f / RAMP


def spin_down(f):
    """Flywheel angle on frame f of deactivate: from OMEGA falling linearly to rest (one whole turn)."""
    return OMEGA * f - 0.5 * OMEGA * f * f / RAMP


def sweep(f):
    """A carriage's height on frame f of active: up the field and back, easing at both ends."""
    return TRAVEL * (1 - math.cos(2 * math.pi * f / LOOP)) / 2


# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}. Every frame is
# keyed (spinning), so the interpolation is linear; each flywheel step is under 180 degrees and every
# action ends the flywheels on whole turns, so activate -> active (loop) -> deactivate chain seamlessly.
ANIMATIONS = {
    "activate": (False, "LINEAR", {w: [(f, spin_up(f)) for f in range(RAMP + 1)] for w in FLYWHEELS}),
    "active": (True, "LINEAR", {**{c: [(f, sweep(f)) for f in range(LOOP + 1)] for c in CARRIAGES},
                                **{w: [(f, OMEGA * f) for f in range(LOOP + 1)] for w in FLYWHEELS}}),
    "deactivate": (False, "LINEAR", {w: [(f, spin_down(f)) for f in range(RAMP + 1)] for w in FLYWHEELS}),
}
PREVIEW_STATES = {"active": {**{c: TRAVEL * 0.55 for c in CARRIAGES}, **{w: 45.0 for w in FLYWHEELS}},
                  "sweep_top": {c: TRAVEL for c in CARRIAGES}}
PREVIEW_VIEWS = {"active": ["front", "back", "right", "front_left", "rear_right"]}
FK_TEST_STATE = {**{c: TRAVEL * 0.3 for c in CARRIAGES}, **{w: 30.0 for w in FLYWHEELS}}
SHOWCASE = ["activate", "active", "active", "deactivate"]  # animate.py plays these in order

# slot: (base colour, metallic, roughness, emission strength). Map-generic, in Tensor's materials.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): the frame's shell
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): plinths, threshold, carriages, spiders, grab bars
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black: machined insides, mounts, bezels, drums
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: rods, axles, drum faces, treads, bolts
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # outer strips and header displays
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.22, 0.0),      # the flywheels' bearing hubs
    "M_PortalStatus": ((1.0, 0.12, 0.10), 0.0, 0.4, 6.0), # inner emitter lenses: game availability
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, STATUS = SLOTS
FIELD_MATERIAL = ("M_Portal", (0.0, 0.75, 0.85), 2.0)   # the field's own slot: the game's shader replaces it

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
# Parts
# --------------------------------------------------------------------------------------------

def pillar_rings(sx):
    """A pillar's sections up its height (PILLAR): each an octagon, its four vertical edges chamfered."""
    rings = []
    for z, xi, xo, d, co, ci in PILLAR:
        xi, xo = sx * xi, sx * xo
        pts = [(xo, -d + co), (xo, d - co), (xo - sx * co, d), (xi + sx * ci, d), (xi, d - ci), (xi, -d + ci),
               (xi + sx * ci, -d), (xo - sx * co, -d)]
        rings.append([(x, y, z) for x, y in pts])
    return rings


def span_rings(stations, hd, z0, cb, ct):
    """Sections along X of a beam: octagons half-depth hd from z0 up to each station's top, bottom
    corners chamfered cb and top ct."""
    def ring(x, z1):
        pts = [(hd, z0 + cb), (hd, z1 - ct), (hd - ct, z1), (-hd + ct, z1), (-hd, z1 - ct), (-hd, z0 + cb),
               (-hd + cb, z0), (hd - cb, z0)]
        return [(x, y, z) for y, z in pts]
    return [ring(x, z1) for x, z1 in stations]


def header_rings():
    """The header between the towers, its ends buried in them."""
    z0, hd, cb, ct, top, xe = HEADER
    return span_rings([(-xe, top), (xe, top)], hd, z0, cb, ct)


def crown_rings():
    """The crown over the header's middle, 2 cm prouder front and back: its top rising from the
    header's in straight 45-degree ramps."""
    z0, _, cb, ct, top, _ = HEADER
    hd, x_ramp, x_top = CROWN
    return span_rings([(-x_ramp, top), (-x_top, HEIGHT), (x_top, HEIGHT), (x_ramp, top)], hd, z0, cb, ct)


def pod_rings(sx):
    """The raised pod on a column's outer face: out of the column, its outer edges chamfered."""
    x0, hw, z0, z1, c = POD

    def ring(x, w, lo, hi):
        return [(sx * x, -w, lo), (sx * x, w, lo), (sx * x, w, hi), (sx * x, -w, hi)]
    return [ring(x0, hw, z0, z1), ring(POD_FACE - c, hw, z0, z1), ring(POD_FACE, hw - c, z0 + c, z1 - c)]


POD_FACE = XO - 0.005                        # the pod's outer face (|x|): its bolt heads stay in the envelope
HANDLE = (0.03, 0.016, 0.85, 1.15, 0.005)  # the grab handle's pocket in the pod: depth, half-width, z; the bar's radius
STRIP_X = (XI + PILLAR[2][5] + COLUMN_XO - PILLAR[2][4]) / 2   # the column's front flat's centre (|x|)
STRIP_Z = (0.28, 1.75)


POD_VENTS = (0.42, 5, 0.018, 0.008, 0.016, 0.003, 0.005)  # |z| from the handle's centre, count, pitch, height,
                                                          # half-width, end lean, depth


def pod_vents(sx):
    """The pod's vents: a batch of horizontal slots above the grab handle and one below it, each slot's
    ends slanted out toward its top (symmetric front to back), cut into the pod's face."""
    off, n, pitch, h, hw, lean, depth = POD_VENTS
    zc = (HANDLE[2] + HANDLE[3]) / 2
    x = sx * POD_FACE
    out = []
    for s in (1, -1):
        mid = zc + s * off
        for i in range(n):
            z0 = mid + (i - (n - 1) / 2) * pitch - h / 2
            pts = [(x, -hw, z0), (x, hw, z0), (x, hw + lean, z0 + h), (x, -hw - lean, z0 + h)]
            out.append(slab_bm(pts, 2 * depth, (1, 0, 0)))
    return out


def build_frame(k):
    """The frame: one unibody shell (the two towers, the header, the crown over its middle, a pod on
    each column's outer face, fused), then machined: the recessed channel down each inner face, the
    flywheels' through-bores in the crown, the
    grooves of the lit strips, slanted vents in the header and the pods, and a pocket for each
    grab handle. Off-white, the plinths and pods grey, every cut matte black."""
    solid = boolean(loft_bm(pillar_rings(1)), [loft_bm(pillar_rings(-1)), loft_bm(header_rings()),
                                               loft_bm(crown_rings()), loft_bm(pod_rings(1)), loft_bm(pod_rings(-1))], "UNION")
    depth, hw, cz0, cz1 = CHANNEL
    cutters = [block_bm((sx * (XI - 0.01 + XF) / 2, 0, (cz0 + cz1) / 2), (XF - XI + 0.01, 2 * hw, cz1 - cz0))
               for sx in (1, -1)]
    x, z, r = FLYWHEEL[:3]
    cutters += [rod_bm((sx * x, -0.3, z), (sx * x, 0.3, z), r, 16) for sx in (1, -1)]
    for sx in (1, -1):
        for sy in (1, -1):
            z0, z1 = STRIP_Z
            cutters.append(block_bm((sx * STRIP_X, sy * COLUMN_D, (z0 + z1) / 2), (0.012, 0.008, z1 - z0)))
            cutters += lean_slots((0, sy * HEADER[1], 0), (0, 1, 0), (sx, 0, 0), (0, 0, 1),  # the header: leaning out
                                  [0.44 + 0.03 * i for i in range(5)], 0.012, 1.875, 1.925, 0.01, 0.005)
        cutters += pod_vents(sx)
    depth, hw, z0, z1, _ = HANDLE
    cutters += [block_bm((sx * POD_FACE, 0, (z0 + z1) / 2), (2 * depth, 2 * hw, z1 - z0)) for sx in (1, -1)]
    _, pw, pz0, pz1, _ = POD

    def material(f, c, cut):
        if cut:
            return FRM
        if c.z < PLINTH_H - 1e-4:
            return SEC
        if abs(c.x) > COLUMN_XO + 1e-4 and pz0 - 1e-3 < c.z < pz1 + 1e-3 and abs(c.y) < pw + 1e-3:
            return SEC
        return PRI

    machine(k, solid, cutters, "Root", material)


def build_handles(k):
    """A stainless steel grab bar standing in each pod's pocket, its ends on the pocket's top and bottom
    faces, and a bolt at each corner of the pod's face."""
    depth, _, z0, z1, r = HANDLE
    _, pw, pz0, pz1, c = POD
    for sx in (1, -1):
        x = sx * (POD_FACE - depth + 0.015)
        k.tube([(x, 0, z0), (x, 0, z1)], r, "Root", JNT, sides=8)
        for y in (pw - c - 0.006, -(pw - c - 0.006)):
            for z in (pz0 + c + 0.012, pz1 - c - 0.012):
                bolt(k, (sx * POD_FACE, y, z), (sx, 0, 0), "Root", r=0.003, head=0.002)


def build_threshold(k):
    """The threshold: a grey plate between the pillars, ramped front and back, with a stainless steel
    tread bar either side of the field's line."""
    h, ramp = THRESHOLD
    hd = HALF_D
    outline = [(0, -hd, 0), (0, hd, 0), (0, hd, 0.005), (0, hd - ramp, h), (0, -hd + ramp, h), (0, -hd, 0.005)]
    k.plate(outline, 2 * XI, (1, 0, 0), "Root", SEC)
    for sy in (1, -1):
        for y in (0.027,):
            k.span((-XI + 0.075, sy * y - 0.004, h - 0.0005), (XI - 0.075, sy * y + 0.004, h + 0.002), "Root", JNT)


def build_rails(k):
    """Two tubular linear motors down each pillar's inner channel, one each side of the field: a
    stainless steel rod between two grey mounts bolted to the channel's floor."""
    off, ry, rr, z_lo, z_hi = RAIL
    md, mw, mh = MOUNT
    for sx in (1, -1):
        for sy in (1, -1):
            y = sy * ry
            k.cyl((sx * RAIL_X, y, z_lo + 0.01), (sx * RAIL_X, y, z_hi - 0.01), rr, "Root", JNT, segs=8)
            for z0 in (z_lo, z_hi - mh):
                x0, x1 = sorted((sx * (XF + 0.0005), sx * (XF - md)))
                k.span((x0, y - mw, z0), (x1, y + mw, z0 + mh), "Root", SEC)
                bolt(k, (sx * (XF - md), y, z0 + mh / 2), (-sx, 0, 0), "Root", r=0.003, head=0.002)


def build_carriages(k):
    """The emitter carriages: off-white forcer blocks riding the rods (0.7 mm clear), a lit lens on
    each one's face across the opening."""
    depth, hw, h, _ = CARRIAGE
    for name in CARRIAGES:
        sx, sy = side_signs(name)
        cx, cy = sx * RAIL_X, sy * RAIL[1]
        k.plate(rect(depth / 2, hw, CARRIAGE_ZC, ca=cx, cb=cy, chamfer=0.003), h, UP, name, PRI,
                holes=[ring_xy(cx, cy, RAIL[2] + 0.0007, CARRIAGE_ZC, 8)])
        face = cx - sx * depth / 2
        k.prism([(face, cy + s * 0.006, CARRIAGE_ZC + t * 0.035) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))],
                0.002, (1, 0, 0), name, STATUS)


def build_flywheels(k):
    """In the crown's two through-bores, a pair of counter-rotating flywheels: a black drum with a
    stainless steel face at each end (four pockets in it, so it reads turning) on a stainless axle,
    turning in bronze hubs held by three-armed grey spiders just inside the crown's faces."""
    x, z, r_bore, r_drum, half = FLYWHEEL
    y0, y1 = SPIDER
    for name in FLYWHEELS:
        sx, _ = side_signs(name)
        cx = sx * x
        drum = rod_bm((cx, -half, z), (cx, half, z), r_drum, 16)
        pockets = [rod_bm((cx + 0.021 * math.cos(a), s * (half - 0.007), z + 0.021 * math.sin(a)),
                          (cx + 0.021 * math.cos(a), s * (half + 0.01), z + 0.021 * math.sin(a)), 0.008, 8)
                   for s in (1, -1) for a in (math.radians(45 + 90 * i) for i in range(4))]

        def material(f, c, cut):
            return JNT if abs(f.normal.y) > 0.99 and abs(c.y) > half - 1e-4 else FRM

        machine(k, drum, pockets, name, material)
        k.cyl((cx, -(y1 - 0.002), z), (cx, y1 - 0.002, z), 0.007, name, JNT, segs=8)      # the axle
        for sy in (1, -1):
            k.cyl((cx, sy * y0, z), (cx, sy * y1, z), 0.014, "Root", BRZ, segs=12)         # the bearing hub
            ym = sy * (y0 + y1) / 2
            for a in (90, 210, 330):                                                     # the spider's arms
                d = Vector((math.cos(math.radians(a)), 0, math.sin(math.radians(a))))
                k.obox(Vector((cx, ym, z)) + d * 0.011, Vector((cx, ym, z)) + d * (r_bore + 0.003), 0.007, 0.006,
                       (0, 1, 0), "Root", SEC)


def build_displays(k):
    """A status display standing on the crown's face, front and back: a black bezel and a lit screen."""
    for sy in (1, -1):
        y0, y1 = sorted((sy * (CROWN[0] - 0.003), sy * (HALF_D - 0.0015)))
        k.span((-0.12, y0, 1.872), (0.12, y1, 1.972), "Root", FRM)
        y0, y1 = sorted((sy * (HALF_D - 0.002), sy * HALF_D))
        k.span((-0.11, y0, 1.882), (0.11, y1, 1.962), "Root", EMI)


def build_strips(k):
    """The lit strips down the columns' front and back faces, set 1 mm under the face in their
    grooves (the tower heads are unlit: user)."""
    for sx in (1, -1):
        for sy in (1, -1):
            z0, z1 = STRIP_Z
            y0, y1 = sorted((sy * (COLUMN_D - 0.005), sy * (COLUMN_D - 0.001)))
            k.span((sx * STRIP_X - 0.005, y0, z0 + 0.005), (sx * STRIP_X + 0.005, y1, z1 - 0.005), "Root", EMI)


def build_all(k, pistons, joints):
    build_frame(k)
    build_handles(k)
    build_threshold(k)
    build_rails(k)
    build_carriages(k)
    build_flywheels(k)
    build_displays(k)
    build_strips(k)


def sweep_states(joints):
    """The carriages' whole travel with the flywheels turning, on top of the animation frames."""
    return [(f"sweep {i}", {**{c: TRAVEL * i / 30 for c in CARRIAGES}, **{w: 12.0 * i for w in FLYWHEELS}})
            for i in range(31)]


def check_envelope(kit, joints, states):
    """The gate stays in its envelope (1.5 x 0.1 x 2 m, standing on z = 0) in every state, and nothing
    stands in the passage (PASSAGE: 1.12 m wide up to 1.76 m, 0.9 m wide up to 1.83 m, over the
    threshold), at rest and on every state."""
    problems = []
    lo, hi = Vector((-HALF_W, -HALF_D, 0.0)), Vector((HALF_W, HALF_D, HEIGHT))
    passage = PASSAGE
    zmin = min(v.z for p in all_parts(kit) for v in p.verts)
    if abs(zmin) > 1e-6:
        problems.append(f"lowest point at z {zmin:.4f}, not on the floor")
    for tag, state in [("rest", {})] + states[::5]:
        m = fk(joints, expand(state))
        for part in all_parts(kit):
            vs = [m[part.bone] @ v for v in part.verts]
            if any(v[i] < lo[i] - 1e-6 or v[i] > hi[i] + 1e-6 for v in vs for i in range(3)):
                problems.append(f"{part.bone} (line {part.line}) leaves the envelope at {tag}")
            for hx, z0, z1 in passage:
                if any(abs(v.x) < hx and z0 < v.z < z1 for v in vs):
                    problems.append(f"{part.bone} (line {part.line}) stands in the passage at {tag}")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


# --------------------------------------------------------------------------------------------
# The field, gizmos, preview and export
# --------------------------------------------------------------------------------------------

def build_field(rig):
    """The field: one rectangle across the opening at y = 0, 1 inch clear of the frame all round, facing front
    (double-sided material), UVs 0..1 across it (u to the gate's left, +X, v up). Its own material slot
    for the game's shader; emissive for previews. Skinned to Root."""
    name, color, strength = FIELD_MATERIAL
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    mat.diffuse_color = (*color, 1.0)
    mat.use_backface_culling = False
    hx, z0, z1 = FIELD
    mesh = bpy.data.meshes.new(f"SK_{TITLE}Field_Mesh")
    mesh.from_pydata([(-hx, 0, z0), (hx, 0, z0), (hx, 0, z1), (-hx, 0, z1)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = ((co.x + hx) / (2 * hx), (co.z - z0) / (z1 - z0))
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(f"SK_{TITLE}Field", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.vertex_groups.new(name="Root").add([0, 1, 2, 3], 1.0, "REPLACE")
    skin(obj, rig)
    return obj


def place_on_bone(obj, rig, bone_name, m):
    """Parent obj to a bone and give it the world matrix m (at rest)."""
    bone = rig.data.bones[bone_name]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    obj.matrix_basis = m
    return obj


def gizmo_specs():
    """(name, origin, forward, up): SpawnFront / SpawnBack on the floor in front of and behind the
    field, facing away from it (where a player arrives through it, walking out); FieldCenter at the
    field's centre, facing front (sounds, effects, the trigger's centre)."""
    hx, z0, z1 = FIELD
    return [("SpawnFront", (0, -SPAWN, 0), (0, -1, 0), (0, 0, 1)),
            ("SpawnBack", (0, SPAWN, 0), (0, 1, 0), (0, 0, 1)),
            ("FieldCenter", (0, 0, (z0 + z1) / 2), (0, -1, 0), (0, 0, 1))]


def build_gizmos(rig):
    objs = []
    for name, origin, fwd, up in gizmo_specs():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type, e.empty_display_size = "SINGLE_ARROW", 0.2
        bpy.context.scene.collection.objects.link(e)
        fwd, up = Vector(fwd), Vector(up)
        m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
        m.translation = origin
        objs.append(place_on_bone(e, rig, "Root", m))
    return objs


def build_preview_floor():
    """A floor slab under the gate, for previews only (never exported)."""
    mat = bpy.data.materials.new("PRV_Floor")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.26, 0.27, 0.28, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    bm = block_bm((0, 0, -0.01), (5.0, 5.0, 0.02))
    mesh = bpy.data.meshes.new("PRV_Floor_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("PRV_Floor", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def write_rig_json(joints, tris):
    def vec(v):
        return [round(c, 4) for c in v]

    hx, z0, z1 = FIELD
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, front -Y, the floor is z = 0 with the origin at the field's foot. glTF/Godot: "
                 "(x, z, -y). Carriages slide along their bones' local Y (metres, positive = up); flywheels turn about "
                 "their bones' local X (degrees, unlimited).",
        "rest": "inactive: carriages parked at the bottom, flywheels still",
        "size_m": [2 * HALF_W, 2 * HALF_D, HEIGHT],
        "opening_m": {"width": 2 * XI, "height": HEADER[0], "threshold_height": THRESHOLD[0],
                      "passage": "clear 1.12 m wide up to 1.76 m and 0.9 m wide up to 1.83 m, over the threshold (Tensor is 1.753 m)"},
        "field": {"object": f"SK_{TITLE}Field", "material": FIELD_MATERIAL[0], "plane": "y = 0 (glTF z = 0)",
                  "rect_m": {"x": [-hx, hx], "z": [z0, z1]}, "size_m": [round(2 * hx, 4), round(z1 - z0, 4)],
                  "normal": "-Y (front; glTF +Z), double-sided",
                  "uv": "u 0..1 across (to the gate's left, +X), v 0..1 up; seen from the front u runs left to right",
                  "gap_to_frame_m": FIELD_GAP,
                  "note": "it floats 1 inch (25.4 mm) clear of the frame all round, its side edges straddled by the rail "
                          "mounts and the carriages (front and back of it); hide it when the portal is off"},
        "gizmos": [{"name": n, "bone": "Root", "origin": vec(o), "forward": vec(f), "up": vec(u)}
                   for n, o, f, u in gizmo_specs()],
        "materials_note": "map-generic finish in Tensor's materials (off-white and grey paint, matte black, stainless "
                          "steel, bronze): no team colours",
        "materials": SLOTS + [FIELD_MATERIAL[0]],
        "triangles": tris,
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "flywheel_deg_per_frame": OMEGA,
        "usage": "activate (2 s) spins the flywheels up, then loop active (4 s: the emitter carriages sweep the field's "
                 "height and back, the flywheels run); deactivate (2 s) spins them down. Start deactivate at the end of "
                 "an active loop (the carriages parked). Show SK_PortalGateField while active and put the portal's "
                 "shader on its M_Portal surface; teleport players who cross the field (y = 0) to the other portal's "
                 "SpawnFront or SpawnBack, by the side they entered from.",
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
    check_envelope(kit, joints, states)
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_motion(kit, joints, states)
    print(f"[{NAME}] checks passed ({len(states)} motion states); carriage travel {TRAVEL:.3f} m, "
          f"field {2 * FIELD[0]:.3f} x {FIELD[2] - FIELD[1]:.3f} m")

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    check_coplanar(body)
    skin(body, rig)
    if "--no-cull" not in sys.argv:
        cull_unseen(body, rig, joints, pistons, states, (-1e-4, -1e-4), (1e-4, 1e-4))
    unwrap(body)
    tris = triangles(body)
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET})")
    if tris > TRI_BUDGET and "--no-cull" not in sys.argv:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")

    field_obj = build_field(rig)
    gizmos = build_gizmos(rig)
    export([rig, body, field_obj, *gizmos], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, tris)
    build_preview_floor()

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
