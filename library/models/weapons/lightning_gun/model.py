"""Lightning gun - an arc rifle for KYLR, modelled, rigged and animated from script.

Run headless from the repo root:
    blender --background --factory-startup --python models/weapons/lightning_gun/model.py

Produces, next to this script:
    lightning_gun.blend             source scene (the gun, its cell pack and preview-only gizmo markers),
                                    opened by preview.py and animate.py
    lightning_gun.glb / .fbx        SK_LightningGun and SK_LightningGunAmmo skinned to RIG_LightningGun,
                                    with the actions idle, fire_start, fire, fire_end, fire_orb,
                                    mag_release and mag_insert, and the gizmos Muzzle, ArcTip1..ArcTip3,
                                    VentLeft, VentRight, LeftHandSocket, RightHandSocket
    lightning_gun_ammo.glb / .fbx   SM_LightningGunAmmo: the cell pack on its own, level, origin at its
                                    bottom centre, for the in-game ammo pickup
    lightning_gun_rig.json          joints, actuators, animations, gizmos, hand sockets, pack

Design: a rifle whose body is one shroud lofted from one machined section along the bore, every edge
a straight line down the gun: a titanium chassis (a flat keel, two big chamfers at each lower corner,
upright flanks) under a narrower military blue housing stepped in at the seam, its flanks leaning in
and its top corners chamfered. The forend runs straight (the support hand's palm flat on its lower
left chamfer), climbs one 45-degree ramp to the cowl's crest in front of the cell pack, lies under
the pack's bay and slopes straight down to the stock; the nose and the rear end are chamfered all
round. Each flank's chassis carries a finned heat-sink pocket (the vent), the housing's bolts under
the ledge and a recoil buffer (a lug on the barrel out through a slot in the forend drives a stainless steel
rod into a damper clamped to the flank), and on the ledge behind them the charge regulator's cap,
whose lit ring is the side's one light; a capacitor is clamped to each housing flank, a bronze line from
its front bending into the housing, the two linked at their backs by a black cable over the top behind the pack. The barrel runs in a blind bore inside the shroud and recoils into it. Ahead
of the shroud is the coil stack: a hexagonal end plate on the nose, three accelerator coils (hexagonal
titanium flanges, bronze windings), the tri-point collar and the muzzle block, carried by two black
rails on the hexagons' flat sides, bronze-lined and bolted into the plates; two black feeds leave bronze glands in the cowl's
ramp, run along the forend's top and drop onto the rear coil's winding. The barrel slides in all
their bores, the barrel's stainless steel emitter nozzle and its lit crystal on its end. Three military blue
prongs (the receptors) pivot on pins in the block's slotted lugs and close round the emitter; each is
opened by its own actuator, the barrel pinned between the cheeks of a slotted lobe of the collar, the
stainless steel rod in a yoke on the prong. The cell pack is an enclosed power module, pitched up toward the
back: a lofted titanium shell between black bumpers, riding the bay on two runners, a military blue
cover screwed on its top with a vent grille cut down into the shell and three lit stripes, rubber
grip ribs on its sides, a pull loop at its back, and on its rear bumper the lit charge gauge and a
test button facing the gunner. Its front bumper's nubs plug into bores in the cowl's rear face, and a
latch on the cowl's crest hooks that bumper. A pistol grip hangs from the belly behind a trigger
housing (an open guard, the pistol's small curved trigger); the stock is a metallic black octagonal
tube out of the shroud's rear into a black upright (a titanium lock collar at it), a black strut
under it, and a titanium buttpad the size of the upright's back face; a display console stands on
the rear slope facing the gunner.
Finish: military blue, matte titanium, matte black, stainless steel and bronze.

Every part is rigid and weighted 1.0 to one bone. The build fails if a part floats, a joint axis
misses its rotor or bearing, a slide leaves its guide, an actuator crosses its hinge or hits a part,
a palm would sink into a grip, the gun leaves its size envelope, or anything collides through any
animation frame or across the joints' ranges. Conventions: 1 unit = 1 m, Z up, the muzzle points -Y
(forward), the origin is on the gun's bottom plane (the grip's pommel) midway along it, so the
item table's and the weapon holder's WeaponMount takes it by its bottom. Rest pose: prongs closed, barrel home, pack in,
latch shut, trigger released.
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

NAME = "lightning_gun"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from material_uv import prepare_export
BLEND_PATH = HERE / f"{NAME}.blend"
RIG_JSON_PATH = HERE / f"{NAME}_rig.json"
TITLE = "".join(w.capitalize() for w in NAME.split("_"))  # LightningGun

SHARP_ANGLE = math.radians(40)
TRI_BUDGET = 5_000       # the gun (SK_LightningGun)
AMMO_BUDGET = 1_500      # the cell pack (SK_LightningGunAmmo / SM_LightningGunAmmo), on its own budget
FPS = 30

# --------------------------------------------------------------------------------------------
# === SPEC ===
# --------------------------------------------------------------------------------------------

FWD, BACK, UP, DOWN = (0, -1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)
SIDES = ("Left", "Right")              # the kit's mirror naming (nothing here is mirrored)

# Size: every weapon fits a 0.25 (wide) x 0.75 (long) x 0.35 m (high) envelope, its bottom on z = 0,
# centred along its length (check_envelope).
WEAPON_MAX = (0.25, 0.75, 0.35)

BORE_Z = 0.205                         # the bore axis
BELLY = 0.159                          # the belly the pistol grip hangs from

# The cell pack (bone Mag) lies on the shroud's bay, pitched up PACK_PITCH toward the back. Pack
# coordinates (x, s, h): s along its axis from its front, h up from its sled's underside (pk()).
PACK_PITCH = 7
PACK_O = (0.0, -0.092, 0.254)          # its sled's underside at its front, on the centre line
PACK_L = 0.150                         # its length along its axis (15 cm at most: user rule)
HOUSING = (0.0415, 0.034, (0.004, PACK_L))  # the power module: its bumpers' half-width and height, from / to (s)
SHELL = (0.040, 0.002, 0.032, 0.004, 0.009)  # its shell between them: half-width, bottom, top, bottom and top corner radii
CELL_X, CELL_H = 0.0225, 0.016         # the connector's two contact nubs, out of the front bumper at x +-CELL_X, height CELL_H
NUB = (0.0055, 0.016)                  # the nubs: radius, length out of the front bumper
MAG_TRAVEL = 0.015                     # the pack runs this far along its axis before it is free (nubs out)
LATCH_PIN = (-0.011, 0.045)            # the pack latch's pin over the cowl's crest (s, h)
LATCH_OPEN = 35

# The shroud: at each y one machined section round the bore (shroud_ring), every edge a straight line
# down the gun: a titanium chassis (a flat keel on the belly's line, two big chamfers at each lower
# corner, upright flanks up to SEAM_Z) under a narrower military blue housing (stepped in LEDGE at
# SEAM_Z, its flanks leaning in LEAN, a 45-degree chamfer TOP_CHAMFER at its top corners). The top runs
# straight along the forend, climbs one straight 45-degree ramp to the cowl's flat crest, drops to the
# pack's bay, lies under the pack and slopes straight down to the stock; the nose and the rear end are
# chamfered all round (END_CHAMFER).
SHROUD_Y = (-0.205, 0.215)             # its nose face (the coil stack's end plate) and its rear end (the stock's tube)
SHROUD_W = 0.038                       # the chassis' half-width
KEEL_ARC = (0.022, (270, 310, 360))    # the lower corners: two chords of a 22 mm arc (deg round it, 270 = straight down)
LEDGE, LEAN, TOP_CHAMFER = 0.003, 4, 0.010  # the housing's step in at the seam, its flanks' lean in (deg), its top chamfer
END_CHAMFER = 0.003                    # the nose's and the rear end's chamfer
SEAM_Z = 0.214                         # military blue above (the housing), titanium below (the chassis)
NOSE_BAND = -0.193                     # the titanium band at the nose
FOREND_TOP = 0.248                     # the forend's top
COWL = (-0.175, -0.130)                # the cowl's ramp from the forend's top straight up to its crest (y)
CREST_Z = 0.2905                       # the cowl's crest, over the socket face
REAR = (0.170, 0.263)                  # behind the pack the top slopes straight down from y REAR[0] to REAR[1] at the end
HEATSINK = ((-0.068, -0.014), (0.1855, 0.2085), 0.006, 6)  # the flanks' finned pockets: y, z, depth, fins
DISPLAY = (0.200, 15, (0.036, 0.034))  # the display console on the rear slope: y, lean toward the muzzle (deg), width, height
BUFFER = ((-0.1905, -0.1825), (-0.160, -0.122), 0.0055)  # the recoil buffers: the barrel's lug (y), the damper (y), its radius
REGULATOR = (0.150, SEAM_Z, 0.016)     # the charge regulators' caps, centred on the seam's ledge (user): y, z, radius
CAPACITOR = ((-0.050, 0.086), 0.2375, 0.0095, 0.0025)  # the capacitor on each housing flank: y, axis z, radius, its lines' radius
FEEDS = (70, 0.0022)                   # the coil feeds: the azimuth they drop square onto the rear coil at, cable radius
FASTENERS = (-0.100, 0.012, 0.072)     # the housing's bolts through the chassis' flanks under the ledge (y)


# Barrel (bone Barrel): slides in the shroud's blind bore and the muzzle block's (a sliding fit, same
# 12-sided phase), recoiling back into the shroud.
BARREL_R, BARREL_BORE = 0.0105, 0.0065
GUIDE_R = BARREL_R + 0.00005
RECOIL, RECOIL_F = 0.01, (15, 15)      # the barrel's recoil as it fires: 1 cm back in 0.5 s, home in 0.5 s
BARREL_REAR = -0.120                   # its rear end at rest, deep in the shroud
BORE_FLOOR = BARREL_REAR + RECOIL + 0.003   # the blind bore's floor, 3 mm behind a recoiled barrel
EMIT = (-0.356, -0.336)                # the emitter nozzle on its front: its face, its rear (12 mm ahead of the block)
# The rail section ahead of the shroud: a hexagonal end plate on the nose, three accelerator coils
# (hexagonal titanium flanges, bronze windings), the collar and the muzzle block, carried by two black
# rails bearing on the hexagons' flat sides (bronze-lined, bolted into the plates).
END_PLATE = (-0.2045, -0.2105)         # the end plate (y), 0.5 mm into the nose
COILS = ((-0.231, -0.214), (-0.252, -0.235), (-0.273, -0.256))  # the accelerator coils round the barrel (y)
COIL_R, FLANGE, WINDING = 0.040, 0.0035, 0.026  # a flange's corner radius (hexagon), its thickness, the winding's radius
RAIL = (COIL_R * math.cos(math.pi / 6), 0.005, 0.007)  # the rails: inner x (on the hexagons' flats), thickness, half-height
BLOCK = (-0.324, -0.303)               # the muzzle block (y), on the rails' front ends

# Prongs (the receptors): three, round the emitter, each on a pin across a slotted lug of the muzzle
# block (radius PIN[0], y PIN[1]); + opens a prong (its tip outward). Each is driven by an actuator:
# barrel pinned in a slotted lobe of the tri-point collar (radius ACT_U, y ACT_A_Y), rod pinned in a
# yoke on the prong.
PRONG_AZ = (90, 210, 330)
PRONGS = [f"Prong{i + 1}" for i in range(3)]
PIN = (0.032, -0.3195)
PRONG_BEAM, PRONG_OPEN = 10, 18        # the prongs' opening firing the beam, and firing the orb (its limit)
ACT_R = 0.0035                         # the actuators' barrel radius
ACT_B = (0.012, 0.020)                # the rod's pin on the prong's yoke from the prong's pin: forward, outward
ACT_U = PIN[0] + ACT_B[1]              # the actuators' line from the bore axis (0.052), clear over the shroud
ACT_A_Y = PIN[1] - ACT_B[0] + 0.0485                       # the barrel's pin, in the collar's lobe (y)
COLLAR = (ACT_A_Y - 0.006, ACT_A_Y + 0.006)  # the tri-point collar round the barrel, the rails through it (y)

# Hands: Tensor's hand bone frame (X = knuckle line, Y = wrist to knuckles, Z = out of the palm),
# its palm 0.094 long from 1 cm past the wrist, 0.09 wide, its face 0.016 off the bone line.
PALM = (0.010, 0.104, 0.045, 0.016)    # palm along Y (from, to), half-width along X, half-thickness
GRIP_ALONG = {"Left": 0.072, "Right": 0.070}  # the grip line from the wrist along Y
GRIP_RAKE = 15                         # the pistol grip's rake (deg)
GRIP_G = (0.0, 0.1464, 0.0865)         # the firing hand's centre on the pistol grip's axis, its web close
                                       # under the belly (raised 14 mm up the raked axis: user)
GRIP_HALF = (0.014, 0.023)             # pistol grip half-width (x) and half-depth (fore-aft)
WEB = (0.012, 0.030, 0.040, 0.062)     # the web relief: the backstrap cut to this depth (local y) from z 0.030
                                       # (full by 0.040) to 0.062 up the grip from the hand's centre, where the
                                       # firing thumb's first joints wrap behind the grip onto its far side
TRIGGER_REACH = 0.048                  # trigger face ahead of the grip axis, at the index finger's height
# The trigger: the pistol's small curved lever (user rule: every gun's), placed as on the pistol from the
# grip's hand centre; its block under the belly, the open guard round it, its bottom bar stopping short
# of the curled fingers (they lie flush along the grip's front, so a bar joining it would pass through one).
TRIGGER_PIVOT = (0.0, GRIP_G[1] - 0.0595, GRIP_G[2] + 0.0515)
TRIGGER_OUTLINE = [(-0.0040, -0.0025), (0.0015, -0.0180), (0.0048, -0.0290), (0.0060, -0.0370), (0.0048, -0.0418),
                   (0.0080, -0.0428), (0.0105, -0.0360), (0.0080, -0.0180), (0.0035, -0.0025)]
# (the lever's face concave, leaning forward from the pivot, curving back under the index finger, its tip
# turned forward: user, the old lever's convex face and back-hooked tip looked the wrong way round)
TRIGGER_PULL = 12
GUARD_FRONT = (TRIGGER_PIVOT[1] - 0.032, TRIGGER_PIVOT[1] - 0.024)  # the guard's front bar (y)
GUARD_BOTTOM = (GRIP_G[2] - 0.005, 0.007, GRIP_G[1] - 0.060)  # its bottom bar: underside, thickness, rear end
TRIGGER_BLOCK = ((GUARD_FRONT[1], GRIP_G[1] - 0.042), TRIGGER_PIVOT[2] - 0.0075)  # the trigger's block: y, its bottom
TRIGGER_HALF = 0.0095                  # the trigger housing's half-width
# The support hand holds the forend from below at y LSUP_Y, the palm up but canted LSUP_ROLL toward the
# gun's right, onto the forend's lower left corner (roll 0 is flat on the bottom), the fingers LSUP_TURN
# from straight ahead toward the right, wrapping up the far side: the FPS pose, the gun shouldered.
# With the fingers 50 deg across and the grip line
# 72 mm from the wrist (GRIP_ALONG) the wrist housing (46 mm round) sits beside the forend, not in it.
LSUP_Y, LSUP_ROLL, LSUP_TURN = -0.040, 20, 50
# The grip pose for Tensor's hands on the sockets (exported; animations/retarget.py closes his hands to it):
# each finger's curl (proximal; intermediate x1.1, distal x0.8, as Tensor's finger_pose) and the
# thumb (metacarpal x, z; proximal = distal curl).
GRIP_POSE = {"Left": ({"Index": 10, "Middle": 19, "Ring": 24, "Little": 27}, (24, 25, 16)),  # open, along the forend
             "Right": ({"Index": 36, "Middle": 65, "Ring": 65, "Little": 52}, (42, -25, 50))}  # thumb round the grip
# The support hand's grip on the ammo pack for a reload (user: every hand placement is a socket the animation plugs
# into, exported as AmmoHandSocket on the Mag bone; a wide grip, not a C cup): the palm flat on the pack's outer end
# (the face away from the gun), the fingers spread across it and over its far (right) edge, the thumb up its front;
# centred along the pack.
AMMO_ACROSS = (-1.0, 0.0, 0.0)   # the fingers' way across the pack (the left hand reaches over to its right edge)
AMMO_OUT = (0.0, -math.sin(math.radians(PACK_PITCH)), math.cos(math.radians(PACK_PITCH)))   # its outer end (the way it leaves the gun)
AMMO_GRIP = 0.004                # the knuckles short of the pack's far edge (the fingers wrap over it)
AMMO_GRIP_POSE = ({"Index": 45, "Middle": 50, "Ring": 50, "Little": 45}, (25, 40, 15))  # spread, the thumb out

# Actions (30 fps): idle (looped) lets the prongs breathe on their actuators; fire_start pulls the
# trigger and opens them to the beam; fire (looped) holds them, flickering, and the barrel pulses back
# 1 cm and home each second; fire_end closes them; fire_orb (the secondary fire, from idle) snaps them
# wide and the barrel recoils.
IDLE_F, IDLE_BREATH = 60, 3.0          # idle's loop, the prongs' breath (deg)
START_F, END_F = 8, 10
FLICKER = (1.2, (3, 4, 5))             # fire's flicker: amplitude (deg), each prong's cycles per loop
ORB_F = 3                              # fire_orb: the orb leaves the emitter
ORB_END = ORB_F + sum(RECOIL_F)        # the barrel is home again on fire_orb's last frame

BARREL = "Barrel"
TRIGGER, MAG, LATCH = "Trigger", "Mag", "MagLatch"

# slot: (base colour, metallic, roughness, emission strength[, alpha])
MATERIALS = {
    "M_Primary": ((0.069, 0.110, 0.162), 0.25, 0.55, 0.0),   # military blue: the shroud's upper part, prongs, cells
    "M_Secondary": ((0.018, 0.018, 0.02), 0.2, 0.72, 0.0),   # matte black: grip, stock, actuators, latch
    "M_Frame": ((0.29, 0.29, 0.30), 1.0, 0.5, 0.0),          # matte titanium: lower shroud, barrel, coils, collar, block
    "M_Joint": ((0.55, 0.55, 0.54), 1.0, 0.2, 0.0),         # stainless steel: pins, rods, emitter, cell caps
    "M_Emissive": ((0.35, 0.72, 1.0), 0.0, 0.4, 6.0),        # emitter crystal, cell cores, charge rings, display
    "M_Bronze": ((0.72, 0.46, 0.2), 1.0, 0.25, 0.0),         # coil windings, rail linings, contacts, window rings
    "M_Glass": ((0.55, 0.75, 0.8), 0.0, 0.03, 0.0, 0.25),    # the cells' windows, the display cover
    "M_Metal": ((0.035, 0.036, 0.04), 1.0, 0.32, 0.0),       # metallic black: the pack's sled and bands, the prongs' yokes
}
SLOTS = list(MATERIALS)
PRI, SEC, FRM, JNT, EMI, BRZ, GLS, MTL = SLOTS


def az_point(r, az, y, cx=0.0, cz=BORE_Z):
    """Point at radius r, azimuth az (deg in the XZ plane, 0 = +X, 90 = up) round (cx, cz), at y."""
    return Vector((cx + r * math.cos(math.radians(az)), y, cz + r * math.sin(math.radians(az))))


def radial(az):
    return Vector((math.cos(math.radians(az)), 0.0, math.sin(math.radians(az))))


def tangent(az):
    return Vector((-math.sin(math.radians(az)), 0.0, math.cos(math.radians(az))))


_P = math.radians(PACK_PITCH)
PACK_D = Vector((0.0, math.cos(_P), math.sin(_P)))   # the pack's axis: back and up
PACK_N = Vector((0.0, -math.sin(_P), math.cos(_P)))  # square to it, up


def pk(x, s, h):
    """A point in pack coordinates: x across, s along its axis from its front, h up from its sled."""
    return Vector(PACK_O) + Vector((x, 0, 0)) + PACK_D * s + PACK_N * h


def bay_z(y):
    """The pack's bay floor at y: 0.5 mm under the sled, pitched with it."""
    return PACK_O[2] + math.tan(_P) * (y - PACK_O[1]) - 0.0005 / math.cos(_P)


def shroud_top(y):
    """The shroud's top at y: straight lines between the stations."""
    def lerp(y0, v0, y1, v1):
        return v0 + (v1 - v0) * (y - y0) / (y1 - y0)
    if y <= COWL[0]:
        return FOREND_TOP
    if y <= COWL[1]:
        return lerp(COWL[0], FOREND_TOP, COWL[1], CREST_Z)          # the ramp, one 45-degree plane
    if y <= -0.088:
        return CREST_Z
    if y <= -0.078:
        return lerp(-0.088, CREST_Z, -0.078, bay_z(-0.078) + 0.003)  # the cowl's rear face, the cells' sockets in it
    if y <= REAR[0]:
        return bay_z(y) + 0.003                                     # cut flat to the bay under the pack
    return lerp(REAR[0], bay_z(REAR[0]) + 0.003, SHROUD_Y[1], REAR[1])


SHROUD_STATIONS = [SHROUD_Y[0], SHROUD_Y[0] + END_CHAMFER, NOSE_BAND, COWL[0], COWL[1], -0.088, -0.078, REAR[0],
                   SHROUD_Y[1] - END_CHAMFER, SHROUD_Y[1]]


def keel_points():
    """The chassis' lower right-hand corner (+x): the chords' ends round KEEL_ARC, from the keel up."""
    rb, angles = KEEL_ARC
    cx, cz = SHROUD_W - rb, BELLY + rb
    return [(cx + rb * math.cos(math.radians(a)), cz + rb * math.sin(math.radians(a))) for a in angles]


def housing_x(z):
    """The housing's flank at height z (+x side): stepped in LEDGE at the seam, leaning in LEAN."""
    return SHROUD_W - LEDGE - (z - SEAM_Z) * math.tan(math.radians(LEAN))


def shroud_ring(y):
    """The shroud's section at y as a ring of points, counter-clockwise from the +x flank's seam: the
    ledge, the housing's leaning flank, its top chamfer and flat top, down the far side, the chassis'
    upright flank, its two keel chamfers and flat keel (every station has the same points, so every
    edge runs as a straight line). The nose and rear end stations are the section inset END_CHAMFER."""
    zt, W = shroud_top(y), SHROUD_W
    xt = housing_x(zt - TOP_CHAMFER)
    right = [(W, SEAM_Z), (W - LEDGE, SEAM_Z), (xt, zt - TOP_CHAMFER), (xt - TOP_CHAMFER, zt)]
    keel = keel_points()                                            # (W - rb, BELLY) .. (W, BELLY + rb)
    pts = right + [(-x, z) for x, z in reversed(right)] + [(-x, z) for x, z in reversed(keel)] + keel
    if min(abs(y - SHROUD_Y[0]), abs(y - SHROUD_Y[1])) < 1e-9:
        zc, h = (zt + BELLY) / 2, (zt - BELLY) / 2
        sx, sz = (W - END_CHAMFER) / W, (h - END_CHAMFER) / h
        pts = [(x * sx, zc + (z - zc) * sz) for x, z in pts]
    return [Vector((x, y, z)) for x, z in pts]


def forend_contact(roll):
    """The middle of the keel chamfer on the forend's lower left corner whose outward normal is
    (sin roll, 0, -cos roll), and that normal (the support hand's palm lies flat on it)."""
    pts = keel_points()
    for (x0, z0), (x1, z1), (a0, a1) in zip(pts, pts[1:], zip(KEEL_ARC[1], KEEL_ARC[1][1:])):
        if abs((a0 + a1) / 2 - 270 - roll) < 1e-6:
            n = Vector((math.sin(math.radians(roll)), 0.0, -math.cos(math.radians(roll))))
            return Vector(((x0 + x1) / 2, 0.0, (z0 + z1) / 2)), n
    raise ValueError(f"no keel chamfer faces {roll} deg")


def prong_pin(az):
    return az_point(PIN[0], az, PIN[1])


def prong_axis(az):
    """A prong's pin: tangential, so that + turns the prong's tip (forward) outward."""
    return Vector(FWD).cross(radial(az))


def prong_point(az, a, u):
    """A point in a prong's radial plane: a forward of its pin, u out from the bore axis."""
    return Vector((0.0, PIN[1] - a, BORE_Z)) + radial(az) * u


def act_a(az):
    return az_point(ACT_U, az, ACT_A_Y)


def act_b(az):
    return prong_point(az, ACT_B[0], ACT_U)


def grip_axes():
    """The pistol grip's frame: g up its axis (raked back at the bottom), f forward square to it."""
    s, c = math.sin(math.radians(GRIP_RAKE)), math.cos(math.radians(GRIP_RAKE))
    return Vector((0, -s, c)), Vector((0, -c, -s))


def hand_frame(side):
    """Tensor's hand bone frame gripping each handle: (wrist pivot, X, Y, Z). Z points out of the
    palm onto the grip, Y from the wrist to the knuckles, X = Y x Z along the knuckle line (the left
    thumb on -X, the right on +X). The grip line runs across the palm GRIP_ALONG from the wrist, the
    grip's surface on the palm's face."""
    if side == "Left":   # support hand: palm tangent to the forend from below and the left
        t = math.radians(LSUP_TURN)
        p, n = forend_contact(LSUP_ROLL)
        z = -n
        y0 = Vector((-math.sin(t), -math.cos(t), 0.0))
        y = (y0 - z * y0.dot(z)).normalized()
        grip, face = Vector((p.x, LSUP_Y, p.z)), 0.0
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


def recoil_keys(f0, f_end):
    """A barrel's recoil on every frame from f0: RECOIL back over RECOIL_F[0] frames, fast then
    slowing (1 - (1 - u)^3), and home again over RECOIL_F[1] (smoothstep); at rest before and after."""
    back, home = RECOIL_F
    keys = [(f, 0.0) for f in range(0, f0)]
    keys += [(f0 + i, RECOIL * (1 - (1 - i / back) ** 3)) for i in range(back)]
    keys += [(f0 + back + i, RECOIL * (1 - (3 - 2 * i / home) * (i / home) ** 2)) for i in range(home + 1)]
    return keys + [(f, 0.0) for f in range(f0 + back + home + 1, f_end + 1)]


# Joints: (name, parent, kind, pivot, axis, bone direction, limits), world space. The barrel recoils
# back into the shroud, each prong opens on its pin, the trigger pulls back, the latch lifts and the
# pack slides back and up its axis (positive = out).
JOINT_SPECS = [
    ("Root", None, "fixed", (0, 0, 0), UP, UP, None),
    (BARREL, "Root", "slide", (0, BARREL_REAR, BORE_Z), BACK, None, (0, RECOIL)),
    *[(p, "Root", "hinge", tuple(prong_pin(az)), tuple(prong_axis(az)), FWD, (0, PRONG_OPEN))
      for p, az in zip(PRONGS, PRONG_AZ)],
    (TRIGGER, "Root", "hinge", TRIGGER_PIVOT, (1, 0, 0), DOWN, (0, TRIGGER_PULL)),
    (MAG, "Root", "slide", tuple(pk(0, PACK_L / 2, 0)), tuple(PACK_D), None, (0, MAG_TRAVEL)),
    (LATCH, "Root", "hinge", tuple(pk(0, *LATCH_PIN)), (1, 0, 0), tuple(PACK_D), (0, LATCH_OPEN)),
]
# The prong actuators: (name, barrel's bone, its pin, rod's bone, its pin, barrel radius).
PISTON_SPECS = [(f"{p}Act", "Root", tuple(act_a(az)), p, tuple(act_b(az)), ACT_R) for p, az in zip(PRONGS, PRONG_AZ)]


def prongs(keys):
    return {p: keys for p in PRONGS}


ANIMATIONS = {
    "idle": (True, "LINEAR", prongs([(f, IDLE_BREATH * (1 - math.cos(2 * math.pi * f / IDLE_F)) / 2)
                                     for f in range(IDLE_F + 1)])),
    "fire_start": (False, "LINEAR", {
        TRIGGER: eased([(0, 0), (3, TRIGGER_PULL), (START_F, TRIGGER_PULL)]),
        **prongs(eased([(0, 0), (6, PRONG_BEAM), (START_F, PRONG_BEAM)]))}),
    "fire": (True, "LINEAR", {
        TRIGGER: [(0, TRIGGER_PULL), (30, TRIGGER_PULL)],
        **{p: [(f, PRONG_BEAM + FLICKER[0] * math.sin(2 * math.pi * n * f / 30)) for f in range(31)]
           for p, n in zip(PRONGS, FLICKER[1])},
        BARREL: recoil_keys(0, 30)}),
    "fire_end": (False, "LINEAR", {
        TRIGGER: eased([(0, TRIGGER_PULL), (4, 0), (END_F, 0)]),
        **prongs(eased([(0, PRONG_BEAM), (END_F, 0)]))}),
    "fire_orb": (False, "LINEAR", {
        TRIGGER: eased([(0, 0), (2, TRIGGER_PULL), (10, TRIGGER_PULL), (14, 0), (ORB_END, 0)]),
        **prongs(eased([(0, 0), (ORB_F, PRONG_OPEN), (12, PRONG_OPEN), (24, 0), (ORB_END, 0)])),
        BARREL: recoil_keys(ORB_F, ORB_END)}),
    "mag_release": (False, "BEZIER", {LATCH: [(0, 0), (5, LATCH_OPEN)], MAG: [(0, 0), (5, 0), (12, MAG_TRAVEL)]}),
    "mag_insert": (False, "BEZIER", {MAG: [(0, MAG_TRAVEL), (8, 0)], LATCH: [(0, LATCH_OPEN), (8, LATCH_OPEN), (12, 0)]}),
}
PREVIEW_STATES = {
    "beam": {**prongs(PRONG_BEAM), TRIGGER: TRIGGER_PULL, BARREL: RECOIL},
    "orb": {**prongs(PRONG_OPEN), TRIGGER: TRIGGER_PULL, BARREL: 0.6 * RECOIL},
    "mag_out": {LATCH: LATCH_OPEN, MAG: MAG_TRAVEL},
}
PREVIEW_VIEWS = {"beam": ["front_left", "front"], "orb": ["front_left", "left"], "mag_out": ["front_left", "rear_right"]}
FK_TEST_STATE = {BARREL: 0.6 * RECOIL, PRONGS[0]: 5, PRONGS[1]: 12, PRONGS[2]: PRONG_OPEN, TRIGGER: 6, MAG: 0.01,
                 LATCH: 20}
SHOWCASE = ["idle", "fire_start", "fire", "fire", "fire_end", "idle", "fire_orb", "idle", "mag_release", "mag_insert"]
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
# Parts: the shroud
# --------------------------------------------------------------------------------------------

def shroud_mat(f):
    """Titanium on the nose band, the chassis and its ledge; military blue on the housing above it."""
    c = f.calc_center_median()
    return FRM if c.y < NOSE_BAND - 1e-6 or c.z < SEAM_Z + 1e-5 else PRI


def heatsink_pocket(sx):
    """A flank's heat-sink pocket, cut HEATSINK's depth into the chassis' flank (a shroud box cut)."""
    (y0, y1), (z0, z1), depth, _ = HEATSINK
    return ((sx * (SHROUD_W + 0.005 - depth / 2), (y0 + y1) / 2, (z0 + z1) / 2), (depth + 0.01, y1 - y0, z1 - z0))


def display_frame():
    """The display console on the rear slope: its foot on the slope's centre line, u up it (leaning toward
    the muzzle), n out of its face (up and back, toward the gunner's eye)."""
    y, lean, _ = DISPLAY
    a = math.radians(lean)
    return Vector((0, y, shroud_top(y))), Vector((0, -math.sin(a), math.cos(a))), Vector((0, math.cos(a), math.sin(a)))


def build_display(k):
    """The display console standing on the rear slope, facing the gunner: a metallic black plinth sunk
    into the slope, a black housing on it, the lit screen under glass on its face."""
    b, u, n = display_frame()
    w, h = DISPLAY[2]
    k.obox(b - u * 0.005, b + u * 0.007, w + 0.004, 0.016, n, "Root", MTL)                     # plinth
    k.obox(b - u * 0.003, b + u * h, w, 0.007, n, "Root", SEC)                                  # housing
    k.obox(b + u * 0.009 + n * 0.0038, b + u * (h - 0.003) + n * 0.0038, w - 0.006, 0.001, n, "Root", EMI)  # screen
    k.obox(b + u * 0.0088 + n * 0.0046, b + u * (h - 0.0028) + n * 0.0046, w - 0.0058, 0.0006, n, "Root", GLS)  # glass


def build_flank_details(k):
    """What each flank carries, mirrored: the heat sink (metallic black fins standing in the chassis'
    pocket, the side's vent), the housing's bolts through the chassis under the ledge, the recoil buffer
    (the barrel's lug out through the forend's slot, its stainless steel rod into a black damper clamped to the
    flank) and, centred on the seam's ledge, the charge regulator's cap (a titanium boss seated across the step, a
    bronze bearing ring, a stainless steel hub with a hex nut, and between them the lit ring: the side's one
    light); the capacitor on the housing's flank (a metallic black can clamped to it, bronze terminals, a
    bronze line from its front bending into the housing), the two capacitors' backs linked by a black
    cable over the housing's top behind the pack's bay (every bend rounded)."""
    (l0, l1), (d0, d1), dr = BUFFER
    (h0, h1), (z0, z1), depth, fins = HEATSINK
    W = SHROUD_W
    for sx in (1, -1):
        X = lambda d: sx * (W + d)
        pitch = (h1 - h0) / fins
        for i in range(fins):                                                            # heat-sink fins
            y = h0 + pitch * (i + 0.5)
            x0, x1 = sorted((X(-depth - 0.0005), X(-0.0008)))
            k.span((x0, y - 0.0008, z0 + 0.001), (x1, y + 0.0008, z1 - 0.001), "Root", MTL)
        for y in FASTENERS:                                                              # housing bolts
            bolt(k, (X(0), y, SEAM_Z - 0.0045), (sx, 0, 0), "Root", r=0.0024, head=0.0014)
        xd = X(dr - 0.0005)                                                             # the damper's axis
        k.cyl((xd, d0, BORE_Z), (xd, d1, BORE_Z), dr, "Root", SEC, segs=10)            # damper
        k.cyl((xd, d0 - 0.002, BORE_Z), (xd, d0 + 0.004, BORE_Z), dr + 0.0009, "Root", FRM, segs=10)  # its gland
        k.cyl((xd, d1 - 0.004, BORE_Z), (xd, d1 + 0.001, BORE_Z), dr + 0.0006, "Root", FRM, segs=10)  # its end cap
        for yc in (d0 + 0.012, d1 - 0.010):                                              # clamps to the flank
            x0, x1 = sorted((X(-0.001), X(2 * dr + 0.0008)))
            k.span((x0, yc - 0.003, BORE_Z - dr - 0.0012), (x1, yc + 0.003, BORE_Z + dr + 0.0012), "Root", FRM)
        x0, x1 = sorted((sx * 0.009, X(2 * dr + 0.0005)))
        k.span((x0, l0, BORE_Z - 0.0025), (x1, l1, BORE_Z + 0.0025), BARREL, FRM)       # the barrel's lug
        k.cyl((xd, l1 - 0.001, BORE_Z), (xd, d0 + 0.012, BORE_Z), 0.0022, BARREL, JNT, segs=6)  # its rod
        ry, rz, rr = REGULATOR
        a = math.radians(LEAN)
        n, base = Vector((sx, 0, 0)), Vector((sx * W, ry, rz))
        at = lambda d: base + n * d
        k.cyl(at(housing_x(rz + rr) - 0.001 - W), at(0.0045), rr, "Root", FRM, segs=16)  # boss, seated across the ledge
        k.cyl(at(0.0045), at(0.0065), rr - 0.0035, "Root", BRZ, segs=14)                 # bearing ring
        k.cyl(at(0.0064), at(0.0072), rr - 0.0058, "Root", EMI, segs=12)                 # lit ring
        k.cyl(at(0.0066), at(0.0098), rr - 0.009, "Root", JNT, segs=12)                  # hub
        bolt(k, at(0.0098), n, "Root", r=0.0032, head=0.0018)                            # its hex nut
        (c0, c1), cz, cr, lr = CAPACITOR
        cx = sx * (housing_x(cz) + (cr - 0.0008) / math.cos(a))                          # its axis, the can on the flank
        k.cyl((cx, c0, cz), (cx, c1, cz), cr, "Root", MTL, segs=12)                      # capacitor can
        for y0, y1 in ((c0 - 0.003, c0 + 0.0005), (c1 - 0.0005, c1 + 0.003)):
            k.cyl((cx, y0, cz), (cx, y1, cz), 0.0068, "Root", BRZ, segs=8)               # its terminals
        for yc in (c0 + 0.016, c1 - 0.016):                                              # its clamps to the flank
            x0, x1 = sorted((sx * (housing_x(cz + cr + 0.001) - 0.001), cx + sx * (cr + 0.0012)))
            k.span((x0, yc - 0.003, cz - cr - 0.0012), (x1, yc + 0.003, cz + cr + 0.0012), "Root", FRM)
        yf = c0 - 0.003 - 0.011                                                          # its front: a bend into the housing
        k.tube(fillet([(cx, c0 - 0.003, cz), (cx, yf, cz), (sx * housing_x(cz), yf, cz)], 0.005), lr, "Root", BRZ,
               sides=6)
    (c0, c1), cz, cr, lr = CAPACITOR
    cx = housing_x(cz) + (cr - 0.0008) / math.cos(math.radians(LEAN))
    yx = c1 + 0.003 + 0.011                                                              # the link behind the pack's bay
    zx = shroud_top(yx) + lr + 0.0005
    k.tube(fillet([(cx, c1 + 0.003, cz), (cx, yx, cz), (cx, yx, zx), (-cx, yx, zx), (-cx, yx, cz), (-cx, c1 + 0.003, cz)],
                  0.006), lr, "Root", SEC, sides=6)


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


def build_feeds(k):
    """The coil feeds: two black cables out of bronze glands sunk in the cowl's ramp (each cable's nut on
    its gland's face), resting along the forend's top, over the end plate and down square onto the rear
    coil's winding between its flanges."""
    az, r = FEEDS
    z = FOREND_TOP + r + 0.0002                                                        # resting on the top
    ya = sum(COILS[0]) / 2                                                               # mid-winding
    for sx in (1, -1):
        a = az if sx > 0 else 180 - az
        drop = radial(a)
        top = Vector((0, ya, BORE_Z)) + drop * ((z - BORE_Z) / drop.z)                   # where it turns down
        x = top.x
        k.cyl((x, -0.163, z), (x, -0.1805, z), 0.0048, "Root", BRZ, segs=6)               # gland
        k.tube([(x, -0.1805, z), tuple(top), tuple(az_point(WINDING, a, ya))], r, "Root", SEC, sides=6)


def build_shroud(k):
    """The shroud: lofted from its sections, military blue over titanium, then machined: the barrel's blind
    bore, the pack's bay under the sled and the cells' socket bores in the cowl's rear face, the
    heat-sink pockets, the recoil buffers' slots; the display console, the flanks' details and the coil
    feeds on it."""
    cuts = [bore_cut(SHROUD_Y[0] - 0.01, BORE_FLOOR)]
    cuts += [(pk(sx * CELL_X, -0.016, CELL_H), pk(sx * CELL_X, 0.01, CELL_H), NUB[0] + 0.0006, 10) for sx in (1, -1)]
    (l0, l1), _, _ = BUFFER
    boxes = [((sx * 0.03, (l0 + l1 + RECOIL) / 2, BORE_Z), (0.04, l1 - l0 + RECOIL + 0.0015, 0.0065)) for sx in (1, -1)]  # buffer slots
    boxes += [heatsink_pocket(sx) for sx in (1, -1)]
    bay_end = PACK_L + MAG_TRAVEL + 0.004                                                # the pack slides out this far
    bay = (pack_side([(-0.0005, -0.0005), (bay_end, -0.0005), (bay_end, 0.3), (-0.0005, 0.3)]), (1, 0, 0), 0.3)
    carve(k, loft(SHROUD_STATIONS, shroud_ring), "Root", PRI, cuts=cuts, boxes=boxes, subtract=[bay],
          material=shroud_mat)
    build_display(k)
    build_flank_details(k)
    build_feeds(k)


def hexagon(r):
    """A hexagon's corners round the bore (x, z), one on each prong's azimuth, its flat sides square to x."""
    return [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in range(30, 360, 60)]


def star(lobes, u0):
    """A plate's outline round the bore: lobes (az, out to, half-width) joined across their roots at u0,
    counter-clockwise (u0 far enough out that neighbouring lobes' roots do not cross)."""
    lobes = sorted(lobes)
    for (a0, _, h0), (a1, _, h1) in zip(lobes, lobes[1:] + [(lobes[0][0] + 360, 0, lobes[0][2])]):
        if math.degrees(math.atan2(h0, u0) + math.atan2(h1, u0)) >= a1 - a0:
            raise ValueError(f"star: the lobes at {a0} and {a1 % 360} deg cross at their roots (u0 {u0})")
    pts = []
    for az, u1, hw in sorted(lobes):
        pts += lobe(az, u0, u1, hw)
    return pts


def build_rails(k):
    """The rail section's frame: the hexagonal titanium end plate on the shroud's nose (the barrel through
    it) and the two black rails from it to the muzzle block (sunk 5 mm into it), bearing on the end
    plate's, the coils' and the collar's flat sides, slotted between the collar and the block, bronze
    conductor strips on their inner faces between the plates, bolted into the end plate, each coil's
    rear flange and the collar."""
    y0, y1 = END_PLATE
    k.plate(xz_poly(hexagon(COIL_R), (y0 + y1) / 2), y1 - y0, (0, 1, 0), "Root", FRM,
            cuts=[bore_cut(y0 + 0.01, y1 - 0.01)])
    xi, th, hh = RAIL
    stops = sorted([BLOCK, COLLAR, *COILS, (END_PLATE[1], END_PLATE[0])])
    gaps = [(a[1], b[0]) for a, b in zip(stops, stops[1:])]
    for sx in (1, -1):
        xc = sx * (xi + th / 2)
        slots = [((xc, (a + b) / 2, BORE_Z), (0.01, b - a - 0.004, 0.006)) for a, b in gaps if b - a > 0.007]
        k.plate([(xc, BLOCK[1] - 0.005, BORE_Z - hh), (xc, END_PLATE[0], BORE_Z - hh), (xc, END_PLATE[0], BORE_Z + hh),
                 (xc, BLOCK[1] - 0.005, BORE_Z + hh)], th, (1, 0, 0), "Root", SEC, boxes=slots, bevel=0.0008)
        for a, b in gaps:
            x0, x1 = sorted((sx * (xi - 0.0008), sx * (xi + 0.0002)))
            k.span((x0, a + 0.0005, BORE_Z - 0.0045), (x1, b - 0.0005, BORE_Z + 0.0045), "Root", BRZ)
        for y in [sum(END_PLATE) / 2] + [c[1] - FLANGE / 2 for c in COILS] + [sum(COLLAR) / 2]:
            bolt(k, (sx * (xi + th), y, BORE_Z), (sx, 0, 0), "Root", r=0.0022, head=0.0016)


def build_coils(k):
    """The accelerator coils: two hexagonal titanium flanges each, the rails on their flat sides, a
    bronze winding between them (its bore 0.5 mm clear of the barrel); the barrel slides in the flanges' bores."""
    hexa = hexagon(COIL_R)
    for y0, y1 in COILS:
        for f0, f1 in ((y0, y0 + FLANGE), (y1 - FLANGE, y1)):
            k.plate(xz_poly(hexa, (f0 + f1) / 2), FLANGE, (0, 1, 0), "Root", FRM, cuts=[bore_cut(f0 - 0.01, f1 + 0.01)])
        pipe(k, (0, y0 + FLANGE - 0.0005, BORE_Z), (0, y1 - FLANGE + 0.0005, BORE_Z), WINDING, GUIDE_R + 0.0005, "Root", BRZ,
             segs=12)


def build_collar(k):
    """The tri-point collar: a titanium spider round the barrel (its bore a sliding fit), three slotted lobes
    (each the two cheeks of an actuator's barrel eye) and the rails' ears, the rails through them."""
    lobes = [(az, ACT_U + 0.008, 0.0075) for az in PRONG_AZ] + [(az, RAIL[0] + RAIL[1] + 0.0015, RAIL[2] + 0.0025)
                                                                 for az in (0, 180)]
    y0, y1 = COLLAR
    slots = [lug_slot(az, ACT_U - 0.0075, ACT_U + 0.02, ACT_R * 1.2 + 0.0006, y0 - 0.01, y1 + 0.01) for az in PRONG_AZ]
    k.plate(xz_poly(star(lobes, 0.034), (y0 + y1) / 2), y1 - y0, (0, 1, 0), "Root", FRM,
            cuts=[bore_cut(y0 - 0.01, y1 + 0.01)], subtract=slots)


def build_grip(k):
    """The pistol grip, raked back, machined in its own frame (z up its axis, -y forward): finger
    grooves on its front, a pommel standing on the bottom plane, a beavertail over the hand's web and a web relief under it,
    its top sunk 5 mm into the belly; the trigger housing ahead of it (the open guard, the small
    curved trigger's block)."""
    g, f = grip_axes()
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
        k.plate([(0, y, z) for y, z in prof], 2 * hx, (1, 0, 0), "Root", SEC,
                intersect=[([(x, z, 0) for x, _, z in octagon_xz(hx, -D - 0.02, D + 0.02, 0.005, 0.005, 0)], (0, 0, 1), 1.0)],
                cuts=grooves)
    build_trigger_housing(k)


def build_trigger_housing(k):
    """The trigger housing (matte black), one plate hanging from the belly ahead of the grip: the open
    trigger guard (its front bar, its bottom bar ending short of the curled fingers) and the trigger's
    block and slot, its back into the grip's front; the trigger's stainless steel pin."""
    g0, g1 = GUARD_FRONT
    zb, th, ye = GUARD_BOTTOM
    zt = BELLY + 0.005
    (b0, b1), bz = TRIGGER_BLOCK
    pts = [(g0, zt), (g0, zb), (ye, zb), (ye, zb + th), (g1 + 0.010, zb + th), (g1, zb + th + 0.004), (g1, bz),
           (b1, bz), (b1, zt)]
    outline = rounded(pts, [0, 0.006, 0.003, 0.003, 0.003, 0.004, 0.002, 0, 0], n=2)
    ty, tz = TRIGGER_PIVOT[1:]
    boxes = [((0, ty + 0.003, (bz - 0.002 + tz + 0.008) / 2), (0.009, 0.020, tz + 0.010 - bz))]
    k.plate([(0, y, z) for y, z in outline], 2 * TRIGGER_HALF, (1, 0, 0), "Root", SEC, boxes=boxes)
    k.cyl((-TRIGGER_HALF - 0.0012, ty, tz), (TRIGGER_HALF + 0.0012, ty, tz), 0.0016, "Root", JNT, segs=6)


def build_trigger(k):
    """The trigger: the pistol's small curved lever on its pin in the block's slot."""
    py, pz = TRIGGER_PIVOT[1:]
    k.cyl((-0.0034, py, pz), (0.0034, py, pz), 0.0048, TRIGGER, MTL, segs=10)
    k.prism([(0, py + y, pz + z) for y, z in TRIGGER_OUTLINE], 0.0062, (1, 0, 0), TRIGGER, MTL, convex=False)


STOCK_TUBE = ((0.200, 0.332), 0.2445, 0.0145)  # the stock's tube: y (from inside the shroud into the upright), axis z, inradius
STOCK_STRUT = ((0.205, 0.1755), (0.338, 0.093), 0.009)  # its strut: front and rear on its centre line (y, z), half-width
STOCK_POST = ((0.332, 0.357), (0.078, 0.263))  # its upright: y, z
BUTT = (0.357, 0.3675)                  # the buttpad on the upright's back face (z 0.078..0.263)


def build_stock(k):
    """The stock: a metallic black octagonal tube out of the shroud's rear end into a black upright, a
    titanium lock collar on the tube at the upright, a black strut from under the shroud's rear down to
    the upright's toe (plates chamfered all round); the titanium buttpad on the upright's back face,
    exactly as high and wide as it and chamfered the same, its back corners rounded, with grip grooves
    and two bolts."""
    (t0, t1), tz, tr = STOCK_TUBE
    rc = tr / math.cos(math.pi / 8)                                                      # its corners' radius
    k.cyl((0, t0, tz), (0, t1 + 0.004, tz), rc, "Root", MTL, segs=8)
    k.cyl((0, t1 - 0.014, tz), (0, t1 + 0.0005, tz), rc + 0.0025, "Root", FRM, segs=8)  # lock collar
    bolt(k, (0, t1 - 0.007, tz - rc - 0.0025), DOWN, "Root", r=0.0028, head=0.0018)       # its clamp bolt
    (p0, p1), (z0, z1) = STOCK_POST
    post = rounded([(p0, z0), (p1, z0), (p1, z1), (p0, z1)], [0.004, 0.0, 0.0, 0.006], n=2)
    k.plate([(0, y, z) for y, z in post], 0.026, (1, 0, 0), "Root", SEC, bevel=0.003)
    a, b, hw = STOCK_STRUT
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    n = Vector((-d.y, d.x))
    strut = [a - n * hw, b - n * hw, b + n * hw, a + n * hw]
    k.plate([(0, q.x, q.y) for q in strut], 0.020, (1, 0, 0), "Root", SEC, bevel=0.003)
    b0, b1 = BUTT
    pad = rounded([(b0, z0), (b1, z0), (b1, z1), (b0, z1)], [0.0, 0.005, 0.005, 0.0])
    slots = [((0, b1, z), (0.04, 0.003, 0.004)) for z in (0.120, 0.132, 0.144)]
    k.plate([(0, y, z) for y, z in pad], 0.026, (1, 0, 0), "Root", FRM, boxes=slots, bevel=0.004)
    for z in (0.105, 0.24):
        bolt(k, (0, b1, z), BACK, "Root", r=0.003)


# --------------------------------------------------------------------------------------------
# Parts: the barrel, the muzzle block and the prongs
# --------------------------------------------------------------------------------------------

def build_block(k):
    """The muzzle block on the rails' ends: a titanium spider round the barrel (a sliding fit), three
    lugs slotted for the prongs and the rails' ears, each prong's stainless steel pin across its slot, showing
    past its lug on both sides."""
    lobes = [(az, PIN[0] + 0.0045, 0.0065) for az in PRONG_AZ] + [(az, RAIL[0] + RAIL[1] + 0.0015, RAIL[2] + 0.0025)
                                                                  for az in (0, 180)]
    y0, y1 = BLOCK
    slots = [lug_slot(az, PIN[0] - 0.0085, PIN[0] + 0.02, 0.0035, y0 - 0.01, PIN[1] + 0.0085) for az in PRONG_AZ]
    k.plate(xz_poly(star(lobes, 0.031), (y0 + y1) / 2), y1 - y0, (0, 1, 0), "Root", FRM,
            cuts=[bore_cut(y0 - 0.01, y1 + 0.01)], subtract=slots)
    for az in PRONG_AZ:
        p, t = prong_pin(az), prong_axis(az)
        k.cyl(p - t * 0.0075, p + t * 0.0075, 0.0018, "Root", JNT, segs=6)


PRONG_OUTLINE = [(0.004, 0.0278), (0.028, 0.0280), (0.044, 0.0212), (0.0565, 0.0130), (0.0590, 0.0165), (0.047, 0.0272),
                 (0.030, 0.0352), (0.014, 0.0362), (0.004, 0.0365), (-0.003, 0.0355), (-0.0045, 0.032), (-0.003, 0.0285)]
PRONG_TIP = (0.0572, 0.0148)


def build_prong(k, i):
    """One prong: a military blue claw on its pin (a boss round it in the block's slot), curving in round
    the emitter to a stainless steel electrode tip; a metallic black yoke on its back, the two cheeks of its
    actuator's rod eye."""
    bone, az = PRONGS[i], PRONG_AZ[i]
    t = prong_axis(az)
    pt = lambda a, u: tuple(prong_point(az, a, u))
    k.prism([pt(a, u) for a, u in PRONG_OUTLINE], 0.006, t, bone, PRI, convex=False)
    pin = prong_pin(az)
    k.cyl(pin - t * 0.0032, pin + t * 0.0032, 0.0045, bone, PRI, segs=10)               # boss, a touch proud of the claw
    tip = prong_point(az, *PRONG_TIP)
    k.cyl(tip - t * 0.0036, tip + t * 0.0036, 0.0024, bone, JNT, segs=6)               # electrode tip
    ya, yb = ACT_B[0] - 0.004, ACT_B[0] + 0.004
    top = ACT_U - ACT_R * 1.2 - 0.0008
    k.prism([pt(a, u) for a, u in ((ya, 0.0355), (yb, 0.0355), (yb, top), (ya, top))], 0.014, t, bone, MTL)  # yoke
    cheek = [(ya, top - 0.0005), (yb, top - 0.0005), (yb, ACT_U + 0.003), (ACT_B[0], ACT_U + 0.0055), (ya, ACT_U + 0.003)]
    for sgn in (1, -1):
        off = t * sgn * 0.0059
        k.prism([tuple(Vector(pt(a, u)) + off) for a, u in cheek], 0.0022, t, bone, MTL)


def build_barrel(k):
    """The barrel: a titanium tube sliding in the shroud's bore, the coils', the collar's and the block's,
    recoiling into the shroud; the stainless steel emitter nozzle on its end, its lit crystal in the throat."""
    pipe(k, (0, EMIT[1] - 0.002, BORE_Z), (0, BARREL_REAR, BORE_Z), BARREL_R, BARREL_BORE, BARREL, FRM, segs=12)
    lathe(k, [(BARREL_R + 0.0005, EMIT[1]), (0.0145, EMIT[1] - 0.004), (0.0155, EMIT[0] + 0.006), (0.0142, EMIT[0]),
              (0.0105, EMIT[0]), (0.0082, EMIT[0] + 0.008), (0.0068, EMIT[1] - 0.001)], BARREL, JNT, segs=12, loop=True)
    lathe(k, [(0, EMIT[1] - 0.0042), (0.0074, EMIT[1] - 0.0065), (0.0080, EMIT[1] - 0.0095), (0, EMIT[1] - 0.0110)],
          BARREL, EMI, segs=12)


# --------------------------------------------------------------------------------------------
# Parts: the latch and the cell pack
# --------------------------------------------------------------------------------------------

LATCH_OUTLINE = [(-0.020, 0.0535), (-0.016, 0.0555), (-0.006, 0.0495), (0.017, 0.0480), (0.017, 0.0420), (0.0145, 0.0420),
                 (0.0145, 0.0300), (0.0095, 0.0300), (0.0095, 0.0410), (-0.006, 0.0410), (-0.016, 0.0470)]


def build_latch(k):
    """The pack latch: two titanium ears sunk into the cowl's crest with a stainless steel pin, a boss on it between
    them, a black lever back over the pack's front plate, its hook in the plate's rebate (bearing on its
    front wall), a thumb tab in front."""
    ps, ph = LATCH_PIN
    for sx in (1, -1):
        ear = [(ps - 0.0065, 0.032), (ps + 0.0065, 0.032), (ps + 0.0055, ph + 0.003), (ps, ph + 0.0055),
               (ps - 0.0055, ph + 0.003)]
        k.prism(pack_side(ear, sx * 0.008), 0.003, (1, 0, 0), "Root", FRM)
    k.cyl(pk(-0.0115, ps, ph), pk(0.0115, ps, ph), 0.0018, "Root", JNT, segs=6)
    k.cyl(pk(-0.0062, ps, ph), pk(0.0062, ps, ph), 0.0042, LATCH, FRM, segs=10)
    k.prism(pack_side(LATCH_OUTLINE), 0.010, (1, 0, 0), LATCH, SEC, convex=False)


COVER = ((0.028, 0.124), 0.028, 0.0012)            # the cover plate on the shell's top: s, half-width, thickness
GRILLE = [(0.074 + 0.0095 * i) for i in range(5)]    # the vent grille's slots across the cover (s), 2.5 mm wide
STRIPES = (0.038, 0.047, 0.056)                      # the three lit stripes across the cover (s)
RIBS = ((0.030, 0.122), (0.010, 0.015, 0.020))       # the grip ribs on the sides: s, heights
LOOP = (0.130, 0.022, 0.008)                         # the pull loop on the top at the back: s, half-span, height


def rounded_rect(w, zb, zt, rb, rt, n=3):
    """(x, z) points of a rounded rectangle, counter-clockwise from the right flank's bottom."""
    def arc(cx, cz, r, a0):
        return [(cx + r * math.cos(math.radians(a0 + 90 * i / n)), cz + r * math.sin(math.radians(a0 + 90 * i / n)))
                for i in range(n + 1)]
    return (arc(w - rb, zb + rb, rb, 270) + arc(w - rt, zt - rt, rt, 0) + arc(-w + rt, zt - rt, rt, 90)
            + arc(-w + rb, zb + rb, rb, 180))


def build_pack(k):
    """The cell pack (bone Mag), an enclosed power module: a titanium shell lofted between two black bumpers
    (the front one carrying the connector's bronze nubs and the latch's rebate), two metallic black
    runners under it on the bay; a military blue cover plate on its top, four screws, a six-slot vent grille
    cut down through it into the shell (the cells' cooling) and three lit stripes; three rubber grip
    ribs down each side; a stainless steel pull loop on the top at the back (lift the latch, pull the pack out);
    on the rear bumper, facing the gunner, the charge gauge (five lit pips in a recess, the pack's one
    light) and a stainless steel test button."""
    hw, top, (a0, a1) = HOUSING
    w, zb, zt, rb, rt = SHELL
    fs, rs = (a0, a0 + 0.012), (a1 - 0.014, a1)                                          # the bumpers (s)
    ring = rounded_rect(w, zb, zt, rb, rt)
    (c0, c1), cw, cth = COVER
    grille = [([tuple(pk(x, s, zt)) for x, s in ((-0.022, sc - 0.00125), (0.022, sc - 0.00125), (0.022, sc + 0.00125),
                                                  (-0.022, sc + 0.00125))], tuple(PACK_N), 0.010) for sc in GRILLE]
    rebate = (pack_side([(0.009, 0.028), (0.03, 0.028), (0.03, 0.05), (0.009, 0.05)]), (1, 0, 0), 0.011)  # the latch's
    carve(k, loft([fs[1] - 0.001, rs[0] + 0.001], lambda s: [pk(x, s, h) for x, h in ring]), MAG, FRM,
          subtract=grille + [rebate])
    bumper = rounded([(hw, 0.001), (hw, top), (-hw, top), (-hw, 0.001)], [0.005, 0.010, 0.010, 0.005], n=3)
    gauge = ([tuple(pk(x, a1, h)) for x, h in ((-0.016, 0.014), (0.010, 0.014), (0.010, 0.022), (-0.016, 0.022))],
             tuple(PACK_D), 0.003)
    k.plate(pack_poly(bumper, sum(fs) / 2), fs[1] - fs[0], tuple(PACK_D), MAG, SEC, subtract=[rebate], bevel=0.001)
    k.plate(pack_poly(bumper, sum(rs) / 2), rs[1] - rs[0], tuple(PACK_D), MAG, SEC, subtract=[gauge], bevel=0.001)
    for i in range(5):                                                                    # charge gauge pips
        x = -0.0135 + 0.005 * i
        k.obox(pk(x, a1 - 0.0016, 0.018), pk(x + 0.0035, a1 - 0.0016, 0.018), 0.005, 0.0012, tuple(PACK_D), MAG, EMI)
    k.cyl(pk(0.019, a1 - 0.001, 0.018), pk(0.019, a1 + 0.0022, 0.018), 0.0032, MAG, JNT, segs=8)  # test button
    for sx in (1, -1):
        c = pk(sx * CELL_X, a0, CELL_H)
        k.cyl(c - PACK_D * (NUB[1] - 0.004), c + PACK_D * 0.0005, NUB[0], MAG, BRZ, segs=8)  # contact nub
        x0 = sx * 0.020
        k.obox(pk(x0, fs[1] - 0.0005, zb - 0.001), pk(x0, rs[0] + 0.0005, zb - 0.001), 0.008, 0.002, tuple(PACK_N), MAG,
               MTL)                                                                        # runner
        for h in RIBS[1]:                                                                  # grip ribs
            k.obox(pk(sx * (w + 0.0004), RIBS[0][0], h), pk(sx * (w + 0.0004), RIBS[0][1], h), 0.0022, 0.0016, (sx, 0, 0),
                   MAG, SEC)
    cover = rounded([(cw, c0), (cw, c1), (-cw, c1), (-cw, c0)], [0.004] * 4, n=2)
    slot = lambda sc: ((-0.022, sc - 0.00125), (0.022, sc - 0.00125), (0.022, sc + 0.00125), (-0.022, sc + 0.00125))
    holes = [[tuple(pk(x, s, zt + cth / 2)) for x, s in slot(sc)] for sc in GRILLE]
    k.plate([tuple(pk(x, s, zt + cth / 2)) for x, s in cover], cth, tuple(PACK_N), MAG, PRI, holes=holes,
            bevel=0.0004)                                                                  # cover plate
    for x in (-cw + 0.005, cw - 0.005):
        for s in (c0 + 0.005, c1 - 0.005):
            bolt(k, pk(x, s, zt + cth), tuple(PACK_N), MAG, r=0.0018, head=0.0008)
    for s in STRIPES:                                                                    # lit stripes
        k.obox(pk(-0.016, s, zt + cth - 0.0002), pk(0.016, s, zt + cth - 0.0002), 0.0028, 0.0012, tuple(PACK_N), MAG, EMI)
    s, half, lift = LOOP
    k.tube([pk(-half, s, zt), pk(-half, s, zt + lift), pk(half, s, zt + lift), pk(half, s, zt)], 0.0022, MAG, JNT, sides=6)


def build_gun(k, pistons, joints):
    build_shroud(k)
    build_rails(k)
    build_coils(k)
    build_collar(k)
    build_grip(k)
    build_trigger(k)
    build_stock(k)
    build_block(k)
    for i in range(3):
        build_prong(k, i)
    build_pistons(k, pistons, joints)
    build_barrel(k)
    build_latch(k)


# --------------------------------------------------------------------------------------------
# Checks specific to the lightning gun
# --------------------------------------------------------------------------------------------

def sweep_states(joints):
    """Joint-range sweeps on top of the animation frames: the barrel's recoil; the prongs together (barrel
    home and recoiled) and out of step; the trigger, the latch, the pack."""
    states = [(f"barrel {RECOIL * i / 5:.3f}", {BARREL: RECOIL * i / 5}) for i in range(1, 6)]
    states += [(f"prongs {v} barrel {b}", {**prongs(v), BARREL: b}) for v in range(0, PRONG_OPEN + 1, 2)
               for b in (0.0, RECOIL)]
    states += [(f"prongs staggered {v}", {PRONGS[0]: v, PRONGS[1]: PRONG_OPEN - v, PRONGS[2]: v / 2})
               for v in range(0, PRONG_OPEN + 1, 6)]
    states += [(f"trigger {v}", {TRIGGER: v}) for v in range(0, TRIGGER_PULL + 1, 2)]
    states += [(f"latch {v}", {LATCH: v}) for v in range(0, LATCH_OPEN + 1, 5)]
    states += [(f"mag {MAG_TRAVEL * i / 10:.4f}", {LATCH: LATCH_OPEN, MAG: MAG_TRAVEL * i / 10}) for i in range(11)]
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
    it), each arc tip its prong (it opens with it, up pointing out from the bore), each vent its flank
    (forward = out of the flank)."""
    out = [("Muzzle", BARREL, Vector((0, EMIT[0] - 0.01, BORE_Z)), Vector(FWD), Vector(UP))]
    out += [(f"ArcTip{i + 1}", PRONGS[i], prong_point(az, *PRONG_TIP), Vector(FWD), radial(az))
            for i, az in enumerate(PRONG_AZ)]
    for side, sx in (("Left", 1), ("Right", -1)):
        (y0, y1), (z0, z1), _, _ = HEATSINK
        out.append((f"Vent{side}", "Root", Vector((sx * SHROUD_W, (y0 + y1) / 2, (z0 + z1) / 2)), Vector((sx, 0, 0)),
                    Vector(UP)))
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
    """The cell pack on its own for the pickup: an unskinned copy, levelled (its sled's underside on
    z = 0, its axis along Y, the nubs toward -Y), its origin at its bottom centre."""
    mesh = ammo.data.copy()
    basis = Matrix((Vector((1, 0, 0)), PACK_D, PACK_N)).transposed().to_4x4()   # pack (x, s, h) -> world
    P = basis.inverted() @ Matrix.Translation(-pk(0, PACK_L / 2, 0))
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
            "grips": "the forend, from below, palm up" if side == "Left" else "pistol grip",
            "wrist_blender": vec(wrist), "bone_x_blender": vec(x), "bone_y_blender": vec(y), "bone_z_blender": vec(z),
            "wrist_godot": godot(wrist), "bone_x_godot": godot(x), "bone_y_godot": godot(y), "bone_z_godot": godot(z),
            "grip_pose_deg": pose}
    spec = lambda n: [{"name": g, "bone": b, "position": vec(o), "forward": vec(f), "up": vec(u)}
                      for g, b, o, f, u in gizmo_specs() if g.startswith(n)]
    data = {
        "name": NAME,
        "space": "Blender coords: +Z up, the muzzle points -Y, the origin is the gun's bottom centre (the pistol grip's "
                 "pommel plane, midway along the gun). glTF/Godot: (x, z, -y), so the muzzle points +Z (glTF's front). "
                 "Hinges turn about their bone's local X (degrees), slides move along their bone's local Y (metres).",
        "rest": "prongs closed, barrel home, rotor at 0, pack in, latch shut, trigger released",
        "size_m": {"wide": round(size.x, 3), "long": round(size.y, 3), "high": round(size.z, 3),
                   "max_wide_long_high": list(WEAPON_MAX), "bore_axis_height": round(BORE_Z, 4),
                   "note": "every weapon fits 0.25 x 0.75 x 0.35 m; it fits the item table's and the weapon holder's hatches and the item table's "
                           "0.5 m tall-weapon stroke"},
        "materials": SLOTS,
        "triangles": {f"SK_{TITLE}": tris, f"SK_{TITLE}Ammo": ammo_tris, f"SM_{TITLE}Ammo": ammo_tris},
        "joints": [{"bone": j.name, "parent": j.parent, "type": j.kind, "pivot": vec(j.pivot), "axis": vec(j.axis),
                    "range": list(j.limits) if j.limits else None,
                    "channel": {"hinge": "rotation_x_deg", "slide": "location_y_m"}.get(j.kind)}
                   for j in joints.values()],
        "pistons": [{"name": p.name, "barrel_bone": p.cylinder, "rod_bone": p.rod, "barrel_on": p.cyl_parent,
                     "rod_on": p.rod_parent, "pin_a": vec(p.a), "pin_b": vec(p.b), "radius": p.radius,
                     "stroke_m": [round(v, 4) for v in p.stroke]} for p in pistons],
        "pistons_note": "each prong's actuator is baked into the actions (its barrel and rod bones' rotations); "
                        "in a pose of your own, aim the barrel at the rod's pin and the rod at the barrel's",
        "animations": {name: {"frames": [0, max(f for ks in keys.values() for f, _ in ks)],
                              "fps": FPS, "loop": loop, "joints": sorted(expand(keys))}
                       for name, (loop, _, keys) in ANIMATIONS.items()},
        "fire": {
            "beam": f"primary fire (hold): play fire_start once ({START_F} frames: the trigger pulls, the prongs open "
                    f"{PRONG_BEAM} deg), then loop fire (30 frames: the prongs flicker +-{FLICKER[0]:g} deg and the "
                    f"barrel pulses {RECOIL * 100:g} cm back and home once a second, {RECOIL_F[0]} frames back, "
                    f"{RECOIL_F[1]} home), and on release play fire_end ({END_F} frames). Draw the beam from Muzzle "
                    f"(forward = the beam's direction) from fire_start's frame 3 and through fire; arc the ArcTip "
                    f"gizmos to it; heat shimmer at the Vent gizmos.",
            "orb": f"secondary fire: play fire_orb ({ORB_END} frames, from idle): the prongs snap open "
                   f"{PRONG_OPEN} deg by frame {ORB_F}, when the orb leaves: spawn it at Muzzle's transform; the "
                   f"barrel recoils {RECOIL * 100:g} cm and is home by the last frame.",
            "idle": f"loop idle between shots: the prongs breathe {IDLE_BREATH:g} deg open and closed over "
                    f"{IDLE_F} frames. Every prong action starts and ends closed (fire at the beam's opening), so "
                    f"they chain without a jump.",
            "recoil_m": RECOIL, "recoil_frames": list(RECOIL_F), "orb_frame": ORB_F},
        "gizmos": {
            "convention": "empties: in Blender local +Y is the gizmo's forward and +Z its up; in glTF / Godot -Z is "
                          "forward and +Y up (Marker3D / Node3D under a BoneAttachment3D, so they follow the "
                          "animations)",
            "muzzle": spec("Muzzle")[0],
            "muzzle_note": "1 cm in front of the emitter's face, on the barrel's bone (it recoils with the barrel): "
                           "the lightning's origin, the orb's spawn point and where to play the muzzle flash",
            "arc_tips": spec("ArcTip"),
            "arc_tip_note": "each prong's electrode tip, on the prong's bone (it opens with it): arc them to the "
                            "muzzle's beam while firing",
            "vents": spec("Vent"),
            "vent_note": "the middle of each flank's heat sink, forward out of the flank: heat shimmer or sparks while firing",
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
                 "pickup_mesh": f"SM_{TITLE}Ammo", "pickup_origin": "its bottom centre, levelled", "cells": 2,
                 "axis": vec(PACK_D), "pitch_deg": PACK_PITCH, "rails_m": MAG_TRAVEL,
                 "note": "mag_release lifts the latch and runs the pack back and up its axis until its cells' nubs "
                         "leave their sockets; past MAG_TRAVEL it is free: hide the pack mesh and drop a physics copy "
                         "of the pickup mesh at the Mag bone's transform (pitched). To reload, put the pack back at "
                         "the end of its travel and play mag_insert."},
        "usage": "idle (loop); primary: fire_start, fire (loop), fire_end; secondary: fire_orb; "
                 "mag_release / mag_insert swap the cell pack.",
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
    check_piston_clearance(pistons, joints, kit.solids, all_parts(kit))
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
    ammo_tris = finish(ammo, rig, joints, AMMO_BUDGET, [])  # the pack only hides from itself: it detaches

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
