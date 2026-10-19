"""Repair station - KYLR's repair bay: Tensor walks onto its pad and stands, a shield rises round the
bay and two robotic arms work over him, modelled, rigged and animated from script.

Run headless from the repo root (after Tensor's model.py and animations/retarget.py: the arms' paths are
planned against his idle pose, and the build fails if they touch him):
    blender --background --factory-startup --python models/gameplay/repair_station/model.py

Produces, next to this script:
    repair_station.blend       source scene, opened by preview.py and animate.py
    repair_station.glb / .fbx  SK_RepairStation (the station) and SK_RepairStationShield (the shield, its own
                               M_Shield slot for the game's shader) skinned to RIG_RepairStation, the gizmos
                               PlayerMount, TorchTip and GripperCenter, and the actions activate, repair and
                               deactivate
    repair_station_rig.json    the joints and their ranges, the arms' kinematics, the shield, the gizmos, the
                               animations and how the game plays them

Design (the environment props' unibody language and finish): a 2 x 2 m deck (user: it stands on a 2 x 2 m
floor tile, so its outside matches it exactly, square corners) with an off-white repair pad in its middle,
lit broken rings inlaid in the pad, and a lit emitter ring round it that raises the shield. Two service
towers stand at its sides (+-X), each one lofted unibody: a grey plinth, an off-white column with lit cells
in its front and back and slanted vents in its outer face, a grey head with a hood hooking in over the arm,
a downlight under the hood's tip. A channel down each tower's inner face carries a linear axis: a carriage
on two stainless rods. On each carriage a SCARA arm: a shoulder and an elbow turning about vertical axes (a
titanium motor over each joint, the forearm stacked under the upper link so it folds right under it), then
a wrist about a vertical axis. The left arm carries a welding torch (a lit arc at its tip); the right arm a
gripper that rolls about its axis, with two fingers.
Shield: its own mesh (SK_RepairStationShield, M_Shield: the game's shader replaces it; 90% transparent and
emissive in previews), a dome over the whole bay rising from the emitter ring, on its own bone scaled up
its height (activate grows it, deactivate shrinks it back into the ring).

Every rigid part is weighted 1.0 to one bone. The build fails if a part floats, a joint isn't coaxial with
its bearing, anything collides through any animation frame or across the joints' ranges, anything leaves
the 2 x 2 m tile or the shield in any state, anything but the deck stands in the entry corridor with the
arms stowed, an arm comes within 1.5 cm of Tensor standing in his idle on the pad, or a joint leaves its
limits. Conventions: 1 unit = 1 m, Z up, front = -Y (its left is +X). The origin is on the floor at the
tile's centre. Rest pose = stowed: the carriages parked high, the arms folded along the towers, the gripper
closed; the shield at full size (the bind pose: hide it when the station is idle).
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_RepairStatus': 'Emissive',
    'M_Secondary': 'Metallic',
    'M_Shield': 'Emissive',
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

NAME = "repair_station"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # RepairStation
LIB = HERE.parents[2]
TENSOR_BLEND = LIB / "models" / "characters" / "tensor" / "tensor.blend"
TENSOR_IDLE = LIB / "animations" / "target" / "blend" / "tensor" / "common" / "idle.blend"

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
SHIELD_BUDGET = 1_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored by the kit)
N = 12                                 # sides of the round parts' default

HALF = 1.0                             # (user) the 2 x 2 m floor tile it stands on: its outside, exactly
DECK = 0.06                            # the deck's top (a 6 cm step onto it)
PAD = (0.585, 0.600, 0.005)            # the repair pad: its radius, the black groove round it (to r), its depth
# The pad's lit broken rings (ref: a service bay's floor): (r in, r out, arcs, gap between arcs deg, phase deg)
LIGHT_RINGS = [(0.200, 0.232, 3, 24.0, 90.0), (0.345, 0.377, 4, 20.0, 45.0)]
CENTRE_LAMP = 0.034                    # the lit disc at the pad's centre (PlayerMount)
LIT_DEPTH = 0.004                      # the lit pockets' depth (their floors lit)
EMITTER = (0.945, 0.975, 0.008)        # the shield's emitter groove round the pad: r from, to, depth
RING_N, EMITTER_N = 40, 32             # sides of the shield and of the emitter groove
SHIELD = (0.960, 1.950, 0.550)         # the shield: its radius (in the groove), wall top, dome height (top 2.5 m)
SHIELD_MARGIN = 0.01                   # everything stays this far inside the shield
CORRIDOR = (0.47, 1.85)                # arms stowed, nothing but the deck within |x| < 0.47 m up to 1.85 m (the entry)
PATIENT_CLEAR = 0.015                  # nothing of an arm comes nearer Tensor than this, in any frame

# The towers (+-X), each lofted up through octagons (z, inner |x|, outer |x|, half-depth, outer and inner
# corner chamfers): a grey plinth, a band in to the column, a flare out to the grey head, its roof.
PILLAR = [(DECK, 0.68, 0.90, 0.20, 0.030, 0.015), (0.26, 0.68, 0.90, 0.20, 0.030, 0.015),
          (0.30, 0.70, 0.88, 0.18, 0.030, 0.015), (1.84, 0.70, 0.88, 0.18, 0.030, 0.015),
          (1.87, 0.68, 0.90, 0.20, 0.030, 0.015), (1.97, 0.68, 0.90, 0.20, 0.030, 0.015),
          (2.00, 0.70, 0.88, 0.18, 0.020, 0.010)]
PLINTH_TOP, HEAD_BOTTOM = 0.301, 1.842  # the grey plinth up to here, the grey head from here
# The hood hooking in from the head over the pad (ref: a service bay's hooked pylons): sections along |x| (x,
# half-depth, z bottom, z top, chamfer), from inside the head, tapering and rising to its tip.
HOOD = [(0.74, 0.17, 1.875, 2.000, 0.020), (0.66, 0.17, 1.875, 2.000, 0.020), (0.56, 0.12, 1.905, 1.995, 0.016),
        (0.45, 0.07, 1.935, 1.985, 0.012)]
DOWNLIGHT = (0.500, 0.020, 0.012)      # the lit downlight under the hood's tip: |x|, radius, pocket depth
CELLS = [(0.80, 0.92), (1.00, 1.62)]   # the lit cells in each column's front and back: z from, to
CELL = (0.030, 0.006)                  # ...their half-width and pocket depth
VENTS = (1.56, 7, 0.026, 0.012, 0.060, 0.006, 0.006)  # outer face vents (user: horizontal, stacked): centre z, count,
                                       # pitch, height, half-width, end lean, depth
CHANNEL = (0.04, 0.085, 0.32, 1.82)    # the linear axis' channel down each inner face: depth, half-width, z from, to
RAIL = (0.025, 0.050, 0.010)           # the guide rods: axis off the channel's floor, |y|, radius
MOUNT = (0.050, 0.070, 0.040, (0.330, 1.770))  # the rods' mounts: depth off the floor, half-width, height, bottoms z
CARRIAGE = (0.075, 0.075, 0.190, 0.003)  # a carriage: depth (from 3 mm off the floor), half-width, height, floor gap
BORE = 0.0007                          # the carriage's bores' clearance round the rods
ZC0 = 1.53                             # a carriage's centre parked (rest): high, where Tensor is slim, so the arms
                                       # unfold and are at work within activate's second
TRAVEL = (0.50 - ZC0, 1.67 - ZC0)      # its travel from there (down, up): the axis' whole length between the mounts
# The SCARA arms (the left one's; the right mirrors it): the shoulder's axis |x|, the links (hub to hub) and
# their z bands about the carriage's centre, stacked so the forearm folds right under the upper link.
XS = 0.54
L1, L2 = 0.37, 0.33
UPPER = (-0.030, 0.040, 0.050, 0.044, 0.008)  # upper link: z from, to (about the carriage centre), end radii, chamfer
FORE = (-0.095, -0.035, 0.044, 0.038, 0.008)  # forearm: the same
SHELF = (0.045, 0.095, 0.064, 0.050)   # the carriage's shoulder shelf: z from, to, its root and end radii
TOOL_DZ = 0.130                        # the tools' axis under the carriage's centre
HUB = (-0.160, -0.100, 0.032)          # the tool hubs under the wrist: z from, to, radius
TORCH_TIP, GRIP_TIP = 0.200, 0.200     # the welding tip's and the fingertips' reach from the wrist axis
ROLL_S = 0.084                         # the gripper's roll joint along the tool
FINGER = (0.116, 0.017, 28.0)          # finger pivots: along the tool, off its axis; open angle (deg)
LIMITS = {"Shoulder": (-185.0, 35.0), "Elbow": (-175.0, 175.0), "Wrist": (-160.0, 160.0), "Roll": (-90.0, 90.0),
          "Finger": (0.0, 32.0)}
# Repair (user: 5 s of welding and fixing while he stands there): each arm works two spots, 75 frames each
# (approach, work, back off, travel). A spot: (height of the tool's axis, a point its line of approach passes
# over (x, y), approach direction (x, y)).
SPOT_T = (12, 39, 10, 14)              # frames per spot: approach, work, retreat, travel
LOOP = 2 * sum(SPOT_T)                 # frames of repair: two spots (150, 5 s); it ends where it starts, so it loops
RETREAT = 0.15                         # the tool backs off this far along its approach
BOW = 0.06                             # ...and travels to the next spot bowed out this much at mid-way
STANDOFF = {"Left": 0.030, "Right": 0.035}  # tip to Tensor's surface at work (welding tip; fingertips)
PROBE_W = {"Left": 0.030, "Right": 0.050}   # the tool's half-width swept by the surface probes
# Tensor's idle stands turned some 35 degrees to his left, his left foot forward and his hands hanging in front of
# his thighs: his chest faces the left tower (the torch), his back the right one (the gripper).
SPOTS = {"Left": [(1.25, (0.10, 0.00), (-0.45, 0.89)),    # chest, front left (the torch welds a seam upward)
                  (1.10, (0.30, -0.12), (-0.30, 0.95))],  # left upper arm, front
         "Right": [(1.28, (-0.08, 0.00), (0.40, -0.92)),  # power pack, back right (the gripper grips and turns)
                   (1.12, (-0.30, 0.17), (0.30, -0.95))]}  # right upper arm, back
SEAM = 0.08                            # the weld's rise
PHASE = {"Left": 0, "Right": sum(SPOT_T[:3])}  # the right arm's schedule runs this far ahead (frame 0 at a rest:
                                       # backed off from its first spot)
RAMP = 30                              # activate / deactivate (user: shield on, shield off): 1 s each
SHIELD_T = 20                          # ...the shield growing (activate's first frames) or sinking (deactivate's last)
UNFOLD = (0.0, 30.0)                # activate: the arm unfolded at its parked height (shoulder, elbow), the wrist
                                       # turning its tool to its first approach
OUT = 0.15                             # ...then its tool backed off this much more along its first approach, to rise
RISE = (2, 12, 19, 25, RAMP)           # activate's frames: unfold from, to; backed off; lowered; at the repair's start
IDLE_FRAMES = list(range(0, 60, 6))    # Tensor's idle frames the arms are fitted against
PREVIEW_FRAME = {"lo": [-1.0, -1.0, 0.0], "hi": [1.0, 1.0, 2.5]}
# === END SPEC ===

ARMS = {"Left": 1, "Right": -1}        # side sign (+X is the station's left)
TOOLS = {"Left": "torch", "Right": "gripper"}
TIP = {"Left": TORCH_TIP, "Right": GRIP_TIP}
SHIELD_BONE = "Shield"
ROLL, FINGERS = "GripperRollRight", ("FingerRight1", "FingerRight2")
XI, XO = PILLAR[2][1], PILLAR[2][2]    # a column's inner and outer faces (|x|)
HD = PILLAR[2][3]
XF = XI + CHANNEL[0]                   # the channel's floor (|x|)
RAIL_X = XF - RAIL[0]                  # the rods' axes (|x|)
CX0 = XF - CARRIAGE[3]                 # a carriage's outer face (|x|)
CX1 = CX0 - CARRIAGE[0]                # ...its inner face
SHIELD_Z0 = DECK - EMITTER[2] + 0.001  # the shield's foot in the groove (1 mm over its lit floor)
WRIST_Z = ZC0 + FORE[0] - 0.001        # the wrists' pivots: in their bearing rings under the forearms
GROUPS = ()
PLATFORM_FRAME = Matrix.Identity(4)    # the floor round the tile


def hatch(a, b, n):  # (the framework's pistons; this prop has none)
    return Vector((a, b, n))


def arm_bones(side):
    return {k: f"{k}{side}" for k in ("Carriage", "Shoulder", "Elbow", "Wrist")}


def turn(side):
    """The arm's frame: the right arm is the left one turned half round about the station's axis (so the
    same joint values move it alike, turned), the left one as authored."""
    return Matrix.Identity(3) if side == "Left" else Matrix.Rotation(math.pi, 3, "Z")


def rest_points(side):
    """The arm folded (rest), at the carriage's parked centre: shoulder S, elbow E, wrist W and the tool's
    heading h. The left arm's upper link points to the front along its tower, the forearm folded back
    under it and the tool pointing back along that (it works Tensor's front); the right arm is the same
    turned half round (it works his back)."""
    t = turn(side)
    return (t @ Vector((XS, 0.0, ZC0)), t @ Vector((XS, -L1, ZC0)), t @ Vector((XS, L2 - L1, ZC0)),
            t @ Vector((0.0, 1.0, 0.0)))


def tool_frame(side):
    """The tool's frame at rest: its axis through the wrist's (local z up), local +Y along the tool, +X = Y x Z."""
    _, _, W, h = rest_points(side)
    m = Matrix((h.cross(Vector(UP)), h, Vector(UP))).transposed().to_4x4()
    m.translation = (W.x, W.y, ZC0 - TOOL_DZ)
    return m


def joint_specs():
    specs = [("Root", None, "fixed", (0, 0, 0), UP, UP, None),
             (SHIELD_BONE, "Root", "fixed", (0, 0, SHIELD_Z0), UP, UP, None)]  # scaled up its height (keys only)
    for side, s in ARMS.items():
        b = arm_bones(side)
        S, E, W, h = rest_points(side)
        specs.append((b["Carriage"], "Root", "slide", (s * RAIL_X, 0, ZC0), UP, None, TRAVEL))
        specs.append((b["Shoulder"], b["Carriage"], "hinge", tuple(S), UP, tuple(E - S), LIMITS["Shoulder"]))
        specs.append((b["Elbow"], b["Shoulder"], "hinge", tuple(E), UP, tuple(W - E), LIMITS["Elbow"]))
        specs.append((b["Wrist"], b["Elbow"], "hinge", (W.x, W.y, WRIST_Z), UP, tuple(h), LIMITS["Wrist"]))
    m = tool_frame("Right")
    specs.append((ROLL, "WristRight", "hinge", tuple(m @ Vector((0, ROLL_S, 0))), tuple(m.col[1][:3]), UP,
                  LIMITS["Roll"]))
    for name, sgn in zip(FINGERS, (-1, 1)):  # + opens each finger (finger 1 on the tool's local -X side)
        specs.append((name, ROLL, "hinge", tuple(m @ Vector((sgn * FINGER[1], FINGER[0], 0))), (0, 0, -sgn),
                      tuple(m.col[1][:3]), LIMITS["Finger"]))
    return specs


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space.
JOINT_SPECS = joint_specs()
PISTON_SPECS = []                      # every joint turns on its own motor; the carriages ride linear motors
PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015

# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}, planned in main() against
# Tensor's idle (plan_animations): activate (the shield rises, the arms unfold to the repair's first frame),
# repair (the loop), deactivate (the arms fold back and park, the shield sinks into its ring). SHIELD_KEYS:
# the shield bone's height scale per action.
ANIMATIONS, SHIELD_KEYS = {}, {}
PREVIEW_STATES, PREVIEW_SHIELD, PREVIEW_VIEWS, PREVIEW_SHOW = {}, {}, {}, {}
FK_TEST_STATE = {"CarriageLeft": -0.4, "ShoulderLeft": -60.0, "ElbowLeft": 90.0, "WristLeft": -30.0,
                 "CarriageRight": -0.7, "ShoulderRight": -20.0, "ElbowRight": 70.0, "WristRight": 40.0,
                 ROLL: 35.0, FINGERS[0]: 20.0, FINGERS[1]: 10.0}
SHOWCASE = ["activate", "repair", "repair", "deactivate"]

# slot: (base colour, metallic, roughness, emission strength). The environment props' finish in Tensor's
# materials; M_Shield (its own mesh) is the game's shader's slot, 90% transparent and emissive in previews.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): the pad, columns, links, torch
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): deck, plinths, heads, mounts, palm
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black: every cut, the tool hubs, the finger pads
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: rods, axles, pins, the torch's nozzle
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # downlights and welding arc
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.22, 0.0),      # motor caps, the wrists' bearing rings
    "M_Titanium": ((0.29, 0.29, 0.30), 1.0, 0.45, 0.0),   # matte titanium: the joint motors, the roll housing
    "M_RepairStatus": ((1.0, 0.12, 0.10), 0.0, 0.4, 6.0), # pad/emitter rings, cells and carriage indicators
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, TI, STATUS = SLOTS
SHIELD_MATERIAL = ("M_Shield", (0.30, 0.95, 0.75), 0.10, 1.5)  # colour, alpha (90% transparent), emission

# The framework below (kinematics, pistons, mesh kit, checks, rig, actions, export) is the
# item table's and weapon holder's generic code (the CTF flag's copy), unchanged.


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



# --------------------------------------------------------------------------------------------
# The station's shapes
# --------------------------------------------------------------------------------------------

def span_sorted(k, p0, p1, bone, mat):
    """An axis-aligned box between two corners given in any order."""
    k.span(tuple(min(a, b) for a, b in zip(p0, p1)), tuple(max(a, b) for a, b in zip(p0, p1)), bone, mat)


def chamfer_box_bm(lo, hi, ch):
    """A box between two corners, every edge chamfered ch."""
    lo, hi = Vector(lo), Vector(hi)
    bm = block_bm(tuple((lo + hi) / 2), tuple(hi - lo))
    bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=ch, offset_type="OFFSET", segments=1, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    return bm


def stadium(c0, r0, c1, r1, z, n0=6, n1=6):
    """The convex outline round two circles (c0, r0) and (c1, r1) at height z (a link's plan: a round end
    about each axis, straight flanks tangent to both), counter-clockwise, n0 / n1 steps round each end."""
    c0, c1 = Vector((c0[0], c0[1])), Vector((c1[0], c1[1]))
    u = c1 - c0
    phi = math.atan2(u.y, u.x)
    beta = math.acos(max(-1.0, min(1.0, (r0 - r1) / u.length)))
    pts = [(c1.x + r1 * math.cos(a), c1.y + r1 * math.sin(a), z)
           for a in (phi - beta + 2 * beta * i / n1 for i in range(n1 + 1))]
    return pts + [(c0.x + r0 * math.cos(a), c0.y + r0 * math.sin(a), z)
                  for a in (phi + beta + (2 * math.pi - 2 * beta) * i / n0 for i in range(n0 + 1))]


def link_bm(c0, r0, c1, r1, z0, z1, ch, n0=6, n1=6):
    """A SCARA link's shell: the stadium round its two axes from z0 to z1, its top and bottom edges chamfered."""
    return loft_bm([stadium(c0, r0 - ch, c1, r1 - ch, z0, n0, n1), stadium(c0, r0, c1, r1, z0 + ch, n0, n1),
                    stadium(c0, r0, c1, r1, z1 - ch, n0, n1), stadium(c0, r0 - ch, c1, r1 - ch, z1, n0, n1)])


def sector(r0, r1, a0, a1, z, step=12.0):
    """An annular sector's outline (r0..r1, a0..a1 degrees) at height z."""
    n = max(2, math.ceil(abs(a1 - a0) / step))
    arc = [math.radians(a0 + (a1 - a0) * i / n) for i in range(n + 1)]
    return ([(r1 * math.cos(a), r1 * math.sin(a), z) for a in arc]
            + [(r0 * math.cos(a), r0 * math.sin(a), z) for a in reversed(arc)])


def oct_section(s, w, hh, f=0.3):
    """A tool body's section at s along it (local y): an octagon w half-wide (x), hh half-high (z), its
    corners cut f of the smaller half."""
    c = f * min(w, hh)
    return [(x, s, z) for x, z in ((w, hh - c), (w - c, hh), (-w + c, hh), (-w, hh - c), (-w, -hh + c), (-w + c, -hh),
                                   (w - c, -hh), (w, -hh + c))]


def light_arcs(z):
    """The pad's lit broken rings: each ring's arcs, as outlines at height z."""
    out = []
    for r0, r1, n, gap, phase in LIGHT_RINGS:
        span = 360.0 / n
        for i in range(n):
            a0 = phase + i * span + gap / 2
            out.append(sector(r0, r1, a0, a0 + span - gap, z))
    return out


def corner_vents():
    """Four slanted vent slots across each of the deck's corners, outside the emitter ring."""
    out = []
    for sx in (1, -1):
        for sy in (1, -1):
            u, t = Vector((sx, sy, 0)).normalized(), Vector((-sy, sx, 0)).normalized()
            out += lean_slots((0, 0, DECK), UP, u, t, [1.03 + 0.04 * i for i in range(4)], 0.018, -0.07, 0.07, 0.012,
                              0.006)
    return out


def pillar_rings(sx):
    """A tower's sections up its height (PILLAR): octagons, the four vertical edges chamfered."""
    rings = []
    for z, xi, xo, d, co, ci in PILLAR:
        xi, xo = sx * xi, sx * xo
        pts = [(xo, -d + co), (xo, d - co), (xo - sx * co, d), (xi + sx * ci, d), (xi, d - ci), (xi, -d + ci),
               (xi + sx * ci, -d), (xo - sx * co, -d)]
        rings.append([(x, y, z) for x, y in pts])
    return rings


def hood_rings(sx):
    """The hood's sections along |x|, from inside the head out over the arm: chamfered octagons."""
    rings = []
    for x, hd, z0, z1, c in HOOD:
        pts = [(hd, z0 + c), (hd, z1 - c), (hd - c, z1), (-hd + c, z1), (-hd, z1 - c), (-hd, z0 + c), (-hd + c, z0),
               (hd - c, z0)]
        rings.append([(sx * x, y, z) for y, z in pts])
    return rings


def hood_underside(x):
    """The hood's underside's height at |x| (between its sections)."""
    for (xa, _, za, _, _), (xb, _, zb, _, _) in zip(HOOD, HOOD[1:]):
        if xb <= x <= xa:
            return za + (zb - za) * (xa - x) / (xa - xb)
    raise ValueError(f"|x| {x} is off the hood")


CELL_X = (XI + PILLAR[2][5] + XO - PILLAR[2][4]) / 2   # the middle of a column's front flat (|x|)


# --------------------------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------------------------

def build_deck(k):
    """The deck: one grey block exactly on the 2 x 2 m tile (square outside corners), machined: the black
    groove round the off-white pad, the pockets of the pad's lit broken rings and its centre lamp, the
    emitter groove round the pad (the shield rises from it) and slanted vents across the corners. The lit
    pockets' and the emitter groove's floors are lit, their walls matte black."""
    solid = block_bm((0, 0, DECK / 2), (2 * HALF, 2 * HALF, DECK))
    r_pad, r_groove, d_groove = PAD
    e0, e1, e_d = EMITTER
    cutters = [torus_bm([(r_pad, -d_groove), (r_groove, -d_groove), (r_groove, 0.01), (r_pad, 0.01)], DECK, 32),
               torus_bm([(e0, -e_d), (e1, -e_d), (e1, 0.01), (e0, 0.01)], DECK, EMITTER_N),
               rod_bm((0, 0, DECK - LIT_DEPTH), (0, 0, DECK + 0.01), CENTRE_LAMP, 16)]
    cutters += [slab_bm(a, 2 * LIT_DEPTH, UP) for a in light_arcs(DECK)]
    cutters += corner_vents()

    def material(f, c, cut):
        if cut:
            lit = f.normal.z > 0.9 and min(abs(c.z - (DECK - LIT_DEPTH)), abs(c.z - (DECK - e_d))) < 2e-4
            return STATUS if lit else FRM
        if f.normal.z > 0.9 and c.z > DECK - 1e-4 and math.hypot(c.x, c.y) < r_pad + 1e-4:
            return PRI
        return SEC

    machine(k, solid, cutters, "Root", material)


def tower_vents(sx):
    """The vents in a tower's outer face (user: horizontal slots stacked up it, not vertical ones): each slot's
    ends slanting out toward its top, the batch centred on the face."""
    zc, n, pitch, h, hw, lean, depth = VENTS
    x = sx * XO
    out = []
    for i in range(n):
        z0 = zc + (i - (n - 1) / 2) * pitch - h / 2
        pts = [(x, -hw, z0), (x, hw, z0), (x, hw + lean, z0 + h), (x, -hw - lean, z0 + h)]
        out.append(slab_bm(pts, 2 * depth, (1, 0, 0)))
    return out


def build_towers(k):
    """Each tower: one unibody (the lofted column and the hood hooking in from its head over the pad, fused),
    machined: the linear axis' channel down its inner face, the lit cells' pockets in its front and back,
    slanted vents in its outer face and the downlight's pocket under the hood's tip. The plinth, the head and
    the hood grey, the column off-white, every cut matte black but the cells' and the downlight's lit floors."""
    depth, hw, cz0, cz1 = CHANNEL
    xl, rl, dl = DOWNLIGHT
    zl = hood_underside(xl)
    for sx in (1, -1):
        solid = boolean(loft_bm(pillar_rings(sx)), [loft_bm(hood_rings(sx))], "UNION")
        cutters = [block_bm((sx * (XI - 0.01 + XF) / 2, 0, (cz0 + cz1) / 2), (XF - XI + 0.01, 2 * hw, cz1 - cz0))]
        for sy in (1, -1):
            for z0, z1 in CELLS:
                cutters.append(block_bm((sx * CELL_X, sy * HD, (z0 + z1) / 2), (2 * CELL[0], 2 * CELL[1], z1 - z0)))
        cutters += tower_vents(sx)
        cutters.append(rod_bm((sx * xl, 0, zl - 0.02), (sx * xl, 0, zl + dl), rl, 12))

        def material(f, c, cut):
            if cut:
                cell = abs(f.normal.y) > 0.9 and abs(abs(c.y) - (HD - CELL[1])) < 2e-4
                lamp = f.normal.z < -0.9 and abs(c.z - (zl + dl)) < 2e-4
                return STATUS if cell else EMI if lamp else FRM
            return SEC if c.z < PLINTH_TOP or c.z > HEAD_BOTTOM else PRI

        machine(k, solid, cutters, "Root", material)


def build_rails(k):
    """Each linear axis: two stainless guide rods down the channel, between grey mounts bolted to its floor."""
    md, mw, mh, bottoms = MOUNT
    for sx in (1, -1):
        for sy in (1, -1):
            k.cyl((sx * RAIL_X, sy * RAIL[1], bottoms[0] + 0.005), (sx * RAIL_X, sy * RAIL[1], bottoms[1] + mh - 0.005),
                  RAIL[2], "Root", JNT, segs=8)
        for z0 in bottoms:
            span_sorted(k, (sx * (XF + 0.0005), -mw, z0), (sx * (XF - md), mw, z0 + mh), "Root", SEC)
            for y in (-0.022, 0.022):
                bolt(k, (sx * (XF - md), y, z0 + mh / 2), (-sx, 0, 0), "Root", r=0.004, head=0.002)


def build_carriage(k, side):
    """A carriage (the linear motor's forcer): one off-white unibody, a chamfered block riding the rods in
    its bores (0.7 mm clear) and the shoulder's shelf fused on top of it, reaching in to the shoulder's axis;
    a lit slot in its inner face; the titanium shoulder motor on the shelf's end (its bronze cap on top)."""
    s, bone = ARMS[side], f"Carriage{side}"
    hw, h = CARRIAGE[1], CARRIAGE[2]
    S = rest_points(side)[0]
    x0, x1 = sorted((s * CX1, s * CX0))
    block = chamfer_box_bm((x0, -hw, ZC0 - h / 2), (x1, hw, ZC0 + h / 2), 0.006)
    sz0, sz1, rr, re = SHELF
    shelf = link_bm((s * (CX1 + 0.012), 0), rr, (S.x, S.y), re, ZC0 + sz0, ZC0 + sz1, 0.005)
    solid = boolean(block, [shelf], "UNION")
    cutters = [rod_bm((s * RAIL_X, sy * RAIL[1], ZC0 - h), (s * RAIL_X, sy * RAIL[1], ZC0 + h), RAIL[2] + BORE, 12)
               for sy in (1, -1)]
    cutters.append(block_bm((s * CX1, 0, ZC0 - 0.055), (0.006, 0.07, 0.014)))

    def material(f, c, cut):  # the slot's floor lit
        if cut and abs(f.normal.x) > 0.9 and abs(abs(c.x) - (CX1 + 0.003)) < 2e-4:
            return STATUS
        return FRM if cut else PRI

    machine(k, solid, cutters, bone, material)
    k.cyl((S.x, S.y, ZC0 + sz1 - 0.001), (S.x, S.y, ZC0 + sz1 + 0.045), 0.038, bone, TI, segs=12)
    k.cyl((S.x, S.y, ZC0 + sz1 + 0.044), (S.x, S.y, ZC0 + sz1 + 0.049), 0.022, bone, BRZ, segs=10)


def link_vents(a, b, z):
    """Four slanted vent slots across the middle of a link's top face (at z) between its axes a and b."""
    mid, along = (a + b) / 2, (b - a).normalized()
    return lean_slots((mid.x, mid.y, z), UP, along, along.cross(Vector(UP)), [-0.035 + 0.02 * i for i in range(4)],
                      0.010, -0.016, 0.016, 0.008, 0.003)


def build_links(k, side):
    """The SCARA links, each one off-white shell round its two axes, slanted vents across its top: the upper
    link under the shelf (a stainless axle up into it; the elbow's titanium motor on its far end), the forearm
    stacked under the upper link (its axle up into it; the wrist's bronze bearing ring under its far end)."""
    b = arm_bones(side)
    S, E, W, _ = rest_points(side)
    z0, z1, r0, r1, ch = UPPER
    machine(k, link_bm(S, r0, E, r1, ZC0 + z0, ZC0 + z1, ch), link_vents(S, E, ZC0 + z1), b["Shoulder"],
            lambda f, c, cut: FRM if cut else PRI)
    k.cyl((S.x, S.y, ZC0 + z1 - 0.002), (S.x, S.y, ZC0 + SHELF[0] + 0.012), 0.020, b["Shoulder"], JNT, segs=12)
    k.cyl((E.x, E.y, ZC0 + z1 - 0.001), (E.x, E.y, ZC0 + z1 + 0.038), 0.034, b["Shoulder"], TI, segs=12)
    k.cyl((E.x, E.y, ZC0 + z1 + 0.037), (E.x, E.y, ZC0 + z1 + 0.042), 0.020, b["Shoulder"], BRZ, segs=10)
    z0, z1, r0, r1, ch = FORE
    machine(k, link_bm(E, r0, W, r1, ZC0 + z0, ZC0 + z1, ch), link_vents(E, W, ZC0 + z1), b["Elbow"],
            lambda f, c, cut: FRM if cut else PRI)
    k.cyl((E.x, E.y, ZC0 + z1 - 0.002), (E.x, E.y, ZC0 + UPPER[0] + 0.010), 0.018, b["Elbow"], JNT, segs=12)
    k.cyl((W.x, W.y, ZC0 + z0 + 0.002), (W.x, W.y, ZC0 + z0 - 0.004), 0.030, b["Elbow"], BRZ, segs=12)


def tool_hub(k, bone):
    """(In the tool's frame) the tool's black hub turning under the wrist's bearing ring, its stainless axle up
    through the ring into the forearm."""
    k.cyl((0, 0, HUB[0] + TOOL_DZ), (0, 0, HUB[1] + TOOL_DZ), HUB[2], bone, FRM, segs=12)
    k.cyl((0, 0, HUB[1] + TOOL_DZ - 0.002), (0, 0, FORE[0] + TOOL_DZ + 0.010), 0.014, bone, JNT, segs=10)


def build_torch(k):
    """The left arm's welding torch: an off-white lofted body out of the hub with a grey collar, tapering to a
    stainless nozzle, slanted vents on its top and a lit arc at its tip (TorchTip)."""
    bone = "WristLeft"
    with k.frame(tool_frame("Left")):
        tool_hub(k, bone)
        body = loft_bm([oct_section(*sec) for sec in ((-0.012, 0.026, 0.026), (0.080, 0.026, 0.026),
                                                      (0.100, 0.023, 0.023), (0.122, 0.019, 0.019),
                                                      (0.145, 0.015, 0.015), (0.165, 0.012, 0.012))])
        vents = lean_slots((0, 0, 0.026), UP, (0, 1, 0), (1, 0, 0), [0.030, 0.044, 0.058], 0.007, -0.013, 0.013, 0.005,
                           0.003)
        machine(k, body, vents, bone, lambda f, c, cut: FRM if cut else (SEC if 0.100 < c.y < 0.122 else PRI))
        k.cyl((0, 0.163, 0), (0, 0.190, 0), 0.0115, bone, JNT, segs=10, r1=0.007)
        k.cyl((0, 0.189, 0), (0, TORCH_TIP, 0), 0.0045, bone, EMI, segs=8)


def build_gripper(k):
    """The right arm's gripper: a titanium roll motor out of the hub, its stainless rotor face turning a grey
    palm whose front is slotted into two jaws; in the slot two off-white fingers turn on stainless pins
    (bosses on the jaws), black pads on their tips (GripperCenter between them)."""
    with k.frame(tool_frame("Right")):
        tool_hub(k, "WristRight")
        k.cyl((0, 0.018, 0), (0, ROLL_S, 0), 0.026, "WristRight", TI, segs=12)
        k.cyl((0, ROLL_S - 0.001, 0), (0, ROLL_S + 0.005, 0), 0.022, ROLL, JNT, segs=12)
        palm = chamfer_box_bm((-0.028, ROLL_S + 0.004, -0.019), (0.028, 0.126, 0.019), 0.004)
        machine(k, palm, [block_bm((0, 0.121, 0), (0.075, 0.038, 0.015))], ROLL, lambda f, c, cut: FRM if cut else SEC)
        fs = FINGER[0]
        for name, sgn in zip(FINGERS, (-1, 1)):
            fx = sgn * FINGER[1]
            for z0, z1 in ((0.0185, 0.0235), (-0.0235, -0.0185)):
                k.cyl((fx, fs, z0), (fx, fs, z1), 0.0065, ROLL, JNT, segs=8)
            ring = [(fx + 0.008 * math.cos(a), fs + 0.008 * math.sin(a)) for a in (i * math.pi / 4 for i in range(8))]
            outline = hull2d(ring + [(sgn * 0.031, 0.165), (sgn * 0.016, 0.196), (sgn * 0.004, GRIP_TIP),
                                     (sgn * 0.004, 0.153)])
            k.prism([(u, v, 0.0) for u, v in outline], 0.013, UP, name, PRI)
            span_sorted(k, (sgn * 0.0025, 0.165, -0.005), (sgn * 0.0045, 0.194, 0.005), name, FRM)
            k.cyl((fx, fs, -0.021), (fx, fs, 0.021), 0.0034, name, JNT, segs=6)


def build_all(k, pistons, joints):
    build_deck(k)
    build_towers(k)
    build_rails(k)
    for side in ARMS:
        build_carriage(k, side)
        build_links(k, side)
    build_torch(k)
    build_gripper(k)


# --------------------------------------------------------------------------------------------
# The patient: Tensor standing on the pad in his idle
# --------------------------------------------------------------------------------------------

def load_patient():
    """Tensor as built (his body and default head, models/characters/tensor) in his idle clip (the animation
    library's baked action), standing on the pad at PlayerMount: his world-space mesh on each of IDLE_FRAMES
    (one BVH over them all, for the arms' paths and checks), and his first frame as static preview-only
    meshes (PRV_Tensor*, never exported). His rig and meshes are then removed again."""
    for path in (TENSOR_BLEND, TENSOR_IDLE):
        if not path.exists():
            raise SystemExit(f"[{NAME}] {path} not found - run Tensor's model.py and animations/retarget.py first")
    names = ["RIG_Tensor", "SK_Tensor", "SK_TensorHeadProjector"]
    with bpy.data.libraries.load(str(TENSOR_BLEND), link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    objs = {o.name: o for o in dst.objects if o is not None}
    if sorted(objs) != sorted(names):
        raise SystemExit(f"[{NAME}] {TENSOR_BLEND} lacks {names}")
    scene = bpy.context.scene
    for o in objs.values():
        scene.collection.objects.link(o)
    with bpy.data.libraries.load(str(TENSOR_IDLE), link=False) as (src, dst):
        dst.actions = list(src.actions)
    action = dst.actions[0]
    rig = objs["RIG_Tensor"]
    rig.animation_data_create()
    rig.animation_data.action = action
    meshes = [objs["SK_Tensor"], objs["SK_TensorHeadProjector"]]
    lift = Matrix.Translation((0, 0, DECK))
    verts, polys = [], []
    for f in IDLE_FRAMES:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for o in meshes:
            ev = o.evaluated_get(dg)
            m = ev.to_mesh()
            base = len(verts)
            verts += [lift @ (ev.matrix_world @ v.co) for v in m.vertices]
            polys += [[base + i for i in p.vertices] for p in m.polygons]
            ev.to_mesh_clear()
    scene.frame_set(IDLE_FRAMES[0])
    dg = bpy.context.evaluated_depsgraph_get()
    preview = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(lift @ ev.matrix_world)
        prv = bpy.data.objects.new("PRV_" + o.name[3:], me)
        scene.collection.objects.link(prv)
        preview.append(prv)
    scene.frame_set(0)
    arm_data = rig.data
    for o in objs.values():
        data = o.data
        bpy.data.objects.remove(o)
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
    bpy.data.armatures.remove(arm_data)
    bpy.data.actions.remove(action)
    lo = Vector(min(v[i] for v in verts) for i in range(3))
    hi = Vector(max(v[i] for v in verts) for i in range(3))
    return BVHTree.FromPolygons(verts, polys), preview, (lo, hi)


# --------------------------------------------------------------------------------------------
# The arms' paths: inverse kinematics against the patient
# --------------------------------------------------------------------------------------------

A1_REST = 180.0                        # the upper link's heading at rest (the left arm's frame: to the front)


def hvec(a):
    """A heading (degrees, counter-clockwise from +Y about +Z) as a unit vector in the plane."""
    r = math.radians(a)
    return Vector((-math.sin(r), math.cos(r)))


def heading(v):
    return math.degrees(math.atan2(-v[0], v[1]))


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ik(side, tip, a_tool, prev=None):
    """The arm's shoulder, elbow and wrist values putting its tool's tip at `tip` (x, y) heading a_tool
    (degrees), the elbow out on the side away from the patient; solved in the left arm's frame (the right arm
    is it turned half round). With `prev`, each value is taken nearest the previous one."""
    q = turn(side).transposed() @ Vector((tip[0], tip[1], 0.0))
    a = a_tool - (0.0 if side == "Left" else 180.0)
    S = Vector((XS, 0.0))
    W = Vector((q.x, q.y)) - hvec(a) * TIP[side]
    sw = W - S
    d = sw.length
    if not abs(L1 - L2) + 0.02 < d < 0.985 * (L1 + L2):
        raise SystemExit(f"[{NAME}] {side} arm: tip {tuple(round(c, 3) for c in tip)} out of reach "
                         f"(wrist {d:.3f} m from the shoulder)")
    alpha = math.degrees(math.acos((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))
    a1 = heading(sw) + alpha
    a2 = heading(W - (S + hvec(a1) * L1))
    v = [wrap(a1 - A1_REST), wrap(a2 - a1 - 180.0), wrap(a - a2)]
    if prev is not None:
        v = [p + wrap(x - p) for x, p in zip(v, prev)]
    return v


def probe(bvh, side, aim, d, zs):
    """Where the tool's tip stops at a spot: STANDOFF short of the first of Tensor's surfaces met coming in
    along d on the line over `aim`, across the tool's width and height and over each height in zs."""
    d3, p = Vector((d.x, d.y, 0.0)), Vector((-d.y, d.x, 0.0))
    start = Vector((aim[0], aim[1], 0.0)) - d3 * 1.5
    best = None
    for z in zs:
        for dl in (-1.0, -0.5, 0.0, 0.5, 1.0):
            for dz in (-0.03, 0.0, 0.03):
                o = start + p * (dl * PROBE_W[side]) + Vector((0, 0, z + dz))
                hit = bvh.ray_cast(o, d3, 3.0)[0]
                if hit is not None:
                    t = (hit - o).dot(d3)
                    best = t if best is None else min(best, t)
    if best is None:
        raise SystemExit(f"[{NAME}] {side} arm: no surface of Tensor on the line over {aim}")
    tip = start + d3 * (best - STANDOFF[side])
    return Vector((tip.x, tip.y))


def track(keys, tau):
    """A piecewise track [(frame, value), ...] at tau: each move eases in and out between its keys."""
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= tau <= f1:
            return v0 + (v1 - v0) * (smooth((tau - f0) / (f1 - f0)) if f1 > f0 else 1.0)
    return keys[-1][1]


GRIP_CLOSED, TWIST, WEAVE = 3.0, 60.0, (0.006, 3)   # the gripper's grip and twist (deg); the weld's weave (m, count)
GRIP_CYCLE = 39                        # frames of one grip-turn-release (one per spot)


def arm_plan(side, bvh):
    """An arm's repair loop as eased tracks over one loop: its tool tip (x, y), heading and axis height, and
    (the gripper) its fingers and roll; each spot: approach, work (the torch welds a seam upward, weaving; the
    gripper grips, turns and lets go), back off, travel to the next."""
    ta, tw, tr, tt = SPOT_T
    tip, head, zs, grip, roll, work, travel = [], [], [], [(0, 0.0)], [(0, 0.0)], [], []
    t = 0
    for z, aim, d in SPOTS[side]:
        d = Vector(d).normalized()
        z0, z1 = (z - SEAM / 2, z + SEAM / 2) if TOOLS[side] == "torch" else (z, z)
        at = probe(bvh, side, aim, d, (z0, z1))
        back = at - d * RETREAT
        a = heading(d) if not head else head[-1][1] + wrap(heading(d) - head[-1][1])
        w = t + ta
        tip += [(t, back), (w, at), (w + tw, at), (w + tw + tr, back)]
        head += [(t, a), (w + tw + tr, a)]
        zs += [(t, z0), (w, z0), (w + tw, z1), (w + tw + tr, z1)]
        work.append((w, w + tw, Vector((-d.y, d.x))))
        travel.append((w + tw + tr, w + tw + tr + tt, d))
        if TOOLS[side] == "gripper":
            grip += [(t + 2, 0.0), (t + 12, FINGER[2])]
            n = max(1, round(tw / GRIP_CYCLE))
            for i in range(n):  # each cycle: close, turn, let go, turn back open
                c, span = w + i * tw / n, tw / n
                grip += [(c + 0.05 * span, FINGER[2]), (c + 0.19 * span, GRIP_CLOSED), (c + 0.67 * span, GRIP_CLOSED),
                         (c + 0.83 * span, FINGER[2])]
                roll += [(c + 0.19 * span, 0.0), (c + 0.64 * span, TWIST), (c + 0.83 * span, TWIST), (c + span, 0.0)]
            grip += [(w + tw, FINGER[2]), (w + tw + tr, 0.0)]
        t = w + tw + tr + tt
    if t != LOOP:
        raise SystemExit(f"[{NAME}] {side} arm: its spots take {t} frames, not {LOOP}")
    tip.append((LOOP, tip[0][1]))
    head.append((LOOP, head[0][1] + 360.0 * round((head[-1][1] - head[0][1]) / 360.0)))
    zs.append((LOOP, zs[0][1]))
    grip.append((LOOP, 0.0))
    roll.append((LOOP, 0.0))
    # each travel bows out, away from him: along both approaches' mean, backward
    travel = [(t0, t1, -(d + travel[(i + 1) % len(travel)][2]).normalized()) for i, (t0, t1, d) in enumerate(travel)]
    return {"tip": tip, "head": head, "z": zs, "grip": grip, "roll": roll, "work": work, "travel": travel}


def arm_frames(side, plan):
    """The arm's joint values on every frame of the repair loop (its schedule PHASE frames ahead)."""
    b = arm_bones(side)
    out, prev = [], None
    for f in range(LOOP + 1):
        tau = (f + PHASE[side]) % LOOP
        p = track(plan["tip"], tau)
        if TOOLS[side] == "torch":
            for w0, w1, lat in plan["work"]:
                if w0 <= tau <= w1:
                    u = (tau - w0) / (w1 - w0)
                    p = p + lat * (WEAVE[0] * math.sin(2 * math.pi * WEAVE[1] * u) * math.sin(math.pi * u))
        for t0, t1, away in plan["travel"]:
            if t0 <= tau <= t1:
                p = p + away * (BOW * math.sin(math.pi * (tau - t0) / (t1 - t0)))
        prev = ik(side, p, track(plan["head"], tau), prev)
        vals = {b["Carriage"]: track(plan["z"], tau) + TOOL_DZ - ZC0, b["Shoulder"]: prev[0], b["Elbow"]: prev[1],
                b["Wrist"]: prev[2]}
        if TOOLS[side] == "gripper":
            vals[ROLL] = track(plan["roll"], tau)
            vals[FINGERS[0]] = vals[FINGERS[1]] = track(plan["grip"], tau)
        out.append(vals)
    return out


def frame_of(keys, f):
    """A joint state from animation keys at frame f (keys on every frame)."""
    return {j: dict(ks)[f] for j, ks in keys.items()}


def fk_tip(side, v):
    """The tool's tip (x, y) and heading of an arm at shoulder, elbow and wrist values v (the inverse of ik)."""
    a1 = A1_REST + v[0]
    E = Vector((XS, 0.0)) + hvec(a1) * L1
    a2 = a1 + 180.0 + v[1]
    a = a2 + v[2]
    q = E + hvec(a2) * L2 + hvec(a) * TIP[side]
    tip = turn(side) @ Vector((q.x, q.y, 0.0))
    return Vector((tip.x, tip.y)), a + (0.0 if side == "Left" else 180.0)


def arm_rise(side, plan, ready):
    """The arm's activate: from folded (rest) it unfolds low down, where Tensor is slim (UNFOLD, eased in joint
    space: its tool swings round to the front of its tower), backs its tool off along the first approach
    (OUT), rises to the repair's first height there and closes in to the repair's first frame (eased in the
    plane, by ik); every frame keyed."""
    b = arm_bones(side)
    tau = PHASE[side] % LOOP
    tip0, head0, z0 = track(plan["tip"], tau), track(plan["head"], tau), track(plan["z"], tau)
    unfold = [UNFOLD[0], UNFOLD[1], 0.0]      # the wrist turns the tool to the first approach's heading
    unfold[2] = wrap(head0 - (0.0 if side == "Left" else 180.0) - (A1_REST + 180.0 + unfold[0] + unfold[1]))
    tip_u, head_u = fk_tip(side, unfold)
    head0 = head_u + wrap(head0 - head_u)
    out = tip0 - hvec(head0) * OUT
    zp = ZC0 - TOOL_DZ
    f0, f1, f2, f3, f4 = RISE
    tips = [(f1, tip_u), (f2, out), (f3, out), (f4, tip0)]
    heads = [(f1, head_u), (f2, head0), (f4, head0)]
    zs = [(f1, zp), (f2, zp), (f3, z0), (f4, z0)]
    frames, prev = [], list(unfold)
    for f in range(RAMP + 1):
        if f <= f1:
            u = smooth((f - f0) / (f1 - f0))
            vals = {b["Carriage"]: 0.0, b["Shoulder"]: unfold[0] * u, b["Elbow"]: unfold[1] * u, b["Wrist"]: unfold[2] * u}
        else:
            prev = ik(side, track(tips, f), track(heads, f), prev)
            vals = {b["Carriage"]: track(zs, f) + TOOL_DZ - ZC0, b["Shoulder"]: prev[0], b["Elbow"]: prev[1],
                    b["Wrist"]: prev[2]}
        frames.append(vals)
    for j, v in frames[-1].items():
        if abs(v - ready[j]) > 1e-4:
            raise SystemExit(f"[{NAME}] {side} arm: activate ends at {j} {v:.3f}, not the repair's {ready[j]:.3f}")
    return frames


def plan_animations(joints, bvh):
    """The actions, planned against the patient: repair (both arms' loops, keyed every frame), activate (the
    shield rises out of its ring; each arm unfolds low down, where Tensor is slim, then rises clear of him and
    closes in to the repair's first frame) and deactivate (activate's arms played backward, then the shield
    sinks). Also the preview states."""
    plans = {side: arm_plan(side, bvh) for side in ARMS}
    frames = {side: arm_frames(side, plans[side]) for side in ARMS}
    repair = [{**frames["Left"][f], **frames["Right"][f]} for f in range(LOOP + 1)]
    ready = repair[0]
    rises = {side: arm_rise(side, plans[side], ready) for side in ARMS}
    extras = {j: v for j, v in ready.items() if j in (ROLL, *FINGERS)}   # (the gripper's, at rest there)
    act = [{**rises["Left"][f], **rises["Right"][f], **extras} for f in range(RAMP + 1)]
    deact = act[::-1]

    def keyed(seq):
        return {j: [(f, round(s[j], 5)) for f, s in enumerate(seq)] for j in seq[0]}

    anims = {"activate": (False, "LINEAR", keyed(act)), "repair": (True, "LINEAR", keyed(repair)),
             "deactivate": (False, "LINEAR", keyed(deact))}
    shrink = 0.999
    shield = {"activate": [(f, round(1 - shrink * (1 - smooth(f / SHIELD_T)), 5)) for f in range(RAMP + 1)],
              "deactivate": [(f, round(1 - shrink * smooth((f - (RAMP - SHIELD_T)) / SHIELD_T), 5))
                             for f in range(RAMP + 1)]}
    weld = (SPOT_T[0] + SPOT_T[1] // 2 - PHASE["Left"]) % LOOP                # the torch mid-seam at the chest
    grip = (SPOT_T[0] + GRIP_CYCLE // 2 - PHASE["Right"]) % LOOP                # the gripper mid-turn at the pack
    rising = SHIELD_T // 2
    states = {"ready": dict(ready), "weld": dict(repair[weld]), "grip": dict(repair[grip]),
              "reach": dict(repair[LOOP // 2]), "rising": dict(act[rising])}
    views = {"ready": ["front_left", "rear_right", "front", "left", "top"], "weld": ["front_left", "left"],
             "grip": ["rear_right", "back"], "reach": ["front_left", "rear_right", "top"], "rising": ["front_left"]}
    return anims, shield, states, {"rising": shield["activate"][rising][1]}, views


# --------------------------------------------------------------------------------------------
# Actions (the framework's, with the shield's height scale keyed)
# --------------------------------------------------------------------------------------------

def build_actions(rig, joints, pistons):
    """One action per animation, each on its own muted NLA track so every one is exported; the shield bone's
    height scale (its local Y, up) keyed in the actions that raise and lower it."""
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
        pb = rig.pose.bones[SHIELD_BONE]
        for frame, value in SHIELD_KEYS.get(name, ()):
            pb.scale = (1.0, value, 1.0)
            pb.keyframe_insert("scale", index=1, frame=frame)
        pb.scale = (1.0, 1.0, 1.0)
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
        track_ = rig.animation_data.nla_tracks.new()
        track_.name = name
        track_.strips.new(name, 0, action)
        track_.mute = True
        reset_pose(rig)
    return actions


# --------------------------------------------------------------------------------------------
# The station's checks
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """The carriages' whole travel with the arms stowed, and the gripper's roll and fingers over their ranges
    at the ready pose, on top of the animation frames."""
    out = [(f"carriages {v:.2f}", {"CarriageLeft": v, "CarriageRight": v}) for v in (TRAVEL[0] + (TRAVEL[1] - TRAVEL[0]) * i / 12 for i in range(13))]
    ready = PREVIEW_STATES["ready"]
    lo, hi = LIMITS["Roll"]
    return out + [(f"roll {r:+.0f} fingers {g:.0f}", {**ready, ROLL: r, FINGERS[0]: g, FINGERS[1]: g})
                  for r in (lo, lo / 2, 0.0, hi / 2, hi) for g in (0.0, LIMITS["Finger"][1] / 2, LIMITS["Finger"][1])]


def inside_shield(v, margin=SHIELD_MARGIN):
    """Is a point inside the shield's dome (its wall, then the half-ellipse over it), `margin` in from it?"""
    r_s, zw, hc = SHIELD
    r = math.hypot(v.x, v.y)
    if v.z <= zw:
        return r <= r_s - margin
    return (r / (r_s - margin)) ** 2 + ((v.z - zw) / (hc - margin)) ** 2 <= 1.0


def check_envelope(kit, joints, states):
    """In every state nothing leaves the 2 x 2 m tile or goes under the floor, and everything over the deck
    stays SHIELD_MARGIN inside the shield; the deck's bottom is on the floor; stowed (rest), nothing but the
    deck stands in the entry corridor (|x| < CORRIDOR[0], up to CORRIDOR[1]) Tensor walks in and out through."""
    problems = []
    low = min(v.z for p in all_parts(kit) for v in p.verts)
    if abs(low) > 1e-6:
        problems.append(f"lowest point at z {low:.4f}: the deck is not on the floor")
    top = 0.0
    for tag, state in [("rest", {})] + states:
        m = fk(joints, expand(state))
        for part in all_parts(kit):
            if part.bone == "Root" and tag != "rest":
                continue
            vs = [m[part.bone] @ v for v in part.verts]
            top = max(top, max(v.z for v in vs))
            if any(abs(v.x) > HALF + 1e-6 or abs(v.y) > HALF + 1e-6 or v.z < -1e-6 for v in vs):
                problems.append(f"{part.bone} (line {part.line}) leaves the tile at {tag}")
            if not all(inside_shield(v) for v in vs if v.z > DECK + 1e-4):
                problems.append(f"{part.bone} (line {part.line}) leaves the shield at {tag}")
    for part in all_parts(kit):
        if any(abs(v.x) < CORRIDOR[0] and DECK + 1e-4 < v.z < CORRIDOR[1] for v in part.verts):
            problems.append(f"{part.bone} (line {part.line}) stands in the entry corridor, stowed")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(list(dict.fromkeys(problems))[:40]))
    return top


def patient_states():
    """Every frame of every action."""
    out = []
    for name, (_, _, keys) in ANIMATIONS.items():
        n = max(f for ks in keys.values() for f, _ in ks)
        out += [(f"{name} frame {f}", frame_of(keys, f)) for f in range(n + 1)]
    return out


def check_patient(kit, joints, bvh, box):
    """Tensor standing on the pad in his idle (every sampled frame at once): on every frame of every action no
    part of an arm or carriage enters him or comes within PATIENT_CLEAR of him (its corners and faces' centres).
    Returns the nearest approach and where."""
    arm = [p for p in all_parts(kit) if p.bone != "Root"]
    lo, hi = box[0] - Vector((0.1,) * 3), box[1] + Vector((0.1,) * 3)
    samples = {id(p): p.verts + [sum((p.verts[i] for i in f), Vector()) / len(f) for f in p.faces] for p in arm}
    problems, near = [], (1.0, "")
    for tag, state in patient_states():
        m = fk(joints, expand(state))
        for p in arm:
            mm = m[p.bone]
            cs = [mm @ Vector((x, y, z)) for x in (p.lo.x, p.hi.x) for y in (p.lo.y, p.hi.y) for z in (p.lo.z, p.hi.z)]
            if any(min(c[i] for c in cs) > hi[i] or max(c[i] for c in cs) < lo[i] for i in range(3)):
                continue
            if p.moved(mm).bvh.overlap(bvh):
                problems.append(f"{p.bone} (line {p.line}) enters Tensor at {tag}")
                continue
            for v in samples[id(p)]:
                d = bvh.find_nearest(mm @ v)[3]
                if d is not None and d < near[0]:
                    near = (d, f"{p.bone} (line {p.line}) at {tag}")
    if near[0] < PATIENT_CLEAR:
        problems.append(f"{near[1]}: {1000 * near[0]:.1f} mm from Tensor (under {1000 * PATIENT_CLEAR:.0f} mm)")
    if problems:
        raise SystemExit(f"[{NAME}] patient check failed:\n  " + "\n  ".join(list(dict.fromkeys(problems))[:40]))
    return near


# --------------------------------------------------------------------------------------------
# The shield, gizmos, preview and export
# --------------------------------------------------------------------------------------------

def build_shield_material():
    """M_Shield: the game's shader replaces it; for previews a solid 90% transparent emissive (double-sided)."""
    name, color, alpha, strength = SHIELD_MATERIAL
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.2
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    mat.diffuse_color = (*color, alpha)
    mat.use_backface_culling = False
    for attr, value in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, value)
            except (TypeError, AttributeError):
                pass
    return mat


def shield_profile():
    """The shield's section (radius, z) from its foot in the emitter groove up the wall, then round the
    half-ellipse of its dome to the apex."""
    r, zw, hc = SHIELD
    return [(r, SHIELD_Z0), (r, zw)] + [(r * math.cos(math.radians(a)), zw + hc * math.sin(math.radians(a)))
                                         for a in (15, 30, 45, 60, 75)] + [(0.0, zw + hc)]


def build_shield(rig, mat):
    """SK_RepairStationShield: the dome over the bay (RING_N sides, smooth), rigid on the Shield bone (its foot
    in the emitter groove: scaling the bone's height grows it out of the ring). One M_Shield slot. UVs: u 0..1
    round it from +X toward +Y, v 0 at its foot to 1 at the apex (by length along the section)."""
    prof = shield_profile()
    lengths = [0.0]
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        lengths.append(lengths[-1] + math.hypot(r1 - r0, z1 - z0))
    vs = [l / lengths[-1] for l in lengths]
    n = RING_N
    verts, faces, uvs = [], [], []
    rings = []
    for r, z in prof[:-1]:
        rings.append(len(verts))
        verts += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    apex = len(verts)
    verts.append((0.0, 0.0, prof[-1][1]))
    for k in range(len(rings)):
        for i in range(n):
            j = (i + 1) % n
            if k + 1 < len(rings):
                faces.append((rings[k] + i, rings[k] + j, rings[k + 1] + j, rings[k + 1] + i))
                uvs.append([(i / n, vs[k]), ((i + 1) / n, vs[k]), ((i + 1) / n, vs[k + 1]), (i / n, vs[k + 1])])
            else:
                faces.append((rings[k] + i, rings[k] + j, apex))
                uvs.append([(i / n, vs[k]), ((i + 1) / n, vs[k]), ((i + 0.5) / n, 1.0)])
    mesh = bpy.data.meshes.new(f"SK_{TITLE}Shield_Mesh")
    mesh.from_pydata(verts, [], faces)
    uv = mesh.uv_layers.new(name="UVMap")
    for poly, face_uv in zip(mesh.polygons, uvs):
        for li, co in zip(poly.loop_indices, face_uv):
            uv.data[li].uv = co
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(f"SK_{TITLE}Shield", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.vertex_groups.new(name=SHIELD_BONE).add(list(range(len(verts))), 1.0, "REPLACE")
    if hasattr(obj, "visible_shadow"):
        obj.visible_shadow = False
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
    """(name, bone, origin, forward, up): PlayerMount on the pad's centre (where Tensor stands, facing out of
    the front); for the game's effects (user): TorchTip at the welding arc (along the torch: sparks, the arc's
    light and flicker), GripperCenter between the fingertips (along the gripper), ShieldCenter in the middle
    of the shield (its hum, hits on it), and DownlightLeft / DownlightRight on the hoods' lamps (pointing
    down: light cones, scan beams)."""
    tl, tr = tool_frame("Left"), tool_frame("Right")
    return [("PlayerMount", "Root", (0.0, 0.0, DECK), FWD, UP),
            ("TorchTip", "WristLeft", tuple(tl @ Vector((0, TORCH_TIP, 0))), tuple(tl.col[1][:3]), UP),
            ("GripperCenter", ROLL, tuple(tr @ Vector((0, 0.186, 0))), tuple(tr.col[1][:3]), UP),
            ("ShieldCenter", "Root", (0.0, 0.0, round((SHIELD_Z0 + SHIELD[1] + SHIELD[2]) / 2, 4)), FWD, UP)] + [
            (f"Downlight{side}", "Root", (s * DOWNLIGHT[0], 0.0, round(hood_underside(DOWNLIGHT[0]) + DOWNLIGHT[2], 4)),
             DOWN, FWD) for side, s in ARMS.items()]


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


def build_preview_floor():
    """A floor slab round the tile, for previews only (never exported)."""
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


def weld_windows():
    """repair's frame windows while the torch welds (its work at each spot, shifted by its PHASE)."""
    ta, tw, tr, tt = SPOT_T
    per = sum(SPOT_T)
    return [[(i * per + ta - PHASE["Left"]) % LOOP, (i * per + ta + tw - PHASE["Left"]) % LOOP]
            for i in range(len(SPOTS["Left"]))]


def write_rig_json(joints, tris, shield_tris, top, near):
    def vec(v):
        return [round(c, 4) for c in v]

    r_s, zw, hc = SHIELD
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, front -Y, left +X; the origin is on the floor at the tile's centre. glTF/Godot: "
                 "(x, z, -y). Hinges turn about their bones' local X (degrees), carriages slide along their bones' local "
                 "Y (metres, + up), the shield bone scales along its local Y (up).",
        "rest": "stowed: the carriages parked high (the tools at 1.4 m), the arms folded along the towers (the left one pointing to the front, "
                "the right one to the back), the gripper closed; the shield at full size (the bind pose: hide it while "
                "the station is idle, or hold deactivate's last frame)",
        "size_m": {"footprint": [2 * HALF, 2 * HALF], "deck_height": DECK, "height": round(top, 4),
                   "note": "(user) it stands on a 2 x 2 m floor tile and matches it exactly: square outside corners, "
                           "nothing leaves the tile in any state"},
        "patient": {"gizmo": "PlayerMount", "note": "put the player on PlayerMount (on the pad, facing the station's front, "
                    "-Z in Godot) and let him idle there; the arms' paths are planned against Tensor's idle clip "
                    "(animations/target tensor/common/idle) and keep clear of him on every frame",
                    "nearest_m": round(near, 4), "clearance_min_m": PATIENT_CLEAR,
                    "entry": f"with the arms stowed nothing but the deck stands within |x| < {CORRIDOR[0]} m: he walks in "
                             "and out at the front or the back"},
        "shield": {"object": f"SK_{TITLE}Shield", "material": SHIELD_MATERIAL[0], "triangles": shield_tris,
                   "bone": SHIELD_BONE, "shape": {"radius": r_s, "wall_top": zw, "apex": zw + hc, "foot_z": round(SHIELD_Z0, 4),
                                                   "note": "a wall round the bay, then a half-ellipse dome"},
                   "uv": "u 0..1 round it from +X toward +Y (the station's left, then its back), v 0 at its foot to 1 at "
                         "the apex (by length along its section)",
                   "animation": "its bone's local Y scale (height) grows 0.001 -> 1 in activate and shrinks back in "
                                "deactivate; repair doesn't key it",
                   "shader": "the game's: while it is up, bullets and blasts stop on it; 90% transparent emissive in "
                             "previews (double-sided)"},
        "arms": {"kinematics": "SCARA: a carriage sliding up its tower, then a shoulder, an elbow and a wrist turning "
                               "about vertical axes; the right arm is the left one turned half round, so the same values "
                               "move it alike",
                 "links_m": [L1, L2], "tool_reach_m": {"torch": TORCH_TIP, "gripper": GRIP_TIP},
                 "tools": {"Left": "welding torch (TorchTip)", "Right": "gripper: roll, two fingers (GripperCenter)"}},
        "gizmos": [{"name": n, "bone": b, "origin": vec(o), "forward": vec(f), "up": vec(u),
                    "godot": "-Z along forward, +Y up"} for n, b, o, f, u in gizmo_specs()],
        "materials_note": "the environment props' finish in Tensor's materials (off-white and grey paint, matte black, "
                          "stainless steel, bronze, titanium): no team colours; M_Shield is the shield's own slot",
        "materials": SLOTS + [SHIELD_MATERIAL[0]],
        "triangles": tris,
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)], "fps": FPS, "loop": loop,
                              "joints": sorted(expand(keys)) + ([SHIELD_BONE] if name in SHIELD_KEYS else [])}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "effects": {"TorchTip": {"welding_frames": weld_windows(), "note": "repair's frames (at 30 fps) while the torch "
                                 "welds: run the sparks and the arc's flicker on TorchTip then"}},
        "usage": f"When the player stands on the pad: snap him to PlayerMount, show the shield and play activate "
                 f"({RAMP / FPS:.0f} s, shield on: it grows out of its ring while the arms unfold and come down to him), then "
                 f"repair ({LOOP / FPS:.0f} s: the torch welds two seams over his front, the gripper grips and turns at his "
                 "back; it ends where it starts, so loop it for a longer repair), then deactivate "
                 f"({RAMP / FPS:.0f} s, shield off: the arms fold away while the shield sinks) and hide the shield. The shield "
                 "blocks hits from activate to deactivate.",
    }
    RIG_JSON_PATH.write_text(json.dumps(data, indent=2))


def main():
    global ANIMATIONS, SHIELD_KEYS, PREVIEW_STATES, PREVIEW_SHIELD, PREVIEW_VIEWS
    reset_scene()
    build_materials()
    shield_mat = build_shield_material()
    bvh, patient, box = load_patient()
    joints = resolve_joints()
    ANIMATIONS, SHIELD_KEYS, PREVIEW_STATES, PREVIEW_SHIELD, PREVIEW_VIEWS = plan_animations(joints, bvh)
    pistons = resolve_pistons(joints)
    check_states(joints)
    rig = build_rig(joints, pistons)
    check_rig_fk(rig, joints)
    actions = build_actions(rig, joints, pistons)

    kit = Kit()
    build_all(kit, pistons, joints)
    states = action_states(actions, joints) + sweep_states(joints)
    top = check_envelope(kit, joints, states)
    check_footprint(kit, (-HALF, -HALF), (HALF, HALF), [0.0, DECK])
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_motion(kit, joints, states)
    near, where = check_patient(kit, joints, bvh, box)
    print(f"[{NAME}] checks passed ({len(states)} motion states); {top:.3f} m tall; the arms keep "
          f"{1000 * near:.1f} mm from Tensor at the nearest ({where})")

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    check_coplanar(body)
    skin(body, rig)
    if "--no-cull" not in sys.argv:
        cull_unseen(body, rig, joints, pistons, states[::3], (-HALF, -HALF), (HALF, HALF), PLATFORM_FRAME)
    sys.path.insert(0,str(HERE.parents[1]))
    from gameplay.dimensions import assert_authored_bounds
    assert_authored_bounds(HERE.name,[body])
    unwrap(body)
    shield = build_shield(rig, shield_mat)
    tris, shield_tris = triangles(body), triangles(shield)
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET}); shield: {shield_tris} tris (budget {SHIELD_BUDGET})")
    if tris > TRI_BUDGET and "--no-cull" not in sys.argv:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")
    if shield_tris > SHIELD_BUDGET:
        raise SystemExit(f"[{NAME}] shield over its triangle budget: {shield_tris}")

    gizmos = build_gizmos(rig)
    export([rig, body, shield, *gizmos], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, tris, shield_tris, top, near)
    build_preview_floor()

    def pose_entry(jname, v):
        return {"rot": [v, 0, 0]} if joints[jname].kind == "hinge" else {"loc": [0, v, 0]}

    poses = {s: {j: pose_entry(j, v) for j, v in expand(st).items()} for s, st in PREVIEW_STATES.items()}
    for s, v in PREVIEW_SHIELD.items():
        poses[s][SHIELD_BONE] = {"scale": [1.0, v, 1.0]}
    shown = [o.name for o in patient] + [shield.name]
    rig["preview_poses"] = json.dumps(poses)
    rig["preview_pose_views"] = json.dumps(PREVIEW_VIEWS)
    rig["preview_pose_show"] = json.dumps({s: shown for s in PREVIEW_STATES if s != "reach"})
    for o in patient + [shield]:  # the patient and the shield show only in the repair's renders and the showcase
        o.hide_render = True
    scene = bpy.context.scene
    scene["preview_actions"] = json.dumps(SHOWCASE)
    scene["preview_frame"] = json.dumps(PREVIEW_FRAME)
    scene["preview_show"] = json.dumps(shown)
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
