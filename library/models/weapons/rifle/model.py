"""Rifle - a designated marksman rifle for KYLR (an assault rifle with a sniper's optic), modelled,
rigged and animated from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/weapons/rifle/model.py

Produces, next to this script:
    rifle.blend             source scene (the rifle, its magazine and preview-only gizmo markers), opened by
                            preview.py and animate.py
    rifle.glb / .fbx        SK_Rifle, SK_RifleOptic and SK_RifleAmmo skinned to RIG_Rifle, with the actions
                            idle, fire_start, fire, fire_end, scope_in, idle_scoped, fire_marksman, scope_out,
                            charge, mag_release and mag_insert, and the gizmos Muzzle, ShellEject, ScopeEye,
                            Flashlight, LeftHandSocket, RightHandSocket
    rifle_ammo.glb / .fbx   SM_RifleAmmo: the magazine on its own, upright, origin at its bottom centre, for the
                            in-game ammo pickup
    rifle_rig.json          joints, animations, gizmos, hand sockets, magazine

Design: the body is one shell lofted along the bore from the nose to the stock, its top one straight line:
a stepped section (the upper band set in over the lower band, the step running straight down both flanks),
faceted shoulders to a flat top, true-arc lower edges. It is slim at the front (the handguard round the
barrel) and widens and deepens in one faceted ramp into the receiver. It is military beige ahead of a
slanted split just behind the magwell and matte black behind it (user). The handguard is cut half open at
the front (a long slanted cut through both upper flanks onto the barrel and its bronze heat-sink collars)
with a row of slanted vents behind it; the machined walls are dark, the receiver's access panels recessed.
A floodlight hangs under the nose on a hinged clevis mount, tilting on its stainless steel pin. The action is short recoil: the barrel
(machined in steps out of the nose, a slotted, ported flash hider on its end) recoils 1 cm locked to the bronze bolt carrier, which runs on
in its raceway on two stainless steel guide rods; the case leaves through the ejection port in the right flank,
whose hinged dust cover drops open while firing and closes after. A non-reciprocating charging handle
rides a slot in the left flank and pulls the carrier back by its lug. A wide quad-stack magazine (its
rounds seen through slots in both flanks) drops out of a flared, raked beige magwell when the cross-bolt
catch is pressed. Behind the magwell hang the trigger housing (an open guard, the small curved trigger)
and the raked pistol grip; the fire selector (auto / marksman) turns on the left flank over the grip,
the ammo display stands raised on the left flank ahead of the charging slot (the side's one light). A
black rail along the whole top carries the matte black optic (its own mesh) in two clamp mounts that
slide along it, to set it farther or closer, or off its front end to take it off; faceted like the shell
(octagonal sections): an elevation turret on top and windage on the right, a laser rangefinder over its
nose, and an objective sleeve that a steel-rodded actuator slides out of the objective housing to zoom
for the marksman mode
(the ScopeEye gizmo is the sniper's eye point behind the eyepiece). The stock rides two stainless steel rods out
of the shell's rear face: a black lofted buttstock, an beige cheek riser on two stainless steel posts over its
faceted comb, a skeleton opening through it (beige walls), a metallic black buttpad exactly its back face.
Finish: military beige ahead, matte black behind, metallic black details (user), a titanium barrel and
brake, stainless steel and bronze.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a joint axis misses
its rotor or bearing, a slide leaves its guide, a palm would sink into a grip, the gun leaves its size
envelope, or anything collides through any animation frame or across the joints' ranges. Conventions:
1 unit = 1 m, Z up, the muzzle points -Y (forward), the origin is on the gun's bottom plane (the
magazine's and the grip's bottom) midway along it, so the item table's and the weapon holder's WeaponMount takes it by its
bottom. Rest pose: bolt and barrel home, dust cover shut, charging handle forward, trigger forward,
selector on auto, the optic at its place on the rail, its sleeve in, the lamp level, magazine in, catch out.
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

NAME = "rifle"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # Rifle

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000       # the rifle (SK_Rifle)
AMMO_BUDGET = 1_500      # the magazine (SK_RifleAmmo / SM_RifleAmmo), on its own budget
OPTIC_BUDGET = 1_500     # the detachable optic (SK_RifleOptic)
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN, LEFT = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored)

# Size: every weapon fits a 0.25 (wide) x 0.75 (long) x 0.35 m (high) envelope, its bottom on z = 0,
# centred along its length (check_envelope). +x is the gun's left (the muzzle points -y).
WEAPON_MAX = (0.25, 0.75, 0.35)

BORE_Z = 0.212                         # the bore axis

# The shell: one loft along the bore (shell_ring) from its nose face to its rear face. Its section: a
# flat bottom, the lower edges true arcs (LOW_R; the support palm's seat), flat lower flanks up to the
# step, the upper band set in STEP[1] over a 45-degree step, faceted shoulders (SHOULDER, 45 deg) to a
# flat top on TOP_Z all along. Slim at the front (W_F, bottom ZB_F) to FRONT_END, it widens and deepens
# in one straight ramp to the receiver's section (W_R, belly ZB_R) at REC_START. Military beige ahead of
# the slanted split (COLOUR_SPLIT: from its foot on the belly up to the top, leaning forward), matte black
# behind it (user); the nose edges chamfered EDGE.
SHELL_Y = (-0.265, 0.175)              # nose face, rear face (the stock's rods; the receiver ends close behind the
                                       # grip, as a real rifle's, so the stock is its proper length: user)
FRONT_END, REC_START = -0.075, -0.045
W_F, W_R = 0.0270, 0.0335              # the lower band's half-width: the front, the receiver
ZB_F, ZB_R = 0.168, 0.159              # the bottom: the front, the receiver (its belly)
TOP_Z = 0.246
STEP = (0.197, 0.0025)                 # the step: its height, how far the upper band is set in
SHOULDER = 0.011
LOW_R = 0.013
ARC = (0, 20, 55, 90)                  # the lower edges' arc points (deg from straight down; the palm on 20)
EDGE = 0.005
BELLY = ZB_R
COLOUR_SPLIT = ((0.075, BELLY), (0.034, TOP_Z))  # the split line's foot and top (y, z)
# Its machining: the barrel's bore through the nose and the channel round the barrel behind it, the
# raceway the bolt carrier runs in, the magazine's opening, the ejection port (right) and the charging
# slot (left) into the raceway, the half cut and the slanted vents through both upper flanks of the
# handguard, seam grooves where the front ends, recessed access panels on the receiver.
CHANNEL = (-0.251, 0.0200)             # the barrel's channel: its front (y), radius (it runs back into the raceway)
RACEWAY = ((-0.0695, 0.160), 0.0155, (0.1925, 0.2315))  # the bolt carrier's raceway: y, half-width, z
PORT = ((-0.034, 0.012), (0.2025, 0.2275))  # the ejection port through the right upper flank: y, z
HALF_CUT = ((-0.252, -0.192), (0.2025, 0.2275), 0.010)  # the long cut through both upper flanks at the front onto
                                       # the barrel: y (its front, rear at its foot), z, how far its ends lean back
SLANT_VENTS = ((-0.178, -0.160, -0.142, -0.124, -0.106), 0.0025, (0.2025, 0.2275), 0.010)  # behind it: y at the
                                       # foot, half-width, z, lean back (parallel to the cut's ends)
SEAM_Y = -0.082
PANELS = (((0.074, 0.112), (0.1735, 0.1935)), ((0.100, 0.152), (0.2040, 0.2310)))  # the access panels, both flanks:
                                       # on the lower band over the trigger, on the upper band behind the port / slot: y, z
DISPLAY = ((-0.040, -0.008), (0.2045, 0.2315), 15)  # the ammo display on the left upper flank: y, z, tilt up (deg)
RAIL = ((-0.245, 0.150), 0.0105, 0.0065, (-0.236, 0.028, 14))  # the rail along the whole top: y, half-width, height,
                                       # slots (first y, pitch, n)

# The barrel (bone Barrel): short recoil, RECOIL back locked to the bolt carrier's face, then home with
# it. Its chamber block (the barrel extension) slides in the raceway's front, its tube in the nose's bore
# (a sliding fit) and the barrel nut; bronze heat-sink collars in the channel behind the half cut; its ported,
# stepped length out of the nose on its front.
BARREL_R, BARREL_BORE = 0.0095, 0.0056
GUIDE_R = BARREL_R + 0.00005
CHAMBER = ((-0.068, -0.050), 0.0140)   # the barrel extension: y, half-size (square, chamfered)
RECOIL = 0.010                         # 1 cm back (user rule), locked to the bolt
COLLARS = ((-0.242, -0.226, -0.210), 0.0165, 0.005)  # the heat-sink collars, in the half cut: y, radius, thickness
# The barrel's exposed length is machined in steps (user: multi-level cuts and punctures, as a real one): a
# jacket with ring grooves (starting a centimetre ahead of the nut, so it clears it recoiling), the bare
# neck, a lock collar, and the flash hider: four tines slotted back from its face, two rows of side ports
# and a compensator port on top. It is as long as the 0.75 m envelope allows (user).
JACKET = ((-0.305, -0.2795), 0.0112, (-0.2875, -0.2955), 0.0020, 0.0012)  # y, radius, its grooves (y, width, depth)
MUZZLE_COLLAR = ((-0.3255, -0.3180), 0.0125)  # y, radius
BRAKE = (-0.3779, -0.3255, 0.0118)     # the flash hider: its face, its rear, radius
HIDER_SLOTS = (0.020, 0.0026)          # its tines' slots back from the face: length, width
HIDER_PORTS = ((-0.3345, -0.3425), 0.0024)  # its side ports (y), radius
NUT = (-0.2685, SHELL_Y[0] + 0.0015, 0.0145)  # the barrel nut on the nose face: front, rear (sunk), radius

# The bolt carrier (bone Bolt, bronze): in the raceway, its front the bolt face on the barrel's chamber,
# running back BOLT_TRAVEL on two stainless steel guide rods fixed in the raceway's rear wall and running forward
# into bores in the carrier; a lug on its left flank in the charging slot.
BOLT_Y = (CHAMBER[0][1], 0.070)
BOLT_W, BOLT_Z = 0.0145, (0.1935, 0.2305)
BOLT_TRAVEL = 0.060                    # the case (y -0.040..0.010 when fully back) clears the port
BOLT_RODS = (0.0075, 0.2215, 0.0025, (0.018, RACEWAY[0][1] + 0.008))  # the guide rods: x, z, radius, y
ROD_BORE = (0.0030, -0.045)            # their bores in the carrier: radius, bottom (y)
LUG = ((0.022, 0.030), (0.2185, 0.2255))  # the carrier's charging lug on its left flank: y, z (x to SLOT's inside)
# The charging handle (bone Charger): a slider in the left flank's slot, ahead of the carrier's lug, its
# T-knob out on the flank; pulled back it pushes the carrier back by the lug (the carrier never drags it).
SLOT = ((0.004, 0.092), (0.2175, 0.2265))  # the charging slot through the left upper flank: y, z
CHARGER = ((0.0045, 0.0215), (0.2180, 0.2260))  # its slider in the slot at rest: y, z
KNOB = (0.0460, 0.0055)                # its knob out to x, radius
# The dust cover (bone EjectCover): a plate over the port hinged on a pin along the step under it; it
# drops open COVER_OPEN (a solenoid releases it, a torsion spring round its pin closes it).
COVER = ((-0.0375, 0.0155), (0.2005, 0.2300), 0.0015)  # y, z (hinge edge, top), thickness
COVER_PIN = (-0.0333, 0.2000, 0.0011)  # the pin: x, z, radius (along y)
COVER_OPEN = 100

# The magazine (bone Mag): a wide box (a quad stack; its outer columns' rounds show through three
# slots in each flank), its base plate on z = 0, its body up the magwell, its feed tower up the shell's
# opening with the top round in its lips under the carrier. It drops MAG_TRAVEL along the magwell before
# it is free.
MAG_Y = (-0.035, 0.040)
MAG_W, MAG_R = 0.027, 0.006            # half-width, vertical corners' radius
MAG_TOP = 0.155                        # its body's top (the tower above)
BASE = (0.011, 0.0015)                 # the base plate: height, how far it stands out
MAG_SLOTS = ((-0.0185, 0.0025, 0.0235), 0.003, (0.030, 0.140))  # the slots onto the rounds: y, half-width, z
TOWER = ((-0.030, 0.035), 0.0125, 0.1885)  # the feed tower: y, half-width, its top
ROUND = (0.0058, 0.063, 0.045)         # a round: radius, length, its case's length
ROUND_ROWS = (0.024, 0.0122, 10)       # the outer columns' rounds: first z, pitch, count per column
TOP_ROUND_Z = BOLT_Z[0] - 0.0012 - ROUND[0]  # the top round's axis, in the feed lips under the carrier
MAG_TRAVEL = 0.030
MAGWELL = (0.108, BELLY + 0.007, 0.0035, 0.012, 0.0025, 0.008)  # the magwell collar: mouth z, top (sunk into the belly),
                                       # side walls, rear wall, the mouth's flare, its front face's rake (forward at the mouth)
# The catch (bone MagCatch): a cross bolt through the magwell's rear wall; its button on the right,
# its tooth at its left end in a notch in the magazine's rear left corner; pushed in (+x, toward the
# gun's left) the tooth leaves the notch.
CATCH = (MAG_Y[1] + 0.0075, 0.140, 0.0020)  # the bolt's axis: y, z; radius
TOOTH = ((MAG_Y[1] - 0.004, MAG_Y[1] + 0.0065), (0.137, 0.143), (MAG_W - 0.0035, MAG_W + 0.0005))  # y, z, x at rest
BUTTON = (-(MAG_W + MAGWELL[2]) - 0.0065, 0.0038)  # its button's outer face (x), radius
CATCH_TRAVEL = 0.0045

# Hands: Tensor's hand bone frame (X = knuckle line, Y = wrist to knuckles, Z = out of the palm),
# its palm 0.094 long from 1 cm past the wrist, 0.09 wide, its face 0.016 off the bone line.
PALM = (0.010, 0.104, 0.045, 0.016)    # palm along Y (from, to), half-width along X, half-thickness
GRIP_ALONG = {"Left": 0.072, "Right": 0.070}  # the grip line from the wrist along Y
GRIP_RAKE = 15                         # the pistol grip's rake (deg)
GRIP_G = (0.0, 0.1464, 0.0865)         # the firing hand's centre on the pistol grip's axis
GRIP_HALF = (0.014, 0.023)             # pistol grip half-width (x) and half-depth (fore-aft)
WEB = (0.012, 0.030, 0.040, 0.062)     # the web relief: the backstrap cut to this depth (local y) from z 0.030
                                       # (full by 0.040) up the grip from the hand's centre
# The trigger: the pistol's small curved lever (user rule: every gun's), placed as on the pistol from the
# grip's hand centre; its block under the belly, the open guard round it (behind the magwell, its bottom
# bar stopping short of the curled fingers).
TRIGGER_PIVOT = (0.0, GRIP_G[1] - 0.0595, GRIP_G[2] + 0.0515)
TRIGGER_OUTLINE = [(-0.0040, -0.0025), (0.0015, -0.0180), (0.0048, -0.0290), (0.0060, -0.0370), (0.0048, -0.0418),
                   (0.0080, -0.0428), (0.0105, -0.0360), (0.0080, -0.0180), (0.0035, -0.0025)]
# (the lever's face concave, leaning forward from the pivot, curving back under the index finger, its tip
# turned forward: user, the old lever's convex face and back-hooked tip looked the wrong way round)
TRIGGER_PULL = 12
GUARD_FRONT = (MAG_Y[1] + MAGWELL[3] + 0.003, MAG_Y[1] + MAGWELL[3] + 0.011)  # the guard's front bar (y)
GUARD_BOTTOM = (GRIP_G[2] - 0.005, 0.007, GRIP_G[1] - 0.060)  # its bottom bar: underside, thickness, rear end
TRIGGER_BLOCK = ((GUARD_FRONT[1], 0.104), TRIGGER_PIVOT[2] - 0.0075)  # the trigger's block: y, its bottom
TRIGGER_HALF = 0.0095                  # the trigger housing's half-width
# The fire selector (bone Selector) on the left flank over the grip: forward on auto, turned up to
# SEL_SEMI for the marksman mode.
SEL_PIVOT = (W_R, 0.122, 0.1795)
SEL_SEMI = 60
# The support hand holds the magwell (user: every long gun takes the rocket launcher's hold, the rifle's support grip
# moved back to its spacing; the handguard's palm seat ran into the magwell, so a magwell grip, as real shooters use):
# the palm flat on the magwell's left, flush with the receiver's flank over it (3 mm out from the magwell's face), the
# fingers forward round the magwell's front, tilted LSUP_TILT down, the thumb up along the belly.
LSUP_Z, LSUP_TILT, LSUP_INSET = 0.145, 8, 0.004   # the palm's centre height, the fingers' tilt down (deg), the grip line
                                                # behind the magwell's front face
GRIP_POSE = {"Left": ({"Index": 45, "Middle": 50, "Ring": 52, "Little": 48}, (20, 30, 20)),
             "Right": ({"Index": 36, "Middle": 65, "Ring": 65, "Little": 52}, (42, -25, 50))}
# The support hand's grip on the ammo pack for a reload (user: every hand placement is a socket the animation plugs
# into, exported as AmmoHandSocket on the Mag bone; a wide grip, not a C cup): the palm flat on the pack's outer end
# (the face away from the gun), the fingers spread across it and over its far (right) edge, the thumb up its front;
# centred along the pack.
AMMO_ACROSS = (-1.0, 0.0, 0.0)   # the fingers' way across the pack (the left hand reaches over to its right edge)
AMMO_OUT = (0.0, 0.0, -1.0)   # its outer end (the way it leaves the gun)
AMMO_GRIP = 0.004                # the knuckles short of the pack's far edge (the fingers wrap over it)
AMMO_GRIP_POSE = ({"Index": 45, "Middle": 50, "Ring": 50, "Little": 45}, (25, 40, 15))  # spread, the thumb out

# The stock: two stainless steel rods out of the shell's rear face carry the black lofted buttstock (stock_section):
# a flat faceted comb under an adjustable beige cheek riser, a skeleton opening through its flanks (user:
# open in the centre, as the lightning gun's), its bottom sloping straight down to the toe; the metallic
# black buttpad is exactly its back face.
# The rifle is 10 cm shorter behind the grip than it was (user: shorten the stock): its butt on Tensor's chest as he
# shoulders it, his firing wrist only 14 cm ahead of his shoulder joint so the handguard stays in his other hand's
# reach; the receiver was shortened with it so the stock keeps a real rifle's proportions (user).
STOCK_Y = (0.179, 0.257, 0.271)        # its front face, its back face (the buttpad's front), the buttpad's back
STOCK_W, COMB_Z, COMB_F = 0.022, 0.236, 0.006
STOCK_BOTTOM = (0.172, 0.112)          # its bottom at its front and back faces (the toe clear of the firing forearm)
STOCK_RODS = (0.012, BORE_Z, 0.0040, (SHELL_Y[1] - 0.012, STOCK_Y[0] + 0.012))  # x, z, radius, y
STOCK_HOLE = ((0.194, 0.243), (0.013, 0.013))  # the opening through it: y (front, back edges), its top's and
                                       # bottom's inset from the comb and the underside
RISER = ((0.193, 0.246), 0.0175, (COMB_Z + 0.007, COMB_Z + 0.013), (0.204, 0.235), 0.003)  # the cheek riser over the
                                       # comb on two stainless steel posts: y, half-width, z, the posts' y, their radius

# The optic (bone Optic, its own mesh SK_RifleOptic): two clamp mounts sliding along the rail (OPTIC_TRAVEL:
# back, and forward to the rail's front end, past which it comes off), faceted like the shell, every section
# an octagon with flats up, down and to the sides: a matte black body along SCOPE_Z (not the body's colour,
# user), the metallic black objective housing flaring from its front, the sleeve (bone Zoom, on the optic) sliding out of the housing's octagonal bore ZOOM_TRAVEL for
# the marksman mode, pushed by an actuator (black barrel on a bracket on the body's left, stainless steel rod to the sleeve's
# ear); the eyepiece behind; the elevation turret on top, the windage turret on the right, the laser
# rangefinder over the nose. The ScopeEye gizmo is EYE_RELIEF behind the eyepiece.
SCOPE_Z = 0.2855
BODY = ((-0.055, 0.072), 0.0175)       # the body: y, across-flats half
BELL = ((-0.092, -0.062), 0.0245, 0.0215)  # the objective housing: y (front, its bore's floor), across flats (half),
                                       # its octagonal bore's
SLEEVE = ((-0.098, -0.066), 0.02145, 0.0185)  # the sleeve at rest: y, outer and inner across flats (half)
ZOOM_TRAVEL = 0.016
ZOOM_ACT = ((0.030, SCOPE_Z - 0.0065), (-0.072, -0.030), 0.0035, 0.0018)  # the actuator: x, z; barrel y; radii
EYEPIECE = ((0.070, 0.110), 0.0190)    # y, the eyecup's across flats (half)
EYE_RELIEF = 0.075
MOUNTS = (-0.040, 0.052)               # the clamp mounts on the rail (y centres), 14 mm long
OPTIC_TRAVEL = (-0.040, 0.170)         # the optic along the rail from its place: back, forward (the front mount at the
                                       # rail's front end: past it the optic is off)
TURRET = (0.006, 0.0085, 0.0145)       # the turrets: y, radius, height out of the body
RANGEFINDER = ((-0.054, -0.030), 0.0070, 0.0085)  # over the nose: y, half-width, height

# The lamp (bone Lamp): a floodlight hanging under the nose, ahead of the support hand, on a clevis mount
# (its cheeks sunk into the shell's bottom, a stainless steel pin across them); its hub on the pin, an arm down to the
# clamp ring round its body; + tilts its beam down. Matte black body, titanium grip rings, a metallic black
# head, a stainless steel bezel round the lit lens; the Flashlight gizmo on the lens.
LAMP_MOUNT = ((-0.262, -0.248), 0.0105, 0.1390)  # the clevis: y, half-width, its cheeks' bottom (z)
LAMP_PIVOT = (0.0, -0.255, 0.1445)
LAMP = ((-0.2625, -0.2935, -0.3075), 0.0125, 0.0165, 0.118)  # its tail, the head's rear, its face (y; half its first
                                       # length, user); body and head
                                       # radius; its axis (z)
LAMP_TILT = 20

# Actions (30 fps). Auto: fire_start pulls the trigger and drops the dust cover open, fire (looped) is four
# shots at 600 rounds a minute (the bolt cycles every CYCLE frames, the barrel back with it), fire_end lets
# the trigger go and closes the cover. Marksman: scope_in turns the selector and runs the sleeve out,
# idle_scoped holds it, fire_marksman is one shot with the cover opening and closing round it, scope_out
# turns back. charge pulls the carrier back on the charging handle; mag_release / mag_insert swap the
# magazine. Nothing moves at rest, so idle (and idle_scoped) hold the pose, a loop for the game to sit in.
IDLE_F = 30
CYCLE, FIRE_F = 3, 12                  # a shot every 3 frames (600 rpm), four per loop
START_F, END_F = 4, 10
MARKS_F, MARKS_SHOT = 20, 3            # fire_marksman: its length, the shot's frame
SCOPE_F = 10
ACT_F = 15

BARREL, BOLT, CHARGE, COVER_BONE = "Barrel", "Bolt", "Charger", "EjectCover"
TRIGGER, SELECTOR, ZOOM, MAG, CATCH_BONE = "Trigger", "Selector", "Zoom", "Mag", "MagCatch"
OPTIC, LAMP_BONE = "Optic", "Lamp"

# slot: (base colour, metallic, roughness, emission strength[, alpha])
MATERIALS = {
    "M_Primary": ((0.578, 0.468, 0.262), 0.2, 0.6, 0.0),     # military beige: the shell ahead of the split, the
                                                             # magwell, the stock opening's walls and riser
    "M_Secondary": ((0.018, 0.018, 0.02), 0.2, 0.72, 0.0),   # matte black: the shell behind the split, grip, trigger
                                                             # housing, stock, magazine, rail, cover, optic, lamp
    "M_Frame": ((0.29, 0.29, 0.30), 1.0, 0.5, 0.0),          # matte titanium: the barrel, its collars, flash hider
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),         # stainless steel: pins, rods, screws, knob, bullets
    "M_Emissive": ((0.30, 0.85, 1.0), 0.0, 0.4, 6.0),        # the ammo display's screen, the lamp's lens
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.25, 0.0),         # the bolt carrier, the heat-sink collars, the cases
    "M_Glass": ((0.35, 0.55, 0.85), 0.0, 0.03, 0.0, 0.3),    # the optic's lenses, the display's cover
    "M_Metal": ((0.035, 0.036, 0.04), 1.0, 0.32, 0.0),       # metallic black: the machined walls, objective housing,
                                                             # buttpad, mounts, lamp head, trigger, controls
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, GLS, MTL = SLOTS


def radial(az):
    return Vector((math.cos(math.radians(az)), 0.0, math.sin(math.radians(az))))


def tangent(az):
    return Vector((-math.sin(math.radians(az)), 0.0, math.cos(math.radians(az))))


def shell_dims(y):
    """The shell's lower band half-width and bottom at y (slim front, a straight ramp, the receiver)."""
    if y <= FRONT_END:
        return W_F, ZB_F
    if y >= REC_START:
        return W_R, ZB_R
    u = (y - FRONT_END) / (REC_START - FRONT_END)
    return W_F + (W_R - W_F) * u, ZB_F + (ZB_R - ZB_F) * u


def grip_axes():
    """The pistol grip's frame: g up its axis (raked back at the bottom), f forward square to it."""
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))
    return Vector((0, -s, c)), Vector((0, -c, -s))


def hand_frame(side):
    """Tensor's hand bone frame gripping each handle: (wrist pivot, X, Y, Z). Z points out of the
    palm onto the grip, Y from the wrist to the knuckles, X = Y x Z along the knuckle line (the left
    thumb on -X, the right on +X). The grip line runs across the palm GRIP_ALONG from the wrist, the
    grip's surface on the palm's face."""
    if side == "Left":   # support hand: palm on the magwell's left, the fingers round its front
        t = math.radians(LSUP_TILT)
        z = Vector((-1.0, 0.0, 0.0))
        y = Vector((0.0, -math.cos(t), -math.sin(t)))
        front = MAG_Y[0] - MAGWELL[2] - MAGWELL[5] / 2                   # the magwell's front face at mid-height
        grip, face = Vector((W_R + 0.0003, front + LSUP_INSET, LSUP_Z)), 0.0
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


def auto_bolt(n):
    """The bolt carrier firing on auto: a shot every CYCLE frames (on frames 0, 3, ...), fully back the
    next frame (the case out), half home the frame after, home for the next shot."""
    phase = (0.0, BOLT_TRAVEL, 0.42 * BOLT_TRAVEL)
    return [(f, phase[f % CYCLE] if f < n else 0.0) for f in range(n + 1)]


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), world space. The bolt carrier and the
# barrel recoil back (the barrel derived from the carrier, expand()), the charging handle pulls back, the
# dust cover drops open, the trigger pulls back, the selector turns up to marksman, the optic slides along
# the rail (forward +) and its sleeve runs forward, the lamp tilts down, the magazine drops, the catch is
# pushed in.
JOINT_SPECS = [
    ("Root", None, "fixed", (0, 0, 0), UP, UP, None),
    (BOLT, "Root", "slide", (0, BOLT_Y[0], BORE_Z), BACK, None, (0, BOLT_TRAVEL)),
    (BARREL, "Root", "slide", (0, CHAMBER[0][0], BORE_Z), BACK, None, (0, RECOIL)),
    (CHARGE, "Root", "slide", (RACEWAY[1] + 0.008, CHARGER[0][0], sum(CHARGER[1]) / 2), BACK, None, (0, BOLT_TRAVEL)),
    (COVER_BONE, "Root", "hinge", (COVER_PIN[0], sum(COVER[0]) / 2, COVER_PIN[1]), FWD, UP, (0, COVER_OPEN)),
    (TRIGGER, "Root", "hinge", TRIGGER_PIVOT, (1, 0, 0), DOWN, (0, TRIGGER_PULL)),
    (SELECTOR, "Root", "hinge", SEL_PIVOT, (-1, 0, 0), FWD, (0, SEL_SEMI)),
    (OPTIC, "Root", "slide", (0, MOUNTS[0], TOP_Z + RAIL[2]), FWD, None, OPTIC_TRAVEL),
    (ZOOM, OPTIC, "slide", (0, SLEEVE[0][1], SCOPE_Z), FWD, None, (0, ZOOM_TRAVEL)),
    (LAMP_BONE, "Root", "hinge", LAMP_PIVOT, (1, 0, 0), DOWN, (0, LAMP_TILT)),
    (MAG, "Root", "slide", (0, sum(MAG_Y) / 2, 0.0), DOWN, None, (0, MAG_TRAVEL)),
    (CATCH_BONE, "Root", "slide", (0, CATCH[0], CATCH[1]), LEFT, None, (0, CATCH_TRAVEL)),
]
PISTON_SPECS = []

_N = ACT_F
ANIMATIONS = {
    "idle": (True, "LINEAR", {TRIGGER: hold_keys(0.0, IDLE_F), COVER_BONE: hold_keys(0.0, IDLE_F)}),
    "fire_start": (False, "LINEAR", {
        TRIGGER: eased([(0, 0), (2, TRIGGER_PULL), (START_F, TRIGGER_PULL)]),
        COVER_BONE: eased([(0, 0), (3, COVER_OPEN), (START_F, COVER_OPEN)])}),
    "fire": (True, "LINEAR", {
        TRIGGER: hold_keys(TRIGGER_PULL, FIRE_F), COVER_BONE: hold_keys(COVER_OPEN, FIRE_F), BOLT: auto_bolt(FIRE_F)}),
    "fire_end": (False, "LINEAR", {
        TRIGGER: eased([(0, TRIGGER_PULL), (3, 0), (END_F, 0)]),
        COVER_BONE: eased([(0, COVER_OPEN), (3, COVER_OPEN), (9, 0), (END_F, 0)])}),
    "scope_in": (False, "LINEAR", {
        SELECTOR: eased([(0, 0), (4, SEL_SEMI), (SCOPE_F, SEL_SEMI)]),
        ZOOM: eased([(0, 0), (3, 0), (SCOPE_F, ZOOM_TRAVEL)])}),
    "idle_scoped": (True, "LINEAR", {SELECTOR: hold_keys(SEL_SEMI, IDLE_F), ZOOM: hold_keys(ZOOM_TRAVEL, IDLE_F)}),
    "fire_marksman": (False, "LINEAR", {
        SELECTOR: hold_keys(SEL_SEMI, MARKS_F), ZOOM: hold_keys(ZOOM_TRAVEL, MARKS_F),
        TRIGGER: eased([(0, 0), (2, TRIGGER_PULL), (8, TRIGGER_PULL), (12, 0), (MARKS_F, 0)]),
        COVER_BONE: eased([(0, 0), (2, COVER_OPEN), (12, COVER_OPEN), (17, 0), (MARKS_F, 0)]),
        BOLT: shaped([(0, 0, "io"), (MARKS_SHOT, 0, "io"), (MARKS_SHOT + 2, BOLT_TRAVEL, "out"),
                      (MARKS_SHOT + 3, BOLT_TRAVEL, "io"), (MARKS_SHOT + 7, 0, "io")], MARKS_F)}),
    "scope_out": (False, "LINEAR", {
        ZOOM: eased([(0, ZOOM_TRAVEL), (7, 0), (SCOPE_F, 0)]),
        SELECTOR: eased([(0, SEL_SEMI), (6, SEL_SEMI), (SCOPE_F, 0)])}),
    "charge": (False, "LINEAR", {
        CHARGE: shaped([(0, 0, "io"), (6, BOLT_TRAVEL, "io"), (9, BOLT_TRAVEL, "io"), (12, 0, "in")], 18)}),
    "mag_release": (False, "LINEAR", {
        CATCH_BONE: eased([(0, 0), (3, CATCH_TRAVEL), (_N, CATCH_TRAVEL)]),
        MAG: shaped([(0, 0, "io"), (3, 0, "io"), (10, MAG_TRAVEL, "in")], _N)}),
    "mag_insert": (False, "LINEAR", {
        MAG: shaped([(0, MAG_TRAVEL, "io"), (8, 0, "io")], _N),
        CATCH_BONE: eased([(0, CATCH_TRAVEL), (8, CATCH_TRAVEL), (11, 0), (_N, 0)])}),
}
PREVIEW_STATES = {
    "fire": {BOLT: BOLT_TRAVEL, COVER_BONE: COVER_OPEN, TRIGGER: TRIGGER_PULL},
    "scoped": {SELECTOR: SEL_SEMI, ZOOM: ZOOM_TRAVEL, CHARGE: BOLT_TRAVEL},
    "mag_out": {MAG: MAG_TRAVEL, CATCH_BONE: CATCH_TRAVEL},
    "optic_forward": {OPTIC: 0.12, LAMP_BONE: LAMP_TILT},
}
PREVIEW_VIEWS = {"fire": ["front_left", "right"], "scoped": ["front_left", "left"], "mag_out": ["front_left", "right"],
                 "optic_forward": ["front_left", "left"]}
FK_TEST_STATE = {BOLT: 0.03, CHARGE: 0.01, COVER_BONE: 40, TRIGGER: 5, SELECTOR: 30, OPTIC: 0.05, ZOOM: 0.008,
                 LAMP_BONE: 10, MAG: 0.01, CATCH_BONE: 0.002}
SHOWCASE = ["idle", "fire_start", "fire", "fire", "fire", "fire", "fire_end", "idle", "scope_in", "idle_scoped",
            "fire_marksman", "idle_scoped", "fire_marksman", "scope_out", "mag_release", "mag_insert", "charge", "idle"]
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
# The rifle's coupled joints: the barrel rides the bolt carrier (short recoil), the charging handle
# pushes the carrier
# --------------------------------------------------------------------------------------------

def expand(state):
    """A joint state (or animation keys) with the coupled joints derived: the bolt carrier is at least as
    far back as the charging handle pushes it (the handle never follows the carrier); the barrel rides
    the carrier's first RECOIL as it fires (locked to its face), not when the carrier is pulled back by
    hand. Animation keys are on every frame, the carrier's and the handle's on the same frames."""
    out = dict(state)
    if any(isinstance(v, list) for v in out.values()):
        if BOLT in out or CHARGE in out:
            bolt, ch = dict(out.get(BOLT, [])), dict(out.get(CHARGE, []))
            frames = sorted(set(bolt) | set(ch))
            if BOLT in out:
                out[BARREL] = [(f, min(bolt.get(f, 0.0), RECOIL)) for f in frames]
            out[BOLT] = [(f, max(bolt.get(f, 0.0), ch.get(f, 0.0))) for f in frames]
        return out
    b = out.get(BOLT, 0.0)
    out[BARREL] = min(b, RECOIL)
    out[BOLT] = max(b, out.get(CHARGE, 0.0))
    return out


# --------------------------------------------------------------------------------------------
# Sections and helpers
# --------------------------------------------------------------------------------------------

def shell_section(w, zb, zt):
    """(x, z) of the shell's section, from the bottom's left end up the left flank, across the top and
    down the right flank: the lower edges' arcs (a vertex at every ARC angle), the lower band, the
    45-degree step, the upper band set in, the faceted shoulder, the flat top."""
    st_z, st = STEP
    r = LOW_R
    half = [(w - r + r * math.sin(math.radians(a)), zb + r - r * math.cos(math.radians(a))) for a in ARC]
    half += [(w, st_z), (w - st, st_z + st), (w - st, zt - SHOULDER), (w - st - SHOULDER, zt)]
    return half + [(-x, z) for x, z in reversed(half)]


def shell_ring(y):
    """The shell's section at y, its nose and rear edges chamfered."""
    s = max(0.0, EDGE - (y - SHELL_Y[0]), 0.002 - (SHELL_Y[1] - y))
    w, zb = shell_dims(y)
    return [Vector((x, y, z)) for x, z in shell_section(w - s, zb + s, TOP_Z - s)]


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


def split_y(z):
    """The colour split's y at height z (a straight line, leaning forward toward the top)."""
    (y0, z0), (y1, z1) = COLOUR_SPLIT
    return y0 + (z - z0) * (y1 - y0) / (z1 - z0)


def split_region(ahead):
    """The (x = 0) side outline of the half-space ahead of (or behind) the split, as an `intersect` profile."""
    far = 1.0
    ya, yb = split_y(-far), split_y(far)
    pts = [(-far, -far), (ya, -far), (yb, far), (-far, far)] if ahead else [(ya, -far), (far, -far), (far, far), (yb, far)]
    return [(0.0, y, z) for y, z in pts], (1, 0, 0), 2 * far


def shell_mat(skin):
    """A face colour for one piece of the shell: `skin` on its outer surface, metallic black on the walls the
    machining cut (round the recesses, the half cut, the vents, the port and the slots), the recesses'
    floors the skin's colour."""
    def mat(f):
        c = f.calc_center_median()
        f.normal_update()
        cap = abs(f.normal.y) > 0.99 and min(abs(c.y - SHELL_Y[0]), abs(c.y - SHELL_Y[1])) < 1e-5
        if not cap and abs(f.normal.x) < 0.99 and machined((c.x, c.z), [(q.x, q.z) for q in shell_ring(c.y)]):
            return MTL
        return skin
    return mat


def rounded_rect(hx, y0, y1, r, n=2):
    """(x, y) of a rounded rectangle (vertical corners)."""
    return rounded([(hx, y0), (hx, y1), (-hx, y1), (-hx, y0)], [r] * 4, n=n)


def vslot(y, hw, z0, z1, n=2):
    """(y, z) of an upright slot with round ends."""
    return rounded([(y - hw, z0), (y + hw, z0), (y + hw, z1), (y - hw, z1)], [hw - 0.0001] * 4, n=n)


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


def loft_z(stations, ring):
    """loft() along z: ring(z) the same count of points at every station."""
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in ring(z)] for z in stations]
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
# Parts: the shell and what stands on it
# --------------------------------------------------------------------------------------------

def build_shell(k):
    """The shell, lofted from its stepped section along the bore and made in two pieces, military beige
    ahead of the slanted split and matte black behind it (user), then machined: the barrel's bore through
    the nose and its channel behind it, the bolt carrier's raceway, the magazine's opening, the ejection port
    (right) and the charging slot (left) into the raceway, the handguard's half cut and slanted vents into
    the channel, the seam grooves where the front ends, the access panels' recesses; the lamp's clevis
    under the nose."""
    rx, rw, (rz0, rz1) = RACEWAY[0], RACEWAY[1], RACEWAY[2]
    cuts = [bore_cut(CHANNEL[0] + 0.001, SHELL_Y[0] - 0.01),
            (Vector((0, CHANNEL[0], BORE_Z)), Vector((0, rx[0] + 0.001, BORE_Z)), CHANNEL[1], 12)]
    boxes = [((0, sum(rx) / 2, (rz0 + rz1) / 2), (2 * rw, rx[1] - rx[0], rz1 - rz0))]                      # raceway
    (m0, m1), mw = MAG_Y, MAG_W + 0.0009
    boxes.append(((0, (m0 + m1) / 2, (0.150 + rz0 + 0.0005) / 2), (2 * mw, m1 - m0 + 0.0018, rz0 + 0.0005 - 0.150)))
    (p0, p1), (pz0, pz1) = PORT
    boxes.append(((-(rw - 0.0005 + W_R + 0.003) / 2, (p0 + p1) / 2, (pz0 + pz1) / 2),
                  (W_R + 0.003 - rw + 0.0005, p1 - p0, pz1 - pz0)))                                      # ejection port
    (s0, s1), (sz0, sz1) = SLOT
    boxes.append((((rw - 0.0005 + W_R + 0.003) / 2, (s0 + s1) / 2, (sz0 + sz1) / 2),
                  (W_R + 0.003 - rw + 0.0005, s1 - s0, sz1 - sz0)))                                      # charging slot
    wu = W_F - STEP[1]
    for sx in (1, -1):                                                                                    # seam grooves
        boxes.append(((sx * W_F, SEAM_Y, (ZB_F + LOW_R + STEP[0]) / 2), (0.002, 0.0015, STEP[0] - ZB_F - LOW_R - 0.002)))
        boxes.append(((sx * wu, SEAM_Y, (STEP[0] + STEP[1] + TOP_Z - SHOULDER) / 2),
                      (0.002, 0.0015, TOP_Z - SHOULDER - STEP[0] - STEP[1] - 0.002)))
    for ((a0, a1), (az0, az1)), x in zip(PANELS, (W_R, W_R - STEP[1])):
        boxes += [((sx * x, (a0 + a1) / 2, (az0 + az1) / 2), (0.002, a1 - a0, az1 - az0)) for sx in (1, -1)]
    (c0, c1), (vz0, vz1), lean = HALF_CUT
    cutouts = [[(c0, vz0), (c1, vz0), (c1 + lean, vz1), (c0 + lean, vz1)]]
    ys, hw, (vz0, vz1), lean = SLANT_VENTS
    cutouts += [[(y - hw, vz0), (y + hw, vz0), (y + hw + lean, vz1), (y - hw + lean, vz1)] for y in ys]
    subtract = [([(sx * 0.021, y, z) for y, z in c], (1, 0, 0), 0.018) for sx in (1, -1) for c in cutouts]
    stations = [SHELL_Y[0], SHELL_Y[0] + EDGE, FRONT_END, REC_START, SHELL_Y[1] - 0.002, SHELL_Y[1]]
    for ahead, skin in ((True, PRI), (False, SEC)):
        carve(k, loft(stations, shell_ring), "Root", skin, cuts=cuts, boxes=boxes, intersect=[split_region(ahead)],
              subtract=subtract, material=shell_mat(skin))
    # the lamp's clevis under the nose: its cheeks round the hub's slot, the stainless steel pin across them
    (l0, l1), lw, lz = LAMP_MOUNT
    py, pz = LAMP_PIVOT[1:]
    k.plate([(0, y, z) for y, z in rounded([(l0, lz), (l1, lz), (l1, ZB_F + 0.003), (l0, ZB_F + 0.003)],
                                           [0.004, 0.004, 0, 0], n=2)], 2 * lw, (1, 0, 0), "Root", MTL,
            boxes=[((0, py, lz), (2 * lw - 0.006, l1 - l0 + 0.002, 2 * (pz - lz) + 0.0105))])
    k.cyl((-lw - 0.001, py, pz), (lw + 0.001, py, pz), 0.0016, "Root", JNT, segs=6)
    # the barrel nut on the nose face round the barrel
    pipe(k, (0, NUT[1], BORE_Z), (0, NUT[0], BORE_Z), NUT[2], GUIDE_R + 0.0004, "Root", MTL, segs=12)
    # the access panels' screws
    for ((a0, a1), (az0, az1)), x in zip(PANELS, (W_R, W_R - STEP[1])):
        for sx in (1, -1):
            for y, z in ((a0 + 0.006, az1 - 0.005), (a1 - 0.006, az0 + 0.005)):
                bolt(k, (sx * (x - 0.001), y, z), (sx, 0, 0), "Root", r=0.0022, head=0.0014)


def build_rail(k):
    """The matte black rail along the top: a dovetailed bar sunk 1 mm into the top, cross slots cut into it."""
    (y0, y1), hw, h, (f, pitch, n) = RAIL
    zb, zt = TOP_Z - 0.001, TOP_Z + h
    sec = [(x, 0.0, z) for x, _, z in octagon_xz(hw, zb, zt, 0.0015, 0.002, 0)]

    def ring(y):
        return [Vector((x, y, z)) for x, _, z in sec]
    boxes = [((0, f + pitch * i, zt), (2 * hw + 0.004, 0.003, 0.005)) for i in range(n)]
    carve(k, loft([y0, y1], ring), "Root", SEC, boxes=boxes)


def display_frame():
    """The display console on the left upper flank: (y0, y1), its face's bottom and top (x, z) points, its
    outward normal (tilted up toward the gunner's eye)."""
    (y0, y1), (z0, z1), tilt = DISPLAY
    a = math.radians(tilt)
    d0 = 0.0058
    d1 = d0 - (z1 - z0) * math.tan(a)
    wu = W_R - STEP[1]
    return (y0, y1), (wu + d0, z0), (wu + d1, z1), Vector((math.cos(a), 0, math.sin(a)))


def build_display(k):
    """The ammo display standing on the left upper flank: a metallic black wedge (its face tilted up), the
    lit screen inset in its face (no glass over it), a stainless steel screw: the side's one light."""
    (y0, y1), (xb, zb), (xt, zt), n = display_frame()
    wu = W_R - STEP[1]
    side = [(wu - 0.001, zb), (xb, zb), (xt, zt), (wu - 0.001, zt)]
    k.prism([(x, (y0 + y1) / 2, z) for x, z in side], y1 - y0, (0, 1, 0), "Root", MTL)
    mid = Vector(((xb + xt) / 2, 0, (zb + zt) / 2))
    h = (Vector((xt, 0, zt)) - Vector((xb, 0, zb))).length
    for off, th, mat, inset in ((0.0004, 0.0008, EMI, 0.0045),):
        p = mid + n * (off - th / 2 + 0.0002)
        k.obox((p.x, y0 + inset + 0.004, p.z), (p.x, y1 - inset, p.z), h - 2 * inset + 0.002, th, tuple(n), "Root", mat)
    bolt(k, (mid.x, y0 + 0.0035, mid.z), tuple(n), "Root", r=0.0014, head=0.0007)


def build_selector(k):
    """The fire selector on the left lower band over the grip: a stainless steel shaft in the shell, a black hub on
    it and a lever pointing forward (auto), turned up SEL_SEMI for the marksman mode."""
    x, y, z = SEL_PIVOT
    k.cyl((x - 0.004, y, z), (x + 0.0045, y, z), 0.0015, "Root", JNT, segs=6)                  # shaft
    k.cyl((x - 0.0007, y, z), (x + 0.0035, y, z), 0.0045, SELECTOR, MTL, segs=10)              # hub
    lever = [(y - 0.002, z - 0.003), (y - 0.015, z - 0.0014), (y - 0.016, z), (y - 0.015, z + 0.0014), (y - 0.002, z + 0.003)]
    k.prism([(x + 0.0030, ly, lz) for ly, lz in lever], 0.0016, (1, 0, 0), SELECTOR, MTL)


def build_cover(k):
    """The dust cover over the ejection port: a matte black plate, its hinge edge notched round the
    receiver's two knuckles, its own knuckle between them on the stainless steel pin along the step."""
    (y0, y1), (z0, z1), th = COVER
    px, pz, pr = COVER_PIN
    ka, kb = -0.028, 0.006                       # its knuckle (y)
    x = -(W_R - STEP[1]) - 0.0002 - th / 2
    zn = z0 + 0.003
    outline = rounded([(y0, zn), (ka, zn), (ka, z0), (kb, z0), (kb, zn), (y1, zn), (y1, z1), (y0, z1)],
                      [0, 0, 0, 0, 0, 0, 0.003, 0.003], n=2)
    k.plate([(x, y, z) for y, z in outline], th, (1, 0, 0), COVER_BONE, SEC)
    k.cyl((px, ka + 0.0003, pz), (px, kb - 0.0003, pz), 0.0019, COVER_BONE, SEC, segs=8)
    for a, b in ((y0, ka - 0.0005), (kb + 0.0005, y1)):
        k.cyl((px, a, pz), (px, b, pz), 0.0019, "Root", SEC, segs=8)
    k.cyl((px, y0 - 0.001, pz), (px, y1 + 0.001, pz), pr, "Root", JNT, segs=6)


def build_charger(k):
    """The charging handle: a slider in the left flank's slot, ahead of the carrier's lug, its stem out
    through the slot to a T-knob."""
    (c0, c1), (z0, z1) = CHARGER
    rw = RACEWAY[1]
    k.span((rw + 0.0003, c0, z0), (W_R - STEP[1] - 0.0004, c1, z1), CHARGE, MTL)
    yc, zc = (c0 + c1) / 2, (z0 + z1) / 2
    xk, rk = KNOB
    k.cyl((W_R - STEP[1] - 0.001, yc, zc), (xk - 0.003, yc, zc), 0.0034, CHARGE, MTL, segs=8)
    k.cyl((xk - 0.006, yc - 0.010, zc), (xk - 0.006, yc + 0.010, zc), rk - 0.001, CHARGE, JNT, segs=8)


# --------------------------------------------------------------------------------------------
# Parts: the barrel, the bolt carrier and its guide rods
# --------------------------------------------------------------------------------------------

def build_barrel(k):
    """The barrel (titanium): the barrel extension (its chamber's mouth in its rear face, against the bolt
    face), the tube in the nose's bore and the nut, bronze heat-sink collars in the channel; out of the nose
    the grooved jacket, the bare neck, the lock collar and the slotted, ported flash hider (all titanium)."""
    (b0, b1), h = CHAMBER
    sq = [(x, (b0 + b1) / 2, BORE_Z + z) for x, _, z in octagon_xz(h, -h, h, 0.002, 0.002, 0)]
    k.plate(sq, b1 - b0, (0, 1, 0), BARREL, FRM, cuts=[((0, b1 + 0.001, BORE_Z), (0, b1 - 0.012, BORE_Z), 0.0066, 10)])
    f, rear, r = BRAKE
    pipe(k, (0, b0 + 0.001, BORE_Z), (0, rear - 0.006, BORE_Z), BARREL_R, BARREL_BORE, BARREL, FRM, segs=12)
    ys, cr, th = COLLARS
    for y in ys:
        k.cyl((0, y - th / 2, BORE_Z), (0, y + th / 2, BORE_Z), cr, BARREL, BRZ, segs=12)
    ri = BARREL_R - 0.0003                                                                # sits on the tube
    (j0, j1), jr, gys, gw, gd = JACKET
    prof = [(jr - 0.001, j1), (jr, j1 - 0.001)]
    for gy in sorted(gys, reverse=True):
        prof += [(jr, gy + gw / 2), (jr - gd, gy + gw / 2), (jr - gd, gy - gw / 2), (jr, gy - gw / 2)]
    prof += [(jr, j0 + 0.0015), (jr - 0.0015, j0), (ri, j0), (ri, j1)]
    lathe(k, prof, BARREL, FRM, segs=10, loop=True)                                      # jacket
    (c0, c1), cr = MUZZLE_COLLAR
    lathe(k, [(cr - 0.001, c1), (cr, c1 - 0.001), (cr, c0 + 0.001), (cr - 0.001, c0), (ri, c0), (ri, c1)], BARREL, FRM,
          segs=12, loop=True)                                                            # lock collar
    prof = [(r, rear + 0.0005), (r, f + 0.003), (r - 0.0018, f), (0.0068, f), (0.0068, rear + 0.0005)]
    bm = revolve_bm(prof, (0, 0, BORE_Z), (0, 1, 0), (1, 0, 0), segs=12, loop=True)
    ln, sw = HIDER_SLOTS
    boxes = [((0, f + ln / 2 - 0.001, BORE_Z), (0.03, ln + 0.002, sw)), ((0, f + ln / 2 - 0.001, BORE_Z), (sw, ln + 0.002, 0.03))]
    ys, pr = HIDER_PORTS
    ports = [((-0.02, y, BORE_Z), (0.02, y, BORE_Z), pr, 8) for y in ys]
    ports.append(((0, sum(ys) / 2, BORE_Z), (0, sum(ys) / 2, BORE_Z + 0.02), 0.0020, 6))
    carve(k, bm, BARREL, FRM, cuts=ports, boxes=boxes)                                    # flash hider


def build_bolt(k):
    """The bolt carrier (bronze): a block in the raceway, its front the bolt face, the guide rods' bores up
    its back, a relief along its right flank (seen through the port), the stainless steel extractor at its front
    right, the charging lug on its left flank."""
    (y0, y1), w, (z0, z1) = (BOLT_Y[0] + 0.0002, BOLT_Y[1]), BOLT_W, BOLT_Z
    rx, rz, _, _ = BOLT_RODS
    br, bend = ROD_BORE
    cuts = [((sx * rx, y1 + 0.005, rz), (sx * rx, bend, rz), br, 8) for sx in (1, -1)]
    boxes = [((-w, (y0 + 0.018 + y1 - 0.02) / 2, 0.212), (0.003, y1 - 0.02 - y0 - 0.018, 0.016))]
    sec = [(x, (y0 + y1) / 2, z) for x, _, z in octagon_xz(w, z0, z1, 0.0015, 0.0015, 0)]
    k.plate(sec, y1 - y0, (0, 1, 0), BOLT, BRZ, cuts=cuts, boxes=boxes)
    k.span((-w - 0.0005, y0 + 0.002, 0.2045), (-w + 0.0008, y0 + 0.016, 0.2095), BOLT, JNT)            # extractor
    (l0, l1), (lz0, lz1) = LUG
    k.span((w - 0.0008, l0, lz0), (RACEWAY[1] + 0.0045, l1, lz1), BOLT, BRZ)                              # lug


def build_bolt_rods(k):
    """The carrier's guide rods: stainless steel, fixed in the raceway's rear wall, running forward into its bores."""
    x, z, r, (y0, y1) = BOLT_RODS
    for sx in (1, -1):
        k.cyl((sx * x, y0, z), (sx * x, y1, z), r, "Root", JNT, segs=8)


# --------------------------------------------------------------------------------------------
# Parts: the magwell, the catch, the trigger housing, the trigger, the grip
# --------------------------------------------------------------------------------------------

def magwell_ring(z):
    zm, zt, side, rear, flare, rake = MAGWELL
    g = flare * max(0.0, 1 - (z - zm) / flare)
    f = rake * (zt - z) / (zt - zm)
    (m0, m1), w = MAG_Y, MAG_W
    return [Vector((x, y, z)) for x, y in rounded([(w + side + g, m0 - side - g - f), (w + side + g, m1 + rear + g),
                                                   (-w - side - g, m1 + rear + g), (-w - side - g, m0 - side - g - f)],
                                                  [0.006, 0.004, 0.004, 0.006], n=2)]


def build_magwell(k):
    """The magwell (military beige): a collar lofted round the magazine, its mouth flared, its front face raked
    forward to the mouth, its top sunk into the belly; the catch's bore across its rear wall, the button's
    counterbore on the right, the tooth's pocket on the left."""
    zm, zt, side, rear, flare, rake = MAGWELL
    hole = [Vector((x, y, 0)) for x, y in rounded_rect(MAG_W + 0.0005, MAG_Y[0] - 0.0005, MAG_Y[1] + 0.0005, MAG_R + 0.0005)]
    cy, cz, cr = CATCH
    xo = MAG_W + side
    cuts = [((-xo - 0.002, cy, cz), (xo + 0.002, cy, cz), cr + 0.0003, 8),
            ((-xo - 0.001, cy, cz), (-xo + 0.0045, cy, cz), BUTTON[1] + 0.0002, 10)]
    (t0, t1), (tz0, tz1), (tx0, _) = TOOTH
    boxes = [(((tx0 - 0.0005 + xo + 0.003) / 2, (MAG_Y[1] + t1 + 0.001) / 2, (tz0 + tz1) / 2),
              (xo + 0.003 - tx0 + 0.0005, t1 + 0.001 - MAG_Y[1], tz1 - tz0 + 0.001))]
    carve(k, loft_z([zm, zm + flare, zt], magwell_ring), "Root", PRI, holes=[hole], cuts=cuts, boxes=boxes)


def build_catch(k):
    """The magazine catch (bone MagCatch): a stainless steel cross bolt through the magwell's rear wall, its black
    button on the right, its tooth at its left end in the magazine's notch."""
    cy, cz, cr = CATCH
    (t0, t1), (tz0, tz1), (tx0, tx1) = TOOTH
    bx, brr = BUTTON
    k.cyl((bx + 0.001, cy, cz), (tx1 - 0.001, cy, cz), cr, CATCH_BONE, JNT, segs=6)
    k.cyl((bx, cy, cz), (bx + 0.006, cy, cz), brr, CATCH_BONE, MTL, segs=10)
    k.span((tx0, t0, tz0), (tx1, t1, tz1), CATCH_BONE, MTL)


def build_trigger_housing(k):
    """The trigger housing (matte black), one bevelled plate hanging from the belly behind the magwell: the
    open trigger guard (its front bar, its bottom bar ending short of the curled fingers) and the
    trigger's block and slot, its back into the grip's front; the trigger's stainless steel pin."""
    g0, g1 = GUARD_FRONT
    zb, th, ye = GUARD_BOTTOM
    zt = BELLY + 0.005
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


def build_grip(k):
    """The pistol grip (matte black), raked back, machined in its own frame (z up its axis, -y forward):
    finger grooves on its front, slanted grip grooves across both sides, a pommel on the bottom plane, a
    beavertail over the hand's web and a web relief under it, its top sunk 5 mm into the belly, its section
    chamfered."""
    G = Vector(GRIP_G)
    hx, D = GRIP_HALF
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))

    def top(y):  # local z of the world plane z = BELLY + 0.005 at local y
        return (BELLY + 0.005 - G.z - y * s) / c

    def bottom(y):  # local z of the bottom plane z = 0 at local y
        return (-G.z - y * s) / c

    prof = [(-D, top(-D)), (-D, -0.056), (-D - 0.004, -0.063), (-D + 0.002, bottom(-D + 0.002)),
            (D + 0.004, bottom(D + 0.004)), (D + 0.006, -0.061), (D, -0.052), (D, WEB[1]), (WEB[0], WEB[2]),
            (WEB[0], min(WEB[3], top(D) - 0.014))]
    if top(D) - 0.014 > WEB[3] + 0.008:              # a grip taller than the hand: the backstrap resumes
        prof += [(D, WEB[3] + 0.008), (D, top(D) - 0.014)]
    prof += [(D + 0.016, top(D + 0.016) - 0.004), (D + 0.016, top(D + 0.016))]
    frame = Matrix.Translation(G) @ Matrix.Rotation(math.radians(GRIP_RAKE), 4, "X")
    with k.frame(frame):
        grooves = [((-0.02, -D - 0.0045, z), (0.02, -D - 0.0045, z), 0.0075, 8) for z in (0.01, -0.01, -0.03)]
        ribs = [([(sx * hx, y, z + dz) for y, dz in ((-D + 0.007, 0.0), (D - 0.005, 0.006), (D - 0.005, 0.009),
                                                     (-D + 0.007, 0.003))], (1, 0, 0), 0.0024)
                for sx in (1, -1) for z in (-0.046, -0.032, -0.018, -0.004)]
        k.plate([(0, y, z) for y, z in prof], 2 * hx, (1, 0, 0), "Root", SEC,
                intersect=[([(x, z, 0) for x, _, z in octagon_xz(hx, -D - 0.02, D + 0.02, 0.005, 0.005, 0)], (0, 0, 1), 1.0)],
                cuts=grooves, subtract=ribs)


# --------------------------------------------------------------------------------------------
# Parts: the stock
# --------------------------------------------------------------------------------------------

def stock_bottom(y):
    (f, b, _), (zf, zb) = STOCK_Y, STOCK_BOTTOM
    return zf + (zb - zf) * (y - f) / (b - f)


def stock_section(y, s=0.0):
    w, zt, cf, zb = STOCK_W - s, COMB_Z - s, COMB_F, stock_bottom(y) + s
    return rounded([(w, zb), (w, zt - cf), (w - cf, zt), (-w + cf, zt), (-w, zt - cf), (-w, zb)],
                   [0.007, 0, 0, 0, 0, 0.007], n=2)


def build_stock(k):
    """The skeleton stock (user: open in the centre, as the lightning gun's): two stainless steel rods out of the
    shell's rear face into the black lofted buttstock (its front edge chamfered), an opening through it
    (its front and back edges upright, its top parallel to the comb, its bottom to the sloping underside,
    its walls beige), the beige cheek riser over its comb on two stainless steel posts, the metallic black buttpad
    exactly its back face, grip grooves across it."""
    f, b, e = STOCK_Y
    ring = lambda y: [Vector((x, y, z)) for x, z in stock_section(y, max(0.0, 0.002 - (y - f)))]
    (y0, y1), (tz, bz) = STOCK_HOLE
    hole = rounded([(y0, COMB_Z - tz), (y0, stock_bottom(y0) + bz), (y1, stock_bottom(y1) + bz), (y1, COMB_Z - tz)],
                   [0.008] * 4, n=2)

    def walls(face):  # the opening's walls beige
        face.normal_update()
        c = face.calc_center_median()
        return PRI if abs(face.normal.x) < 0.5 and y0 - 0.0005 < c.y < y1 + 0.0005 and             stock_bottom(c.y) + bz - 0.0005 < c.z < COMB_Z - tz + 0.0005 else SEC
    carve(k, loft([f, f + 0.002, b], ring), "Root", SEC, holes=[[Vector((0, y, z)) for y, z in hole]],
          bevel_normal=(1, 0, 0), material=walls)
    (r0, r1), rw, (rz0, rz1), posts, pr = RISER
    top = rounded([(rw, r0), (rw, r1), (-rw, r1), (-rw, r0)], [0.006, 0.006, 0.006, 0.006], n=2)
    k.plate([(x, y, (rz0 + rz1) / 2) for x, y in top], rz1 - rz0, (0, 0, 1), "Root", PRI, bevel=0.0015)
    for y in posts:
        k.cyl((0, y, COMB_Z - 0.003), (0, y, rz0 + 0.001), pr, "Root", JNT, segs=8)
    pad = lambda y: [Vector((x, y, z)) for x, z in stock_section(b)]
    grooves = [((0, e, z), (2 * STOCK_W - 0.008, 0.003, 0.0025)) for z in (0.118, 0.141, 0.164, 0.187, 0.210)]
    carve(k, loft([b, e], pad), "Root", MTL, boxes=grooves, bevel=0.0015, bevel_normal=(0, 1, 0))
    x, z, r, (y0, y1) = STOCK_RODS
    for sx in (1, -1):
        k.cyl((sx * x, y0, z), (sx * x, y1, z), r, "Root", JNT, segs=10)


# --------------------------------------------------------------------------------------------
# Parts: the optic
# --------------------------------------------------------------------------------------------

def octagon(a, y):
    """(x, y, z) of an octagon a across flats (half) round the optic's axis at y, flats up, down and to the sides."""
    R = a / math.cos(math.pi / 8)
    return [(R * math.cos(math.pi / 8 + math.pi / 4 * i), y, SCOPE_Z + R * math.sin(math.pi / 8 + math.pi / 4 * i))
            for i in range(8)]


def octagon_loft(keys):
    """A closed octagonal loft through (y, across flats) keys."""
    return loft([y for y, _ in keys], lambda y: [Vector(p) for p in octagon(dict(keys)[y], y)])


def build_optic(k):
    """The optic (bone Optic) on the rail: two metallic black clamp mounts straddling the rail and sliding
    along it (a stainless steel clamp screw across each, over the rail); the matte black octagonal body, its edges
    chamfered at both ends; the metallic black objective housing
    flaring from its front, the sleeve's octagonal bore in it; the rubber eyepiece behind (an octagonal
    recess and its lens); the elevation turret on top and the windage turret on the right (stainless steel caps);
    the laser rangefinder over the nose with its lens; the zoom actuator's black barrel on a bracket on the
    body's left."""
    (b0, b1), a = BODY
    for y in MOUNTS:
        hw, lo = RAIL[1] + 0.0007, TOP_Z + 0.0005
        u = [(0.0145, lo), (0.0145, SCOPE_Z - a + 0.0025), (-0.0145, SCOPE_Z - a + 0.0025), (-0.0145, lo),
             (-hw, lo), (-hw, TOP_Z + RAIL[2] + 0.0003), (hw, TOP_Z + RAIL[2] + 0.0003), (hw, lo)]
        k.prism([(x, y, z) for x, z in u], 0.014, (0, 1, 0), OPTIC, MTL, convex=False)
        k.cyl((-0.0162, y, TOP_Z + RAIL[2] + 0.0045), (0.0162, y, TOP_Z + RAIL[2] + 0.0045), 0.0022, OPTIC, JNT, segs=6)
    k.emit(octagon_loft([(b0, a - 0.002), (b0 + 0.002, a), (b1 - 0.002, a), (b1, a - 0.002)]), OPTIC, SEC, False,
           convex=False, exact=True)
    (bf, bb), ba, bore = BELL
    housing = octagon_loft([(b0 + 0.002, a - 0.0015), (bb - 0.004, ba), (bf + 0.002, ba), (bf, ba - 0.002)])
    carve(k, housing, OPTIC, MTL, subtract=[(octagon(bore, (bf - 0.01 + bb) / 2), (0, 1, 0), bb - bf + 0.01)])
    (e0, e1), ea = EYEPIECE
    cup = octagon_loft([(e0 - 0.002, a - 0.0015), (e0 + 0.010, a - 0.0015), (e0 + 0.018, ea), (e1 - 0.002, ea),
                        (e1, ea - 0.002)])
    carve(k, cup, OPTIC, SEC, subtract=[(octagon(ea - 0.0045, e1), (0, 1, 0), 0.016)])
    k.prism(octagon(ea - 0.0043, e1 - 0.0082), 0.0008, (0, 1, 0), OPTIC, GLS)
    ty, tr, th = TURRET
    for p0, p1 in (((0, ty, SCOPE_Z + a - 0.0005), (0, ty, SCOPE_Z + a + th)),
                   ((-a + 0.0005, ty, SCOPE_Z), (-a - th, ty, SCOPE_Z))):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        k.cyl(p0, p1, tr, OPTIC, MTL, segs=12)
        k.cyl(p1 - d * 0.0005, p1 + d * 0.0012, tr - 0.0022, OPTIC, JNT, segs=10)
    (r0, r1), rw, rh = RANGEFINDER
    k.span((-rw, r0, SCOPE_Z + a - 0.0005), (rw, r1, SCOPE_Z + a + rh), OPTIC, MTL)
    k.span((-rw + 0.0015, r0 - 0.0006, SCOPE_Z + a + 0.002), (rw - 0.0015, r0 + 0.0003, SCOPE_Z + a + rh - 0.0015), OPTIC, GLS)
    (ax, az), (ya, yb), rb, rr = ZOOM_ACT
    k.cyl((ax, ya, az), (ax, yb, az), rb, OPTIC, MTL, segs=8)
    k.span((a - 0.0005, yb - 0.016, az - rb), (ax, yb - 0.002, az + 0.003), OPTIC, MTL)                  # bracket


def build_zoom(k):
    """The objective sleeve (bone Zoom): a titanium octagonal tube sliding in the housing's bore (a
    sliding fit, the same octagon), a hood at its front with the actuator's ear, the objective lens inside,
    and the actuator's stainless steel rod from the ear back into the barrel."""
    (s0, s1), ao, ai = SLEEVE
    tube = octagon_loft([(s0 - 0.0055, ao + 0.0012), (s0, ao + 0.0012), (s0 + 0.0001, ao), (s1, ao)])
    carve(k, tube, ZOOM, FRM, subtract=[(octagon(ai, (s0 + s1) / 2), (0, 1, 0), s1 - s0 + 0.02)])
    k.prism(octagon(ai + 0.0002, s0 + 0.0085), 0.001, (0, 1, 0), ZOOM, GLS)
    (ax, az), (ya, yb), rb, rr = ZOOM_ACT
    k.span((ao, s0 - 0.0055, az - 0.004), (ax + 0.0035, s0 - 0.0006, az + 0.004), ZOOM, MTL)                # ear
    k.cyl((ax, s0 - 0.003, az), (ax, ya + 0.026, az), rr, ZOOM, JNT, segs=6)                                # rod


def build_lamp(k):
    """The floodlight (bone Lamp) hanging under the nose: its hub on the clevis's pin between the cheeks, an
    arm down to the clamp ring round its matte black body, titanium grip rings, a stainless steel tail button, the
    metallic black head flaring at the front round the lit lens in a stainless steel bezel."""
    py, pz = LAMP_PIVOT[1:]
    (t, hr, f), br, hd, az = LAMP
    k.cyl((-0.0070, py, pz), (0.0070, py, pz), 0.0045, LAMP_BONE, MTL, segs=10)                            # hub
    k.span((-0.005, py - 0.0035, az + br + 0.001), (0.005, py + 0.0035, pz - 0.003), LAMP_BONE, MTL)       # arm
    k.cyl((0, py + 0.0055, az), (0, py - 0.0055, az), br + 0.002, LAMP_BONE, MTL, segs=12)                 # clamp ring
    k.cyl((0, t, az), (0, hr + 0.001, az), br, LAMP_BONE, SEC, segs=12)                                   # body
    for y in (-0.2735, -0.2825):
        k.cyl((0, y + 0.0015, az), (0, y - 0.0015, az), br + 0.0008, LAMP_BONE, FRM, segs=12)              # grip rings
    k.cyl((0, t + 0.0015, az), (0, t - 0.001, az), 0.005, LAMP_BONE, JNT, segs=8)                          # tail button
    revolve(k, [(0.0, hr), (br - 0.0005, hr), (hd, hr - 0.005), (hd, f + 0.0015), (hd - 0.0015, f),
                (hd - 0.0045, f), (hd - 0.0045, f + 0.0025), (0.0, f + 0.0025)],
            (0, 0, az), (0, 1, 0), (1, 0, 0), LAMP_BONE, MTL, segs=12)                                    # head
    k.cyl((0, f + 0.0027, az), (0, f + 0.0021, az), hd - 0.0044, LAMP_BONE, EMI, segs=12)                  # lens
    pipe(k, (0, f + 0.0018, az), (0, f - 0.0004, az), hd - 0.0012, hd - 0.0046, LAMP_BONE, JNT, segs=12)   # bezel


def build_scope(k):
    """The optic and its sleeve: their own mesh (it comes off the rail)."""
    build_optic(k)
    build_zoom(k)


def build_gun(k, pistons, joints):
    build_shell(k)
    build_rail(k)
    build_display(k)
    build_selector(k)
    build_cover(k)
    build_charger(k)
    build_barrel(k)
    build_bolt(k)
    build_bolt_rods(k)
    build_magwell(k)
    build_catch(k)
    build_trigger_housing(k)
    build_trigger(k)
    build_grip(k)
    build_stock(k)
    build_lamp(k)


# --------------------------------------------------------------------------------------------
# Parts: the magazine
# --------------------------------------------------------------------------------------------

def build_round(k, y1, x, z, bone):
    """A round lying along the bore (its base at y1): a bronze case and a steel-tipped bullet."""
    r, length, case = ROUND
    k.cyl((x, y1, z), (x, y1 - case, z), r, bone, BRZ, segs=6)
    k.cyl((x, y1 - case + 0.0005, z), (x, y1 - length, z), r - 0.0003, bone, JNT, segs=6, r1=0.0022)


def build_pack(k):
    """The magazine (bone Mag), matte black: a wide box lofted up from its beige base plate, a cavity
    holding the rounds, three upright slots through each flank onto the outer columns' rounds, grip
    grooves across its front, the catch's notch in its rear left corner; its feed tower up into the shell
    with the top round in its lips."""
    (m0, m1), w, r = MAG_Y, MAG_W, MAG_R
    zb = BASE[0] - 0.001
    ring = lambda z: [Vector((x, y, z)) for x, y in rounded_rect(w, m0, m1, r)]
    boxes = [((0, (m0 + m1) / 2, (0.014 + MAG_TOP - 0.004) / 2), (2 * (w - 0.004), m1 - m0 - 0.008, MAG_TOP - 0.018))]
    boxes += [((0, m0, z), (2 * w - 0.014, 0.003, 0.003)) for z in (0.045, 0.065, 0.085, 0.105)]
    (t0, t1), (tz0, tz1), (tx0, tx1) = TOOTH
    boxes.append((((tx0 - 0.0005 + w + 0.002) / 2, (t0 - 0.0005 + m1 + 0.002) / 2, (tz0 + tz1) / 2),
                  (w + 0.002 - tx0 + 0.0005, m1 + 0.002 - t0 + 0.0005, tz1 - tz0 + 0.0012)))
    ys, hw, (sz0, sz1) = MAG_SLOTS
    subtract = [([(sx * (w - 0.002), y, z) for y, z in vslot(y, hw, sz0, sz1)], (1, 0, 0), 0.006)
                for sx in (1, -1) for y in ys]
    carve(k, loft_z([zb, MAG_TOP], ring), MAG, SEC, boxes=boxes, subtract=subtract)
    h, g = BASE
    k.plate([(x, y, h / 2) for x, y in rounded_rect(w + g, m0 - g, m1 + g, r + g)], h, (0, 0, 1), MAG, PRI, bevel=0.0012)
    (y0, y1), tw, tz = TOWER
    k.span((-tw, y0, MAG_TOP - 0.002), (tw, y1, tz), MAG, SEC)
    z0, pitch, n = ROUND_ROWS
    xr = w - 0.004 - ROUND[0] - 0.0007
    for i in range(n):
        build_round(k, m1 - 0.0045, xr, z0 + pitch * i, MAG)
        build_round(k, m1 - 0.0045, -xr, z0 + pitch * (i + 0.5), MAG)
    build_round(k, m1 - 0.0045, 0.0, TOP_ROUND_Z, MAG)


# --------------------------------------------------------------------------------------------
# Checks specific to the rifle
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """Joint-range sweeps on top of the animation frames: the carrier's travel (the barrel with it), the
    charging handle's (the carrier with it), the dust cover, the trigger, the selector, the zoom, the catch,
    the magazine with the catch pressed, and the cover open with the carrier cycling."""
    states = [(f"bolt {BOLT_TRAVEL * i / 12:.4f}", {BOLT: BOLT_TRAVEL * i / 12, COVER_BONE: COVER_OPEN}) for i in range(1, 13)]
    states += [(f"charge {BOLT_TRAVEL * i / 8:.4f}", {CHARGE: BOLT_TRAVEL * i / 8}) for i in range(1, 9)]
    states += [(f"cover {a}", {COVER_BONE: a}) for a in range(0, COVER_OPEN + 1, 10)]
    states += [(f"trigger {v}", {TRIGGER: v}) for v in range(0, TRIGGER_PULL + 1, 2)]
    states += [(f"selector {a}", {SELECTOR: a}) for a in range(0, SEL_SEMI + 1, 10)]
    states += [(f"zoom {ZOOM_TRAVEL * i / 8:.4f}", {ZOOM: ZOOM_TRAVEL * i / 8}) for i in range(1, 9)]
    lo, hi = OPTIC_TRAVEL
    states += [(f"optic {lo + (hi - lo) * i / 16:.4f}", {OPTIC: lo + (hi - lo) * i / 16, ZOOM: ZOOM_TRAVEL * (i % 2)})
               for i in range(17)]
    states += [(f"lamp {a}", {LAMP_BONE: a}) for a in range(0, LAMP_TILT + 1, 4)]
    states += [(f"catch {CATCH_TRAVEL * i / 4:.4f}", {CATCH_BONE: CATCH_TRAVEL * i / 4}) for i in range(1, 5)]
    states += [(f"mag {MAG_TRAVEL * i / 10:.4f}", {CATCH_BONE: CATCH_TRAVEL, MAG: MAG_TRAVEL * i / 10}) for i in range(11)]
    return states


def check_envelope(kit):
    """Every weapon fits WEAPON_MAX (wide x long x high) at rest, its bottom on z = 0 (the item table's and the weapon holder's
    mount takes it by its bottom). Returns its size and how far along Y the export moves it so its origin is midway
    along it (it is authored where it was before its stock was shortened)."""
    parts = all_parts(kit)
    lo = Vector(min(p.lo[i] for p in parts) for i in range(3))
    hi = Vector(max(p.hi[i] for p in parts) for i in range(3))
    size, problems = hi - lo, []
    for i, what in enumerate(("wide", "long", "high")):
        if size[i] > WEAPON_MAX[i] + 1e-6:
            problems.append(f"{size[i]:.3f} m {what}: over the {WEAPON_MAX[i]} m limit")
    if abs(lo.z) > 1e-4:
        problems.append(f"its bottom is at z {lo.z:.4f}, not on z = 0")
    if problems:
        raise SystemExit(f"[{NAME}] envelope failed:\n  " + "\n  ".join(problems))
    return size, round(-(lo.y + hi.y) / 2, 4)


def check_hand_sockets(kit):
    """Tensor's palm (a box in its hand bone frame) at each socket: it sinks into no part of the gun,
    and its face lies on the grip (within 1.5 mm)."""
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
    """(name, bone, origin, forward, up) of every gizmo: an empty whose local +Y is `forward` and +Z
    `up` in Blender (in glTF / Godot: -Z forward, +Y up). The muzzle rides the barrel (it recoils with
    it); the shell ejection point is on the port in the right flank, pointing out, up and back as a case
    leaves; ScopeEye is the sniper's eye point behind the eyepiece, looking down the optic's axis (it moves
    with the optic along the rail); Flashlight is on the lamp's lens, looking along its beam."""
    out = [("Muzzle", BARREL, Vector((0, BRAKE[0] - 0.01, BORE_Z)), Vector(FWD), Vector(UP))]
    (p0, p1), (pz0, pz1) = PORT
    eject = Vector((-0.85, 0.3, 0.45)).normalized()
    up = (Vector(UP) - eject * eject.dot(Vector(UP))).normalized()
    out.append(("ShellEject", "Root", Vector((-(W_R - STEP[1]), (p0 + p1) / 2, (pz0 + pz1) / 2)), eject, up))
    out.append(("ScopeEye", OPTIC, Vector((0, EYEPIECE[0][1] + EYE_RELIEF, SCOPE_Z)), Vector(FWD), Vector(UP)))
    out.append(("Flashlight", LAMP_BONE, Vector((0, LAMP[0][2] - 0.001, LAMP[3])), Vector(FWD), Vector(UP)))
    return out


def shift_gun(rig, meshes, dy):
    """The built gun moved dy along Y (its origin midway along it): the rig's bones and the meshes skinned to them;
    the gizmos ride their bones."""
    select_only([rig])
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in rig.data.edit_bones:
        eb.head.y += dy
        eb.tail.y += dy
    bpy.ops.object.mode_set(mode="OBJECT")
    for m in meshes:
        m.data.transform(Matrix.Translation((0.0, dy, 0.0)))


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


def build_preview_markers(rig, dy):
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
        m.translation = origin + Vector((0.0, dy, 0.0))
        place_on_bone(obj, rig, bone, m)


def export_pickup(ammo, dy):
    """The magazine on its own for the pickup: an unskinned copy, upright as it rides in the magwell (the
    rounds' tips toward -Y), its origin at its bottom centre."""
    mesh = ammo.data.copy()
    P = Matrix.Translation(-Vector((0, sum(MAG_Y) / 2 + dy, 0.0)))
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
    """Skin, unwrap and hold to the budget without the unseen-face cull: the magazine's rounds show only
    through its narrow slots, at grazing angles the cull's rays miss (a culled build lost slivers of them),
    and it fits its budget whole."""
    check_coplanar(obj)
    skin(obj, rig)
    unwrap(obj)
    tris = triangles(obj)
    print(f"[{NAME}] {obj.name}: {tris} tris (budget {budget}, not culled)")
    if tris > budget:
        raise SystemExit(f"[{NAME}] {obj.name} over triangle budget: {tris}")
    return tris


def write_rig_json(ammo_frame, joints, pistons, tris, ammo_tris, size, optic_tris, dy):
    at = lambda v: Vector(v) + Vector((0.0, dy, 0.0))   # (the gun moved along Y, its origin midway)
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
            "grips": "the magwell: the palm on its left, the fingers round its front" if side == "Left" else "pistol grip",
            "wrist_blender": vec(at(wrist)), "bone_x_blender": vec(x), "bone_y_blender": vec(y), "bone_z_blender": vec(z),
            "wrist_godot": godot(at(wrist)), "bone_x_godot": godot(x), "bone_y_godot": godot(y), "bone_z_godot": godot(z),
            "grip_pose_deg": pose}
    spec = lambda n: [{"name": g, "bone": b, "position": vec(at(o)), "forward": vec(f), "up": vec(u)}
                      for g, b, o, f, u in gizmo_specs() if g.startswith(n)]
    shots = list(range(0, FIRE_F, CYCLE))
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, the muzzle points -Y, the origin is the gun's bottom centre (the magazine's "
                 "and the grip's bottom plane, midway along the gun). glTF/Godot: (x, z, -y), so the muzzle points +Z "
                 "(glTF's front). Hinges turn about their bone's local X (degrees), slides move along their bone's "
                 "local Y (metres).",
        "rest": "bolt carrier and barrel home, dust cover shut, charging handle forward, trigger forward, selector on "
                "auto, the optic's sleeve in, magazine in, catch out",
        "size_m": {"wide": round(size.x, 3), "long": round(size.y, 3), "high": round(size.z, 3),
                   "max_wide_long_high": list(WEAPON_MAX), "bore_axis_height": round(BORE_Z, 4),
                   "note": "a designated marksman rifle (assault rifle with a sniper's optic); every weapon fits "
                           "0.25 x 0.75 x 0.35 m"},
        "materials": SLOTS,
        "triangles": {f"SK_{TITLE}": tris, f"SK_{TITLE}Optic": optic_tris, f"SK_{TITLE}Ammo": ammo_tris,
                      f"SM_{TITLE}Ammo": ammo_tris},
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(at(j.pivot)), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "coupled": {BARREL: f"min({BOLT} as fired, {RECOIL}): short recoil, the barrel rides the carrier's first "
                            "centimetre locked to its face, then stops, and the carrier brings it home (not when "
                            "the carrier is pulled back on the charging handle)",
                    BOLT: f"max({BOLT}, {CHARGE}): the charging handle pushes the carrier back by its lug; the carrier "
                          "never drags the handle (baked into every action)"},
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "fire": {
            "auto": f"fire_start ({START_F} frames: the trigger pulls, the dust cover drops open), then loop fire "
                    f"({FIRE_F} frames, {len(shots)} shots, {60 * FPS // CYCLE} rounds a minute): a shot on frames "
                    f"{shots}: fire the hitscan / spawn the muzzle flash at Muzzle then; the carrier is fully back "
                    f"the frame after each (throw the case from ShellEject, forward = its direction); then fire_end "
                    f"({END_F} frames: the trigger lets go, the cover closes).",
            "marksman": f"scope_in ({SCOPE_F} frames: the selector turns to marksman, the optic's sleeve runs "
                        f"{ZOOM_TRAVEL * 1000:g} mm out to zoom), loop idle_scoped, and fire_marksman per shot "
                        f"({MARKS_F} frames: the shot on frame {MARKS_SHOT}, the case out on frame {MARKS_SHOT + 2}, "
                        f"the cover opening and closing round it); scope_out to go back. Put the camera on "
                        f"ScopeEye to look through the optic.",
            "reload": "mag_release, mag_insert, then charge (the charging handle pulls the carrier back and lets it "
                      "run home).",
            "idle": f"idle ({IDLE_F} frames, loop) and idle_scoped hold their pose between shots: nothing on the "
                    "rifle moves at rest; every action starts and ends at rest except the fire loop (from fire_start, "
                    "into fire_end) and the marksman actions (from scope_in, into scope_out).",
            "cycle_frames": CYCLE, "shot_frames": shots, "bolt_travel_m": BOLT_TRAVEL, "recoil_m": RECOIL,
            "zoom_travel_m": ZOOM_TRAVEL},
        "gizmos": {
            "convention": "empties: in Blender local +Y is the gizmo's forward and +Z its up; in glTF / Godot -Z is "
                          "forward and +Y up (Marker3D / Node3D under a BoneAttachment3D, so they follow the "
                          "animations)",
            "muzzle": spec("Muzzle")[0],
            "muzzle_note": "1 cm in front of the flash hider's face, on the barrel's bone: the hitscan's origin and "
                           "where to play the muzzle flash (and its light)",
            "shell_eject": spec("ShellEject")[0],
            "shell_eject_note": "on the ejection port in the right flank, forward = out, up and back as a case "
                                "leaves: spawn the spent case there when the carrier is fully back",
            "scope_eye": spec("ScopeEye")[0],
            "scope_eye_note": f"the sniper's eye point, {EYE_RELIEF * 1000:g} mm behind the optic's eyepiece on its "
                              "axis, looking forward along it, on the Optic bone (it moves with the optic along the "
                              "rail): move the camera here for the marksman mode",
            "flashlight": spec("Flashlight")[0],
            "flashlight_note": "on the lamp's lens, on the Lamp bone, forward = the beam: put the spotlight here and "
                               "toggle it; tilt the lamp (Lamp, 0 to LAMP_TILT deg down) to aim the beam lower",
        },
        "ammo_hand_socket": ammo_socket_json((at(ammo_frame[0]),) + tuple(ammo_frame[1:])),
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
        "optic": {"mesh": f"SK_{TITLE}Optic", "bone": OPTIC, "travel_m": list(OPTIC_TRAVEL),
                  "note": "the optic rides the rail on the Optic bone (local Y, forward +): set it anywhere in its "
                          "travel to put it farther or closer; slid past the front end of its travel it is off the "
                          "rail: hide SK_RifleOptic (and use the iron-free view), slide it back on to refit it."},
        "lamp": {"bone": LAMP_BONE, "tilt_deg": [0, LAMP_TILT], "gizmo": "Flashlight"},
        "ammo": {"mesh": f"SK_{TITLE}Ammo", "bone": MAG, "pickup_file": f"{NAME}_ammo.glb",
                 "pickup_mesh": f"SM_{TITLE}Ammo", "pickup_origin": "its bottom centre, upright", "axis": [0, 0, -1],
                 "rails_m": MAG_TRAVEL,
                 "note": "mag_release presses the catch and drops the magazine down the magwell; past MAG_TRAVEL it "
                         "is free: hide the magazine mesh and drop a physics copy of the pickup mesh at the Mag "
                         "bone's transform. To reload, put the magazine back at the end of its travel and play "
                         "mag_insert (the catch snaps into its notch), then charge."},
        "usage": "idle (loop); auto: fire_start, fire (loop), fire_end; marksman: scope_in, idle_scoped (loop), "
                 "fire_marksman per shot, scope_out; reload: mag_release, mag_insert, charge.",
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
    build_scope(kit)
    build_pack(kit)
    size, dy = check_envelope(kit)
    print(f"[{NAME}] size {size.x:.3f} wide x {size.y:.3f} long x {size.z:.3f} m high (max {WEAPON_MAX})")
    check_connectivity(kit, joints, pistons)
    check_joint_alignment(kit, joints)
    check_hand_sockets(kit)
    ammo_frame = check_ammo_socket(kit, joints)
    states = action_states(actions, joints) + sweep_states(joints)
    check_motion(kit, joints, states)
    print(f"[{NAME}] checks passed ({len(states)} motion states)")

    gun_kit, optic_kit, ammo_kit = Kit(), Kit(), Kit()
    build_gun(gun_kit, pistons, joints)
    build_scope(optic_kit)
    build_pack(ammo_kit)
    body = gun_kit.to_object(f"SK_{TITLE}", joints=rotary_joints(joints))
    optic = optic_kit.to_object(f"SK_{TITLE}Optic")
    ammo = ammo_kit.to_object(f"SK_{TITLE}Ammo")
    tris = finish(body, rig, joints, TRI_BUDGET, states)
    optic_tris = finish_whole(optic, rig, OPTIC_BUDGET)
    ammo_tris = finish_whole(ammo, rig, AMMO_BUDGET)
    print(f"[{NAME}] the rifle with its optic: {tris + optic_tris} tris")

    gizmos = build_gizmos(rig, gizmo_specs(), ammo_frame=ammo_frame)
    shift_gun(rig, [body, optic, ammo], dy)
    pack_frame = export_pickup(ammo, dy)                   # (the pack as its own model)
    mounts = build_mounts(rig, pack_frame)
    export([rig, body, optic, *gizmos, *mounts], NAME)
    bpy.data.objects.remove(ammo)                   # (the weapon's files carry no pack mesh)
    constrain(rig, joints, pistons)
    write_rig_json(ammo_frame, joints, pistons, tris, ammo_tris, size, optic_tris, dy)
    add_mounts_json(pack_frame)
    build_preview_markers(rig, dy)

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
