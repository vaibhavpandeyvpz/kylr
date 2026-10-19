"""Barricade - a pop-up steel barricade for KYLR, modelled, rigged and animated from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/gameplay/barricade/model.py

Produces, next to this script:
    barricade.blend          source scene (the barricade plus a preview-only floor slab), opened by
                             preview.py and animate.py
    barricade.glb / .fbx     SK_Barricade skinned to RIG_Barricade, with the actions raise and lower
    barricade_rig.json       the hinge and its range, the rams, the animations and the floor cut-out

Design: a complete 4 x 2 m outer frame enclosing an inset steel block, 0.3 m thick,
lying flush in the floor. It is hinged along its front
long edge, which is rounded about the hinge axis: three knuckles on the frame turn in notches in that
edge on a pin through the block. Two three-stage telescopic hydraulic struts at the block's ends,
their barrels in clevises on pedestals in the pit, their stainless steel stages and rods in lugs under steel
spine beams on the block's back, push it up (raise) to stand as a wall with its top face to the
front, braced from behind like a kickstand, and pull it back down (lower). The block is one unibody
shell (the weapons' language), its edges and ends chamfered: the load frame on its back (spine beams,
ribs and cross beams in a grid of equal bays, each X-braced) is milled out of it, the struts' lugs
fused into the spine beams, and its top face carries three recessed armour panels (user: no light
strip, no vents). Under the lowered
block, a deck on four hydraulic rams carries it; once the wall is up, the deck rises flush with the
floor behind it, so there is ground to take cover on, notched where the struts pass. It drops back
before the wall comes down. A flush frame rims the pocket and a grey open box lines the pit.
The game raises and lowers it, for example from a pressure plate. Map-generic finish.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, the hinge misses
its rotor or bearing, a strut crosses its hinge, leaves its stages or passes through armour or the
deck, or anything collides through any animation frame or across the joints' ranges.
Conventions: 1 unit = 1 m, Z up, the floor is z = 0 with the origin at the block's centre (lowered);
the long side runs along X, front = -Y (the hinge side). Rest pose = lowered (flush).
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
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

NAME = "barricade"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # Barricade

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored)

OUTER_W, OUTER_L = 4.0, 2.0            # complete frame/pit footprint, including running clearances
SLAB_T = 0.30
HINGE_C = 0.05                         # the hinge axis runs this far in from the block's front and top
                                       # faces (the radius of its rounded front edge)
GAP = 0.005                            # running clearance round the block and the deck
RIM, RIM_D = 0.05, 0.05                # the flush frame round the pocket: width, depth
# Reserve the rear corner's circular sweep as well as both rim/gap bands.
# OUTER_L = HINGE_C + REACH + 2*GAP + 2*RIM.
SLAB_A = OUTER_W / 2 - GAP - RIM
SLAB_B = (HINGE_C + math.sqrt((OUTER_L - HINGE_C - 2*GAP - 2*RIM)**2
                              - (SLAB_T - HINGE_C)**2)) / 2
PIT_D = 1.50                           # exact 1.5 m resting envelope below the flush frame
RAISE = 90                             # raised: the block stands upright
STRUT_X = (-SLAB_A + .15, SLAB_A - .15) # preserve lug/spine clearance from the inset slab ends
STRUT_R = 0.06                         # strut barrel radius
STRUT_STAGES = 2                       # stages between barrel and rod (three joints)
STRUT_B = (1.20 * SLAB_B, -0.39)       # lug pins, inset with the shorter slab; heights unchanged
STRUT_A = (1.85 * SLAB_B, -0.95)       # pit pins, inset together with the lug pins
KNUCKLES = (-1.6, 0.0, 1.6)            # the frame's hinge knuckles (x); one sits at the hinge's pivot
KNUCKLE_L = 0.24                       # knuckle length
CHAMFER = 0.025                        # the block's chamfer round its front (top) face, its ends and its back
FRAME_D = 0.06                         # how far the load frame stands off the block's back (its rib tops)
FRAME_Y = 0.85 * SLAB_B                # keep the rear load frame clear of the rising deck
FRAME_GRID = (4, 2)                    # its equal bays: columns between the spine beams, rows
FRAME_W = 0.05                         # its ribs' and cross beams' width
BRACE_W = 0.04                         # its X braces' width
SPINE = 0.115                          # the spine beams' half-width (x): just wider than the lugs they carry
FRAME_CHAMFER = 0.012                  # the chamfer round the load frame's outer edge
POCKET_IN = 0.01                       # the pockets between the ribs are milled this far into the block's back
POCKET_R = 0.012                       # the pockets' corner radius (the cutter's)
PANELS = 3                             # recessed armour panels across the front (top) face, equal
PANEL_BORDER, PANEL_WEB = 0.12, 0.08   # the border round them and the web between them
PANEL_D = 0.02                         # their depth, with 45-degree walls
DECK_CLEAR = 0.002                     # the lowered deck waits this far under the load frame (the struts hold it)
DECK_T = 0.05                          # deck thickness
DECK_RAMS = [(sx * 1.3, y) for sx in (1, -1) for y in (-0.35, 0.75)]  # the deck's rams (x, y)
DECK_RAM_R = (0.05, 0.008)             # their barrel radius and wall (the rod fills the bore)
PREVIEW_FRAME = {"lo": [-2.1, -1.1, -0.1], "hi": [2.1, 1.1, 1.95]}
# === END SPEC ===

HY, HZ = -SLAB_B + HINGE_C, -HINGE_C      # the hinge axis (y, z), along X
REACH = math.hypot(2 * SLAB_B - HINGE_C, SLAB_T - HINGE_C)  # the block's back-bottom edge, about the axis
BACK_GAP = REACH - (2 * SLAB_B - HINGE_C) + GAP  # it swings back this far as the block starts to rise
POCKET = (-(SLAB_A + GAP), SLAB_A + GAP, -(SLAB_B + GAP), SLAB_B + BACK_GAP)  # the rim's inner edge: x0, x1, y0, y1
PATCH = (POCKET[0] - RIM, POCKET[1] + RIM, POCKET[2] - RIM, POCKET[3] + RIM)  # the floor cut-out
assert abs(PATCH[1] - PATCH[0] - OUTER_W) < 1e-10
assert abs(PATCH[3] - PATCH[2] - OUTER_L) < 1e-10
HEIGHT = HZ + 2 * SLAB_B - HINGE_C        # the wall's top above the floor when raised
DECK_LOW = -SLAB_T - FRAME_D - DECK_CLEAR  # the deck's top, lowered: just under the block's load frame
DECK_RISE = -DECK_LOW                     # it rises flush with the floor
DECK_Y = (HY + SLAB_T - HINGE_C + GAP, POCKET[3] - GAP)  # front (behind the raised wall's back) to back
DECK_ROD = DECK_RISE + 0.08               # the deck rams' rods: 8 cm still in their barrels, raised
STRUT_AY, STRUT_AZ = HY + STRUT_A[0], HZ + STRUT_A[1]
STRUT_BY, STRUT_BZ = HY + STRUT_B[0], HZ + STRUT_B[1]
LUG = (0.10, 0.08)                        # the struts' lugs and clevises: half-width (x), half-length (y)
SLOT = STRUT_R + 0.004                    # half-width of their slots: clear of the eyes, inside the pins
SLAB, DECK = "Slab", "Deck"
GROUPS = ()  # joints that move together (none)


def swing(y, z, deg):
    """A point of the block (y, z at rest) with the block raised by deg about the hinge."""
    c, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return HY + (y - HY) * c - (z - HZ) * s_, HZ + (y - HY) * s_ + (z - HZ) * c


def deck_notch():
    """The y-range the deck is notched over at its ends, found by sweeping each strut's axis and lug
    through the block's swing (deck down) and the deck's rise (wall up), wherever they cross the
    deck's thickness, plus the strut's radius and 2 cm."""
    ys, m = [], STRUT_R + 0.02
    lug = [(STRUT_BY + e * LUG[1], z) for e in (1, -1) for z in (STRUT_BZ - 0.08, -SLAB_T)]
    for deg in range(0, RAISE + 1):
        by, bz = swing(STRUT_BY, STRUT_BZ, deg)
        pts = [(STRUT_AY + (by - STRUT_AY) * t / 50, STRUT_AZ + (bz - STRUT_AZ) * t / 50) for t in range(51)]
        pts += [swing(y, z, deg) for y, z in lug]
        ys += [y for y, z in pts if DECK_LOW - DECK_T - m <= z <= DECK_LOW + m]
    by, bz = swing(STRUT_BY, STRUT_BZ, RAISE)
    for t in range(51):
        y, z = STRUT_AY + (by - STRUT_AY) * t / 50, STRUT_AZ + (bz - STRUT_AZ) * t / 50
        if DECK_LOW - DECK_T - m <= z <= m:
            ys.append(y)
    return min(ys) - m, max(ys) + m


NOTCH_Y = deck_notch()


def hatch(a, b, n):  # the pistons' coordinates are world coordinates here
    return Vector((a, b, n))


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space. The block turns
# about +X: + lifts its back edge, 90 = upright. The deck slides up +Z from under the lowered block.
JOINT_SPECS = [
    ("Root", None, "fixed", (0, 0, 0), UP, UP, None),
    (SLAB, "Root", "hinge", (0, HY, HZ), (1, 0, 0), BACK, (0, RAISE)),
    (DECK, "Root", "slide", (0, (DECK_Y[0] + DECK_Y[1]) / 2, DECK_LOW), UP, None, (0, DECK_RISE)),
]
# Struts: telescopic, barrel in a clevis on a pedestal in the pit (end A), rod in a lug under the
# block's spine beam (end B), with a long lever about the hinge all the way up.
# (name, cylinder parent, A, rod parent, B, barrel radius, stages)
PISTON_SPECS = [(f"Strut{i + 1}", "Root", (x, STRUT_AY, STRUT_AZ), SLAB, (x, STRUT_BY, STRUT_BZ), STRUT_R, STRUT_STAGES)
                for i, x in enumerate(STRUT_X)]
PISTON_MIN_OVERLAP = 0.08  # telescopes keep a long overlap at every joint
PISTON_MIN_ARM = 0.015
SLOT_GAP = 0.00125

# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}. It pops up fast.
ANIMATIONS = {  # it pops up fast; the deck follows it up, and goes down first
    "raise": (False, "BEZIER", {SLAB: [(0, 0), (9, RAISE)], DECK: [(0, 0), (9, 0), (19, DECK_RISE)]}),
    "lower": (False, "BEZIER", {DECK: [(0, DECK_RISE), (10, 0)], SLAB: [(0, RAISE), (10, RAISE), (22, 0)]}),
}
PREVIEW_STATES = {"halfway": {SLAB: 45}, "deck_rising": {SLAB: RAISE, DECK: DECK_RISE / 2},
                  "raised": {SLAB: RAISE, DECK: DECK_RISE}}
PREVIEW_VIEWS = {"raised": ["front_left", "rear_right", "right"], "halfway": ["front_left", "right"],
                 "deck_rising": ["rear_right"]}
FK_TEST_STATE = {SLAB: 37, DECK: 0.1}
SHOWCASE = ["raise", "lower"]  # animate.py plays these in order

# slot: (base colour, metallic, roughness, emission strength). Map-generic, in Tensor's materials: off-white and grey paint, matte black, stainless steel.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): the block
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): pit liner, strut and ram barrels
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black (Tensor's frames): frame, load frame, lugs, clevises, deck
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: knuckles, pins, strut stages and rods, ram rods
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # unused on the block (user: no light strip); kept so the slots match
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI = SLOTS

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


def expand(state):
    """A joint state with each group's first joint's value copied to the group's other joints."""
    out = dict(state)
    for group in GROUPS:
        if group and group[0] in state:
            for other in group[1:]:
                out.setdefault(other, state[group[0]])
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
        tmp = machine(prism_bm(outline, thickness, n0), cuts, boxes, intersect,
                      [(h, n0, thickness * 3) for h in holes] + list(subtract))
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


def arc_xz(cx, cz, r, a0, a1, n):
    """(x, z) points on a circle about (cx, cz) from angle a0 to a1 (deg, from +x toward +z), n segments."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def fillet(points, r, n=2):
    """A polyline with each inner corner rounded: an arc of radius r (n segments) tangent to both legs."""
    pts = [Vector(q) for q in points]
    out = [pts[0]]
    for a, q, b in zip(pts, pts[1:], pts[2:]):
        u, v = (a - q).normalized(), (b - q).normalized()
        half = math.acos(max(-1.0, min(1.0, u.dot(v)))) / 2
        d = min(r / math.tan(half), 0.45 * (a - q).length, 0.45 * (b - q).length)
        rr = d * math.tan(half)
        c = q + (u + v).normalized() * (rr / math.sin(half))
        e0, e1 = q + u * d - c, q + v * d - c
        phi = math.pi - 2 * half
        out += [c + (e0 * math.sin((1 - f / n) * phi) + e1 * math.sin(f / n * phi)) / math.sin(phi) for f in range(n + 1)]
    return out + [pts[-1]]


def loft_rings(rings):
    """A closed bmesh through rings of points (the same count in each, in order), capped at both ends."""
    bm = bmesh.new()
    vs = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    n = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    bm.faces.new(vs[0][::-1])
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def prism_bm(points, thickness, normal):
    """A closed prism: the polygon `points` extruded `thickness` along `normal`, centred on it."""
    n = Vector(normal).normalized() * (thickness / 2)
    bm = bmesh.new()
    bot = [bm.verts.new(Vector(q) - n) for q in points]
    top = [bm.verts.new(Vector(q) + n) for q in points]
    bm.faces.new(top)
    bm.faces.new(bot[::-1])
    for i in range(len(points)):
        j = (i + 1) % len(points)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def machine(bm, cuts=(), boxes=(), intersect=(), subtract=(), union=(), remove=()):
    """The closed bmesh `bm` machined with exact booleans, returned as a new bmesh (bm, `union` and `remove`
    are freed): the closed bmeshes in `union` are fused into it first (fairings: one unibody), then it is
    intersected with each `intersect` (points, normal, thickness) prism, then `cuts` (p0, p1, r[, sides])
    cylinders, `boxes` (center, size) blocks, `subtract` (points, normal, thickness) prisms and the closed
    bmeshes in `remove` (lofted cutters: a recess with drafted walls) are cut away."""
    def temp(b, name):
        mesh = bpy.data.meshes.new(name)
        b.to_mesh(mesh)
        b.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def rod(p0, p1, r, segs=16):
        p0, p1 = Vector(p0), Vector(p1)
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=(p1 - p0).length)
        rot = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix()
        for v in b.verts:
            v.co = rot @ v.co + (p0 + p1) / 2
        return temp(b, "_rod")

    def block(center, size):
        b = bmesh.new()
        bmesh.ops.create_cube(b, size=1.0)
        for v in b.verts:
            v.co = Vector(center) + Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        return temp(b, "_block")

    base = temp(bm, "_solid")
    fused = [temp(b, "_fairing") for b in union]
    for fairing in fused:
        mod = base.modifiers.new("fuse", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "UNION", "EXACT", fairing
    shapers = [temp(prism_bm(pts, th, nrm), "_slab") for pts, nrm, th in intersect]
    for shaper in shapers:
        mod = base.modifiers.new("shape", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", shaper
    cutters = ([rod(*c) for c in cuts] + [block(*b) for b in boxes]
               + [temp(prism_bm(pts, th, nrm), "_slab") for pts, nrm, th in subtract] + [temp(b, "_loft") for b in remove])
    for cutter in cutters:
        mod = base.modifiers.new("cut", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    out = bmesh.new()
    out.from_object(base, bpy.context.evaluated_depsgraph_get())
    for obj in (base, *fused, *shapers, *cutters):
        mesh = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
    return out


def in_polygon(p, poly, tol=1e-5):
    """Is the 2D point p inside the polygon, or within tol of its outline?"""
    x, y = p
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy or 1.0)))
        if math.hypot(x - x0 - t * dx, y - y0 - t * dy) < tol:
            return True
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * dx / dy:
            inside = not inside
    return inside


def carve(k, bm, bone, mat, cuts=(), boxes=(), subtract=(), inner=FRM, bevel=0.0, flanks=(), intersect=(), union=()):
    """A unibody shell: the closed bmesh `bm`, with the fairings in `union` fused in, machined as a plate
    is (see machine()). Faces on its uncut surface (its own, the fairings' or the `intersect` profiles')
    take `mat`, faces the cuts make take `inner`. With `bevel`, every convex edge round a face
    lying in one of the `flanks` planes (normal, offset: the shell's sides, frame-local) is chamfered,
    so the side outline and its round ends are chamfered alike (the cuts' openings stay sharp). The
    faces are triangulated for the checks (a concave n-gon would be fanned across its gaps);
    optimise() merges the flat ones again."""
    # The uncut surface's faces as planes and outlines, tested exactly: a BVH's closest point is
    # computed in floats and drifts up to a millimetre on long thin faces (a 4 m facet), which
    # painted uncut faces as cuts.
    source = []
    profiles = [prism_bm(pts, th, nrm) for pts, nrm, th in intersect]
    for b in (bm, *union, *profiles):
        b.normal_update()
        for f in b.faces:
            n = tuple(float(x) for x in f.normal)
            ax = max(range(3), key=lambda i: abs(n[i]))
            u, v = [i for i in range(3) if i != ax]
            source.append((n, sum(n[i] * f.verts[0].co[i] for i in range(3)), u, v,
                           [(float(q.co[u]), float(q.co[v])) for q in f.verts]))
    for b in profiles:
        b.free()
    tmp = machine(bm, cuts, boxes, intersect, subtract, union)
    tmp.normal_update()
    skin = set()
    for tri in tmp.calc_loop_triangles():  # a point inside each face (a concave face's centre may lie off it)
        f = tri[0].face
        if f in skin:
            continue
        c = [sum(float(l.vert.co[i]) for l in tri) / 3 for i in range(3)]
        m = tuple(float(x) for x in f.normal)
        if any(n[0] * m[0] + n[1] * m[1] + n[2] * m[2] > 0.9999 and abs(sum(n[i] * c[i] for i in range(3)) - d) < 2e-5
               and in_polygon((c[u], c[v]), pts) for n, d, u, v, pts in source):
            skin.add(f)
    for f in tmp.faces:
        f.material_index = SLOTS.index(mat if f in skin else inner)
    if bevel > 0:
        tmp.normal_update()
        planes = [(Vector(n).normalized(), d) for n, d in flanks]

        def on_flank(f):
            c = f.calc_center_median()
            return any(abs(f.normal.dot(n)) > 0.999 and abs(c.dot(n) - d) < 1e-5 for n, d in planes)
        edges = []
        for e in tmp.edges:
            if len(e.link_faces) == 2 and e.is_convex:
                a, b = e.link_faces
                if on_flank(b):
                    a, b = b, a
                if on_flank(a) and not on_flank(b) and b in skin:
                    edges.append(e)
        bmesh.ops.bevel(tmp, geom=edges, offset=bevel, offset_type="OFFSET", segments=1, profile=0.5, affect="EDGES",
                        clamp_overlap=True)
    bmesh.ops.triangulate(tmp, faces=tmp.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])
    mats = [f.material_index for f in tmp.faces]
    for f, m in zip(k.emit(tmp, bone, mat, False, convex=False, exact=True), mats):
        f.material_index = m


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
# Parts
# --------------------------------------------------------------------------------------------

def build_frame(k):
    """The flush frame round the pocket and the three hinge knuckles on its front rail: 8-sided
    barrels coaxial with the hinge axis, their top edge flush with the floor, each carried by a web
    from the rail."""
    x0, x1, y0, y1 = POCKET
    X0, X1, Y0, Y1 = PATCH
    zc = -RIM_D / 2
    k.plate([(X1, Y1, zc), (X0, Y1, zc), (X0, Y0, zc), (X1, Y0, zc)], RIM_D, UP, "Root", FRM,
            holes=[[(x1, y1, zc), (x0, y1, zc), (x0, y0, zc), (x1, y0, zc)]])
    for x in KNUCKLES:
        ring = [(x, HY + HINGE_C * math.cos(math.radians(a)), HZ + HINGE_C * math.sin(math.radians(a)))
                for a in range(0, 360, 45)]
        k.plate(ring, KNUCKLE_L, (1, 0, 0), "Root", JNT)                               # knuckle
        k.span((x - KNUCKLE_L / 2, y0, -0.10), (x + KNUCKLE_L / 2, -SLAB_B, 0.0), "Root", FRM)  # web


def build_pit(k):
    """The pit: an open grey box inside the frame's footprint; the struts' clevises, each a
    pedestal on the pit floor rounded about its pin and slotted for the barrel's eye (open toward the
    strut over its whole swing), the pin through both cheeks; the deck's ram barrels on the floor, each
    with a gland collar."""
    X0, X1, Y0, Y1 = PATCH
    k.shell((X0, Y0, -PIT_D), (X1, Y1, -RIM_D), "Root", SEC)
    ay, az = STRUT_AY, STRUT_AZ
    clevis = [(ay - 0.10, -PIT_D), (ay + 0.10, -PIT_D)] + arc_xz(ay, az, 0.10, 0, 180, 8)  # round about its pin
    for x in STRUT_X:
        k.plate([(x, y, z) for y, z in clevis], 2 * LUG[0], (1, 0, 0), "Root", FRM,
                boxes=[((x, ay - 0.16, az + 0.21), (2 * SLOT, 0.48, 0.58))])
        k.cyl((x - LUG[0] - 0.003, ay, az), (x + LUG[0] + 0.003, ay, az), 0.012, "Root", JNT, segs=12, solid=False)  # pin
    r, wall = DECK_RAM_R
    top = DECK_LOW - DECK_T - 0.01                      # 1 cm under the lowered deck
    for x, y in DECK_RAMS:
        zc = (top - PIT_D) / 2
        k.plate(ring_xy(x, y, r, zc, 12), top + PIT_D, UP, "Root", SEC, holes=[ring_xy(x, y, r - wall, zc, 12)])
        k.plate(ring_xy(x, y, r + 0.008, top - 0.015, 12), 0.03, UP, "Root", FRM,
                holes=[ring_xy(x, y, r, top - 0.015, 12)])                         # gland collar, round the barrel's top


def inset(poly, offsets):
    """A convex 2D polygon with each edge i (from point i to i + 1) moved in by offsets[i]."""
    pts = [Vector(q) for q in poly]
    turn = 1 if sum(a.x * b.y - b.x * a.y for a, b in zip(pts, pts[1:] + pts[:1])) > 0 else -1
    lines = []
    for i, a in enumerate(pts):
        d = (pts[(i + 1) % len(pts)] - a).normalized()
        lines.append((a + Vector((-d.y, d.x)) * (turn * offsets[i]), d))
    out = []
    for (p0, d0), (p1, d1) in zip(lines[-1:] + lines[:-1], lines):
        t = ((p1.x - p0.x) * d1.y - (p1.y - p0.y) * d1.x) / (d0.x * d1.y - d0.y * d1.x)
        out.append(p0 + d0 * t)
    return out


def rounded(poly, r, n=2):
    """A closed polygon with every corner filleted (radius r, n segments)."""
    poly = list(poly)
    return fillet(poly[-1:] + poly + poly[:1], r, n)[1:-1]


def frame_bays():
    """The load frame's bays (x0, x1, y0, y1): FRAME_GRID of equal bays between the spine beams and inside
    the end cross beams, the ribs and cross beams FRAME_W between them."""
    fy, w = FRAME_Y, FRAME_W
    cols, rows = FRAME_GRID
    x0, x1 = STRUT_X[0] + SPINE, STRUT_X[1] - SPINE
    y0 = -fy + w
    px, py = (x1 - x0 + w) / cols, (2 * fy - w) / rows    # bay plus member
    return [(x0 + i * px, x0 + (i + 1) * px - w, y0 + j * py, y0 + (j + 1) * py - w)
            for i in range(cols) for j in range(rows)]


def build_slab(k):
    """The block, one unibody shell (the weapons' language) carved from its side profile: its front top
    edge rounded about the hinge axis and notched round the frame's knuckles, its other long edges and
    its ends chamfered (CHAMFER). Its top face (the wall's front when raised) carries PANELS armour
    panels recessed with 45-degree walls (no vents: holes in a wall's front defeat it, user). On its
    back, the load frame is milled out of the block itself: a raised field (FRAME_Y, its outer edge chamfered) with
    pockets cut between the ribs, leaving a spine beam over each strut, ribs and cross beams in a grid
    of equal bays (FRAME_GRID) centred on the back and an X in every bay standing; the pockets' floors
    and walls are matte black, the rib tops the block's paint. Each spine beam carries its strut's lug
    fused into it: a round-ended web about the pin with 45-degree root gussets, slotted between its
    cheeks (open toward the strut over the whole swing), the pin through both cheeks, its ends showing.
    The hinge pin runs through the block."""
    c, ch = HINGE_C, CHAMFER
    zb, fy = -SLAB_T - FRAME_D, FRAME_Y                      # the rib tops; the frame's half-height
    arc = [(HY + c * math.cos(math.radians(a)), HZ + c * math.sin(math.radians(a))) for a in (90, 112.5, 135, 157.5, 180)]
    side = [(-SLAB_B, -SLAB_T + ch), (-SLAB_B + ch, -SLAB_T), (SLAB_B - ch, -SLAB_T), (SLAB_B, -SLAB_T + ch),
            (SLAB_B, -ch), (SLAB_B - ch, 0.0)] + arc
    block = prism_bm([(0, y, z) for y, z in side], 2 * SLAB_A, (1, 0, 0))

    # The load frame's field: its side profile chamfered along its outer edge, its ends trimmed by an end
    # profile chamfered alike; its top sits inside the block, so the union leaves no seam.
    xe, fc, zi = STRUT_X[1] + SPINE, FRAME_CHAMFER, -SLAB_T + 0.02
    field = prism_bm([(0, y, z) for y, z in [(-fy, zi), (fy, zi), (fy, zb + fc), (fy - fc, zb), (-fy + fc, zb),
                                              (-fy, zb + fc)]], 2 * xe + 0.1, (1, 0, 0))
    ends = [(x, 0, z) for x, z in [(-xe, zi + 0.01), (xe, zi + 0.01), (xe, zb + fc), (xe - fc - 0.01, zb - 0.01),
                                   (-xe + fc + 0.01, zb - 0.01), (-xe, zb + fc)]]
    field = machine(field, intersect=[(ends, (0, 1, 0), 2 * fy + 0.2)])

    # The struts' lugs: a web from the spine beam, round-ended about the pin, with 45-degree root gussets.
    by, bz, L, g = STRUT_BY, STRUT_BZ, LUG[1], 0.02
    web = ([(by - L - g - 0.01, zb + 0.01), (by - L, zb - g)] + arc_xz(by, bz, L, 180, 360, 8)
           + [(by + L, zb - g), (by + L + g + 0.01, zb + 0.01)])
    lugs = [prism_bm([(x, y, z) for y, z in web], 2 * LUG[0], (1, 0, 0)) for x in STRUT_X]

    # The front's armour panels, recessed with 45-degree walls: equal, inside a border round the flat.
    n, d = PANELS, PANEL_D
    ya, yb = HY + PANEL_BORDER, SLAB_B - ch - PANEL_BORDER
    xa = SLAB_A - ch - PANEL_BORDER
    pw, ph, ym = (2 * xa - (n - 1) * PANEL_WEB) / n, yb - ya, (ya + yb) / 2
    centres = [-xa + pw / 2 + i * (pw + PANEL_WEB) for i in range(n)]
    recesses = [loft_rings([rect(pw / 2 - d, ph / 2 - d, -d, cx, ym), rect(pw / 2 + 0.01, ph / 2 + 0.01, 0.01, cx, ym)])
                for cx in centres]
    shell = machine(block, union=[field, *lugs], remove=recesses)

    # Cut: the knuckles' notches, the lugs' slots, the pockets between the ribs.
    notches = [((x - KNUCKLE_L / 2 - 0.006, HY, HZ), (x + KNUCKLE_L / 2 + 0.006, HY, HZ), c + 0.004, 16)
               for x in KNUCKLES]
    slots = [((x, by, bz - 0.1125), (2 * SLOT, 0.5, 0.375)) for x in STRUT_X]
    floor = -SLAB_T + POCKET_IN
    pockets = []
    for x0, x1, y0, y1 in frame_bays():                     # four pockets round the X in each bay
        m = Vector(((x0 + x1) / 2, (y0 + y1) / 2))
        corners = [Vector(q) for q in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        for q in range(4):
            tri = rounded(inset([corners[q], corners[(q + 1) % 4], m], (0, BRACE_W / 2, BRACE_W / 2)), POCKET_R)
            pockets.append(([(v.x, v.y, floor - 0.1) for v in tri], (0, 0, 1), 0.2))
    carve(k, shell, SLAB, PRI, cuts=notches, boxes=slots, subtract=pockets, bevel=ch,
          flanks=[((1, 0, 0), SLAB_A), ((1, 0, 0), -SLAB_A)])
    k.cyl((-SLAB_A + 0.03, HY, HZ), (SLAB_A - 0.03, HY, HZ), 0.02, SLAB, JNT, segs=8)  # hinge pin
    for x in STRUT_X:                                       # the lugs' pins, their ends 3 mm proud of the cheeks
        k.cyl((x - LUG[0] - 0.003, by, bz), (x + LUG[0] + 0.003, by, bz), 0.012, SLAB, JNT, segs=12, solid=False)


def build_deck(k):
    """The deck: a plate filling the pocket behind the raised wall, notched at its ends where the
    struts and their lugs pass, with panel grooves; under it, the rods of its four rams."""
    x0, x1 = -SLAB_A, SLAB_A
    y0, y1 = DECK_Y
    zc = DECK_LOW - DECK_T / 2
    nx = abs(STRUT_X[1]) - LUG[0] - 0.02
    ny0, ny1 = NOTCH_Y
    notches = [((e * (nx + 0.5), (ny0 + ny1) / 2, zc), (1.0, ny1 - ny0, DECK_T + 0.02)) for e in (1, -1)]
    grooves = [((0, y, DECK_LOW - 0.003), (2 * SLAB_A - 0.3, 0.012, 0.0061)) for y in (y0 + (y1 - y0) * f for f in (1 / 3, 2 / 3))]
    k.plate([(x1, y1, zc), (x0, y1, zc), (x0, y0, zc), (x1, y0, zc)], DECK_T, UP, DECK, FRM, boxes=notches + grooves)
    r, wall = DECK_RAM_R
    under = DECK_LOW - DECK_T
    for x, y in DECK_RAMS:
        k.plate(ring_xy(x, y, r - wall - 0.0008, under - DECK_ROD / 2, 12), DECK_ROD, UP, DECK, JNT)


def build_all(k, pistons, joints):
    build_frame(k)
    build_pit(k)
    build_slab(k)
    build_deck(k)
    build_pistons(k, pistons, joints)


def sweep_states(joints):
    """The hinge's whole range with the deck down, and the deck's whole travel with the wall up."""
    states = [(f"slab {v}", {SLAB: v}) for v in range(0, RAISE + 1, 3)]
    states += [(f"deck {DECK_RISE * i / 12:.3f}", {SLAB: RAISE, DECK: DECK_RISE * i / 12}) for i in range(13)]
    return states


def check_rams_clear(kit, joints, pistons, states):
    """Every piston against every body outside its own chain (for the struts: the deck), in every
    motion state: its axis, less its ends, must stay its barrel's radius clear of their exact parts."""
    problems = []
    for p in pistons:
        chain = descendants(joints, p.rod_parent) | {p.cyl_parent}
        others = [q for q in all_parts(kit) if q.bone in joints and q.bone not in chain and q.solid]
        for tag, state in states:
            m = fk(joints, expand(state))
            a, b = m[p.cyl_parent] @ p.a, m[p.rod_parent] @ p.b
            skip = (p.radius + 0.02) / (b - a).length
            xs = [a.lerp(b, t / 40) for t in range(41) if skip < t / 40 < 1 - skip]
            for q in others:
                inv = m[q.bone].inverted()
                if any(q.hits(inv @ x, p.radius) for x in xs):
                    problems.append(f"{p.name} hits {q.bone} (line {q.line}) at {tag}")
                    break
    if problems:
        raise SystemExit(f"[{NAME}] ram clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


# --------------------------------------------------------------------------------------------
# Preview and export
# --------------------------------------------------------------------------------------------

def build_preview_floor():
    """A floor slab round the frame (the frame sits flush in it), for previews only (never exported)."""
    mat = bpy.data.materials.new("PRV_Floor")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.26, 0.27, 0.28, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    X0, X1, Y0, Y1 = PATCH
    ca, cb, ha, hb = (X0 + X1) / 2, (Y0 + Y1) / 2, (X1 - X0) / 2, (Y1 - Y0) / 2
    bm = bmesh.new()
    inner = [bm.verts.new(p) for p in rect(ha, hb, 0.0, ca, cb, chamfer=0.001)]
    outer = [bm.verts.new(p) for p in rect(6.0, 5.0, 0.0, ca, cb, chamfer=0.001)]
    under = [bm.verts.new(p) for p in rect(6.0, 5.0, -0.02, ca, cb, chamfer=0.001)]
    low = [bm.verts.new(p) for p in rect(ha, hb, -0.02, ca, cb, chamfer=0.001)]
    for i in range(8):
        j = (i + 1) % 8
        bm.faces.new((inner[i], inner[j], outer[j], outer[i]))  # top
        bm.faces.new((outer[i], outer[j], under[j], under[i]))  # rim
        bm.faces.new((under[i], under[j], low[j], low[i]))      # underside
        bm.faces.new((low[i], low[j], inner[j], inner[i]))      # hole wall
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new("PRV_Floor_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("PRV_Floor", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def write_rig_json(joints, pistons, tris):
    def vec(v):
        return [round(c, 4) for c in v]

    X0, X1, Y0, Y1 = PATCH
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, front -Y (the hinge side), the floor is z = 0 with the origin at the "
                 "lowered block's centre. glTF/Godot: (x, z, -y). Hinges turn about their bone's local X (value in "
                 "degrees; the block's 90 = raised); slides move along their bone's local Y (metres).",
        "rest": "lowered (flush with the floor), deck down",
        "outer_footprint_m": {"length": OUTER_L, "width": OUTER_W},
        "cutout_m": {"x": [round(X0, 4), round(X1, 4)], "y": [round(Y0, 4), round(Y1, 4)], "depth": PIT_D,
                     "note": "the frame's top is flush with the floor at z = 0; the pit hangs below it, inside "
                             "its footprint"},
        "raised_m": {"width": 2 * SLAB_A, "height": round(HEIGHT, 4), "thickness": SLAB_T,
                     "front_face_y": -SLAB_B, "deck_y": [round(DECK_Y[0], 4), round(DECK_Y[1], 4)],
                     "deck_notches_y": [round(NOTCH_Y[0], 4), round(NOTCH_Y[1], 4)],
                     "note": "raised, the block stands behind the hinge; the deck rises flush with the floor behind "
                             "it, notched at its ends where the struts pass"},
        "materials_note": "map-generic finish in Tensor's materials (off-white and grey paint, matte black, stainless steel): no team colours",
        "materials": SLOTS,
        "triangles": tris,
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "pistons": [{"cylinder": p.cylinder, "rod": p.rod, "cylinder_parent": p.cyl_parent,
                     "rod_parent": p.rod_parent, "cylinder_aims_at": p.rod, "rod_aims_at": p.cylinder,
                     "stroke_m": [round(p.stroke[0], 4), round(p.stroke[1], 4)],
                     "tube_length_m": round(p.cyl_len, 4), "rest_length_m": round(p.rest, 4),
                     "stages": [{"bone": s, "parent": p.cylinder,
                                 "slide_y_m": f"({i} / {p.stages + 1}) * (distance(cylinder, rod) - rest_length_m)"}
                                for i, s in enumerate(p.stage_names, 1)]}
                    for p in pistons],
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "usage": "raise pops the block up into a wall (0.3 s) and then lifts the deck flush behind it; lower drops "
                 "the deck and then the wall (0.7 s in all). The game toggles between them, for example on a "
                 "pressure plate's press. The struts (aims and telescope stages) are baked into the animations; "
                 "rebuild them from 'pistons' only for procedural poses.",
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
    check_footprint(kit, (PATCH[0], PATCH[2]), (PATCH[1], PATCH[3]), (0.0, -RIM_D))
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_piston_clearance(pistons, joints, kit.solids, kit.parts)
    states = action_states(actions, joints) + sweep_states(joints)
    check_motion(kit, joints, states)
    check_rams_clear(kit, joints, pistons, states)
    for tag, state in states:
        pose_state(rig, joints, pistons, state)
        transforms = {b.name: rig.pose.bones[b.name].matrix @ b.matrix_local.inverted()
                      for b in rig.data.bones}
        for part in kit.parts:
            for vertex in part.verts:
                point = transforms[part.bone] @ vertex
                assert PATCH[0]-1e-5 <= point.x <= PATCH[1]+1e-5, (tag, part.bone, point)
                assert PATCH[2]-1e-5 <= point.y <= PATCH[3]+1e-5, (tag, part.bone, point)
    reset_pose(rig)
    print(f"[{NAME}] checks passed ({len(states)} motion states)")

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    check_coplanar(body)
    skin(body, rig)
    cull_unseen(body, rig, joints, pistons, states, (PATCH[0], PATCH[2]), (PATCH[1], PATCH[3]))
    sys.path.insert(0,str(HERE.parents[1]))
    from gameplay.dimensions import assert_authored_bounds
    assert_authored_bounds(HERE.name,[body])
    unwrap(body)
    tris = triangles(body)
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET})")
    if tris > TRI_BUDGET:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")
    for p in pistons[:1]:
        print(f"[{NAME}] {p.name}: stroke {p.stroke[0]:.3f}-{p.stroke[1]:.3f} m, {p.stages + 2} tubes of "
              f"{p.cyl_len:.3f} m, min overlap {p.overlap:.3f} m; deck notches y {NOTCH_Y[0]:.3f}..{NOTCH_Y[1]:.3f}")

    export([rig, body], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, pistons, tris)
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
