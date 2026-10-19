"""Flamethrower - a pressurised flamethrower for KYLR, modelled, rigged and animated from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/weapons/flamethrower/model.py

Produces, next to this script:
    flamethrower.blend             source scene (the flamethrower, its twin-can pack and preview-only gizmo
                                   markers), opened by preview.py and animate.py
    flamethrower.glb / .fbx        SK_Flamethrower and SK_FlamethrowerAmmo skinned to RIG_Flamethrower, with the
                                   actions idle, fire_start, fire, fire_end, mag_release and mag_insert, and the
                                   gizmos Muzzle, PilotFlame, FumeVent, LeftHandSocket, RightHandSocket
    flamethrower_ammo.glb / .fbx   SM_FlamethrowerAmmo: the pack (two gas cans) on its own, origin under its
                                   valve on its bottom plane, for the in-game ammo pickup
    flamethrower_rig.json          joints, coupling, animations, gizmos, hand sockets, the pack

Design: the body is a pressure vessel, one shell lofted along the bore: a round section with four machined
flats (the crown the handles stand on, a flat down each flank for the fittings, the keel the pack plugs
into), a straight conical nose, a full-size front chamber, a 45-degree shoulder down to a slimmer rear and a
faceted domed head at the back; a bolted titanium flange over the nose's joint, a groove where the head
meets the body, vent slots cut into the rear's flanks (user: real vents, not strips) and a bolted
inspection boss on its crown. Military red nose, military yellow body, matte black head (user palette).
Out of the nose the nozzle (titanium, a stainless steel flared tip, bronze cooling fins) runs in a perforated black
heat shield between titanium collars, pulsing 1 cm back and home each second while it fires. Under the tip,
a pilot burner like a spark plug (a titanium shell through a spot-faced lug under the front collar, a
stainless steel hex, a ceramic insulator, its jet aimed up into the stream ahead of the nozzle) is fed by a thin
bronze gas line from its back, clipped under the shield, into the body's keel: it burns all the time and
lights the stream. The ammo pack (user: two smaller cans, tilted): two brushed aluminium gas cans with
matte black domes and bands, side by side under the body and pitched 12 degrees nose-down, joined at their
front domes by a shiny bronze crossover pipe, a relief valve on each back, clamped under a bolted manifold
yoke whose valve neck plugs up into a socket block under the keel, locked by a cross-bolt catch in a
groove round the neck. A bronze line runs from the socket to the fuel pump on the left flank: two black
cylinders ahead of a pump block, their stainless steel rods (bronze crossheads on them) stroking in turn while it
fires; a relief valve ahead of them. The fumes leave through a louvred exhaust on the right flank ahead of
the pressure gauge (its needle quivering at idle, dropping as it fires): three slats on stainless steel pins through
a titanium bezel's ends swing open while firing. Held like the minigun: the support hand on a side grip standing on
a titanium arm out of the left flank (user: the bail over the front it had first was out of the support arm's reach
in the carry), taken thumb up; the firing hand on an upright grip on top (a pistol grip standing on the crown); its
military red head carries the pistol's small
trigger, mirrored so its tip sweeps forward (user), in a trigger housing with an open guard, and the fuel
display tilted back to face the gunner (user). A red handwheel (the pilot's regulator) on the domed head.
Finish: military yellow and military red (user), matte black, brushed aluminium, stainless steel, bronze and
titanium.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a joint axis misses
its rotor or bearing, a slide leaves its guide, a palm would sink into a grip, the gun leaves its size
envelope, or anything collides through any animation frame or across the joints' ranges. Conventions:
1 unit = 1 m, Z up, the nozzle points -Y, the origin is on the gun's bottom plane (the cans' lowest point)
midway along it, so the item table's and the weapon holder's WeaponMount takes it by its bottom. Rest pose: nozzle home, trigger
forward, louvres shut, the gauge's needle up, pump rods home, pack in, catch out.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Alu': 'Metallic',
    'M_Bronze': 'Metallic',
    'M_Ceramic': 'Diffuse',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Metallic',
    'M_Joint': 'Metallic',
    'M_Metal': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Red': 'Metallic',
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

NAME = "flamethrower"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # Flamethrower

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000       # the flamethrower (SK_Flamethrower)
AMMO_BUDGET = 1_500      # the pack of two gas cans (SK_FlamethrowerAmmo / SM_FlamethrowerAmmo), on its own budget
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN, LEFT = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored)

# Size: every weapon fits a 0.25 (wide) x 0.75 (long) x 0.35 m (high) envelope, its bottom on z = 0,
# centred along its length (check_envelope). +x is the gun's left (the nozzle points -y).
WEAPON_MAX = (0.25, 0.75, 0.35)

BORE_Z = 0.155                         # the bore axis (the nozzle's)

# The body: one loft along the bore (body_ring). Its section: a circle BODY_R round the bore axis with four
# flats (FLATS: the side flats' x, the crown's and the keel's z from the axis), ARC_SEGS facets on each arc
# between them. A straight cone from the nose face (scaled NOSE[1]) to NOSE[0], the full section along the
# front chamber, a 45-degree shoulder (STEP) down to the slimmer rear, the domed head at the back (DOME:
# (y, scale) stations). Grooves (GROOVES, GROOVE_D deep) where the
# nose and the head meet the body; the nose face's edge chamfered EDGE. Military red ahead of the first
# groove, military yellow between, matte black behind the second (user palette).
BODY_R = 0.046
FLATS = (0.041, 0.040, 0.041)
ARC_SEGS = 3
BODY_FRONT = -0.228                    # the nose face
NOSE = (-0.1835, 0.88)                 # the cone's end (y), the section's scale at the nose face
GROOVES = ((-0.1835, -0.1815), (0.2665, 0.2685))
GROOVE_D = 0.0012
STEP = (0.010, 0.014, 0.92)            # the shoulder from the front chamber down to the slimmer rear: y, its scale
DOME = ((0.285, 0.92), (0.300, 0.895), (0.312, 0.83), (0.322, 0.72), (0.329, 0.57), (0.333, 0.42))
EDGE = 0.002
FLANGE = ((-0.1880, -0.1740), 1.10, 0.0021)  # the titanium flange bolted over the nose's joint: y, its
                                       # section's scale, the bolt heads' radius (one on each flat)
CROWN, KEEL = BORE_Z + FLATS[1], BORE_Z - FLATS[2]
REAR_CROWN, REAR_FLAT = BORE_Z + FLATS[1] * STEP[2], FLATS[0] * STEP[2]  # the rear's crown (z), side flats (x)
# The rear's vents (user: real vents, not strips): upright slots with round ends cut into its side flats,
# their walls dark: (side, y centres) and a slot's half-width, half-height, depth. A bolted titanium
# inspection boss on the rear's crown behind the grip (BOSS_TOP: y, radius, height).
VENTS = ((-1, (0.166, 0.1785, 0.191, 0.2035, 0.216, 0.2285)), (1, (0.2035, 0.216, 0.2285, 0.241)))
VENT_SLOT = (0.0025, 0.0120, 0.0040)
BOSS_TOP = (0.212, 0.0130, 0.0035)

# The nozzle (bone Barrel): a titanium tube sliding in the body's bore and the front collar's bushing, its
# stainless steel flared tip, bronze cooling fins inside the heat shield (seen through its holes). It pulses RECOIL
# back and home over RECOIL_F frames while firing (user rule: every barrel recoils 1 cm over 1 s).
NOZZLE_R, NOZZLE_BORE = 0.0115, 0.0075
GUIDE_R = NOZZLE_R + 0.00005           # the bores it slides in (a sliding fit)
NOZZLE_Y = (-0.205, -0.336)            # the tube's rear (in the body's bore), its front (in the tip)
TIP = (-0.334, -0.352, 0.0220)         # the stainless steel tip: its rear, its face, its flare's radius
FINS = ((-0.300, -0.279, -0.258), 0.0250, 0.003)  # y, radius, thickness
BORE_FLOOR = -0.191                    # the body's bore for the tube ends here
RECOIL, RECOIL_F = 0.010, (15, 15)
# The heat shield (fixed): a perforated matte black tube (hexagonal holes in staggered rings) between a
# titanium collar on the nose face and a front collar that is the nozzle's bushing.
SHIELD = ((-0.3215, -0.2255), 0.0310, 0.0290)  # y (front in the collar, rear sunk in the nose), outer, inner radius
SHIELD_HOLES = ((-0.300, -0.279, -0.258), 0.0048)  # the rings of holes (y), their radius (6-sided)
REAR_COLLAR = (-0.240, BODY_FRONT + 0.0005, 0.0340)  # y, radius
FRONT_COLLAR = (-0.323, -0.311, 0.0340)

# The pilot burner (fixed), under the nozzle's tip: a spark-plug-like body along PILOT_DIR through a lug
# under the front collar, its jet at PILOT_TIP aimed at PILOT_AIM (the stream ahead of the nozzle), the
# bronze gas line from its back (the terminal) under the shield (a clip on the rear collar) into the keel.
PILOT_TIP = (-0.3290, 0.1165)          # its jet (y, z)
PILOT_AIM = (-0.4000, BORE_Z)          # where its flame meets the stream
PILOT_LUG = ((-0.3225, -0.3125), (0.098, BORE_Z - FRONT_COLLAR[2] + 0.0015), 0.006)  # y, z, half-width
PILOT_LINE = (0.0016, -0.166)          # the gas line's radius, where it rises into the keel (y)
PILOT_CLIP = (-0.2365, -0.2305)        # the line's clip hanging from the rear collar (y)

# The gas cans (bone Mag), the ammo pack (user: two smaller cans, tilted): two bottles side by side under the
# body, pitched CAN_TILT nose-down, brushed aluminium with matte black domes and two raised black bands
# (user: dual tone), joined at their front domes by a shiny bronze crossover pipe (user), a relief valve on
# each one's back; a metallic black manifold yoke clamped
# across both carries the valve (a bronze boss, a stainless steel neck with a latch groove) plugged up into the socket
# block under the keel. The pack drops MAG_TRAVEL (the neck leaving the bore) before it is free. A can's
# local frame (can_frame): y along its axis, centred on the valve's y; its lowest point on z = 0.
CAN_R, BAND_T = 0.032, 0.0015
CANS_X = 0.034                         # the cans' axes (x, each side)
CAN_TILT = 12                          # nose-down (deg)
CAN_Y = (-0.075, 0.075, 0.018)         # a can's cylinder's front and back (local y), the domes' depth
BANDS = ((-0.045, 0.045), 0.008)       # the bands: local y centres, width
CROSSOVER = (0.0030, 0.016)            # the crossover pipe: radius, how far it runs ahead of the fittings
VALVE_Y = -0.015
MANIFOLD = ((VALVE_Y - 0.014, VALVE_Y + 0.014), 0.046, (0.064, 0.097))  # the yoke: y, half-width, z
BOSS = (0.014, (0.0965, 0.1040))       # the valve boss: radius (hex), z
NECK = (0.0075, (0.1030, 0.1435), (0.1100, 0.1130), 0.0015)  # the neck: radius, z, its groove's z, depth
MAG_TRAVEL = 0.030
SOCKET = ((VALVE_Y - 0.021, VALVE_Y + 0.021), 0.019, KEEL + 0.003, 0.0985)  # the socket block: y, half-width, its
                                       # top (in the keel), its bottom
SOCKET_BORE_TOP = 0.1445
# The catch (bone MagCatch): a stainless steel cross bolt through the socket block behind the neck, its black button
# on the right, a tooth on it in the neck's groove; pushed in (+x, toward the gun's left) the tooth clears.
CATCH = (VALVE_Y + 0.0098, 0.1115, 0.0018)  # the bolt's axis: y, z; radius
TOOTH = ((VALVE_Y + 0.0062, VALVE_Y + 0.0090), (0.1105, 0.1125), (-0.0035, 0.0035))  # y, z, x at rest
BUTTON = (-SOCKET[1] - 0.0045, 0.0040)  # its button's outer face (x), radius
CATCH_TRAVEL = 0.010

# Hands: Tensor's hand bone frame (X = knuckle line, Y = wrist to knuckles, Z = out of the palm), its palm
# 0.094 long from 1 cm past the wrist, 0.09 wide, its face 0.016 off the bone line. The support hand on the side
# grip (the minigun's grip, standing), the firing hand on the upright grip, which is a pistol grip standing on the
# crown (its hand frame, trigger and guard as the pistol's; the grip's head where the pistol's frame is).
PALM = (0.010, 0.104, 0.045, 0.016)    # palm along Y (from, to), half-width along X, half-thickness
GRIP_ALONG = {"Left": 0.070, "Right": 0.070}  # the grip line from the wrist along Y
# The side grip (user: instead of the bail over the front, which the support arm couldn't reach in the carry): a
# titanium arm square out of the left side flat, centred on it, on a bolted flange; a round matte black grip standing
# on its end in a titanium collar, a titanium cap on top; taken thumb up, the palm on its outer side, the fingers
# round its front, turned LGRIP_ROLL round its axis. Placed where the arm reaches (user: the sockets are where the
# animation puts the hands): over the carry clips, Tensor's support hand lands on it exactly from +40 to +55 deg.
LGRIP = (0.095, -0.060)                # the grip's axis (x, y)
LGRIP_R = 0.0165
LGRIP_Z = (BORE_Z - 0.015, 0.270)      # its collar's underside, its cap's top
LGRIP_HAND_Z = 0.2165                  # the hand's centre on it (the palm clear of the collar and the cap)
LGRIP_ROLL = 48                        # the support hand turned round the grip's axis, wrapping it from the front
LGRIP_ARM = (0.020, 0.022)             # the arm's width (y), height (z)
GRIP_RAKE = 15                         # the grip's rake (deg; its head forward)
GRIP_G = (0.0, 0.110, CROWN + 0.060)   # the firing hand's centre on the grip's axis
GRIP_HALF = (0.014, 0.023)             # grip half-width (x) and half-depth (fore-aft)
WEB = (0.012, 0.030, 0.040, 0.062)     # the web relief: the backstrap cut to this depth (local y) from z 0.030
                                       # (full by 0.040) up the grip from the hand's centre
HEAD = ((0.0145, 0.156), (GRIP_G[2] + 0.0725, 0.3395), 0.015)  # the grip's head: y, z (bottom, top), half-width
# The trigger: the pistol's small curved lever (user rule: every gun's), placed as on the pistol from the
# grip's hand centre; its block under the head, the open guard round it (its bottom bar stopping short of
# the curled fingers).
TRIGGER_PIVOT = (0.0, GRIP_G[1] - 0.0595, GRIP_G[2] + 0.0515)
TRIGGER_OUTLINE = [(-0.0040, -0.0025), (-0.0030, -0.0090), (0.0015, -0.0180), (0.0048, -0.0290), (0.0060, -0.0370),
                   (0.0058, -0.0405), (0.0048, -0.0418), (0.0070, -0.0428), (0.0095, -0.0415), (0.0105, -0.0350),
                   (0.0095, -0.0250), (0.0065, -0.0120), (0.0035, -0.0025)]  # from its pivot (y, z): the pistol's lever
                                       # turned round (user): its face concave, leaning forward from the pivot and
                                       # curving back to the index finger's seat, its tip turned forward; it ends over
                                       # the middle finger, which lies just under the index
TRIGGER_PULL = 12
GUARD_FRONT = (TRIGGER_PIVOT[1] - 0.032, TRIGGER_PIVOT[1] - 0.024)  # the guard's front bar (y)
GUARD_BOTTOM = (GRIP_G[2] - 0.005, 0.007, GRIP_G[1] - 0.060)  # its bottom bar: underside, thickness, rear end
TRIGGER_BLOCK = ((GUARD_FRONT[1], GRIP_G[1] - 0.042), TRIGGER_PIVOT[2] - 0.0075)  # the trigger's block: y, its bottom
TRIGGER_HALF = 0.0095                  # the trigger housing's half-width
DISPLAY = ((0.112, 0.146), 0.0105, 10)  # the fuel display on the head's top: y, half-width, tilt back (deg)
GRIP_POSE = {"Left": ({"Index": 60, "Middle": 65, "Ring": 60, "Little": 55}, (50, 25, 60)),
             "Right": ({"Index": 36, "Middle": 65, "Ring": 65, "Little": 52}, (42, -25, 50))}
# The support hand's grip on the ammo pack for a reload (user: every hand placement is a socket the animation plugs
# into, exported as AmmoHandSocket on the Mag bone; a wide grip, not a C cup): the palm flat on the pack's outer end
# (the face away from the gun), the fingers spread across it and over its far (right) edge, the thumb up its front;
# centred along the pack.
AMMO_ACROSS = (-1.0, 0.0, 0.0)   # the fingers' way across the pack (the left hand reaches over to its right edge)
AMMO_OUT = (0.0, 0.0, -1.0)   # its outer end (the way it leaves the gun)
AMMO_GRIP = 0.004                # the knuckles short of the pack's far edge (the fingers wrap over it)
AMMO_GRIP_POSE = ({"Index": 45, "Middle": 50, "Ring": 50, "Little": 45}, (25, 40, 15))  # spread, the thumb out

# The exhaust (bones Louvre1..3, top to bottom, Louvre1 driving): a pocket in the right side flat behind a
# titanium bezel; three black slats, each hanging from its knuckle on a stainless steel pin through the bezel's
# ends, slanting out to the bottom, swing out VENT_OPEN while firing so the fumes leave down and out.
LOUVRE = ((-0.160, -0.100), (BORE_Z - 0.0175, BORE_Z + 0.0175), 0.004, 0.002)  # the opening: y, z; the bezel's
                                       # end and edge walls
BEZEL_X = (-FLATS[0] + 0.0005, -FLATS[0] - 0.0060)  # the bezel: sunk into the flat, its face
SLAT = (-FLATS[0] - 0.0022, 0.0105, 0.0098, 0.0016, 0.0012, 0.0022)  # the pins' x, pitch, a slat's drop, the knuckle's
                                       # radius, its thickness, how far out its bottom edge slants
VENT_OPEN = 45
POCKET_X = -0.025                      # the pocket's floor
# The pressure gauge (bone Needle) on the right side flat: a titanium boss, a stainless steel bezel, the lit dial,
# the needle on a stainless steel hub; up at rest, down as the pressure falls while firing.
GAUGE = (-0.045, 0.0175, 0.0150)       # y, the boss's radius, the dial's
GAUGE_X = (-FLATS[0] + 0.0005, -FLATS[0] - 0.0060, -FLATS[0] - 0.0085)  # boss (sunk), dial, the bezel's face
NEEDLE_RANGE = (-80, 10)
NEEDLE_FIRE = -45
# The fuel pump on the left flank (bones PumpA, upper, and PumpB): two black cylinders on a bracket, their
# stainless steel rods running back through titanium glands into the pump block, a bronze crosshead on each rod;
# they stroke PUMP_STROKE back in turn while firing.
PUMP_X = REAR_FLAT + 0.0110             # the cylinders' axes (x)
PUMP_Z = (BORE_Z + 0.0095, BORE_Z - 0.0095)
PUMP_R, ROD_R = 0.0085, 0.0035
PUMP_CYL = (0.012, 0.096)              # the cylinders: front, rear (the gland behind)
GLAND = (0.094, 0.102, 0.0095)
PUMP_BLOCK = ((0.132, 0.188), REAR_FLAT + 0.0245)  # y, its outer face (x)
PUMP_BRACKET = (0.018, 0.026)          # the cylinders' front bracket (y)
PUMP_ROD = (0.080, 0.160)              # a rod at rest: front (in its cylinder), back (in the block)
CROSSHEAD = ((0.112, 0.118), 0.0060)   # y at rest, radius
PUMP_STROKE = 0.012
FUEL_LINE = 0.0022                     # the line from the socket block to the pump's block: radius
RELIEF = (-0.120, 0.0065)              # the relief valve on the left side flat ahead: y, its hex's radius
# The pilot's regulator: a red handwheel on the domed head's face.
WHEEL = (DOME[-1][0] + 0.0085, 0.0150, 0.0022)  # the rim's y, its radius, the rim's section radius

# Actions (30 fps). idle (loop): the pilot burns (the game's flame), the gauge's needle quivers and the
# pump rods breathe a little. fire_start pulls the trigger, swings the louvres open, drops the needle and
# starts the pump; fire (loop) holds them, the louvres fluttering, the rods stroking in turn (each twice a
# loop) and the nozzle pulsing 1 cm back and home; fire_end lets go and settles everything home.
# mag_release / mag_insert swap the pack.
IDLE_F = 60
START_F, FIRE_F, END_F = 8, 30, 14
ACT_F = 15

BARREL, TRIGGER, NEEDLE, MAG, CATCH_BONE = "Barrel", "Trigger", "Needle", "Mag", "MagCatch"
LOUVRES = ["Louvre1", "Louvre2", "Louvre3"]
PUMPS = ["PumpA", "PumpB"]

# slot: (base colour, metallic, roughness, emission strength[, alpha])
MATERIALS = {
    "M_Primary": ((0.521, 0.356, 0.076), 0.25, 0.5, 0.0),    # military yellow: the body
    "M_Secondary": ((0.018, 0.018, 0.02), 0.2, 0.72, 0.0),   # matte black: the domed head, shield, grip, sleeve,
                                                             # pump, slats, guard, the cans' domes and bands
    "M_Frame": ((0.29, 0.29, 0.30), 1.0, 0.5, 0.0),          # matte titanium: the nozzle, collars, bezel, glands
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),         # stainless steel: pins, rods, bolts, the tip, the neck
    "M_Emissive": ((1.0, 0.55, 0.16), 0.0, 0.4, 6.0),        # the fuel display, the gauge's dial (amber)
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.18, 0.0),         # fins, gas lines, crossheads, the cans' valve and
                                                             # crossover pipe (shiny)
    "M_Red": ((0.180, 0.035, 0.025), 0.3, 0.5, 0.0),         # military red: the nose, the grip's head,
                                                             # the handwheel, the needle
    "M_Metal": ((0.035, 0.036, 0.04), 1.0, 0.32, 0.0),       # metallic black: machined walls, grooves, the socket
                                                             # block, pump block, lug, trigger
    "M_Ceramic": ((0.80, 0.78, 0.72), 0.0, 0.35, 0.0),       # the pilot's insulator
    "M_Alu": ((0.60, 0.61, 0.63), 1.0, 0.32, 0.0),           # brushed aluminium: the gas cans' bodies
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, RED, MTL, CER, ALU = SLOTS
GLS = "M_Glass"                        # (no glass: the cull's glass test finds none)


def radial(az):
    return Vector((math.cos(math.radians(az)), 0.0, math.sin(math.radians(az))))


def tangent(az):
    return Vector((-math.sin(math.radians(az)), 0.0, math.cos(math.radians(az))))


def grip_axes():
    """The grip's frame: g up its axis (raked forward at the head), f forward square to it."""
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))
    return Vector((0, -s, c)), Vector((0, -c, -s))


def hand_frame(side):
    """Tensor's hand bone frame gripping each handle: (wrist pivot, X, Y, Z). Z points out of the palm onto
    the grip, Y from the wrist to the knuckles, X = Y x Z along the knuckle line (the left thumb on -X, the
    right on +X). The grip line runs across the palm GRIP_ALONG from the wrist, the grip's surface on the
    palm's face."""
    if side == "Left":   # support hand on the side grip, thumb up, fingers round its front, turned LGRIP_ROLL
        grip = Vector((LGRIP[0], LGRIP[1], LGRIP_HAND_Z))
        z, y, face = Vector((-1, 0, 0)), Vector((0, -1, 0)), LGRIP_R
        turn = Matrix.Rotation(math.radians(LGRIP_ROLL), 3, y.cross(z))   # round the grip's axis
        z, y = turn @ z, turn @ y
    else:                # firing hand on the upright grip, thumb up by the head, fingers round its front
        g, f = grip_axes()
        grip = Vector(GRIP_G)
        z, y, face = Vector((1, 0, 0)), f, GRIP_HALF[0]
    x = y.cross(z)
    wrist = grip - z * (face + PALM[3]) - y * GRIP_ALONG[side]
    return wrist, x, y, z


def pilot_dir():
    """The pilot's axis, from its terminal toward its jet (aimed at the stream)."""
    return Vector((0, PILOT_AIM[0] - PILOT_TIP[0], PILOT_AIM[1] - PILOT_TIP[1])).normalized()


def pilot_point(t):
    """A point on the pilot's axis, t along it from its jet (negative: back toward the terminal)."""
    return Vector((0, PILOT_TIP[0], PILOT_TIP[1])) + pilot_dir() * t


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


def wave(n, fn):
    """Keys on every frame 0..n of fn(u), u = f / n (a loop: fn(0) == fn(1))."""
    return [(f, fn(f / n)) for f in range(n + 1)]


def recoil_pulse():
    """The nozzle's pulse through the fire loop: RECOIL back over RECOIL_F[0] frames, fast then slowing
    (1 - (1 - u)^3), and home over RECOIL_F[1] (smoothstep)."""
    back, home = RECOIL_F
    keys = [(i, RECOIL * (1 - (1 - i / back) ** 3)) for i in range(back)]
    return keys + [(back + i, RECOIL * (1 - (3 - 2 * i / home) * (i / home) ** 2)) for i in range(home + 1)]


TAU = 2 * math.pi
STROKE = lambda u, ph: PUMP_STROKE * (1 - math.cos(TAU * (2 * u + ph))) / 2   # a rod's stroke through the fire loop

# Joints: (name, parent, kind, pivot, axis, bone direction, limits), world space. The nozzle recoils back,
# the trigger pulls back, the slats swing out (Louvre2 and 3 follow Louvre1, expand()), the needle turns
# down, the pump rods stroke back, the pack drops, the catch is pushed in.
_SLAT_Z = [LOUVRE[1][1] - 0.0020 - SLAT[1] * i for i in range(3)]
JOINT_SPECS = [
    ("Root", None, "fixed", (0, 0, 0), UP, UP, None),
    (BARREL, "Root", "slide", (0, NOZZLE_Y[0], BORE_Z), BACK, None, (0, RECOIL)),
    (TRIGGER, "Root", "hinge", TRIGGER_PIVOT, (1, 0, 0), DOWN, (0, TRIGGER_PULL)),
    *[(LOUVRES[i], "Root", "hinge", (SLAT[0], sum(LOUVRE[0]) / 2, _SLAT_Z[i]), BACK, DOWN, (0, VENT_OPEN))
      for i in range(3)],
    (NEEDLE, "Root", "hinge", (GAUGE_X[1], GAUGE[0], BORE_Z), (-1, 0, 0), UP, NEEDLE_RANGE),
    *[(PUMPS[i], "Root", "slide", (PUMP_X, sum(CROSSHEAD[0]) / 2, PUMP_Z[i]), BACK, None, (0, PUMP_STROKE))
      for i in range(2)],
    (MAG, "Root", "slide", (0, VALVE_Y, 0.0), DOWN, None, (0, MAG_TRAVEL)),
    (CATCH_BONE, "Root", "slide", (0, CATCH[0], CATCH[1]), LEFT, None, (0, CATCH_TRAVEL)),
]
PISTON_SPECS = []

_N = ACT_F
ANIMATIONS = {
    "idle": (True, "LINEAR", {
        NEEDLE: wave(IDLE_F, lambda u: 1.6 * math.sin(TAU * 2 * u) + 0.7 * math.sin(TAU * 5 * u)),
        PUMPS[0]: wave(IDLE_F, lambda u: 0.0015 * (1 - math.cos(TAU * u)) / 2),
        PUMPS[1]: wave(IDLE_F, lambda u: 0.0010 * (1 - math.cos(TAU * 2 * u)) / 2)}),
    "fire_start": (False, "LINEAR", {
        TRIGGER: eased([(0, 0), (2, TRIGGER_PULL), (START_F, TRIGGER_PULL)]),
        LOUVRES[0]: eased([(0, 0), (1, 0), (6, VENT_OPEN), (START_F, VENT_OPEN)]),
        NEEDLE: eased([(0, 0), (2, 0), (START_F, NEEDLE_FIRE)]),
        PUMPS[1]: eased([(0, 0), (1, 0), (START_F, PUMP_STROKE)])}),
    "fire": (True, "LINEAR", {
        TRIGGER: hold_keys(TRIGGER_PULL, FIRE_F),
        LOUVRES[0]: wave(FIRE_F, lambda u: VENT_OPEN - 2.5 * (1 - math.cos(TAU * 3 * u))),
        NEEDLE: wave(FIRE_F, lambda u: NEEDLE_FIRE + 3.0 * math.sin(TAU * 2 * u) + 1.2 * math.sin(TAU * 5 * u)),
        PUMPS[0]: wave(FIRE_F, lambda u: STROKE(u, 0.0)),
        PUMPS[1]: wave(FIRE_F, lambda u: STROKE(u, 0.5)),
        BARREL: recoil_pulse()}),
    "fire_end": (False, "LINEAR", {
        TRIGGER: eased([(0, TRIGGER_PULL), (3, 0), (END_F, 0)]),
        LOUVRES[0]: eased([(0, VENT_OPEN), (4, VENT_OPEN), (12, 0), (END_F, 0)]),
        NEEDLE: eased([(0, NEEDLE_FIRE), (3, NEEDLE_FIRE), (12, 4), (END_F, 0)]),
        PUMPS[1]: eased([(0, PUMP_STROKE), (8, 0), (END_F, 0)])}),
    "mag_release": (False, "LINEAR", {
        CATCH_BONE: eased([(0, 0), (3, CATCH_TRAVEL), (_N, CATCH_TRAVEL)]),
        MAG: shaped([(0, 0, "io"), (3, 0, "io"), (10, MAG_TRAVEL, "in")], _N)}),
    "mag_insert": (False, "LINEAR", {
        MAG: shaped([(0, MAG_TRAVEL, "io"), (8, 0, "io")], _N),
        CATCH_BONE: eased([(0, CATCH_TRAVEL), (8, CATCH_TRAVEL), (11, 0), (_N, 0)])}),
}
PREVIEW_STATES = {
    "fire": {TRIGGER: TRIGGER_PULL, LOUVRES[0]: VENT_OPEN, NEEDLE: NEEDLE_FIRE, PUMPS[0]: PUMP_STROKE, BARREL: RECOIL},
    "mag_out": {MAG: MAG_TRAVEL, CATCH_BONE: CATCH_TRAVEL},
}
PREVIEW_VIEWS = {"fire": ["front_left", "right", "rear_right"], "mag_out": ["front_left", "left"]}
FK_TEST_STATE = {BARREL: 0.006, TRIGGER: 5, LOUVRES[0]: 30, NEEDLE: -30, PUMPS[0]: 0.005, PUMPS[1]: 0.009,
                 MAG: 0.01, CATCH_BONE: 0.004}
SHOWCASE = ["idle", "fire_start", "fire", "fire", "fire", "fire_end", "idle", "mag_release", "mag_insert", "idle"]
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
# The flamethrower's coupled joints: the lower louvres follow the top one
# --------------------------------------------------------------------------------------------

def expand(state):
    """A joint state (or animation keys) with the coupled joints derived: Louvre2 and Louvre3 turn with
    Louvre1 (a link bar inside the bezel ties the three slats' cranks, as on a shutter)."""
    out = dict(state)
    if LOUVRES[0] in out:
        v = out[LOUVRES[0]]
        for name in LOUVRES[1:]:
            out[name] = list(v) if isinstance(v, list) else v
    return out


# --------------------------------------------------------------------------------------------
# Sections and helpers
# --------------------------------------------------------------------------------------------

def body_section(s=1.0, inset=0.0):
    """(x, z) of the body's section round the bore axis, scaled s and offset `inset` inward: the four arcs
    (ARC_SEGS facets each) from the left flat's top round over the crown, down the right, under the keel;
    the flats lie between them."""
    R = BODY_R * s - inset
    fx, fc, fk = (f * s - inset for f in FLATS)
    a_s, a_c, a_k = math.acos(fx / R), math.asin(fc / R), math.asin(fk / R)
    arcs = [(a_s, a_c), (math.pi - a_c, math.pi - a_s), (math.pi + a_s, math.pi + a_k),
            (2 * math.pi - a_k, 2 * math.pi - a_s)]
    pts = []
    for a0, a1 in arcs:
        pts += [(R * math.cos(a0 + (a1 - a0) * i / ARC_SEGS), R * math.sin(a0 + (a1 - a0) * i / ARC_SEGS))
                for i in range(ARC_SEGS + 1)]
    return pts


def body_scale(y):
    """The section's scale at y: the straight cone, the full section, the domed head's stations."""
    if y < NOSE[0]:
        return NOSE[1] + (1 - NOSE[1]) * (y - BODY_FRONT) / (NOSE[0] - BODY_FRONT)
    if y <= STEP[0]:
        return 1.0
    if y < STEP[1]:
        return 1.0 + (STEP[2] - 1.0) * (y - STEP[0]) / (STEP[1] - STEP[0])
    if y <= DOME[0][0]:
        return STEP[2]
    for (y0, s0), (y1, s1) in zip(DOME, DOME[1:]):
        if y0 <= y <= y1:
            return s0 + (s1 - s0) * (y - y0) / (y1 - y0)
    return DOME[-1][1] if y > DOME[-1][0] else 1.0


def body_stations():
    """(y, scale, inset) of the loft's rings: the nose face's chamfer, the cone, each groove (stepped in and
    out), the domed head."""
    st = [(BODY_FRONT, NOSE[1], EDGE), (BODY_FRONT + EDGE, body_scale(BODY_FRONT + EDGE), 0.0)]
    for i, (g0, g1) in enumerate(GROOVES):
        s = body_scale(g0)
        st += [(g0, s, 0.0), (g0 + 1e-4, s, GROOVE_D), (g1 - 1e-4, s, GROOVE_D), (g1, s, 0.0)]
        if i == 0:
            st += [(STEP[0], 1.0, 0.0), (STEP[1], STEP[2], 0.0)]
    return st + [(y, s, 0.0) for y, s in DOME]


def loft_rings(rings):
    """A closed bmesh through rings of points (the same count each), capped at both ends."""
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    bm.faces.new(vs[0][::-1])
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / (ab[0] ** 2 + ab[1] ** 2 or 1e-12)))
    return math.hypot(p[0] - a[0] - ab[0] * t, p[1] - a[1] - ab[1] * t)


def inside_2d(p, poly):
    x, y, c = p[0], p[1], False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def machined(p, poly, depth=0.0003):
    """Is (x, z) p inside the section poly by more than `depth` (a face the machining made)?"""
    return inside_2d(p, poly) and min(seg_dist(p, a, b) for a, b in zip(poly, poly[1:] + poly[:1])) > depth


def body_mat(f):
    """The body's colours: military red ahead of the first groove, military yellow to the second, matte black
    behind; metallic black on the faces the machining cut (the grooves, the vents, the exhaust's pocket)."""
    c = f.calc_center_median()
    f.normal_update()
    cap = abs(f.normal.y) > 0.99 and (abs(c.y - BODY_FRONT) < 1e-5 or abs(c.y - DOME[-1][0]) < 1e-5)
    if not cap and c.y > BODY_FRONT + EDGE + 1e-4 and machined((c.x, c.z - BORE_Z), body_section(body_scale(c.y))):
        return MTL
    if c.y < GROOVES[0][0]:
        return RED
    return SEC if c.y > GROOVES[1][1] else PRI


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


# --------------------------------------------------------------------------------------------
# Parts: the body and what stands on it
# --------------------------------------------------------------------------------------------

def build_body(k):
    """The body, lofted from its flatted round section (the cone, the grooves, the domed head) and
    machined: the nozzle's bore up the nose, the pack's neck bore up from the keel, the exhaust's pocket
    in the right side flat, the vent slots in the rear's side flats."""
    rings = [[Vector((x, y, BORE_Z + z)) for x, z in body_section(s, d)] for y, s, d in body_stations()]
    cuts = [bore_cut(BODY_FRONT - 0.01, BORE_FLOOR),
            (Vector((0, VALVE_Y, KEEL - 0.004)), Vector((0, VALVE_Y, SOCKET_BORE_TOP)), NECK[0] + 0.0004, 12)]
    hw, hh, dp = VENT_SLOT
    subtract = [([(sx * REAR_FLAT, y + a, BORE_Z + b) for a, b in rounded([(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)],
                                                                         [hw - 0.0001] * 4, n=1)], (1, 0, 0), 2 * dp)
                for sx, ys in VENTS for y in ys]
    (y0, y1), (z0, z1) = LOUVRE[:2]
    x0 = BEZEL_X[1]
    boxes = [(((x0 + POCKET_X) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (POCKET_X - x0, y1 - y0, z1 - z0))]
    carve(k, loft_rings(rings), "Root", PRI, cuts=cuts, boxes=boxes, subtract=subtract, material=body_mat)


def build_flange(k):
    """The titanium flange bolted over the joint between the nose and the body: the body's flatted section
    scaled up, its edges chamfered, a stainless steel bolt head on its front face at each flat."""
    (y0, y1), s, br = FLANGE
    e = 0.0012
    rings = [[Vector((x, y, BORE_Z + z)) for x, z in body_section(s, d)] for y, d in ((y0, e), (y0 + e, 0.0),
                                                                                    (y1 - e, 0.0), (y1, e))]
    k.emit(loft_rings(rings), "Root", FRM, False, convex=False, exact=True)
    cone = body_scale(y0)
    for a, f in ((0, FLATS[0]), (90, FLATS[1]), (180, FLATS[0]), (270, FLATS[2])):
        r = f * (cone + s) / 2
        d = Vector((math.cos(math.radians(a)), 0, math.sin(math.radians(a))))
        bolt(k, Vector((0, y0, BORE_Z)) + d * r, (0, -1, 0), "Root", r=br, head=0.0014)


def build_boss(k):
    """The inspection boss on the rear's crown behind the grip: a titanium boss, a stainless steel hex nut on its centre,
    four stainless steel screws round it."""
    y, r, h = BOSS_TOP
    z = REAR_CROWN
    k.cyl((0, y, z - 0.001), (0, y, z + h), r, "Root", FRM, segs=12)
    k.cyl((0, y, z + h - 0.0005), (0, y, z + h + 0.0030), 0.0055, "Root", JNT, segs=6)
    for a in (45, 135, 225, 315):
        d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0)) * (r - 0.0035)
        bolt(k, (d.x, y + d.y, z + h - 0.0003), (0, 0, 1), "Root", r=0.0016, head=0.0010)


def build_relief(k):
    """The pressure relief valve standing out of the left side flat ahead of the pump: a bronze hex body, a
    stainless steel cap."""
    y, r = RELIEF
    x = FLATS[0]
    k.cyl((x - 0.0005, y, BORE_Z), (x + 0.0070, y, BORE_Z), r, "Root", BRZ, segs=6)
    k.cyl((x + 0.0068, y, BORE_Z), (x + 0.0100, y, BORE_Z), r - 0.0020, "Root", JNT, segs=8)


def build_side_grip(k):
    """The side grip: a titanium arm square out of the left side flat (centred on it) on a metallic black flange with
    four bolts, its end in the titanium collar at the foot of a round matte black grip standing over it, a titanium
    cap on top."""
    gx, gy = LGRIP
    z0, z1 = LGRIP_Z
    aw, ah = LGRIP_ARM
    x0 = FLATS[0]
    flange = rounded([(gy - 0.019, BORE_Z - 0.015), (gy + 0.019, BORE_Z - 0.015), (gy + 0.019, BORE_Z + 0.015),
                      (gy - 0.019, BORE_Z + 0.015)], [0.005] * 4, n=1)
    k.plate([(x0 + 0.0015, y, z) for y, z in flange], 0.005, (1, 0, 0), "Root", MTL)
    for a in (-0.0135, 0.0135):
        for b in (-0.0105, 0.0105):
            bolt(k, (x0 + 0.004, gy + a, BORE_Z + b), (1, 0, 0), "Root", r=0.0020, head=0.0012)
    k.obox((x0 + 0.003, gy, BORE_Z), (gx, gy, BORE_Z), aw, ah, (0, 0, 1), "Root", FRM, bevel=0.002)   # the arm
    k.cyl((gx, gy, z0), (gx, gy, z0 + 0.030), LGRIP_R + 0.003, "Root", FRM, segs=10)                 # collar
    k.cyl((gx, gy, z0 + 0.0295), (gx, gy, z1 - 0.0065), LGRIP_R, "Root", SEC, segs=10)                # grip
    k.cyl((gx, gy, z1 - 0.007), (gx, gy, z1), LGRIP_R + 0.0015, "Root", FRM, segs=10)                 # cap


def build_grip(k):
    """The upright grip on the crown (matte black), a pistol grip standing up: raked forward at its head,
    machined in its own frame (z up its axis, -y forward): finger grooves on its front, slanted grip grooves
    across both sides, its base flared onto the crown and sunk 3 mm in, a beavertail under the head over the
    hand's web and a web relief under it, its top sunk 5 mm into the head, its section chamfered."""
    G = Vector(GRIP_G)
    hx, D = GRIP_HALF
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))

    def top(y):  # local z of the head's underside (+5 mm) at local y
        return (HEAD[1][0] + 0.005 - G.z - y * s) / c

    def bottom(y):  # local z of the rear's crown (-3 mm) at local y
        return (REAR_CROWN - 0.003 - G.z - y * s) / c

    prof = [(-D, top(-D)), (-D, -0.044), (-D - 0.004, -0.051), (-D + 0.002, bottom(-D + 0.002)),
            (D + 0.004, bottom(D + 0.004)), (D + 0.006, -0.050), (D, -0.041), (D, WEB[1]), (WEB[0], WEB[2]),
            (WEB[0], min(WEB[3], top(D) - 0.014))]
    if top(D) - 0.014 > WEB[3] + 0.008:
        prof += [(D, WEB[3] + 0.008), (D, top(D) - 0.014)]
    prof += [(D + 0.016, top(D + 0.016) - 0.004), (D + 0.016, top(D + 0.016))]
    frame = Matrix.Translation(G) @ Matrix.Rotation(math.radians(GRIP_RAKE), 4, "X")
    with k.frame(frame):
        grooves = [((-0.02, -D - 0.0045, z), (0.02, -D - 0.0045, z), 0.0075, 8) for z in (0.01, -0.01, -0.03)]
        ribs = [([(sx * hx, y, z + dz) for y, dz in ((-D + 0.007, 0.0), (D - 0.005, 0.006), (D - 0.005, 0.009),
                                                     (-D + 0.007, 0.003))], (1, 0, 0), 0.0024)
                for sx in (1, -1) for z in (-0.032, -0.016, 0.000)]
        k.plate([(0, y, z) for y, z in prof], 2 * hx, (1, 0, 0), "Root", SEC,
                intersect=[([(x, z, 0) for x, _, z in octagon_xz(hx, -D - 0.02, D + 0.02, 0.005, 0.005, 0)], (0, 0, 1), 1.0)],
                cuts=grooves, subtract=ribs)


def build_head(k):
    """The grip's head (military red): a block over the grip carrying the trigger housing, its front raked,
    its long edges chamfered; the fuel display standing on its top, tilted back toward the gunner (the top's
    one light), a stainless steel screw beside it."""
    (y0, y1), (z0, z1), hw = HEAD
    outline = rounded([(y0, z0), (y1, z0), (y1, z1), (y0 + 0.012, z1), (y0, z1 - 0.006)],
                      [0.0015, 0.004, 0.004, 0.003, 0.0015], n=2)
    sec = [(a, (y0 + y1) / 2, b) for a, b in chamfered(hw, z0, z1, 0.0015, 0.0035)]
    k.plate([(0, y, z) for y, z in outline], 2 * hw, (1, 0, 0), "Root", RED, intersect=[(sec, (0, 1, 0), 0.3)])
    (d0, d1), dw, tilt = DISPLAY
    t = math.tan(math.radians(tilt))
    h0 = 0.0015
    side = [(d0, z1 - 0.0005), (d1, z1 - 0.0005), (d1, z1 + h0), (d0, z1 + h0 + (d1 - d0) * t)]  # high at the front
    k.prism([(0, y, z) for y, z in side], 2 * dw, (1, 0, 0), "Root", MTL)
    n = Vector((0, math.sin(math.radians(tilt)), math.cos(math.radians(tilt))))
    a = Vector((0, d0 + 0.004, z1 + h0 + (d1 - d0 - 0.004) * t))
    b = Vector((0, d1 - 0.004, z1 + h0 + 0.004 * t))
    k.obox(a + n * 0.0002, b + n * 0.0002, 2 * dw - 0.005, 0.0008, tuple(n), "Root", EMI)
    bolt(k, (0, y0 + 0.022, z1 - 0.0004), (0, 0, 1), "Root", r=0.0022, head=0.0012)


def build_trigger_housing(k):
    """The trigger housing (matte black), one bevelled plate hanging from the head: the open trigger guard (its
    front bar, its bottom bar ending short of the curled fingers) and the trigger's block and slot, its back
    into the grip's front; the trigger's stainless steel pin."""
    g0, g1 = GUARD_FRONT
    zb, th, ye = GUARD_BOTTOM
    zt = HEAD[1][0] + 0.004
    (b0, b1), bz = TRIGGER_BLOCK
    pts = [(g0, zt), (g0, zb), (ye, zb), (ye, zb + th), (g1 + 0.010, zb + th), (g1, zb + th + 0.004), (g1, bz),
           (b1, bz), (b1, zt)]
    outline = rounded(pts, [0, 0.006, 0.003, 0.003, 0.003, 0.004, 0.002, 0, 0], n=2)
    ty, tz = TRIGGER_PIVOT[1:]
    boxes = [((0, ty + 0.003, (bz - 0.002 + tz + 0.008) / 2), (0.009, 0.020, tz + 0.010 - bz))]
    carve(k, slab_bm([(0, y, z) for y, z in outline], 2 * TRIGGER_HALF, (1, 0, 0)), "Root", SEC, boxes=boxes,
          bevel=0.0015, bevel_normal=(1, 0, 0))
    k.cyl((-TRIGGER_HALF - 0.0012, ty, tz), (TRIGGER_HALF + 0.0012, ty, tz), 0.0016, "Root", JNT, segs=6)


def build_trigger(k):
    """The trigger: the pistol's small curved lever (metallic black) on its pin in the block's slot."""
    py, pz = TRIGGER_PIVOT[1:]
    k.cyl((-0.0034, py, pz), (0.0034, py, pz), 0.0048, TRIGGER, MTL, segs=10)
    k.prism([(0, py + y, pz + z) for y, z in TRIGGER_OUTLINE], 0.0062, (1, 0, 0), TRIGGER, MTL, convex=False)


def build_exhaust(k):
    """The louvred exhaust in the right side flat: a titanium bezel round the pocket, three stainless steel pins through
    its ends; on each pin a black slat (bone Louvre1..3) hanging from its knuckle, slanting out to its bottom
    edge over the knuckle below."""
    (y0, y1), (z0, z1), we, wz = LOUVRE
    bx0, bx1 = BEZEL_X
    xm = (bx0 + bx1) / 2
    outer = rounded([(y0 - we, z0 - wz), (y1 + we, z0 - wz), (y1 + we, z1 + wz), (y0 - we, z1 + wz)], [0.0015] * 4, n=1)
    hole = [(xm, y, z) for y, z in [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]]
    k.plate([(xm, y, z) for y, z in outer], bx0 - bx1, (1, 0, 0), "Root", FRM, holes=[hole], bevel=0.0008)
    px, pitch, drop, kr, th, slant = SLAT
    for i, bone in enumerate(LOUVRES):
        pz = _SLAT_Z[i]
        k.cyl((px, y0 - we - 0.0008, pz), (px, y1 + we + 0.0008, pz), 0.0010, "Root", JNT, segs=6)       # pin
        k.cyl((px, y0 + 0.0005, pz), (px, y1 - 0.0005, pz), kr, bone, SEC, segs=8)                        # knuckle
        plate = [(px + th / 2, pz), (px - th / 2, pz), (px - slant - th / 2, pz - drop), (px - slant + th / 2, pz - drop)]
        k.prism([(x, (y0 + y1) / 2, z) for x, z in plate], y1 - y0 - 0.0016, (0, 1, 0), bone, SEC)


def build_gauge(k):
    """The pressure gauge on the right side flat: a titanium boss, the lit dial, a stainless steel bezel ring round it,
    the military red needle on its stainless steel hub (bone Needle)."""
    y, rb, rd = GAUGE
    xb, xd, xf = GAUGE_X
    k.cyl((xb, y, BORE_Z), (xd, y, BORE_Z), rb, "Root", FRM, segs=12)                                     # boss
    k.cyl((xd + 0.0002, y, BORE_Z), (xd - 0.0004, y, BORE_Z), rd + 0.0003, "Root", EMI, segs=12)          # dial
    pipe(k, (xd + 0.0003, y, BORE_Z), (xf, y, BORE_Z), rb + 0.0006, rd, "Root", JNT, segs=12)                        # bezel
    k.cyl((xd - 0.0001, y, BORE_Z), (xd - 0.0024, y, BORE_Z), 0.0020, NEEDLE, JNT, segs=8)                # hub
    x = xd - 0.0016
    k.prism([(x, y + dy, BORE_Z + dz) for dy, dz in ((-0.0012, -0.003), (0.0012, -0.003), (0.0005, 0.0115),
                                                    (-0.0005, 0.0115))], 0.0006, (1, 0, 0), NEEDLE, RED)


def build_pump(k):
    """The fuel pump on the left side flat: two black cylinders from a bracket back to their titanium glands,
    the metallic black pump block behind (bolted), their stainless steel rods (bones PumpA, PumpB) from inside the
    cylinders back into the block, a bronze crosshead on each."""
    (c0, c1), (g0, g1, gr) = PUMP_CYL, GLAND
    xi = REAR_FLAT - 0.0005
    for i, z in enumerate(PUMP_Z):
        k.cyl((PUMP_X, c0, z), (PUMP_X, c1, z), PUMP_R, "Root", SEC, segs=10)
        k.cyl((PUMP_X, c0 - 0.003, z), (PUMP_X, c0 + 0.001, z), PUMP_R - 0.0018, "Root", FRM, segs=10)     # end cap
        k.cyl((PUMP_X, g0, z), (PUMP_X, g1, z), gr, "Root", FRM, segs=10)                                  # gland
        k.cyl((PUMP_X, PUMP_ROD[0], z), (PUMP_X, PUMP_ROD[1], z), ROD_R, PUMPS[i], JNT, segs=6)            # rod
        (h0, h1), hr = CROSSHEAD
        k.cyl((PUMP_X, h0, z), (PUMP_X, h1, z), hr, PUMPS[i], BRZ, segs=6)                                 # crosshead
    zb, zt = BORE_Z - 0.0185, BORE_Z + 0.0185
    (b0, b1), bx = PUMP_BLOCK
    sec = [(x, (b0 + b1) / 2, z) for x, z in rounded([(xi, zb), (bx, zb), (bx, zt), (xi, zt)], [0, 0.003, 0.003, 0], n=1)]
    k.plate(sec, b1 - b0, (0, 1, 0), "Root", MTL, bevel=0.0012)
    for y in (b0 + 0.008, b1 - 0.008):
        for z in (zb + 0.006, zt - 0.006):
            bolt(k, (bx - 0.001, y, z), (1, 0, 0), "Root", r=0.0022, head=0.0014)
    ro = PUMP_X + PUMP_R + 0.003
    br = rounded([(xi, zb), (ro, zb), (ro, zt), (xi, zt)], [0, 0.004, 0.004, 0], n=2)
    k.plate([(x, sum(PUMP_BRACKET) / 2, z) for x, z in br], PUMP_BRACKET[1] - PUMP_BRACKET[0], (0, 1, 0), "Root", MTL)


def build_fuel_line(k):
    """The bronze fuel line from the socket block's left face, under the body, up into the pump block."""
    y, z = VALVE_Y + 0.005, KEEL - 0.0055
    x0 = SOCKET[1]
    yb, zb = sum(PUMP_BLOCK[0]) / 2, BORE_Z - 0.0185
    pts = [(x0, y, z), (0.040, y, z), (0.040, yb - 0.012, z), (PUMP_X, yb, z + 0.011), (PUMP_X, yb, zb)]
    k.tube(pts, FUEL_LINE, "Root", BRZ, sides=6)


def build_wheel(k):
    """The pilot's regulator on the domed head's face: a stainless steel stem and hub, a military red handwheel (a rim
    on three spokes)."""
    wy, wr, sr = WHEEL
    ye = DOME[-1][0]
    k.cyl((0, ye - 0.001, BORE_Z), (0, wy + 0.0010, BORE_Z), 0.0035, "Root", JNT, segs=8)                   # stem
    k.cyl((0, wy - 0.0025, BORE_Z), (0, wy + 0.0025, BORE_Z), 0.0055, "Root", JNT, segs=8)                  # hub
    prof = [(wr + sr * math.cos(math.radians(a)), wy + sr * math.sin(math.radians(a))) for a in range(0, 360, 90)]
    lathe(k, prof, "Root", RED, segs=12, cz=BORE_Z, loop=True)                                            # rim
    for az in (90, 210, 330):
        d = Vector((math.cos(math.radians(az)), 0, math.sin(math.radians(az))))
        c = Vector((0, wy, BORE_Z))
        k.obox(c + d * 0.004, c + d * (wr + 0.0005), 0.0030, 0.0028, (0, 1, 0), "Root", RED)              # spoke


# --------------------------------------------------------------------------------------------
# Parts: the nozzle, the heat shield, the pilot
# --------------------------------------------------------------------------------------------

def build_nozzle(k):
    """The nozzle (bone Barrel): a titanium tube, the stainless steel flared tip on its front, bronze cooling fins."""
    pipe(k, (0, NOZZLE_Y[0], BORE_Z), (0, NOZZLE_Y[1], BORE_Z), NOZZLE_R, NOZZLE_BORE, BARREL, FRM, segs=12)
    t0, t1, rf = TIP
    prof = [(NOZZLE_R + 0.0010, t0), (NOZZLE_R + 0.0010, t0 - 0.004), (0.0190, t0 - 0.0115), (rf, t1 + 0.002),
            (rf - 0.0006, t1), (0.0175, t1), (0.0110, t1 + 0.007), (0.0090, t0 - 0.0035), (NOZZLE_R - 0.0003, t0 - 0.0025),
            (NOZZLE_R - 0.0003, t0)]
    lathe(k, prof, BARREL, JNT, segs=12, loop=True)
    ys, fr, th = FINS
    for y in ys:
        k.cyl((0, y - th / 2, BORE_Z), (0, y + th / 2, BORE_Z), fr, BARREL, BRZ, segs=10)


def build_shield(k):
    """The heat shield (matte black): a tube with staggered rings of hexagonal holes onto the nozzle and its
    fins, between the titanium collar on the nose face and the front collar (the nozzle's bushing)."""
    (s0, s1), ro, ri = SHIELD
    bm = revolve_bm([(ro, s0), (ro, s1), (ri, s1), (ri, s0)], (0, 0, BORE_Z), (0, 1, 0), (1, 0, 0), segs=12, loop=True)
    ys, hr = SHIELD_HOLES
    cuts = []
    for i, y in enumerate(ys):
        for j in range(2):
            a = math.radians(45 + 90 * j + (45 if i % 2 else 0))
            d = Vector((math.cos(a), 0, math.sin(a))) * 0.04
            cuts.append((Vector((0, y, BORE_Z)) - d, Vector((0, y, BORE_Z)) + d, hr, 6))
    carve(k, bm, "Root", SEC, cuts=cuts)
    c0, c1, cr = REAR_COLLAR
    lathe(k, [(ro - 0.0005, c0), (cr - 0.0008, c0), (cr, c0 + 0.0008), (cr, c1), (ro - 0.0005, c1)], "Root", FRM,
          segs=16, loop=True)
    f0, f1, fr = FRONT_COLLAR
    lathe(k, [(GUIDE_R, f0), (fr - 0.001, f0), (fr, f0 + 0.001), (fr, f1 - 0.0008), (fr - 0.0008, f1), (GUIDE_R, f1)],
          "Root", FRM, segs=12, loop=True)


def build_pilot(k):
    """The pilot burner under the nozzle's tip, like a spark plug along its axis (aimed up into the stream): a
    titanium shell through a metallic black lug hanging from the front collar (spot-faced square to it), a
    stainless steel hex seated on the spot face, a ceramic insulator with ribs, a stainless steel terminal, the stainless steel jet; the
    bronze gas line from the terminal's back, back and under the shield (a clip on the rear collar) and up
    into the keel."""
    P = pilot_point
    (l0, l1), (lz0, lz1), lw = PILOT_LUG
    lug = rounded([(l0, lz0), (l1, lz0), (l1, lz1), (l0, lz1)], [0.003, 0.003, 0, 0], n=2)
    k.plate([(0, y, z) for y, z in lug], 2 * lw, (1, 0, 0), "Root", MTL,
            cuts=[(P(-0.030), P(0.004), 0.0046, 8), (P(-0.035), P(-0.0170), 0.0066, 8)])
    k.cyl(P(-0.019), P(-0.004), 0.0045, "Root", FRM, segs=8)                                             # shell
    k.cyl(P(-0.0245), P(-0.0168), 0.0062, "Root", JNT, segs=6)                                           # hex
    ins = [(0.0, -0.039), (0.0030, -0.039), (0.0030, -0.0365), (0.0040, -0.0360), (0.0040, -0.0320),
           (0.0033, -0.0315), (0.0042, -0.0305), (0.0042, -0.0240), (0.0, -0.0240)]
    revolve(k, ins, P(0.0), pilot_dir(), (1, 0, 0), "Root", CER, segs=6)                                 # insulator
    k.cyl(P(-0.045), P(-0.0385), 0.0024, "Root", JNT, segs=8)                                            # terminal
    k.cyl(P(-0.0045), P(0.0), 0.0024, "Root", JNT, segs=8)                                               # jet
    r, ry = PILOT_LINE
    a, b = P(-0.045), P(-0.053)
    line = [a, b, Vector((0, ry, b.z)), Vector((0, ry, KEEL))]
    k.tube(line, r, "Root", BRZ, sides=6)
    c0, c1 = PILOT_CLIP
    cz = BORE_Z - REAR_COLLAR[2] + 0.0015
    clip = rounded([(c0, b.z - 0.004), (c1, b.z - 0.004), (c1, cz), (c0, cz)], [0.002, 0.002, 0, 0], n=1)
    k.plate([(0, y, z) for y, z in clip], 0.007, (1, 0, 0), "Root", MTL,
            cuts=[((0, c0 - 0.005, b.z), (0, c1 + 0.005, b.z), r + 0.0003, 8)])


# --------------------------------------------------------------------------------------------
# Parts: the socket block, the catch
# --------------------------------------------------------------------------------------------

def build_socket(k):
    """The socket block (metallic black) under the keel, over the cans' manifold: the neck's bore up through it (on up into the body), the valve boss's counterbore, the catch's bore across it behind
    the neck (the button's counterbore on the right) and the tooth's pocket."""
    (s0, s1), hw, top, bot = SOCKET
    outline = rounded([(hw, bot), (hw, top), (-hw, top), (-hw, bot)], [0.003, 0, 0, 0.003], n=1)
    cy, cz, cr = CATCH
    (t0, t1), (tz0, tz1), (tx0, tx1) = TOOTH
    cuts = [((0, VALVE_Y, bot - 0.001), (0, VALVE_Y, top + 0.001), NECK[0] + 0.00005, 12),
            ((0, VALVE_Y, bot - 0.001), (0, VALVE_Y, BOSS[1][1] + 0.0015), BOSS[0] + 0.0015, 12),
            ((-hw - 0.001, cy, cz), (tx1 + CATCH_TRAVEL + 0.004, cy, cz), cr + 0.0003, 8),
            ((-hw - 0.001, cy, cz), (-hw + 0.014, cy, cz), BUTTON[1] + 0.0003, 10)]
    boxes = [(((tx0 - 0.0005 + tx1 + CATCH_TRAVEL + 0.001) / 2, (t0 + t1) / 2, (tz0 + tz1) / 2),
              (tx1 + CATCH_TRAVEL + 0.0015 - tx0, t1 - t0 + 0.0006, tz1 - tz0 + 0.0006))]
    k.plate([(x, (s0 + s1) / 2, z) for x, z in outline], s1 - s0, (0, 1, 0), "Root", MTL, cuts=cuts, boxes=boxes)


def build_catch(k):
    """The can's catch (bone MagCatch): a stainless steel cross bolt through the socket block behind the neck, its black
    button on the right, its tooth in the neck's groove."""
    cy, cz, cr = CATCH
    (t0, t1), (tz0, tz1), (tx0, tx1) = TOOTH
    bx, brr = BUTTON
    k.cyl((bx + 0.001, cy, cz), (tx1 + 0.001, cy, cz), cr, CATCH_BONE, JNT, segs=6)
    k.cyl((bx, cy, cz), (bx + 0.006, cy, cz), brr, CATCH_BONE, SEC, segs=10)
    k.span((tx0, t0, tz0), (tx1, t1, tz1), CATCH_BONE, MTL)


def build_gun(k, pistons, joints):
    build_body(k)
    build_flange(k)
    build_boss(k)
    build_relief(k)
    build_side_grip(k)
    build_grip(k)
    build_head(k)
    build_trigger_housing(k)
    build_trigger(k)
    build_exhaust(k)
    build_gauge(k)
    build_pump(k)
    build_fuel_line(k)
    build_wheel(k)
    build_nozzle(k)
    build_shield(k)
    build_pilot(k)
    build_socket(k)
    build_catch(k)


# --------------------------------------------------------------------------------------------
# Parts: the ammo pack (two gas cans)
# --------------------------------------------------------------------------------------------

def can_profile():
    """(radius, local y) of a can's body: elliptic domes, poles at both ends."""
    c0, c1, dd = CAN_Y
    th = [90 * i / 5 for i in range(1, 6)]
    prof = [(0.0, c0 - dd)] + [(CAN_R * math.sin(math.radians(a)), c0 - dd * math.cos(math.radians(a))) for a in th]
    prof += [(CAN_R * math.sin(math.radians(a)), c1 + dd * math.cos(math.radians(a))) for a in reversed(th)]
    return prof + [(0.0, c1 + dd)]


def band_profile(y):
    rb, w = CAN_R + BAND_T, BANDS[1]
    return [(CAN_R - 0.002, y - w / 2), (rb, y - w / 2), (rb, y + w / 2), (CAN_R - 0.002, y + w / 2)]


def can_frame(sx):
    """A can's local frame: its axis along local y (nose at -y), pitched CAN_TILT nose-down about x, centred
    on the valve's y, lifted so its lowest point (a ring's bottom vertex) is on z = 0."""
    t = math.radians(CAN_TILT)
    pts = can_profile() + [p for y in BANDS[0] for p in band_profile(y)]
    z = -min(y * math.sin(t) - r * math.cos(t) for r, y in pts)
    return Matrix.Translation((sx * CANS_X, VALVE_Y, z)) @ Matrix.Rotation(t, 4, "X")


def build_pack(k):
    """The ammo pack (bone Mag): two gas cans side by side, pitched nose-down, brushed aluminium with matte black
    domes and raised black bands (user: dual tone), a stainless steel fitting on each front dome and the shiny bronze
    crossover pipe between them (user), a bronze relief valve (stainless steel cap) on each back; the metallic black
    manifold yoke clamped across their tops (bolted), its bronze valve boss and the stainless steel neck with the
    catch's groove standing up out of it."""
    c0, c1, dd = CAN_Y
    for sx in (1, -1):
        frame = can_frame(sx)
        inv = frame.inverted()
        with k.frame(frame):
            k.bm.faces.ensure_lookup_table()
            first = len(k.bm.faces)
            revolve(k, can_profile(), (0, 0, 0), (0, 1, 0), (1, 0, 0), MAG, ALU, segs=12)
            k.bm.faces.ensure_lookup_table()
            for f in k.bm.faces[first:]:                                                             # black domes
                y = (inv @ f.calc_center_median()).y
                if y < c0 + 1e-4 or y > c1 - 1e-4:
                    f.material_index = SLOTS.index(SEC)
            for y in BANDS[0]:
                revolve(k, band_profile(y), (0, 0, 0), (0, 1, 0), (1, 0, 0), MAG, SEC, segs=12, loop=True)
            k.cyl((0, c0 - dd + 0.0015, 0), (0, c0 - dd - 0.0030, 0), 0.0065, MAG, JNT, segs=8)          # fitting
            k.cyl((0, c1 + dd - 0.0015, 0), (0, c1 + dd + 0.0045, 0), 0.0060, MAG, BRZ, segs=6)          # relief valve
            k.cyl((0, c1 + dd + 0.0043, 0), (0, c1 + dd + 0.0070, 0), 0.0038, MAG, JNT, segs=8)
    r, run = CROSSOVER
    yf = c0 - dd - 0.0030
    with k.frame(can_frame(0)):                                                                    # crossover pipe
        pts = [(CANS_X, yf, 0), (CANS_X, yf - run + 0.008, 0), (CANS_X - 0.008, yf - run, 0),
               (-CANS_X + 0.008, yf - run, 0), (-CANS_X, yf - run + 0.008, 0), (-CANS_X, yf, 0)]
        k.tube(pts, r, MAG, BRZ, sides=6)
    (m0, m1), mw, (mz0, mz1) = MANIFOLD
    yoke = rounded([(mw, mz0), (mw, mz1), (-mw, mz1), (-mw, mz0)], [0.006, 0.004, 0.004, 0.006], n=2)
    k.plate([(x, (m0 + m1) / 2, z) for x, z in yoke], m1 - m0, (0, 1, 0), MAG, MTL, bevel=0.0012)
    for sx in (1, -1):
        bolt(k, (sx * (mw - 0.007), m0, mz1 - 0.006), (0, -1, 0), MAG, r=0.0022, head=0.0014)
    br, (bz0, bz1) = BOSS
    k.cyl((0, VALVE_Y, bz0), (0, VALVE_Y, bz1), br, MAG, BRZ, segs=6)                                  # valve boss
    nr, (n0, n1), (g0, g1), gd = NECK
    revolve(k, [(0.0, n0), (nr, n0), (nr, g0), (nr - gd, g0 + 0.0004), (nr - gd, g1 - 0.0004), (nr, g1),
                (nr, n1 - 0.001), (nr - 0.001, n1), (0.0, n1)], (0, VALVE_Y, 0), (0, 0, 1), (1, 0, 0), MAG, JNT,
            segs=12)                                                                                   # neck


# --------------------------------------------------------------------------------------------
# Checks specific to the flamethrower
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """Joint-range sweeps on top of the animation frames: the nozzle's recoil, the trigger, the louvres, the
    needle, the pump rods (against each other), the catch, the can with the catch pressed."""
    states = [(f"nozzle {RECOIL * i / 5:.4f}", {BARREL: RECOIL * i / 5}) for i in range(1, 6)]
    states += [(f"trigger {v}", {TRIGGER: v}) for v in range(0, TRIGGER_PULL + 1, 2)]
    states += [(f"louvres {a}", {LOUVRES[0]: a}) for a in range(0, VENT_OPEN + 1, 5)]
    states += [(f"needle {a}", {NEEDLE: a}) for a in range(NEEDLE_RANGE[0], NEEDLE_RANGE[1] + 1, 10)]
    states += [(f"pumps {i}", {PUMPS[0]: PUMP_STROKE * i / 6, PUMPS[1]: PUMP_STROKE * (6 - i) / 6}) for i in range(7)]
    states += [(f"catch {CATCH_TRAVEL * i / 4:.4f}", {CATCH_BONE: CATCH_TRAVEL * i / 4}) for i in range(1, 5)]
    states += [(f"can {MAG_TRAVEL * i / 10:.4f}", {CATCH_BONE: CATCH_TRAVEL, MAG: MAG_TRAVEL * i / 10}) for i in range(11)]
    return states


def check_envelope(kit):
    """Every weapon fits WEAPON_MAX (wide x long x high) at rest, its bottom on z = 0 (the item table's and the weapon holder's mount takes
    it by its bottom) and centred along its length. Returns its size."""
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
    """Tensor's palm (a box in its hand bone frame) at each socket: it sinks into no part of the gun, and its
    face lies on the grip (within 1.5 mm)."""
    problems = []
    parts = [p for p in all_parts(kit) if p.bone == "Root"]
    for side in ("Left", "Right"):
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
    """(name, bone, origin, forward, up) of every gizmo: an empty whose local +Y is `forward` and +Z `up` in
    Blender (in glTF / Godot: -Z forward, +Y up). The muzzle rides the nozzle (it pulses with it); PilotFlame is
    on the pilot's jet, looking along its axis at the stream ahead of the nozzle; FumeVent is on the exhaust,
    looking out and down as the open louvres send the fumes."""
    out = [("Muzzle", BARREL, Vector((0, TIP[1] - 0.01, BORE_Z)), Vector(FWD), Vector(UP))]
    d = pilot_dir()
    out.append(("PilotFlame", "Root", pilot_point(0.001), d, (Vector(UP) - d * d.z).normalized()))
    vent = Vector((-1, 0, -0.5)).normalized()
    out.append(("FumeVent", "Root", Vector((BEZEL_X[1], sum(LOUVRE[0]) / 2, BORE_Z)), vent,
                (Vector(UP) - vent * vent.z).normalized()))
    return out


def place_on_bone(obj, rig, bone_name, m):
    """Parent obj to a bone and give it the world matrix m (at rest)."""
    bone = rig.data.bones[bone_name]
    obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone_name
    obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()
    obj.matrix_basis = m
    return obj


def build_gizmos(rig, specs, hands=True, ammo_frame=None):
    """The exported gizmos (empties, invisible in game), each on its bone, and the two hand sockets. A hand
    socket's glTF / Godot axes are Tensor's hand bone axes (X knuckle line, Y wrist to knuckles, Z out of the
    palm) and its origin the wrist pivot: in Blender that is local X = X, -Y = Z, +Z = Y, because Blender's
    exporter converts an empty's axes (+Y to -Z, +Z to +Y) but not a bone's."""
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
    """The ammo pack (the two cans on their manifold) on its own for the pickup: an unskinned copy, tilted as it
    rides under the gun, its origin under its valve on its bottom plane."""
    mesh = ammo.data.copy()
    P = Matrix.Translation(-Vector((0, VALVE_Y, 0.0)))
    P = Matrix.Rotation(math.radians(CAN_TILT), 4, "X") @ P       # (square to its own axes: the cans level)
    low = min((P @ v.co).z for v in mesh.vertices)
    P = Matrix.Translation((0.0, 0.0, -low)) @ P                       # (its bottom on z = 0)
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




def finish_whole(obj, rig, budget):
    """Skin, unwrap and hold to the budget without the unseen-face cull: the pack's cans are closed bottles whose
    every face shows, and it fits its budget whole."""
    check_coplanar(obj)
    skin(obj, rig)
    unwrap(obj)
    tris = triangles(obj)
    print(f"[{NAME}] {obj.name}: {tris} tris (budget {budget}, not culled)")
    if tris > budget:
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
            "grips": "the side grip standing out of the left flank, thumb up" if side == "Left"
                     else "the upright grip on top (a pistol grip standing on the crown)",
            "wrist_blender": vec(wrist), "bone_x_blender": vec(x), "bone_y_blender": vec(y), "bone_z_blender": vec(z),
            "wrist_godot": godot(wrist), "bone_x_godot": godot(x), "bone_y_godot": godot(y), "bone_z_godot": godot(z),
            "grip_pose_deg": pose}
    spec = lambda n: [{"name": g, "bone": b, "position": vec(o), "forward": vec(f), "up": vec(u)}
                      for g, b, o, f, u in gizmo_specs() if g.startswith(n)]
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, the nozzle points -Y, the origin is the gun's bottom centre (the cans' "
                 "lowest point, midway along the gun). glTF/Godot: (x, z, -y), so the nozzle points +Z "
                 "(glTF's front). Hinges turn about their bone's local X (degrees), slides move along their bone's "
                 "local Y (metres).",
        "rest": "nozzle home, trigger forward, louvres shut, the gauge's needle up, pump rods home, pack in, "
                "catch out",
        "size_m": {"wide": round(size.x, 3), "long": round(size.y, 3), "high": round(size.z, 3),
                   "max_wide_long_high": list(WEAPON_MAX), "bore_axis_height": round(BORE_Z, 4),
                   "note": "a pressurised flamethrower; every weapon fits 0.25 x 0.75 x 0.35 m"},
        "materials": SLOTS,
        "triangles": {f"SK_{TITLE}": tris, f"SK_{TITLE}Ammo": ammo_tris, f"SM_{TITLE}Ammo": ammo_tris},
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "coupled": {name: f"= {LOUVRES[0]}: the three slats swing together (baked into every action)"
                    for name in LOUVRES[1:]},
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "fire": {
            "hold": f"fire_start ({START_F} frames: the trigger pulls, the louvres swing open, the gauge drops, the "
                    f"pump starts), then loop fire ({FIRE_F} frames: the pump's rods stroke in turn, the louvres "
                    f"flutter open, the nozzle pulses {RECOIL * 100:g} cm back and home once a second, "
                    f"{RECOIL_F[0]} frames back, {RECOIL_F[1]} home), and on release fire_end ({END_F} frames: "
                    "everything settles home). Emit the flame stream from Muzzle (forward = its direction) from "
                    "fire_start's frame 2 through fire; smoke from FumeVent while the louvres are open (fire_start "
                    "frame 3 to fire_end frame 10).",
            "pilot": "the pilot burns all the time the gun is held (idle, firing, reloading): a small flame at "
                     "PilotFlame, its forward pointing at the stream ahead of the nozzle; it is what lights the "
                     "stream as it leaves the nozzle.",
            "idle": f"idle ({IDLE_F} frames, loop): the gauge's needle quivers and the pump rods breathe; it starts "
                    "and ends at rest, as every action except the fire loop (from fire_start, into fire_end).",
            "recoil_m": RECOIL, "recoil_frames": list(RECOIL_F), "vent_open_deg": VENT_OPEN,
            "pump_stroke_m": PUMP_STROKE},
        "gizmos": {
            "convention": "empties: in Blender local +Y is the gizmo's forward and +Z its up; in glTF / Godot -Z is "
                          "forward and +Y up (Marker3D / Node3D under a BoneAttachment3D, so they follow the "
                          "animations)",
            "muzzle": spec("Muzzle")[0],
            "muzzle_note": "1 cm in front of the nozzle's tip, on its bone (it pulses with it): the flame stream's "
                           "and the damage's origin, forward = the stream's direction",
            "pilot_flame": spec("PilotFlame")[0],
            "pilot_flame_note": "on the pilot's jet under the nozzle's tip, forward = along the pilot's axis, up "
                                "into the stream about 5 cm ahead of the nozzle: a small, always-on flame here",
            "fume_vent": spec("FumeVent")[0],
            "fume_vent_note": "on the louvred exhaust in the right flank, forward = out and down (the open slats "
                              "turn the fumes down): smoke / heat haze while firing",
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
                 "pickup_mesh": f"SM_{TITLE}Ammo", "pickup_origin": "its bottom centre, lying as under the gun",
                 "axis": [0, 0, -1], "travel_m": MAG_TRAVEL,
                 "note": "mag_release presses the catch and drops the pack (two cans on their manifold) off its socket (its neck out of the "
                         "bore); past MAG_TRAVEL it is free: hide the pack's mesh and drop a physics copy of the "
                         "pickup mesh at the Mag bone's transform. To reload, put the pack back at the end of its "
                         "travel and play mag_insert (the catch snaps into the neck's groove)."},
        "usage": "idle (loop); fire: fire_start, fire (loop), fire_end; reload: mag_release, mag_insert.",
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
    print(f"[{NAME}] checks passed ({len(states)} motion states)")

    gun_kit, ammo_kit = Kit(), Kit()
    build_gun(gun_kit, pistons, joints)
    build_pack(ammo_kit)
    body = gun_kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    ammo = ammo_kit.to_object(f"SK_{TITLE}Ammo")
    tris = finish(body, rig, joints, TRI_BUDGET, states)
    ammo_tris = finish_whole(ammo, rig, AMMO_BUDGET)

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
