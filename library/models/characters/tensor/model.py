"""Tensor - a combat warbot for KYLR, sculpted, modelled and rigged from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/characters/tensor/model.py

Produces, next to this script:
    tensor.blend                  source scene (body, default head and hidden head variants), opened by preview.py and animate.py
    tensor.glb / tensor.fbx       third-person body plus one mesh per head variant, skinned to
                                  RIG_Tensor (Godot: use the .glb; show one head, hide the rest),
                                  and the FlagMount gizmo (where a carried CTF flag's BackMount goes)
    tensor_rig.json               joint limits, coupled limits, mechanical stages, pistons, head
                                  variants: to rebuild the mechanics in-engine

Every mesh is checked mechanically first, then losslessly trimmed of faces that can never be
seen (Kit.optimise) before export.

Design: a 5 ft 9 in (1.753 m) warbot with a man's proportions, its armour lofted shells carved with
exact booleans (a keeled chest shield, a pelvis girdle, a deltoid upper arm, a gauntlet, a sculpted
thigh, a boot guard), over rigid mechanics. Every vertex is weighted 1.0 to exactly one
bone, so nothing stretches. Joints are hinges and servos with real rotation limits. Pistons are
pairs of aim-constrained bones, and their stroke is derived from the joint limits below.
Conventions: 1 unit = 1 m, faces -Y, Z up, origin at the feet, left side = +X.
Bone names follow Godot's SkeletonProfileHumanoid so retargeting maps automatically.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Alu': 'Metallic',
    'M_Black': 'Diffuse',
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Hose': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
    'M_Titanium': 'Metallic',
    'M_Wire': 'Metallic',
}

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

NAME = "tensor"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
BODY_STEM = NAME

HEIGHT = 1.753  # 5 ft 9 in: the head's top (user)
SHARP_ANGLE = math.radians(40)  # edges sharper than this shade hard; smoother ones blend
HEAD_BUDGET = 2_500  # per head variant mesh
TRI_BUDGET = 15_000  # per exported mesh (body)

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)

# --------------------------------------------------------------------------------------------
# Spec: joint positions (m) for the LEFT side (+X). The right side is mirrored in code.
# A man of 5 ft 9 in (1.753 m, the head's top; user): shoulder joints at 1.405 m, 0.35 m apart, a 0.30 m
# upper arm and 0.25 m forearm, the hips at 0.915 m, a 0.425 m thigh and 0.405 m shin, the head 0.23 m
# from chin to crown on a pitch axle at 1.60 m.
# --------------------------------------------------------------------------------------------

J = {k: Vector(v) for k, v in {
    "root": (0, 0, 0),
    "hips": (0, 0, 0.94), "spine": (0, 0, 1.04), "chest": (0, 0, 1.15), "upper_chest": (0, 0, 1.27),
    "neck": (0, 0, 1.434), "head": (0, 0, 1.60), "head_top": (0, 0, HEIGHT),
    "clavicle": (0.03, 0, 1.405), "shoulder": (0.175, 0, 1.405), "elbow": (0.475, 0, 1.405),
    "wrist": (0.725, 0, 1.405), "knuckles": (0.82, 0, 1.405),
    "hip": (0.095, 0, 0.915), "knee": (0.095, -0.01, 0.49), "ankle": (0.095, 0, 0.085),
    "ball": (0.095, -0.125, 0.035), "toe": (0.095, -0.195, 0.035),
}.items()}
S, E, W, H, K, A = (J[n] for n in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle"))


def hinge(lo, hi):
    """Single-axis joint: flexes about local X only."""
    return {"x": (lo, hi), "y": (0, 0), "z": (0, 0)}


# (name, head, tail, parent, flex, limits)
#   flex:   world direction the bone tip moves for +X rotation. Bone roll is set so that
#           local Z = flex and local X (= Y x Z) is the hinge axis.
#   limits: degrees per local axis. Missing axis = free, (0, 0) = locked.
BONE_SPECS = [
    ("Root", J["root"], (0, 0, 0.15), None, FWD, {}),
    ("Hips", J["hips"], J["spine"], "Root", FWD, {}),
    # Waist: two ball-jointed stages. Forward bending comes mostly from the hips; the waist adds a
    # little flex and generous twist, within what its rear struts can stroke.
    ("Spine", J["spine"], J["chest"], "Hips", FWD, {"x": (-8, 15), "y": (-25, 25), "z": (-10, 10)}),
    ("Chest", J["chest"], J["upper_chest"], "Spine", FWD, {"x": (-5, 10), "y": (-20, 20), "z": (-6, 6)}),
    ("UpperChest", J["upper_chest"], J["neck"], "Chest", FWD, {"x": (-10, 15), "y": (-15, 15), "z": (-10, 10)}),
    # Neck is a rotating shaft on a yaw bearing (yaw only); Head is a pitch hinge in the shaft's yoke,
    # driven by two hydraulics.
    ("Neck", J["neck"], J["head"], "UpperChest", FWD, {"x": (0, 0), "y": (-90, 90), "z": (0, 0)}),
    ("Head", J["head"], J["head_top"], "Neck", FWD, hinge(-20, 25)),
    # The clavicle: shrug and reach, within its motor's socket in the chest flank.
    ("LeftShoulder", J["clavicle"], J["shoulder"], "UpperChest", UP, {"x": (-4, 5), "y": (0, 0), "z": (-5, 5)}),
    ("LeftUpperArm", J["shoulder"], J["elbow"], "LeftShoulder", FWD, {"x": (-60, 80), "y": (-90, 90), "z": (-95, 55)}),
    # Elbow: a hinge, then the forearm's roll about its own axis in a housing behind the hinge.
    ("LeftLowerArm", J["elbow"], J["wrist"], "LeftUpperArm", FWD, {"x": (0, 140), "y": (-90, 90), "z": (0, 0)}),
    ("LeftHand", J["wrist"], J["knuckles"], "LeftLowerArm", DOWN, {"x": (-70, 80), "y": (-90, 90), "z": (-25, 25)}),
    ("LeftUpperLeg", J["hip"], J["knee"], "Hips", FWD, {"x": (-30, 100), "y": (-15, 5), "z": (-10, 75)}),
    ("LeftLowerLeg", J["knee"], J["ankle"], "LeftUpperLeg", BACK, hinge(0, 105)),
    ("LeftFoot", J["ankle"], J["ankle"] + Vector((0, -0.12, 0)), "LeftLowerLeg", UP, {"x": (-30, 40), "y": (-15, 15), "z": (0, 0)}),
    ("LeftToes", J["ball"], J["toe"], "LeftFoot", UP, hinge(-20, 45)),
]

# Mechanical stages: helper bones that turn on the intermediate axes of multi-axis joints, so each
# joint is a chain of real rotary stages whose axes meet at its pivot. Animations only drive the
# humanoid bones; the stages follow them through constraints (rebuilt in Godot from _rig.json).
#   Shoulder: pitch (lateral) -> roll (fore-aft) -> twist of the arm in the roll housing.
#   Hip (Cardan + yaw): yaw (vertical, motor in the pelvis) -> roll (fore-aft, the spider in the
#       yaw fork) -> pitch (lateral, the thigh knuckle on the spider). A marker bone on the thigh's
#       pitch axis tells the stages where that axis points.
#   Ankle: pitch (lateral hub in the shin yoke) -> roll of the foot about its own long axis.
#   Elbow: hinge (vertical hub in the upper arm's yoke, carrying the crank and the roll housing) ->
#       roll of the forearm about its own long axis, its rotor turning in that housing.
# (name, parent, pivot, direction, roll_to, constraint, target bone, head_tail, lock, track)
MECH_STAGES = (
    ("LeftShoulderPitch", "LeftShoulder", "shoulder", "arm", "arm_flex", "LOCKED_TRACK", "LeftUpperArm", 1.0, "LOCK_Y", "TRACK_X"),
    ("LeftShoulderRoll", "LeftShoulderPitch", "shoulder", "arm", "arm_flex", "DAMPED_TRACK", "LeftUpperArm", 1.0, None, "TRACK_Y"),
    ("LeftHipYaw", "Hips", "hip", (0, 0, 1), FWD, "LOCKED_TRACK", "LeftHipAxis", 1.0, "LOCK_Y", "TRACK_X"),
    ("LeftHipRoll", "LeftHipYaw", "hip", (1, 0, 0), UP, "DAMPED_TRACK", "LeftHipAxis", 1.0, None, "TRACK_Y"),
    ("LeftAnklePitch", "LeftLowerLeg", "ankle", "foot", "foot_flex", "LOCKED_TRACK", "LeftFoot", 1.0, "LOCK_X", "TRACK_Y"),
    ("LeftElbowHinge", "LeftUpperArm", "elbow", "forearm", "forearm_flex", "LOCKED_TRACK", "LeftLowerArm", 1.0, "LOCK_X", "TRACK_Y"),
)
# Hinge stages: a stage that turns with one bone's hinge (local X) alone, the bone rolling on it.
HINGE_STAGES = {"LeftElbowHinge": "LeftLowerArm"}
# Coupled limits: the box limits above are the hull; a real pose must also lie inside one of these
# boxes (x, y, z degrees), or the thigh knuckle meets the hip fork / pelvis. Full straddle is near
# neutral flexion and twist; deep flexion keeps the legs close. Exported for the animation/IK layer.
LIMIT_ENVELOPES = {"LeftUpperLeg": (((-30, 30), (-5, 5), (-10, 75)),
                                    ((-30, 60), (-15, 5), (-10, 40)),
                                    ((-30, 100), (-10, 5), (-10, 10)))}


def in_envelope(name, rot):
    boxes = LIMIT_ENVELOPES.get(name.replace("Right", "Left"))
    if name.startswith("Right"):
        rot = (rot[0], -rot[1], -rot[2])
    return boxes is None or any(all(lo - 1e-6 <= a <= hi + 1e-6 for a, (lo, hi) in zip(rot, box)) for box in boxes)


# Euler order per bone, matching its stage chain (Blender order: first letter applies first, in the
# parent frame). The ankle is pitch (shin-fixed hinge) then roll about the pitched foot axis: YXZ;
# the elbow likewise, hinge then the forearm's roll.
ROT_ORDER = {"LeftFoot": "YXZ", "LeftLowerArm": "YXZ"}


def rot_order(name):
    return ROT_ORDER.get(name.replace("Right", "Left"), "XYZ")


MARKERS = (("LeftHipAxis", "LeftUpperLeg", "hip", (0.08, 0, 0)),)  # (name, parent, pivot, offset)
MECH_PARENT = {"LeftUpperArm": "LeftShoulderRoll", "LeftShoulderRoll": "LeftShoulderPitch",
               "LeftShoulderPitch": "LeftShoulder",
               "LeftUpperLeg": "LeftHipRoll", "LeftHipRoll": "LeftHipYaw", "LeftHipYaw": "Hips",
               "LeftFoot": "LeftAnklePitch", "LeftAnklePitch": "LeftLowerLeg",
               "LeftLowerArm": "LeftElbowHinge", "LeftElbowHinge": "LeftUpperArm"}  # physical load path

# Fingers: knuckle position (from the wrist) and phalanx lengths (proximal, intermediate, distal).
# Palm faces -Z. The hand is the one every weapon's sockets were fitted to, unchanged about the wrist.
FINGERS = {
    "Index": (W + Vector((0.095, -0.030, 0.0)), (0.040, 0.028, 0.022)),
    "Middle": (W + Vector((0.098, -0.010, 0.0)), (0.044, 0.030, 0.024)),
    "Ring": (W + Vector((0.095, 0.010, 0.0)), (0.041, 0.028, 0.022)),
    "Little": (W + Vector((0.088, 0.030, 0.0)), (0.033, 0.024, 0.020)),
}
FINGER_SEGMENTS = ("Proximal", "Intermediate", "Distal")
FINGER_LIMITS = ((-15, 90), (0, 100), (0, 80))
THUMB_POINTS = tuple(W + Vector(d) for d in ((0.025, -0.038, -0.008), (0.052, -0.062, -0.012), (0.076, -0.078, -0.015),
                                            (0.096, -0.088, -0.017)))
THUMB_SEGMENTS = ("Metacarpal", "Proximal", "Distal")
THUMB_LIMITS = ({"x": (-10, 50), "y": (0, 0), "z": (-25, 25)}, hinge(0, 70), hinge(0, 80))
THUMB_FLEX = (0.1, 0.6, -0.8)  # curls across the palm

DIGITS = []  # left-side finger/thumb bone names, in chain order
for finger, (base, lengths) in FINGERS.items():
    parent, p = "LeftHand", Vector(base)
    for seg, length, lim in zip(FINGER_SEGMENTS, lengths, FINGER_LIMITS):
        name, tail = f"Left{finger}{seg}", p + Vector((length, 0, 0))
        BONE_SPECS.append((name, p, tail, parent, DOWN, hinge(*lim)))
        DIGITS.append(name)
        parent, p = name, tail
for i, (seg, lim) in enumerate(zip(THUMB_SEGMENTS, THUMB_LIMITS)):
    name = f"LeftThumb{seg}"
    parent = "LeftHand" if i == 0 else f"LeftThumb{THUMB_SEGMENTS[i - 1]}"
    BONE_SPECS.append((name, THUMB_POINTS[i], THUMB_POINTS[i + 1], parent, THUMB_FLEX, lim))
    DIGITS.append(name)

# Pistons: cylinder rides on the parent bone (end A), rod on the child bone (end B). Each aims
# at the other's anchor, so the rod slides in the barrel as the child joint (local X) rotates.
# Wide hinges (elbow, knee) drive a crank horn on an axle stub outside the joint's own yoke, so
# the actuator never sweeps through the joint. check_piston_clearance() enforces this.
# (name, cylinder parent, A, rod parent, B, barrel radius)
STRUT_A = (0.025, 0.106, 0.995)  # lower rod end, on a lug on the pelvis girdle's back face
STRUT_B = (0.030, 0.100, 1.190)  # upper rod end, on a lug on the abdomen block's upper back flat
# The elbow folds to 140 deg (user: at 120 his firing wrist couldn't come nearer than 28 cm to the shoulder, so a
# shouldered weapon's forend was out of his other hand's reach); the horn is long enough to keep
# PISTON_MIN_ARM at both ends (the rest direction balances them: the barrel sits off the arm's axis), the barrel
# anchored far enough back for the stroke.
ELBOW_CRANK = (0.046, (-0.9483, 0.3173))  # horn length, rest direction in XY (balancing the moment arm over 0..140)
ELBOW_PISTON_A = E.x - 0.19              # the barrel's anchor along the upper arm's top flat
ELBOW_PISTON_Z = S.z + 0.08              # piston plane, lying on the upper arm's top face
KNEE_CRANK_B = (H.x + 0.112, -0.07, K.z + 0.07)  # horn tip, outboard of the knee bearing
ROLL_HOUSING = (E.x + 0.11, E.x + 0.14)   # the forearm roll housing on the elbow's hinge stage (x): out on the tongue,
ROLL_R = 0.040                            # so at the full fold it clears the yoke and the upper arm tapering to it
PISTON_SPECS = [
    # Head hydraulics: from clevises on the neck's bearing boot up to clevises under the head's mount plate,
    # ahead of the axle.
    ("LeftHeadPiston", "Neck", (0.04, -0.054, 1.506), "Head", (0.04, -0.054, 1.618), 0.008),
    # Waist struts behind the spine: pelvis back face -> abdomen block, across both ball-jointed stages.
    ("LeftSpineStrut", "Hips", STRUT_A, "Chest", STRUT_B, 0.008),
    ("LeftElbowPiston", "LeftUpperArm", (ELBOW_PISTON_A, 0.01, ELBOW_PISTON_Z), "LeftElbowHinge",
     (E.x + ELBOW_CRANK[0] * ELBOW_CRANK[1][0], ELBOW_CRANK[0] * ELBOW_CRANK[1][1], ELBOW_PISTON_Z), 0.013),
    ("LeftKneePiston", "LeftUpperLeg", (H.x + 0.112, 0.0, 0.785), "LeftLowerLeg", KNEE_CRANK_B, 0.016),
    ("LeftAnklePiston", "LeftLowerLeg", (A.x, 0.108, 0.302), "LeftFoot", (A.x, 0.09, 0.064), 0.014),
]
STRUT_EYE_HALF = 0.0085  # half-width of a strut rod-end housing along its pin
PISTON_MIN_OVERLAP = 0.015  # rod stays at least this deep inside the barrel at full extension

# slot: (base colour, metallic, roughness, emission strength). The weapons' materials: paints matte-ish,
# metals as machined.
MATERIALS = {
    "M_Primary": ((0.70, 0.68, 0.63), 0.3, 0.58, 0.0),    # the armour shells: off-white by default (user),
                                                           # a team's paint in play (TEAM_COLORS)
    "M_Secondary": ((0.16, 0.16, 0.17), 0.25, 0.58, 0.0),  # accents: roll cage, grab bars, piston barrels, stripes,
                                                           # hatches: grey by default, a team's accent in play
    "M_Frame": ((0.026, 0.026, 0.029), 0.25, 0.66, 0.0),  # matte black (user): chassis, frames, yokes, machined insides
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),      # stainless steel: rods, pins, axles, rotor faces
    "M_Emissive": ((0.25, 1.0, 0.4), 0.0, 0.4, 6.0),      # the head's sensors, the lamps, the status light
    "M_Wire": ((0.72, 0.36, 0.18), 1.0, 0.35, 0.0),       # copper power/signal looms (never team-coloured)
    "M_Hose": ((0.90, 0.70, 0.08), 0.0, 0.55, 0.0),       # yellow hydraulic lines (never team-coloured)
    "M_Titanium": ((0.29, 0.29, 0.30), 1.0, 0.45, 0.0),   # matte titanium: motors, bearing housings, hubs
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.22, 0.0),      # bushings, bearing caps, fittings
    "M_Alu": ((0.60, 0.61, 0.63), 1.0, 0.32, 0.0),        # brushed aluminium: canisters, heat sinks, stacks
    "M_Black": ((0.018, 0.018, 0.02), 0.2, 0.72, 0.0),    # matte black: soles, pads, grips, bellows
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, WIRE, HOSE, TIT, BRZ, ALU, BLK = SLOTS
TEAM_MATERIALS = (PRI, SEC)  # swap these two per team; the rest stay fixed
TEAM_COLORS = {  # the team variants (the default is MATERIALS' off-white and grey): military paints,
               # each with a contrasting military accent
    "green": {PRI: (0.13, 0.17, 0.08), SEC: (0.40, 0.29, 0.15)},      # olive drab, coyote tan
    "red": {PRI: (0.18, 0.035, 0.025), SEC: (0.45, 0.39, 0.25)},      # military red, desert sand
    "yellow": {PRI: (0.521, 0.356, 0.076), SEC: (0.069, 0.110, 0.162)},  # military yellow, military blue
    "blue": {PRI: (0.069, 0.110, 0.162), SEC: (0.521, 0.356, 0.076)},    # military blue, military yellow
}


def mirror_name(name):
    return "Right" + name[4:] if name.startswith("Left") else name


def mirror_vec(v):
    return Vector((-v[0], v[1], v[2]))


def mirror_limits(limits):
    """Mirroring flips the sense of rotation about local Y and Z; X (the flex axis) is unchanged."""
    out = dict(limits)
    for ax in "yz":
        if ax in limits:
            lo, hi = limits[ax]
            out[ax] = (-hi if hi else 0, -lo if lo else 0)
    return out


# --------------------------------------------------------------------------------------------
# Resolved rig data
# --------------------------------------------------------------------------------------------

@dataclass
class BoneDef:
    name: str
    head: Vector
    tail: Vector
    parent: str | None
    flex: Vector
    limits: dict

    @property
    def axis(self):
        return (self.tail - self.head).normalized()

    @property
    def hinge_axis(self):
        return self.axis.cross(self.flex).normalized()


@dataclass
class PistonDef:
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
    sides: list = field(default_factory=list)
    multi: bool = False  # spans multi-axis joints: ball rod-ends, stroke sampled over the limit box

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


def resolve_bones():
    bones = []
    for name, head, tail, parent, flex, limits in BONE_SPECS:
        head, tail, flex = Vector(head), Vector(tail), Vector(flex)
        d = (tail - head).normalized()
        flex = (flex - d * flex.dot(d)).normalized()
        bones.append(BoneDef(name, head, tail, parent, flex, limits))
        if name.startswith("Left"):
            bones.append(BoneDef(mirror_name(name), mirror_vec(head), mirror_vec(tail),
                                 mirror_name(parent), mirror_vec(flex), mirror_limits(limits)))
    return {b.name: b for b in bones}


def chain_poses(bones, top, bottom, steps=(0.0, 0.5, 1.0)):
    """Sample every combination of the limit boxes of the bones from `bottom` up to (excluding)
    `top`. Each pose is a list of cumulative (R, t) per chain bone: p' = R @ p + t."""
    chain, n = [], bottom
    while n != top:
        chain.append(bones[n])
        n = bones[n].parent
    chain.reverse()
    poses = [[]]
    for b in chain:
        frame = Matrix((b.hinge_axis, b.axis, b.flex)).transposed()
        limits = [b.limits.get(ax, (0, 0)) for ax in "xyz"]
        eulers = {tuple(lo + (hi - lo) * f for (lo, hi), f in zip(limits, (fx, fy, fz)))
                  for fx in steps for fy in steps for fz in steps}
        new = []
        for pose in poses:
            r0, t0 = pose[-1] if pose else (Matrix.Identity(3), Vector())
            for e in eulers:
                rl = frame @ Euler([math.radians(a) for a in e], rot_order(b.name)).to_matrix() @ frame.transposed()
                new.append(pose + [(r0 @ rl, r0 @ (b.head - rl @ b.head) + t0)])
        poses = new
    return [b.name for b in chain], poses


def hinge_of(bones, name):
    """The bone whose hinge (local X) `name` turns with: a hinge stage's bone, else itself."""
    left = HINGE_STAGES.get(name.replace("Right", "Left"))
    if left is None:
        return bones[name]
    return bones[mirror_name(left) if name.startswith("Right") else left]


def is_hinge_span(bones, cyl_parent, rod_parent):
    j = hinge_of(bones, rod_parent)
    return j.parent == cyl_parent and (j.name != rod_parent or j.limits.get("y") == (0, 0) and j.limits.get("z") == (0, 0))


def resolve_pistons(bones):
    """Sweep the joint(s) the piston spans through their limits to size barrel and rod for the
    full stroke: hinges finely along X, multi-axis spans over their whole limit box."""
    pistons = []
    for name, cyl_parent, a, rod_parent, b, radius in PISTON_SPECS:
        a, b = Vector(a), Vector(b)
        joint = hinge_of(bones, rod_parent)
        multi = not is_hinge_span(bones, cyl_parent, rod_parent)
        dists = []
        if multi:
            _, poses = chain_poses(bones, cyl_parent, rod_parent)
            dists = [((pose[-1][0] @ b + pose[-1][1]) - a).length for pose in poses]
        else:
            lo, hi = joint.limits["x"]
            for i in range(91):
                rot = Matrix.Rotation(math.radians(lo + (hi - lo) * i / 90), 3, joint.hinge_axis)
                dists.append((joint.head + rot @ (b - joint.head) - a).length)
        dmin, dmax = min(dists), max(dists)
        cyl_len = rod_len = 0.85 * dmin
        overlap = cyl_len + rod_len - dmax
        if overlap < PISTON_MIN_OVERLAP:
            raise SystemExit(f"[{NAME}] {name}: stroke {dmin:.3f}-{dmax:.3f} m too long for its mounts "
                             f"(overlap {overlap:.3f} m < {PISTON_MIN_OVERLAP} m); move A/B")
        for flip in (False, True):
            pistons.append(PistonDef(
                mirror_name(name) if flip else name,
                mirror_name(cyl_parent) if flip else cyl_parent, mirror_vec(a) if flip else a,
                mirror_name(rod_parent) if flip else rod_parent, mirror_vec(b) if flip else b,
                radius, (dmin, dmax), cyl_len, rod_len, overlap, multi=multi))
    return pistons


PISTON_MIN_ARM = 0.015  # piston line must stay at least this far from its hinge axis


def descendants(bones, root):
    """`root` and every bone it carries, with the hinge stages turning with them."""
    out = {root}
    for b in bones.values():  # BONE_SPECS lists parents before children
        if b.parent in out:
            out.add(b.name)
    return out | {s for s, j in HINGE_STAGES.items() if j in out}


BAR_CHECK_JOINTS = ("Head", "LeftLowerArm", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes")
ALIGN_TOL = 0.002  # rotor axis must pass within 2 mm of the joint pivot


def check_connectivity(kit, bones, pistons):
    """Every part must touch the rest of its own rigid body (one connected piece per bone), and
    each bone's geometry must touch its parent's (hub in yoke, barrel in mount, rod on horn)."""
    parent = {b.name: b.parent for b in bones.values()}
    parent.update(MECH_PARENT)
    for p in pistons:
        parent[p.cylinder], parent[p.rod] = p.cyl_parent, p.rod_parent
    by_bone = {}
    for part in kit.parts:
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
    for bone, pts, r in kit.tubes:  # between its buried ends a bar must stand clear of its body
        length = sum((b - a).length for a, b in zip(pts, pts[1:]))
        run = 0.0
        for a, b in zip(pts, pts[1:]):
            n = max(1, int((b - a).length / 0.005))
            for k in range(n):
                q, at = a.lerp(b, k / n), run + (b - a).length * k / n
                if min(at, length - at) < r + 0.02:
                    continue  # the buried end and its fillet
                hit = next((part for part in kit.parts if part.bone == bone and part.solid
                            and (part.inside(q) or part.bvh.find_nearest(q)[3] < r * 0.9)), None)
                if hit:
                    problems.append(f"{bone}: bar passes into the body (line {hit.line}) at "
                                    f"{tuple(round(c, 3) for c in q)}")
                    break
            run += (b - a).length
    for bone, pts, _ in kit.tubes:  # each end sits on a structural surface, square to it
        for end, nxt in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            t = (nxt - end).normalized()
            best = None
            for q in kit.parts:
                if q.bone == bone and q.solid:  # boolean-cut (non-convex) mounts count too
                    loc, normal, _, dist = q.bvh.find_nearest(end)
                    if dist is not None and (best is None or dist < best[0]):
                        best = (dist, normal)
            if best is None or best[0] > 0.0025:
                problems.append(f"{bone}: bar end {tuple(round(c, 3) for c in end)} is not on a mounting surface")
            elif abs(best[1].normalized().dot(t)) < 0.95:
                problems.append(f"{bone}: bar end {tuple(round(c, 3) for c in end)} meets its surface at an angle")
    for p in pistons:
        if p.name.startswith("Left") and not any(a.touches(b) for a in by_bone.get(p.rod, [])
                                                 for b in by_bone.get(p.cylinder, [])):
            problems.append(f"{p.name}: rod is not inside its barrel")
    if problems:
        raise SystemExit(f"[{NAME}] connectivity failed:\n  " + "\n  ".join(problems))


def check_motion_clearance(kit, bones):
    """Sweep each hinge in BAR_CHECK_JOINTS through its limits: no part of the moving chain may hit
    a part of the parent that it does not already touch at rest (seats like hub-in-yoke)."""
    problems = []
    for name in BAR_CHECK_JOINTS:
        joint = bones[name]
        moving = [q for q in kit.parts if q.bone in descendants(bones, name)]
        static = [q for q in kit.parts if q.bone == joint.parent]
        seated = {(id(m), id(s)) for m in moving for s in static if m.touches(s, tol=0.0)}
        lo, hi = joint.limits["x"]
        for i in range(25):
            angle = lo + (hi - lo) * i / 24
            rot = Matrix.Rotation(math.radians(angle), 3, joint.hinge_axis)
            for m in moving:
                moved = Part(m.bone, m.line, [joint.head + rot @ (v - joint.head) for v in m.verts],
                             m.faces, m.convex)
                for st in static:
                    if (id(m), id(st)) not in seated and moved.touches(st, tol=0.0):
                        problems.append(f"{m.bone} (line {m.line}) hits {st.bone} (line {st.line}) "
                                        f"at {name} {angle:.0f} deg")
    def sweep(moving_xf, static_bones, label):
        """Serial stages through sampled poses. moving_xf: [(bone set, fn(pose) -> 3x3 rotation about
        the pivot)]; each stage group is checked against the fixed parent and against every other
        group, skipping pairs already seated against each other at rest."""
        groups = [([q for q in kit.parts if q.bone in bset], fn) for bset, fn in moving_xf]
        static = [q for q in kit.parts if q.bone in static_bones]
        pairs = [(gi, m, None, st) for gi, (ps, _) in enumerate(groups) for m in ps for st in static]
        pairs += [(gi, m, gj, n) for gi, (ps, _) in enumerate(groups) for gj, (qs, _) in enumerate(groups)
                  if gj > gi for m in ps for n in qs]
        pairs = [pr for pr in pairs if not pr[1].touches(pr[3], tol=0.0)]
        for pose, pivot, tag in label():
            cache = {}

            def moved(gi, part):
                if (gi, id(part)) not in cache:
                    rot = groups[gi][1](pose)
                    cache[gi, id(part)] = Part(part.bone, part.line, [pivot + rot @ (v - pivot) for v in part.verts],
                                               part.faces, part.convex)
                return cache[gi, id(part)]
            for gi, m, gj, n in pairs:
                other = n if gj is None else moved(gj, n)
                if moved(gi, m).touches(other, tol=0.0):
                    problems.append(f"{m.bone} (line {m.line}) hits {n.bone} (line {n.line}) at {tag}")

    # Hip: sample the thigh's limit envelopes; resolve yaw and roll exactly as the stage constraints do.
    leg = bones["LeftUpperLeg"]
    leg_rest = Matrix((leg.hinge_axis, leg.axis, leg.flex)).transposed()
    out_axis = Vector((1, 0, 0))

    def hip_poses():
        for (xl, xh), (yl, yh), (zl, zh) in LIMIT_ENVELOPES["LeftUpperLeg"]:
          for ex in (xl + (xh - xl) * i / 6 for i in range(7)):
            for ey in (yl + (yh - yl) * i / 4 for i in range(5)):
                for ez in (zl + (zh - zl) * i / 6 for i in range(7)):
                    r_leg = leg_rest @ Euler([math.radians(a) for a in (ex, ey, ez)], "XYZ").to_matrix() @ leg_rest.transposed()
                    h = r_leg @ out_axis
                    r_yaw = Matrix.Rotation(math.atan2(h.y, h.x), 3, Vector((0, 0, 1)))
                    hx = r_yaw @ out_axis
                    sw = hx.cross(h)
                    r_roll = (Matrix.Rotation(hx.angle(h), 3, sw.normalized()) if sw.length > 1e-6
                              else Matrix.Identity(3)) @ r_yaw
                    yield (r_yaw, r_roll, r_leg), leg.head, f"hip x {ex:.0f} y {ey:.0f} z {ez:.0f}"

    sweep([({"LeftHipYaw"}, lambda p: p[0]), ({"LeftHipRoll"}, lambda p: p[1]),
           (descendants(bones, "LeftUpperLeg"), lambda p: p[2])], {"Hips"}, hip_poses)

    # Ankle: pitch x roll; the pitch stage follows the foot's long axis about the pitch hinge.
    foot = bones["LeftFoot"]
    foot_rest = Matrix((foot.hinge_axis, foot.axis, foot.flex)).transposed()

    def ankle_poses():
        (xl, xh), (yl, yh) = foot.limits["x"], foot.limits["y"]
        for ex in (xl + (xh - xl) * i / 6 for i in range(7)):
            for ey in (yl + (yh - yl) * i / 4 for i in range(5)):
                r_foot = foot_rest @ Euler((math.radians(ex), math.radians(ey), 0), rot_order("LeftFoot")).to_matrix() @ foot_rest.transposed()
                r_pitch = Matrix.Rotation(math.radians(ex), 3, foot.hinge_axis)
                yield (r_pitch, r_foot), foot.head, f"ankle x {ex:.0f} y {ey:.0f}"

    sweep([({"LeftAnklePitch"}, lambda p: p[0]), (descendants(bones, "LeftFoot"), lambda p: p[1])],
          {"LeftLowerLeg"}, ankle_poses)

    # Elbow: hinge x forearm roll; the hinge stage (hub, crank, roll housing) turns with the hinge only.
    fore = bones["LeftLowerArm"]
    fore_rest = Matrix((fore.hinge_axis, fore.axis, fore.flex)).transposed()

    def elbow_poses():
        (xl, xh), (yl, yh) = fore.limits["x"], fore.limits["y"]
        for ex in (xl + (xh - xl) * i / 8 for i in range(9)):
            for ey in (yl + (yh - yl) * i / 8 for i in range(9)):
                r_fore = fore_rest @ Euler((math.radians(ex), math.radians(ey), 0), rot_order("LeftLowerArm")).to_matrix() @ fore_rest.transposed()
                yield (Matrix.Rotation(math.radians(ex), 3, fore.hinge_axis), r_fore), fore.head, f"elbow x {ex:.0f} y {ey:.0f}"

    sweep([({"LeftElbowHinge"}, lambda p: p[0]), (descendants(bones, "LeftLowerArm") - {"LeftElbowHinge"}, lambda p: p[1])],
          {"LeftUpperArm"}, elbow_poses)

    # Neck yaw x head pitch against the upper body (raised collar, floodlight, cage).
    neck, head = bones["Neck"], bones["Head"]
    moving = [q for q in kit.parts if q.bone in ("Neck", "Head")]
    static = [q for q in kit.parts if q.bone == "UpperChest"]
    seated = {(id(m), id(s)) for m in moving for s in static if m.touches(s, tol=0.0)}
    for yaw in range(-90, 91, 15):
        ry = Matrix.Rotation(math.radians(yaw), 3, neck.axis)
        hh = neck.head + ry @ (head.head - neck.head)
        for pitch in (-20, -10, 0, 12, 25):
            rp = Matrix.Rotation(math.radians(pitch), 3, ry @ head.hinge_axis)
            for m in moving:
                verts = [neck.head + ry @ (v - neck.head) for v in m.verts]
                if m.bone == "Head":
                    verts = [hh + rp @ (v - hh) for v in verts]
                moved = Part(m.bone, m.line, verts, m.faces, m.convex)
                for st in static:
                    if (id(m), id(st)) not in seated and moved.touches(st, tol=0.0):
                        problems.append(f"{m.bone} (line {m.line}) hits {st.bone} (line {st.line}) "
                                        f"at neck yaw {yaw} head pitch {pitch}")
    arm = bones["LeftUpperArm"]
    roll_group = {"LeftShoulderRoll"} | descendants(bones, "LeftUpperArm")
    pitch_group = {"LeftShoulderPitch"} | roll_group
    moving = [q for q in kit.parts if q.bone in pitch_group]
    static = [q for q in kit.parts if q.bone in ("LeftShoulder", "UpperChest")]
    seated = {(id(m), id(s)) for m in moving for s in static if m.touches(s, tol=0.0)}
    # Sample the arm's real limit box and resolve the stages exactly as the rig constraints do.
    rest = Matrix((arm.hinge_axis, arm.axis, arm.flex)).transposed()  # bone rest frame (X, Y, Z)
    (x_lo, x_hi), (z_lo, z_hi) = arm.limits["x"], arm.limits["z"]
    for xi in range(8):
        for zi in range(9):
            ex = x_lo + (x_hi - x_lo) * xi / 7
            ez = z_lo + (z_hi - z_lo) * zi / 8
            local = Euler((math.radians(ex), 0.0, math.radians(ez)), "XYZ").to_matrix()
            r_arm = rest @ local @ rest.transposed()
            d = r_arm @ arm.axis
            flat = d - arm.axis * d.dot(arm.axis)  # pitch: Locked Track (lock Y) aims local X at the tip
            pitch = arm.hinge_axis.angle(flat) if flat.length > 1e-6 else 0.0
            if flat.length > 1e-6 and arm.hinge_axis.cross(flat).dot(arm.axis) < 0:
                pitch = -pitch
            r_pitch = Matrix.Rotation(pitch, 3, arm.axis)
            swing = arm.axis.cross(d)  # roll: Damped Track swings the stage's Y onto the tip
            r_roll = (Matrix.Rotation(arm.axis.angle(d), 3, swing.normalized()) if swing.length > 1e-6
                      else Matrix.Identity(3)) @ r_pitch
            for m in moving:
                rot = r_pitch if m.bone == "LeftShoulderPitch" else r_roll if m.bone == "LeftShoulderRoll" else r_arm
                moved = Part(m.bone, m.line, [arm.head + rot @ (v - arm.head) for v in m.verts], m.faces, m.convex)
                for st in static:
                    if (id(m), id(st)) not in seated and moved.touches(st, tol=0.0):
                        problems.append(f"{m.bone} (line {m.line}) hits {st.bone} (line {st.line}) "
                                        f"at LeftUpperArm x {ex:.0f} z {ez:.0f}")
    if problems:
        raise SystemExit(f"[{NAME}] motion clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


def hinge_joints(bones):
    """(bone, axis) for every single-axis joint: hinges, the yaw shaft, and primary axes of the
    two-axis ankle and thumb base."""
    for b in bones.values():
        if not b.name.startswith("Right") and b.limits:
            if b.name == "Neck":
                yield b, b.axis
            elif b.limits.get("y") == (0, 0) and b.limits.get("z") == (0, 0) or b.name == "LeftThumbMetacarpal":
                yield b, b.hinge_axis


def rotary_joints(bones):
    """(bone, axis, pivot, mechanical parent) for every joint that turns about one axis: hinges,
    the neck yaw shaft, the primary axes of the ankle and thumb base, and each stage of the
    shoulder, hip, ankle and elbow chains."""
    arm = bones["LeftUpperArm"]
    return [(b.name, axis, b.head, b.parent) for b, axis in hinge_joints(bones)] + [
        ("LeftShoulderPitch", arm.axis, arm.head, "LeftShoulder"),                   # lateral axis
        ("LeftShoulderRoll", arm.flex, arm.head, "LeftShoulderPitch"),               # fore-aft axis
        ("LeftUpperArm", arm.axis, arm.head, "LeftShoulderRoll"),                    # twist
        ("LeftHipYaw", Vector((0, 0, 1)), bones["LeftUpperLeg"].head, "Hips"),         # hip yaw
        ("LeftHipRoll", Vector((0, 1, 0)), bones["LeftUpperLeg"].head, "LeftHipYaw"),  # hip roll
        ("LeftUpperLeg", Vector((1, 0, 0)), bones["LeftUpperLeg"].head, "LeftHipRoll"),  # hip pitch
        ("LeftAnklePitch", bones["LeftFoot"].hinge_axis, bones["LeftFoot"].head, "LeftLowerLeg"),
        ("LeftElbowHinge", bones["LeftLowerArm"].hinge_axis, bones["LeftLowerArm"].head, "LeftUpperArm"),  # elbow
        ("LeftLowerArm", bones["LeftLowerArm"].axis, bones["LeftLowerArm"].head, "LeftElbowHinge"),  # forearm roll
        ("LeftFoot", bones["LeftFoot"].axis, bones["LeftFoot"].head, "LeftAnklePitch"),  # ankle roll
    ]


def check_joint_alignment(kit, bones, only=None):
    """Each joint needs a rotor on the moving bone that is coaxial with the joint's real axis and
    centred on its pivot, and a bearing/yoke on the parent that the axis actually passes through."""
    problems = []
    for name, axis, pivot, parent in rotary_joints(bones):
        if only is not None and name not in only:
            continue
        rotor = False
        for bone, mid, ax, half in kit.axes:
            off = pivot - mid
            if bone == name and abs(ax.dot(axis)) > 0.999 and (off - ax * off.dot(ax)).length < ALIGN_TOL:
                rotor = True
                break
        line = [pivot + axis * (0.01 * k) for k in range(-10, 11)]
        bearing = any(part.bone == parent and any(part.inside(q) for q in line) for part in kit.parts)
        if not rotor:
            problems.append(f"{name}: no rotor coaxial with its axis {tuple(round(c, 3) for c in axis)} "
                            f"through {tuple(round(c, 3) for c in pivot)}")
        if not bearing:
            problems.append(f"{name}: its axis passes through no part of {parent}")
    if problems:
        raise SystemExit(f"[{NAME}] joint alignment failed:\n  " + "\n  ".join(problems))


def check_bar_clearance(bones, solids, tubes):
    """Sweep each hinge through its X limits and fail if a guard bar / roll cage on one side of
    the joint passes through a solid part or bar on the other side. Bars are anchored into their
    own bone's parts by design, so only cross-joint contact counts."""
    problems = []
    for name in BAR_CHECK_JOINTS:
        joint = bones[name]
        moving, static = descendants(bones, name), {joint.parent}
        lo, hi = joint.limits["x"]
        for i in range(31):
            angle = lo + (hi - lo) * i / 30
            rot = Matrix.Rotation(math.radians(angle), 3, joint.hinge_axis)

            def place(bone, p):
                return joint.head + rot @ (p - joint.head) if bone in moving else p

            samples = []  # (side, bone, point, radius) along every bar near this joint
            for bone, pts, r in tubes:
                side = "moving" if bone in moving else "static" if bone in static else None
                if side is None:
                    continue
                for p0, p1 in zip(pts, pts[1:]):
                    n = max(2, int((p1 - p0).length / 0.01))
                    samples += [(side, bone, place(bone, p0.lerp(p1, k / n)), r) for k in range(n + 1)]
            for side, bone, q, r in samples:
                other = static if side == "moving" else moving
                for s in solids:
                    if s.bone not in other:
                        continue
                    center = place(s.bone, s.center)
                    srot = rot @ s.rot if s.bone in moving else s.rot
                    if s.contains(center, srot, q, r):
                        problems.append(f"{bone} bar hits {s.bone} {s.kind} @ "
                                        f"{tuple(round(c, 3) for c in s.center)} at {name} {angle:.0f} deg")
                        break
            for (sa, ba, qa, ra), (sb, bb, qb, rb) in ((a, b) for a in samples for b in samples
                                                       if a[0] == "moving" and b[0] == "static"):
                if (qa - qb).length < ra + rb:
                    problems.append(f"{ba} bar hits {bb} bar at {name} {angle:.0f} deg")
                    break
    if problems:
        raise SystemExit(f"[{NAME}] bar clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


def check_piston_clearance(pistons, bones, solids, parts=()):
    """Sweep each piston's joint through its X limits and fail the build if, at any angle, the
    piston crosses (or comes within PISTON_MIN_ARM of) the hinge axis, or passes through a solid
    part of the parent or of the moving chain. This keeps actuators on one side of their joint
    and outside the armour for the whole range of motion."""
    problems = []
    machined = [q for q in parts if q.exact and q.solid]  # prism/plate parts: test exact meshes

    def hits_machined(bones_xf, a, span, radius, end_skip):
        """bones_xf: bone -> (R, t) placing that bone's rest geometry; test the piston line."""
        for q in machined:
            if q.bone not in bones_xf:
                continue
            r, t = bones_xf[q.bone]
            rt = r.transposed()
            for k in range(25):
                f = k / 24
                if end_skip < f < 1 - end_skip and q.hits(rt @ (a + span * f - t), radius):
                    return q
        return None

    for p in pistons:
        if p.name.startswith("Right"):
            continue  # mirror image of the left
        if p.multi:  # ball-ended strut: sample the whole limit box, check against every chain part
            names, poses = chain_poses(bones, p.cyl_parent, p.rod_parent)
            for pose in poses:
                b = pose[-1][0] @ p.b + pose[-1][1]
                span = b - p.a
                end_skip = (p.radius + 0.02) / span.length
                for s in solids:
                    if s.bone == p.cyl_parent:
                        center, srot = s.center, s.rot
                    elif s.bone in names:
                        r, t = pose[names.index(s.bone)]
                        center, srot = r @ s.center + t, r @ s.rot
                    else:
                        continue
                    if any(end_skip < t < 1 - end_skip and s.contains(center, srot, p.a + span * t, p.radius)
                           for t in (k / 24 for k in range(25))):
                        problems.append(f"{p.name} hits {s.bone} {s.kind} @ {tuple(round(c, 3) for c in s.center)}")
                        break
                xf = {p.cyl_parent: (Matrix.Identity(3), Vector())}
                xf.update({n: pose[i] for i, n in enumerate(names)})
                q = hits_machined(xf, p.a, span, p.radius, end_skip)
                if q:
                    problems.append(f"{p.name} hits {q.bone} (line {q.line})")
            continue
        joint = hinge_of(bones, p.rod_parent)
        moving = descendants(bones, joint.name)
        # On a hinge stage the rod end turns with the hinge alone and the bone beyond it also rolls
        # about its own axis: sample that roll too, for the parts that roll.
        rolling = moving - {p.rod_parent} if joint.name != p.rod_parent else set()
        yl, yh = joint.limits.get("y", (0, 0)) if rolling else (0, 0)
        rolls = sorted({yl + (yh - yl) * j / 6 for j in range(7)})
        lo, hi = joint.limits["x"]
        arms = []
        for i in range(61):
            angle = lo + (hi - lo) * i / 60
            rot = Matrix.Rotation(math.radians(angle), 3, joint.hinge_axis)
            b = joint.head + rot @ (p.b - joint.head)
            span = b - p.a
            u = span.normalized()
            arms.append(((joint.head - p.a).cross(u)).dot(joint.hinge_axis))
            end_skip = (p.radius + 0.02) / span.length  # ends sit on their mounts by design
            for roll in rolls:
                rot_r = rot @ Matrix.Rotation(math.radians(roll), 3, joint.axis)
                tag = f"{angle:.0f} deg" + (f" roll {roll:.0f}" if rolling else "")
                for s in solids:
                    if s.bone in moving:
                        r = rot_r if s.bone in rolling else rot
                        center, srot = joint.head + r @ (s.center - joint.head), r @ s.rot
                    elif s.bone == p.cyl_parent:
                        center, srot = s.center, s.rot
                    else:
                        continue
                    hit = next((t for t in (k / 24 for k in range(25)) if end_skip < t < 1 - end_skip
                                and s.contains(center, srot, p.a + span * t, p.radius)), None)
                    if hit is not None:
                        problems.append(f"{p.name} at {tag} hits {s.bone} {s.kind} "
                                        f"@ {tuple(round(c, 3) for c in s.center)} (t={hit:.2f})")
                        break
                xf = {n: (r, joint.head - r @ joint.head) for n in moving for r in [rot_r if n in rolling else rot]}
                xf[p.cyl_parent] = (Matrix.Identity(3), Vector())
                q = hits_machined(xf, p.a, span, p.radius, end_skip)
                if q:
                    problems.append(f"{p.name} at {tag} hits {q.bone} (line {q.line})")
        if min(arms) * max(arms) <= 0 or min(abs(a) for a in arms) < PISTON_MIN_ARM:
            problems.append(f"{p.name} crosses its hinge axis: moment arm "
                            f"{min(arms):.3f}..{max(arms):.3f} m over {lo}..{hi} deg")
    if problems:
        raise SystemExit(f"[{NAME}] piston clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


# --------------------------------------------------------------------------------------------
# Mesh kit: rigid parts accumulated into one bmesh, each weighted 1.0 to one bone
# --------------------------------------------------------------------------------------------

@dataclass
class Solid:
    """Collision volume of one rigid part (left side), used to check piston clearance."""
    bone: str
    kind: str  # "box" (half = half extents) or "cyl" (half = (r, r, half length))
    center: Vector
    rot: Matrix
    half: Vector

    def contains(self, center, rot, p, margin):
        q = rot.transposed() @ (p - center)
        if self.kind == "box":
            return all(abs(q[i]) < self.half[i] + margin for i in range(3))
        return abs(q.z) < self.half.z + margin and q.x * q.x + q.y * q.y < (self.half.x + margin) ** 2


def build_line():
    """Line of the build_* call that created a part, for error messages."""
    f = sys._getframe(1)
    while f:
        if f.f_code.co_name.startswith("build_"):
            return f.f_lineno
        f = f.f_back
    return 0


class Part:
    """Exact geometry of one rigid part (left side), for connectivity and alignment checks."""

    def __init__(self, bone, line, verts, faces, convex, solid=True, exact=False):
        self.bone, self.line, self.verts, self.faces, self.convex = bone, line, verts, faces, convex
        self.solid, self.exact = solid, exact
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

    def hits(self, p, margin):
        """Exact test: is point p inside this part or within `margin` of its surface?"""
        if any(p[i] < self.lo[i] - margin or p[i] > self.hi[i] + margin for i in range(3)):
            return False
        dist = self.bvh.find_nearest(p)[3]
        if dist is not None and dist < margin:
            return True
        crossings, origin, ray = 0, p.copy(), Vector((0.0123, 0.0071, 1.0)).normalized()
        while crossings < 64:  # ray parity: odd = inside
            hit = self.bvh.ray_cast(origin, ray)[0]
            if hit is None:
                break
            crossings += 1
            origin = hit + ray * 1e-5
        return crossings % 2 == 1

    def inside(self, p, tol=0.0):
        return self.convex and all(n.dot(p - a) <= tol for n, a in self.planes)

    def buried(self, p):
        """Is p strictly inside this closed part? Convex parts: exact planes. Others: ray parity,
        which two different ray directions must agree on (so a grazing ray can't fake it)."""
        if any(p[i] <= self.lo[i] or p[i] >= self.hi[i] for i in range(3)):
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
        self.tubes = []  # (bone, points, radius) of guard bars, checked across joints
        self.parts = []  # Part per emitted left-side part
        self.axes = []   # (bone, mid, axis, half length) of every cylinder, for joint alignment
        self.bearings = []  # (bone, mid, axis, half length, inscribed radius) of every true cylinder
        self.detail = detail

    def segs(self, n, r=None):
        """Segment count; parts under 1 cm radius (bolts, pins, knuckles) go 4-sided on the
        third-person body, where they read the same and save a lot of triangles."""
        floor = 4 if r is not None and r < 0.01 and self.detail <= 1 else 6
        return max(floor, round(n * self.detail))

    def emit(self, tmp, bone, mat, mirror, convex=True, solid=True, exact=False, mats=None):
        tmp.verts.index_update()
        faces = [[v.index for v in f.verts] for f in tmp.faces]
        self.parts.append(Part(bone, build_line(), [v.co.copy() for v in tmp.verts], faces, convex, solid, exact))
        if mirror and not bone.startswith("Left"):  # centre bone: its mirrored copy is on the same bone
            self.parts.append(Part(bone, build_line(), [mirror_vec(v.co) for v in tmp.verts],
                                   [f[::-1] for f in faces], convex, solid, exact))
        for flip in ((False, True) if mirror else (False,)):
            name = mirror_name(bone) if flip else bone
            if name not in self.groups:
                self.groups.append(name)
            group = self.groups.index(name)
            vmap = {}
            for v in tmp.verts:
                co = mirror_vec(v.co) if flip else v.co.copy()
                nv = self.bm.verts.new(co)
                nv[self.deform][group] = 1.0
                vmap[v] = nv
            for fi, f in enumerate(tmp.faces):
                verts = [vmap[v] for v in f.verts]
                if flip:
                    verts.reverse()
                self.bm.faces.new(verts).material_index = SLOTS.index(mats[fi] if mats else mat)
        tmp.free()

    def obox(self, p0, p1, w, h, up, bone, mat, bevel=0.0, mirror=True, solid=True):
        """Straight box from p0 to p1; `h` along `up`, `w` across (limbs never taper).
        solid=False for mounts/lugs that pistons are meant to touch."""
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
                            segments=1 if self.detail <= 1 else 2, profile=0.5, affect="EDGES",
                            clamp_overlap=True)
        rot, center = Matrix((W, U, L)).transposed(), (p0 + p1) / 2
        for v in tmp.verts:
            v.co = rot @ v.co + center
        if solid:
            half = Vector((w / 2, h / 2, length / 2))
            self.solids.append(Solid(bone, "box", center, rot, half))
        self.emit(tmp, bone, mat, mirror, solid=solid)

    def box(self, center, size, bone, mat, **kw):
        c, hz = Vector(center), Vector((0, 0, size[2] / 2))
        self.obox(c - hz, c + hz, size[0], size[1], BACK, bone, mat, **kw)

    def cyl(self, p0, p1, r, bone, mat, segs=8, r1=None, mirror=True, solid=True):
        p0, p1 = Vector(p0), Vector(p1)
        tmp = bmesh.new()
        bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=False, segments=self.segs(segs, max(r, r1 or r)),
                              radius1=r, radius2=r if r1 is None else r1, depth=(p1 - p0).length)
        rot, mid = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix(), (p0 + p1) / 2
        for v in tmp.verts:
            v.co = rot @ v.co + mid
        if solid:
            rmax = max(r, r if r1 is None else r1)
            self.solids.append(Solid(bone, "cyl", mid, rot, Vector((rmax, rmax, (p1 - p0).length / 2))))
        self.axes.append((bone, mid, (p1 - p0).normalized(), (p1 - p0).length / 2))
        if r1 is None:  # inscribed radius of the n-gon: what stays covered at any angle about its axis
            n = self.segs(segs, r)
            ax = (p1 - p0).normalized()
            self.bearings.append((bone, mid, ax, (p1 - p0).length / 2, r * math.cos(math.pi / n)))
            if mirror and not bone.startswith("Left"):
                self.bearings.append((bone, mirror_vec(mid), mirror_vec(ax), (p1 - p0).length / 2,
                                      r * math.cos(math.pi / n)))
        self.emit(tmp, bone, mat, mirror, solid=solid)

    def sphere(self, center, r, bone, mat, mirror=True):
        """Low-poly ball: ball joints and rod-end bearings (a small bearing ball gets one ring fewer)."""
        tmp = bmesh.new()
        bmesh.ops.create_uvsphere(tmp, u_segments=self.segs(6), v_segments=3 if r < 0.015 and self.detail <= 1 else 4,
                                  radius=r)
        for v in tmp.verts:
            v.co += Vector(center)
        self.emit(tmp, bone, mat, mirror, solid=False)

    def prism(self, points, thickness, normal, bone, mat, mirror=True):
        """Flat plate (gussets, brackets): coplanar polygon extruded by `thickness` along `normal`."""
        n = Vector(normal).normalized() * (thickness / 2)
        tmp = bmesh.new()
        bot = [tmp.verts.new(Vector(p) - n) for p in points]
        top = [tmp.verts.new(Vector(p) + n) for p in points]
        tmp.faces.new(top)
        tmp.faces.new(bot[::-1])
        for i in range(len(points)):
            j = (i + 1) % len(points)
            tmp.faces.new((bot[i], bot[j], top[j], top[i]))
        self.emit(tmp, bone, mat, mirror, exact=True)

    def plate(self, outline, thickness, normal, bone, mat, holes=(), cuts=(), boxes=(), intersect=(),
              mirror=True):
        """Flat plate with through-cut openings (exact boolean difference): wishbones, brackets.
        `holes` are polygons cut straight through; `cuts` are (p0, p1, r) cylinders, e.g. to fit
        armour flush around a motor, with an optional side count; `boxes` are (center, size) blocks
        for pockets and grooves; `intersect` are (points, normal, thickness) profiles the shape is
        intersected with first, carving a solid from two views."""
        n0 = Vector(normal).normalized()

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
            mesh = bpy.data.meshes.new("_slab")
            bm.to_mesh(mesh)
            bm.free()
            obj = bpy.data.objects.new("_slab", mesh)
            bpy.context.scene.collection.objects.link(obj)
            return obj

        def rod(p0, p1, r, segs=16):
            p0, p1 = Vector(p0), Vector(p1)
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=(p1 - p0).length)
            rot = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix()
            for v in bm.verts:
                v.co = rot @ v.co + (p0 + p1) / 2
            mesh = bpy.data.meshes.new("_rod")
            bm.to_mesh(mesh)
            bm.free()
            obj = bpy.data.objects.new("_rod", mesh)
            bpy.context.scene.collection.objects.link(obj)
            return obj

        def block(center, size):
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            for v in bm.verts:
                v.co = Vector(center) + Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
            mesh = bpy.data.meshes.new("_block")
            bm.to_mesh(mesh)
            bm.free()
            obj = bpy.data.objects.new("_block", mesh)
            bpy.context.scene.collection.objects.link(obj)
            return obj

        base = slab(outline, thickness)
        shapers = [slab(pts, th, nrm) for pts, nrm, th in intersect]
        for shaper in shapers:
            mod = base.modifiers.new("shape", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", shaper
        cutters = ([slab(h, thickness * 3) for h in holes] + [rod(*c) for c in cuts]
                   + [block(*b) for b in boxes])
        for cutter in cutters:
            mod = base.modifiers.new("cut", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
        tmp = bmesh.new()
        tmp.from_object(base, bpy.context.evaluated_depsgraph_get())
        for obj in (base, *shapers, *cutters):
            mesh = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(mesh)
        self.emit(tmp, bone, mat, mirror, convex=not (holes or cuts or boxes or intersect), exact=True)

    def tube(self, points, r, bone, mat, sides=6, mirror=True, foot_segs=6, bar=True, round_bends=True):
        """Swept tube along a polyline (roll cages, guard bars). Each end must sit on a mounting
        surface with its end segment square to it; it gets a bolted flange foot there. bar=False
        sweeps a plain wire (a coil spring): no flange feet, not held to the bar rules. A bar's sharp
        bends (over 45 degrees) are rounded a little (user: no pointy corners on handles): each corner
        point becomes two, set back along either leg, so the bend turns in two half-steps."""
        pts = [Vector(p) for p in points]
        if bar and round_bends:  # (a hose is a free curve already)
            rounded = [pts[0]]
            for a, p, b in zip(pts, pts[1:], pts[2:]):
                d0, d1 = (p - a).normalized(), (b - p).normalized()
                if d0.angle(d1) > math.radians(45):
                    c = min(1.5 * r, 0.35 * (p - a).length, 0.35 * (b - p).length)
                    rounded += [p - d0 * c, p + d1 * c]
                else:
                    rounded.append(p)
            pts = rounded + [pts[-1]]
        # plain wires under 1 cm may go 4-sided; on the body a smaller count asked for is kept (hoses: 5)
        sides = sides if sides < 6 and self.detail <= 1 else self.segs(sides, None if bar else r)
        tmp = bmesh.new()
        dirs = [(b - a).normalized() for a, b in zip(pts, pts[1:])]
        ref = Vector((0, 0, 1)) if abs(dirs[0].z) < 0.9 else Vector((1, 0, 0))
        normals = [(ref - dirs[0] * ref.dot(dirs[0])).normalized()]
        for d0, d1 in zip(dirs, dirs[1:]):  # carry the section frame round each bend (no twist)
            normals.append(d0.rotation_difference(d1) @ normals[-1])
        rings = []
        for i, p in enumerate(pts):
            d_in, n = (dirs[i - 1], normals[i - 1]) if i > 0 else (dirs[0], normals[0])
            b = d_in.cross(n)
            offsets = [(n * math.cos(a) + b * math.sin(a)) * r for a in (2 * math.pi * j / sides for j in range(sides))]
            if 0 < i < len(pts) - 1:  # true mitre: cut the incoming tube on the bisector plane
                t = (dirs[i - 1] + dirs[i]).normalized()
                offsets = [o - d_in * (o.dot(t) / d_in.dot(t)) for o in offsets]
            rings.append([tmp.verts.new(p + o) for o in offsets])
        for r0, r1 in zip(rings, rings[1:]):
            for j in range(sides):
                tmp.faces.new((r0[j], r0[(j + 1) % sides], r1[(j + 1) % sides], r1[j]))
        tmp.faces.new(rings[0][::-1])
        tmp.faces.new(rings[-1])
        if bar:
            self.tubes.append((bone, pts, r))
        self.emit(tmp, bone, mat, mirror, convex=False, solid=False)
        for end, nxt in ((pts[0], pts[1]), (pts[-1], pts[-2])) if bar else ():
            t = (nxt - end).normalized()
            self.cyl(end - t * 0.001, end + t * 0.005, r * 1.9, bone, FRM, segs=foot_segs, mirror=mirror, solid=False)

    def optimise(self, eps=2e-4, joints=()):
        """Lossless triangle reduction, run after the checks:
        1. Cull faces that can never be seen: the whole face, nudged `eps` outward, lies inside
           ONE other part of the same bone. For a convex part that is exact: all of the face's
           vertices inside it put the whole face inside it. For a non-convex part the vertices
           and dense points along every edge (pulled 1% inward) must all be inside it. Parts of
           one bone never move apart, so such a face stays hidden in every pose and animation; a
           face merely covered by another bone's part at rest is kept, since it can show when the
           joint moves. Right-side faces are tested against the mirrored left-side parts.
        Across a single-axis joint (`joints`, from rotary_joints) a face is also culled when it lies
           wholly inside a true cylinder of the other bone that is coaxial with the joint axis:
           within its inscribed radius and its length. Turning about that axis keeps both, so the
           face stays covered at every joint angle (an axle in its bearing, a hub in its boss).
        2. Dissolve what the boolean cuts leave on flat faces (collinear edge vertices, coplanar
           splits), within one material, so flat faces need fewer triangles.
        Returns (culled faces, triangles before, triangles after)."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        before = sum(len(f.verts) - 2 for f in self.bm.faces)
        by_bone = {}
        for part in self.parts:
            by_bone.setdefault(part.bone, []).append(part)
        coax = {}  # bone -> bearings of the bones it turns against, coaxial with that joint's axis
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
            flip = bone.startswith("Right")
            parts = by_bone.get(mirror_name(bone) if flip else bone)
            if not parts:
                continue
            c = f.calc_center_median()
            ring = [v.co.lerp(c, 0.01) for v in f.verts]
            corners = [q + f.normal * eps for q in ring]
            edges = [a.lerp(b, t) + f.normal * eps for a, b in zip(ring, ring[1:] + ring[:1])
                     for t in (0.2, 0.4, 0.6, 0.8)] + [c + f.normal * eps]
            if flip:
                corners, edges = [mirror_vec(q) for q in corners], [mirror_vec(q) for q in edges]
            lo = Vector(min(q[i] for q in corners) for i in range(3))
            hi = Vector(max(q[i] for q in corners) for i in range(3))
            for part in parts:
                if any(lo[i] < part.lo[i] or hi[i] > part.hi[i] for i in range(3)):
                    continue
                if all(part.buried(q) for q in corners) and (part.convex or all(part.buried(q) for q in edges)):
                    dead.append(f)
                    break
            else:
                for mid, ax, half, r_in in coax.get(mirror_name(bone) if flip else bone, ()):
                    def within(q):
                        d = q - mid
                        t = d.dot(ax)
                        return abs(t) < half - 1e-5 and (d - ax * t).length < r_in - 1e-5
                    if all(within(q) for q in corners):
                        dead.append(f)
                        break
        # Keep shading exact: a culled face must not have been part of a kept neighbour's smooth
        # vertex normal (an edge between them that is neither flat nor hard, see SHARP_ANGLE).
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

    def to_object(self, name, optimise=True, joints=()):
        if optimise:
            culled, before, after = self.optimise(joints=joints)
            print(f"[{NAME}] {name}: {before} -> {after} tris ({culled} hidden faces culled)")
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
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
        mesh.set_sharp_from_angle(angle=SHARP_ANGLE)  # faceted hard-surface, smooth barrels
        return obj


# --------------------------------------------------------------------------------------------
# Parts (left side; mirror=True adds the right side)
# --------------------------------------------------------------------------------------------

def ring(cx, cz, r, y, n=16):
    """Circle polygon in an XZ plane at depth y (or, via plane swap, XY at height y)."""
    return [(cx + r * math.cos(2 * math.pi * i / n), y, cz + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def ring_xy(cx, cy, r, z, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), z)
            for i in range(n)]


# --------------------------------------------------------------------------------------------
# Sculpting: lofted shells carved with exact booleans (the weapons' language). A shell's surface
# takes its paint; every face a cut makes takes the machined colour underneath.
# --------------------------------------------------------------------------------------------

def sym(half):
    """A closed ring symmetric about u = 0 from its half at u >= 0, listed from one end on the axis
    (u = 0) to the other."""
    return list(half) + [(-u, v) for u, v in reversed(half[1:-1])]


def loft(sections):
    """A closed bmesh through rings of 3D points (the same count in each), capped at both ends. Quads
    that come out twisted (non-planar) are split, so no face is left bent."""
    bm = bmesh.new()
    rings = [[bm.verts.new(Vector(p)) for p in r] for r in sections]
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    def bent(f):
        vs = [v.co for v in f.verts]
        n = (vs[1] - vs[0]).cross(vs[2] - vs[0])
        return n.length > 1e-12 and any(abs((q - vs[0]).dot(n.normalized())) > 1e-6 for q in vs[3:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3 and bent(f)])
    return bm


def zloft(stations, half):
    """Horizontal sections: stations [(z, *args)], half(*args) the ring's +x half (x, y), from the front
    centre to the back centre."""
    return loft([[(x, y, z) for x, y in sym(half(*a))] for z, *a in stations])


def axis_loft(origin, axis, side, stations):
    """Sections square to `axis` from `origin`: stations [(t, ring)] with ring points (u, v): u along
    `side`, v along axis x side."""
    o, a, s = Vector(origin), Vector(axis).normalized(), Vector(side).normalized()
    v = a.cross(s)
    return loft([[o + a * t + s * p + v * q for p, q in r] for t, r in stations])


def octo(hu, v0, v1, cb, ct):
    """Half an octagon (u >= 0) from the bottom centre to the top centre: half-width hu, v0..v1,
    corner chamfers cb (bottom) and ct (top)."""
    return [(0.0, v0), (hu - cb, v0), (hu, v0 + cb), (hu, v1 - ct), (hu - ct, v1), (0.0, v1)]


def carve(k, bm, bone, mat, cuts=(), boxes=(), subtract=(), intersect=(), inner=FRM, paint=None, mirror=True,
          solid=True, union=(), difference=()):
    """A closed shell with exact boolean cuts: `union` closed bmeshes fused into it first (fairings: one
    unibody), then `cuts` (p0, p1, r[, sides]) cylinders, `boxes` (center, size) blocks, `subtract` /
    `intersect` (points, normal, thickness) prisms; `difference` accepts closed lofted cutters.
    Faces on the uncut surface take `mat` (or paint(face)
    when given); faces the cuts make take `inner`."""
    verts, polys = [], []
    for b in (bm, *union):
        b.verts.index_update()
        polys += [[v.index + len(verts) for v in f.verts] for f in b.faces]
        verts += [v.co.copy() for v in b.verts]
    surface = BVHTree.FromPolygons(verts, polys)

    def temp(b, name):
        mesh = bpy.data.meshes.new(name)
        b.to_mesh(mesh)
        b.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def slab(points, nrm, th):
        n = Vector(nrm).normalized()
        b = bmesh.new()
        bot = [b.verts.new(Vector(q) - n * th / 2) for q in points]
        top = [b.verts.new(Vector(q) + n * th / 2) for q in points]
        b.faces.new(top)
        b.faces.new(bot[::-1])
        for i in range(len(points)):
            j = (i + 1) % len(points)
            b.faces.new((bot[i], bot[j], top[j], top[i]))
        bmesh.ops.recalc_face_normals(b, faces=b.faces[:])
        return temp(b, "_slab")

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

    if cuts or boxes or subtract or intersect or union or difference:
        base = temp(bm, "_solid")
        fused = [temp(b, "_fuse") for b in union]
        for body in fused:
            mod = base.modifiers.new("fuse", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "UNION", "EXACT", body
        shapers = [slab(*s) for s in intersect]
        for shaper in shapers:
            mod = base.modifiers.new("shape", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", shaper
        cutters = ([rod(*c) for c in cuts] + [block(*b) for b in boxes] + [slab(*s) for s in subtract]
                   + [temp(b, "_profile_cut") for b in difference])
        for cutter in cutters:
            mod = base.modifiers.new("cut", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
        tmp = bmesh.new()
        tmp.from_object(base, bpy.context.evaluated_depsgraph_get())
        for obj in (base, *fused, *shapers, *cutters):
            mesh = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(mesh)
    else:
        tmp = bm
    tmp.normal_update()
    mats = []
    for f in tmp.faces:
        loc, nrm, _, dist = surface.find_nearest(f.calc_center_median())
        on = dist is not None and dist < 1e-5 and nrm.dot(f.normal) > 0.999
        mats.append((paint(f) if paint else mat) if on else inner)
    k.emit(tmp, bone, mat, mirror, convex=False, solid=solid, exact=True, mats=mats)


def hose(k, a, na, b, nb, r, bone, mat, reach=None, sag=0.0, bulge=(0, 0, 0), n=4, mirror=True):
    """A flexible cable or hydraulic line: out of gland `a` square to its face (normal na), in a free
    curve (a cubic through handles `reach` long, sagging and bulging mid-run), into gland `b` square
    to its face (normal nb). Held to the bar rules: both ends on flanges, clear of the body between."""
    a, b, na, nb = Vector(a), Vector(b), Vector(na).normalized(), Vector(nb).normalized()
    h = reach if reach is not None else 0.4 * (b - a).length
    p0, p1, p2, p3 = a + na * 0.008, a + na * (0.008 + h), b + nb * (0.008 + h), b + nb * 0.008
    pts = [a]
    for i in range(n + 1):
        t = i / n
        q = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
        pts.append(q + (Vector((0, 0, -sag)) + Vector(bulge)) * math.sin(math.pi * t))
    pts.append(b)
    k.tube(pts, r, bone, mat, sides=5, mirror=mirror, foot_segs=6, round_bends=False)


def bolt(k, at, normal, bone, r=0.0042, mat=JNT, head=0.003, mirror=True):
    """A bolt head standing `head` proud of a face, its shank sunk 2 mm in."""
    n = Vector(normal).normalized()
    k.cyl(Vector(at) - n * 0.002, Vector(at) + n * head, r, bone, mat, segs=6, solid=False, mirror=mirror)


def slant_slots(c, u, v, n, count, pitch, length, width, lean, depth):
    """`count` slanted vent slots across a face: centred on c, spread along u, each `length` along v
    leaning `lean` along u, `width` wide, cut `depth` into a face of normal n (subtract prisms)."""
    c, u, v, n = Vector(c), Vector(u).normalized(), Vector(v).normalized(), Vector(n).normalized()
    out = []
    for i in range(count):
        m = c + u * (pitch * (i - (count - 1) / 2))
        lo, hi = m - v * length / 2 - u * lean / 2, m + v * length / 2 + u * lean / 2
        out.append(([lo - u * width / 2, lo + u * width / 2, hi + u * width / 2, hi - u * width / 2], tuple(n), 2 * depth))
    return out


# Cables and hydraulic lines. Every run stays on one rigid part: it leaves the part square to a face
# through a gland (the tube's flange foot), runs free in a curve, and dives back in at the other end,
# as if routed on through the hollow joints. Looms in M_Wire and hydraulic lines in M_Hose: their own
# fixed colours, never the frame or a team colour.
CABLE, LINE = (0.0065, WIRE), (0.0055, HOSE)


# --------------------------------------------------------------------------------------------
# Torso: pelvis girdle and crotch keel, spine, abdomen, the chest shield, back pack, lamps, cage
# --------------------------------------------------------------------------------------------

def chest_half(w, yf, yb):
    """The chest shield's section: a keeled front (sternum ridge, pectoral facets), flat flanks and a
    chamfered back."""
    return [(0.0, yf), (0.42 * w, yf + 0.012), (0.74 * w, yf + 0.034), (w, yf + 0.076), (w, yb - 0.045),
            (w - 0.045, yb), (0.0, yb)]


CHEST = ((1.228, 0.066, -0.080, 0.070), (1.28, 0.094, -0.116, 0.094), (1.35, 0.126, -0.138, 0.108),
         (1.435, 0.154, -0.136, 0.110), (1.476, 0.138, -0.114, 0.106), (1.498, 0.122, -0.092, 0.098))


def chest_at(z):
    """(w, yf, yb) of the chest shield at height z (linear between its stations)."""
    for (z0, *a0), (z1, *a1) in zip(CHEST, CHEST[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return tuple(p + (q - p) * t for p, q in zip(a0, a1))
    raise ValueError(z)


COLLAR = (0.0, 180.0, 0.09, (0.102, 0.098), (1.47, 1.496, 1.545))  # the neck collar: its span (deg from +x
# round the back: the back half, user), inner radius, outer radius at its foot and top, its foot, its ends' top
# and its top
LAMP = (0.103, -0.086, 0.018)  # the floodlight pods: x, their front's y, radius (axes on the shield's top)
# The pods' fairing, part of the shield: (y, radius, centre z) from the lens back, full round, then shrinking
# and sinking until it is under the shoulder's top (z CHEST[-1][0]).
LAMP_FAIRING = ((LAMP[1], LAMP[2], 1.498), (-0.05, LAMP[2], 1.498), (-0.03, 0.013, 1.494), (-0.014, 0.008, 1.492),
                (-0.004, 0.004, 1.49))  # (sunk by the neck's axis, where the collar's ends are)


def hull2(pts):
    """Convex hull of 2D points, counter-clockwise."""
    pts = sorted(set(pts))
    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (q[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(q)
        return h
    lo, hi = half(pts), half(pts[::-1])
    return lo[:-1] + hi[:-1]


def strut_lug(k, pin, bone, y0, zlo, zhi, r=0.015, t=0.0055):
    """A strut's clevis: two cheeks either side of the rod-end housing (clearing its ball), each seated on a
    flat at y0 over z zlo..zhi and tapering to a round end of radius r centred on the pin, a web between
    them at the flat."""
    slot = STRUT_EYE_HALF + 0.0025 + 0.0003
    ring_ = [(pin.y + r * math.cos(math.radians(a)), pin.z + r * math.sin(math.radians(a))) for a in range(0, 360, 30)]
    outline = hull2([(y0, zlo), (y0, zhi)] + ring_)
    for sx in (1, -1):
        x = pin.x + sx * (slot + t / 2)
        k.prism([(x, y, z) for y, z in outline], t, (1, 0, 0), bone, FRM)
    k.box((pin.x, y0 + 0.005, (zlo + zhi) / 2), (2 * slot + 0.002, 0.016, zhi - zlo), bone, FRM)  # web


def pelvis_half(w, yf, yb):
    return [(0.0, yf), (0.55 * w, yf + 0.004), (w - 0.022, yf + 0.018), (w, yf + 0.045), (w, yb - 0.028),
            (w - 0.028, yb), (0.0, yb)]


PELVIS = ((0.978, 0.134, -0.08, 0.078), (1.02, 0.1458, -0.0918, 0.08), (1.035, 0.15, -0.096, 0.068),
          (1.074, 0.13, -0.084, 0.056))  # the back chamfered from 1.02, clear of the struts


def build_pelvis(k):
    hip = H
    slot = STRUT_EYE_HALF + 0.0025 + 0.0003  # a strut fork's slot: clears the bearing ball

    # Pelvis: a lofted girdle over the hip drives, pocketed underneath for each hip's yaw motor and
    # fork, with the spine's socket in its top; a keel between the hip forks carries the codpiece.
    pockets = [((sx * hip.x, 0, 0.96), (sx * hip.x, 0, hip.z + 0.103), 0.094, 20) for sx in (1, -1)]  # open hip bays
    carve(k, zloft(PELVIS, pelvis_half), "Hips", PRI, mirror=False, inner=PRI,  # one colour, cuts included
          cuts=pockets + [((0, 0, 1.03), (0, 0, 1.09), 0.044, 16)],
          boxes=[((0, -0.092, 0.984), (0.13, 0.056, hip.z + 0.103 - 0.95))])  # the keel's bay: thighs flex up into it
    for sx in (1, -1):  # hip yaw motors, seated in the pockets' roofs
        k.cyl((sx * hip.x, 0, hip.z + 0.09), (sx * hip.x, 0, hip.z + 0.104), 0.052, "Hips", FRM, segs=14, mirror=False)
    keel = ((0.874, 0.016, -0.062, 0.05), (0.93, 0.024, -0.084, 0.062), (1.024, 0.026, -0.088, 0.068))
    carve(k, zloft(keel, lambda w, yf, yb: [(0.0, yf), (w, yf + 0.024), (w, yb - 0.01), (0.0, yb)]),
          "Hips", PRI, mirror=False)
    # Strut clevis: a short lug on the girdle's flat back face, round-ended on the cross pin.
    ax, ay, az = STRUT_A
    strut_lug(k, Vector(STRUT_A), "Hips", 0.074, az - 0.015, az + 0.015)
    k.cyl((ax - 0.02, ay, az), (ax + 0.02, ay, az), 0.004, "Hips", JNT, solid=False)  # cross pin

def build_upper_body(k, variant="default"):
    # Spine: a ball in the girdle's socket, a stainless steel column with titanium vertebra discs, and a
    # second ball under the abdomen block.
    k.sphere((0, 0, 1.055), 0.036, "Spine", JNT, mirror=False)
    k.cyl((0, 0, 1.05), (0, 0, 1.17), 0.024, "Spine", JNT, segs=10, mirror=False)
    for z0 in (1.099, 1.117):
        k.cyl((0, 0, z0), (0, 0, z0 + 0.01), 0.042, "Spine", TIT, segs=12, mirror=False)
    k.cyl((0, 0, 1.132), (0, 0, 1.141), 0.036, "Spine", FRM, segs=12, mirror=False)
    k.sphere((0, 0, 1.165), 0.03, "Chest", JNT, mirror=False)
    # Abdomen: a lofted block, plain, its back carrying the upper strut clevis.
    abd = ((1.152, 0.072, -0.062, 0.068), (1.175, 0.086, -0.076, 0.078), (1.195, 0.08, -0.07, 0.072))
    carve(k, zloft(abd, lambda w, yf, yb: [(0.0, yf), (0.6 * w, yf + 0.006), (w, yf + 0.03), (w, yb - 0.02),
                                            (w - 0.02, yb), (0.0, yb)]),
          "Chest", PRI, mirror=False)
    k.cyl((0, 0, 1.19), (0, 0, 1.242), 0.04, "Chest", TIT, segs=12, mirror=False)  # socket cup for the chest's ball
    k.sphere((0, 0, J["upper_chest"].z), 0.03, "UpperChest", JNT, mirror=False)  # in the cup, up into the shield
    bx, by, bz = STRUT_B
    strut_lug(k, Vector(STRUT_B), "Chest", 0.068, 1.177, 1.193, r=0.013)  # the upper clevis, on the abdomen's back flat
    k.cyl((bx - 0.02, by, bz), (bx + 0.02, by, bz), 0.004, "Chest", JNT, solid=False)

    if variant != "default":
        build_upper_shell(k, variant)
        return

    # Chest shield: a keeled, faceted shell from the narrow waist to the shoulders. Round sockets in
    # its flanks seat the shoulder motors, a well in its top the neck's turntable; a hexagonal intake
    # and a number plate are recessed in the front, slanted vents in the flanks under the sockets.
    c = S
    sockets = [((sx * 0.074, 0, c.z), (sx * 0.25, 0, c.z), 0.076, 20) for sx in (1, -1)]
    intake = [(0.046 * math.cos(math.radians(a)), -0.124, 1.318 + 0.036 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    vents = []
    for sx in (1, -1):
        w, yf, yb = chest_at(1.303)
        (za, wa, *_), (zc, wc, *_) = CHEST[1], CHEST[2]
        up, nrm = Vector((sx * (wc - wa), 0, zc - za)).normalized(), Vector((sx * (zc - za), 0, wa - wc)).normalized()
        vents += slant_slots((sx * w, 0.0, 1.303), (0, 1, 0), up, nrm, 4, 0.018, 0.04, 0.005, 0.012, 0.007)
    pods = [loft([[(sx * LAMP[0] + r * math.cos(math.radians(a)), y, zc + r * math.sin(math.radians(a)))
                   for a in range(0, 360, 30)] for y, r, zc in LAMP_FAIRING]) for sx in (1, -1)]
    # The neck collar (user: the original model's): a half circle round the back of the neck, rising out
    # of the shoulders' top and fused into the shield, full height but for its last fifth each side, where
    # it eases flush into the top; its inner face clears the head hydraulics' swing (their clevises reach
    # 84 mm from the neck's axis at full yaw).
    a0, a1, r_in, (r_bot, r_top), (z_bot, z_end, z_top) = COLLAR

    def collar_section(a):
        u = min(1.0, min(a - a0, a1 - a) / (0.2 * (a1 - a0)))
        zt = z_end + (z_top - z_end) * u * u * (3 - 2 * u)  # eased flush at the ends
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        return [(r * c, r * s_, z) for r, z in ((r_in, z_bot), (r_bot, z_bot), (r_top, zt), (r_in, zt))]
    collar = loft([collar_section(a0 + (a1 - a0) * i / 12) for i in range(13)])
    carve(k, zloft(CHEST, chest_half), "UpperChest", PRI, mirror=False, union=pods + [collar],
          cuts=sockets + [((0, 0, 1.425), (0, 0, 1.52), 0.082, 20), ((0, 0, 1.21), (0, 0, 1.262), 0.058, 16)],
          boxes=[((0, -0.131, 1.418), (0.07, 0.012, 0.036))],                       # number plate recess
          subtract=[(intake, (0, 1, 0), 0.036)] + vents)
    for sx in (1, -1):  # floodlights: the pods' steel bezels and lenses
        lx, lz = sx * LAMP[0], CHEST[-1][0]
        k.cyl((lx, LAMP[1] + 0.001, lz), (lx, LAMP[1] - 0.005, lz), LAMP[2] + 0.0015, "UpperChest", JNT, segs=12,
              mirror=False)
        k.cyl((lx, LAMP[1] - 0.005, lz), (lx, LAMP[1] - 0.006, lz), LAMP[2] - 0.004, "UpperChest", EMI, segs=12,
              mirror=False)
    k.box((0, -0.1235, 1.418), (0.062, 0.006, 0.028), "UpperChest", SEC, mirror=False)  # unit number plate
    for sx in (1,-1):
        bolt(k,(sx*.024,-.1265,1.418),FWD,"UpperChest",r=.0025,head=.0012,mirror=False)
    for ix in range(4):  # louvres across the intake, slanted down
        z = 1.302 + ix * 0.011
        k.obox((-0.03, -0.108, z), (0.03, -0.108, z), 0.012, 0.0025, (0, 0.6, 0.8), "UpperChest", FRM, mirror=False)
    # The neck bearing at the bottom of the well.
    k.cyl((0, 0, J["neck"].z - 0.02), (0, 0, J["neck"].z), 0.048, "UpperChest", TIT, segs=14, mirror=False)

    # Back pack: power unit bolted to the shield's back (two bolts high on its back flat), finned heat-sink
    # grooves; two bearing caps on top and a grab handle across its back.
    pack = ((1.262, 0.08, 0.162), (1.30, 0.108, 0.19), (1.43, 0.112, 0.19), (1.468, 0.094, 0.172))
    fins = [((0, 0.19, z), (0.15, 0.014, 0.006)) for z in (1.312, 1.326, 1.34, 1.354, 1.368)]
    carve(k, zloft(pack, lambda w, yb: [(0.0, 0.08), (w, 0.08), (w, yb - 0.022), (w - 0.022, yb), (0.0, yb)]),
          "UpperChest", PRI, mirror=False, boxes=fins)
    for sx in (1, -1):
        bolt(k, (sx * 0.075, 0.19, 1.418), BACK, "UpperChest", mirror=False)
    for sx in (1, -1):  # bearing caps on the pack's top flat, inboard of the power trunks
        k.cyl((sx * 0.028, 0.15, 1.462), (sx * 0.028, 0.15, 1.474), 0.018, "UpperChest", TIT, segs=12, mirror=False)
        k.cyl((sx * 0.028, 0.15, 1.474), (sx * 0.028, 0.15, 1.478), 0.012, "UpperChest", BRZ, segs=10, mirror=False)
    hx, (_, hy, hz) = GRAB_HANDLE[0], FLAG_MOUNT
    k.tube([(hx, 0.19, hz), (hx, hy, hz), (-hx, hy, hz), (-hx, 0.19, hz)], GRAB_HANDLE[1],
           "UpperChest", SEC, mirror=False)  # grab handle (a carried flag hooks onto its bar: FlagMount)

    # Roll cage: a bar from flanges on the shield's upper front, down the pectoral facets inboard of the
    # arms' forward sweep, meeting in a loop before the waist. Standoff posts hold it off the facets.
    def facet(z, off, f=0.58):
        """A point on the pectoral facet (between its 0.42 and 0.74 breaks) at fraction f, `off` out."""
        w, yf, yb = chest_at(z)
        p0, p1 = Vector((0.42 * w, yf + 0.012)), Vector((0.74 * w, yf + 0.034))
        d = (p1 - p0).normalized()
        q = p0.lerp(p1, (f - 0.42) / 0.32) + Vector((d.y, -d.x)) * off
        return Vector((q.x, q.y, z))
    top = facet(1.465, 0.0)
    along = facet(1.465, 0.0, 0.66) - facet(1.465, 0.0, 0.5)
    nrm = along.cross(facet(1.47, 0.0) - facet(1.46, 0.0)).normalized()
    nrm = nrm if nrm.y < 0 else -nrm            # the facet's true normal: it leans back toward the top
    cage = [top, top + nrm * 0.024, facet(1.435, 0.026), facet(1.36, 0.026), facet(1.30, 0.026, 0.5),
            Vector((0.03, -0.148, 1.262)), Vector((0.0, -0.148, 1.262))]
    k.tube(cage + [Vector((-p.x, p.y, p.z)) for p in reversed(cage[:-1])], 0.0095, "UpperChest", SEC, mirror=False,
           round_bends=False)  # (its bends are gentle)
    for z, f in ((1.36, 0.58), (1.30, 0.5)):
        p, q = facet(z, 0.0, f), facet(z, 0.026, f)
        k.cyl(p - (q - p).normalized() * 0.01, q, 0.005, "UpperChest", FRM, segs=6, solid=False)

    # Power trunks: out of the pack's top, over into the shield's back, a loom and a hydraulic line
    # per side, in free curves.
    for (r, mat), x in ((CABLE, 0.074), (LINE, 0.058)):
        w, yf, yb = chest_at(1.488)
        (za, _, _, ya), (zc, _, _, yc) = CHEST[-2], CHEST[-1]
        hose(k, (x, 0.132, pack[-1][0]), UP, (x, yb, 1.488), (0, zc - za, ya - yc), r, "UpperChest", mat, reach=0.016)


UPPER_BODY_VARIANTS = ("default", "aegis", "lamellar", "vesper", "conduit", "reactor")
UPPER_BODY_BUDGET = 4_500


def upper_body_mesh_name(variant):
    return f"SK_{NAME.capitalize()}UpperBody{variant.capitalize()}"


def build_torso(k, variant="default"):
    build_pelvis(k)
    build_upper_body(k, variant)


def offset_outline(outline, margin):
    """Offset a convex CCW XZ footprint by an exact perpendicular margin."""
    result = []
    for i, point in enumerate(outline):
        p, a, b = Vector(point), Vector(outline[i-1]), Vector(outline[(i+1) % len(outline)])
        u, v = (p-a).normalized(), (b-p).normalized()
        n, m = Vector((u.y, -u.x)), Vector((v.y, -v.x))
        result.append(tuple(p + (n+m) * (margin / (1+n.dot(m)))))
    return result


def shell_patch(surface, outline, outer=0.0025, inner=-0.003, outward=-1):
    """A closed cover or pocket that retains every underlying loft facet.

    Clip the actual shell triangles in XZ, then offset their two skins in Y.
    The mating floor is identical to the cover's back; a separate expanded
    footprint defines the perimeter clearance. No flat plate crosses the shell.
    """
    patch = bmesh.new()
    for face in surface.faces:
        if face.normal.y * outward < 0.05:
            continue
        polygon = [v.co.copy() for v in face.verts]
        for a, b in zip(outline, outline[1:]+outline[:1]):
            def signed(p):
                return (b[0]-a[0])*(p.z-a[1]) - (b[1]-a[1])*(p.x-a[0])
            clipped = []
            for p, q in zip(polygon, polygon[1:]+polygon[:1]):
                dp, dq = signed(p), signed(q)
                if dp >= -1e-10: clipped.append(p)
                if (dp >= -1e-10) != (dq >= -1e-10):
                    clipped.append(p.lerp(q, dp/(dp-dq)))
            polygon = clipped
            if len(polygon) < 3: break
        if len(polygon) >= 3:
            verts = [patch.verts.new(p) for p in polygon]
            patch.faces.new(verts)
    if not patch.faces:
        raise ValueError("Service cover has no supporting shell surface")
    bmesh.ops.remove_doubles(patch, verts=patch.verts[:], dist=1e-6)
    bmesh.ops.dissolve_degenerate(patch, edges=patch.edges[:], dist=1e-6)
    slivers = [f for f in patch.faces if f.calc_area()<1e-9]
    if slivers: bmesh.ops.delete(patch, geom=slivers, context="FACES")
    loose = [e for e in patch.edges if not e.link_faces]
    if loose: bmesh.ops.delete(patch, geom=loose, context="EDGES")
    patch.verts.index_update()
    boundary = [(e.verts[0].index,e.verts[1].index) for e in patch.edges if len(e.link_faces)==1]
    result = bmesh.new()
    front, back = [], []
    for v in patch.verts:
        front.append(result.verts.new(v.co + Vector((0,outward*outer,0))))
        back.append(result.verts.new(v.co + Vector((0,outward*inner,0))))
    for f in patch.faces:
        result.faces.new([front[v.index] for v in f.verts])
        result.faces.new([back[v.index] for v in reversed(f.verts)])
    for a,b in boundary:
        result.faces.new((front[a],front[b],back[b],back[a]))
    patch.free()
    bmesh.ops.recalc_face_normals(result, faces=result.faces[:])
    if any(len(e.link_faces)!=2 for e in result.edges):
        raise ValueError("Fitted panel is not a closed two-manifold solid")
    return result


def shell_point(surface, x, z, outward=-1):
    """Point and true facet normal for a fastener wholly inside its mounting land."""
    hits = []
    for f in surface.faces:
        if f.normal.y*outward < 0.05: continue
        p = Vector((x,0,z))
        p.y = -f.normal.dot(p-f.verts[0].co)/f.normal.y
        # Barycentric inclusion, independent of the front/back triangle winding.
        a,b,c = [v.co for v in f.verts]
        u,v,w = b-a,c-a,p-a
        uu,uv,vv,wu,wv = u.dot(u),u.dot(v),v.dot(v),w.dot(u),w.dot(v)
        det = uu*vv-uv*uv
        if abs(det)<1e-18: continue
        s,t = (wu*vv-wv*uv)/det,(wv*uu-wu*uv)/det
        if s>=-1e-7 and t>=-1e-7 and s+t<=1+1e-7:
            hits.append((p,f.normal.copy()))
    if not hits: raise ValueError(f"Fastener has no mounting facet at {(x,z)}")
    return max(hits,key=lambda hit:hit[0].y*outward)


def build_upper_shell(k, variant):
    """Interchangeable castings on the native waist cup, shoulder drives and neck bearing.

    All service equipment stays on UpperChest. The exposed Spine and Chest retain
    their own rigid weights; hoses never bridge moving bones.
    """
    bone = "UpperChest"
    sockets = [((sx * 0.074, 0, S.z), (sx * 0.25, 0, S.z), 0.076, 20) for sx in (1, -1)]
    cuts = sockets + [((0, 0, 1.425), (0, 0, 1.52), 0.082, 20),
                      ((0, 0, 1.21), (0, 0, 1.262), 0.058, 16)]
    boxes = []
    profile = chest_half
    # Broad planar faces are deliberate mounting lands; the outer shoulder and
    # neck stations retain the validated joint envelope.
    stations = list(CHEST)
    if variant == "aegis":
        stations[1:4] = [(1.28, 0.094, -0.116, 0.094), (1.35, 0.126, -0.138, 0.108),
                         (1.435, 0.154, -0.136, 0.110)]
    elif variant == "lamellar":
        stations[1:3] = [(1.28, 0.082, -0.116, 0.094), (1.35, 0.111, -0.138, 0.108)]
        # Machined horizontal reliefs leave a continuous rear shear wall and
        # central load spine. Four overlapping breast courses read as ribs.
        for z, width in ((1.277, 0.13), (1.315, 0.17), (1.353, 0.20), (1.391, 0.21)):
            boxes.append(((0, -0.119, z), (width, 0.078, 0.012)))
    elif variant == "vesper":
        stations[1:4] = [(1.28, 0.094, -0.116, 0.094), (1.35, 0.126, -0.138, 0.108),
                         (1.435, 0.154, -0.136, 0.110)]
        boxes = [((0, -0.132, 1.34), (0.041, 0.124, 0.17))]
        cuts += [((sx*.065,.14,1.275),(sx*.065,.14,1.46),.0343,10) for sx in (1,-1)]
        # Two sculpted pectoral lobes with a recessed centre channel, rather
        # than a single shield carrying decorative pads.
        def profile(w, yf, yb):
            return [(0,yf+0.070),(0.22*w,yf+0.070),(0.42*w,yf+0.014),
                    (0.74*w,yf+0.034),(w,yf+0.076),(w,yb-0.045),(w-0.045,yb),(0,yb)]
    elif variant == "conduit":
        stations[1:3] = [(1.28, 0.078, -0.116, 0.094), (1.35, 0.103, -0.138, 0.108)]
        # Two deep inspection windows expose the bolted power manifold. A
        # clavicular yoke, central keel and side rails carry the shoulder loads.
        boxes = [((sx * 0.062, -0.055, 1.335), (0.057, 0.24, 0.139)) for sx in (1, -1)]
    elif variant == "reactor":
        stations[3] = (1.435, 0.128, -0.136, 0.110)
        cuts.append(((0, -0.20, 1.355), (0, -0.063, 1.355), 0.066, 20))

    shell = zloft(stations, profile)
    surface = shell.copy()
    bmesh.ops.triangulate(surface, faces=surface.faces[:])
    surface.normal_update()
    covers = []
    if variant == "aegis":
        covers.append(([( -.042,1.434),(.042,1.434),(.059,1.455),(.047,1.474),
                         (-.047,1.474),(-.059,1.455)], [(-.034,1.455),(.034,1.455)], [], -1))
        covers.append(([(-.010,1.313),(.010,1.313),(.017,1.32),(.017,1.40),
                        (.010,1.407),(-.010,1.407),(-.017,1.40),(-.017,1.32)],
                       [(.008,1.322),(-.008,1.399)], [], -1))
    elif variant == "lamellar":
        covers.append(([(-.006,1.29),(.006,1.29),(.012,1.30),(.015,1.421),
                        (.009,1.445),(-.009,1.445),(-.015,1.421),(-.012,1.30)],
                       [(.006,1.31),(-.006,1.43)], [], -1))
        covers.append(([(-.012,1.284),(.012,1.284),(.013,1.44),(-.013,1.44)],
                       [(.006,1.30),(-.006,1.432)], [], 1))
    elif variant == "conduit":
        covers.append(([(-.009,1.274),(.009,1.274),(.018,1.287),(.019,1.41),
                        (.012,1.431),(-.012,1.431),(-.019,1.41),(-.018,1.287)],
                       [(.008,1.286),(-.009,1.354),(.008,1.418)], [], -1))
        covers.append(([(-.013,1.29),(.013,1.29),(.019,1.44),(-.019,1.44)],
                       [(.007,1.30),(-.008,1.43)], [], 1))
    elif variant == "vesper":
        covers.append(([(-.010,1.275),(.010,1.275),(.012,1.402),(-.012,1.402)],
                       [(.005,1.287),(-.005,1.39)], [], -1))
        def width(z):
            for (za,wa,*_), (zb,wb,*_) in zip(stations,stations[1:]):
                if za <= z <= zb: return wa+(wb-wa)*(z-za)/(zb-za)
            raise ValueError(z)
        outline = [(width(z)*fraction+offset,z) for z,fraction,offset in
                   ((1.345,.42,.004),(1.345,.74,-.004),(1.42,.74,-.004),(1.42,.42,.004))]
        slots = [[(width(z)*fraction,z) for z,fraction in
                  ((center-.0025,.49),(center-.0025,.67),(center+.0025,.67),(center+.0025,.49))]
                 for center in (1.37,1.385,1.40)]
        for sx in (1,-1):
            def side(points):
                p = [(sx*x,z) for x,z in points]
                return p if sx==1 else p[::-1]
            covers.append((side(outline), [(sx*width(z)*.58,z) for z in (1.354,1.413)],
                           [side(slot) for slot in slots], -1))
    pockets = []
    for outline, fasteners, slots, outward in covers:
        pockets.append(shell_patch(surface,offset_outline(outline,.0007),outer=.018,inner=-.003,outward=outward))
        for slot in slots:
            pockets.append(shell_patch(surface,slot,outer=.018,inner=-.012,outward=outward))
    carve(k, shell, bone, PRI, mirror=False, cuts=cuts, boxes=boxes, difference=pockets)
    for index,(outline, fasteners, slots, outward) in enumerate(covers):
        cover = shell_patch(surface,outline,outward=outward)
        openings = [shell_patch(surface,slot,outer=.015,inner=-.008,outward=outward) for slot in slots]
        mat = FRM if variant=="aegis" and index==1 else SEC
        carve(k,cover,bone,mat,mirror=False,difference=openings)
        for x,z in fasteners:
            point,normal = shell_point(surface,x,z,outward)
            point.y += outward*.0025
            bolt(k,point,normal,bone,r=.0023,head=.0013,mirror=False)
    k.cyl((0, 0, J["neck"].z - 0.02), (0, 0, J["neck"].z), 0.048, bone, TIT, segs=14, mirror=False)

    def mirrored_outline(points, sx):
        return [(sx*x,z) for x,z in (points if sx==1 else points[::-1])]

    def back_module(outline, depth, mat=PRI, grooves=(), bores=(), fasteners=()):
        """A casting seated on the shell's actual back, with integral machined fins."""
        module = shell_patch(surface,outline,outer=depth,inner=0,outward=1)
        channels = [shell_patch(surface,slot,outer=depth+.01,inner=depth-.009,outward=1)
                    for slot in grooves]
        carve(k,module,bone,mat,mirror=False,difference=channels,cuts=bores,inner=TIT)
        for x,z in fasteners:
            point,normal = shell_point(surface,x,z,1)
            point.y += depth
            bolt(k,point,normal,bone,r=.0026,head=.0015,mirror=False)

    if variant == "aegis":
        # Status windows share the keel's facets and sit on their fitted bezel.
        for z in (1.335, 1.352, 1.369, 1.386):
            window = [(-.008,z-.002),(.008,z-.002),(.008,z+.002),(-.008,z+.002)]
            carve(k,shell_patch(surface,window,outer=.0035,inner=.0025),bone,EMI,mirror=False)
        footprint = [(-.065,1.28),(.065,1.28),(.093,1.31),(.093,1.44),(.065,1.475),(-.065,1.475),(-.093,1.44),(-.093,1.31)]
        grooves = [[(-.057,z-.003),(.057,z-.003),(.057,z+.003),(-.057,z+.003)] for z in (1.32,1.337,1.354)]
        back_module(footprint,.057,grooves=grooves,fasteners=[(-.056,1.418),(.056,1.418)])
    elif variant == "lamellar":
        for z in (1.30, 1.338, 1.376):
            for sx in (1, -1):
                w = next(wa+(wb-wa)*(z-za)/(zb-za) for (za,wa,*_), (zb,wb,*_) in zip(stations,stations[1:]) if za<=z<=zb)
                point,normal = shell_point(surface,sx*w*.58,z)
                bolt(k,point,normal,bone,r=.003,mirror=False)
        # Radiator castings follow the taper of the back. Cooling channels are
        # machined into the castings, leaving a continuous supported root.
        for sx in (1, -1):
            footprint = mirrored_outline([(.035,1.28),(.09,1.28),(.102,1.35),(.09,1.45),(.035,1.45)],sx)
            grooves = [mirrored_outline([(.043,z-.0035),(.087,z-.0035),(.087,z+.0035),(.043,z+.0035)],sx)
                       for z in (1.31,1.33,1.35,1.37,1.39,1.41,1.43)]
            back_module(footprint,.055,grooves=grooves,fasteners=[(sx*.062,1.291),(sx*.062,1.442)])
    elif variant == "vesper":
        # Two large removable pectoral cartridges flank a recessed sternum bus.
        for sx in (1,-1):
            # Shaped saddles have a bored seat for the two annular clamp bands.
            footprint = mirrored_outline([(.033,1.294),(.086,1.294),(.099,1.35),(.096,1.442),(.033,1.442)],sx)
            back_module(footprint,.035,bores=[((sx*.065,.14,1.28),(sx*.065,.14,1.455),.037,10)])
            k.cyl((sx*0.065,0.14,1.285),(sx*0.065,0.14,1.447),0.034,bone,PRI,segs=10,mirror=False)
            for z in (1.306,1.418):
                band = loft([ring_xy(sx*.065,.14,.037,zz,n=10) for zz in (z,z+.012)])
                carve(k,band,bone,SEC,mirror=False,inner=SEC,
                      cuts=[((sx*.065,.14,z-.001),(sx*.065,.14,z+.013),.034,10)])
    elif variant == "conduit":
        # Exposed vertical collector pipes terminate in manifold blocks inside
        # the windows. Short wire loops route around the replaceable modules.
        for sx in (1,-1):
            for z in (1.28,1.40):
                block = loft([[(sx*x,y,zz) for x,y in ((0.025,-0.091),(0.094,-0.091),
                                (0.094,-0.013),(0.025,-0.013))] for zz in (z-0.013,z+0.013)])
                carve(k,block,bone,TIT,mirror=False,cuts=sockets)
            for x in (0.041,0.058):
                k.cyl((sx*x,-0.058,1.285),(sx*x,-0.058,1.395),0.0065,bone,BRZ,segs=8,mirror=False)
            hose(k,(sx*0.058,-0.091,1.40),FWD,(sx*0.058,-0.091,1.28),FWD,
                 0.005,bone,WIRE,reach=0.028,bulge=(sx*0.008,0,0),mirror=False)
            footprint = mirrored_outline([(.071,1.29),(.087,1.29),(.101,1.35),(.099,1.445),(.071,1.445)],sx)
            back_module(footprint,.035,fasteners=[(sx*.084,z) for z in (1.31,1.35,1.39,1.43)])
    elif variant == "reactor":
        # A recessed radial heat exchanger: dark socket, steel rotor plate,
        # discrete luminous coolant passages and a painted bolted hub.
        k.cyl((0,-0.061,1.355),(0,-0.078,1.355),0.063,bone,FRM,segs=20,mirror=False)
        k.cyl((0,-0.078,1.355),(0,-0.084,1.355),0.049,bone,TIT,segs=20,mirror=False)
        for i in range(12):
            a = i*math.tau/12
            p = Vector((0.024*math.cos(a),-0.086,1.355+0.024*math.sin(a)))
            q = Vector((0.044*math.cos(a),-0.086,1.355+0.044*math.sin(a)))
            k.obox(p,q,0.004,0.004,(0,1,0),bone,EMI,mirror=False)
        k.cyl((0,-0.083,1.355),(0,-0.095,1.355),0.019,bone,SEC,segs=12,mirror=False)
        bolt(k,(0,-0.096,1.355),FWD,bone,r=0.007,mirror=False)
        # Rear cassette and protective rails retain the back's native facets.
        footprint = [(-.05,1.285),(.05,1.285),(.067,1.35),(.06,1.445),(-.06,1.445),(-.067,1.35)]
        grooves = [[(-.044,z-.0035),(.044,z-.0035),(.044,z+.0035),(-.044,z+.0035)]
                   for z in (1.31,1.334,1.358,1.382,1.406,1.43)]
        back_module(footprint,.07,grooves=grooves)
        for sx in (1,-1):
            rail = mirrored_outline([(.071,1.29),(.087,1.29),(.096,1.35),(.091,1.455),(.071,1.455)],sx)
            back_module(rail,.05,SEC,fasteners=[(sx*.08,1.303),(sx*.08,1.44)])

    # Native carried-flag interface on a bolted saddle, common to every pack.
    saddle = loft([[(-.07,.084,z),(.07,.084,z),(.07,.19,z),(-.07,.19,z)] for z in (1.3715,1.4085)])
    clearance = ([((sx*.065,.14,1.36),(sx*.065,.14,1.42),.0343,10) for sx in (1,-1)]
                 if variant=="vesper" else [])
    carve(k,saddle,bone,FRM,mirror=False,inner=FRM,cuts=clearance)
    hx, (_, hy, hz) = GRAB_HANDLE[0], FLAG_MOUNT
    k.tube([(hx,0.19,hz),(hx,hy,hz),(-hx,hy,hz),(-hx,0.19,hz)],
           GRAB_HANDLE[1],bone,SEC,mirror=False)
    surface.free()


GRAB_HANDLE = (0.06, 0.008)            # the power pack's grab handle: its bar's half-length and radius
FLAG_MOUNT = (0.0, 0.222, 1.39)         # the middle of the handle bar's axis: the FlagMount gizmo, where a carried
                                        # CTF flag's BackMount goes (models/gameplay/ctf_flag)


def build_flag_mount(rig):
    """FlagMount: an empty on UpperChest at the middle of the grab handle bar's axis, facing Tensor's front
    (its local +Y forward, +Z up: in glTF / Godot -Z forward, +Y up). The CTF flag's BackMount lies on its
    hook's pocket axis with the same axes, so matching the two gizmos seats the flag's hook on the bar."""
    e = bpy.data.objects.new("FlagMount", None)
    e.empty_display_type, e.empty_display_size = "ARROWS", 0.1
    bpy.context.scene.collection.objects.link(e)
    bone = rig.data.bones["UpperChest"]
    e.parent, e.parent_type, e.parent_bone = rig, "BONE", "UpperChest"
    e.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    fwd, up = Vector((0, -1, 0)), Vector((0, 0, 1))
    m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
    m.translation = FLAG_MOUNT
    e.matrix_basis = m
    return e


NECK_TOP = J["head"].z - 0.003                          # the yaw shaft's top face, just under the pitch axle
PLATE_Z = (J["head"].z + 0.026, J["head"].z + 0.036)    # the head's underside mount plate; every head sits on it


def build_neck(k):
    """The neck (the previous model's assembly, user): a yaw shaft on its bearing deep in the chest's well, a
    conical bearing boot at the well's mouth carrying the head hydraulics' lower clevises, a stainless steel clamp
    ring (the base collar) whose looms curve up into the column's back under a cable collar, and a short pitch yoke on its top: two cheeks
    holding the head's axle."""
    n, p = J["neck"].z, J["head"]
    k.cyl((0, 0, n), (0, 0, NECK_TOP), 0.044, "Neck", FRM, segs=12, mirror=False)             # yaw shaft
    k.cyl((0, 0, 1.488), (0, 0, 1.52), 0.057, "Neck", FRM, segs=14, r1=0.05, mirror=False)   # bearing boot
    k.cyl((0, 0, 1.52), (0, 0, 1.532), 0.054, "Neck", JNT, segs=14, mirror=False)             # clamp ring
    k.cyl((0, 0, 1.578), (0, 0, 1.586), 0.0505, "Neck", JNT, segs=12, mirror=False)            # cable collar
    for sx in (1, -1):  # the pitch yoke's cheeks, standing on the shaft's top face
        k.obox((sx * 0.032, 0, NECK_TOP - 0.002), (sx * 0.032, 0, p.z + 0.012), 0.012, 0.04, FWD, "Neck", FRM,
               mirror=False)
    for a0, a1, zb, mat in ((58, 75, 1.566, WIRE), (32, 45, 1.556, HOSE)):  # the looms: out of the base collar,
        a0, a1 = math.radians(a0), math.radians(a1)                    # into the column's facets (centres at 15+30k deg)
        out = Vector((math.cos(a1), math.sin(a1), 0))
        hose(k, (0.05 * math.cos(a0), 0.05 * math.sin(a0), 1.532), UP, out * 0.044 * math.cos(math.pi / 12) + Vector((0, 0, zb)),
             out, 0.004, "Neck", mat, reach=0.02, mirror=False)
    ax, ay, az = PISTON_SPECS[0][2]
    clevis(k, Vector((ax, ay, az)), "Neck", 1.499, az + 0.013)  # the hydraulics' lower clevises, on the boot


def clevis(k, pin, bone, z0, z1, gap=0.011, t=0.004):
    """A clevis for a piston eye on a pin along x: two cheeks `t` thick, `gap` either side of the pin's centre
    (the eye turns between them), from z0 to z1."""
    for sx in (1, -1):
        k.box((pin.x + sx * (gap + t / 2), pin.y, (z0 + z1) / 2), (t, 0.02, z1 - z0), bone, FRM, solid=False)


def head_mount(k):
    """The interface every head variant is built on: the pitch axle between the neck's yoke cheeks, a saddle up
    from it into the underside mount plate (every head sits on the plate) and the hydraulics' upper clevises
    hanging from the plate."""
    p = J["head"]
    k.cyl((-0.026, 0, p.z), (0.026, 0, p.z), 0.017, "Head", JNT, mirror=False)  # pitch axle, between the cheeks
    k.box((0, 0, (p.z + 0.01 + PLATE_Z[0] + 0.002) / 2), (0.048, 0.024, PLATE_Z[0] + 0.002 - p.z - 0.01), "Head", FRM,
          mirror=False)                                                           # saddle, axle to plate
    k.box((0, -0.024, sum(PLATE_Z) / 2), (0.12, 0.092, PLATE_Z[1] - PLATE_Z[0]), "Head", FRM, mirror=False)  # plate
    bx, by, bz = PISTON_SPECS[0][4]
    clevis(k, Vector((bx, by, bz)), "Head", bz - 0.01, PLATE_Z[0] + 0.004)  # upper clevises, under the plate


def helm(k, stations, half, mat=PRI, **cut):
    """A head shell lofted front to back: stations [(y, inset)], half(inset) its +x half profile (x, z)
    from the bottom centre to the top centre (a bigger inset chamfers that end)."""
    sections = [[(x, y, z) for x, z in sym(half(i))] for y, i in stations]
    carve(k, loft(sections), "Head", mat, mirror=False, **cut)


def crown_hatch(k, y, z, r=0.032):
    """The bolted hatch set into a head's flat crown at height z: returns its recess (a cut for the shell);
    the disc and its four bolts sit in it."""
    k.cyl((0, y, z - 0.007), (0, y, z - 0.001), r - 0.003, "Head", SEC, segs=16, mirror=False)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        bolt(k, (0.7 * r * math.cos(a), y + 0.7 * r * math.sin(a), z - 0.001), UP, "Head", r=0.003, head=0.0015,
             mirror=False)
    return ((0, y, z - 0.007), (0, y, z + 0.02), r, 16)


def head_projector(k):
    """Projector (default): a wide sensor box on the neck's plate, a perforated grille over a lit sensor array in
    its front bay, a bolted hatch and seams on top and heat-sink grooves behind."""
    half = lambda i: [(0.0, 1.636 + i), (0.094 - i, 1.636 + i), (0.108 - i, 1.651), (0.108 - i, 1.712),
                      (0.094 - i, 1.726 - i * 0.5), (0.0, 1.726 - i * 0.5)]
    helm(k, [(-0.142, 0.01), (-0.132, 0.0), (0.056, 0.0), (0.068, 0.01)], half, cuts=[crown_hatch(k, -0.037, 1.726)],
         boxes=[((0, -0.142, 1.683), (0.176, 0.022, 0.042))]                                   # sensor bay
         + [((sx * 0.05, -0.04, 1.726), (0.004, 0.16, 0.006)) for sx in (1, -1)]               # top seams
         + [((0, 0.068, z), (0.15, 0.012, 0.005)) for z in (1.668, 1.683, 1.698)])            # heat sink
    k.box((0, -0.1305, 1.683), (0.17, 0.002, 0.03), "Head", EMI, mirror=False)                 # sensor array
    holes = [[(-0.064 + i * 0.016 + dx, -0.135, z + dz) for dx, dz in ((0, 0), (0.008, 0), (0.008, 0.008), (0, 0.008))]
             for i in range(9) for z in (1.667, 1.686)]
    k.plate([(-0.086, -0.135, 1.664), (0.086, -0.135, 1.664), (0.086, -0.135, 1.702), (-0.086, -0.135, 1.702)],
            0.006, FWD, "Head", FRM, holes=holes, mirror=False)                                # perforated grille


def head_sentinel(k):
    """Sentinel: a wide, low housing on the neck's plate with twin lens barrels in bezels, a bolted hatch in its
    crown and side vent slots."""
    half = lambda i: [(0.0, 1.636 + i), (0.086 - i, 1.636 + i), (0.1 - i, 1.65), (0.1 - i, 1.69),
                      (0.086 - i, 1.702 - i * 0.5), (0.0, 1.702 - i * 0.5)]
    helm(k, [(-0.122, 0.01), (-0.112, 0.0), (0.06, 0.0), (0.072, 0.012)], half, cuts=[crown_hatch(k, -0.025, 1.702)],
         boxes=[((sx * 0.1, y, 1.668), (0.012, 0.007, 0.034)) for sx in (1, -1) for y in (-0.05, -0.034, -0.018, -0.002)])
    for sx in (1, -1):
        c = Vector((sx * 0.046, -0.112, 1.668))
        k.cyl(c + Vector((0, 0.006, 0)), c - Vector((0, 0.02, 0)), 0.022, "Head", TIT, segs=12, mirror=False)  # barrels
        k.plate(ring(c.x, c.z, 0.025, c.y - 0.021, 12), 0.005, FWD, "Head", FRM, holes=[ring(c.x, c.z, 0.018, c.y - 0.021, 12)],
                mirror=False)                                                                  # bezels
        k.cyl(c - Vector((0, 0.018, 0)), c - Vector((0, 0.021, 0)), 0.018, "Head", FRM, segs=12, mirror=False)  # dark glass
        k.cyl(c - Vector((0, 0.021, 0)), c - Vector((0, 0.023, 0)), 0.007, "Head", EMI, segs=8, mirror=False)  # cores


def head_porthole(k):
    """Porthole: a tall rounded helm with one round eye bored in its face (a lit lens behind a flush bezel)
    between vertical slot pairs, ear discs with status lights on its flanks and a rear
    radiator with light bars; a bolted hatch in its crown."""
    half = lambda i: [(0.0, 1.636 + i * 0.3), (0.064 - i, 1.636 + i * 0.3), (0.072 - i, 1.644), (0.072 - i, 1.72),
                      (0.056 - i * 0.7, 1.742 - i * 0.2), (0.0, 1.752 - i * 0.3)]
    ez, fy = 1.684, -0.12
    helm(k, [(-0.12, 0.012), (-0.108, 0.0), (0.058, 0.0), (0.078, 0.014)], half,
         cuts=[((0, fy - 0.01, ez), (0, fy + 0.014, ez), 0.03, 16), crown_hatch(k, -0.025, 1.752, 0.03)],
         boxes=[((sx * 0.045 + dx, fy, ez), (0.003, 0.012, 0.04)) for sx in (1, -1) for dx in (-0.004, 0.004)])
    k.plate(ring(0, ez, 0.03, fy + 0.004, 16), 0.006, FWD, "Head", TIT, holes=[ring(0, ez, 0.023, fy + 0.004, 16)],
            mirror=False)                                                                      # bezel
    k.cyl((0, fy + 0.012, ez), (0, fy + 0.008, ez), 0.023, "Head", EMI, segs=14, mirror=False)  # lens
    k.cyl((0.071, 0.01, 1.685), (0.084, 0.01, 1.685), 0.026, "Head", FRM, segs=12)             # ear discs
    k.cyl((0.084, 0.01, 1.685), (0.088, 0.01, 1.685), 0.014, "Head", TIT, segs=10)
    k.box((0.0855, 0.01, 1.705), (0.002, 0.004, 0.01), "Head", EMI)                            # status light
    k.box((0, 0.082, 1.684), (0.08, 0.012, 0.06), "Head", FRM, mirror=False)                   # rear radiator
    for z in (1.669, 1.684, 1.699):
        k.box((0, 0.0885, z), (0.06, 0.002, 0.004), "Head", EMI, mirror=False)                 # light bars


def head_raptor(k):
    """Raptor: a swept, faceted cranium carved from two views, a recessed visor slot and its light strip,
    a crest along the crown and sensor canisters on its flanks."""
    front = [(-0.064, 1.636), (0.064, 1.636), (0.074, 1.646), (0.074, 1.7), (0.05, 1.742), (-0.05, 1.742),
             (-0.074, 1.7), (-0.074, 1.646)]                                                    # (x, z)
    side = [(-0.14, 1.66), (-0.12, 1.636), (0.06, 1.636), (0.09, 1.67), (0.07, 1.72), (-0.02, 1.744),
            (-0.1, 1.725), (-0.14, 1.7)]                                                       # (y, z)
    k.plate([(x, -0.03, z) for x, z in front], 0.3, FWD, "Head", PRI, mirror=False,
            intersect=[([(0, y, z) for y, z in side], (1, 0, 0), 0.2)],
            boxes=[((0, -0.14, 1.685), (0.15, 0.03, 0.018))])                                 # shell, visor slot
    k.box((0, -0.1255, 1.685), (0.13, 0.002, 0.008), "Head", EMI, mirror=False)                # visor light
    crest = [(-0.08, 1.72), (0.05, 1.72), (0.03, HEIGHT), (-0.05, HEIGHT)]  # its root sunk in the crown
    k.plate([(0, y, z) for y, z in crest], 0.008, (1, 0, 0), "Head", SEC, mirror=False)        # crest
    k.cyl((0.07, 0.02, 1.673), (0.092, 0.02, 1.673), 0.02, "Head", TIT, segs=10)                 # sensor canisters
    k.cyl((0.092, 0.02, 1.673), (0.096, 0.02, 1.673), 0.013, "Head", FRM, segs=8)


def head_arachne(k):
    """Arachne: a compact faceted housing with a cluster of lens barrels on its face (one main optic ringed
    by four) and slotted team-accent panels on its flanks."""
    front = [(-0.064, 1.636), (0.064, 1.636), (0.074, 1.646), (0.074, 1.715), (0.056, 1.74), (-0.056, 1.74),
             (-0.074, 1.715), (-0.074, 1.646)]
    side = [(-0.13, 1.66), (-0.11, 1.636), (0.06, 1.636), (0.08, 1.656), (0.08, 1.715), (0.06, 1.74), (-0.1, 1.74),
            (-0.13, 1.715)]
    k.plate([(x, -0.03, z) for x, z in front], 0.3, FWD, "Head", FRM, mirror=False,
            intersect=[([(0, y, z) for y, z in side], (1, 0, 0), 0.2)])                       # housing
    oz = 1.688
    k.cyl((0, -0.11, oz), (0, -0.15, oz), 0.026, "Head", TIT, segs=12, mirror=False)          # main optic
    k.plate(ring(0, oz, 0.029, -0.153, 16), 0.006, FWD, "Head", FRM, holes=[ring(0, oz, 0.02, -0.153, 16)],
            mirror=False)
    k.cyl((0, -0.146, oz), (0, -0.151, oz), 0.02, "Head", FRM, segs=12, mirror=False)          # dark glass
    k.cyl((0, -0.151, oz), (0, -0.153, oz), 0.009, "Head", EMI, segs=8, mirror=False)          # its core
    for lz in (oz - 0.024, oz + 0.024):                                                                  # the four small optics
        k.cyl((0.05, -0.108, lz), (0.05, -0.142, lz), 0.013, "Head", TIT, segs=8)
        k.cyl((0.05, -0.142, lz), (0.05, -0.144, lz), 0.006, "Head", EMI, segs=6)
    panel = [(-0.1, 1.655), (0.04, 1.655), (0.052, 1.667), (0.052, 1.705), (0.04, 1.715), (-0.1, 1.715)]
    k.plate([(0.0765, y, z) for y, z in panel], 0.005, (1, 0, 0), "Head", SEC,
            holes=[[(0.0765, y, z) for y, z in ((y0, 1.667), (y0 + 0.01, 1.667), (y0 + 0.01, 1.703), (y0, 1.703))]
                   for y0 in (-0.08, -0.06)])                                                  # side panels, slotted


# Head variants: every one is built on head_mount() and checked like the rest of the body; each is
# its own mesh in the export (skinned to Head), so the engine shows one and hides the others. Every head
# sits on the neck's mount plate (its underside at z 1.636) and stays under 1.753 m.
HEAD_VARIANTS = {"projector": head_projector, "sentinel": head_sentinel, "porthole": head_porthole,
                 "raptor": head_raptor, "arachne": head_arachne}
DEFAULT_HEAD = "projector"


def build_head(k, variant=DEFAULT_HEAD):
    head_mount(k)
    HEAD_VARIANTS[variant](k)


def head_mesh_name(variant):
    return f"SK_{NAME.capitalize()}Head{variant.capitalize()}"


# --------------------------------------------------------------------------------------------
# Arm: clavicle and shoulder motor, the shoulder's pitch / roll / twist stages, a sculpted upper arm
# with its deltoid, the elbow with its crank and roll housing, a lofted gauntlet, the hand
# --------------------------------------------------------------------------------------------

def build_arm(k):
    c, e, z = S, E, S.z
    k.obox((0.03, 0, z), (0.1, 0, z), 0.06, 0.07, UP, "LeftShoulder", FRM, bevel=0.01)  # clavicle
    k.cyl((0.095, 0, z), (0.14, 0, z), 0.056, "LeftShoulder", TIT, segs=14)           # pitch motor, lateral axis
    for x in (0.106, 0.122):                                                           # its cooling fins
        k.cyl((x, 0, z), (x + 0.004, 0, z), 0.059, "LeftShoulder", FRM, segs=10)
    # Pitch stage: output flange with two ears carrying the roll bearings on the fore-aft axis.
    k.cyl((0.14, 0, z), (0.148, 0, z), 0.055, "LeftShoulderPitch", JNT, segs=14)
    for sy in (1, -1):
        k.obox((0.143, sy * 0.048, z), (0.197, sy * 0.048, z), 0.01, 0.05, UP, "LeftShoulderPitch", FRM)
        k.cyl((c.x, sy * 0.043, z), (c.x, sy * 0.058, z), 0.02, "LeftShoulderPitch", TIT, segs=10)
    # Roll stage: hub between the ears, carrying the twist housing around the arm axis.
    k.cyl((c.x, -0.0435, z), (c.x, 0.0435, z), 0.024, "LeftShoulderRoll", JNT, segs=10)
    k.cyl((0.195, 0, z), (0.237, 0, z), 0.026, "LeftShoulderRoll", FRM, segs=12)
    # Upper arm: the twist rotor turning in the housing, then a lofted shell with a deltoid bulge on top
    # (its outer face when the arm hangs), a slanted vent bank and a recessed panel, narrowing to the
    # elbow yoke.
    k.cyl((0.237, 0, z), (0.249, 0, z), 0.032, "LeftUpperArm", JNT, segs=12)
    ua = [(0.247, octo(0.03, -0.03, 0.03, 0.01, 0.012)), (0.272, octo(0.054, -0.035, 0.062, 0.024, 0.03)),
          (0.318, octo(0.05, -0.034, 0.058, 0.02, 0.024)), (0.35, octo(0.04, -0.033, 0.048, 0.015, 0.018)),
          (0.392, octo(0.034, -0.048, 0.048, 0.003, 0.003))]   # tapering to the elbow (the folded forearm's room),
    # its end as tall as the yoke and nearly square, so the lugs come out of its bottom flush with its faces (user: they
    # sat on its outside)
    stations = [(t - c.x, sym(h)) for t, h in ua]
    carve(k, axis_loft(c, (1, 0, 0), (0, 1, 0), stations), "LeftUpperArm", PRI,
          subtract=slant_slots((0.30, -lerp_st(ua, 0.30), z + 0.006), (1, 0, 0), (0, 0, 1), (0, 1, 0), 4, 0.012, 0.03, 0.004,
                               0.01, 0.006),
          boxes=[((0.355, 0.0, z + 0.042), (0.05, 0.03, 0.008))])
    ax_, ay_, az_ = PISTON_SPECS[2][2]
    eye_low = az_ - PISTON_SPECS[2][5] - 0.001      # 1 mm under the barrel's eye, which turns on the pin above it
    k.box((ax_, ay_, (z + 0.042 + eye_low) / 2), (0.032, 0.032, eye_low - z - 0.042), "LeftUpperArm", FRM,
          solid=False)  # piston mount: a pedestal out of the upper arm's top flat (user: it cut through the eye)
    # A loom and a hydraulic line down the back of the upper arm (the elbow folds forward, away).
    hy = lambda x: lerp_st(ua, x)
    hose(k, (0.286, hy(0.286), z + 0.016), BACK, (0.372, hy(0.372), z + 0.016), BACK, CABLE[0], "LeftUpperArm",
         WIRE, reach=0.018, sag=0.004)
    hose(k, (0.29, hy(0.29), z - 0.006), BACK, (0.366, hy(0.366), z - 0.006), BACK, LINE[0], "LeftUpperArm", HOSE,
         reach=0.012, sag=0.006)
    k.box(((0.39 + e.x - 0.04) / 2, 0.018, z), (e.x - 0.04 - 0.39, 0.024, 0.066), "LeftUpperArm", FRM)  # yoke web, behind
                                                                         # (clear of the tongue at the full fold)
    for dz in (-0.04, 0.04):  # elbow yoke
        k.cyl((e.x, 0, z + dz - 0.0075), (e.x, 0, z + dz + 0.0075), 0.045, "LeftUpperArm", FRM, segs=12)
        k.obox((0.385, 0, z + dz), (e.x, 0, z + dz), 0.06, 0.015, UP, "LeftUpperArm", FRM)
    k.cyl((e.x, 0, z - 0.0475), (e.x, 0, z - 0.0505), 0.024, "LeftUpperArm", BRZ, segs=10)  # bearing cap, under
    # Elbow hinge stage: the hub turning in the yoke, the crank, the tongue and the roll housing.
    k.cyl((e.x, 0, z - 0.0325), (e.x, 0, z + 0.0325), 0.036, "LeftElbowHinge", JNT, segs=12)  # elbow hub
    # Crank lever on the top face: a wishbone bolted flat on the saddle block over the roll housing,
    # running back over the elbow (where it is also carried by the axle boss) to a square pad under
    # the piston's rod-end pin.
    horn_len, (hx, hy) = ELBOW_CRANK
    bx, by = e.x + horn_len * hx, horn_len * hy
    tz = z + 0.0595
    k.cyl((e.x, 0, z + 0.03), (e.x, 0, z + 0.0665), 0.015, "LeftElbowHinge", JNT, segs=8)  # axle, up through the lever
    k.cyl((e.x, 0, z + 0.0475), (e.x, 0, z + 0.0535), 0.022, "LeftElbowHinge", TIT, segs=10)  # axle boss, under the lever
    pad = 0.014
    k.plate([(ROLL_HOUSING[1] - 0.002, -0.03, tz), (ROLL_HOUSING[1] - 0.002, 0.03, tz), (e.x + 0.03, by + 0.016, tz),
             (bx + pad, by + pad, tz), (bx - pad, by + pad, tz), (bx - pad, by - pad, tz),
             (bx + pad, by - pad, tz), (e.x + 0.03, -0.028, tz)], 0.012, UP, "LeftElbowHinge", FRM,
            holes=[[(e.x + 0.062, -0.014, tz), (e.x + 0.062, 0.014, tz), (e.x + 0.035, 0.0, tz)]])  # lightening cut
    for wy in (-0.019, 0.019):  # bolts into the saddle block
        k.cyl((e.x + 0.077, wy, tz + 0.006), (e.x + 0.077, wy, tz + 0.011), 0.0045, "LeftElbowHinge", JNT, segs=6,
              solid=False)
    x0, x1 = ROLL_HOUSING
    k.obox((e.x, 0, z), (x0 + 0.004, 0, z), 0.05, 0.062, UP, "LeftElbowHinge", FRM, bevel=0.006)  # tongue
    k.cyl((x0, 0, z), (x1, 0, z), ROLL_R, "LeftElbowHinge", TIT, segs=14)  # forearm roll housing
    k.obox((x0 + 0.002, 0, z + 0.0425), (x1 - 0.002, 0, z + 0.0425), 0.05, 0.022, UP, "LeftElbowHinge", FRM,
           bevel=0.003)  # saddle block: its foot sunk in the housing's top, the wishbone on its flat
    # Forearm: the roll rotor turning in the housing, then a lofted gauntlet, fuller near the elbow,
    # with a vent bank on its top (its outer face when the arm hangs) and a recessed side panel.
    k.cyl((x1, 0, z), (x1 + 0.008, 0, z), ROLL_R - 0.007, "LeftLowerArm", JNT, segs=12)  # roll rotor
    fa = [(x1 + 0.007, octo(0.04, -0.036, 0.04, 0.012, 0.014)), (x1 + 0.03, octo(0.047, -0.041, 0.05, 0.014, 0.02)),
          (W.x - 0.06, octo(0.042, -0.036, 0.043, 0.012, 0.016)), (W.x - 0.024, octo(0.036, -0.032, 0.036, 0.01, 0.012))]
    carve(k, axis_loft(c, (1, 0, 0), (0, 1, 0), [(t - c.x, sym(h)) for t, h in fa]), "LeftLowerArm", PRI,
          subtract=slant_slots(((x1 + W.x) / 2 + 0.005, 0.0, z + 0.046), (1, 0, 0), (0, 1, 0), (0, 0, 1), 5, 0.014,
                               0.04, 0.005, 0.005, 0.006),
          boxes=[(((x1 + W.x) / 2, -0.045, z - 0.004), (0.06, 0.008, 0.03))])
    k.cyl((W.x - 0.025, 0, z), (W.x - 0.004, 0, z), 0.046, "LeftLowerArm", TIT, segs=14)  # wrist housing
    # (no loom or line on the forearm: the gauntlet is too short for them since the roll housing moved out on the
    # tongue; user: remove them, there's no room)


def lerp_st(stations, x):
    """The half-width of a lofted limb's octagon stations [(x, half)] at x."""
    for (x0, h0), (x1, h1) in zip(stations, stations[1:]):
        if x0 <= x <= x1:
            return h0[2][0] + (h1[2][0] - h0[2][0]) * (x - x0) / (x1 - x0)
    raise ValueError(x)


def sgn(v):
    return 1 if v > 0 else -1


def build_hand(k, bones):
    z = W.z
    k.cyl((W.x - 0.004, 0, z), (W.x + 0.014, 0, z), 0.04, "LeftHand", JNT, segs=12)  # wrist rotator
    k.obox((W.x + 0.01, 0, z), (W.x + 0.104, 0, z), 0.09, 0.032, UP, "LeftHand", FRM, bevel=0.004)  # palm
    # Back of the hand: a lofted armour shell over the palm.
    bh = [(W.x + 0.016, [(0.0, 0.015), (0.036, 0.015), (0.04, 0.022), (0.03, 0.03), (0.0, 0.032)]),
          (W.x + 0.074, [(0.0, 0.015), (0.042, 0.015), (0.045, 0.023), (0.034, 0.033), (0.0, 0.035)]),
          (W.x + 0.086, [(0.0, 0.015), (0.042, 0.015), (0.044, 0.021), (0.034, 0.026), (0.0, 0.027)])]
    carve(k, axis_loft(W, (1, 0, 0), (0, 1, 0), [(t - W.x, sym(h)) for t, h in bh]), "LeftHand", PRI)
    for name in DIGITS:
        b = bones[name]
        last = name.endswith("Distal")
        k.cyl(b.head - b.hinge_axis * 0.0085, b.head + b.hinge_axis * 0.0085, 0.0085, name, TIT, segs=4)
        tip = b.tail - b.axis * 0.002 if last else b.tail + b.axis * 0.005  # reaches the next knuckle pin
        k.obox(b.head + b.axis * 0.006, tip, 0.015, 0.016, -b.flex, name, FRM, bevel=0.002)


# --------------------------------------------------------------------------------------------
# Leg: the hip's Cardan under its yaw motor, a sculpted thigh, the knee clevis and crank, the shin
# frame inside a lofted boot guard with its kneecap, the ankle's Cardan cross and a heavy foot
# --------------------------------------------------------------------------------------------

KNEE_INSET = 0.006  # knee link plates sit this far inside the thigh's side faces
KNEE_R = 0.04       # the knee lugs' round ends (and half their width): inside the thigh's section
HUMP_X = (0.047, 0.064)  # the thigh's outer hump: its inner face (against the outer cheek) and outer face
HUMP = ((-0.056, -0.1), (-0.056, -0.075), (-0.04, -0.056), (-0.022, -0.046), (0.022, -0.046), (0.042, -0.056),
        (0.062, -0.075), (0.062, -0.1))  # its side outline (y, z from the hip pivot), rising out of the shell's top
HUMP_INSET = 0.006  # how far its upper edges are drawn in on the outer face
TOE_HINGE = (-0.107, -0.143, 0.016, 0.036)  # the toe hinge: the foot base's front, the toe cap's back, the
                                            # knuckles' radius, the outer knuckles' inner faces (from the foot axis)
THIGH = ((H.z - 0.09, 0.064, -0.084, 0.08), (0.70, 0.064, -0.09, 0.082), (K.z + 0.075, 0.058, -0.078, 0.072))
PLATE_X = THIGH[-1][1] - KNEE_INSET - 0.0075   # knee link plates' centres, either side of the thigh axis
SHIN_HALF = PLATE_X - 0.0075 - 0.002           # shin half-width: clears the knee link plates by 2 mm
PISTON_A = {spec[0]: Vector(spec[2]) for spec in PISTON_SPECS}  # barrel-end mount point per piston
PISTON_B = {spec[0]: Vector(spec[4]) for spec in PISTON_SPECS}  # rod-end mount point per piston


HATCH = (-0.011, 0.35)  # the shin's access hatch: centre (y from the knee, z), on the side face's flat


def thigh_half(w, yf, yb):
    return [(0.0, yf), (0.55 * w, yf + 0.006), (w, yf + 0.03), (w, yb - 0.018), (w - 0.018, yb), (0.0, yb)]


def build_leg(k):
    hip, knee, ankle = H, K, A
    hx = hip.x
    # Hip, a Cardan joint under a yaw motor: the yaw stage's output flange carries a fork whose
    # bosses hold the spider's fore-aft (roll) arms; the thigh knuckle turns on the spider's lateral
    # (pitch) arms. All three axes meet at the hip pivot.
    k.cyl((hx, hip.y, hip.z + 0.082), (hx, hip.y, hip.z + 0.09), 0.042, "LeftHipYaw", FRM, segs=14)  # yaw flange
    k.box((hx, hip.y, hip.z + 0.0765), (0.036, 0.114, 0.011), "LeftHipYaw", FRM, bevel=0.003)          # fork crosshead
    for sy in (1, -1):
        k.obox((hx, hip.y + sy * 0.052, hip.z + 0.077), (hx, hip.y + sy * 0.052, hip.z - 0.002), 0.036, 0.01, BACK,
               "LeftHipYaw", FRM)  # fork plates
        k.cyl((hx, hip.y + sy * 0.047, hip.z), (hx, hip.y + sy * 0.06, hip.z), 0.017, "LeftHipYaw", TIT,
              segs=10)  # roll bosses
    k.cyl((hx, hip.y - 0.056, hip.z), (hx, hip.y + 0.056, hip.z), 0.012, "LeftHipRoll", JNT)  # spider: roll arms
    k.cyl((hx - 0.04, hip.y, hip.z), (hx + 0.04, hip.y, hip.z), 0.015, "LeftHipRoll", JNT)   # pitch arms
    k.box(hip, (0.032, 0.032, 0.032), "LeftHipRoll", FRM, bevel=0.004)
    # Thigh knuckle: a boss on each pitch arm on a cheek down into the shell (the outer cheek beside the
    # shell's hump); each boss 2 mm proud of its cheek either side, so no faces are coplanar.
    for bx in (hx - 0.039, hx + 0.039):
        k.cyl((bx - 0.009, hip.y, hip.z), (bx + 0.009, hip.y, hip.z), 0.028, "LeftUpperLeg", TIT, segs=12)
        k.obox((bx, hip.y, hip.z), (bx, hip.y, THIGH[0][0] - 0.01), 0.014, 0.044, FWD, "LeftUpperLeg", FRM)
    k.cyl((hx + 0.048, hip.y, hip.z), (hx + 0.053, hip.y, hip.z), 0.016, "LeftUpperLeg", BRZ, segs=8)  # outer bearing cap
    # Thigh: a lofted shell centred on the hip axis, hanging below the knuckle with its top 0.112 m
    # under the hip pivot (full flexion swings clear under the fork), keeled in front, with slanted vents
    # and screws down its front and a grab handle across its upper front.
    def span(zz):
        (z0, w0, f0, _), (z1, w1, f1, _) = next((p, q) for p, q in zip(THIGH, THIGH[1:]) if q[0] <= zz <= p[0])
        t = (zz - z0) / (z1 - z0)
        return w0 + (w1 - w0) * t, hip.y + f0 + (f1 - f0) * t

    def front(zz, u, off=0.0):  # a point on the keeled front (both facets of thigh_half), `off` ahead of it
        w, yf = span(zz)
        b, a = 0.55 * w, abs(u)
        y = yf + 0.006 * a / b if a <= b else yf + 0.006 + 0.024 * (a - b) / (w - b)
        return Vector((hx + u, y - off, zz))
    # Five slanted vents down the front, across the keel's ridge (their prisms deep enough for its V).
    front_vents = [sl for i in range(5) for sl in slant_slots(front(0.628 + 0.0225 * i, 0.0) + Vector((0, 0.0017, 0)),
                                                                (0, 0, 1), (1, 0, 0), (0, -1, 0), 1, 0.0, 0.04, 0.004,
                                                                0.006, 0.0045)]
    shell = zloft([(zz, w, hip.y + yf, hip.y + yb) for zz, w, yf, yb in THIGH], thigh_half)
    for v in shell.verts:
        v.co.x += hx
    # The hump: the shell's outer side swelling up toward the hip like a kneecap (user), outboard of the
    # outer cheek: a rounded outline in side view (HUMP), its upper edges drawn in toward the outer face.
    def inset(y, z):  # the outer face's outline: sides and top drawn in, the foot (inside the shell) as is
        if z <= -0.09:
            return y, z
        return y - math.copysign(HUMP_INSET, y), z - (HUMP_INSET if z > -0.07 else 0.0)
    ext = bmesh.new()
    rings = [[ext.verts.new((hx + x, hip.y + y, hip.z + z)) for y, z in (HUMP if x == HUMP_X[0] else map(inset, *zip(*HUMP)))]
             for x in HUMP_X]
    ext.faces.new(rings[0][::-1])
    ext.faces.new(rings[1])
    for i in range(len(HUMP)):
        j = (i + 1) % len(HUMP)
        ext.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
    bmesh.ops.triangulate(ext, faces=ext.faces[:])  # the drawn-in sides are not planar
    bmesh.ops.recalc_face_normals(ext, faces=ext.faces[:])
    carve(k, shell, "LeftUpperLeg", PRI, union=[ext],
          boxes=[((hx + 0.064, hip.y + 0.0025, 0.66), (0.01, 0.07, 0.1))],
          subtract=slant_slots((hx + 0.063, hip.y + 0.0025, 0.745), (0, 1, 0), (0, 0, 1), (1, 0, 0), 3, 0.014, 0.034,
                               0.005, 0.01, 0.007) + front_vents)
    for zz in (0.614, 0.732):  # screws on the keel's facets, either side of the vents
        for u in (-0.03, 0.03):
            b = 0.55 * span(zz)[0]
            bolt(k, front(zz, u), (math.copysign(0.006 / b, u), -1, 0), "LeftUpperLeg", mat=TIT, r=0.0035, head=0.002)
    hz, hy = 0.775, front(0.775, 0.03).y
    k.tube([(hx - 0.03, hy, hz), (hx - 0.03, hy - 0.028, hz), (hx + 0.03, hy - 0.028, hz),
            (hx + 0.03, hy, hz)], 0.007, "LeftUpperLeg", SEC)                         # grab handle
    hose(k, (hx - 0.02, hip.y + 0.08, 0.775), BACK, (hx - 0.02, hip.y + 0.078, 0.655), BACK, CABLE[0],
         "LeftUpperLeg", WIRE, reach=0.016, sag=0.0, bulge=(0, 0.006, 0))
    hose(k, (hx + 0.02, hip.y + 0.08, 0.775), BACK, (hx + 0.022, hip.y + 0.078, 0.655), BACK, LINE[0],
         "LeftUpperLeg", HOSE, reach=0.012, bulge=(0.004, 0.004, 0))
    # Knee clevis: two link plates, each as deep as its round end, rooted in the shell's bottom and set
    # KNEE_INSET inside its sides; the shell ties them together. The shin's hub turns between them.
    lug = ([(-KNEE_R * math.cos(math.radians(a)), -KNEE_R * math.sin(math.radians(a))) for a in range(0, 181, 20)]
           + [(KNEE_R, THIGH[-1][0] + 0.03 - knee.z), (-KNEE_R, THIGH[-1][0] + 0.03 - knee.z)])
    for x in (hx - PLATE_X, hx + PLATE_X):  # each one lug: straight sides running tangent into its round end
        k.prism([(x, knee.y + u, knee.z + v) for u, v in lug], 0.015, (1, 0, 0), "LeftUpperLeg", FRM)
    k.cyl((hx + PLATE_X + 0.0075, knee.y, knee.z), (hx + PLATE_X + 0.0165, knee.y, knee.z), KNEE_R - 0.008,
          "LeftUpperLeg", TIT, segs=12)  # knee bearing, inside the outer lug's round end
    ax_, ay_, az_ = PISTON_A["LeftKneePiston"]
    k.obox((hx + 0.058, ay_, az_), (ax_ - 0.017, ay_, az_), 0.03, 0.035, UP, "LeftUpperLeg", FRM,
           solid=False)  # piston outrigger on the shell's side face

    k.cyl((hx - PLATE_X + 0.0075, knee.y, knee.z), (hx + PLATE_X - 0.0075, knee.y, knee.z), KNEE_R - 0.003,
          "LeftLowerLeg", JNT, segs=12)  # knee hub, between the lugs' inner faces
    # Crank: the shin's axle runs out through the thigh's bearing and carries the piston horn.
    kx, ky, kz = KNEE_CRANK_B
    horn = (Vector((ky, kz)) - Vector((knee.y, knee.z))).normalized()
    k.cyl((hx + PLATE_X - 0.0075, knee.y, knee.z), (kx - 0.029, knee.y, knee.z), 0.016, "LeftLowerLeg", JNT, segs=8)  # ends in the horn
    k.obox((kx - 0.022 - 0.007, knee.y - 0.015 * horn.x, knee.z - 0.015 * horn.y), (kx - 0.029, ky, kz), 0.03, 0.014,
           (1, 0, 0), "LeftLowerLeg", FRM, solid=False)
    k.box((kx - 0.029, ky, kz), (0.018, 0.042, 0.042), "LeftLowerLeg", FRM, solid=False)  # square pad under the rod eye
    # Shin: a closed armour boot. A block between the knee link plates carries the knee hub; below the
    # plates' reach the boot flares to its full width: a keeled front with a stripe in its groove,
    # rising into the kneecap (one shell), two screws, four slanted vents and a grab handle down it, a calf bulging behind (the ankle actuator runs down behind it, an Achilles drive), slanted vents and
    # a bolted access hatch on the outer side, the ankle yoke hanging from its sole plate.
    x0, x1 = hx - SHIN_HALF, hx + SHIN_HALF
    zt, zb = knee.z - 0.02, ankle.z + 0.06
    k.box((hx, knee.y - 0.01, zt - 0.023), (2 * SHIN_HALF, 0.1, 0.046), "LeftLowerLeg", FRM)  # knee block, on the boot's top
    boot = ((zb, 0.044, -0.072, 0.07), (0.2, 0.05, -0.08, 0.108), (0.3, 0.054, -0.086, 0.142),
            (knee.z - 0.13, 0.054, -0.087, 0.055), (knee.z - 0.058, 0.054, -0.088, 0.04))
    # The kneecap: the boot's keeled front carried on up past its top, tapering over the knee (its
    # chamfers scaled with its width), fused into the boot so the two are one shell.
    cap = [(knee.z - 0.07, 0.054, -0.0878), (knee.z - 0.005, 0.044, -0.088), (knee.z + 0.058, 0.03, -0.08)]
    kneecap = zloft([(zz, w, knee.y + yf) for zz, w, yf in cap],
                    lambda w, yf: [(0.0, yf), (0.5 * w, yf + 0.004), (w, yf + 0.024 * w / 0.054),
                                   (w, knee.y - 0.058), (0.0, knee.y - 0.058)])
    for v in kneecap.verts:
        v.co.x += hx
    shell = zloft([(zz, w, knee.y + yf, knee.y + yb) for zz, w, yf, yb in boot],
                  lambda w, yf, yb: [(0.0, yf), (0.5 * w, yf + 0.004), (w, yf + 0.024), (w, yb - 0.022),
                                     (w - 0.02, yb), (0.0, yb)])
    for v in shell.verts:
        v.co.x += hx
    carve(k, shell, "LeftLowerLeg", PRI, union=[kneecap],
          boxes=[((hx, knee.y - 0.09, 0.28), (0.03, 0.012, 0.13)),                        # stripe groove
                 ((hx + 0.055, knee.y + HATCH[0], HATCH[1]), (0.008, 0.05, 0.07)),         # hatch recess
                 ((hx, 0.105, 0.302), (0.025, 0.09, 0.058)),                               # the actuator's channel:
                 ((hx, 0.105, 0.2), (0.036, 0.09, 0.16))],                                 # cheeks, then clear
          subtract=slant_slots((hx + 0.052, knee.y + HATCH[0], 0.24), (0, 1, 0), (0, 0, 1), (1, 0, 0), 4, 0.014,
                               0.036, 0.005, 0.01, 0.006)
          + [sl for i in range(4) for sl in slant_slots((hx, knee.y - 0.088 + 0.0012, 0.40 + 0.028 * i), (0, 0, 1),
                                                          (1, 0, 0), (0, -1, 0), 1, 0.0, 0.03, 0.004, 0.006, 0.004)])
    k.box((hx, knee.y - 0.0855, 0.28), (0.022, 0.004, 0.118), "LeftLowerLeg", SEC)  # stripe, in its groove
    for u in (-0.012, 0.012):  # screws on the kneecap's keel facets
        w_, yf_ = 0.044 + (0.03 - 0.044) * 0.476, knee.y - 0.088 + 0.008 * 0.476
        bolt(k, (hx + u, yf_ + 0.004 * abs(u) / (0.5 * w_), 0.515), (math.copysign(0.004 / (0.5 * w_), u), -1, 0.127),
             "LeftLowerLeg", mat=TIT, r=0.0035, head=0.002)
    hz, hy = 0.37, knee.y - 0.087 + 0.004 * 0.025 / 0.027
    k.tube([(hx - 0.025, hy, hz), (hx - 0.025, hy - 0.026, hz), (hx + 0.025, hy - 0.026, hz),
            (hx + 0.025, hy, hz)], 0.007, "LeftLowerLeg", SEC)                        # grab handle
    k.box((hx + 0.0525, knee.y + HATCH[0], HATCH[1]), (0.004, 0.042, 0.062), "LeftLowerLeg", TIT)  # access hatch
    for dy in (-0.015, 0.015):
        for dz in (-0.024, 0.024):
            bolt(k, (hx + 0.0545, knee.y + HATCH[0] + dy, HATCH[1] + dz), (1, 0, 0), "LeftLowerLeg", r=0.003, head=0.0015)
    # The ankle actuator's upper rod end turns on a cross pin through the channel's cheeks in the calf.
    ax_, ay_, az_ = PISTON_A["LeftAnklePiston"]
    k.cyl((ax_ - 0.03, ay_, az_), (ax_ + 0.03, ay_, az_), 0.004, "LeftLowerLeg", JNT, solid=False)  # cross pin
    for x in (x0 + 0.0065, x1 - 0.0065):  # ankle yoke, hanging from the boot's sole plate
        k.obox((x, 0, zb + 0.01), (x, 0, ankle.z - 0.015), 0.013, 0.07, FWD, "LeftLowerLeg", FRM)

    # Ankle, a Cardan cross: the pitch hub turns in the shin's yoke and carries fore-aft roll stubs,
    # level with the sole and square to the hub; the foot's clevis grips the stubs in two bosses,
    # its cheeks rooted in the foot's base. Both axes meet at the ankle pivot.
    k.cyl((x0 + 0.013, 0, ankle.z), (x1 - 0.013, 0, ankle.z), 0.03, "LeftAnklePitch", JNT, segs=12)  # pitch hub
    k.cyl((hx, -0.052, ankle.z), (hx, 0.052, ankle.z), 0.011, "LeftAnklePitch", JNT, segs=8)  # roll stubs
    for sy in (1, -1):
        k.cyl((hx, sy * 0.038, ankle.z), (hx, sy * 0.05, ankle.z), 0.017, "LeftFoot", TIT, segs=10)  # boss
        k.obox((hx, sy * 0.044, ankle.z), (hx, sy * 0.044, 0.03), 0.034, 0.012, BACK, "LeftFoot", FRM)
    k.cyl((hx, -0.05, ankle.z), (hx, -0.054, ankle.z), 0.012, "LeftFoot", BRZ, segs=8)  # bearing cap
    # Foot: a black sole with a tread, a machined base, a lofted instep armour over the front and a heel
    # fork for the ankle piston; the ankle guard bar arcs outside the shin's yoke.
    k.obox((hx, 0.1, 0.0065), (hx, -0.121, 0.0065), 0.122, 0.013, UP, "LeftFoot", BLK)            # sole
    k.obox((hx, 0.1, 0.0265), (hx, TOE_HINGE[0], 0.0265), 0.116, 0.027, UP, "LeftFoot", FRM, bevel=0.006)  # base
    inst = [(TOE_HINGE[0] + 0.001, 0.052, 0.04, 0.052), (-0.06, 0.056, 0.04, 0.068), (-0.04, 0.052, 0.04, 0.064)]
    shell = loft([[(hx + u, y, v) for u, v in sym([(0.0, zb_), (w, zb_), (w, zt_ - 0.012), (w - 0.014, zt_), (0.0, zt_)])]
                  for y, w, zb_, zt_ in inst])
    carve(k, shell, "LeftFoot", PRI, boxes=[((hx, -0.09, 0.052 + 0.012), (0.08, 0.008, 0.004))])  # instep armour
    hx_, hy_, hz_ = PISTON_B["LeftAnklePiston"]
    slot = STRUT_EYE_HALF + 0.0025 + 0.0003  # the heel fork's slot: clears the bearing ball
    k.plate([(hx_ - 0.024, 0.055, 0.058), (hx_ + 0.024, 0.055, 0.058), (hx_ + 0.024, 0.1, 0.058),
             (hx_ - 0.024, 0.1, 0.058)], 0.04, UP, "LeftFoot", FRM,
            holes=[[(hx_ - slot, hy_ - 0.026, 0.058), (hx_ + slot, hy_ - 0.026, 0.058), (hx_ + slot, 0.12, 0.058),
                    (hx_ - slot, 0.12, 0.058)]])
    k.cyl((hx_ - 0.028, hy_, hz_), (hx_ + 0.028, hy_, hz_), 0.004, "LeftFoot", JNT, solid=False)  # cross pin
    k.tube([(hx + 0.058, 0.055, 0.03), (hx + 0.09, 0.055, 0.03), (hx + 0.09, 0.035, 0.075), (hx + 0.09, -0.065, 0.075),
            (hx + 0.09, -0.085, 0.03), (hx + 0.058, -0.085, 0.03)], 0.007, "LeftFoot", SEC)  # ankle guard

    # The toe hinge, a knuckle hinge in the open between the instep armour and the toe cap: the base stops
    # short of it and two lugs carry the foot's outer knuckles (standing above the base); the toe's centre
    # knuckle turns between them on a web from the toe cap; a steel pin through all three, its ends showing.
    ball = J["ball"]
    y0, y1, kr, kx = TOE_HINGE
    for sx in (1, -1):
        k.obox((hx + sx * (kx + 0.011), y0 + 0.002, 0.024), (hx + sx * (kx + 0.011), ball.y, 0.024), 0.022, 0.022, UP,
               "LeftFoot", FRM)                                                            # knuckle lug, off the base
        k.cyl((hx + sx * kx, ball.y, ball.z), (hx + sx * (kx + 0.022), ball.y, ball.z), kr, "LeftFoot", FRM,
              segs=8)                                                                       # outer knuckle
    k.cyl((hx - kx + 0.002, ball.y, ball.z), (hx + kx - 0.002, ball.y, ball.z), kr, "LeftToes", TIT, segs=8)  # centre knuckle
    k.box((hx, (ball.y + y1 - 0.003) / 2, 0.0325), (2 * kx - 0.01, ball.y - y1 + 0.003, 0.025), "LeftToes", FRM)  # its web
    k.cyl((hx - kx - 0.026, ball.y, ball.z), (hx + kx + 0.026, ball.y, ball.z), 0.006, "LeftToes", JNT, solid=False)  # pin
    k.obox((hx, y1, 0.0065), (hx, -0.2, 0.0065), 0.122, 0.013, UP, "LeftToes", BLK)              # toe sole
    toe = [(y1, 0.056, 0.013, 0.05), (-0.185, 0.054, 0.013, 0.042), (-0.2, 0.046, 0.013, 0.03)]
    shell = loft([[(hx + u, y, v) for u, v in sym([(0.0, zb_), (w, zb_), (w, zt_ - 0.012), (w - 0.016, zt_), (0.0, zt_)])]
                  for y, w, zb_, zt_ in toe])
    carve(k, shell, "LeftToes", PRI, boxes=[((hx, -0.2, 0.03), (0.07, 0.01, 0.006))])           # toe cap
    tz = 0.050 + (0.042 - 0.050) * (0.16 + y1) / (0.185 + y1)
    k.tube([(hx - 0.036, -0.16, tz), (hx - 0.036, -0.16, 0.062), (hx - 0.036, -0.205, 0.062), (hx + 0.036, -0.205, 0.062),
            (hx + 0.036, -0.16, 0.062), (hx + 0.036, -0.16, tz)], 0.0065, "LeftToes", SEC)  # toe bumper


def build_pistons(k, pistons, bones):
    """Barrel and rod each end in an eye that turns on a pin parallel to the driven hinge axis
    (the linkage moves in the hinge's plane). Pins belong to the mounts."""
    for p in pistons:
        if p.name.startswith("Right"):
            continue  # mirrored by the kit
        d = (p.b - p.a).normalized()
        if p.multi:
            # Rod-end bearings: each end is a housing around a spherical bearing (the ball stands
            # proud at the sides) that turns on the cross pin of a clevis on its mount, so the
            # strut can swing any way.
            ball, pin_ax = p.radius * 1.3, Vector((1, 0, 0))
            for bone, end in ((p.cylinder, p.a), (p.rod, p.b)):
                k.cyl(end - pin_ax * STRUT_EYE_HALF, end + pin_ax * STRUT_EYE_HALF, ball * 1.25, bone, FRM,
                      segs=6, solid=False)
                k.sphere(end, ball, bone, JNT)
            k.cyl(p.a + d * ball * 1.1, p.a + d * p.cyl_len, p.radius, p.cylinder, SEC, solid=False)
            k.cyl(p.b - d * ball * 1.1, p.b - d * p.rod_len, p.radius * 0.55, p.rod, JNT, segs=6, solid=False)
            continue
        ax = hinge_of(bones, p.rod_parent).hinge_axis
        eye = p.radius * 1.15
        k.cyl(p.a - ax * p.radius, p.a + ax * p.radius, eye, p.cylinder, FRM, segs=6, solid=False)  # barrel eye
        k.cyl(p.a + d * eye * 0.7, p.a + d * p.cyl_len, p.radius, p.cylinder, SEC, solid=False)
        k.cyl(p.a + d * (p.cyl_len - 0.006), p.a + d * p.cyl_len, p.radius * 1.12, p.cylinder, ALU, segs=6, solid=False)  # gland
        k.cyl(p.b - d * eye * 0.7, p.b - d * p.rod_len, p.radius * 0.55, p.rod, JNT, segs=6, solid=False)
        k.cyl(p.b - ax * p.radius, p.b + ax * p.radius, eye * 0.85, p.rod, FRM, segs=6, solid=False)  # rod eye
        for bone, pin in ((p.cyl_parent, p.a), (p.rod_parent, p.b)):
            k.cyl(pin - ax * (p.radius + 0.008), pin + ax * (p.radius + 0.008), 0.005, bone, JNT, segs=4,
                  solid=False)


# --------------------------------------------------------------------------------------------
# Sweeps the redesign added: the waist's ball-jointed stages and the clavicle in its socket
# --------------------------------------------------------------------------------------------

def check_waist_clearance(kit, bones):
    """Sweep the waist's three ball-jointed stages (Spine, Chest, UpperChest) together over every corner
    of their limit boxes: no part of a stage may hit the pelvis or a stage below it that it does not
    already touch at rest (the balls in their sockets)."""
    names, poses = chain_poses(bones, "Hips", "UpperChest", steps=(0.0, 1.0))
    near = lambda q: q.lo.z < 1.32  # the chest's upper parts never come near the waist
    groups = {n: [q for q in kit.parts if q.bone == n and near(q)] for n in ["Hips"] + names}
    order = ["Hips"] + names
    pairs = [(a, b, m, s) for i, a in enumerate(order) for b in order[i + 1:] for m in groups[b] for s in groups[a]
             if not m.touches(s, tol=0.0)]
    problems = []
    for pose in poses:
        xf = {n: pose[i] for i, n in enumerate(names)}
        cache = {}

        def moved(q):
            if q.bone == "Hips":
                return q
            if id(q) not in cache:
                r, t = xf[q.bone]
                cache[id(q)] = Part(q.bone, q.line, [r @ v + t for v in q.verts], q.faces, q.convex)
            return cache[id(q)]
        for a, b, m, s in pairs:
            if moved(m).touches(moved(s), tol=0.0):
                problems.append(f"{m.bone} (line {m.line}) hits {s.bone} (line {s.line}) in a waist bend")
    if problems:
        raise SystemExit(f"[{NAME}] waist clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


def check_clavicle_clearance(kit, bones):
    """Sweep the clavicle (shrug and reach) through its limit box with the arm at rest: the shoulder
    motor, its fins and the arm's root must stay clear of the chest's socket."""
    cl = bones["LeftShoulder"]
    rest = Matrix((cl.hinge_axis, cl.axis, cl.flex)).transposed()
    moving = [q for q in kit.parts if q.bone in descendants(bones, "LeftShoulder") | {"LeftShoulderPitch", "LeftShoulderRoll"}
              and q.lo.x < 0.27]
    static = [q for q in kit.parts if q.bone == "UpperChest"]
    # Seated: touching at rest, or embedded in it (the clavicle strut is mounted inside the chest's solid).
    seated = {(id(m), id(s)) for m in moving for s in static
              if m.touches(s, tol=0.0) or any(s.buried(v) for v in m.verts)}
    (xl, xh), (zl, zh) = cl.limits["x"], cl.limits["z"]
    problems = []
    for ex in (xl + (xh - xl) * i / 4 for i in range(5)):
        for ez in (zl + (zh - zl) * i / 4 for i in range(5)):
            r = rest @ Euler((math.radians(ex), 0.0, math.radians(ez)), "XYZ").to_matrix() @ rest.transposed()
            for m in moving:
                mv = Part(m.bone, m.line, [cl.head + r @ (v - cl.head) for v in m.verts], m.faces, m.convex)
                for s in static:
                    if (id(m), id(s)) not in seated and mv.touches(s, tol=0.0):
                        problems.append(f"{m.bone} (line {m.line}) hits UpperChest (line {s.line}) at clavicle x {ex:.0f} z {ez:.0f}")
    if problems:
        raise SystemExit(f"[{NAME}] clavicle clearance failed:\n  " + "\n  ".join(dict.fromkeys(problems)))


# --------------------------------------------------------------------------------------------
# Scene, materials, rig
# --------------------------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def build_materials():
    for slot, (color, metallic, roughness, emission) in MATERIALS.items():
        mat = bpy.data.materials.new(slot)
        if mat.node_tree is None:  # pre-5.x; use_nodes is deprecated in 5.x
            mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission:
            bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission
        mat.diffuse_color = (*color, 1.0)


def stage_frame(bones, side, pivot, direction, roll_to):
    """Head, direction and roll vector of a mechanical stage bone (mirrored for the right side)."""
    arm, fore, leg, foot = (bones[f"{side}{n}"] for n in ("UpperArm", "LowerArm", "UpperLeg", "Foot"))
    head = {"shoulder": arm.head, "elbow": fore.head, "hip": leg.head, "ankle": foot.head}[pivot]
    named = {"arm": arm.axis, "arm_flex": arm.flex, "forearm": fore.axis, "forearm_flex": fore.flex,
             "foot": foot.axis, "foot_flex": foot.flex}
    d = named[direction] if isinstance(direction, str) else Vector(direction)
    r = named[roll_to] if isinstance(roll_to, str) else Vector(roll_to)
    if side == "Right" and not isinstance(direction, str):
        d, r = mirror_vec(d), mirror_vec(r)
    return head, d.normalized(), r


def build_rig(bones, pistons):
    arm = bpy.data.armatures.new("RIG_Tensor")
    rig = bpy.data.objects.new("RIG_Tensor", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)

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

    for b in bones.values():
        add(b.name, b.head, b.tail, b.parent, b.flex)
    for side in ("Left", "Right"):
        flip = side == "Right"
        for stage in MECH_STAGES:
            name, parent, pivot, direction, roll_to = stage[:5]
            head, d, r = stage_frame(bones, side, pivot, direction, roll_to)
            add(name.replace("Left", side), head, head + d * 0.05, parent.replace("Left", side), r)
        for name, parent, pivot, offset in MARKERS:
            head = bones[f"{side}UpperLeg"].head if pivot == "hip" else J[pivot]
            off = mirror_vec(offset) if flip else Vector(offset)
            add(name.replace("Left", side), head, head + off, parent.replace("Left", side), deform=False)
    for p in pistons:
        d = (p.b - p.a).normalized()
        add(p.cylinder, p.a, p.a + d * p.cyl_len, p.cyl_parent)
        add(p.rod, p.b, p.b - d * p.rod_len, p.rod_parent)
        add(p.anchor_a, p.a, p.a + Vector((0, 0, 0.02)), p.cyl_parent, deform=False)
        add(p.anchor_b, p.b, p.b + Vector((0, 0, 0.02)), p.rod_parent, deform=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    for b in bones.values():
        pb = rig.pose.bones[b.name]
        pb.rotation_mode = rot_order(b.name)
        if not b.limits:
            continue
        c = pb.constraints.new("LIMIT_ROTATION")
        c.owner_space = "LOCAL"
        for i, ax in enumerate("xyz"):
            if ax in b.limits:
                lo, hi = b.limits[ax]
                setattr(c, f"use_limit_{ax}", True)
                setattr(c, f"min_{ax}", math.radians(lo))
                setattr(c, f"max_{ax}", math.radians(hi))
                if lo == hi == 0:
                    pb.lock_rotation[i] = True
    for side in ("Left", "Right"):
        for name, _, _, direction, _, kind, target, head_tail, lock, track in MECH_STAGES:
            c = rig.pose.bones[name.replace("Left", side)].constraints.new(kind)
            c.target, c.subtarget, c.head_tail = rig, target.replace("Left", side), head_tail
            if side == "Right" and direction == (0, 0, 1) and track == "TRACK_X":
                track = "TRACK_NEGATIVE_X"  # mirrored yaw stage: its +X points inboard
            if lock:
                c.lock_axis = lock
            c.track_axis = track
    for p in pistons:
        # Anchors are separate bones so the two aims don't form a dependency cycle.
        for bone, target in ((p.cylinder, p.anchor_b), (p.rod, p.anchor_a)):
            c = rig.pose.bones[bone].constraints.new("DAMPED_TRACK")
            c.target, c.subtarget, c.track_axis = rig, target, "TRACK_Y"
    return rig


def skin(obj, rig):
    obj.parent = rig
    obj.modifiers.new("Armature", "ARMATURE").object = rig


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def select_only(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


# --------------------------------------------------------------------------------------------
# Test poses for preview.py (bone: local XYZ Euler degrees; right side mirrored automatically)
# --------------------------------------------------------------------------------------------

def finger_pose(curl, thumb):
    pose = {}
    for finger in FINGERS:
        for seg, scale in zip(FINGER_SEGMENTS, (1.0, 1.1, 0.8)):
            pose[f"Left{finger}{seg}"] = {"rot": (curl * scale, 0, 0)}
    for seg, scale in zip(THUMB_SEGMENTS, (0.6, 1.0, 1.0)):
        pose[f"LeftThumb{seg}"] = {"rot": (thumb * scale, 0, 0)}
    return pose


POSES = {
    "idle": {"LeftUpperArm": {"rot": (8, 0, -78)}, "LeftLowerArm": {"rot": (25, 0, 0)},
             **finger_pose(25, 15)},
    # crouch and wide: leg angles solved by animate.py's IK (feet planted flat).
    "crouch": {"Hips": {"loc": (0, -0.27, -0.12)}, "Spine": {"rot": (15, 0, 0)}, "Chest": {"rot": (10, 0, 0)},
               "Head": {"rot": (-20, 0, 0)},
               "LeftUpperLeg": {"rot": (55.7, 0, 0)}, "LeftLowerLeg": {"rot": (90.0, 0, 0)},
               "LeftFoot": {"rot": (34.4, 0, 0)}, "LeftUpperArm": {"rot": (40, 0, -60)},
               "LeftLowerArm": {"rot": (60, 0, 0)}, **finger_pose(40, 20)},
    "grip": {"LeftUpperArm": {"rot": (20, 0, -70)}, "LeftLowerArm": {"rot": (100, -40, 0)},  # forearm rolled
             "LeftHand": {"rot": (0, -20, 0)}, **finger_pose(80, 50)},
    "straddle": {"Hips": {"loc": (0, -0.5305, 0)}, "LeftUpperLeg": {"rot": (0, 0, 70)}, "LeftFoot": {"rot": (0, -15, 0)},
                 "LeftUpperArm": {"rot": (60, 0, -50)}, "LeftLowerArm": {"rot": (20, 0, 0)}},
    "wide": {"Hips": {"loc": (0, -0.15, 0)}, "LeftUpperLeg": {"rot": (32.4, 0.1, 5.0)},
             "LeftLowerLeg": {"rot": (66.6, 0, 0)}, "LeftFoot": {"rot": (34.2, -5.0, 0)},
             "LeftUpperArm": {"rot": (70, 0, -20)}, "LeftLowerArm": {"rot": (35, 0, 0)}},
    "look": {"Neck": {"rot": (0, 50, 0)}, "Head": {"rot": (25, 0, 0)},
             "LeftUpperArm": {"rot": (8, 0, -78)}, "LeftLowerArm": {"rot": (25, 0, 0)}},
}


POSE_VIEWS = {"straddle": ["front", "back", "front_left", "rear_right"]}  # others: front_left only

def check_poses(bones):
    """Every preview pose must sit inside the joint limits and limit envelopes it demonstrates."""
    problems = []
    for pose, entries in POSES.items():
        for bone, entry in entries.items():
            rot = entry.get("rot")
            if rot is None or bone not in bones:
                continue
            for i, ax in enumerate("xyz"):
                lo, hi = bones[bone].limits.get(ax, (-180, 180))
                if not lo - 1e-6 <= rot[i] <= hi + 1e-6:
                    problems.append(f"{pose}: {bone} {ax} {rot[i]} outside ({lo}, {hi})")
            if not in_envelope(bone, rot):
                problems.append(f"{pose}: {bone} {rot} outside its limit envelopes")
    if problems:
        raise SystemExit(f"[{NAME}] preview poses out of range:\n  " + "\n  ".join(problems))


def mirrored_pose(pose):
    out = {}
    for bone, entry in pose.items():
        out[bone] = entry
        if bone.startswith("Left"):
            x, y, z = entry.get("rot", (0, 0, 0))
            out[mirror_name(bone)] = {"rot": (x, -y, -z)}
    return out


# --------------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------------

def export(objects, stem):
    prepare_export(objects, HERE, stem)
    select_only(objects)
    bpy.ops.export_scene.fbx(
        filepath=str(HERE / f"{stem}.fbx"),
        use_selection=True,
        object_types={"MESH", "ARMATURE", "EMPTY"},
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=False,
        use_mesh_modifiers=False,
        mesh_smooth_type="OFF",  # export split normals as authored
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=True,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
    )
    bpy.ops.export_scene.gltf(
        filepath=str(HERE / f"{stem}.glb"),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_skins=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
    )


def write_rig_json(bones, pistons, tris):
    def vec(v):
        return [round(c, 4) for c in v]

    data = {
        "name": NAME,
        "height_m": HEIGHT,
        "space": "Blender coords: +Z up, faces -Y, left = +X. glTF/Godot: (x, z, -y). "
                 "Limits are degrees about each bone's local axes; local X is the flex axis. "
                 "limit_envelopes_deg: the pose must lie inside one of these [x, y, z] boxes (coupled limits).",
        "team_materials": list(TEAM_MATERIALS),
        "team_presets": {team: {m: list(c) for m, c in cols.items()} for team, cols in TEAM_COLORS.items()},
        "materials": SLOTS,
        "uv_atlases": {"materials": SLOTS, "resolution": 2048,
                       "note": "Unique 0..1 layouts shared by body and head variants; "
                               "each original material has its own atlas. Source finishes and emission are unchanged."},
        "triangles": tris,
        "head_variants": {"default": DEFAULT_HEAD, "note": "one mesh per head, skinned to Head; show one, hide the rest",
                          "meshes": {v: head_mesh_name(v) for v in HEAD_VARIANTS}},
        "upper_body_variants": {"default": "default", "note": "show one upper body; shared pelvis, limbs, neck and rig",
                                "meshes": {v: upper_body_mesh_name(v) for v in UPPER_BODY_VARIANTS}},
        "bones": [{"name": b.name, "parent": b.parent, "head": vec(b.head), "tail": vec(b.tail),
                   "flex_axis": vec(b.hinge_axis), "limits_deg": b.limits, "euler_order": rot_order(b.name),
                   **({"limit_envelopes_deg": [[list(r) if b.name.startswith("Left") else [-r[1], -r[0]] if i else list(r)
                                                for i, r in enumerate(box)] for box in LIMIT_ENVELOPES[b.name.replace("Right", "Left")]]}
                      if b.name.replace("Right", "Left") in LIMIT_ENVELOPES else {})} for b in bones.values()],
        "pistons": [{"cylinder": p.cylinder, "rod": p.rod,
                     "cylinder_parent": p.cyl_parent, "rod_parent": p.rod_parent,
                     "cylinder_aims_at": p.rod, "rod_aims_at": p.cylinder,
                     "stroke_m": [round(p.stroke[0], 4), round(p.stroke[1], 4)],
                     "cylinder_length_m": round(p.cyl_len, 4), "rod_length_m": round(p.rod_len, 4),
                     "min_overlap_m": round(p.overlap, 4)} for p in pistons],
        "mech_stages": [{"bone": st[0].replace("Left", side), "parent": st[1].replace("Left", side),
                         "driver": st[5].lower(), "target": st[6].replace("Left", side), "target_point": "tail",
                         "lock_axis": st[8],
                         "track_axis": "TRACK_NEGATIVE_X" if side == "Right" and st[3] == (0, 0, 1) else st[9]}
                        for side in ("Left", "Right") for st in MECH_STAGES],
        "markers": [{"bone": m[0].replace("Left", side), "parent": m[1].replace("Left", side)}
                    for side in ("Left", "Right") for m in MARKERS],
        "gizmos": [{"name": "FlagMount", "bone": "UpperChest", "origin": vec(FLAG_MOUNT), "forward": [0, -1, 0],
                    "up": [0, 0, 1], "godot": "-Z forward, +Y up",
                    "note": "the middle of the grab handle bar's axis on the power pack: put a carried CTF flag's "
                            "BackMount here (the same axes), its hook's pocket on the bar"}],
    }
    RIG_JSON_PATH.write_text(json.dumps(data, indent=2))


def main():
    reset_scene()
    build_materials()
    bones = resolve_bones()
    pistons = resolve_pistons(bones)
    rig = build_rig(bones, pistons)

    # Full checks with the default head on; every other head variant is checked on the neck and
    # upper body it sits on (connectivity, head hydraulics, head pitch and neck yaw sweeps, axle).
    check_kit = Kit(detail=1.0)
    build_torso(check_kit)
    build_neck(check_kit)
    build_head(check_kit, DEFAULT_HEAD)
    build_arm(check_kit)
    build_hand(check_kit, bones)
    build_leg(check_kit)
    build_pistons(check_kit, pistons, bones)
    check_piston_clearance(pistons, bones, check_kit.solids, check_kit.parts)
    check_bar_clearance(bones, check_kit.solids, check_kit.tubes)
    check_connectivity(check_kit, bones, pistons)
    check_motion_clearance(check_kit, bones)
    check_waist_clearance(check_kit, bones)
    check_clavicle_clearance(check_kit, bones)
    check_joint_alignment(check_kit, bones)
    check_poses(bones)
    head_pistons = [p for p in pistons if "Head" in p.name]
    for variant in HEAD_VARIANTS:
        if variant == DEFAULT_HEAD:
            continue
        vk = Kit(detail=1.0)
        build_torso(vk)
        build_neck(vk)
        build_head(vk, variant)
        build_pistons(vk, head_pistons, bones)
        check_piston_clearance(head_pistons, bones, vk.solids, vk.parts)
        check_bar_clearance(bones, vk.solids, vk.tubes)
        check_connectivity(vk, bones, head_pistons)
        check_motion_clearance(vk, bones)
        check_joint_alignment(vk, bones, only={"Neck", "Head"})
        print(f"[{NAME}] head '{variant}' passed its checks")

    for variant in UPPER_BODY_VARIANTS[1:]:
        vk = Kit(detail=1.0)
        build_torso(vk, variant)
        build_neck(vk)
        build_arm(vk)
        build_hand(vk, bones)
        build_leg(vk)
        build_pistons(vk, pistons, bones)
        # Test every head against every upper casting, including its hydraulics.
        for head in HEAD_VARIANTS:
            hk = Kit(detail=1.0)
            build_head(hk, head)
            vk.parts.extend(hk.parts)
            check_motion_clearance(vk, bones)
            del vk.parts[-len(hk.parts):]
            hk.bm.free()
        build_head(vk, DEFAULT_HEAD)
        check_piston_clearance(pistons, bones, vk.solids, vk.parts)
        check_bar_clearance(bones, vk.solids, vk.tubes)
        check_connectivity(vk, bones, pistons)
        check_waist_clearance(vk, bones)
        check_clavicle_clearance(vk, bones)
        check_joint_alignment(vk, bones, only={"Neck"})
        vk.bm.free()
        print(f"[{NAME}] upper body '{variant}' passed its checks")

    body_kit = Kit(detail=1.0)
    build_pelvis(body_kit)
    build_neck(body_kit)
    build_arm(body_kit)
    build_hand(body_kit, bones)
    build_leg(body_kit)
    build_pistons(body_kit, pistons, bones)
    joints = [j for j in rotary_joints(bones) if j[0] != "LeftThumbMetacarpal"]  # pure single-axis only
    body = body_kit.to_object(f"SK_{NAME.capitalize()}", joints=joints)
    uppers = {}
    for variant in UPPER_BODY_VARIANTS:
        uk = Kit(detail=1.0)
        build_upper_body(uk, variant)
        uppers[variant] = uk.to_object(upper_body_mesh_name(variant))
    heads = {}
    for variant in HEAD_VARIANTS:
        hk = Kit(detail=1.0)
        build_head(hk, variant)
        heads[variant] = hk.to_object(head_mesh_name(variant))

    for obj in (body, *heads.values(), *uppers.values()):
        skin(obj, rig)

    # Every original material keeps its faces and finish, with its own UV atlas.
    prepare_export([body, *heads.values(), *uppers.values()], HERE, NAME)

    tris = {"body": triangles(body)}
    budgets = {"body": TRI_BUDGET}
    for variant, obj in heads.items():
        tris[f"head_{variant}"], budgets[f"head_{variant}"] = triangles(obj), HEAD_BUDGET
    for variant, obj in uppers.items():
        tris[f"upper_body_{variant}"], budgets[f"upper_body_{variant}"] = triangles(obj), UPPER_BODY_BUDGET
        if triangles(body) + triangles(obj) > TRI_BUDGET:
            raise SystemExit(f"[{NAME}] assembled body '{variant}' exceeds {TRI_BUDGET} triangles")
    for part, count in tris.items():
        print(f"[{NAME}] {part}: {count} tris (budget {budgets[part]})")
    over = {k: v for k, v in tris.items() if v > budgets[k]}
    if over:
        raise SystemExit(f"[{NAME}] over triangle budget: {over}")
    for p in pistons:
        if p.name.startswith("Left"):
            print(f"[{NAME}] {p.name}: stroke {p.stroke[0]:.3f}-{p.stroke[1]:.3f} m, "
                  f"barrel/rod {p.cyl_len:.3f} m, min overlap {p.overlap:.3f} m")

    flag_mount = build_flag_mount(rig)
    export([rig, body, *heads.values(), *uppers.values(), flag_mount], BODY_STEM)
    write_rig_json(bones, pistons, tris)

    # Preview metadata, read generically by preview.py.
    rig["preview_poses"] = json.dumps({k: mirrored_pose(v) for k, v in POSES.items()})
    rig["preview_pose_views"] = json.dumps(POSE_VIEWS)
    bpy.context.scene["preview_team_colors"] = json.dumps(TEAM_COLORS)
    bpy.context.scene["preview_variants"] = json.dumps(
        {"head": {"default": DEFAULT_HEAD, "objects": {v: o.name for v, o in heads.items()}},
         "upper_body": {"default": "default", "objects": {v: o.name for v, o in uppers.items()}}})
    for variant, obj in uppers.items():
        if variant != "default":
            obj.hide_render = True
            obj.hide_set(True)
    for variant, obj in heads.items():  # renders show the default head; the engine swaps the others in
        if variant != DEFAULT_HEAD:
            obj.hide_render = True
            obj.hide_set(True)

    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backups on rebuild
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)
    print(f"[{NAME}] saved {BLEND_PATH}")
    print(f"[{NAME}] exported {BODY_STEM}.glb/.fbx, {RIG_JSON_PATH.name}")


if __name__ == "__main__":
    if "--uv-only" in sys.argv:
        from material_uv import refresh_asset
        refresh_asset(HERE)
    else: main()
