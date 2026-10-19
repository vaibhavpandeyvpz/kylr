"""Pistol - a suppressed sidearm for KYLR, modelled, rigged and animated from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/weapons/pistol/model.py

Produces, next to this script:
    pistol.blend             source scene (the pistol, its cartridge and preview-only gizmo markers),
                             opened by preview.py and animate.py
    pistol.glb / .fbx        SK_Pistol and SK_PistolAmmo skinned to RIG_Pistol, with the actions idle,
                             fire, fire_empty, slide_release, mag_release and mag_insert, and the gizmos
                             Muzzle, ShellEject, CompVent, HookVent, LeftHandSocket, RightHandSocket
    pistol_ammo.glb / .fbx   SM_PistolAmmo: the cartridge on its own, upright, origin at its bottom
                             centre, for the in-game ammo pickup
    pistol_rig.json          joints, animations, gizmos, hand sockets, cartridge

Design: a full-size pistol at 1.25 scale with a single barrel and a fat front: a suppressor housing
lofted in one piece along the bore, wider, taller and longer than the slide, a military yellow shell with a
vaulted crown over flat flanks, its top level and then raked down to the nose, and its front hooking
down into a leg (the suppressor's expansion chamber) whose rounded toe lines up with the cartridge's
bottom: the support hand wraps that hook. The titanium suppressor cap (threaded, spanner-notched, six exit
vents) stands out of the front face over the hook; exhaust slots are cut under the hook and finger
grooves across its front. The barrel runs in the housing's bore, its chamber block at the front of the
tunnel in the housing's rear where the slide's nose (its breech block) runs; bronze cooling fins round
the barrel show through a bezelled window in each flank, and move with it as it recoils. The slide
(matte titanium) rides the frame's top behind the housing and recoils 42 mm on two stainless steel guide rods
fixed in the tunnel; the barrel travels its first centimetre with it (short recoil), then stops while
the slide runs on. The spent case leaves upward through the ejection port in the crown, over the
chamber.
The left flank carries the gas regulator's rotary dial (bronze ring, slotted stainless steel rotor; user: moved from the
right), fed by a gas line from the expansion chamber, in its lower band, and the raised display console above. A reflex sight sits on
the crown ahead of the port, compensator slots across the raked nose. The cartridge, as wide as the housing, fills the
space behind the hook under it: slots through its flanks show the staggered rounds, a charge gauge
on its power cell is the right side's one light, and a sliding catch in the trigger guard's front bar
holds it. The lower frame (titanium, bevelled) is one piece: the trigger guard from behind the cartridge
round under the trigger (its bottom bar stops just short of the curled fingers: they lie flush along the
grip's front, so a bar joining it would pass through one), the trigger block with the small curved trigger, the grip's core with
black textured panels, finger grooves, the web relief, and a lanyard hole in the pommel. The upper
frame under the slide carries the external hammer between its rear cheeks (double action: the
trigger cocks and drops it, the slide cams it back and it rides home with it) and the slide stop lever
on its left flank, which rises into a notch in the slide to hold it open after the last round.
Finish: military yellow, matte titanium, matte and metallic black, stainless steel and bronze.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a joint axis
misses its rotor or bearing, a slide leaves its guide, a palm would sink into a grip, the gun leaves
its size envelope, or anything collides through any animation frame or across the joints' ranges.
Conventions: 1 unit = 1 m, Z up, the muzzle points -Y (forward), the origin is on the gun's bottom
plane (the grip's pommel) midway along it, so the item table's and the weapon holder's WeaponMount takes it by its bottom.
Rest pose: slide and barrel home, hammer down on the firing pin, trigger forward, slide stop down,
cartridge in, catch out.
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
    'M_Secondary': 'Diffuse',
}

import json
import math
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

NAME = "pistol"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # Pistol

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000       # the pistol (SK_Pistol)
AMMO_BUDGET = 1_500      # the cartridge (SK_PistolAmmo / SM_PistolAmmo), on its own budget
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming

# Size: every weapon fits a 0.25 (wide) x 0.75 (long) x 0.35 m (high) envelope, its bottom on z = 0,
# centred along its length (check_envelope). The pistol is a full-size pistol's proportions at 1.25.
WEAPON_MAX = (0.25, 0.75, 0.35)

BORE_Z = 0.152                         # the bore axis

# The slide (bone Slide): its nose (the breech block, its front face the breech face) runs in the
# housing's tunnel, its body rides the frame's top behind the housing. It recoils SLIDE_TRAVEL back.
SLIDE_Y = (-0.0405, 0.137)             # its breech face and rear face
SLIDE_W = 0.0165                       # its half-width
SLIDE_Z = (0.130, 0.1735)              # its underside (on the frame's top) and top
SLIDE_R = 0.0055                       # its top corners' radius
SLIDE_CHAMFER = 0.008                  # its rear top edge, chamfered at 45 deg
SLIDE_TRAVEL = 0.042                   # full recoil: the breech face 2 mm behind the cartridge's top round
SERRATIONS = ((0.092, 0.0062, 5), (0.1345, 0.1665), 0.0012)  # rear cocking grooves: first y, pitch, count; z; depth
POCKETS = ((0.043, 0.056, 0.069), 0.1585, 0.0032, 0.0025)  # lightening pockets in both flanks: y, z, radius, depth
FRONT_SERRATIONS = (0.0140, 0.0050, 3)  # and front ones, just behind the housing: first y, pitch, count
FIRING_PIN = 0.0035                    # the firing pin's cap on the rear face, which the hammer strikes

# The housing: one military yellow shell lofted along the bore (housing_ring): a vaulted crown over flat flanks,
# each flank stepped in along its length over STEP (the upper flank carries the windows and the
# display, the lower band the dial and the support hand's palm), a flat bottom level over the
# cartridge; its top level from the rear face to NOSE[0], then falling straight by NOSE[1] to the front
# face; its front edges chamfered EDGE all round. Under its front hangs the hook (the expansion chamber,
# metallic black, lofted on its own) down to HOOK[1], its toe rounded HOOK[2]: the black band of the hook
# and the cartridge under the military yellow runs in one straight line. Its tunnel (the slide's section, 0.5 mm
# clear) runs from its rear face to the chamber block's front.
HOUSING_Y = (-0.140, 0.0075)           # front face, rear face (the tunnel's mouth)
HOUSING_W = 0.031                      # half-width
HOUSING_Z = (0.100, 0.181, 0.190)      # bottom, the crown's springing line, the crown's top
HOUSING_R = (0.004, 0.004)             # the bottom's and the springing line's fillets
EDGE = 0.004                           # the front edges' chamfer
STEP = (0.1352, 0.0018)                # the flanks' step: its height, how far the upper flank is set in
W_UP = HOUSING_W - STEP[1]             # the upper flank
FLANK_VENTS = ((-0.1305, -0.1265, -0.1225), 0.0022, (0.1495, 0.1685), 0.003)  # the suppressor's gas vents in
                                       # both upper flanks at the front: y, width, z, depth
NOSE = (-0.110, 0.010)                 # the top falls this much from y NOSE[0] to the front face
HOOK = ((HOUSING_Y[0], -0.112), 0.045, 0.012)  # the hook: y (front, rear face), bottom, toe radius
TUNNEL = 0.0005                        # the tunnel's clearance round the slide
CAP = (-0.157, -0.138, 0.0175)         # the suppressor's end cap: front, rear (in a counterbore), radius
COMP = ((-0.132, -0.125, -0.118), 0.011, 0.0028, 0.005)  # compensator slots across the raked top: y, half-length, width, depth
HOOK_VENTS = ((0.058, 0.067, 0.076), 0.017, 0.0032, 0.006)  # exhaust slots across the hook's front face: z, half-length,
                                       # height, depth (the expansion chamber vents forward, clear of the support hand)
EJECT_PORT = ((-0.046, -0.006), 0.0075)  # the ejection port through the crown into the tunnel, over the chamber: y, half-width
FIN_WINDOW = ((-0.110, -0.076), (0.1510, 0.1660))  # the windows onto the barrel's fins, both flanks: y, z (centred
                                       # on the display's and the vents' line, user)
FIN_CAVITY = (-0.116, 0.0165)          # the cavity round the fins: front (y; it runs back into the tunnel), radius
DISPLAY = ((-0.036, -0.004), (0.148, 0.168), 15)  # the display console on the left flank: y, z, tilt up (deg)
DIAL = (-0.088, 0.1195, 0.012)         # the gas regulator's dial, centred on the left flank's lower band (user): y, z, radius
SIGHT = ((-0.098, -0.068), 0.0085, 0.011)  # the reflex sight on the crown, ahead of the port: y, half-width, height

# The barrel (bone Barrel): a chamber block at the tunnel's front and a tube in the housing's bores (a
# sliding fit), bronze cooling fins round it in the cavity behind the windows; it recoils RECOIL with
# the slide, locked to its breech face, then stops.
BARREL_R, BARREL_BORE = 0.0085, 0.0056
GUIDE_R = BARREL_R + 0.00005
CHAMBER = ((-0.0625, SLIDE_Y[0]), 0.0115)  # the chamber block: y, half-size (square, chamfered)
BARREL_FRONT = -0.130                  # its front end, in the bore ahead of the cavity
FINS = (-0.1090, 0.0056, 6, 0.0150, 0.0018)  # the fins: first y, pitch, count, radius, thickness
RECOIL = 0.010                         # 1 cm back (user rule), on the slide's first centimetre
TUNNEL_FRONT = CHAMBER[0][0] - 0.001   # the tunnel's front wall, 1 mm ahead of the chamber block
RODS = (0.0142, 0.1355, 0.0018, (TUNNEL_FRONT - 0.001, 0.012))  # the recoil guide rods: x, z, radius, y
ROD_BORE = (0.0022, 0.016)             # their bores in the slide's nose: radius, bottom (y)

# The upper frame (titanium): under the slide from the housing's rear face to the hammer.
FRAME_Y = (HOUSING_Y[1], 0.142)
FRAME_W = 0.0150
FRAME_Z = (0.113, SLIDE_Z[0])          # its belly, its top (the slide's rails)
BELLY = FRAME_Z[0]

# The cartridge (bone Mag): as wide as the housing, from the hook's rear face to the trigger guard, its
# top against the housing's bottom and its bottom on the hook's line. Its rear part holds the rounds
# (a staggered double stack, the top rounds up its tongue in the housing's feed opening to the lips
# under the slide), seen through slots in both flanks; its front part is the power cell, its charge
# gauge on the right flank.
PACK_Y = (HOOK[0][1] + 0.0005, 0.007)
PACK_W = HOUSING_W
PACK_Z = (HOOK[1], HOUSING_Z[0] - 0.0005)
LOW_R = 0.012                          # the lower edges of the hook and the cartridge: true arcs (the support palm's seat)
CAVITY = ((-0.0365, -0.0003), 0.021, 0.050)  # the rounds' cavity: y, half-width, floor
SLOTS_Y = ((-0.031, -0.023, -0.015, -0.007), 0.0045, (0.061, 0.094))  # the slots onto the rounds: y, width, z
GAUGE = ((-0.100, -0.058), (0.066, 0.076))  # the charge gauge on the right flank: y, z
CHANNEL = ((-0.0350, -0.0005), 0.0138)  # the tongue's channel into the housing: y, half-width
TONGUE = ((-0.0347, -0.0008), 0.0135, (PACK_Z[1] - 0.001, 0.1265))  # the cartridge's tongue: y, half-width, z
ROUND = (0.0055, 0.033)                # a round: radius, length
TOP_ROUND_Z = SLIDE_Z[0] - 0.0005 - ROUND[0]  # the top round's axis, in the feed lips under the slide
MAG_TRAVEL = 0.020                     # the cartridge drops this far along the hook's rear face before it is free
# The catch (bone MagCatch): a cross bar sliding in a slot through the trigger guard's front bar, its tooth
# through the bar's front skin in a notch in the cartridge's rear face, its finger tab in the guard;
# pulled back (+y) it frees the cartridge.
GUARD_FRONT = (PACK_Y[1] + 0.0015, PACK_Y[1] + 0.0105)  # the guard's front bar: y
CATCH_Z = (0.0865, 0.0915)
CATCH_TRAVEL = 0.004

# The lower frame (titanium, bevelled): the trigger guard, the trigger block and the grip's core in one
# plate; black textured panels on the grip's sides.
LOWER_HALF, PANEL = 0.0145, 0.0022
GUARD_BOTTOM = (PACK_Z[0], 0.007, 0.050)  # the guard's bottom bar: its underside (the cartridge's line), thickness,
                                       # its rear end, short of the curled fingers
TRIGGER_BLOCK = ((GUARD_FRONT[1], 0.054), 0.094)  # the trigger's block under the belly: y, its bottom

# The hammer (bone Hammer): between the frame's rear cheeks on a pin; + turns it back. At rest it
# stands down on the firing pin's cap; the trigger's pull cocks it HAMMER_DA and trips it (double
# action); the recoiling slide cams it back, and it rides home against the slide's rear face.
HAMMER_PIVOT = (0.0, 0.1305, 0.1215)
HAMMER_OUTLINE = [(0.1275, 0.1160), (0.1350, 0.1165), (0.1450, 0.1290), (0.1480, 0.1500), (0.1470, 0.1590),
                  (0.1420, 0.1610), (0.1385, 0.1585), (0.1380, 0.1440), (0.1380, 0.1300), (0.1330, 0.1255)]
HAMMER_HUB, HAMMER_HALF = 0.0055, 0.0038
HAMMER_DA, HAMMER_MAX = 35, 80
HAMMER_SLOT = (0.0045, 0.1235)         # the cheeks' slot: half-width, front (y)
FRAME_WEB = ((0.102, 0.130), 0.1186)   # the frame's belly relieved behind the grip (y, up to z): the firing thumb's
                                       # first joints pass under it as they wrap round the grip

# The slide stop (bone SlideStop): a lever on a pin through the frame's left flank; + lifts its tip into
# the notch in the slide's lower left edge, which holds the slide open after the last round.
STOP_PIVOT = (0.0, 0.036, 0.1215)
STOP_X = (FRAME_W, FRAME_W + 0.0022)
STOP_TIP = (0.071, 0.076, 0.1285)      # the tip: y from, to, its top at rest
STOP_UP = 6.5
STOP_NOTCH = ((0.026, 0.038), 0.0145, 0.1335)  # the slide's notch at rest: y, inner x, top
_sy, (_t0, _t1, _tz) = STOP_PIVOT[1], STOP_TIP
STOP_ARM = [(_sy - 0.0045, 0.1185), (_t0 - 0.004, 0.1150), (_t1 + 0.0015, 0.1150), (_t1 + 0.0015, 0.1235), (_t1, _tz),
            (_t0, _tz), (_t0 - 0.001, 0.1255), (_sy + 0.004, 0.1250), (_sy - 0.0045, 0.1245)]  # its side outline (y, z)

# Hands: Tensor's hand bone frame (X = knuckle line, Y = wrist to knuckles, Z = out of the palm),
# its palm 0.094 long from 1 cm past the wrist, 0.09 wide, its face 0.016 off the bone line.
PALM = (0.010, 0.104, 0.045, 0.016)    # palm along Y (from, to), half-width along X, half-thickness
GRIP_ALONG = {"Left": 0.070, "Right": 0.070}  # the grip line from the wrist along Y
GRIP_RAKE = 15                         # the pistol grip's rake (deg)
GRIP_G = (0.0, 0.100, 0.050)           # the firing hand's centre on the pistol grip's axis
GRIP_HALF = (LOWER_HALF + PANEL, 0.023)  # pistol grip half-width (x: the core and its panel) and half-depth
WEB = (0.012, 0.030, 0.040, 0.062)     # the web relief: the backstrap cut to this depth (local y) from z 0.030
                                       # (full by 0.040) up the grip from the hand's centre
TRIGGER_REACH = 0.048                  # trigger face ahead of the grip axis, at the index finger's height
TRIGGER_PIVOT = (0.0, 0.0405, 0.1015)  # in the trigger block
TRIGGER_OUTLINE = [(0.0365, 0.0990), (0.0420, 0.0835), (0.0453, 0.0725), (0.0465, 0.0645), (0.0453, 0.0597),
                   (0.0485, 0.0587), (0.0510, 0.0655), (0.0485, 0.0835), (0.0440, 0.0990)]  # a small curved lever (y, z)
# (its face concave, leaning forward from the pivot, curving back under the index finger, its tip turned
# forward: user, the old lever's convex face and back-hooked tip looked the wrong way round)
TRIGGER_PULL = 12
# The support hand holds the cartridge from below, as the lightning gun's holds its forend (user): the palm
# up but canted LSUP_ROLL toward the gun's right, tangent to the lower left arc of the cartridge and the
# hook (their lower edges are true arcs, LOW_R) along a line from under the cartridge forward to the
# hook's sole, the fingers LSUP_TURN from straight ahead toward the right, up the far side. The wrist
# housing stays out beside the flank. Fitted where Tensor's arm puts the hand exactly (animations/retarget.py's
# hold over the pistol clips and aim poses) with his whole closed hand behind the front face, clear of the muzzle
# and the hook's exhaust vents (user: the fingers had reached past it), and under the flanks' gas vents.
LSUP_Y, LSUP_ROLL, LSUP_TURN = -0.039, 20, 55
# Tensor's left hand closed to GRIP_POSE["Left"], boxed in its Hand bone's frame (x, y, z ranges; measured from
# SK_Tensor): the fingers and the thumb, for check_hand_sockets' clearances.
HAND_BOXES = {"fingers": ((-0.0385, 0.0385), (0.0804, 0.1819), (-0.0084, 0.0598)),
              "thumb": ((-0.078, -0.030), (0.0136, 0.0806), (-0.0017, 0.0748))}
HAND_CLEAR = 0.002                     # the hand this far behind the front face and under the gas vents
# The grip pose for Tensor's hands on the sockets (exported; animations/retarget.py closes his hands to it):
# each finger's curl (proximal; intermediate x1.1, distal x0.8, as Tensor's finger_pose) and the
# thumb (metacarpal x, z; proximal = distal curl).
GRIP_POSE = {"Left": ({"Index": 10, "Middle": 19, "Ring": 24, "Little": 27}, (24, 25, 16)),
             "Right": ({"Index": 36, "Middle": 65, "Ring": 60, "Little": 42}, (42, -25, 50))}
# The support hand's grip on the ammo pack for a reload (user: every hand placement is a socket the animation plugs
# into, exported as AmmoHandSocket on the Mag bone; a wide grip, not a C cup): the palm flat on the pack's outer end
# (the face away from the gun), the fingers spread across it and over its far (right) edge, the thumb up its front;
# centred along the pack.
AMMO_ACROSS = (-1.0, 0.0, 0.0)   # the fingers' way across the pack (the left hand reaches over to its right edge)
AMMO_OUT = (0.0, 0.0, -1.0)   # its outer end (the way it leaves the gun)
AMMO_GRIP = 0.004                # the knuckles short of the pack's far edge (the fingers wrap over it)
AMMO_GRIP_POSE = ({"Index": 45, "Middle": 50, "Ring": 50, "Little": 45}, (25, 40, 15))  # spread, the thumb out

# Actions (30 fps). Nothing on a pistol moves at rest, so idle holds the rest pose (a loop for the
# game to sit in between shots).
ACT_F = 15
IDLE_F = 30
SHOT_F = 3                             # the hammer falls on the firing pin: the shot
EJECT_F = 5                            # the slide is fully back: the case leaves the window

SLIDE, BARREL, HAMMER, TRIGGER, STOP = "Slide", "Barrel", "Hammer", "Trigger", "SlideStop"
MAG, CATCH_BONE = "Mag", "MagCatch"

# slot: (base colour, metallic, roughness, emission strength[, alpha])
MATERIALS = {
    "M_Primary": ((0.521, 0.356, 0.076), 0.25, 0.5, 0.0),    # military yellow: the suppressor housing
    "M_Secondary": ((0.018, 0.018, 0.02), 0.2, 0.72, 0.0),   # matte black: grip panels, sights, dial boss
    "M_Frame": ((0.29, 0.29, 0.30), 1.0, 0.5, 0.0),          # matte titanium: slide, frames, barrel
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),         # stainless steel: pins, rods, trigger, rotor, bullets
    "M_Emissive": ((0.25, 0.85, 1.0), 0.0, 0.4, 6.0),        # the display's screen, the charge gauge
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.25, 0.0),         # the rounds' cases, the barrel's fins, the dial's ring
    "M_Glass": ((0.55, 0.75, 0.8), 0.0, 0.03, 0.0, 0.25),    # the display's cover, the sight's lens
    "M_Metal": ((0.15, 0.155, 0.165), 0.7, 0.45, 0.0),       # dark gunmetal grey: hook, cartridge, bezels, hammer
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, GLS, MTL = SLOTS


def grip_axes():
    """The pistol grip's frame: g up its axis (raked back at the bottom), f forward square to it."""
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))
    return Vector((0, -s, c)), Vector((0, -c, -s))


def hand_frame(side):
    """Tensor's hand bone frame gripping each handle: (wrist pivot, X, Y, Z). Z points out of the
    palm onto the grip, Y from the wrist to the knuckles, X = Y x Z along the knuckle line (the left
    thumb on -X, the right on +X). The grip line runs across the palm GRIP_ALONG from the wrist, the
    grip's surface on the palm's face."""
    if side == "Left":   # support hand under the front, palm up, tangent to the lower left arc
        t, r = math.radians(LSUP_TURN), math.radians(LSUP_ROLL)
        n = Vector((math.sin(r), 0.0, -math.cos(r)))
        grip = Vector((HOUSING_W - LOW_R, LSUP_Y, HOOK[1] + LOW_R)) + n * LOW_R
        z = -n
        y0 = Vector((-math.sin(t), -math.cos(t), 0.0))
        y, face = (y0 - z * y0.dot(z)).normalized(), 0.0
    else:                # firing hand on the pistol grip, thumb up, fingers round its front
        g, f = grip_axes()
        grip = Vector(GRIP_G)
        z, y, face = Vector((1, 0, 0)), f, GRIP_HALF[0]
    x = y.cross(z)
    wrist = grip - z * (face + PALM[3]) - y * GRIP_ALONG[side]
    return wrist, x, y, z


def eased(pairs):
    """Smoothstep keys on every frame through (frame, value) waypoints."""
    out = []
    for (f0, v0), (f1, v1) in zip(pairs, pairs[1:]):
        for f in range(f0, f1 + (1 if (f1, v1) == pairs[-1] else 0)):
            u = (f - f0) / (f1 - f0) if f1 > f0 else 1.0
            out.append((f, v0 + (v1 - v0) * u * u * (3 - 2 * u)))
    return out


def shaped(pairs, n):
    """Keys on every frame through (frame, value, ease) waypoints: 'out' fast then slowing
    (1 - (1 - u)^2), 'in' slow then fast (u^2), 'io' smoothstep; held to frame n."""
    out, fns = [], {"out": lambda u: 1 - (1 - u) ** 2, "in": lambda u: u * u, "io": lambda u: u * u * (3 - 2 * u)}
    for (f0, v0, _), (f1, v1, e) in zip(pairs, pairs[1:]):
        out += [(f, v0 + (v1 - v0) * fns[e]((f - f0) / (f1 - f0))) for f in range(f0, f1)]
    f_last, v_last = pairs[-1][:2]
    return out + [(f, v_last) for f in range(f_last, n + 1)]


def hold_keys(v, n):
    return [(f, v) for f in range(n + 1)]


def sample(outline, step=0.00025):
    """Points every `step` round a closed (y, z) outline."""
    pts, ring = [], outline + outline[:1]
    for a, b in zip(ring, ring[1:]):
        n = max(1, int(math.dist(a, b) / step))
        pts += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    return pts


def turned(pts, pivot, deg):
    """(y, z) points turned deg about a pivot (y, z), + carrying +z toward -y... as a hinge about -x does
    with + (the hammer's sense); pass -deg for a hinge about +x."""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(pivot[0] + (y - pivot[0]) * ca + (z - pivot[1]) * sa, pivot[1] - (y - pivot[0]) * sa + (z - pivot[1]) * ca)
            for y, z in pts]


def inside_2d(p, poly):
    x, y, c = p[0], p[1], False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _hammer_points():
    """The hammer's side outline (y, z) sampled every 0.25 mm, and its hub's rim, at rest."""
    pts, ring = [], HAMMER_OUTLINE + HAMMER_OUTLINE[:1]
    for a, b in zip(ring, ring[1:]):
        n = max(1, int(math.dist(a, b) / 0.00025))
        pts += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    py, pz = HAMMER_PIVOT[1:]
    pts += [(py + HAMMER_HUB * math.cos(2 * math.pi * i / 24), pz + HAMMER_HUB * math.sin(2 * math.pi * i / 24))
            for i in range(24)]
    return pts


_HAMMER_PTS = _hammer_points()
_CAM = {}


def hammer_cam(s):
    """The least angle (deg, 0.25 deg steps) at which the hammer clears the slide recoiled s (its rear
    face and the firing pin's cap), 0.3 mm clear: the slide cams the hammer back, and it rides home
    against the slide's rear face."""
    key = round(s, 6)
    if key in _CAM:
        return _CAM[key]
    py, pz = HAMMER_PIVOT[1:]
    rear, gap = SLIDE_Y[1] + s, 0.0003
    corners = [(rear + gap, SLIDE_Z[0] - gap), (rear + 0.0005 + gap, BORE_Z - FIRING_PIN - gap),
               (rear + 0.0005 + gap, BORE_Z + FIRING_PIN + gap)]
    for i in range(4 * HAMMER_MAX + 1):
        clear = True
        for y2, z2 in turned(_HAMMER_PTS, (py, pz), i / 4):
            face = rear + (0.0005 if abs(z2 - BORE_Z) < FIRING_PIN + gap else 0.0)
            if z2 > SLIDE_Z[0] - gap and y2 < face + gap:
                clear = False
                break
        poly = turned(HAMMER_OUTLINE, (py, pz), i / 4)
        if clear and not any(inside_2d(c, poly) for c in corners):
            _CAM[key] = i / 4
            return i / 4
    raise SystemExit(f"[{NAME}] the hammer cannot clear the slide at {s:.4f} m")


def slide_fire_keys(n, lock=None):
    """The slide's cycle as it fires: back fast after the shot, held a frame, then home (or, with
    `lock`, forward onto the slide stop there)."""
    top = SLIDE_TRAVEL
    if lock is None:
        return shaped([(0, 0, "io"), (SHOT_F, 0, "io"), (EJECT_F + 1, top, "out"), (EJECT_F + 2, top, "io"),
                       (EJECT_F + 7, 0, "io")], n)
    return shaped([(0, 0, "io"), (SHOT_F, 0, "io"), (EJECT_F + 1, top, "out"), (EJECT_F + 2, top, "io"),
                   (EJECT_F + 4, lock, "io")], n)


# The slide's lock (open on the slide stop): the notch's rear wall 0.3 mm behind the raised tip's back.
def _stop_in_notch():
    """The raised lever's reach into the slide's notch: its rearmost and foremost y above the slide's
    underside, at every angle of its rise."""
    pts, ends = sample(STOP_ARM), []
    for i in range(1, 11):
        up = [(y, z) for y, z in turned(pts, STOP_PIVOT[1:], -STOP_UP * i / 10) if z > SLIDE_Z[0] - 0.0005]
        if up:
            ends.append((min(y for y, _ in up), max(y for y, _ in up)))
    return min(a for a, _ in ends), max(b for _, b in ends)


_front, _rear = _stop_in_notch()
SLIDE_LOCK = round(_rear + 0.0003 - STOP_NOTCH[0][1], 5)
if STOP_NOTCH[0][0] + SLIDE_TRAVEL > _front - 0.0003:
    raise SystemExit(f"[{NAME}] the slide stop's notch does not clear its tip at full recoil")

# Joints: (name, parent, kind, pivot, axis, bone direction, limits), world space. The slide and the
# barrel recoil back (the barrel derived from the slide, expand()), the hammer turns back on its pin
# (+ = cocking), the trigger pulls back, the slide stop lifts, the cartridge drops, the catch pulls back.
JOINT_SPECS = [
    ("Root", None, "fixed", (0, 0, 0), UP, UP, None),
    (SLIDE, "Root", "slide", (0, SLIDE_Y[0], BORE_Z), BACK, None, (0, SLIDE_TRAVEL)),
    (BARREL, "Root", "slide", (0, CHAMBER[0][0], BORE_Z), BACK, None, (0, RECOIL)),
    (HAMMER, "Root", "hinge", HAMMER_PIVOT, (-1, 0, 0), UP, (0, HAMMER_MAX)),
    (TRIGGER, "Root", "hinge", TRIGGER_PIVOT, (1, 0, 0), DOWN, (0, TRIGGER_PULL)),
    (STOP, "Root", "hinge", STOP_PIVOT, (1, 0, 0), BACK, (0, STOP_UP)),
    (MAG, "Root", "slide", (0, sum(PACK_Y) / 2, PACK_Z[0]), DOWN, None, (0, MAG_TRAVEL)),
    (CATCH_BONE, "Root", "slide", (0, sum(GUARD_FRONT) / 2, sum(CATCH_Z) / 2), BACK, None, (0, CATCH_TRAVEL)),
]
PISTON_SPECS = []

_N = ACT_F
ANIMATIONS = {
    "idle": (True, "LINEAR", {SLIDE: hold_keys(0.0, IDLE_F), TRIGGER: hold_keys(0.0, IDLE_F)}),
    "fire": (False, "LINEAR", {
        TRIGGER: eased([(0, 0), (SHOT_F - 1, TRIGGER_PULL), (EJECT_F + 2, TRIGGER_PULL), (EJECT_F + 7, 0), (_N, 0)]),
        HAMMER: [(0, 0.0), (1, HAMMER_DA / 2), (SHOT_F - 1, HAMMER_DA)] + [(f, 0.0) for f in range(SHOT_F, _N + 1)],
        SLIDE: slide_fire_keys(_N)}),
    "fire_empty": (False, "LINEAR", {
        TRIGGER: eased([(0, 0), (SHOT_F - 1, TRIGGER_PULL), (EJECT_F + 4, TRIGGER_PULL), (EJECT_F + 8, 0), (_N, 0)]),
        HAMMER: [(0, 0.0), (1, HAMMER_DA / 2), (SHOT_F - 1, HAMMER_DA)] + [(f, 0.0) for f in range(SHOT_F, _N + 1)],
        SLIDE: slide_fire_keys(_N, SLIDE_LOCK),
        STOP: eased([(0, 0), (EJECT_F + 1, 0), (EJECT_F + 2, STOP_UP), (_N, STOP_UP)])}),
    "slide_release": (False, "LINEAR", {
        STOP: eased([(0, STOP_UP), (3, 0), (_N, 0)]),
        SLIDE: shaped([(0, SLIDE_LOCK, "io"), (3, SLIDE_LOCK, "io"), (7, 0, "in")], _N),
        HAMMER: hold_keys(0.0, _N)}),
    "mag_release": (False, "LINEAR", {
        CATCH_BONE: eased([(0, 0), (3, CATCH_TRAVEL), (_N, CATCH_TRAVEL)]),
        MAG: shaped([(0, 0, "io"), (3, 0, "io"), (10, MAG_TRAVEL, "in")], _N)}),
    "mag_insert": (False, "LINEAR", {
        MAG: shaped([(0, MAG_TRAVEL, "io"), (8, 0, "io")], _N),
        CATCH_BONE: eased([(0, CATCH_TRAVEL), (8, CATCH_TRAVEL), (11, 0), (_N, 0)])}),
}
PREVIEW_STATES = {
    "fire": {SLIDE: SLIDE_TRAVEL, TRIGGER: TRIGGER_PULL},
    "locked": {SLIDE: SLIDE_LOCK, STOP: STOP_UP, MAG: MAG_TRAVEL, CATCH_BONE: CATCH_TRAVEL},
    "mag_out": {MAG: MAG_TRAVEL, CATCH_BONE: CATCH_TRAVEL},
}
PREVIEW_VIEWS = {"fire": ["front_left", "left"], "locked": ["right", "rear_right"], "mag_out": ["front_left", "left"]}
FK_TEST_STATE = {SLIDE: 0.02, TRIGGER: 5, HAMMER: 30, STOP: 3, MAG: 0.01, CATCH_BONE: 0.002}
SHOWCASE = ["idle", "fire", "fire", "idle", "fire", "fire_empty", "mag_release", "mag_insert", "slide_release",
            "idle"]
# === END SPEC ===

PISTON_MIN_OVERLAP = 0.015
PISTON_MIN_ARM = 0.015
SLOT_GAP = 0.00125


def hatch(a, b, n):  # the pistons' coordinates are world coordinates here
    return Vector((a, b, n))


# The framework below (kinematics, pistons, mesh kit, checks, rig, actions, export) is the
# item table's and weapon holder's generic code, unchanged; the functions this asset defines after it replace
# the framework's (expand, build_materials, action_states, build_pistons) or add to its kit (loft,
# carve, a plate's bevelled edges).

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
# The lightning gun's own kinematics, materials, actuators and action plumbing (replace the framework's)
# --------------------------------------------------------------------------------------------

from mathutils.geometry import tessellate_polygon

_part_init = Part.__init__


def _part_init_tessellated(self, bone, line, verts, faces, convex, solid=True, exact=False, closed=True):
    """Part with its faces ear-clipped into triangles before the BVH is built: a BVH fans an n-gon
    from its first corner, so a concave face (a plate's face round its bores) would claim the holes
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
    """A joint state (or animation keys) as it is: nothing here is coupled (each prong is its own joint,
    keyed together)."""
    return dict(state)


def build_materials():
    for slot, (color, metallic, roughness, emission, *alpha) in MATERIALS.items():
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
        if alpha:  # glass: blended, exported as a glTF BLEND material
            bsdf.inputs["Alpha"].default_value = alpha[0]
            if hasattr(mat, "surface_render_method"):
                mat.surface_render_method = "BLENDED"
            else:
                mat.blend_method = "BLEND"
        mat.diffuse_color = (*color, alpha[0] if alpha else 1.0)


def action_states(actions, joints):
    """Every frame of every action as a joint state, read back from the real f-curves (the joints'
    own channels only; the baked actuator keys are checked by check_piston_clearance)."""
    by_bone = {j.name: j for j in joints.values()}
    states = []
    for name, action in actions.items():
        curves = []
        for fc in action_fcurves(action):
            bone = fc.data_path.split('"')[1]
            if bone in by_bone and fc.data_path.endswith(("rotation_euler", "location")):
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


def build_pistons(k, pistons, joints):
    """The prong actuators, sized to them (the framework's pins are for a prop's rams): each end an eye
    on a pin parallel to the prong's hinge, the pin passing through the cheeks on either side and
    showing 1 mm past them; a black barrel with a titanium gland, a stainless steel rod."""
    for p in pistons:
        d = (p.b - p.a).normalized()
        ax = joints[p.rod_parent].axis
        eye = p.radius * 1.2
        k.cyl(p.a - ax * p.radius, p.a + ax * p.radius, eye, p.cylinder, FRM, segs=8, solid=False)
        k.cyl(p.a + d * eye * 0.7, p.a + d * p.cyl_len, p.radius, p.cylinder, SEC, segs=8, solid=False)
        k.cyl(p.a + d * (p.cyl_len - 0.004), p.a + d * (p.cyl_len + 0.0006), p.radius + 0.0008, p.cylinder, FRM, segs=8,
              solid=False)
        k.cyl(p.b - d * eye * 0.7, p.b - d * p.rod_len, p.radius * 0.55, p.rod, JNT, segs=6, solid=False)
        k.cyl(p.b - ax * p.radius, p.b + ax * p.radius, eye, p.rod, FRM, segs=8, solid=False)
        for bone, pin in ((p.cyl_parent, p.a), (p.rod_parent, p.b)):
            k.cyl(pin - ax * (p.radius + 0.0045), pin + ax * (p.radius + 0.0045), p.radius * 0.4, bone, JNT, segs=6,
                  solid=False)


# --------------------------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------------------------

def ring_xz(cx, cz, r, y, n=16, phase=0.0):
    """Polygon in the XZ plane (square to the bore) round (cx, cz) at y."""
    return [(cx + r * math.cos(phase + 2 * math.pi * i / n), y, cz + r * math.sin(phase + 2 * math.pi * i / n))
            for i in range(n)]


def octagon_xz(w, zb, zt, cb, ct, y):
    """A front profile: half-width w from zb to zt, bottom corners chamfered cb, top corners ct."""
    pts = [(w, y, zb + cb), (w, y, zt - ct), (w - ct, y, zt), (-w + ct, y, zt), (-w, y, zt - ct), (-w, y, zb + cb),
           (-w + cb, y, zb), (w - cb, y, zb)]
    out = []
    for p in pts:  # a zero chamfer leaves a doubled corner
        if not out or (Vector(p) - Vector(out[-1])).length > 1e-9:
            out.append(p)
    return out if (Vector(out[0]) - Vector(out[-1])).length > 1e-9 else out[:-1]


def chamfered(w, lo, hi, cb, ct, o=0.002):
    """(a, b) outline of a section half-width w from lo to hi with 45-degree corner chamfers cb (bottom)
    and ct (top), its flats pushed out by o: intersected with a solid whose own faces are those flats,
    it only cuts the chamfers (no coincident faces)."""
    return [(w + o, lo + cb + o), (w + o, hi - ct - o), (w - ct - o, hi + o), (-w + ct + o, hi + o),
            (-w - o, hi - ct - o), (-w - o, lo + cb + o), (-w + cb + o, lo - o), (w - cb - o, lo - o)]


def xz_poly(pts, y):
    """(x, z) offsets from the bore axis as a polygon square to the bore at y."""
    return [(x, y, BORE_Z + z) for x, z in pts]


def pack_poly(pts, s):
    """(x, h) pack points as a polygon square to the pack's axis at s."""
    return [tuple(pk(x, s, h)) for x, h in pts]


def pack_side(pts, x=0.0):
    """(s, h) pack points as a polygon in the pack's side plane at x."""
    return [tuple(pk(x, s, h)) for s, h in pts]


def pipe(k, p0, p1, r_out, r_in, bone, mat, segs=8):
    """A hollow tube, open at both ends."""
    p0, p1 = Vector(p0), Vector(p1)
    tmp = bmesh.new()
    rot, mid, half = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix(), (p0 + p1) / 2, (p1 - p0).length / 2
    rings = [[tmp.verts.new(rot @ Vector((r * math.cos(2 * math.pi * j / segs), r * math.sin(2 * math.pi * j / segs), z))
                            + mid) for j in range(segs)] for z in (-half, half) for r in (r_out, r_in)]
    o0, i0, o1, i1 = rings
    for j in range(segs):
        n = (j + 1) % segs
        tmp.faces.new((o0[j], o0[n], o1[n], o1[j]))
        tmp.faces.new((i0[n], i0[j], i1[j], i1[n]))
        tmp.faces.new((o0[n], o0[j], i0[j], i0[n]))
        tmp.faces.new((o1[j], o1[n], i1[n], i1[j]))
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])
    k.axes.append((bone, k.xf @ mid, (k.xf.to_3x3() @ (p1 - p0)).normalized(), half))
    k.emit(tmp, bone, mat, False, convex=False)


def revolve(k, profile, origin, axis, ref, bone, mat, segs=12, loop=False):
    """A solid of revolution about `axis` through `origin`, from (radius, t) profile points (t along the
    axis; radius 0 = a pole), its first vertex toward `ref`. Closed with poles at both ends, or a `loop`
    (a ring section, such as a nozzle's wall)."""
    o, a = Vector(origin), Vector(axis).normalized()
    u = (Vector(ref) - a * Vector(ref).dot(a)).normalized()
    v = a.cross(u)
    tmp = bmesh.new()
    rings = []
    for r, t in profile:
        c = o + a * t
        if r < 1e-9:
            rings.append([tmp.verts.new(c)])
        else:
            rings.append([tmp.verts.new(c + (u * math.cos(2 * math.pi * j / segs) + v * math.sin(2 * math.pi * j / segs)) * r)
                          for j in range(segs)])
    for p, q in list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if loop else []):
        for j in range(segs):
            n = (j + 1) % segs
            if len(p) == 1 and len(q) > 1:
                tmp.faces.new((p[0], q[j], q[n]))
            elif len(q) == 1 and len(p) > 1:
                tmp.faces.new((p[j], p[n], q[0]))
            elif len(p) > 1:
                tmp.faces.new((p[j], p[n], q[n], q[j]))
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])
    k.emit(tmp, bone, mat, False, convex=False)


def lathe(k, profile, bone, mat, segs=12, cx=0.0, cz=BORE_Z, loop=False):
    """revolve() about the Y axis through (cx, cz), from (radius, y) points."""
    revolve(k, profile, (cx, 0.0, cz), (0, 1, 0), (1, 0, 0), bone, mat, segs, loop)


def bolt(k, at, normal, bone, r=0.0032, mat=JNT, head=0.0022):
    """A hex bolt head standing `head` proud of the surface at `at`, its shank sunk 2 mm in."""
    n = Vector(normal).normalized()
    k.cyl(Vector(at) - n * 0.002, Vector(at) + n * head, r, bone, mat, segs=6, solid=False)


def rect(ha, hb, n, ca=0.0, cb=0.0, chamfer=0.0):
    """Rectangle (optionally chamfered) in an XY plane at height n."""
    c = chamfer
    pts = [(ha, hb - c), (ha - c, hb), (-ha + c, hb), (-ha, hb - c), (-ha, -hb + c), (-ha + c, -hb),
           (ha - c, -hb), (ha, -hb + c)] if c else [(ha, hb), (-ha, hb), (-ha, -hb), (ha, -hb)]
    return [(ca + a, cb + b, n) for a, b in pts]


def side_rect(x, y0, y1, z0, z1):
    """Rectangle in a flank's plane (x) from y0..y1, z0..z1."""
    return [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]


def lobe(az, u0, u1, hw):
    """A lug's corners round azimuth az, from radius u0 out to u1, half-width hw: (in -t, out -t, out +t,
    in +t) as (x, z) offsets from the bore axis."""
    r, t = radial(az), tangent(az)
    return [((r * u + t * w).x, (r * u + t * w).z) for u, w in ((u0, -hw), (u1, -hw), (u1, hw), (u0, hw))]


def lug_slot(az, u0, u1, hw, y0, y1):
    """A slot through a lug round azimuth az (radius u0..u1, half-width hw, y0..y1), as a plate's
    `subtract` profile."""
    r = radial(az)
    pts = [Vector((0, y, BORE_Z)) + r * u for u, y in ((u0, y0), (u1, y0), (u1, y1), (u0, y1))]
    return [tuple(p) for p in pts], tuple(tangent(az)), 2 * hw



def rounded(pts, radii, n=4):
    """A polygon's corners filleted: corner i rounded with radius radii[i] (0 = sharp), n segments."""
    out = []
    m = len(pts)
    for i in range(m):
        p, a, b = Vector(pts[i]), Vector(pts[i - 1]), Vector(pts[(i + 1) % m])
        r = radii[i]
        if r <= 0:
            out.append(tuple(p))
            continue
        u, v = (a - p).normalized(), (b - p).normalized()
        half = math.acos(max(-1.0, min(1.0, u.dot(v)))) / 2
        d = r / math.tan(half)                     # the tangent points' distance from the corner
        c = p + (u + v).normalized() * (r / math.sin(half))
        t0, t1 = p + u * d, p + v * d
        a0, a1 = math.atan2(t0.y - c.y, t0.x - c.x), math.atan2(t1.y - c.y, t1.x - c.x)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out += [(c.x + r * math.cos(a0 + da * j / n), c.y + r * math.sin(a0 + da * j / n)) for j in range(n + 1)]
    return out


def carve(k, bm, bone, mat, holes=(), cuts=(), boxes=(), intersect=(), subtract=(), bevel=0.0, bevel_normal=None,
          material=None):
    """A solid (a bmesh, closed) with exact boolean cuts, as a plate's (see Kit.plate): `holes` polygons cut
    straight through along `bevel_normal`, `cuts` (p0, p1, r[, sides]) cylinders, `boxes` (center, size)
    blocks, `intersect` / `subtract` (points, normal, thickness) profiles. With `bevel`, the edges round
    each face square to `bevel_normal` (a plate's two sides) are chamfered. `material` (face -> slot)
    colours the faces made."""
    n0 = Vector(bevel_normal or (0, 0, 1)).normalized()

    def temp(b, name):
        mesh = bpy.data.meshes.new(name)
        b.to_mesh(mesh)
        b.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def slab(points, th, nrm=None):
        n = n0 if nrm is None else Vector(nrm).normalized()
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

    base = temp(bm, "_solid")
    shapers = [slab(pts, th, nrm) for pts, nrm, th in intersect]
    for shaper in shapers:
        mod = base.modifiers.new("shape", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", shaper
    cutters = ([slab(h, 1.0) for h in holes] + [rod(*c) for c in cuts]
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
    if bevel > 0:
        tmp.normal_update()
        side = lambda f: abs(f.normal.dot(n0)) > 0.999
        edges = [e for e in tmp.edges if len(e.link_faces) == 2 and side(e.link_faces[0]) != side(e.link_faces[1])]
        bmesh.ops.bevel(tmp, geom=edges, offset=bevel, offset_type="OFFSET", segments=1, profile=0.5, affect="EDGES",
                        clamp_overlap=True)
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])
    made = k.emit(tmp, bone, mat, False, convex=False, exact=True)
    if material:
        for f in made:
            f.material_index = SLOTS.index(material(f))


def _plate(self, outline, thickness, normal, bone, mat, holes=(), cuts=(), boxes=(), intersect=(), subtract=(),
           mirror=False, bevel=0.0):
    """Flat plate with exact boolean cuts (the framework's, through carve), its outline's edges
    chamfered `bevel` on both sides."""
    if mirror:
        raise ValueError("mirrored plates are not used here")
    n0 = Vector(normal).normalized()
    bm = bmesh.new()
    bot = [bm.verts.new(Vector(q) - n0 * thickness / 2) for q in outline]
    top = [bm.verts.new(Vector(q) + n0 * thickness / 2) for q in outline]
    bm.faces.new(top)
    bm.faces.new(bot[::-1])
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if not (holes or cuts or boxes or intersect or subtract or bevel):
        self.emit(bm, bone, mat, False, convex=True, exact=True)
        return
    carve(self, bm, bone, mat, [[Vector(q) for q in h] for h in holes], cuts, boxes, intersect, subtract, bevel,
          tuple(n0))


Kit.plate = _plate


def loft(stations, ring):
    """A closed bmesh through a ring of points (ring(y), the same count at every station) at each
    station, capped at both ends."""
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in ring(y)] for y in stations]
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def bore_cut(y0, y1):
    return (Vector((0, y0, BORE_Z)), Vector((0, y1, BORE_Z)), GUIDE_R, 12)



# --------------------------------------------------------------------------------------------
# The pistol's coupled joints: the barrel and the hammer follow the slide
# --------------------------------------------------------------------------------------------

def expand(state):
    """A joint state (or animation keys) with the coupled joints derived from the slide: the barrel
    rides the slide's first RECOIL, locked to its breech face; the hammer is at least as far back as
    the slide cams it (hammer_cam). Animation keys are on every frame, the slide's and the hammer's on
    the same frames."""
    out = dict(state)
    if any(isinstance(v, list) for v in out.values()):
        if SLIDE in out:
            ham = dict(out.get(HAMMER, []))
            out[BARREL] = [(f, min(v, RECOIL)) for f, v in out[SLIDE]]
            out[HAMMER] = [(f, max(ham.get(f, 0.0), hammer_cam(v))) for f, v in out[SLIDE]]
        return out
    s = out.get(SLIDE, 0.0)
    out[BARREL] = min(s, RECOIL)
    out[HAMMER] = max(out.get(HAMMER, 0.0), hammer_cam(s))
    return out


# --------------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------------

def vault(w, zb, zs, zc, radii, step, m=6):
    """(x, z) of the housing's section: a flat bottom, flat flanks stepped in (step: its height, inset)
    over the lower band, a circular crown from the springing line zs up to zc; filleted (radii: the
    bottom's edges, the springing line)."""
    zst, st = step
    wu = w - st
    s = zc - zs
    r = (wu * wu + s * s) / (2 * s)
    cz = zc - r
    a0 = math.atan2(zs - cz, wu)
    crown = [(r * math.cos(a0 + (math.pi - 2 * a0) * i / m), cz + r * math.sin(a0 + (math.pi - 2 * a0) * i / m))
             for i in range(1, m)]
    pts = ([(w, zb), (w, zst), (wu, zst + st), (wu, zs)] + crown
           + [(-wu, zs), (-wu, zst + st), (-w, zst), (-w, zb)])
    rb, rs = radii
    return rounded(pts, [rb, 0, 0, rs] + [0.0] * (m - 1) + [rs, 0, 0, rb], n=2)


def housing_drop(y):
    """How far the housing's top has fallen at y (its raked nose)."""
    return NOSE[1] * (NOSE[0] - y) / (NOSE[0] - HOUSING_Y[0]) if y < NOSE[0] else 0.0


def housing_top(y):
    return HOUSING_Z[2] - housing_drop(y)


def hook_bottom(y):
    """The hook's sole at y, its toe rounded at the front."""
    (f, rear), zh, rt = HOOK
    if y < f + rt:
        return zh + rt - math.sqrt(max(0.0, rt * rt - (f + rt - y) ** 2))
    return zh


def front_chamfer(y):
    return max(0.0, EDGE - (y - HOUSING_Y[0]))


def housing_ring(y):
    s = front_chamfer(y)
    d = housing_drop(y)
    zb, zs, zc = HOUSING_Z
    return [Vector((x, y, z)) for x, z in vault(HOUSING_W - s, zb + s, zs - d - s, zc - d - s, HOUSING_R, STEP)]


def hook_ring(y):
    """The hook's section at y: its flanks flush with the housing's lower band, its top sunk into the
    housing's bottom, its sole's edges filleted as the cartridge's."""
    s = front_chamfer(y)
    w, zb, zt = HOUSING_W - s, hook_bottom(y) + s, HOUSING_Z[0] + 0.0012
    return [Vector((x, y, z)) for x, z in rounded([(w, zb), (w, zt), (-w, zt), (-w, zb)], [LOW_R, 0, 0, LOW_R], n=3)]


def hook_stations():
    (f, rear), _, rt = HOOK
    toe = [f + rt * (1 + math.cos(math.radians(a))) for a in (180, 202.5, 225, 247.5, 270)]
    return sorted(set(round(y, 6) for y in toe + [f + EDGE, rear]))


def slide_section(w, zb, zt, r):
    """(x, z) of the slide's section: flat flanks and top, the top corners rounded r."""
    return rounded([(w, zb), (w, zt), (-w, zt), (-w, zb)], [0.0008, r, r, 0.0008], n=2)


def slide_ring(y):
    zt = SLIDE_Z[1] - max(0.0, y - (SLIDE_Y[1] - SLIDE_CHAMFER))
    return [Vector((x, y, z)) for x, z in slide_section(SLIDE_W, SLIDE_Z[0], zt, SLIDE_R)]


def tunnel_section(g=0.0):
    t = TUNNEL + g
    return slide_section(SLIDE_W + t, SLIDE_Z[0] - t, SLIDE_Z[1] + t, SLIDE_R + t)


def frame_ring(y):
    w, (zb, zt) = FRAME_W, FRAME_Z
    return [Vector((x, y, z)) for x, z in rounded([(w, zb), (w, zt), (-w, zt), (-w, zb)], [0.003, 0, 0, 0.003], n=2)]


def stadium(y0, y1, z0, z1, grow=0.0, n=3):
    """(y, z) of a stadium (a slot with round ends) in a flank's plane."""
    y0, y1, z0, z1 = y0 - grow, y1 + grow, z0 - grow, z1 + grow
    r = (z1 - z0) / 2 - 0.0002
    return rounded([(y0, z0), (y1, z0), (y1, z1), (y0, z1)], [r] * 4, n=n)


def revolve_bm(profile, origin, axis, ref, segs=12, loop=False):
    """revolve()'s solid of revolution as a closed bmesh (to be machined by carve)."""
    o, a = Vector(origin), Vector(axis).normalized()
    u = (Vector(ref) - a * Vector(ref).dot(a)).normalized()
    v = a.cross(u)
    bm = bmesh.new()
    rings = []
    for r, t in profile:
        c = o + a * t
        rings.append([bm.verts.new(c + (u * math.cos(2 * math.pi * j / segs) + v * math.sin(2 * math.pi * j / segs)) * r)
                      for j in range(segs)])
    for p, q in list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if loop else []):
        for j in range(segs):
            n = (j + 1) % segs
            bm.faces.new((p[j], p[n], q[n], q[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def slab_bm(outline, thickness, normal):
    """A closed bmesh: the outline extruded `thickness` along `normal`, centred on it."""
    n0 = Vector(normal).normalized()
    bm = bmesh.new()
    bot = [bm.verts.new(Vector(q) - n0 * thickness / 2) for q in outline]
    top = [bm.verts.new(Vector(q) + n0 * thickness / 2) for q in outline]
    bm.faces.new(top)
    bm.faces.new(bot[::-1])
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def bore_cut(y0, y1):
    return (Vector((0, y0, BORE_Z)), Vector((0, y1, BORE_Z)), GUIDE_R, 12)


def gw(yl, zl):
    """A point of the grip's own frame (y back, z up its raked axis, from the hand's centre) in world (y, z)."""
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))
    return (GRIP_G[1] + yl * c - zl * s, GRIP_G[2] + yl * s + zl * c)


def grip_top(yl, z=None):
    """The grip frame's local z of the world plane z (default: 5 mm into the frame's belly) at local y."""
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))
    return ((BELLY + 0.005 if z is None else z) - GRIP_G[2] - yl * s) / c


# --------------------------------------------------------------------------------------------
# Parts: the housing
# --------------------------------------------------------------------------------------------

def build_housing(k):
    """The suppressor housing, lofted from its vaulted sections, its front hooking down, then machined:
    the tunnel the slide's nose runs in, the barrel's bores and the fins' cavity, the end cap's
    counterbore, the windows onto the fins in both flanks, the feed opening over the cartridge, the
    ejection port through the crown over the chamber, the compensator slots across the raked top, the
    gas vents in the upper flanks; bezels round the tunnel's mouth and the fins' windows."""
    W = HOUSING_W
    t0, t1 = TUNNEL_FRONT, HOUSING_Y[1] + 0.01
    tunnel = ([(x, (t0 + t1) / 2, z) for x, z in tunnel_section()], (0, 1, 0), t1 - t0)
    (c0, c1), cw = CHANNEL
    cuts = [bore_cut(FIN_CAVITY[0] + 0.001, HOUSING_Y[0] - 0.01),
            (Vector((0, HOUSING_Y[0] - 0.01, BORE_Z)), Vector((0, CAP[1], BORE_Z)), CAP[2] + 0.0002, 14),
            (Vector((0, FIN_CAVITY[0], BORE_Z)), Vector((0, t0 + 0.002, BORE_Z)), FIN_CAVITY[1], 12)]
    zf = SLIDE_Z[0] - TUNNEL
    (py0, py1), pw = EJECT_PORT
    zp = SLIDE_Z[1] + TUNNEL - 0.001
    boxes = [((0, (c0 + c1) / 2, (HOUSING_Z[0] + zf) / 2), (2 * cw, c1 - c0, zf - HOUSING_Z[0] + 0.004)),      # feed
             ((0, (py0 + py1) / 2, (zp + HOUSING_Z[2] + 0.01) / 2), (2 * pw, py1 - py0, HOUSING_Z[2] + 0.01 - zp))]  # ejection
    ys, half, width, depth = COMP
    boxes += [((0, y, housing_top(y)), (2 * half, width, 2 * depth)) for y in ys]                            # comp slots
    ys, width, (vz0, vz1), depth = FLANK_VENTS
    boxes += [((sx * W_UP, y, (vz0 + vz1) / 2), (2 * depth, width, vz1 - vz0)) for sx in (1, -1) for y in ys]  # gas vents
    (fy0, fy1), (fz0, fz1) = FIN_WINDOW
    xm, xd = (W + 0.004 + 0.006) / 2, W + 0.004 - 0.006
    subtract = [tunnel] + [([(sx * xm, y, z) for y, z in stadium(fy0, fy1, fz0, fz1)], (1, 0, 0), xd) for sx in (1, -1)]
    stations = [HOUSING_Y[0], HOUSING_Y[0] + EDGE, NOSE[0], HOUSING_Y[1]]
    carve(k, loft(stations, housing_ring), "Root", PRI, cuts=cuts, boxes=boxes, subtract=subtract)
    # the black bezel round the tunnel's mouth, sunk 1 mm into the rear face, four screws holding it
    yb = HOUSING_Y[1] + 0.0005
    outer = [(x, yb, z) for x, z in slide_section(SLIDE_W + TUNNEL + 0.0045, SLIDE_Z[0] - TUNNEL - 0.0045,
                                                  SLIDE_Z[1] + TUNNEL + 0.0045, SLIDE_R + 0.005)]
    k.plate(outer, 0.002, (0, 1, 0), "Root", MTL, holes=[[(x, yb, z) for x, z in tunnel_section(0.0003)]])
    for sx in (1, -1):
        for z in (SLIDE_Z[0] + 0.004, SLIDE_Z[1] - 0.004):
            bolt(k, (sx * (SLIDE_W + TUNNEL + 0.0025), yb + 0.001, z), BACK, "Root", r=0.0013, head=0.0006)
    # the fins' windows' bezels, both flanks
    for sx in (1, -1):
        x = sx * (W_UP + 0.0005)
        k.plate([(x, y, z) for y, z in stadium(fy0, fy1, fz0, fz1, 0.003)], 0.002, (1, 0, 0), "Root", MTL,
                holes=[[(x, y, z) for y, z in stadium(fy0, fy1, fz0, fz1, -0.0004)]])


def build_hook(k):
    """The hook (metallic black), the suppressor's expansion chamber under the housing's front: lofted on
    its own, its toe rounded and its lower edges true arcs (the support palm's seat), its front edges
    chamfered with the housing's; the exhaust slots across its front face, venting forward."""
    zs, half, height, depth = HOOK_VENTS
    f = HOUSING_Y[0]
    boxes = [((0, f, z), (2 * half, 2 * depth, height)) for z in zs]
    carve(k, loft(hook_stations(), hook_ring), "Root", MTL, boxes=boxes)


def build_sight(k):
    """The reflex sight on the crown: a black base screwed down onto the crown, its emitter at the front,
    the hood at the back framing the tilted glass lens, a stainless steel adjuster on its right."""
    (y0, y1), hw, h = SIGHT
    zc = HOUSING_Z[2]
    base = rounded([(hw, y0), (hw, y1), (-hw, y1), (-hw, y0)], [0.002] * 4, n=2)
    k.plate([(x, y, zc + 0.0015) for x, y in base], 0.007, (0, 0, 1), "Root", MTL)
    k.span((-0.0045, y0 + 0.002, zc + 0.005), (0.0045, y0 + 0.008, zc + 0.0085), "Root", MTL)       # emitter
    yh, hh = y1 - 0.005, hw - 0.0005
    hood = rounded([(hh, zc + 0.004), (hh, zc + h), (-hh, zc + h), (-hh, zc + 0.004)], [0, 0.003, 0.003, 0], n=2)
    hole = rounded([(hw - 0.002, zc + 0.0055), (hw - 0.002, zc + h - 0.002), (-hw + 0.002, zc + h - 0.002),
                    (-hw + 0.002, zc + 0.0055)], [0, 0.0015, 0.0015, 0], n=1)
    k.plate([(x, yh, z) for x, z in hood], 0.009, (0, 1, 0), "Root", MTL, holes=[[(x, yh, z) for x, z in hole]])
    lens = rounded([(hw - 0.0024, zc + 0.0055), (hw - 0.0024, zc + h - 0.0024), (-hw + 0.0024, zc + h - 0.0024),
                    (-hw + 0.0024, zc + 0.0055)], [0, 0.0012, 0.0012, 0], n=1)
    k.plate([(x, yh, z) for x, z in lens], 0.0008, (0, 1, 0), "Root", GLS)
    k.cyl((-hw + 0.0005, (y0 + yh) / 2, zc + 0.0035), (-hw - 0.0022, (y0 + yh) / 2, zc + 0.0035), 0.0022, "Root", JNT, segs=8)
    for y in (y0 + 0.012, yh - 0.007):
        bolt(k, (hw - 0.0025, y, zc + 0.005), UP, "Root", r=0.0011, head=0.0005)


def build_cap(k):
    """The suppressor's end cap: a titanium threaded cap standing out of the housing's front face in its
    counterbore, stepped down to its nose, six spanner notches round its rim (a rotary cap), six exit
    vents round the bore, a stainless steel crown ring at the bore's mouth."""
    f, b, r = CAP
    prof = [(r, b), (r, f + 0.0075), (r - 0.0014, f + 0.0065), (r - 0.0014, f + 0.0015), (r - 0.003, f),
            (0.0082, f), (0.0064, f + 0.0012), (0.0064, b)]
    bm = revolve_bm(prof, (0, 0, BORE_Z), (0, 1, 0), (1, 0, 0), segs=14, loop=True)
    notches, vents = [], []
    for i in range(6):
        a = math.radians(30 + 60 * i)
        rad, tan = Vector((math.cos(a), 0, math.sin(a))), Vector((-math.sin(a), 0, math.cos(a)))
        c = Vector((0, 0, BORE_Z))
        pts = [tuple(c + rad * u + Vector((0, y, 0))) for u, y in ((r - 0.004, f - 0.001), (r + 0.001, f - 0.001),
                                                                    (r + 0.001, f + 0.005), (r - 0.004, f + 0.005))]
        notches.append((pts, tuple(tan), 0.003))
        a = math.radians(60 * i)
        p = c + Vector((math.cos(a), 0, math.sin(a))) * 0.0112
        vents.append((p + Vector((0, -0.005, 0)), p + Vector((0, 0.004, 0)), 0.0013, 6))
    carve(k, bm, "Root", FRM, cuts=vents, subtract=notches)
    pipe(k, (0, f - 0.0004, BORE_Z), (0, f + 0.0006, BORE_Z), 0.0082, 0.0064, "Root", JNT, segs=14)


def display_frame():
    """The display console on the left flank: (y0, y1), its face's bottom and top (x, z) points, its
    outward normal (tilted up toward the gunner's eye)."""
    (y0, y1), (z0, z1), tilt = DISPLAY
    a = math.radians(tilt)
    d0 = 0.0058
    d1 = d0 - (z1 - z0) * math.tan(a)
    return (y0, y1), (W_UP + d0, z0), (W_UP + d1, z1), Vector((math.cos(a), 0, math.sin(a)))


def build_display(k):
    """The display console standing on the left flank: a metallic black wedge (its face tilted up), the
    lit screen under glass inset in the face, a stainless steel screw: the side's one light."""
    (y0, y1), (xb, zb), (xt, zt), n = display_frame()
    W = W_UP
    side = [(W - 0.001, zb), (xb, zb), (xt, zt), (W - 0.001, zt)]
    k.prism([(x, (y0 + y1) / 2, z) for x, z in side], y1 - y0, (0, 1, 0), "Root", MTL)
    mid = Vector(((xb + xt) / 2, 0, (zb + zt) / 2))
    h = (Vector((xt, 0, zt)) - Vector((xb, 0, zb))).length
    for off, th, mat, inset in ((0.0004, 0.0008, EMI, 0.0045), (0.0009, 0.0005, GLS, 0.0040)):
        p = mid + n * (off - th / 2 + 0.0002)
        k.obox((p.x, y0 + inset + 0.004, p.z), (p.x, y1 - inset, p.z), h - 2 * inset + 0.002, th, tuple(n), "Root", mat)
    bolt(k, (mid.x, y0 + 0.0035, mid.z), tuple(n), "Root", r=0.0014, head=0.0007)


def build_dial(k):
    """The gas regulator on the left flank: a black boss standing off the flank, a bronze bearing ring,
    the stainless steel rotor with its slotted knob bar (a rotary cap: it sets how much gas the expansion chamber
    bleeds), and the gas line from the hook's flank running back into the boss's front."""
    y, z, r = DIAL
    W = HOUSING_W
    X = lambda d: W + d
    k.cyl((X(-0.001), y, z), (X(0.0075), y, z), r, "Root", SEC, segs=14)                               # boss
    k.cyl((X(0.0075), y, z), (X(0.0088), y, z), r - 0.0018, "Root", BRZ, segs=14)                       # bearing ring
    k.cyl((X(0.0087), y, z), (X(0.0100), y, z), r - 0.0038, "Root", JNT, segs=12)                       # rotor
    k.obox((X(0.0099), y - (r - 0.005), z), (X(0.0099), y + (r - 0.005), z), 0.0032, 0.0024, (1, 0, 0), "Root", SEC)  # knob
    zt, xt = z, X(0.0045)
    k.tube([(X(0.0), HOUSING_Y[0] + 0.016, zt), (xt, HOUSING_Y[0] + 0.016, zt), (xt, y - r, zt)], 0.0017, "Root", JNT,
           sides=6)


# --------------------------------------------------------------------------------------------
# Parts: the slide, the barrel and the recoil guides
# --------------------------------------------------------------------------------------------

def build_slide(k):
    """The slide (matte titanium), lofted from its section with the rear top edge chamfered: the guide
    rods' bores in its breech face, slanted cocking grooves on both flanks at the back and front, a row
    of round lightening pockets in each flank between them, the slide stop's notch on its lower left edge; the firing pin's stainless steel cap on the rear face, the
    extractor on the nose's right flank (seen through the window)."""
    rx, rz, _, _ = RODS
    br, bend = ROD_BORE
    cuts = [((sx * rx, SLIDE_Y[0] - 0.005, rz), (sx * rx, bend, rz), br, 8) for sx in (1, -1)]
    (y0, pitch, n), (z0, z1), depth = SERRATIONS
    fy0, fpitch, fn = FRONT_SERRATIONS
    lean = (z1 - z0) * math.tan(math.radians(12))
    subtract = []
    for sx in (1, -1):
        x = sx * SLIDE_W
        for y in [y0 + pitch * i for i in range(n)] + [fy0 + fpitch * i for i in range(fn)]:
            subtract.append(([(x, y - 0.001, z0), (x, y + 0.001, z0), (x, y + 0.001 - lean, z1), (x, y - 0.001 - lean, z1)],
                             (1, 0, 0), 2 * depth))
    (ny0, ny1), nx, nz = STOP_NOTCH
    boxes = [(((nx + SLIDE_W + 0.002) / 2, (ny0 + ny1) / 2, (SLIDE_Z[0] - 0.001 + nz) / 2),
              (SLIDE_W + 0.002 - nx, ny1 - ny0, nz - SLIDE_Z[0] + 0.001))]
    pys, pz, pr, pd = POCKETS
    cuts += [((sx * (SLIDE_W + 0.002), y, pz), (sx * (SLIDE_W - pd), y, pz), pr, 7) for sx in (1, -1) for y in pys]
    stations = [SLIDE_Y[0], SLIDE_Y[1] - SLIDE_CHAMFER, SLIDE_Y[1]]
    carve(k, loft(stations, slide_ring), SLIDE, FRM, cuts=cuts, boxes=boxes, subtract=subtract)
    k.cyl((0, SLIDE_Y[1] - 0.001, BORE_Z), (0, SLIDE_Y[1] + 0.0005, BORE_Z), FIRING_PIN, SLIDE, JNT, segs=8)
    k.span((-SLIDE_W - 0.0002, SLIDE_Y[0] + 0.002, 0.1495), (-SLIDE_W + 0.0008, SLIDE_Y[0] + 0.018, 0.1545), SLIDE, JNT)


def build_barrel(k):
    """The barrel (titanium): the chamber block at the tunnel's front (the chamber's mouth in its rear
    face, against the breech face), the tube in the housing's bores, and its bronze cooling fins in the
    cavity behind the flanks' windows."""
    (b0, b1), h = CHAMBER
    sq = [(x, (b0 + b1) / 2, BORE_Z + z) for x, _, z in octagon_xz(h, -h, h, 0.002, 0.002, 0)]
    k.plate(sq, b1 - b0, (0, 1, 0), BARREL, FRM, cuts=[((0, b1 + 0.001, BORE_Z), (0, b1 - 0.012, BORE_Z), 0.0058, 10)])
    pipe(k, (0, b0 + 0.001, BORE_Z), (0, BARREL_FRONT, BORE_Z), BARREL_R, BARREL_BORE, BARREL, FRM, segs=12)
    y0, pitch, n, r, th = FINS
    for i in range(n):
        y = y0 + pitch * i
        k.cyl((0, y - th / 2, BORE_Z), (0, y + th / 2, BORE_Z), r, BARREL, BRZ, segs=10)


def build_rods(k):
    """The recoil guide rods: stainless steel, fixed in the tunnel's front wall, running back into the slide's bores."""
    x, z, r, (y0, y1) = RODS
    for sx in (1, -1):
        k.cyl((sx * x, y0, z), (sx * x, y1, z), r, "Root", JNT, segs=8)


# --------------------------------------------------------------------------------------------
# Parts: the frames, the grip, the trigger, the hammer, the slide stop, the catch
# --------------------------------------------------------------------------------------------

def build_frame(k):
    """The upper frame (matte titanium) under the slide, from the housing's rear face to the hammer: the
    web relief behind the grip, the hammer's slot between its rear cheeks; the stainless steel pins of the hammer
    and the slide stop through it, each showing past both flanks."""
    hw, hy = HAMMER_SLOT
    boxes = [((0, (hy + FRAME_Y[1] + 0.01) / 2, (BELLY + FRAME_Z[1]) / 2), (2 * hw, FRAME_Y[1] + 0.01 - hy, FRAME_Z[1] - BELLY + 0.004))]
    (wy0, wy1), wz = FRAME_WEB
    boxes.append(((0, (wy0 + wy1) / 2, (BELLY - 0.004 + wz) / 2), (2 * FRAME_W + 0.004, wy1 - wy0, wz - BELLY + 0.004)))
    carve(k, loft(list(FRAME_Y), frame_ring), "Root", FRM, boxes=boxes)
    W = FRAME_W
    hy_, hz_ = HAMMER_PIVOT[1:]
    k.cyl((-W - 0.0015, hy_, hz_), (W + 0.0015, hy_, hz_), 0.0018, "Root", JNT, segs=6)                       # hammer pin
    sy, sz = STOP_PIVOT[1:]
    k.cyl((-W - 0.0012, sy, sz), (STOP_X[1] + 0.0012, sy, sz), 0.0017, "Root", JNT, segs=6)                  # stop's pin


def lower_outline():
    """The lower frame's side outline (y, z): the trigger guard's front bar behind the cartridge and its
    bottom bar on the cartridge's line under the trigger, ending short of the curled fingers; the trigger
    block under the belly; the grip's core (its front strap, the flared pommel on z = 0, the web relief up
    its back), its top sunk into the upper frame's belly."""
    D = GRIP_HALF[1]
    bottom = lambda yl: grip_top(yl, 0.0)
    strap = lambda z: gw(-D, grip_top(-D, z))
    g0, g1 = GUARD_FRONT
    zb, th, ye = GUARD_BOTTOM
    zt = BELLY + 0.005
    (b0, b1), bz = TRIGGER_BLOCK
    pts = [(g0, zt), (g0, zb), (ye, zb), (ye, zb + th), (0.024, zb + th), (g1, zb + th + 0.004), (g1, bz),
           (b1 - 0.004, bz), (b1, bz + 0.004), (b1, BELLY - 0.0006), strap(BELLY - 0.0006),
           gw(-D, bottom(-D) + 0.013), gw(-D - 0.004, bottom(-D - 0.004) + 0.006), gw(-D + 0.002, bottom(-D + 0.002)),
           gw(D + 0.004, bottom(D + 0.004)), gw(D + 0.006, bottom(D + 0.006) + 0.006), gw(D, bottom(D) + 0.014),
           gw(D, WEB[1]), gw(WEB[0], WEB[2]), gw(WEB[0], grip_top(WEB[0]))]
    radii = [0, 0.006, 0.003, 0.003, 0.003, 0.004, 0, 0.002, 0.002, 0.002, 0.003, 0.002, 0.002, 0.004, 0.002, 0.002,
             0.003, 0, 0, 0]
    return rounded(pts, radii, n=2)


def build_lower(k):
    """The lower frame (matte titanium), one bevelled plate: the trigger guard (open at its rear, short of the
    fingers), the trigger's
    block and slot, the catch's slot and its tooth's hole in the guard's front bar, the grip's core
    with finger grooves along its front strap and a lanyard hole through the pommel; black grip panels
    on its sides, cross-grooved, a screw each; the trigger's stainless steel pin."""
    D = GRIP_HALF[1]
    outer = lower_outline()
    L = LOWER_HALF
    g0, g1 = GUARD_FRONT
    cz0, cz1 = CATCH_Z
    (b0, b1), bz = TRIGGER_BLOCK
    ty, tz = TRIGGER_PIVOT[1:]
    grooves = []
    for zl in (0.01, -0.01, -0.03):
        y, z = gw(-D - 0.0045, zl)
        grooves.append(((-0.02, y, z), (0.02, y, z), 0.0075, 8))
    ly, lz = gw(D - 0.009, grip_top(D - 0.009, 0.0) + 0.0075)
    lanyard = rounded([(ly - 0.0035, lz - 0.0017), (ly + 0.0035, lz - 0.0017), (ly + 0.0035, lz + 0.0017),
                       (ly - 0.0035, lz + 0.0017)], [0.0015] * 4, n=1)
    boxes = [((0, ty + 0.003, (bz - 0.002 + tz + 0.008) / 2), (0.009, 0.020, tz + 0.010 - bz)),                  # trigger slot
             ((0, (g0 + 0.002 + g1 + CATCH_TRAVEL + 0.001) / 2, (cz0 + cz1) / 2),
              (2 * L + 0.01, g1 + CATCH_TRAVEL + 0.001 - g0 - 0.002, cz1 - cz0 + 0.001)),                        # catch slot
             ((0, g0 + 0.0008, (cz0 + cz1) / 2), (0.0066, 0.0045, cz1 - cz0))]                                   # tooth's hole
    carve(k, slab_bm([(0, y, z) for y, z in outer], 2 * L, (1, 0, 0)), "Root", FRM,
          holes=[[Vector((0, y, z)) for y, z in lanyard]], cuts=grooves,
          boxes=boxes, bevel=0.0018, bevel_normal=(1, 0, 0))
    k.cyl((-L - 0.0012, ty, tz), (L + 0.0012, ty, tz), 0.0016, "Root", JNT, segs=6)                           # trigger pin
    panel_l = [(-D + 0.004, grip_top(-D + 0.004, 0.0) + 0.017), (D - 0.003, grip_top(D - 0.003, 0.0) + 0.019),
               (D - 0.003, WEB[1] - 0.004), (WEB[0] - 0.003, WEB[2] - 0.002), (WEB[0] - 0.003, 0.054), (-D + 0.004, 0.058)]
    panel = rounded([gw(*p) for p in panel_l], [0.004, 0.004, 0.002, 0.002, 0.003, 0.004], n=2)
    for sx in (1, -1):
        xo = sx * (L + PANEL)
        xc = sx * (L + PANEL / 2 - 0.0002)
        ribs = []
        for zl in [-0.026 + 0.0145 * i for i in range(5)]:
            (ya, za), (yb, zb_) = gw(-D + 0.007, zl), gw(D - 0.006, zl)
            (yc, zc), (yd, zd) = gw(D - 0.006, zl + 0.0018), gw(-D + 0.007, zl + 0.0018)
            ribs.append(([(xo, ya, za), (xo, yb, zb_), (xo, yc, zc), (xo, yd, zd)], (1, 0, 0), 0.0014))
        carve(k, slab_bm([(xc, y, z) for y, z in panel], PANEL + 0.0004, (1, 0, 0)), "Root", SEC, subtract=ribs)
        sy_, sz_ = gw(-0.009, 0.051)
        bolt(k, (xo, sy_, sz_), (sx, 0, 0), "Root", r=0.0017, head=0.0007)


def build_trigger(k):
    """The trigger: a small curved lever (metallic black) on its pin in the trigger block's slot."""
    py, pz = TRIGGER_PIVOT[1:]
    k.cyl((-0.0034, py, pz), (0.0034, py, pz), 0.0048, TRIGGER, MTL, segs=10)
    k.prism([(0, y, z) for y, z in TRIGGER_OUTLINE], 0.0062, (1, 0, 0), TRIGGER, MTL, convex=False)


def build_catch(k):
    """The cartridge catch (bone MagCatch): a cross bar in the guard's front bar's slot, its stainless steel tooth
    through the bar's front skin into the cartridge's notch, a bronze finger tab back into the guard."""
    g0, g1 = GUARD_FRONT
    cz0, cz1 = CATCH_Z
    k.span((-LOWER_HALF - 0.0025, g0 + 0.0025, cz0), (LOWER_HALF + 0.0025, g0 + 0.0075, cz1), CATCH_BONE, MTL)
    k.span((-0.0028, PACK_Y[1] - 0.0022, cz0 + 0.0005), (0.0028, g0 + 0.003, cz1 - 0.0005), CATCH_BONE, JNT)
    k.span((-0.004, g0 + 0.007, cz0 + 0.0002), (0.004, g1 + 0.004, cz1 - 0.0002), CATCH_BONE, BRZ)


def build_hammer(k):
    """The hammer (metallic black) between the frame's cheeks: a hub on its pin, the arm up to the head
    whose face strikes the firing pin's cap, a spur on its back."""
    k.prism([(0, y, z) for y, z in HAMMER_OUTLINE], 2 * HAMMER_HALF, (1, 0, 0), HAMMER, MTL, convex=False)
    hy, hz = HAMMER_PIVOT[1:]
    k.cyl((-HAMMER_HALF - 0.0003, hy, hz), (HAMMER_HALF + 0.0003, hy, hz), HAMMER_HUB, HAMMER, MTL, segs=10)


def build_slide_stop(k):
    """The slide stop (metallic black) on the frame's left flank: a hub on its pin, the arm back to the
    tip that rises into the slide's notch, a ribbed thumb tab under the tip."""
    sy, sz = STOP_PIVOT[1:]
    x0, x1 = STOP_X
    ty0, ty1, tz = STOP_TIP
    k.prism([((x0 + x1) / 2, y, z) for y, z in STOP_ARM], x1 - x0, (1, 0, 0), STOP, MTL, convex=False)
    k.cyl((x0 + 0.0003, sy, sz), (x1 + 0.0004, sy, sz), 0.0042, STOP, MTL, segs=10)
    k.plate([(x1 + 0.0009, y, z) for y, z in ((ty0 - 0.004, 0.1152), (ty1 + 0.0012, 0.1152), (ty1 + 0.0012, 0.1222),
                                              (ty0 - 0.004, 0.1222))], 0.0024, (1, 0, 0), STOP, MTL,
            boxes=[((x1 + 0.0021, y, 0.1187), (0.0012, 0.0012, 0.009)) for y in (ty0 - 0.0015, ty0 + 0.0015, ty0 + 0.0045)])


def build_gun(k, pistons, joints):
    build_housing(k)
    build_hook(k)
    build_sight(k)
    build_cap(k)
    build_display(k)
    build_dial(k)
    build_slide(k)
    build_barrel(k)
    build_rods(k)
    build_frame(k)
    build_lower(k)
    build_trigger(k)
    build_catch(k)
    build_hammer(k)
    build_slide_stop(k)


# --------------------------------------------------------------------------------------------
# Parts: the cartridge
# --------------------------------------------------------------------------------------------

def build_round(k, y1, x, z, bone):
    """A round lying along the bore (its base at y1): a bronze case and a steel-tipped bullet."""
    r, length = ROUND
    yc = y1 - 0.024
    k.cyl((x, y1, z), (x, yc, z), r, bone, BRZ, segs=8)
    k.cyl((x, yc + 0.0005, z), (x, y1 - length, z), r - 0.0002, bone, JNT, segs=8, r1=0.0022)


def build_pack(k):
    """The cartridge (bone Mag), metallic black, as wide as the housing: the rounds' cavity in its rear
    part, four slots through each flank onto the staggered rounds, its tongue up the housing's feed
    opening with the top rounds in it, the catch's notch in its rear face; on its front part (the power
    cell) the charge gauge's recess on the right flank with five lit pips (the side's one light)."""
    (y0, y1), W, (z0, z1) = PACK_Y, PACK_W, PACK_Z
    sec = rounded([(W, z0), (W, z1), (-W, z1), (-W, z0)], [LOW_R, 0, 0, LOW_R], n=3)
    (cy0, cy1), cw, cf = CAVITY
    ys, sw, (sz0, sz1) = SLOTS_Y
    boxes = [((0, (cy0 + cy1) / 2, (cf + z1 + 0.002) / 2), (2 * cw, cy1 - cy0, z1 + 0.002 - cf))]
    boxes += [((sx * (W + cw) / 2, y, (sz0 + sz1) / 2), (W - cw + 0.002, sw, sz1 - sz0)) for sx in (1, -1) for y in ys]
    (gy0, gy1), (gz0, gz1) = GAUGE
    boxes.append(((-W, (gy0 + gy1) / 2, (gz0 + gz1) / 2), (0.0024, gy1 - gy0, gz1 - gz0)))
    cz0, cz1 = CATCH_Z
    boxes.append(((0, y1, (cz0 + cz1) / 2), (0.0072, 2 * 0.0026, cz1 - cz0 + 0.0004)))
    k.plate([(x, (y0 + y1) / 2, z) for x, z in sec], y1 - y0, (0, 1, 0), MAG, MTL, boxes=boxes, bevel=0.0008)
    (t0, t1), tw, (tz0, tz1) = TONGUE
    k.plate([(tw, t0, (tz0 + tz1) / 2), (tw, t1, (tz0 + tz1) / 2), (-tw, t1, (tz0 + tz1) / 2), (-tw, t0, (tz0 + tz1) / 2)],
            tz1 - tz0, (0, 0, 1), MAG, MTL)
    for i in range(5):                                                                     # the gauge's pips
        y = gy0 + 0.004 + (gy1 - gy0 - 0.008) * (i + 0.5) / 5
        k.obox((-W + 0.0007, y - 0.003, (gz0 + gz1) / 2), (-W + 0.0007, y + 0.003, (gz0 + gz1) / 2), gz1 - gz0 - 0.003,
               0.001, (-1, 0, 0), MAG, EMI)
    for i in range(7):                                                                     # the staggered stack
        build_round(k, t1 - 0.0002, 0.0045 * (1 if i % 2 else -1), 0.0565 + 0.0088 * i, MAG)
    build_round(k, t1 - 0.0002, 0.0, TOP_ROUND_Z, MAG)


# --------------------------------------------------------------------------------------------
# Checks specific to the pistol
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """Joint-range sweeps on top of the animation frames: the slide's travel (the barrel and the hammer
    with it), the slide stop rising with the slide fully back and holding it open, the trigger, the
    hammer on its own, the catch, the cartridge with the catch pressed."""
    states = [(f"slide {SLIDE_TRAVEL * i / 12:.4f}", {SLIDE: SLIDE_TRAVEL * i / 12}) for i in range(1, 13)]
    states += [(f"stop {a:.1f} slide back", {SLIDE: SLIDE_TRAVEL, STOP: a}) for a in (1.5, 3.0, 4.5, STOP_UP)]
    states += [(f"slide {v:.4f} on the stop", {SLIDE: v, STOP: STOP_UP})
               for v in (SLIDE_LOCK, (SLIDE_LOCK + SLIDE_TRAVEL) / 2)]
    states += [(f"trigger {v}", {TRIGGER: v}) for v in range(0, TRIGGER_PULL + 1, 2)]
    states += [(f"hammer {a}", {HAMMER: a}) for a in range(0, HAMMER_MAX + 1, 5)]
    states += [(f"catch {CATCH_TRAVEL * i / 4:.4f}", {CATCH_BONE: CATCH_TRAVEL * i / 4}) for i in range(1, 5)]
    states += [(f"mag {MAG_TRAVEL * i / 10:.4f}", {CATCH_BONE: CATCH_TRAVEL, MAG: MAG_TRAVEL * i / 10}) for i in range(11)]
    return states


def check_envelope(kit):
    """Every weapon fits WEAPON_MAX (wide x long x high) at rest, its bottom on z = 0 (the item table's and the weapon holder's
    mount takes it by its bottom) and centred along its length. Returns its size."""
    parts = all_parts(kit)
    lo = Vector(min(p.lo[i] for p in parts) for i in range(3))
    hi = Vector(max(p.hi[i] for p in parts) for i in range(3))
    size, problems = hi - lo, []
    for i, what in enumerate(("wide", "long", "high")):
        if size[i] > WEAPON_MAX[i] + 1e-6:
            problems.append(f"{size[i]:.3f} m {what}: over the {WEAPON_MAX[i]} m limit")
    if abs(lo.z) > 1e-4:
        problems.append(f"its bottom is at z {lo.z:.4f}, not on z = 0")
    if abs(lo.y + hi.y) > 0.01:
        problems.append(f"not centred along its length (y {lo.y:.3f}..{hi.y:.3f})")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(problems))
    return size


def check_hand_sockets(kit):
    """Tensor's palm (a box in its hand bone frame) at each socket: it sinks into no part of the gun,
    and its face lies on the grip (within 1.5 mm); the support hand, closed (HAND_BOXES), stays behind the front
    face (the muzzle cap and the hook's exhaust vents are ahead of it) and under the flanks' gas vents."""
    problems = []
    wrist, x, y, z = hand_frame("Left")
    corners = [wrist + x * a + y * b + z * c for bx, by, bz in HAND_BOXES.values()
               for a in bx for b in by for c in bz]
    ahead = HOUSING_Y[0] + HAND_CLEAR - min(q.y for q in corners)
    if ahead > 0:
        problems.append(f"the support hand reaches {ahead * 1000:.1f} mm too far forward (over the front face)")
    high = max(q.z for q in corners) - (FLANK_VENTS[2][0] - HAND_CLEAR)
    if high > 0:
        problems.append(f"the support hand reaches {high * 1000:.1f} mm up over the gas vents")
    for side in ("Left", "Right"):   # (the support hand holds the cartridge from below, the hook ahead of it)
        parts = [p for p in all_parts(kit) if p.bone == "Root" or side == "Left" and p.bone == MAG]
        wrist, x, y, z = hand_frame(side)
        (a0, a1), hw, ht = PALM[:2], PALM[2], PALM[3]
        inner = [wrist + y * (a0 + (a1 - a0) * i / 8) + x * (hw * (2 * j / 6 - 1)) + z * (ht * (2 * l / 4 - 1)) * 0.98
                 for i in range(9) for j in range(7) for l in range(5)]
        sunk = [p for p in parts if any(p.buried(q) for q in inner)]
        if sunk:
            problems.append(f"{side} palm sinks into the part(s) from line(s) {sorted(p.line for p in sunk)}")
        face = [wrist + y * (a0 + (a1 - a0) * i / 8) + x * (hw * (2 * j / 6 - 1)) + z * ht for i in range(9) for j in range(7)]
        gap = min(min((p.bvh.find_nearest(q)[3] or 1.0) for q in face) for p in parts)
        if gap > 0.0015:
            problems.append(f"{side} palm is {gap * 1000:.1f} mm off its grip")
    if problems:
        raise SystemExit(f"[{NAME}] hand sockets failed:\n  " + "\n  ".join(problems))

def ammo_hand_frame(kit):
    """Tensor's left hand bone frame holding the ammo pack (at its rest; it rides the Mag bone), as hand_frame:
    (wrist pivot, X, Y, Z). Z onto the pack's outer end (against AMMO_OUT), Y across it (AMMO_ACROSS: the fingers
    spread over its far edge), X = Y x Z along it; the palm's face on the pack where it stands out furthest under
    the palm (rays from the palm's footprint), its knuckles AMMO_GRIP short of the far edge, centred along the pack."""
    pack = [p for p in all_parts(kit) if p.bone == MAG]
    verts = [v for p in pack for v in p.verts]
    out = Vector(AMMO_OUT).normalized()
    z = -out
    y = Vector(AMMO_ACROSS)
    y = (y - z * y.dot(z)).normalized()
    x = y.cross(z)
    top = max(v.dot(out) for v in verts)
    across = max(v.dot(y) for v in verts) - PALM[1] - AMMO_GRIP
    along = (max(v.dot(x) for v in verts) + min(v.dot(x) for v in verts)) / 2
    wrist = Matrix((x, y, out)).inverted() @ Vector((along, across, top + 0.05))
    (a0, a1), hw = PALM[:2], PALM[2]
    hits = [h.dot(out) for i in range(9) for j in range(7) for p in pack
            for h in [p.bvh.ray_cast(wrist + y * (a0 + (a1 - a0) * i / 8) + x * (hw * (2 * j / 6 - 1)), z)[0]] if h]
    wrist = Matrix((x, y, out)).inverted() @ Vector((along, across, max(hits) + PALM[3]))
    return wrist, x, y, z


def check_ammo_socket(kit, joints):
    """The palm on the ammo pack (ammo_hand_frame): it sinks into no part of the pack and its face lies on it (within
    1.5 mm) and, with the pack released (MAG_TRAVEL out), into no part of the gun. Returns the frame."""
    frame = ammo_hand_frame(kit)
    wrist, x, y, z = frame
    (a0, a1), hw, ht = PALM[:2], PALM[2], PALM[3]
    inner = [wrist + y * (a0 + (a1 - a0) * i / 8) + x * (hw * (2 * j / 6 - 1)) + z * (ht * (2 * l / 4 - 1)) * 0.98
             for i in range(9) for j in range(7) for l in range(5)]
    face = [wrist + y * (a0 + (a1 - a0) * i / 8) + x * (hw * (2 * j / 6 - 1)) + z * ht for i in range(9) for j in range(7)]
    pack = [p for p in all_parts(kit) if p.bone == MAG]
    gun = [p for p in all_parts(kit) if p.bone == "Root"]
    out = fk(joints, {MAG: MAG_TRAVEL})[MAG] @ fk(joints, {})[MAG].inverted()
    problems = []
    sunk = [p for p in pack if any(p.buried(q) for q in inner)]
    if sunk:
        problems.append(f"the palm sinks into the pack's part(s) from line(s) {sorted(p.line for p in sunk)}")
    gap = min(min((p.bvh.find_nearest(q)[3] or 1.0) for q in face) for p in pack)
    if gap > 0.0015:
        problems.append(f"the palm is {gap * 1000:.1f} mm off the pack")
    hit = [p for p in gun if any(p.buried(out @ q) for q in inner)]
    if hit:
        problems.append(f"with the pack released the palm sinks into the part(s) from line(s) {sorted(p.line for p in hit)}")
    if problems:
        raise SystemExit(f"[{NAME}] ammo hand socket failed:\n  " + "\n  ".join(problems))
    return frame


def ammo_socket_json(frame):
    """The AmmoHandSocket's entry in _rig.json (the hand sockets' convention, on the Mag bone)."""
    vec = lambda v: [round(c, 4) for c in v]
    godot = lambda v: [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]
    wrist, x, y, z = frame
    curls, (mx, mz, tc) = AMMO_GRIP_POSE
    pose = {f"Left{f}{seg}": [round(c * k, 1), 0, 0] for f, c in curls.items()
            for seg, k in (("Proximal", 1.0), ("Intermediate", 1.1), ("Distal", 0.8))}
    pose.update({"LeftThumbMetacarpal": [mx, 0, mz], "LeftThumbProximal": [tc, 0, 0], "LeftThumbDistal": [tc, 0, 0]})
    return {"hand_bone": "LeftHand", "bone": MAG,
            "grips": "the ammo pack for a reload, a wide grip: palm on its outer end, fingers across it and over its far edge, thumb up its front",
            "note": "given at the pack's rest; the empty rides the Mag bone. For a reload, put the support hand on it "
                    "where the pack is (released), carry the pack in that hand (pack = hand_bone_global * "
                    "socket_in_pack.inverse()) and put it back the same way",
            "wrist_blender": vec(wrist), "bone_x_blender": vec(x), "bone_y_blender": vec(y), "bone_z_blender": vec(z),
            "wrist_godot": godot(wrist), "bone_x_godot": godot(x), "bone_y_godot": godot(y), "bone_z_godot": godot(z),
            "grip_pose_deg": pose}


# --------------------------------------------------------------------------------------------
# Gizmos, preview markers and export
# --------------------------------------------------------------------------------------------

def gizmo_specs():
    """(name, bone, origin, forward, up) of every gizmo: an empty whose local +Y is `forward` and +Z
    `up` in Blender (in glTF / Godot: -Z forward, +Y up). The muzzle rides the barrel (it recoils with
    it); the shell ejection point is on the port in the crown, pointing up, right and back as a case leaves; the
    compensator vent on the raked top, pointing up; the hook's exhaust on its front face, pointing forward."""
    out = [("Muzzle", BARREL, Vector((0, CAP[0] - 0.01, BORE_Z)), Vector(FWD), Vector(UP))]
    (py0, py1), _ = EJECT_PORT
    eject = Vector((-0.45, 0.2, 0.87)).normalized()
    back = (Vector(BACK) - eject * eject.dot(Vector(BACK))).normalized()
    yp = (py0 + py1) / 2
    out.append(("ShellEject", "Root", Vector((0, yp, housing_top(yp))), eject, back))
    yc = sum(COMP[0]) / len(COMP[0])
    out.append(("CompVent", "Root", Vector((0, yc, housing_top(yc))), Vector(UP), Vector(BACK)))
    zv = sum(HOOK_VENTS[0]) / len(HOOK_VENTS[0])
    out.append(("HookVent", "Root", Vector((0, HOUSING_Y[0], zv)), Vector(FWD), Vector(UP)))
    return out


def place_on_bone(obj, rig, bone_name, m):
    """Parent obj to a bone and give it the world matrix m (at rest)."""
    bone = rig.data.bones[bone_name]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    obj.matrix_basis = m
    return obj


def build_gizmos(rig, specs, hands=True, ammo_frame=None):
    """The exported gizmos (empties, invisible in game), each on its bone, and the two hand sockets.
    A hand socket's glTF / Godot axes are Tensor's hand bone axes (X knuckle line, Y wrist to
    knuckles, Z out of the palm) and its origin the wrist pivot: in Blender that is local X = X,
    -Y = Z, +Z = Y, because Blender's exporter converts an empty's axes (+Y to -Z, +Z to +Y) but not a
    bone's."""
    objs = []
    for name, bone, origin, fwd, up in specs:
        e = bpy.data.objects.new(name, None)
        e.empty_display_type, e.empty_display_size = "SINGLE_ARROW", 0.03
        bpy.context.scene.collection.objects.link(e)
        m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
        m.translation = origin
        objs.append(place_on_bone(e, rig, bone, m))
    for side in ("Left", "Right") if hands else ():
        wrist, x, y, z = hand_frame(side)
        e = bpy.data.objects.new(f"{side}HandSocket", None)
        e.empty_display_type, e.empty_display_size = "ARROWS", 0.04
        bpy.context.scene.collection.objects.link(e)
        m = Matrix((x, -z, y)).transposed().to_4x4()
        m.translation = wrist
        objs.append(place_on_bone(e, rig, "Root", m))
    if ammo_frame is not None:
        wrist, x, y, z = ammo_frame                   # the ammo pack's socket rides the pack
        e = bpy.data.objects.new("AmmoHandSocket", None)
        e.empty_display_type, e.empty_display_size = "ARROWS", 0.04
        bpy.context.scene.collection.objects.link(e)
        m = Matrix((x, -z, y)).transposed().to_4x4()
        m.translation = wrist
        objs.append(place_on_bone(e, rig, MAG, m))
    return objs


def build_preview_markers(rig):
    """1 cm orange diamonds on the gizmos, for previews only (never exported)."""
    mat = bpy.data.materials.new("PRV_Marker")
    if mat.node_tree is None:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 0.45, 0.05, 1.0)
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.45, 0.05, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 3.0
    for name, bone, origin, fwd, up in gizmo_specs():
        bm = bmesh.new()
        r = 0.005
        tips = [bm.verts.new(v) for v in ((r, 0, 0), (-r, 0, 0), (0, 0, r), (0, 0, -r), (0, 2 * r, 0), (0, -r, 0))]
        for t in (tips[4], tips[5]):
            for i, j in ((0, 2), (2, 1), (1, 3), (3, 0)):
                bm.faces.new((tips[i], tips[j], t))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        mesh = bpy.data.meshes.new(f"PRV_{name}_Mesh")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mat)
        obj = bpy.data.objects.new(f"PRV_{name}", mesh)
        bpy.context.scene.collection.objects.link(obj)
        m = Matrix((fwd.cross(up), fwd, up)).transposed().to_4x4()
        m.translation = origin
        place_on_bone(obj, rig, bone, m)


def export_pickup(ammo):
    """The cartridge on its own for the pickup: an unskinned copy, upright as it rides under the housing
    (the rounds' tips toward -Y), its origin at its bottom centre."""
    mesh = ammo.data.copy()
    P = Matrix.Translation(-Vector((0, sum(PACK_Y) / 2, PACK_Z[0])))
    mesh.transform(P)
    obj = bpy.data.objects.new(f"SM_{TITLE}Ammo", mesh)
    bpy.context.scene.collection.objects.link(obj)
    select_only([obj])
    stem = f"{NAME}_ammo"
    prepare_export([obj], HERE, stem)
    select_only([obj])
    bpy.ops.export_scene.fbx(
        filepath=str(HERE / f"{stem}.fbx"), use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z", axis_up="Y", bake_space_transform=False, use_mesh_modifiers=False,
        mesh_smooth_type="OFF", add_leaf_bones=False, bake_anim=False, path_mode="COPY", embed_textures=True)
    bpy.ops.export_scene.gltf(
        filepath=str(HERE / f"{stem}.glb"), export_format="GLB", use_selection=True, export_yup=True,
        export_apply=False, export_skins=False, export_animations=False, export_materials="EXPORT")
    bpy.data.libraries.write(str(HERE / f"{stem}.blend"), {obj}, fake_user=True)   # (its own .blend)
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    return P


def cull_unseen_free(obj, rig, joints, pistons, states):
    """Delete the faces no viewer can ever see on a free-floating asset (a held weapon, a pickup): the
    framework's cull_unseen with no level surface, so any ray that leaves the mesh reaches a viewer.
    The asset is posed in every state (every animation frame and the joint sweeps), so a face that any
    motion or combination of motions uncovers stays. From points over each face rays go out on both
    sides (double-sided materials) over a sphere, with fans close to the axes and rings square to the
    bore axis (the running gaps between the rotors' discs are seen only edge-on). Glass hides nothing
    (the screen and rounds behind it show), though its own faces are tested. A face whose own rigid
    body blocks every ray is settled once at rest; a face hidden by other bodies is re-tested in every
    state where those bodies moved relative to it, the most different states first. A face sharing a
    smooth-shaded corner with a seen face stays, so shading never changes."""
    import numpy as np
    me = obj.data
    polys = [tuple(p.vertices) for p in me.polygons]
    # glass lets the rays through (what is behind it shows): its faces are tested but hide nothing
    glass = {i for i, p in enumerate(me.polygons) if obj.material_slots[p.material_index].name == GLS}
    occl = [(p[0],) * 3 if i in glass else p for i, p in enumerate(polys)]
    rest = np.array([v.co[:] for v in me.vertices])
    up = Vector((0, 0, 1))
    n_dirs = 320
    sphere = []
    for i in range(n_dirs):  # a Fibonacci sphere
        z = 1 - 2 * (i + 0.5) / n_dirs
        a = i * math.pi * (3 - math.sqrt(5))
        rr = math.sqrt(1 - z * z)
        sphere.append(Vector((rr * math.cos(a), rr * math.sin(a), z)))
    axes = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    for ax in axes:  # fans round each axis (slits seen straight on)...
        sphere.append(ax)
        for deg in (0.5, 1.0, 2.0, 4.0, 8.0):
            t = math.radians(deg)
            sphere += [ax * math.cos(t) + o * math.sin(t) for o in axes if abs(o.dot(ax)) < 0.5]
    for k in range(72):  # ...and rings square to the bore axis (the gaps between the rotors' discs)
        a = math.radians(5 * k)
        for deg in (0.0, 0.7, -0.7, 2.0, -2.0):
            t = math.radians(deg)
            sphere.append(Vector((math.cos(a) * math.cos(t), math.sin(t), math.sin(a) * math.cos(t))))
    sphere_np = np.array([d[:] for d in sphere])
    occ_verts, occ_faces = [], []

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
        """Does any ray from these points, on either side of normal n (double-sided materials), leave
        the mesh? With `hits` (a set), the bodies the rays meet are collected."""
        cos = sphere_np @ n
        for side in (1, -1):
            idx = np.nonzero(cos * side > 0.01)[0]
            off = n * (1e-4 * side)
            for p in pts if len(idx) else ():
                o = Vector(p + off)
                for i in idx:
                    loc, _, fi, _ = bvh.ray_cast(o, sphere[i])
                    if loc is None:
                        return True
                    if hits is not None:
                        hits.add(bone_of[fi])
        return False

    group_names = [g.name for g in obj.vertex_groups]
    bone_of = [group_names[me.vertices[p[0]].groups[0].group] for p in polys]
    static = {j.name for j in joints.values() if j.kind == "fixed" and j.parent is None}
    for j in joints.values():  # fixed joints on a fixed parent never move either
        if j.kind == "fixed" and j.parent in static:
            static.add(j.name)
    rest_n = np.array([p.normal[:] for p in me.polygons])

    def placement(f, mats):
        """Where the bodies hiding face f sit relative to its own body: while this is unchanged, every
        ray from the face meets the same geometry."""
        inv = mats[bone_of[f]].inverted()
        key = [round(x, 5) for b in sorted(blockers[f] | {bone_of[f]}) for row in (inv @ mats[b])[:3] for x in row]
        return tuple(key)

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
            # After the rest pose: a face whose every ray is stopped by its own rigid body alone stays
            # hidden however anything moves,
            # so only the faces hidden by other bodies go on to be tested in every state.
            by_bone = {}
            for f in pending:
                by_bone.setdefault(bone_of[f], []).append(f)
            for bone, faces in by_bone.items():
                own = [occl[i] for i in range(len(polys)) if bone_of[i] == bone]
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
        bvh = BVHTree.FromPolygons([Vector(v) for v in co] + occ_verts, occl + occ_faces)
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


def finish(obj, rig, joints, budget, cull_states):
    """Skin, cull the faces never seen (unless -- --no-cull), unwrap and hold to the budget."""
    check_coplanar(obj)
    skin(obj, rig)
    if "--no-cull" not in sys.argv:  # (-- --no-cull: an unculled build, to pixel-diff the cull against)
        t0 = time.time()
        cull_unseen_free(obj, rig, joints, [], cull_states)
        print(f"[{NAME}] {obj.name}: unseen-face cull took {time.time() - t0:.0f} s")
    unwrap(obj)
    tris = triangles(obj)
    print(f"[{NAME}] {obj.name}: {tris} tris (budget {budget})")
    if tris > budget and "--no-cull" not in sys.argv:  # an unculled reference build only reports it
        raise SystemExit(f"[{NAME}] {obj.name} over triangle budget: {tris}")
    return tris




def write_rig_json(ammo_frame, joints, pistons, tris, ammo_tris, size):
    def vec(v):
        return [round(c, 4) for c in v]

    def godot(v):
        return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]

    hands = {}
    for side in ("Left", "Right"):
        curls, (mx, mz, tc) = GRIP_POSE[side]
        pose = {f"{side}{f}{seg}": [round(c * k, 1), 0, 0] for f, c in curls.items()
                for seg, k in (("Proximal", 1.0), ("Intermediate", 1.1), ("Distal", 0.8))}
        pose.update({f"{side}ThumbMetacarpal": [mx, 0, mz], f"{side}ThumbProximal": [tc, 0, 0],
                     f"{side}ThumbDistal": [tc, 0, 0]})
        wrist, x, y, z = hand_frame(side)
        hands[f"{side}HandSocket"] = {
            "hand_bone": f"{side}Hand",
            "grips": "the front from below, palm up on the lower left arc of the hook and cartridge"
                     if side == "Left" else "pistol grip",
            "wrist_blender": vec(wrist), "bone_x_blender": vec(x), "bone_y_blender": vec(y), "bone_z_blender": vec(z),
            "wrist_godot": godot(wrist), "bone_x_godot": godot(x), "bone_y_godot": godot(y), "bone_z_godot": godot(z),
            "grip_pose_deg": pose}
    spec = lambda n: [{"name": g, "bone": b, "position": vec(o), "forward": vec(f), "up": vec(u)}
                      for g, b, o, f, u in gizmo_specs() if g.startswith(n)]
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, the muzzle points -Y, the origin is the gun's bottom centre (the grip's "
                 "pommel plane, midway along the gun). glTF/Godot: (x, z, -y), so the muzzle points +Z (glTF's front). "
                 "Hinges turn about their bone's local X (degrees), slides move along their bone's local Y (metres).",
        "rest": "slide and barrel home, hammer down on the firing pin, trigger forward, slide stop down, cartridge in, "
                "catch out",
        "size_m": {"wide": round(size.x, 3), "long": round(size.y, 3), "high": round(size.z, 3),
                   "max_wide_long_high": list(WEAPON_MAX), "bore_axis_height": round(BORE_Z, 4),
                   "note": "a full-size pistol's proportions at 1.25 scale, with its suppressor housing; every weapon "
                           "fits 0.25 x 0.75 x 0.35 m"},
        "materials": SLOTS,
        "triangles": {f"SK_{TITLE}": tris, f"SK_{TITLE}Ammo": ammo_tris, f"SM_{TITLE}Ammo": ammo_tris},
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "coupled": {BARREL: f"min({SLIDE}, {RECOIL}): the barrel rides the slide's first centimetre, locked to its breech "
                            "face (short recoil), then stops; the slide brings it home",
                    HAMMER: f"at least as far back as the slide cams it: the recoiling slide pushes it back and it rides "
                            f"home on the slide's rear face (baked into every action)"},
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "fire": {
            "shot": f"play fire (single shot, {ACT_F} frames): the trigger pulls and cocks the hammer {HAMMER_DA} deg "
                    f"(double action) and trips it; it falls on frame {SHOT_F}: fire the hitscan / spawn the muzzle "
                    f"flash at Muzzle then, and puff gas at CompVent. The slide runs {SLIDE_TRAVEL * 1000:g} mm back "
                    f"(the barrel {RECOIL * 100:g} cm with it), fully back on frame {EJECT_F}: throw the spent case "
                    f"from ShellEject (forward = its direction) then; it is home by frame {EJECT_F + 7}.",
            "last_round": f"fire_empty: as fire, but the slide stop rises and holds the slide open "
                          f"{SLIDE_LOCK * 1000:.1f} mm back; after mag_release and mag_insert play slide_release "
                          f"(the slide stop drops, the slide runs home).",
            "idle": f"loop idle ({IDLE_F} frames) between shots: it holds the rest pose (nothing on a pistol "
                    f"moves at rest); every action starts and ends at rest except fire_empty, which ends with the "
                    f"slide held open (follow it with the reload and slide_release).",
            "shot_frame": SHOT_F, "eject_frame": EJECT_F, "slide_travel_m": SLIDE_TRAVEL, "slide_lock_m": SLIDE_LOCK,
            "recoil_m": RECOIL},
        "gizmos": {
            "convention": "empties: in Blender local +Y is the gizmo's forward and +Z its up; in glTF / Godot -Z is "
                          "forward and +Y up (Marker3D / Node3D under a BoneAttachment3D, so they follow the "
                          "animations)",
            "muzzle": spec("Muzzle")[0],
            "muzzle_note": "1 cm in front of the suppressor cap's face, on the barrel's bone: the hitscan's origin and "
                           "where to play the muzzle flash (and its light)",
            "shell_eject": spec("ShellEject")[0],
            "shell_eject_note": "on the ejection port in the housing's crown, over the chamber, forward = up, to the "
                                "right and back as a case leaves: spawn the spent case there on fire's eject frame",
            "comp_vent": spec("CompVent")[0],
            "comp_vent_note": "over the compensator slots on the raked top, forward = up: a puff of gas on each shot",
            "hook_vent": spec("HookVent")[0],
            "hook_vent_note": "on the hook's front face over its exhaust slots, forward = out: the expansion chamber's "
                              "gas on each shot",
        },
        "ammo_hand_socket": ammo_socket_json(ammo_frame),
        "hand_sockets": {
            "convention": "origin = the wrist pivot (the head of the character's Hand bone); the socket's glTF / "
                          "Godot basis IS the Hand bone's basis for that grip (Tensor: X along the knuckle line, the "
                          "left thumb on -X and the right on +X, Y from the wrist to the knuckles, Z out of the palm). "
                          "In Godot set the hand bone's global pose to the socket's transform (relative to the "
                          "skeleton) and solve the arm to reach it; or carry the gun in the right hand with "
                          "gun = hand_bone_global * RightHandSocket_local.inverse(). In Blender the empties' own "
                          "axes are (X, -Z, Y) of the bone frame because the exporter converts empties, not bones.",
            "grip_pose": "grip_pose_deg per socket: Tensor's finger and thumb bone rotations (local XYZ, degrees) "
                         "that close each hand onto its grip (animations/retarget.py closes Tensor's hands to them); "
                         "the right index finger curls in to the trigger",
            **hands,
        },
        "ammo": {"mesh": f"SK_{TITLE}Ammo", "bone": MAG, "pickup_file": f"{NAME}_ammo.glb",
                 "pickup_mesh": f"SM_{TITLE}Ammo", "pickup_origin": "its bottom centre, upright", "axis": [0, 0, -1],
                 "rails_m": MAG_TRAVEL,
                 "note": "mag_release pulls the catch back and drops the cartridge down its channel; past "
                         "MAG_TRAVEL it is free: hide the cartridge mesh and drop a physics copy of the pickup mesh at "
                         "the Mag bone's transform. To reload, put the cartridge back at the end of its travel and "
                         "play mag_insert (the catch snaps into its notch)."},
        "usage": "idle (loop); fire per shot; fire_empty on the last round, then mag_release, mag_insert and "
                 "slide_release; mag_release / mag_insert alone swap a cartridge with the slide home.",
    }
    RIG_JSON_PATH.write_text(json.dumps(data, indent=2))



# --------------------------------------------------------------------------------------------
# The ammo pack as its own model and its attachment mount
# --------------------------------------------------------------------------------------------


def build_mounts(rig, pack_frame):
    """The separate ammo pack's bone-aligned attachment."""
    mount = bpy.data.objects.new("AmmoMount", None)
    mount.empty_display_type, mount.empty_display_size = "PLAIN_AXES", 0.03
    bpy.context.scene.collection.objects.link(mount)
    place_on_bone(mount, rig, MAG, pack_frame.inverted())
    return [mount]


def add_mounts_json(pack_frame):
    """Record the separate ammo pack attachment."""
    vec = lambda v: [round(c, 4) for c in v]
    godot = lambda v: [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]
    data = json.loads(RIG_JSON_PATH.read_text())
    m = pack_frame.inverted()
    q = m.to_quaternion()
    data["ammo_mount"] = {
        "gizmo": "AmmoMount", "bone": MAG, "model": f"{NAME}_ammo.glb", "mesh": f"SM_{TITLE}Ammo",
        "position_blender": vec(m.translation), "rotation_wxyz_blender": vec(q),
        "position_godot": godot(m.translation),
        "note": "the ammo pack is its own model (<name>_ammo.glb / .fbx / .blend, its origin at its bottom centre, "
                "square to its own axes, its real size): parent its mesh to the AmmoMount node unmoved and it rides "
                "the Mag bone where the weapon's actions put it (a reload's release and insert); the weapon's own "
                "files carry no pack mesh. The same model is the ammo pickup."}
    if "ammo" in data and isinstance(data["ammo"], dict):
        data["ammo"]["mesh"] = f"SM_{TITLE}Ammo in {NAME}_ammo.glb, at the AmmoMount gizmo"
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

    kit = Kit()  # every part, for the checks
    build_gun(kit, pistons, joints)
    build_pack(kit)
    size = check_envelope(kit)
    print(f"[{NAME}] size {size.x:.3f} wide x {size.y:.3f} long x {size.z:.3f} m high (max {WEAPON_MAX})")
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_hand_sockets(kit)
    ammo_frame = check_ammo_socket(kit, joints)
    states = action_states(actions, joints) + sweep_states(joints)
    check_motion(kit, joints, states)
    print(f"[{NAME}] checks passed ({len(states)} motion states); slide lock {SLIDE_LOCK * 1000:.1f} mm, hammer cammed "
          f"to {hammer_cam(SLIDE_TRAVEL):.1f} deg at full recoil")

    gun_kit, ammo_kit = Kit(), Kit()
    build_gun(gun_kit, pistons, joints)
    build_pack(ammo_kit)
    body = gun_kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    ammo = ammo_kit.to_object(f"SK_{TITLE}Ammo")
    tris = finish(body, rig, joints, TRI_BUDGET, states)
    ammo_tris = finish(ammo, rig, joints, AMMO_BUDGET, [])  # the cartridge only hides from itself: it detaches

    gizmos = build_gizmos(rig, gizmo_specs(), ammo_frame=ammo_frame)
    pack_frame = export_pickup(ammo)                   # (the pack as its own model)
    mounts = build_mounts(rig, pack_frame)
    export([rig, body, *gizmos, *mounts], NAME)
    bpy.data.objects.remove(ammo)                   # (the weapon's files carry no pack mesh)
    constrain(rig, joints, pistons)
    write_rig_json(ammo_frame, joints, pistons, tris, ammo_tris, size)
    add_mounts_json(pack_frame)
    build_preview_markers(rig)

    def pose_entry(jname, v):
        return {"rot": [v, 0, 0]} if joints[jname].kind == "hinge" else {"loc": [0, v, 0]}

    rig["preview_poses"] = json.dumps({s: {j: pose_entry(j, v) for j, v in expand(st).items()}
                                       for s, st in PREVIEW_STATES.items()})
    rig["preview_pose_views"] = json.dumps(PREVIEW_VIEWS)
    bpy.context.scene["preview_actions"] = json.dumps(SHOWCASE)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)
    print(f"[{NAME}] saved {BLEND_PATH}")
    print(f"[{NAME}] exported {NAME}.glb/.fbx, {NAME}_ammo.glb/.fbx, {RIG_JSON_PATH.name}")


if __name__ == "__main__":
    import sys
    if '--uv-only' in sys.argv:
        sys.path.insert(0, str(HERE.parents[1]))
        from material_uv import refresh_asset
        refresh_asset(HERE)
    else:
        main()
