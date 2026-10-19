"""Weapon holder - a weapon pickup that holds the weapon in claws, for KYLR, modelled, rigged
and animated from script. Authored on the floor like the item table (user); the game turns it onto a
wall where it needs one.

Run headless from the repo root:
    blender --background --factory-startup --python models/gameplay/weapon_holder/model.py

Produces, next to this script:
    weapon_holder.blend          source scene (the holder plus a preview-only weapon marker and
                                 floor slab), opened by preview.py and animate.py
    weapon_holder.glb / .fbx     SK_WeaponHolder skinned to RIG_WeaponHolder, with the actions
                                 deploy, retract, claw_open, claw_close and spin
    weapon_holder_rig.json       joints (hinges and slides) with ranges, pistons, the grip table,
                                 animations, the weapon socket and the floor cut-out it needs

Design: the item table's turret with claws. The patch is a 1 x 1 m square frame flush with the
floor round a centred 0.5 x 0.9 m hole, a light strip centred in each thick side. Two door leaves
hinged on the hole's long edges close it flush and swing in to hang against the pit's sides; the
pit, walled in grey, stays inside the patch's footprint. A four-stage
telescopic jack in the pit's centre raises the turret: a grooved drum (the shaft) that
spins in a slew bearing on the jack's top stage, a platform 0.1 m off the floor (an octagonal
shell lofted from the drum's round section, slanted vents on its plain faces, a deck plate on top), and
two 0.25 m arms either side of the weapon, hinged on the platform (their ends 0.3 m up from it,
as the item table's top platform is above its base). Each arm is one unibody shell (the weapons'
language: a side profile with round ends, chamfered all round its flanks, carved with exact
booleans): a knuckle round about its hinge and a pillar tapering up into a head that turns in to a
nose round about the claw's servo axle. One hydraulic piston runs from a lug near the middle of the
platform up into a slot in the pillar's inner face, its rod eye on a pin through the slot's cheeks.
Each claw is one shell too: two fingers either side of the head (the two claws interleaved), joined
under the nose by an arc yoke concentric with it.
The weapon stands upright, its bottom toward the platform; the claws clamp its sides and close to
whatever thickness it has (the grip table); the whole turret spins the weapon over the hatch. Opening folds the
fingers outward.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a joint axis
misses its rotor or bearing, a slide leaves its guide, a piston crosses its hinge or passes through
armour, or anything collides through any animation frame or across the joints' ranges.
Conventions: 1 unit = 1 m, Z up, front -Y, the floor surface is z = 0 with the origin at the centre of
the hatch; the pit hangs below it.
Rest pose = extended, doors open, claws closed on the nominal weapon.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
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

NAME = "weapon_holder"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # WeaponHolder

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# Everything is authored in hatch-local coordinates (a, b, n): a = across the hatch (the doors hinge
# on its long edges and the arms face each other across it), b = the hatch's long axis (the weapon
# lies along it), n = out of the surface. HATCH maps them to world space.
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
HATCH = Matrix.Identity(4)             # floor (user: ground up like the item table): a = +X, b = +Y, n = +Z
SIDES = ("Left", "Right")              # bone-name prefixes of the +a and -a side
CARRIAGE, SPIN = "Extend", "Spin"      # the sliding carriage and the spinning turret
SURFACE = "Floor"                      # the preview slab the frame sits flush in

BASE_TOP = 0.16                        # platform deck: its underside is 0.1 m off the floor
DRUM_TOP = BASE_TOP - 0.06             # the base block is 6 cm thick
ARM_R = 0.155                          # arm hinges at a = +-ARM_R (the turret fits between the hanging doors)
ARMS = (("Left", 0, "claw", 0), ("Right", 180, "claw", 180))  # (tag, azimuth, hand, hand azimuth)
RAMS = ()                              # no rams: the claws hold the weapon
RAM_R, RAM_BODY, RAM_RAISE, RAM_D = 0.12, 0.20, 0.10, 0.03  # (rams only)
TOP_PLATE_R = None                     # no platform
BASE_SHAPE = ("octagon",)              # base block: a chamfered octagon
ARM_LEN = 0.25                         # arm length, hinge to the end of the arm: the ends 0.3 m out from the deck
GUN_UP = (0, 0, 1)                     # the held weapon's up (local): upright, its bottom toward the floor
WEAPON = (0.05, 0.12)                  # nominal receiver thickness (across the claws: the rest grip) and height
MOUNT_CLEARANCE = 0.0                 # the holder's WeaponMount stays between the claws
MOUNT_NAME = "WeaponMount"
CLAW_CLOSE = -40                       # claws' closing limit past rest: the short claws turn further for thin guns
SPACE_NOTE = ("Blender coords: +Z up, front -Y, origin at the floor surface in the hatch centre. Authored on "
              "the floor (user); to mount it on a wall, turn it so +Z points out of the wall.")
CUTOUT_NOTE = "the patch's top is flush with the floor at z = 0; the pit hangs below it, inside its footprint"
CLAW_VIEW = "front"                    # extra view for the claw_open preview (along the hatch's long axis)
PREVIEW_FRAME = {"lo": [-0.5, -0.5, -0.1], "hi": [0.5, 0.5, BASE_TOP + ARM_LEN + 0.28]}
TARGET_OUTER_HEIGHT = 2.0
JACK_STAGE_COUNT = 8
REST_MESH_TOP = 0.62
# === END SPEC ===

# Derived geometry: from here on the code is identical for the item table and the weapon holder.
# The patch: a 1 x 1 m square frame, flush with the surface, around a centred 0.5 x 0.9 m hole. The
# pit or recess behind it stays inside the patch's footprint, so the frame covers the level's cut.
FRAME_A = FRAME_B = 0.5                     # patch half-sizes
OPEN_A, OPEN_B = 0.25, 0.45                 # hole half-sizes: 0.5 across, 0.9 along the weapon
FRAME_DEPTH = 0.10
STRIP_W = 0.03                              # light strip width, centred in each thick side ...
STRIP_GAP = (FRAME_A - OPEN_A - STRIP_W) / 2  # ... with the same gap to every edge of that side
STRIP_A, STRIP_B = (OPEN_A + FRAME_A) / 2, FRAME_B - STRIP_GAP
# Doors: two leaves hinged on the hole's long edges. Closed they sit flush in the frame; open they
# hang down against the pit's sides, so they never leave the patch's footprint.
DOOR_T = 0.02                               # leaf thickness
HINGE_A = OPEN_A - 0.004                    # hinge axis, just inside the hole's long edge
HINGE_N = -DOOR_T                           # at the leaf's underside
DOOR_W = HINGE_A - 0.002                    # leaf width, hinge to free edge
DOOR_CLOSED = 90                            # door value when closed (rest = open, hanging)
PASS_A = HINGE_A - DOOR_T - 0.011           # the turret's half-width across the hole: clear of the hanging doors
# Pit or recess: an open grey box (five faces, seen from inside) with a telescopic jack on
# its floor. The jack's top stage is the carriage: the turret spins on it in a slew bearing.
LIFT_Z = -0.31                              # carriage top (n): the slew collar runs below the hanging doors
DRUM_R = 0.15                               # the drum: the rotating shaft the turret stands on
JACK_STAGES = JACK_STAGE_COUNT              # shorter nested stages fit the exact overall height
JACK_R = 0.11                               # the jack's fixed barrel; each stage nests in the one below
JACK_WALL = 0.008                           # stage tube wall
JACK_GAP = 0.0008                           # radial running clearance between stages
# JACK_OVERLAP is solved below from the complete resting envelope.

CLAMP_W, CLAMP_D = (WEAPON if GUN_UP[2] else WEAPON[::-1])  # weapon extent across the claws (a), along n
PILLAR_Z = BASE_TOP + 0.05                  # arm hinges, on the deck
AXLE_Z = PILLAR_Z + ARM_LEN - 0.035         # hand axles, in the arms' top members
HAND_R = CLAMP_W / 2 + 0.065                # claw axle distance from the weapon axis
WB = 0.065                                  # the weapon's base side above the hand axles
DECK_Z = BASE_TOP + 0.008                   # top of the deck plate
PLATE_Z0 = DECK_Z + RAM_BODY                # underside of the top platform (if any), rams retracted
PLATE_TOP = PLATE_Z0 + 0.04                 # its top: the weapon lies on it
if TOP_PLATE_R:
    SOCKET = (0.0, 0.0, PLATE_TOP + CLAMP_D / 2)   # weapon centre, lying on the platform along b
    TOP = PLATE_TOP + CLAMP_D                      # the weapon's top (rams retracted): it may ride down
else:
    SOCKET = (0.0, 0.0, AXLE_Z + WB + CLAMP_D / 2)  # weapon grip centre, in the claws; along b
    TOP = AXLE_Z + WB + CLAMP_D + 0.01             # finger tips: the turret's top
# Where the game puts the weapon (the mount): by its bottom, centred across the holder (the claws
# close on it symmetrically whatever its size). A platform: above its top surface by the specified
# clearance; claws: the weapon's underside, between them.
MOUNT = tuple(SOCKET[i] - GUN_UP[i] * WEAPON[1] / 2 + (MOUNT_CLEARANCE if i == 2 else 0)
              for i in range(3))
STROKE = TOP + 0.29                         # travel: the turret's top clears the doors' swing when in
JACK_STEP = STROKE / JACK_STAGES            # each stage's travel in the one below it
JACK_OVERLAP = TARGET_OUTER_HEIGHT - REST_MESH_TOP + LIFT_Z - STROKE - JACK_STEP - .02
assert JACK_OVERLAP > .02, "Insufficient jack overlap for the target height"
JACK_LEN = JACK_STEP + JACK_OVERLAP         # stage length
PIT_DEPTH = -(LIFT_Z - STROKE) + JACK_LEN + 0.02  # the pit's floor: the jack collapsed, 1 cm clear of it
LUG_R = 0.07                                # piston lugs, near the middle of the deck
BRIDGE_Z = PILLAR_Z + 0.45 * ARM_LEN        # the pins across the arms' piston slots (a cradle arm's bridge)
ARM_HY = 0.04                               # arm half-thickness (tangential)
ARM_CHANNEL = 0.028                         # half-width of the channel between the arm's side plates
BASE_HALF = (PASS_A - 0.004, PASS_A - 0.004)  # octagonal base block half-sizes (a, b)
BASE_CHAMFER = 0.01                         # base block top-edge chamfer
FINGER_T = ((-0.058, 0.058), (-0.10, 0.10))  # first and second claw's fingers, interleaved so their tips pass
FINGER_HT = 0.014                           # a finger's half-thickness (tangential)
ARM_W = ARM_HY - 0.001                      # a claw arm shell's half-width: clear of the clevis and the fingers
ARM_RK = 0.032                              # its knuckle's round end about the hinge
HEAD_R = 0.035                              # its head's half-height: the nose is round about the hand axle
YOKE = (190, 235, HEAD_R + 0.005, 0.054)    # a claw's yoke: an arc bar about the axle (deg from +x, radii)
SHELL_BEVEL = 0.004                         # the shells' chamfer round their flanks
FLARE_H = 0.05                              # the base shell's flare down into the drum
POD_R = 0.028                               # (rams) the pods round the rams' feet, fused into the base's top ...
POD_TOP = BASE_TOP + 0.029                  # ... standing this high; the ram bodies rise out of them
DECK_POCKET_R = 0.08                        # (rams) the deck pocket between the pods, holding the ready light
CLAW_TAGS = [tag for tag, _, kind, _ in ARMS if kind == "claw"]
ARM_NAMES = [f"Arm{tag}" for tag, *_ in ARMS]
CLAW_NAMES = [f"Claw{tag}" for tag in CLAW_TAGS]
RAM_TAGS = "ABC"[:len(RAMS)]
PLATFORM = "Platform"
JACK_NAMES = [f"Jack{i}" for i in range(1, JACK_STAGES)]  # the jack's lower moving stages, from the barrel up


def hatch(a, b, n):
    return HATCH @ Vector((a, b, n))


def hatch_dir(a, b, n):
    return HATCH.to_3x3() @ Vector((a, b, n))


def turned(deg):
    """Hatch frame turned about n by `deg`: an arm's frame (x radial, y tangential) or a hand's."""
    return HATCH @ Matrix.Rotation(math.radians(deg), 4, "Z")


def polar(r, az, n):
    """Hatch-local point at radius r, azimuth az (deg from +a), height n."""
    return (r * math.cos(math.radians(az)), r * math.sin(math.radians(az)), n)


def jack_stage(i):
    """(bottom, top, outer radius) of the jack's stage i at rest (extended), hatch-local n: 0 is the
    fixed barrel, JACK_STAGES the carriage. Collapsed, every moving stage stands 1 cm off the floor."""
    r = JACK_R - i * (JACK_WALL + JACK_GAP)
    if i == 0:
        return -PIT_DEPTH, -PIT_DEPTH + JACK_LEN, r
    lo = -PIT_DEPTH + 0.01 + i * JACK_STEP
    return lo, lo + JACK_LEN + (0.01 if i == JACK_STAGES else 0.0), r


def arm_geometry(tag):
    """(azimuth, hand kind, hand azimuth, pillar radius along the hand's x, hand-frame y of the
    pillar) for an arm. A claw hand closes along its own x toward the weapon axis; it sits at the
    pillar's y in its own frame, so the arm's top member runs straight in from the pillar."""
    az, kind, psi = next((a, k, p) for t, a, k, p in ARMS if t == tag)
    d = math.radians(az - psi)
    return az, kind, psi, ARM_R * math.cos(d), ARM_R * math.sin(d)


def hand_axle(tag):
    """A claw hand's axle, hatch-local."""
    az, kind, psi, px, t_off = arm_geometry(tag)
    c, s = math.cos(math.radians(psi)), math.sin(math.radians(psi))
    return (HAND_R * c - t_off * s, HAND_R * s + t_off * c, AXLE_Z)


def side_name(s, part):
    return f"{SIDES[0 if s > 0 else 1]}{part}"


def door_open(side):
    """Hatch-local transform from a door's closed pose to its rest pose (open, hanging down)."""
    h = Vector((side * HINGE_A, 0, HINGE_N))
    return Matrix.Translation(h) @ Matrix.Rotation(math.radians(-DOOR_CLOSED), 4, Vector((0, side, 0))) \
        @ Matrix.Translation(-h)


DOOR_NAMES = (side_name(1, "Door"), side_name(-1, "Door"))
GROUPS = (DOOR_NAMES, ARM_NAMES, CLAW_NAMES, (CARRIAGE, *JACK_NAMES))  # joints that move together: the first drives the rest

# Joints: (name, parent, kind, pivot, axis, bone direction, limits), in world space.
#   kind:  "hinge" turns about `axis` through `pivot` (bone local X = axis, pose rotation X, deg);
#          "slide" moves along `axis` (bone local Y = axis, pose location Y, m); "fixed".
#   limits: (lo, hi) of the joint value, None = free (the turret spins without end).
# Rest = deployed with the doors open (hanging) and the rams retracted / the hands closed on the
# nominal weapon, so the door value is how far a door has closed (90 = shut), and the carriage value
# (each jack stage's travel in the one below) is negative going in. Rams: the platform rises RAM_RAISE on their rods. Arms: + tilts the pillar
# outward. Claws: + folds the fingers open, - closes them further onto a thinner weapon (GRIP).
JOINT_SPECS = [("Root", None, "fixed", (0, 0, 0), UP, UP, None)]
for _s, _name in zip((1, -1), DOOR_NAMES):
    JOINT_SPECS.append((_name, "Root", "hinge", hatch(_s * HINGE_A, OPEN_B, HINGE_N), hatch_dir(0, _s, 0),
                        hatch_dir(0, 0, -1), (0, DOOR_CLOSED)))
for _i, _name in enumerate(JACK_NAMES, 1):
    JOINT_SPECS.append((_name, JACK_NAMES[_i - 2] if _i > 1 else "Root", "slide", hatch(0, 0, jack_stage(_i)[1]),
                        hatch_dir(0, 0, 1), None, (-JACK_STEP, 0)))
JOINT_SPECS += [
    (CARRIAGE, JACK_NAMES[-1] if JACK_NAMES else "Root", "slide", hatch(0, 0, LIFT_Z), hatch_dir(0, 0, 1), None,
     (-JACK_STEP, 0)),
    (SPIN, CARRIAGE, "hinge", hatch(0, 0, LIFT_Z + 0.03), hatch_dir(0, 0, 1), hatch_dir(0, -1, 0), None),
]
if RAMS:  # the rams' rods and the platform on them slide as one body in the rams' bodies
    JOINT_SPECS.append((PLATFORM, SPIN, "slide", hatch(0, 0, PLATE_Z0), hatch_dir(0, 0, 1), None, (0, RAM_RAISE)))
for _tag, _az, _kind, _psi in ARMS:
    _c, _s = math.cos(math.radians(_az)), math.sin(math.radians(_az))
    JOINT_SPECS.append((f"Arm{_tag}", SPIN, "hinge", hatch(ARM_R * _c, ARM_R * _s, PILLAR_Z), hatch_dir(-_s, _c, 0),
                        hatch_dir(0, 0, 1), (0, 10)))
    if _kind == "claw":
        _pc, _ps = math.cos(math.radians(_psi)), math.sin(math.radians(_psi))
        JOINT_SPECS.append((f"Claw{_tag}", f"Arm{_tag}", "hinge", hatch(*hand_axle(_tag)), hatch_dir(-_ps, _pc, 0),
                            hatch_dir(0, 0, 1), (CLAW_CLOSE, 105)))
JOINT_SPECS.append(("WeaponSocket", PLATFORM if RAMS else SPIN, "fixed", hatch(*MOUNT), hatch_dir(0, 0, 1),
                    hatch_dir(0, -1, 0), None))

# Pistons, hatch-local: barrel on the turret (end A, in a slotted lug near the middle of the deck),
# rod on the arm (end B, pinned across the slot in its pillar); each runs up and out into the
# slot, with a long lever about the arm's hinge.
# (name, cylinder parent, A, rod parent, B, barrel radius)
PISTON_SPECS = [(f"Arm{_t}Piston", SPIN, polar(LUG_R, _a, PILLAR_Z - 0.015), f"Arm{_t}", polar(ARM_R, _a, BRIDGE_Z),
                 0.011) for _t, _a, _k, _p in ARMS]
PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015
SLOT_GAP = 0.00125  # clearance each side of a piston eye in its slot

# Adaptive grip: for each weapon width (its extent across the claws), the claw angle at which the
# fingers meet it when closing from open, measured on the real finger geometry and exported to
# _rig.json, so the engine closes the claws exactly onto whatever weapon is held.
GRIP_CLAWS = tuple(CLAW_NAMES)
GRIP_WIDTHS = [round(0.03 + 0.01 * i, 3) for i in range(14)]


def grip_box(width):
    """The held weapon's receiver as a box, hatch-local: centred on the socket, CLAMP_D deep."""
    return (-width / 2, -0.24, SOCKET[2] - CLAMP_D / 2), (width / 2, 0.24, SOCKET[2] + CLAMP_D / 2)


# Animations at FPS: {name: (loop, interpolation, {joint: [(frame, value), ...]})}. The first joint of
# each group drives the others with the same value. Joints an action doesn't key keep their pose.
S, T, D0 = JACK_STEP, DOOR_CLOSED, DOOR_NAMES[0]
MOVE = round(24 + 18 * STROKE)  # frames for the carriage's travel
UPD = 18                        # frames for the rams' travel
ANIMATIONS = {
    "deploy": (False, "BEZIER", {D0: [(0, T), (16, 0)], CARRIAGE: [(0, -S), (16, -S), (16 + MOVE, 0)]}),
    "retract": (False, "BEZIER", {CARRIAGE: [(0, 0), (MOVE, -S)], D0: [(0, 0), (MOVE, 0), (MOVE + 16, T)]}),
    "spin": (True, "LINEAR", {SPIN: [(0, 0), (120, 360)]}),
}
# States rendered by preview.py (from the front_left camera) as <name>_pose_<state>.png.
PREVIEW_STATES = {"retracted": {D0: T, CARRIAGE: -S}, "rising": {CARRIAGE: -S * 0.55}, "spinning": {SPIN: 55}}
PREVIEW_VIEWS = {}  # states also rendered from other views
FK_TEST_STATE = {D0: T * 0.7, CARRIAGE: -S * 0.6, SPIN: 37}
SHOWCASE = ["deploy", "spin", "retract"]  # animate.py plays these in order
if RAMS:  # the rams raise the platform once the turret is up, and lower it before it goes in
    U = RAM_RAISE
    up, down = [(0, 0), (UPD, U)], [(0, U), (UPD, 0)]
    dep = ANIMATIONS["deploy"][2]
    dep[PLATFORM] = [(0, 0), (20 + MOVE, 0), (20 + MOVE + UPD, U)]
    ret = ANIMATIONS["retract"][2]
    for j in (CARRIAGE, D0):
        ret[j] = [(f + UPD + 4, v) for f, v in ret[j]]
    ret[CARRIAGE].insert(0, (0, 0))
    ret[PLATFORM] = [(0, U), (UPD, 0)]
    ANIMATIONS["raise"] = (False, "BEZIER", {PLATFORM: up})
    ANIMATIONS["lower"] = (False, "BEZIER", {PLATFORM: down})
    PREVIEW_STATES["raised"] = {PLATFORM: U, SPIN: 30}
    FK_TEST_STATE.update({PLATFORM: U * 0.6})
if ARM_NAMES:  # arms and claws: opening and closing on the weapon
    A0, C0 = ARM_NAMES[0], CLAW_NAMES[0]
    ANIMATIONS["claw_open"] = (False, "BEZIER", {A0: [(0, 0), (12, 10)], C0: [(0, 0), (3, 0), (18, 105)]})
    ANIMATIONS["claw_close"] = (False, "BEZIER", {C0: [(0, 105), (15, 0)], A0: [(0, 10), (6, 10), (18, 0)]})
    PREVIEW_STATES["claw_open"] = {A0: 10, C0: 105, SPIN: 30}
    PREVIEW_VIEWS["claw_open"] = ["front_left", CLAW_VIEW]
    FK_TEST_STATE.update({A0: 9, ARM_NAMES[-1]: 4, C0: 30, CLAW_NAMES[-1]: -12})
    SHOWCASE[2:2] = ["claw_open", "claw_close"]

# slot: (base colour, metallic, roughness, emission strength). Map-generic pickups: an industrial
# finish in Tensor's materials (off-white and grey paint, matte black, stainless steel), no team colours.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # off-white paint (Tensor's): armour (arms, base, doors)
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # grey paint (Tensor's accent): pit liner, piston barrels
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black (Tensor's frames): chassis, frame, fingers
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: axles, rods, pads, jack stages
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # status lights (weapon ready)
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI = SLOTS  # no looms or hoses: the pit holds only the centre jack


def mirror_name(name):
    """The other side's bone name."""
    for mine, other in (SIDES, SIDES[::-1]):
        if name.startswith(mine):
            return other + name[len(mine):]
    return name


def mirror_vec(v):
    return Vector((-v[0], v[1], v[2]))


# --------------------------------------------------------------------------------------------
# Resolved joints and forward kinematics
# --------------------------------------------------------------------------------------------

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


def machine(bm, cuts=(), boxes=(), intersect=(), subtract=(), union=()):
    """The closed bmesh `bm` machined with exact booleans, returned as a new bmesh (bm and `union` are
    freed): the closed bmeshes in `union` are fused into it first (fairings: one unibody), then it is
    intersected with each `intersect` (points, normal, thickness) prism, then `cuts` (p0, p1, r[, sides])
    cylinders, `boxes` (center, size) blocks and `subtract` (points, normal, thickness) prisms are cut away."""
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
               + [temp(prism_bm(pts, th, nrm), "_slab") for pts, nrm, th in subtract])
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


# --------------------------------------------------------------------------------------------
# Parts: hatch and pit (hatch-local), then the turret (world)
# --------------------------------------------------------------------------------------------

def build_hatch(k):
    """The 1 x 1 m frame round the 0.5 x 0.9 m hole, a light strip centred in each thick side, the
    hinge grooves and bearings, and the two door leaves (authored closed, placed open for rest)."""
    with k.frame(HATCH):
        grooves = [((s * STRIP_A, 0, -0.003), (STRIP_W + 0.001, 2 * STRIP_B + 0.001, 0.0061)) for s in (1, -1)]
        hinges = [((s * HINGE_A, -OPEN_B - 0.012, HINGE_N), (s * HINGE_A, OPEN_B + 0.012, HINGE_N), 0.014, 12)
                  for s in (1, -1)]
        k.plate(rect(FRAME_A, FRAME_B, -FRAME_DEPTH / 2), FRAME_DEPTH, UP, "Root", FRM,
                holes=[rect(OPEN_A, OPEN_B, -FRAME_DEPTH / 2)], cuts=hinges, boxes=grooves)
        for s in (1, -1):  # light strips, flush, the same gap to every edge of the thick side
            k.box((s * STRIP_A, 0, -0.003), (STRIP_W, 2 * STRIP_B, 0.006), "Root", EMI)
            for e in (1, -1):  # hinge bearings, in the frame's ends
                k.cyl((s * HINGE_A, e * (OPEN_B - 0.0035), HINGE_N), (s * HINGE_A, e * (OPEN_B + 0.02), HINGE_N), 0.012,
                      "Root", JNT, segs=8)
        for s, name in zip((1, -1), DOOR_NAMES):
            with k.frame(door_open(s)):
                a0, a1 = sorted((s * (HINGE_A - DOOR_W), s * (HINGE_A - 0.004)))
                ribs = [((s * a, 0, 0), (0.008, 2 * OPEN_B - 0.08, 0.006)) for a in (0.06, 0.12, 0.18)]
                k.plate([(a1, OPEN_B - 0.003, -DOOR_T / 2), (a0, OPEN_B - 0.003, -DOOR_T / 2),
                         (a0, -OPEN_B + 0.003, -DOOR_T / 2), (a1, -OPEN_B + 0.003, -DOOR_T / 2)],
                        DOOR_T, UP, name, PRI, boxes=ribs)                           # door leaf, grooved top
                k.cyl((s * HINGE_A, -OPEN_B + 0.004, HINGE_N), (s * HINGE_A, OPEN_B - 0.004, HINGE_N), 0.011, name, JNT,
                      segs=8)                                                     # hinge barrel


def build_pit(k):
    """The pit (or recess): an open grey box inside the patch's footprint, and the telescopic
    jack on its floor: a fixed barrel and nested stages sliding in it, the top one the carriage."""
    with k.frame(HATCH):
        k.shell((-FRAME_A, -FRAME_B, -PIT_DEPTH), (FRAME_A, FRAME_B, -FRAME_DEPTH), "Root", SEC)
        for i in range(JACK_STAGES + 1):
            lo, hi, r = jack_stage(i)
            bone = "Root" if i == 0 else CARRIAGE if i == JACK_STAGES else JACK_NAMES[i - 1]
            zc = (lo + hi) / 2
            bore = [ring_xy(0, 0, r - JACK_WALL, zc, 8)] if i < JACK_STAGES else []  # the top stage is a solid plunger
            k.plate(ring_xy(0, 0, r, zc, 8), hi - lo, UP, bone, FRM if i == 0 else JNT, holes=bore)


def build_turret(k):
    """Slew collar and drive on the carriage (the jack's top stage); the drum, base block, deck, arm clevises and piston
    lugs of the spinning turret. Hatch-local (n = out of the surface)."""
    with k.frame(HATCH):
        k.cyl((0, 0, LIFT_Z), (0, 0, LIFT_Z + 0.03), DRUM_R + 0.02, CARRIAGE, FRM, segs=16)  # slew collar
        k.span((DRUM_R + 0.01, -0.03, LIFT_Z + 0.002), (DRUM_R + 0.06, 0.03, LIFT_Z + 0.025), CARRIAGE, FRM)  # drive housing
        k.cyl((DRUM_R + 0.035, 0, LIFT_Z + 0.025), (DRUM_R + 0.035, 0, LIFT_Z + 0.07), 0.018, CARRIAGE, FRM, segs=8)
        # Drum: the rotating shaft the turret stands on, grooved so the spin reads, with a stainless steel band
        # where it meets the base block.
        k.cyl((0, 0, LIFT_Z + 0.03), (0, 0, LIFT_Z + 0.04), DRUM_R + 0.01, SPIN, JNT, segs=16)   # slew ring
        zc, h = (LIFT_Z + 0.03 + DRUM_TOP) / 2, DRUM_TOP - LIFT_Z - 0.03
        grooves = [((DRUM_R * c, DRUM_R * s, zc - 0.01), (0.012 if c else 0.024, 0.012 if s else 0.024, h - 0.12))
                   for c, s in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        k.plate(ring_xy(0, 0, DRUM_R, zc, 16), h, UP, SPIN, FRM, boxes=grooves)
        # Base block: one lofted shell (the weapons' language) flaring from the drum's round section up
        # into a machined octagon or chamfered triangle, its top edges chamfered (a side profile per
        # face), a recessed status light in its long faces, slanted vents centred on its plain faces.
        # Arms stand on a deck plate on top with a flush "ready" light at its centre; rams rise out of
        # pods fused into the shell's top, round a deck pocket holding the ready light.
        outline, faces, lit, vented = base_outline()
        zb, c = (DRUM_TOP + BASE_TOP) / 2, BASE_CHAMFER

        def radial(az, x, y, z):  # a point given in a frame turned by az about n
            ca, sa = math.cos(math.radians(az)), math.sin(math.radians(az))
            return (x * ca - y * sa, x * sa + y * ca, z)
        shapers = [([radial(az, x, 0, z) for x, z in ((-1.0, DRUM_TOP - 1.0), (d + 0.01, DRUM_TOP - 1.0),
                                                        (d + 0.01, BASE_TOP - c - 0.01), (d - c, BASE_TOP),
                                                        (d - c, BASE_TOP + 1.0), (-1.0, BASE_TOP + 1.0))],  # pods rise inside
                    radial(az, 0, 1, 0), 2.0) for az, d in faces]
        slots = [([radial(az, d, y, z) for y, z in ((-0.06, zb - 0.021), (0.06, zb - 0.021), (0.06, zb + 0.001),
                                                     (-0.06, zb + 0.001))], radial(az, 1, 0, 0), 0.013) for az, d in lit]
        u, v = math.cos(math.radians(60)), math.sin(math.radians(60))
        zv = (DRUM_TOP + BASE_TOP - c) / 2
        vents = [([radial(az, d, y + sy * 0.015 * u + sw * 0.0025 * v, zv + sy * 0.015 * v - sw * 0.0025 * u)
                   for sy, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1))], radial(az, 1, 0, 0), 0.008)
                 for az, d in vented for y in (-0.03, -0.01, 0.01, 0.03)]
        # The flare's rings: the outline resampled (every ~6 cm), and the same azimuths on a circle
        # just outside the drum and inside every face, so the corners sweep down into the drum.
        ring = []
        for p, q in zip(outline, outline[1:] + outline[:1]):
            n = max(1, round(math.dist(p, q) / 0.06))
            ring += [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(n)]
        r0 = min(DRUM_R + 0.012, min(d for _, d in faces) - 0.005)
        flare = [(r0 * math.cos(math.atan2(y, x)), r0 * math.sin(math.atan2(y, x)), DRUM_TOP - FLARE_H) for x, y in ring]
        shell = loft_rings([flare, [(x, y, DRUM_TOP) for x, y in ring], [(x, y, BASE_TOP) for x, y in ring]])
        # The flare's quads (the drum's circle up to the outline) aren't flat: triangulated first, so carve() finds
        # each face in its own plane and paints it the shell's colour (user: it came out black, as if a cut's face).
        bmesh.ops.triangulate(shell, faces=shell.faces[:])
        pods, cuts, boxes = [], [], []
        for az in RAMS:  # a pod round each ram's foot, its bore carrying on the ram body's
            cx, cy, _ = polar(RAM_R, az, 0)
            pods.append(loft_rings([ring_xy(cx, cy, r, z, 12) for r, z in ((POD_R, BASE_TOP - 0.01), (POD_R, POD_TOP - 0.007),
                                                                            (POD_R - 0.007, POD_TOP))]))
            cuts.append(((cx, cy, BASE_TOP - 0.005), (cx, cy, POD_TOP + 0.01), RAM_D / 2 - 0.0035, 12))  # 1 mm over the body's
        if RAMS:
            cuts.append(((0, 0, BASE_TOP - 0.004), (0, 0, BASE_TOP + 0.01), DECK_POCKET_R, 24))  # deck pocket
            boxes.append(((0, 0, BASE_TOP - 0.006), (0.05, 0.05, 0.004)))                   # ready light's seat
        carve(k, shell, SPIN, PRI, cuts=cuts, boxes=boxes, subtract=slots + vents, intersect=shapers, union=pods)
        if RAMS:
            k.span((-0.024, -0.024, BASE_TOP - 0.0085), (0.024, 0.024, BASE_TOP - 0.0045), SPIN, EMI)  # ready light
        else:
            k.plate([(x * 0.9, y * 0.9, BASE_TOP + 0.004) for x, y in outline], 0.008, UP, SPIN, FRM,
                    boxes=[((0, 0, DECK_Z), (0.05, 0.05, 0.008))])               # deck plate
            k.span((-0.024, -0.024, DECK_Z - 0.0035), (0.024, 0.024, DECK_Z), SPIN, EMI)  # ready light
    for az, d in lit:  # status lights, flush in their slots
        with k.frame(turned(az)):
            k.span((d - 0.006, -0.059, zb - 0.02), (d, 0.059, zb), SPIN, EMI)
    for tag, az, kind, psi in ARMS:
        with k.frame(turned(az)):  # x radial, y tangential
            # Arm hinge: a clevis of two cheeks with bearing bosses on the deck, outside the arm's plates.
            for sy in (1, -1):
                y0, y1 = sorted((sy * (ARM_HY + 0.003), sy * (ARM_HY + 0.019)))
                k.span((ARM_R - 0.032, y0, DECK_Z), (ARM_R + 0.032, y1, PILLAR_Z), SPIN, FRM)
                k.cyl((ARM_R, sy * (ARM_HY + 0.002), PILLAR_Z), (ARM_R, sy * (ARM_HY + 0.020), PILLAR_Z), 0.036, SPIN,
                      FRM, segs=12)                                                # boss, proud of the cheek
                k.cyl((ARM_R, sy * (ARM_HY + 0.020), PILLAR_Z), (ARM_R, sy * (ARM_HY + 0.024), PILLAR_Z), 0.02, SPIN,
                      JNT, segs=8)                                                 # bearing cap
            # Piston lug: a slotted block near the middle of the deck; the barrel's eye turns on a
            # cross pin in the slot (see build_pistons).
            a = Vector((LUG_R, 0, PILLAR_Z - 0.015))
            slot = 0.011 * 1.15 + SLOT_GAP
            k.plate([(a.x - 0.015, 0, DECK_Z), (a.x + 0.015, 0, DECK_Z), (a.x + 0.015, 0, a.z + 0.015),
                     (a.x - 0.015, 0, a.z + 0.015)], 0.045, BACK, SPIN, FRM,
                    boxes=[((a.x, 0, a.z + 0.005), (0.04, 2 * slot, 0.04))])


def base_outline():
    """(outline points (a, b), faces [(normal azimuth deg, distance)] for the top-edge chamfer,
    lit faces carrying a status light, plain faces carrying vents) of the base block."""
    if BASE_SHAPE[0] == "triangle":
        _, rc, half = BASE_SHAPE
        corners = sorted(RAMS or (90, 210, 330))
        pts = []
        for c in corners:
            for a in (c - half, c + half):
                pts.append((rc * math.cos(math.radians(a)), rc * math.sin(math.radians(a))))
        edges = [(c + 60, rc * math.cos(math.radians(60 - half))) for c in corners]
        tips = [(c, rc * math.cos(math.radians(half))) for c in corners]
        return pts, edges + tips, edges, tips
    ba, bb = BASE_HALF
    ch = 0.06
    pts = [(ba, -bb + ch), (ba, bb - ch), (ba - ch, bb), (-ba + ch, bb), (-ba, bb - ch),
           (-ba, -bb + ch), (-ba + ch, -bb), (ba - ch, -bb)]
    diag = (ba + bb - ch) / math.sqrt(2)
    faces = [(0, ba), (90, bb), (180, ba), (270, bb), (45, diag), (135, diag), (225, diag), (315, diag)]
    return pts, faces, [(0, ba), (180, ba)], [(90, bb), (270, bb)]


def build_rams(k):
    """Three slim single-stage hydraulic rams on the deck, carrying the round top platform. The body
    (on the turret) is RAM_BODY long and RAM_D across; the rod (on the platform) slides in it by
    RAM_RAISE, so retracted only the body shows and extended the platform is RAM_BODY + RAM_RAISE
    above the deck. The bodies rise out of pods in the base shell's top (build_turret). The platform
    is one lofted shell: a faceted disc with a chamfered lip, its underside stepping in to a flat
    where the rods meet it, a black field set flush into its top and a lit disc under its centre."""
    top, rb = PLATE_Z0, RAM_D / 2                                                  # bodies' tops, rams retracted
    for az in RAMS:
        cx, cy, _ = polar(RAM_R, az, 0)
        with k.frame(HATCH):
            zc = (DECK_Z + 0.01 + top - 0.01) / 2
            k.plate(ring_xy(cx, cy, rb, zc, 12), top - 0.01 - DECK_Z - 0.01, UP, SPIN, SEC,
                    holes=[ring_xy(cx, cy, rb - 0.0045, zc, 12)])                   # body
            k.plate(ring_xy(cx, cy, rb + 0.003, top - 0.005, 12), 0.01, UP, SPIN, JNT,
                    holes=[ring_xy(cx, cy, rb - 0.0045, top - 0.005, 12)])          # gland collar
            k.cyl((cx, cy, DECK_Z + 0.02), (cx, cy, top), rb - 0.0053, PLATFORM, JNT, segs=12)  # rod
    if TOP_PLATE_R:
        with k.frame(HATCH):
            r = TOP_PLATE_R
            under = RAM_R + RAM_D / 2 + 0.012                                      # the underside's flat, over the rams
            k_rings = [ring_xy(0, 0, rr, z, 24) for rr, z in ((under, PLATE_Z0), (r, PLATE_Z0 + 0.014),
                                                              (r, PLATE_TOP - 0.012), (r - 0.012, PLATE_TOP))]
            carve(k, loft_rings(k_rings), PLATFORM, PRI,
                  cuts=[((0, 0, PLATE_TOP - 0.006), (0, 0, PLATE_TOP + 0.01), r - 0.03, 24),
                        ((0, 0, PLATE_Z0 - 0.01), (0, 0, PLATE_Z0 + 0.006), RAM_R - 0.06, 16)])
            k.cyl((0, 0, PLATE_TOP - 0.0055), (0, 0, PLATE_TOP), r - 0.031, PLATFORM, FRM, segs=24)  # field, flush
            k.cyl((0, 0, PLATE_Z0 - 0.002), (0, 0, PLATE_Z0 + 0.0055), RAM_R - 0.061, PLATFORM, EMI, segs=16)  # underglow


def build_arm(k, tag):
    """An H-pillar arm: two side plates on their own knuckles and stub axles (so the channel between
    them stays open for the piston past the hinge), a bridge across the channel where the piston's
    rod end is pinned, and a top member carrying the hand on top of the pillar: a claw's servo, or
    a cradle the weapon rests in. A claw's arm is one shell instead (build_claw_arm)."""
    az, kind, psi, px, t_off = arm_geometry(tag)
    if kind == "claw":
        build_claw_arm(k, tag)
        return
    bone = f"Arm{tag}"
    top0 = AXLE_Z - 0.035
    with k.frame(turned(az)):  # x radial, y tangential
        for sy in (1, -1):
            yc = sy * (ARM_CHANNEL + ARM_HY) / 2
            k.cyl((ARM_R, sy * (ARM_CHANNEL + 0.003), PILLAR_Z), (ARM_R, sy * (ARM_HY + 0.022), PILLAR_Z), 0.013, bone,
                  JNT, segs=8)                                                     # stub axle, ends inside the cap
            k.cyl((ARM_R, sy * (ARM_CHANNEL + 0.002), PILLAR_Z), (ARM_R, sy * (ARM_HY + 0.001), PILLAR_Z), 0.032, bone,
                  JNT, segs=12)                                                    # knuckle, stepped off the plate
            k.plate([(ARM_R - 0.03, yc, PILLAR_Z), (ARM_R + 0.03, yc, PILLAR_Z), (ARM_R + 0.03, yc, top0 + 0.005),
                     (ARM_R - 0.03, yc, top0 + 0.005)], ARM_HY - ARM_CHANNEL, BACK, bone, PRI,
                    boxes=[((ARM_R, sy * ARM_HY, (PILLAR_Z + top0) / 2 + 0.02), (0.034, 0.008, top0 - PILLAR_Z - 0.16))])
        slot = 0.011 * 1.15 + SLOT_GAP                                             # bridge, slotted from below
        k.plate([(ARM_R - 0.03, 0, BRIDGE_Z - 0.015), (ARM_R + 0.03, 0, BRIDGE_Z - 0.015),
                 (ARM_R + 0.03, 0, BRIDGE_Z + 0.03), (ARM_R - 0.03, 0, BRIDGE_Z + 0.03)],
                2 * ARM_CHANNEL + 0.001, BACK, bone, FRM, boxes=[((ARM_R, 0, BRIDGE_Z - 0.01), (0.03, 2 * slot, 0.05))])
    with k.frame(turned(psi)):  # the hand's frame: x toward the weapon axis is -x
        # cradle: a channelled block on the pillar's top, the weapon resting in the channel
        z0, z1 = top0, AXLE_Z + WB - 0.001
        x0, x1 = px - 0.07, px + 0.03
        k.plate(rect((x1 - x0) / 2, 0.05, (z0 + z1) / 2, ca=(x0 + x1) / 2, cb=t_off, chamfer=0.012), z1 - z0, UP,
                bone, PRI, boxes=[(((x0 + x1) / 2, t_off, z1), (0.2, CLAMP_W + 0.006, 0.024))])


def build_claw_arm(k, tag):
    """A claw's arm, one unibody shell (the weapons' language) carved from its side profile: a knuckle
    round about the hinge, a pillar tapering up from it, and a head turning in along the top to a
    nose round about the hand axle (the servo housing), the inside corner filleted and the outer one
    chamfered, every edge round its flanks chamfered. The piston runs up into a slot from the pillar's
    inner face and its rod eye turns on a pin through the slot's cheeks, the pin's ends showing on
    the flanks; slanted vents are cut into the middle of the pillar's plain outer face, a bearing
    ring on each side of the nose marks the claw's axle, and a through axle turns the knuckle in the
    deck's clevis."""
    az, kind, psi, px, t_off = arm_geometry(tag)
    if abs(az - psi) > 1e-6:
        raise ValueError(f"Arm{tag}: a claw arm's shell needs its hand facing along the arm")
    bone, t, w = f"Arm{tag}", t_off, ARM_W
    xo, xi0, xi1 = ARM_R + ARM_RK, ARM_R - ARM_RK, ARM_R - 0.026                    # outer face, inner face (foot, neck)
    zt, zb = AXLE_Z + HEAD_R, AXLE_Z - HEAD_R                                       # the head's top and underside
    corner = [(p.x, p.y) for p in fillet([(HAND_R, zb), (xi1, zb), (xi0, PILLAR_Z)], 0.016, 3)]
    side = (arc_xz(ARM_R, PILLAR_Z, ARM_RK, 180, 360, 8) + [(xo, zt - 0.022), (xo - 0.022, zt)]
            + arc_xz(HAND_R, AXLE_Z, HEAD_R, 90, 270, 8)[:-1] + corner[:-1])
    slot = 0.011 * 1.15 + SLOT_GAP                                                  # the piston's slot, as its lug's
    z0 = PILLAR_Z + 0.025
    vents = []                                                                      # slanted, centred on the outer face
    d = Vector((math.cos(math.radians(20)), math.sin(math.radians(20))))
    n = Vector((-d.y, d.x))
    zc = (PILLAR_Z + zt - 0.022) / 2
    for i in range(4):
        c = Vector((t, zc + 0.018 * (i - 1.5)))
        quad = [c - d * 0.017 - n * 0.003, c + d * 0.017 - n * 0.003, c + d * 0.017 + n * 0.003, c - d * 0.017 + n * 0.003]
        vents.append(([(xo, q.x, q.y) for q in quad], (1, 0, 0), 0.006))
    with k.frame(turned(psi)):  # x radial (the weapon axis is at -x), y tangential
        carve(k, prism_bm([(x, t, z) for x, z in side], 2 * w, (0, 1, 0)), bone, PRI,
              cuts=[((ARM_R, t - slot, BRIDGE_Z), (ARM_R, t + slot, BRIDGE_Z), 0.018, 16)],
              boxes=[((ARM_R - 0.016, t, (z0 + BRIDGE_Z) / 2), (0.068, 2 * slot, BRIDGE_Z - z0))],
              subtract=vents, bevel=SHELL_BEVEL, flanks=[((0, 1, 0), t + w), ((0, 1, 0), t - w)])
        k.cyl((ARM_R, t - ARM_HY - 0.022, PILLAR_Z), (ARM_R, t + ARM_HY + 0.022, PILLAR_Z), 0.013, bone, JNT,
              segs=8)                                                              # axle, its ends in the caps
        k.cyl((ARM_R, t - w - 0.0025, BRIDGE_Z), (ARM_R, t + w + 0.0025, BRIDGE_Z), 0.0055, bone, JNT, segs=8)  # pin
        for sy in (1, -1):
            k.cyl((ARM_R, t + sy * (w - 0.0005), BRIDGE_Z), (ARM_R, t + sy * (w + 0.0015), BRIDGE_Z), 0.009, bone, JNT,
                  segs=12)                                                         # the pin's washer
            k.cyl((HAND_R, t + sy * (w - 0.0005), AXLE_Z), (HAND_R, t + sy * (w + 0.0015), AXLE_Z), 0.022, bone, JNT,
                  segs=12)                                                         # bearing ring


def build_claw(k, tag):
    """A claw hand on the nose of its arm, one unibody shell: two fingers either side of the arm's
    head (and interleaved with the other claw's), each rising from a boss round the servo axle and
    tapering to a raked tip, joined under the nose by the yoke, an arc bar concentric with the nose
    that clears it at every angle. Every edge round the flanks is chamfered. Closed, the fingers'
    pads clamp the weapon; a thinner weapon is met further round (GRIP). No ledge under the weapon:
    rising fingers would lift it into the weapon as they open. Opening folds the fingers outward and
    down beside the head."""
    az, kind, psi, px, t_off = arm_geometry(tag)
    bone, t = f"Claw{tag}", t_off
    w = CLAMP_W
    pad_x = w / 2 + 0.0105
    top = WB + CLAMP_D + 0.01
    f = max(abs(y) for y in FINGER_T[CLAW_TAGS.index(tag) % 2])
    y_in, y_out = f - FINGER_HT, f + FINGER_HT
    a0, a1, r0, r1 = YOKE
    rb = 0.026                                                                      # the root boss round the axle
    tip = Vector((pad_x + 0.02, top - 0.01))
    rel = tip - Vector((HAND_R, 0))
    tangent = math.degrees(math.atan2(rel.y, rel.x) - math.acos(rb / rel.length))  # the outer edge meets the boss
    side = ([(pad_x, top), tuple(tip)] + arc_xz(HAND_R, 0, rb, tangent, -85, 6)
            + arc_xz(HAND_R, 0, r1, a1, a0, 3) + [(pad_x, 0.005)])                 # (x, n - axle)
    rc = r0 / math.cos(math.pi / 24)                                                # the 24-gon's flats at r0
    bore = [(HAND_R + rc * math.cos(2 * math.pi * i / 24), t, AXLE_Z + rc * math.sin(2 * math.pi * i / 24))
            for i in range(24)]
    sweep = [a1 + (a0 + 360 - a1) * i / 12 for i in range(13)]                   # round the rest, in two convex fans
    wedges = [[(HAND_R, t, AXLE_Z)] + [(HAND_R + 0.5 * math.cos(math.radians(a)), t, AXLE_Z + 0.5 * math.sin(math.radians(a)))
                                       for a in half] for half in (sweep[:7], sweep[6:])]
    with k.frame(turned(psi)):
        # Between the fingers everything is cut away but the yoke: the nose's clearance bore and the
        # wedge round the rest.
        carve(k, prism_bm([(x, t, AXLE_Z + z) for x, z in side], 2 * y_out, (0, 1, 0)), bone, FRM,
              subtract=[(p, (0, 1, 0), 2 * y_in) for p in (bore, *wedges)], bevel=SHELL_BEVEL,
              flanks=[((0, 1, 0), t + s * y) for s in (1, -1) for y in (y_in, y_out)])
        k.cyl((HAND_R, t - y_out - 0.006, AXLE_Z), (HAND_R, t + y_out + 0.006, AXLE_Z), 0.013, bone, JNT,
              segs=8)                                                              # servo axle
        for y in (f, -f):
            k.span((w / 2 + 0.003, t + y - 0.008, AXLE_Z + WB + 0.005),
                   (pad_x + 0.001, t + y + 0.008, AXLE_Z + WB + CLAMP_D - 0.005), bone, JNT)  # pad


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


def build_all(k, pistons, joints):
    build_hatch(k)
    build_pit(k)
    build_turret(k)
    build_rams(k)
    for tag, *_ in ARMS:
        build_arm(k, tag)
    for tag in CLAW_TAGS:
        build_claw(k, tag)
    build_pistons(k, pistons, joints)


def grip_table(kit, joints):
    """For each weapon width, each claw's angle when its fingers first meet the weapon, closing from
    fully open in 0.5 deg steps (the weapon box is taken into the claw's frame, so the exact finger
    meshes are tested). Unclamped: the claw reaches its closing limit without touching."""
    rows = []
    for width in GRIP_WIDTHS:
        lo, hi = grip_box(width)
        corners = [hatch(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        row = {"width_m": width}
        for claw in GRIP_CLAWS:
            parts = [p for p in all_parts(kit) if p.bone == claw]
            a_lo, a_hi = joints[claw].limits
            angle, clamped, v = a_lo, False, a_hi
            while v >= a_lo - 1e-9:
                inv = fk(joints, {claw: v})[claw].inverted()
                box = Part("weapon", 0, [inv @ c for c in corners], faces, True)
                if any(p.touches(box, tol=0.0) for p in parts):
                    angle, clamped = round(min(v + 0.5, a_hi), 1), True
                    break
                v -= 0.5
            row[claw] = {"angle_deg": angle, "clamped": clamped}
        rows.append(row)
    return rows


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


def sweep_states(joints):
    """Joint-range sweeps on top of the animation frames."""
    states = []
    for spin in range(0, 360, 15):
        for u in ((0, RAM_RAISE / 2, RAM_RAISE) if RAMS else (0,)):
            rams = {PLATFORM: u} if RAMS else {}
            if not ARM_NAMES:
                states.append((f"spin {spin} rams {u:.3f}", {SPIN: spin, **rams}))
                continue
            for a, c in ((0, 0), (5, 35), (5, 70), (10, 0), (0, 105), (10, 105), (0, CLAW_CLOSE / 2), (0, CLAW_CLOSE)):
                states.append((f"spin {spin} arm {a} claw {c}", {SPIN: spin, ARM_NAMES[0]: a, CLAW_NAMES[0]: c, **rams}))
    for i in range(26):
        v = -JACK_STEP * i / 25
        states.append((f"carriage {v:.3f}", {CARRIAGE: v}))
    for i in range(10):
        door = DOOR_CLOSED * i / 9
        states.append((f"doors {door:.0f} turret in", {DOOR_NAMES[0]: door, DOOR_NAMES[1]: door, CARRIAGE: -JACK_STEP}))
    return states


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


def on_socket(obj, rig):
    """Parent obj to WeaponSocket, with the mount axes matching weapon origins:
    local -Y is the weapon muzzle direction and +Z is up."""
    f, u = hatch_dir(0, 1, 0), hatch_dir(*GUN_UP)
    bone = rig.data.bones["WeaponSocket"]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", "WeaponSocket"
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    m = Matrix((f.cross(u), f, u)).transposed().to_4x4()
    m.translation = hatch(*MOUNT)
    obj.matrix_basis = m
    return obj


def build_weapon_mount(rig):
    """Mount gizmo: an empty on the WeaponSocket bone where the game puts a payload by its bottom:
    above the top platform (item table), or at the weapon's underside, centred between the claws
    (weapon holder). It is exported, and invisible in game."""
    obj = bpy.data.objects.new(MOUNT_NAME, None)
    obj.empty_display_type, obj.empty_display_size = "PLAIN_AXES", 0.05
    bpy.context.scene.collection.objects.link(obj)
    return on_socket(obj, rig)


def build_preview_marker(rig):
    """A 5 cm diamond (an octahedron, 8 triangles) on the weapon mount, for previews only (never
    exported): shows where the weapon goes and moves with the animations. It stands on the mount,
    its bottom tip at the origin and its long axis the weapon's up."""
    mat = bpy.data.materials.new("PRV_Marker")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 0.45, 0.05, 1.0)
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.45, 0.05, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 3.0
    bm = bmesh.new()
    r = 0.025
    z = r
    tips = [bm.verts.new(v) for v in ((r, 0, z), (-r, 0, z), (0, r, z), (0, -r, z), (0, 0, z + r), (0, 0, z - r))]
    for z in (tips[4], tips[5]):
        for i, j in ((0, 2), (2, 1), (1, 3), (3, 0)):
            bm.faces.new((tips[i], tips[j], z) if z is tips[4] else (tips[j], tips[i], z))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new("PRV_WeaponMarker_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("PRV_WeaponMarker", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return on_socket(obj, rig)


def build_preview_floor():
    """A floor or wall slab around the frame (the frame sits flush in it), for previews only (never
    exported)."""
    mat = bpy.data.materials.new(f"PRV_{SURFACE}")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.26, 0.27, 0.28, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    bm = bmesh.new()
    inner = [bm.verts.new(hatch(a, b, n)) for a, b, n in rect(FRAME_A, FRAME_B, 0.0, chamfer=0.001)]
    outer = [bm.verts.new(hatch(a, b, n)) for a, b, n in rect(3.0, 3.0, 0.0, chamfer=0.001)]
    under = [bm.verts.new(hatch(a, b, n)) for a, b, n in rect(3.0, 3.0, -0.02, chamfer=0.001)]
    low = [bm.verts.new(hatch(a, b, n)) for a, b, n in rect(FRAME_A, FRAME_B, -0.02, chamfer=0.001)]
    for i in range(8):
        j = (i + 1) % 8
        bm.faces.new((inner[i], inner[j], outer[j], outer[i]))  # top
        bm.faces.new((outer[i], outer[j], under[j], under[i]))  # rim
        bm.faces.new((under[i], under[j], low[j], low[i]))      # underside
        bm.faces.new((low[i], low[j], inner[j], inner[i]))      # hole wall
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(f"PRV_{SURFACE}_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(f"PRV_{SURFACE}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# --------------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------------

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


def write_rig_json(joints, pistons, tris, grip):
    def vec(v):
        return [round(c, 4) for c in v]

    data = {
        "name": NAME,
        "space": SPACE_NOTE + " glTF/Godot: (x, z, -y). Hinges turn about their bone's local X (value in degrees); "
                 "slides move along their bone's local Y (value in metres).",
        "rest": "deployed, doors open, claws closed (holding)",
        "cutout_m": {"patch": [round(2 * FRAME_A, 3), round(2 * FRAME_B, 3)],
                     "hole": [round(2 * OPEN_A, 3), round(2 * OPEN_B, 3)], "depth": round(PIT_DEPTH, 3),
                     "max_weapon_length": round(2 * OPEN_B - 0.02, 3), "note": CUTOUT_NOTE},
        "materials_note": "map-generic finish in Tensor's materials (off-white and grey paint, matte black, stainless steel): no team colours",
        "materials": SLOTS,
        "triangles": tris,
        "weapon_socket": {"bone": "WeaponSocket", "head": vec(hatch(*MOUNT)), "mount": MOUNT_NAME,
                          "place_by": "bottom",
                          "note": f"the asset carries no weapon: put the game's weapon on the {MOUNT_NAME} node (an "
                                  "invisible marker on the WeaponSocket bone) by its bottom: the origin is where the "
                                  "weapon's underside goes, centred across the holder; the mount's axes match the "
                                  "weapon asset's origin axes for identity attachment and follow the animations. " + (
                                      f"Here: {MOUNT_CLEARANCE:.2f} m above the top platform's surface." if TOP_PLATE_R else
                                      "Here: the weapon stands upright and the claws close on its sides "
                                      "symmetrically, whatever its thickness (see grip).")},
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
        "grip": {"claws": list(GRIP_CLAWS), "width": "the weapon's extent across the claws (m)",
                 "note": "close each claw to angle_deg for the held weapon's width (interpolate between rows); "
                         "claw_close ends at 0 deg, the grip for the nominal width",
                 "nominal_width_m": CLAMP_W, "rows": grip} if grip else None,
        "usage": ("deploy (doors open, turret comes out holding the weapon) -> spin (loop) -> claw_open when the "
                  "weapon is taken -> claw_close -> stop spin at 0 deg -> retract (turret goes in, doors close). "
                  "Pistons are baked into the animations; rebuild their aim constraints only for procedural poses."
                  if ARM_NAMES else
                  "deploy (doors swing open, the turret comes up, the rams raise the platform with the weapon hovering "
                  "above it) -> spin (loop) -> stop spin at 0 deg -> retract (rams lower the platform, the turret goes "
                  "down, doors swing shut). raise / lower move the rams alone. The weapon hovers over the platform at "
                  f"the {MOUNT_NAME} node."),
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
    points = [v for part in kit.parts for v in part.verts]
    assert abs(max(v.z for v in points)-min(v.z for v in points)-TARGET_OUTER_HEIGHT)<1e-5
    check_footprint(kit, (-FRAME_A, -FRAME_B), (FRAME_A, FRAME_B), (0.0, -FRAME_DEPTH), HATCH)
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_piston_clearance(pistons, joints, kit.solids, kit.parts)
    states = action_states(actions, joints) + sweep_states(joints)
    check_motion(kit, joints, states)
    print(f"[{NAME}] checks passed ({len(states)} motion states)")
    grip = grip_table(kit, joints) if GRIP_CLAWS else []
    if grip:
        print(f"[{NAME}] grip: " + ", ".join(
            f"{r['width_m']:.2f} m {r[GRIP_CLAWS[0]]['angle_deg']:+.1f}/{r[GRIP_CLAWS[1]]['angle_deg']:+.1f} deg"
            + ("" if r[GRIP_CLAWS[0]]["clamped"] and r[GRIP_CLAWS[1]]["clamped"] else " (not clamped)") for r in grip))

    body = kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    check_coplanar(body)
    skin(body, rig)
    cull_unseen(body, rig, joints, pistons, states, (-FRAME_A, -FRAME_B), (FRAME_A, FRAME_B), HATCH)
    sys.path.insert(0,str(HERE.parents[1]))
    from gameplay.dimensions import assert_authored_bounds
    assert_authored_bounds(HERE.name,[body])
    unwrap(body)
    tris = triangles(body)
    print(f"[{NAME}] body: {tris} tris (budget {TRI_BUDGET})")
    if tris > TRI_BUDGET:
        raise SystemExit(f"[{NAME}] over triangle budget: {tris}")
    for p in pistons:
        if p.name == PISTON_SPECS[0][0]:
            print(f"[{NAME}] {p.name}: stroke {p.stroke[0]:.3f}-{p.stroke[1]:.3f} m, "
                  f"barrel/rod {p.cyl_len:.3f} m, min overlap {p.overlap:.3f} m")

    mount = build_weapon_mount(rig)
    export([rig, body, mount], NAME)
    constrain(rig, joints, pistons)
    write_rig_json(joints, pistons, tris, grip)
    build_preview_marker(rig)
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
