"""Retarget the Mixamo source animations onto Tensor (and each weapon's own bones): one GLB per clip.

Run headless from the repo root (after Tensor's and the weapons' model.py):
    blender --background --factory-startup --python animations/retarget.py [-- <group/clip pattern> ...]

Sources (animations/source, as downloaded from Mixamo): loose FBX files for the character's own clips
(idle, falls, landing, a death, results) and three packs (zips): the Pro Rifle Pack (8-way walk, run, sprint
and crouch walk, turns, jumps, idles; its deaths), the Basic Shooter Pack (fire, reload, hit reaction; its
grenade toss) and the Pistol Handgun Locomotion Pack. Only the clips of combat with a weapon in hand are
weapon clips (user); the packs' deaths and the grenade toss are the character's own, without a weapon.

Per clip:
  1. Retarget. Every Mixamo bone's world rotation change from its rest (a T-pose, as Tensor's is) is
     carried onto Tensor's Godot-humanoid bone, top-down, then clamped to the bone's limits in its Euler
     order (and the hips' coupled limit envelopes); a clamped parent's lost rotation passes to its child.
  2. Root motion. The hips' travel, scaled by leg length, goes on the Root bone (Godot root motion):
     linear over a loop, smoothed for one-shots, and the turns carry their yaw; the hips keep the rest.
  3. Feet. Foot contacts are found in the retargeted motion (low and still); a planted foot is held flat
     where it landed and each leg is solved onto it (hip, knee, ankle within their limits); nothing goes
     below the floor.
  4. Weapon hold (the weapon clips, per weapon). The weapon rides the firing hand: in its own family's
     clips the weapon follows the retargeted right hand (calibrated so it aims straight ahead in the
     family's aiming idle), turned to where Tensor faces; a sprint's rides the upper chest as in the aiming idle.
     Each family's weapon sits its fitted drop lower than the source's hands. Both hands are then solved exactly onto
     the weapon's hand sockets (user: the sockets are the grips; the animation plugs into them), the arms'
     10 joints each within their limits, the support hand only while the source's hand is on the weapon
     (it lets go for a reload), and the fingers close to the weapon's grip poses. Through a reload the
     support hand takes the ammo pack by its socket (AmmoHandSocket), carries it and puts it back.
  5. Bake and export. Every bone (the mechanical stages, bearings and pistons follow their constraints)
     is baked to keys and the rig exported alone: target/tensor/<group>/<clip>.glb. A weapon clip also
     exports the weapon's bones in sync (its own idle, fire and reload actions, the ammo pack riding the
     support hand by its socket between release and insert): target/weapons/<weapon>/<clip>.glb.

  6. Aim poses (per weapon): its aiming idle raised and lowered from -75 to +75 deg (aim_down75 .. aim_level ..
     aim_up75), the arms doing it (the chest leans a little, the head follows), for Godot's additive 1D aim blend;
     the game turns the whole player to look left and right.

A manifest (target/manifest.json) lists every clip: file, frames, fps, loop, root motion, source and
its checks (worst hand miss on the sockets, lowest point).
"""

import fnmatch
import json
import math
import sys
import tempfile
import os
import zipfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
SRC = HERE / "source"
OUT = Path(os.environ.get("RETARGET_OUT", HERE / "target"))  # (a scratch folder for trial runs)
CHAR = LIB / "models" / "characters" / "tensor"
WEAPONS = LIB / "models" / "weapons"
FPS = 30
DEBUG = bool(os.environ.get("RETARGET_DEBUG"))

# === SPEC ===
# Mixamo bone (after its namespace) -> Tensor bone.
MAP = {"Hips": "Hips", "Spine": "Spine", "Spine1": "Chest", "Spine2": "UpperChest", "Neck": "Neck", "Head": "Head"}
for _s in ("Left", "Right"):
    MAP.update({f"{_s}Shoulder": f"{_s}Shoulder", f"{_s}Arm": f"{_s}UpperArm", f"{_s}ForeArm": f"{_s}LowerArm",
                f"{_s}Hand": f"{_s}Hand", f"{_s}UpLeg": f"{_s}UpperLeg", f"{_s}Leg": f"{_s}LowerLeg",
                f"{_s}Foot": f"{_s}Foot", f"{_s}ToeBase": f"{_s}Toes",
                f"{_s}HandThumb1": f"{_s}ThumbMetacarpal", f"{_s}HandThumb2": f"{_s}ThumbProximal",
                f"{_s}HandThumb3": f"{_s}ThumbDistal"})
    for _m, _t in (("Index", "Index"), ("Middle", "Middle"), ("Ring", "Ring"), ("Pinky", "Little")):
        for _k, _p in ((1, "Proximal"), (2, "Intermediate"), (3, "Distal")):
            MAP[f"{_s}Hand{_m}{_k}"] = f"{_s}{_t}{_p}"

RIFLE, PISTOL, SHOOTER = "Pro Rifle Pack.zip", "Pistol_Handgun Locomotion Pack.zip", "Basic Shooter Pack.zip"
# The weapon families: the source family whose motions they take natively. Each weapon sits in its family's aiming
# idle level and pointing where Tensor faces, carried on his right, the support hand reaching across (user: centred
# between the actor's hands it ran down his middle, even left of it; and too low, its grip under the shoulder on a
# hanging arm). HOLDS, per weapon: its centreline's side across the upper chest (m, -: his right) and its firing
# wrist's place from his right shoulder joint (ahead, up; m), fitted where he holds it exactly (its aim and both hands
# over the steady clips and the aim poses, no arm through it, nothing of it in him). Every long gun takes the rocket
# launcher's hold (user: its holds, aim and positions are gold; one hold for all, consistent): its firing wrist exactly
# where the rocket launcher's is (REFERENCE), level and straight, so the firing arm, the aim, the fire and the body are
# the same for all and only the support hand goes to each gun's own grip. His elbow folds to 140 deg (deepened from 120
# so the forends are in his other hand's reach); the rifle's and the EMP gun's stocks were shortened to sit on his
# chest, and the rifle's support grip moved back onto its magwell, to take this hold. The pistol keeps its own pack's
# two-handed hold, held out at arm's length.
FAMILIES = {
    "rifle": {"source": "rifle"},
    "pistol": {"source": "pistol"},
}
REFERENCE = "rocket_launcher"
HOLDS = {
    "rocket_launcher": (-0.10, (0.22, -0.05)),
    "rifle": REFERENCE, "emp_gun": REFERENCE, "lightning_gun": REFERENCE, "minigun": REFERENCE,
    "flamethrower": REFERENCE, "bio_rifle": REFERENCE, "grenade_launcher": REFERENCE, "flak_cannon": REFERENCE,
    "pistol": (-0.05, (0.28, -0.07)),       # held out at arm's length, a little right of his middle
}
TOP_RELOAD = {"lightning_gun"}    # its pack on top (the others' underneath): reloaded from above, not from the
                                  # rocket launcher's reload carry
WEAPON_FAMILY = {"rifle": "rifle", "emp_gun": "rifle", "lightning_gun": "rifle", "rocket_launcher": "rifle",
                 "minigun": "rifle", "pistol": "pistol", "flamethrower": "rifle", "bio_rifle": "rifle",
                 "grenade_launcher": "rifle", "flak_cannon": "rifle"}
# (user: the flamethrower was carried at the right hip first; raised to the heavy weapons' hold, where Tensor holds it
# exactly, the arms off the rifle clips couldn't reach it at the hip)
CALIBRATE = {"rifle": ("rifle", "idle_aiming"), "pistol": ("pistol", "idle")}  # aiming idles: weapon straight ahead

# Clips: group/name -> (source (pack zip or folder path), file, loop, root motion mode). Root motion modes:
# "none" (in place: all on the hips), "linear" (a loop's stride), "track" (a one-shot's travel, smoothed),
# "turn" (travel and yaw).
COMMON = {
    "idle": ("idle/Idle.fbx", None, True, "none"),
    "falling": ("environmental/falling/Falling.fbx", None, True, "none"),
    "falling_to_landing": ("spawn/falling_to_landing/Falling To Landing.fbx", None, False, "track"),
    "death_flying_back": ("combat/airborne_death/Flying Back Death.fbx", None, False, "track"),
    "defeated": ("results/defeat/defeated/Defeated.fbx", None, False, "none"),
}
for _d in ("Chicken Dance", "Dancing Twerk", "Gangnam Style", "Hip Hop Dancing", "House Dancing", "Locking Hip Hop Dance",
           "Macarena Dance", "Rumba Dancing", "Silly Dancing", "Snake Hip Hop Dance", "Tut Hip Hop Dance", "Twist Dance",
           "Wave Hip Hop Dance"):
    _k = _d.lower().replace(" ", "_")
    COMMON[f"victory_{_k}"] = (f"results/victory/{_k}/{_d}.fbx", None, True, "none")
# The packs' clips that aren't combat with a weapon in hand (user: weapons get only those): the character's own.
COMMON.update({
    "death_front": (RIFLE, "death from the front.fbx", False, "track"),
    "death_back": (RIFLE, "death from the back.fbx", False, "track"),
    "death_right": (RIFLE, "death from right.fbx", False, "track"),
    "death_front_headshot": (RIFLE, "death from front headshot.fbx", False, "track"),
    "death_back_headshot": (RIFLE, "death from back headshot.fbx", False, "track"),
    "death_crouching_headshot": (RIFLE, "death crouching headshot front.fbx", False, "track"),
    "toss_grenade": (SHOOTER, "toss grenade.fbx", False, "none"),
})

RIFLE_MOTIONS = {
    "idle": (RIFLE, "idle.fbx", True, "none"),
    "idle_aiming": (RIFLE, "idle aiming.fbx", True, "none"),
    "idle_crouching": (RIFLE, "idle crouching.fbx", True, "none"),
    "idle_crouching_aiming": (RIFLE, "idle crouching aiming.fbx", True, "none"),
    "turn_90_left": (RIFLE, "turn 90 left.fbx", False, "turn"),
    "turn_90_right": (RIFLE, "turn 90 right.fbx", False, "turn"),
    "crouch_turn_90_left": (RIFLE, "crouching turn 90 left.fbx", False, "turn"),
    "crouch_turn_90_right": (RIFLE, "crouching turn 90 right.fbx", False, "turn"),
    "jump_up": (RIFLE, "jump up.fbx", False, "track"),
    "jump_loop": (RIFLE, "jump loop.fbx", True, "none"),
    "jump_down": (RIFLE, "jump down.fbx", False, "track"),
    "fire": (SHOOTER, "firing rifle.fbx", True, "none"),
    "reload": (SHOOTER, "reloading.fbx", False, "none"),
    "hit_reaction": (SHOOTER, "hit reaction.fbx", False, "none"),
}
for _gait, _pre in (("walk", "walk"), ("run", "run"), ("sprint", "sprint"), ("crouch_walk", "walk crouching")):
    for _dir in ("forward", "forward left", "forward right", "left", "right", "backward", "backward left", "backward right"):
        RIFLE_MOTIONS[f"{_gait}_{_dir.replace(' ', '_')}"] = (RIFLE, f"{_pre} {_dir}.fbx", True, "linear")

PISTOL_MOTIONS = {
    "idle": (PISTOL, "pistol idle.fbx", True, "none"),
    "walk_forward": (PISTOL, "pistol walk.fbx", True, "linear"),
    "walk_backward": (PISTOL, "pistol walk backward.fbx", True, "linear"),
    "run_forward": (PISTOL, "pistol run.fbx", True, "linear"),
    "run_backward": (PISTOL, "pistol run backward.fbx", True, "linear"),
    "strafe_a": (PISTOL, "pistol strafe.fbx", True, "linear"),
    "strafe_b": (PISTOL, "pistol strafe (2).fbx", True, "linear"),
    "walk_arc_a": (PISTOL, "pistol walk arc.fbx", True, "turn"),
    "walk_arc_b": (PISTOL, "pistol walk arc (2).fbx", True, "turn"),
    "run_arc_a": (PISTOL, "pistol run arc.fbx", True, "turn"),
    "run_arc_b": (PISTOL, "pistol run arc (2).fbx", True, "turn"),
    "walk_backward_arc_a": (PISTOL, "pistol walk backward arc.fbx", True, "turn"),
    "walk_backward_arc_b": (PISTOL, "pistol walk backward arc (2).fbx", True, "turn"),
    "run_backward_arc_a": (PISTOL, "pistol run backward arc.fbx", True, "turn"),
    "run_backward_arc_b": (PISTOL, "pistol run backward arc (2).fbx", True, "turn"),
    "jump": (PISTOL, "pistol jump.fbx", False, "track"),
    "jump_running": (PISTOL, "pistol jump (2).fbx", False, "track"),
    "stand_to_kneel": (PISTOL, "pistol stand to kneel.fbx", False, "none"),
    "kneeling_idle": (PISTOL, "pistol kneeling idle.fbx", True, "none"),
    "kneel_to_stand": (PISTOL, "pistol kneel to stand.fbx", False, "none"),
}
# Contacts and hands.
CONTACT_HEIGHT = 0.035   # a foot this close above its rest height...
CONTACT_SPEED = 0.30     # ...and slower than this (m/s) is planted
UPRIGHT = 0.5            # the torso (hips to head) more than 60 deg off vertical (its z below this): lying on the
                         # ground (no planting; the shell meets the floor); a crouch or a squat stays upright
SUPPORT_NEAR, SUPPORT_FAR = 0.06, 0.16  # the support hand grips while its source hand stays this near the aiming
                                        # idle's two-handed grip (in the firing hand's frame)
TOL_HAND = 0.003         # a gripping hand must land within this of its socket (m)...
TOL_TURN = 3.0           # ...and turned within this of it (deg)
ARM_R = (0.050, 0.044)   # Tensor's upper arm and forearm as capsules round their bones (m), for the weapon clash...
WRIST_FREE = 0.06        # ...the forearm's last stretch left out (the wrist is on the grip)
CLASH_TOL = 0.004        # an arm may graze the weapon this deep (m); deeper, the solver looks for another way round
CLASH_W = 2.0            # an arm's depth in the weapon counts this many times its hand's miss
SOCKET_W = 0.1           # a socket's axes against its position in the solves (m per unit of axis error)
AMMO_EASE = 9            # frames the support hand takes onto the ammo pack's socket (and off it) in a reload
# The aim poses (user: the weapon and the head point at the crosshair as the player looks up and down; the game
# turns the whole player to look left and right): each weapon's aiming idle raised or lowered to these pitches
# (deg; + is up), for Godot's additive 1D blend over any movement (aim_level is the base).
AIM_PITCH = tuple(range(-45, 46, 15))   # (user: 45 deg up and down is as far as the game aims)
AIM_CHEST_SHARE = 0.1    # a pitch's share the chest leans (user: the shoulders, elbows and wrists do the rest)
AIM_STEP = 3             # the ramp each way is solved in these steps (deg), each from the one before  (3: at 5 the EMP gun's 45 up missed by 5 mm)
AIM_W = 0.3              # the weapon's turn against its place in the firing hand's solves (m per unit of axis error)
TOL_AIM = 3.0            # the weapon must end up turned within this of where it points (deg)
# === END SPEC ===


def fail(msg):
    print(f"[retarget] {msg}")
    raise SystemExit(1)


# ----------------------------------------------------------------------------------- the rig
class Rig:
    """Tensor's rest frames, hierarchy, Euler orders and limits; forward kinematics of a pose
    ({bone: 4x4 basis}) through the rest frames, as Blender poses bones."""

    def __init__(self, arm, info):
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.parent = {b.name: b.parent.name if b.parent else None for b in arm.data.bones}
        self.order = {pb.name: pb.rotation_mode for pb in arm.pose.bones}
        self.limits = {b["name"]: b for b in info["bones"]}
        self.rel = {n: (self.rest[p].inverted() @ self.rest[n] if p else self.rest[n]) for n, p in self.parent.items()}
        self.humanoid = [b["name"] for b in info["bones"]]              # parents before children
        self.children = {}
        for n, p in self.parent.items():
            self.children.setdefault(p, []).append(n)

    def world(self, name, pose, cache=None):
        if cache is not None and name in cache:
            return cache[name]
        p = self.parent[name]
        m = (self.world(p, pose, cache) if p else Matrix.Identity(4)) @ self.rel[name] @ pose.get(name, Matrix.Identity(4))
        if cache is not None:
            cache[name] = m
        return m

    def clamp(self, name, rot3, prev=None):
        """A basis rotation clamped to the bone's limits (and envelopes): (Euler radians, 3x3)."""
        order = self.order[name] if self.order[name] != "QUATERNION" else "XYZ"
        e = rot3.to_euler(order, prev) if prev is not None else rot3.to_euler(order)
        info = self.limits.get(name)
        if info:
            lim = info.get("limits_deg", {})
            deg = [math.degrees(v) for v in e]
            deg = [min(max(d, lim[a][0]), lim[a][1]) if a in lim else d for d, a in zip(deg, "xyz")]
            boxes = info.get("limit_envelopes_deg")
            if boxes:
                best = None
                for box in boxes:
                    c = [min(max(d, lo), hi) for d, (lo, hi) in zip(deg, box)]
                    dist = sum((a - b) ** 2 for a, b in zip(c, deg))
                    if best is None or dist < best[0]:
                        best = (dist, c)
                deg = best[1]
            e = Euler([math.radians(d) for d in deg], order)
        return e, e.to_matrix()


def basis(rot3, loc=None):
    m = rot3.to_4x4()
    if loc is not None:
        m.translation = loc
    return m


# ----------------------------------------------------------------------------------- sources
def source_path(src, file, cache):
    if src.endswith(".zip"):
        if src not in cache:
            d = Path(tempfile.mkdtemp(prefix="mixamo_"))
            with zipfile.ZipFile(SRC / src) as z:
                z.extractall(d)
            cache[src] = d
        found = [p for p in cache[src].rglob("*.fbx") if p.name == file]
        if not found:
            fail(f"{file} not in {src}")
        return found[0]
    return SRC / src


def import_source(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    arm = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
    names = {b.name.split(":")[-1]: b.name for b in arm.data.bones}
    act = arm.animation_data.action
    f0, f1 = (int(round(v)) for v in act.frame_range)
    return arm, names, f0, f1


# ----------------------------------------------------------------------------------- retarget
def retarget(rig, src, names, f0, f1, root_mode):
    """Per frame a pose {bone: basis} of Tensor's humanoid bones and Root from the source's motion."""
    scene = bpy.context.scene
    tgt_bones = [b for b in rig.humanoid if b in MAP.values()]
    inv_map = {t: names[s] for s, t in MAP.items() if s in names}
    src_rest = {t: (src.matrix_world @ src.data.bones[inv_map[t]].matrix_local).to_3x3().normalized() for t in inv_map}
    tgt_rest = {t: rig.rest[t].to_3x3() for t in tgt_bones}
    hips_src = names["Hips"]
    rest_hips_src = (src.matrix_world @ src.data.bones[hips_src].matrix_local).translation
    # Leg length ratio: stride and bounce scale with it, so the feet land where they should.
    up = lambda n: (src.matrix_world @ src.data.bones[names[n]].matrix_local).translation
    s_leg = (rig.rest["LeftUpperLeg"].translation.z - rig.rest["LeftFoot"].translation.z) / (up("LeftUpLeg").z - up("LeftFoot").z)
    frames = list(range(f0, f1 + 1))
    deltas, hips = [], []
    for f in frames:
        scene.frame_set(f)
        d = {}
        for t, sname in inv_map.items():
            q = (src.matrix_world @ src.pose.bones[sname].matrix).to_3x3().normalized()
            d[t] = q @ src_rest[t].transposed()
        deltas.append(d)
        hips.append((src.matrix_world @ src.pose.bones[hips_src].matrix).translation.copy())
    # Target hips positions and root motion.
    rest_h = rig.rest["Hips"].translation
    T = [Vector((s_leg * (h.x - rest_hips_src.x), s_leg * (h.y - rest_hips_src.y),
                 rest_h.z + s_leg * (h.z - rest_hips_src.z))) for h in hips]
    n = len(frames)
    yaw = [0.0] * n
    if root_mode == "turn":
        for i, d in enumerate(deltas):
            fwd = d["Hips"] @ Vector((0, -1, 0))
            yaw[i] = math.atan2(fwd.x, -fwd.y)   # about +Z from facing -Y
        for i in range(1, n):  # unwrap
            while yaw[i] - yaw[i - 1] > math.pi:
                yaw[i] -= 2 * math.pi
            while yaw[i] - yaw[i - 1] < -math.pi:
                yaw[i] += 2 * math.pi
        yaw = smooth_series([y - yaw[0] for y in yaw], 9)
    if root_mode == "linear":
        root = [Vector(((T[-1].x - T[0].x) * i / (n - 1), (T[-1].y - T[0].y) * i / (n - 1), 0)) for i in range(n)]
    elif root_mode in ("track", "turn"):
        xs = smooth_series([t.x - T[0].x for t in T], 9)
        ys = smooth_series([t.y - T[0].y for t in T], 9)
        root = [Vector((x, y, 0)) for x, y in zip(xs, ys)]
    else:
        root = [Vector((0, 0, 0)) for _ in range(n)]
    rest_root = rig.rest["Root"]
    poses = []
    prev = {}
    for i in range(n):
        pose = {}
        rz = Matrix.Rotation(yaw[i], 3, "Z")
        pose["Root"] = basis(rest_root.to_3x3().transposed() @ rz @ rest_root.to_3x3(),
                             rest_root.to_3x3().transposed() @ root[i])
        worlds = {"Root": rest_root @ pose["Root"]}
        for b in tgt_bones:
            p = rig.parent[b]
            pw = worlds[p] if p in worlds else rig.world(p, pose)
            want = deltas[i][b] @ tgt_rest[b]                      # the bone's world rotation
            local = (pw @ rig.rel[b]).to_3x3().normalized().transposed() @ want
            e, m3 = rig.clamp(b, local, prev.get(b))
            prev[b] = e
            if b == "Hips":
                loc = (pw @ rig.rel[b]).inverted() @ T[i]
                pose[b] = basis(m3, loc)
            else:
                pose[b] = basis(m3)
            worlds[b] = pw @ rig.rel[b] @ pose[b]
        poses.append(pose)
    return poses


def smooth_series(v, w):
    h = w // 2
    out = []
    for i in range(len(v)):
        a, b = max(0, i - h), min(len(v), i + h + 1)
        out.append(sum(v[a:b]) / (b - a))
    # keep the ends exact (a loop's stride, a one-shot's end)
    if len(v) > 1:
        out[0], out[-1] = v[0], v[-1]
    return out


# ----------------------------------------------------------------------------------- IK
def gauss(a, b):
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-15:
            continue
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-15 else 0.0 for i in range(n)]


def socket_error(m, t):
    """How far a hand's frame m is off its socket t: (position error in m, turn in degrees)."""
    turn = (t.to_3x3().transposed() @ m.to_3x3()).to_quaternion().angle
    return (m.translation - t.translation).length, math.degrees(min(turn, 2 * math.pi - turn))


def socket_residual(m, t, w=SOCKET_W):
    """A hand exactly on its socket: its position, and its X and Y axes (w per unit of axis error)."""
    d = m.translation - t.translation
    ex = (m.col[0].xyz - t.col[0].xyz) * w
    ey = (m.col[1].xyz - t.col[1].xyz) * w
    return [d.x, d.y, d.z, ex.x, ex.y, ex.z, ey.x, ey.y, ey.z]


def socket_miss(m, t):
    """A hand's miss on its socket as one number (m): its position error or its turn (TOL_TURN counting as
    TOL_HAND), whichever is worse."""
    pos, turn = socket_error(m, t)
    return max(pos, turn * TOL_HAND / TOL_TURN)


class ChainIK:
    """Damped least squares on a chain's Euler DOFs (degrees, within limits) putting its end bone's frame
    on a target (position, and its X and Y axes at 0.1 m per unit)."""

    def __init__(self, rig, dofs, end, rot_weight=0.1):
        self.rig, self.dofs, self.end, self.w = rig, dofs, end, rot_weight
        self.bounds = []
        for b, i in dofs:
            lim = rig.limits.get(b, {}).get("limits_deg", {})
            self.bounds.append(tuple(lim.get("xyz"[i], (-180, 180))))

    def read(self, pose):
        out = []
        for b, i in self.dofs:
            order = self.rig.order[b]
            out.append(math.degrees(pose[b].to_3x3().to_euler(order)[i]))
        return out

    def write(self, pose, q):
        new = dict(pose)
        eul = {}
        for (b, i), v in zip(self.dofs, q):
            if b not in eul:
                eul[b] = list(pose[b].to_3x3().to_euler(self.rig.order[b]))
            eul[b][i] = math.radians(v)
        for b, e in eul.items():
            m = Euler(e, self.rig.order[b]).to_matrix().to_4x4()
            m.translation = pose[b].translation
            new[b] = m
        return new

    def solve(self, pose, target, pos_only=False, iters=40, q0=None):
        rig = self.rig
        q = [min(max(v, lo), hi) for v, (lo, hi) in zip(q0 if q0 is not None else self.read(pose), self.bounds)]

        def residual(q):
            m = rig.world(self.end, self.write(pose, q))
            d = m.translation - target.translation
            r = [d.x, d.y, d.z]
            if not pos_only:
                ex = (m.col[0].xyz - target.col[0].xyz) * self.w
                ey = (m.col[1].xyz - target.col[1].xyz) * self.w
                r += [ex.x, ex.y, ex.z, ey.x, ey.y, ey.z]
            return r

        clampq = lambda q: [min(max(v, lo), hi) for v, (lo, hi) in zip(q, self.bounds)]
        for _ in range(iters):
            r = residual(q)
            e = sum(v * v for v in r)
            if e < 1e-10:
                break
            jac = []
            for j in range(len(q)):
                dq = list(q)
                dq[j] += 0.2
                rj = residual(dq)
                jac.append([(a - b) / 0.2 for a, b in zip(rj, r)])
            nq = len(q)
            a = [[sum(x * y for x, y in zip(jac[j], jac[k])) + (1e-8 if j == k else 0.0) for k in range(nq)] for j in range(nq)]
            b = [-sum(x * y for x, y in zip(jac[j], r)) for j in range(nq)]
            step = gauss(a, b)
            big = max(abs(v) for v in step) or 1.0
            if big > 12:
                step = [v * 12 / big for v in step]
            for t in (1.0, 0.5, 0.25, 0.125):
                trial = clampq([v + t * dv for v, dv in zip(q, step)])
                if sum(v * v for v in residual(trial)) < e:
                    q = trial
                    break
            else:
                break
        new = self.write(pose, q)
        m = rig.world(self.end, new)
        err = (m.translation - target.translation).length
        self.last, self.turn = q, socket_error(m, target)[1]
        return new, err


UPPER_BODY = ["Spine", "Chest", "UpperChest", "Neck", "Head"] + [f"{s}{b}" for s in ("Left", "Right")
                                                                 for b in ("Shoulder", "UpperArm", "LowerArm", "Hand")]
TORSO_DOFS = [("Spine", 0), ("Chest", 0), ("UpperChest", 0)]   # the helpers only lean it (the chest faces front)
RELOAD_TORSO = TORSO_DOFS + [("Spine", 1), ("Chest", 1), ("UpperChest", 1), ("UpperChest", 2)]   # a reload may twist it
LEG_DOFS = lambda s: [(f"{s}UpperLeg", 0), (f"{s}UpperLeg", 1), (f"{s}UpperLeg", 2), (f"{s}LowerLeg", 0),
                      (f"{s}Foot", 0), (f"{s}Foot", 1)]
ARM_DOFS = lambda s: [(f"{s}Shoulder", 0), (f"{s}Shoulder", 2), (f"{s}UpperArm", 0), (f"{s}UpperArm", 1),
                      (f"{s}UpperArm", 2), (f"{s}LowerArm", 0), (f"{s}LowerArm", 1), (f"{s}Hand", 0),
                      (f"{s}Hand", 1), (f"{s}Hand", 2)]
_ARM_GRID = {}


def arm_starts(rig, pose, side, target, k=4):
    """A global start for an arm's IK onto a hand target (4x4, the hand bone's world frame): the elbow's and the wrist's
    joints sampled within their limits, the upper arm's turn solved for the hand's (and kept within its limits), the
    samples whose wrists land nearest the target kept, `k` of them from different elbow settings (the solver alone,
    from the actor's arm or the frame before, can stick short of a place the arm reaches: a weapon held up at the
    shoulder). Returns a list of ARM_DOFS values (deg), nearest first."""
    ua, la, hb = f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand"
    order = lambda b: rig.order[b] if rig.order[b] != "QUATERNION" else "XYZ"
    lim = lambda b, a: rig.limits[b]["limits_deg"].get(a, (0, 0))

    def grid(b, a, n):
        lo, hi = lim(b, a)
        return [lo + (hi - lo) * k / (n - 1) for k in range(n)] if hi > lo else [lo]

    if side not in _ARM_GRID:   # (elbow values, its turn and the hand's pivot below the upper arm; wrist values, turn)
        rel_la, rel_h = rig.rel[la], rig.rel[hb]
        elbows = []
        for lax in grid(la, "x", 9):
            for lay in grid(la, "y", 9):
                r = Euler((math.radians(lax), math.radians(lay), 0.0), order(la)).to_matrix()
                elbows.append(((lax, lay), rel_la.to_3x3() @ r, (rel_la @ r.to_4x4()) @ rel_h.translation))
        wrists = [((hx, hy, hz), rel_h.to_3x3() @ Euler([math.radians(v) for v in (hx, hy, hz)], order(hb)).to_matrix())
                  for hx in grid(hb, "x", 8) for hy in grid(hb, "y", 9) for hz in grid(hb, "z", 5)]
        _ARM_GRID[side] = (elbows, wrists)
    elbows, wrists = _ARM_GRID[side]
    base = rig.world(f"{side}Shoulder", pose) @ rig.rel[ua]
    turn = base.to_3x3().transposed() @ target.to_3x3()
    ul = [lim(ua, a) for a in "xyz"]
    per_elbow = []
    for ev, er, tip in elbows:
        best = None
        for wv, wr in wrists:
            r = turn @ (er @ wr).transposed()
            e = [math.degrees(v) for v in r.to_euler(order(ua))]
            if any(v < lo - 0.5 or v > hi + 0.5 for v, (lo, hi) in zip(e, ul)):
                continue
            d = (base @ (r @ tip) - target.translation).length
            if best is None or d < best[0]:
                best = (d, e, ev, wv)
        if best:
            per_elbow.append(best)
    sh = pose[f"{side}Shoulder"].to_3x3().to_euler(order(f"{side}Shoulder"))
    return [[math.degrees(sh[0]), math.degrees(sh[2])] + b[1] + list(b[2]) + list(b[3])
            for b in sorted(per_elbow, key=lambda b: b[0])[:k]]


BODY_PTS = None


def body_points(rig):
    """Tensor's shell as points on his humanoid bones, for the floor: each bone's extreme vertices of SK_Tensor (26
    directions) in its rest frame, a vertex of a mechanical stage going to its nearest humanoid bone."""
    global BODY_PTS
    if BODY_PTS is None:
        bpy.ops.wm.open_mainfile(filepath=str(CHAR / "tensor.blend"))
        mesh = bpy.data.objects["SK_Tensor"]
        groups = {vg.index: vg.name for vg in mesh.vertex_groups}
        human, per = set(rig.humanoid), {}
        for v in mesh.data.vertices:
            if not v.groups:
                continue
            b = groups[max(v.groups, key=lambda x: x.weight).group]
            while b and b not in human:
                b = rig.parent.get(b)
            if b:
                per.setdefault(b, []).append(rig.rest[b].inverted() @ (mesh.matrix_world @ v.co))
        dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if x or y or z]
        BODY_PTS = {b: [Vector(t) for t in {tuple(max(pts, key=lambda q: q.dot(d))) for d in dirs}] for b, pts in per.items()}
    return BODY_PTS


FEET = ("LeftFoot", "LeftToes", "RightFoot", "RightToes")


def fold_feet(rig, pose, pts):
    """Lying down, a foot digging into the floor bends back (its ankle's and toes' pitch within their limits, the
    least change that clears it). Returns the pose."""
    pose = dict(pose)
    for s in ("Left", "Right"):
        foot, toes = f"{s}Foot", f"{s}Toes"
        cache = {}
        if min((rig.world(b, pose, cache) @ v).z for b in (foot, toes) for v in pts.get(b, [])) >= 0.0:
            continue
        parent = rig.world(rig.parent[foot], pose)
        ef = list(pose[foot].to_3x3().to_euler(rig.order[foot]))
        et = list(pose[toes].to_3x3().to_euler(rig.order[toes]))
        lf, lt = rig.limits[foot]["limits_deg"]["x"], rig.limits[toes]["limits_deg"]["x"]
        best = None
        for af in range(int(lf[0]), int(lf[1]) + 1, 5):
            mf = Euler([math.radians(af), ef[1], ef[2]], rig.order[foot]).to_matrix().to_4x4()
            wf = parent @ rig.rel[foot] @ mf
            under_f = sum(min(0.0, (wf @ v).z) for v in pts.get(foot, []))
            for at in range(int(lt[0]), int(lt[1]) + 1, 5):
                mt = Euler([math.radians(at), et[1], et[2]], rig.order[toes]).to_matrix().to_4x4()
                wt = wf @ rig.rel[toes] @ mt
                under = under_f + sum(min(0.0, (wt @ v).z) for v in pts.get(toes, []))
                change = abs(math.radians(af) - ef[0]) + abs(math.radians(at) - et[0])
                key = (round(under, 4), change)
                if best is None or key < best[0]:
                    best = (key, mf, mt)
        pose[foot], pose[toes] = best[1], best[2]
        cache = {}
        under = min((rig.world(b, pose, cache) @ v).z for b in (foot, toes) for v in pts.get(b, []))
        if under < 0.0:   # still in the floor: the leg raises it (hip, knee, ankle within their limits), then the fold
            for b in (f"{s}LowerLeg", foot, toes) * 3:
                cache = {}
                under = min((rig.world(c, pose, cache) @ v).z for c in (f"{s}LowerLeg", foot, toes) for v in pts.get(c, []))
                if under >= 0.0:
                    break
                target = rig.world(b, pose).copy()
                target.translation.z -= under - 0.002
                pose, _ = ChainIK(rig, LEG_DOFS(s), b if b != toes else foot).solve(pose, target, pos_only=True, iters=60)
    return pose


def plant_feet(rig, poses):
    """Hold each foot flat where it lands while it is planted (standing); then the floor: standing, where a sole would
    go below it the hips lift; lying or sitting on the ground, a foot digging in bends back and the hips lift only as
    far as Tensor's shell needs; the lift smoothed (never below what a frame needs). Returns the lowest ankle height
    reached."""
    n = len(poses)
    rest_ankle = rig.rest["LeftFoot"].translation.z
    upright = [(rig.world("Head", p).translation - rig.world("Hips", p).translation).normalized().z > UPRIGHT
               for p in poses]
    for s in ("Left", "Right"):
        foot = f"{s}Foot"
        ank = [rig.world(foot, p) for p in poses]
        low = [a.translation.z < rest_ankle + CONTACT_HEIGHT and up for a, up in zip(ank, upright)]
        spd = [0.0] + [(ank[i].translation.xy - ank[i - 1].translation.xy).length * FPS for i in range(1, n)]
        planted = [low[i] and spd[i] < CONTACT_SPEED for i in range(n)]
        spans, i = [], 0
        while i < n:
            if planted[i]:
                j = i
                while j + 1 < n and planted[j + 1]:
                    j += 1
                if j - i >= 2:
                    spans.append((i, j))
                i = j + 1
            else:
                i += 1
        ik = ChainIK(rig, LEG_DOFS(s), foot, rot_weight=0.2)
        rest_rot = rig.rest[foot].to_3x3()
        for a, b in spans:
            mid = sum((ank[k].translation for k in range(a, b + 1)), Vector()) / (b - a + 1)
            fwd = sum((ank[k].to_3x3() @ Vector((0, 1, 0)) for k in range(a, b + 1)), Vector())
            yaw = math.atan2(fwd.y, fwd.x) - math.atan2((rest_rot @ Vector((0, 1, 0))).y, (rest_rot @ Vector((0, 1, 0))).x)
            target = (Matrix.Rotation(yaw, 3, "Z") @ rest_rot).to_4x4()
            target.translation = Vector((mid.x, mid.y, rest_ankle))
            ease = 3
            for k in range(max(0, a - ease), min(n, b + ease + 1)):
                w = 1.0 if a <= k <= b else 1.0 - (min(abs(k - a), abs(k - b)) / (ease + 1))
                goal = target.copy()
                if w < 1.0:  # blend from the free foot toward the planted one near the span's ends
                    goal.translation = ank[k].translation.lerp(target.translation, w)
                    goal = (ank[k].to_3x3().to_quaternion().slerp(target.to_3x3().to_quaternion(), w)).to_matrix().to_4x4()
                    goal.translation = ank[k].translation.lerp(target.translation, w)
                poses[k], _ = ik.solve(poses[k], goal)
    # The floor: each sole's heel, ball and toe tip; where one would go below it, the hips lift.
    soles = []
    for s in ("Left", "Right"):
        fr, tr = rig.rest[f"{s}Foot"], rig.rest[f"{s}Toes"]
        x = fr.translation.x
        soles += [(f"{s}Foot", fr.inverted() @ Vector((x, 0.10, 0.0))), (f"{s}Foot", fr.inverted() @ Vector((x, -0.12, 0.0))),
                  (f"{s}Toes", tr.inverted() @ Vector((x, -0.20, 0.0)))]
    pts = body_points(rig)
    shins = FEET + ("LeftLowerLeg", "RightLowerLeg")
    need = []
    for i, p in enumerate(poses):   # standing: the soles and the shell; lying: the shell above the knees (the legs fold)
        cache = {}
        low = min((rig.world(b, p, cache) @ v).z for b, vs in pts.items() if b not in shins for v in vs)
        if upright[i]:
            low = min(low, min((rig.world(b, p, cache) @ v).z for b, v in soles),
                      min((rig.world(b, p, cache) @ v).z for b in ("LeftLowerLeg", "RightLowerLeg") for v in pts.get(b, [])))
        need.append(max(0.0, -low))
    near = lambda i: need[max(0, i - 2):i + 3]                             # smoothed lightly, never below a frame's need
    lift = [max(need[i], sum(near(i)) / len(near(i))) for i in range(n)]
    if DEBUG:
        print("[retarget]     floor: " + " ".join(f"f{i}:{'U' if upright[i] else 'L'}{need[i] * 1000:.0f}/{lift[i] * 1000:.0f}"
                                                  for i in range(n)))
    lowest = 1e9
    for i, p in enumerate(poses):
        if lift[i] > 0.0:
            hw = rig.world(rig.parent["Hips"], p) @ rig.rel["Hips"]
            m = p["Hips"].copy()
            m.translation = m.translation + hw.to_3x3().inverted() @ Vector((0, 0, lift[i]))
            poses[i] = p = dict(p, Hips=m)
        if not upright[i]:
            poses[i] = p = fold_feet(rig, p, pts)
        cache = {}
        if upright[i]:
            lowest = min(lowest, min((rig.world(b, p, cache) @ v).z for b, v in soles))
        else:        # lying: the shell itself
            lowest = min(lowest, min((rig.world(b, p, cache) @ v).z for b, vs in pts.items() for v in vs))
    return lowest


# ----------------------------------------------------------------------------------- apply & export
def open_tensor():
    bpy.ops.wm.open_mainfile(filepath=str(CHAR / "tensor.blend"))
    rig = bpy.data.objects["RIG_Tensor"]
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            bpy.data.objects.remove(o)
    return rig


def key_poses(arm, poses, name):
    act = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = act
    for i, pose in enumerate(poses):
        for b, m in pose.items():
            pb = arm.pose.bones[b]
            if b in ("Root", "Hips"):
                pb.location = m.translation
                pb.keyframe_insert("location", frame=i)
            if pb.rotation_mode == "QUATERNION":
                pb.rotation_quaternion = m.to_quaternion()
                pb.keyframe_insert("rotation_quaternion", frame=i)
            else:
                pb.rotation_euler = m.to_3x3().to_euler(pb.rotation_mode)
                pb.keyframe_insert("rotation_euler", frame=i)
    return act


def bake_and_export(arm, name, n, path):
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 0, n - 1
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        o.select_set(o == arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.nla.bake(frame_start=0, frame_end=n - 1, only_selected=True, visual_keying=True, clear_constraints=True,
                     use_current_action=True, bake_types={"POSE"})
    bpy.ops.object.mode_set(mode="OBJECT")
    act = arm.animation_data.action
    act.name = name
    path.parent.mkdir(parents=True, exist_ok=True)
    lib = OUT / "blend" / path.relative_to(OUT).with_suffix(".blend")    # the baked action alone, for the videos
    lib.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(lib), {act}, fake_user=True, compress=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIVE_ACTIONS", export_force_sampling=True, export_yup=True,
                              export_def_bones=False, export_frame_range=True)


# ----------------------------------------------------------------------------------- weapons
def fcurves_of(action):
    """An action's F-curves (5.x layered actions: through their channel bags)."""
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out or list(getattr(action, "fcurves", []))


def socket_matrix(h):
    """A hand socket from its _rig.json entry: the hand bone's frame on the grip (in the weapon's rest space)."""
    m = Matrix((h["bone_x_blender"], h["bone_y_blender"], h["bone_z_blender"])).transposed().to_4x4()
    m.translation = h["wrist_blender"]
    return m


def weapon_rig(objects):
    """The weapon's own rig: the armature its visible body mesh rides (a projectile weapon's file also holds the
    projectile's rig)."""
    body = next(o for o in objects if o.type == "MESH" and o.name.startswith("SK_") and not o.hide_render
                and o.parent and o.parent.type == "ARMATURE")
    return body.parent


def load_weapon(w):
    """A weapon's hand sockets and grip poses (from its _rig.json: the two grips and the ammo pack's), and from its
    .blend: its rig's name, the ammo pack's rest and every action sampled per frame ({name: [ {(data_path, index):
    value} ]})."""
    info = json.loads((WEAPONS / w / f"{w}_rig.json").read_text())
    socks = {}
    for side in ("Left", "Right"):
        h = info["hand_sockets"][f"{side}HandSocket"]
        socks[side] = (socket_matrix(h), h["grip_pose_deg"])
    ammo = info.get("ammo_hand_socket")
    bpy.ops.wm.open_mainfile(filepath=str(WEAPONS / w / f"{w}.blend"))
    rig = weapon_rig(bpy.context.scene.objects)
    mag = rig.data.bones.get("Mag")
    actions = {}
    for act in bpy.data.actions:
        f0, f1 = (int(round(v)) for v in act.frame_range)
        curves = fcurves_of(act)
        actions[act.name] = [{(fc.data_path, fc.array_index): fc.evaluate(f) for fc in curves} for f in range(f0, f1 + 1)]
    body = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.parent == rig and not o.hide_render]
    pts = np.array([tuple(o.matrix_world @ v.co) for o in body for v in o.data.vertices])   # its shape, for arm clashes
    return {"name": w, "rig": rig.name, "socks": socks, "pts": pts,
            "mag_rest": mag.matrix_local.copy() if mag else None,
            "mag_mode": rig.pose.bones["Mag"].rotation_mode if mag else None,
            "ammo_sock": (socket_matrix(ammo), ammo["grip_pose_deg"]) if ammo and mag else None,
            "actions": actions, "family": WEAPON_FAMILY[w]}


def mag_frame(wpn, vals):
    """The ammo pack's frame in the weapon's space from an action's sampled values (its rest where they're silent)."""
    pb = 'pose.bones["Mag"].'
    loc = Vector([vals.get((pb + "location", i), 0.0) for i in range(3)])
    if wpn["mag_mode"] == "QUATERNION":
        rot = Quaternion([vals.get((pb + "rotation_quaternion", i), 1.0 if i == 0 else 0.0) for i in range(4)]).to_matrix()
    else:
        rot = Euler([vals.get((pb + "rotation_euler", i), 0.0) for i in range(3)], wpn["mag_mode"]).to_matrix()
    return wpn["mag_rest"] @ Matrix.LocRotScale(loc, rot, None)


def arm_clash(rig, pose, side, place, wpn):
    """How deep one of Tensor's arms runs into the weapon at `place` (m): its upper arm and forearm as capsules
    (ARM_R) round their bones, against the weapon's vertices, the forearm's last WRIST_FREE left out (user: an arm
    through a weapon; the hold put the hands exactly on their sockets whichever way round the arm went)."""
    wc = {}
    inv = place.inverted()
    joints = [inv @ rig.world(f"{side}{b}", pose, wc).translation for b in ("UpperArm", "LowerArm", "Hand")]
    pts, deep = wpn["pts"], 0.0
    for (a, b), r, free in ((joints[:2], ARM_R[0], 0.0), (joints[1:], ARM_R[1], WRIST_FREE)):
        a, ab = np.array(tuple(a)), np.array(tuple(b - a))
        l2 = float(ab @ ab)
        t = (pts - a) @ ab / l2
        keep = (t >= 0.0) & (t <= 1.0 - free / math.sqrt(l2))
        if keep.any():
            d = np.linalg.norm(pts[keep] - (a + np.outer(t[keep], ab)), axis=1)
            deep = max(deep, float(r - d.min()))
    return max(deep, 0.0)


TORSO_BOXES = ("Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftShoulder", "RightShoulder")


def body_clash(rig, pose, place, wpn, shrink=0.008):
    """How deep the weapon at `place` runs into Tensor's torso and head (m): each bone's box round its shell's extreme
    points (body_points), shrunk `shrink` (a box is fuller than his keeled, chamfered shell), against the weapon's
    vertices."""
    deep, wc = 0.0, {}
    for b in TORSO_BOXES:
        pts = BODY_PTS.get(b)
        if not pts:
            continue
        lo = np.array([min(q[i] for q in pts) for i in range(3)]) + shrink
        hi = np.array([max(q[i] for q in pts) for i in range(3)]) - shrink
        m = (rig.world(b, pose, wc) @ rig.rest[b].inverted()).inverted() @ place   # weapon space -> the bone's rest frame
        r = np.array([list(m.to_3x3()[i]) for i in range(3)])
        local = wpn["pts"] @ r.T + np.array(tuple(m.translation))
        inside = np.all((local > lo) & (local < hi), axis=1)
        if inside.any():
            q = local[inside]
            deep = max(deep, float(np.minimum(q - lo, hi - q).min(axis=1).max()))
    return deep


def reload_carry(rig, seat, wpn, guides=None):
    """Where Tensor carries the weapon through a reload (user: it may turn and tilt then, nothing is shot; the hands'
    accuracy first): from the held aiming idle (`seat`), the weapon in the firing hand and his left hand on the released
    pack's AmmoHandSocket, both arms and the torso (RELOAD_TORSO) solved together toward guides lowered, drawn in and
    rolled toward the support hand; the one with the least miss kept, an arm in the weapon or the weapon in his torso
    counting against it. (Held where he aims it, no pack socket is within his left hand's reach: 31 to 133 mm off.)
    With `guides` (the weapon placed where the reference weapon's reload carries its firing hand: one reload for all,
    user) it is held to them firmly, only the left hand going to this weapon's pack, and eased off them only as far
    as the pack needs. Returns (the weapon's frame on the upper chest, which it rides wholly, turning as the chest
    leans and twists through the reload, as the shoulders the arms hang from do; the pose; its miss)."""
    sr = wpn["socks"]["Right"][0]
    place = rig.world("RightHand", seat) @ sr.inverted()
    rel = [mag_frame(wpn, v) for v in wpn["actions"].get("mag_release", [])] or [wpn["mag_rest"]]
    target = rel[-1] @ wpn["mag_rest"].inverted() @ wpn["ammo_sock"][0]      # the released pack's socket, weapon space
    facing = facing_of(rig, seat)
    fwd, left, up = facing @ Vector((0, -1, 0)), facing @ Vector((1, 0, 0)), facing @ Vector((0, 0, 1))
    pivot = (place @ sr).translation

    def attempt(start, guide, iters, guide_w):
        ik = TwoHandIK(rig, sr, sr, support=True, prior=0.0001, torso=RELOAD_TORSO)
        ik.rel, ik.GUIDE, ik.AIM = sr.inverted() @ target, guide_w, 0.02
        solved, _ = ik.solve_pair(start, guide @ sr, iters=iters)
        pl = rig.world("RightHand", solved) @ sr.inverted()
        miss = socket_miss(rig.world("LeftHand", solved), pl @ target)
        key = miss + CLASH_W * (max(0.0, body_clash(rig, solved, pl, wpn) - 0.004)
                                + max(0.0, max(arm_clash(rig, solved, s, pl, wpn) for s in ("Left", "Right")) - CLASH_TOL))
        return key, miss, solved, pl

    reach = ChainIK(rig, ARM_DOFS("Left"), "LeftHand", rot_weight=SOCKET_W)
    starts = [seat] + [reach.write(seat, q) for q in arm_starts(rig, seat, "Left", place @ target, k=2)]
    best = None                                   # (from his arm as held, and with it already reaching for the pack:
    if guides is None:                            # over the top of a gun it may not move at all from the first)
        guides = [Matrix.Translation(pivot - up * down + left * inward) @ Matrix.Rotation(math.radians(roll), 4, fwd)
                  @ Matrix.Translation(-pivot) @ place
                  for down in (0.0, 0.10, 0.20) for inward in (0.0, 0.08, 0.16) for roll in (0, 25, 50)]
        firm = 0.05
    else:
        firm = 0.3
    for start in starts:
        for guide in guides:
            got = attempt(start, guide, 60, firm)
            if best is None or got[0] < best[0] - 1e-4:
                best = got + (guide,)
    for guide_w in (firm / 3, firm / 10, 0.0):                       # then settle it from there, off the guide
        if best[1] <= TOL_HAND * 0.5:                                # only as far as the pack needs
            break
        got = attempt(best[2], best[4], 120, guide_w)
        if got[0] < best[0] - 1e-4:
            best = got + (best[4],)
    key, miss, solved, pl, _ = best
    return rig.world("UpperChest", solved).inverted() @ pl, solved, miss   # (riding the chest, as the arms do)


def placements(rig, poses, wpn, mode, calib, align=None):
    """The weapon's world frame on every frame: riding the (calibrated) right hand natively, aligned to Tensor's
    facing (aligned), or riding the upper chest as in the
    aiming idle (a sprint: "chest", "chest_facing"); each family's weapon its drop lower."""
    align = align or {}
    fam = FAMILIES[wpn["family"]]
    drop = Matrix.Translation((0, 0, -fam.get("drop", 0.0)))
    sr = wpn["socks"]["Right"][0]
    out = []
    for i, p in enumerate(poses):
        if mode == "chest_facing":   # riding the upper chest's place as in the aiming idle, turned with the facing
            out.append(carry_frame(rig, p, "UpperChest") @ calib["CHEST"])
        elif mode == "reload_carry":  # where a reload has it (reload_carry), riding the upper chest
            out.append(rig.world("UpperChest", p) @ calib["RELOAD"])
        elif mode == "chest":  # its grip where the aiming idle has it on the upper chest, pointing where Tensor faces
            grip = rig.world("UpperChest", p) @ calib["CHEST_GRIP"]
            facing = rig.world("Root", p).to_3x3() @ rig.rest["Root"].to_3x3().transposed()
            rot = facing @ calib["CHEST"].to_3x3()
            m = rot.to_4x4()
            m.translation = grip - rot @ sr.translation
            out.append(m)
        else:
            h = rig.world("RightHand", p)
            t = (h.to_3x3() @ calib["C"]).to_4x4()
            t.translation = h.translation
            w = drop @ t @ sr.inverted() @ calib["SHIFT"]
            if align.get("free"):
                out.append(w)                                   # (a reload: as the source's hand has it)
            elif align.get("phase"):                            # (a reload: straight while both hands hold it, as the
                a, u = aligned(rig, p, w, sr), align["phase"][i]  # source's hand has it while the support hand is off)
                rot = a.to_3x3().to_quaternion().slerp(w.to_3x3().to_quaternion(), u).to_matrix()
                m = rot.to_4x4()
                m.translation = (w @ sr).translation - rot @ sr.translation
                out.append(m)
            else:
                out.append(aligned(rig, p, w, sr))
    return out


def calibrate(rig, ref, wpn):
    """A weapon's calibration in a source family's (squared) aiming idle `ref`: level and straight ahead in the firing
    hand ("C"); where it sits from that hand ("SHIFT", in the weapon's frame): its HOLDS place (side, and the firing
    wrist from the right shoulder), or its family's `drop` under the source's hands with its grips centred between
    them (its grips may be spaced unlike the source's weapon, so each arm takes half the difference) at its side. Its place on the upper chest for the chest holds ("CHEST", "CHEST_GRIP")."""
    fam = FAMILIES[wpn["family"]]
    held = HOLDS.get(wpn["name"])
    sr, sl = wpn["socks"]["Right"][0], wpn["socks"]["Left"][0]
    h = rig.world("RightHand", ref)
    c = {"C": h.to_3x3().inverted() @ sr.to_3x3()}
    place = (h.to_3x3() @ c["C"]).to_4x4()
    place.translation = h.translation
    weapon_ref = place @ sr.inverted()
    facing = facing_of(rig, ref)
    local = lambda b: facing.transposed() @ rig.world(b, ref).translation
    if held:
        ref_sr = sr
        if isinstance(held, str):                  # the reference weapon's hold: its firing wrist exactly there
            ref_sr = socket_matrix(json.loads((WEAPONS / held / f"{held}_rig.json").read_text())["hand_sockets"]
                                   ["RightHandSocket"])
            held = HOLDS[held]
        side, (ahead, up) = held
        wrist = Vector((local("UpperChest").x + side + ref_sr.translation.x,
                        local("RightUpperArm").y - ahead, local("RightUpperArm").z + up))
        at = wrist - sr.translation                                 # (the weapon's +X his left, -Y ahead)
        want = facing.to_4x4()
        want.translation = facing @ at
        c["SHIFT"] = weapon_ref.inverted() @ want
    else:
        mid_w = ((weapon_ref @ sr).translation + (weapon_ref @ sl).translation) / 2
        mid_s = (h.translation + rig.world("LeftHand", ref).translation) / 2
        c["SHIFT"] = Matrix.Translation(weapon_ref.to_3x3().inverted() @ (mid_s - mid_w))
        place_ref = placements(rig, [ref], wpn, "native", c)[0]
        x = (facing.transposed() @ (place_ref.translation - rig.world("UpperChest", ref).translation)).x
        c["SHIFT"] = c["SHIFT"] @ Matrix.Translation((fam["side"] - x, 0.0, 0.0))
    place_ref = placements(rig, [ref], wpn, "native", c)[0]
    c["CHEST"] = carry_frame(rig, ref, "UpperChest").inverted() @ place_ref               # its turn from the facing
    c["CHEST_GRIP"] = rig.world("UpperChest", ref).inverted() @ (place_ref @ sr).translation   # its grip on the chest
    return c


def seat(rig, ref, wpn, calib, ref_grip, steps=12):
    """The aiming idle held: Tensor's arms solved onto the calibrated weapon, reached in steps from the weapon in the
    source's hand (each step from the one before, so the arms carry over; solved at once from the actor's arms they
    can stick short of a raised weapon). A start for the holds."""
    end = placements(rig, [ref], wpn, "native", calib)[0]
    h = rig.world("RightHand", ref)
    start = (h.to_3x3() @ calib["C"]).to_4x4()
    start.translation = h.translation
    start = start @ wpn["socks"]["Right"][0].inverted()
    guides = []
    for k in range(steps + 1):
        u = k / steps
        m = start.to_quaternion().slerp(end.to_quaternion(), u).to_matrix().to_4x4()
        m.translation = start.translation.lerp(end.translation, u)
        guides.append(m)
    poses, placed = hold(rig, [ref] * (steps + 1), wpn, guides, ref_grip)[:2]
    seat.miss, seat.aim = hold.per_frame[-1], socket_error(placed[-1], end)[1]
    return poses[-1]


def reference_carry(rig, ref, ref_grip):
    """The reference weapon's reload carry in the rifle aiming idle `ref` (computed once): (its weapon, its seat, its
    frame on the upper chest)."""
    if not hasattr(reference_carry, "got"):
        wpn = load_weapon(REFERENCE)
        c = calibrate(rig, ref, wpn)
        st = seat(rig, ref, wpn, c, ref_grip)
        reference_carry.got = (wpn, st, reload_carry(rig, st, wpn)[0])
    return reference_carry.got


def facing_of(rig, pose):
    """Where Tensor faces: the Root's turn from its rest (3x3)."""
    return rig.world("Root", pose).to_3x3() @ rig.rest["Root"].to_3x3().transposed()


def face_front(rig, poses):
    """With a weapon in hand the chest and the head face front (user: never turned or tilted left or right, only
    leaning or nodding back and forth): the spine's twist and side bend take the upper chest's turn and roll from the
    facing to nothing (its lean kept), then the neck's turn the head's (each within its limits, from the frame
    before). Returns new poses."""
    parts = []
    for dofs, end, roll in (([(b, i) for b in ("Spine", "Chest", "UpperChest") for i in (1, 2)], "UpperChest", True),
                            ([("Neck", 1)], "Head", False)):
        dofs = [(b, i) for b, i in dofs if rig.limits[b]["limits_deg"].get("xyz"[i], (0, 0))[1]
                > rig.limits[b]["limits_deg"].get("xyz"[i], (0, 0))[0]]
        parts.append((ChainIK(rig, dofs, end), end, roll))
    out, prev = [], {}
    for pose in poses:
        pose = dict(pose)
        facing = facing_of(rig, pose)
        for ik, end, roll in parts:
            r0 = rig.rest[end].to_3x3()

            def residual(q):
                d = facing.transposed() @ rig.world(end, ik.write(pose, q)).to_3x3() @ r0.transposed()
                f, side = d @ Vector((0.0, -1.0, 0.0)), d @ Vector((1.0, 0.0, 0.0))
                r = [math.atan2(f.x, -f.y)]
                return r + [math.asin(max(-1.0, min(1.0, side.z)))] if roll else r

            q = [min(max(v, lo), hi) for v, (lo, hi) in zip(prev.get(end) or ik.read(pose), ik.bounds)]
            q_src = ik.read(pose)
            for _ in range(30):
                r = residual(q) + [(a - b) * 0.002 for a, b in zip(q, q_src)]   # (a light pull to the source's)
                e = sum(v * v for v in r)
                if e < 1e-9:
                    break
                jac = []
                for k in range(len(q)):
                    dq = list(q)
                    dq[k] += 0.2
                    rk = residual(dq) + [(a - b) * 0.002 for a, b in zip(dq, q_src)]
                    jac.append([(x - y) / 0.2 for x, y in zip(rk, r)])
                n = len(q)
                a = [[sum(x * y for x, y in zip(jac[u], jac[v])) + (1e-8 if u == v else 0.0) for v in range(n)] for u in range(n)]
                b = [-sum(x * y for x, y in zip(jac[u], r)) for u in range(n)]
                step = gauss(a, b)
                for t in (1.0, 0.5, 0.25, 0.125):
                    trial = [min(max(v + t * dv, lo), hi) for v, dv, (lo, hi) in zip(q, step, ik.bounds)]
                    if sum(v * v for v in residual(trial) + [(x - y) * 0.002 for x, y in zip(trial, q_src)]) < e:
                        q = trial
                        break
                else:
                    break
            pose = ik.write(pose, q)
            prev[end] = q
        out.append(pose)
    return out


def chest_turn(rig, pose):
    """The upper chest's turn from the facing (rad)."""
    d = facing_of(rig, pose).transposed() @ rig.world("UpperChest", pose).to_3x3() @ rig.rest["UpperChest"].to_3x3().transposed()
    f = d @ Vector((0.0, -1.0, 0.0))
    return math.atan2(f.x, -f.y)


def squared(rig, poses):
    """face_front, and where the source's hips turn further than the spine can take back (a strafe, a sprint), the hips
    turn the rest (smoothed) and the feet are planted again first. Returns new poses."""
    poses = face_front(rig, poses)
    rest = smooth_series([chest_turn(rig, p) for p in poses], 5)
    if max(abs(v) for v in rest) < math.radians(2.0):
        return poses
    out = []
    for p, a in zip(poses, rest):
        m = rig.world(rig.parent["Hips"], p) @ rig.rel["Hips"]
        w = m @ p["Hips"]
        turn = Matrix.Translation(w.translation) @ Matrix.Rotation(-a, 4, "Z") @ Matrix.Translation(-w.translation)
        out.append(dict(p, Hips=m.inverted() @ turn @ w))
    plant_feet(rig, out)
    return face_front(rig, out)


def aligned(rig, pose, w, sr, limit=0.0):
    """A weapon frame straight at Tensor's facing (user: no turn, roll or pitch while it's held; only an aim pose
    pitches it), about its firing grip, which stays where the source's hand put it; with `limit` (deg, a reload) its
    turn, roll and pitch from the facing held softly within that instead."""
    rot = facing_of(rig, pose)
    if limit:
        r = rot.transposed() @ w.to_3x3()
        f = r @ Vector((0.0, -1.0, 0.0))
        yaw, pitch = math.atan2(f.x, -f.y), math.asin(max(-1.0, min(1.0, f.z)))
        m = (Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(-pitch, 3, "X")).transposed() @ r
        roll = math.atan2(m[0][2], m[0][0])
        yaw, pitch, roll = (math.radians(limit) * math.tanh(v / math.radians(limit)) for v in (yaw, pitch, roll))
        rot = rot @ Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(-pitch, 3, "X") @ Matrix.Rotation(roll, 3, "Y")
    grip = (w @ sr).translation
    out = rot.to_4x4()
    out.translation = grip - rot @ sr.translation
    return out


def carry_frame(rig, pose, bone):
    """A frame at a bone's position facing where Tensor faces (the Root's yaw), so a turned stance doesn't swing
    what rides it off its line (a sprint's weapon on the upper chest)."""
    root = rig.world("Root", pose).to_3x3()
    m = (root @ rig.rest["Root"].to_3x3().transposed()).to_4x4()
    m.translation = rig.world(bone, pose).translation
    return m


def blend_places(on, off, phase):
    """Weapon frames blended per frame from `on` to `off` by `phase` (0..1): place and turn."""
    out = []
    for a, b, u in zip(on, off, phase):
        rot = a.to_3x3().to_quaternion().slerp(b.to_3x3().to_quaternion(), u).to_matrix()
        m = rot.to_4x4()
        m.translation = a.translation.lerp(b.translation, u)
        out.append(m)
    return out


def off_grip(rig, poses, ref_grip):
    """How far the source's support hand is off its two-handed grip on each frame (0 on it, 1 off it): the hold's own
    letting go (so the weapon never turns while the support hand is on its grip)."""
    out = []
    for p in poses:
        w = 1.0 - smoothstep(((hand_to_hand(rig, p) - ref_grip).length - SUPPORT_NEAR) / (SUPPORT_FAR - SUPPORT_NEAR))
        out.append(0.0 if w > 0.9 else 1.0 if w < 0.1 else 1.0 - w)
    return out


def hand_to_hand(rig, pose):
    """Where the left hand is in the right hand's frame: how a two-handed grip reads."""
    return rig.world("RightHand", pose).inverted() @ rig.world("LeftHand", pose).translation


class TwoHandIK(ChainIK):
    """The torso and both arms at once, the weapon in the firing hand: the firing hand pulled toward its
    guide (softly), the support hand on its socket wherever the weapon then is (firmly), the torso kept near
    the source's."""

    PRIOR, GUIDE, AIM = 0.001, 0.3, AIM_W

    def __init__(self, rig, sr, sl, support=True, prior=None, torso=TORSO_DOFS):
        dofs = torso + ARM_DOFS("Right") + (ARM_DOFS("Left") if support else [])
        super().__init__(rig, dofs, None, 0.05)
        if prior is not None:
            self.PRIOR = prior
        self.rel = sr.inverted() @ sl                        # the support grip in the firing hand's frame
        self.support = support
        self.prior = list(range(len(torso)))

    def solve_pair(self, pose, guide, iters=40):
        rig, q_src = self.rig, self.read(pose)
        q = list(q_src)

        def residual(q):
            new, cache = self.write(pose, q), {}
            h = rig.world("RightHand", new, cache)
            d = (h.translation - guide.translation) * self.GUIDE
            ex = (h.col[0].xyz - guide.col[0].xyz) * self.AIM        # the weapon's turn firmly, its place softly
            ey = (h.col[1].xyz - guide.col[1].xyz) * self.AIM
            r = [d.x, d.y, d.z, ex.x, ex.y, ex.z, ey.x, ey.y, ey.z]
            if self.support:
                r += socket_residual(rig.world("LeftHand", new, cache), h @ self.rel)
            return r + [(q[i] - q_src[i]) * self.PRIOR for i in self.prior]

        clampq = lambda q: [min(max(v, lo), hi) for v, (lo, hi) in zip(q, self.bounds)]
        for _ in range(iters):
            r = residual(q)
            e = sum(v * v for v in r)
            jac = []
            for j in range(len(q)):
                dq = list(q)
                dq[j] += 0.2
                rj = residual(dq)
                jac.append([(a - b) / 0.2 for a, b in zip(rj, r)])
            nq = len(q)
            a = [[sum(x * y for x, y in zip(jac[j], jac[k])) + (1e-8 if j == k else 0.0) for k in range(nq)] for j in range(nq)]
            b = [-sum(x * y for x, y in zip(jac[j], r)) for j in range(nq)]
            step = gauss(a, b)
            big = max(abs(v) for v in step) or 1.0
            if big > 12:
                step = [v * 12 / big for v in step]
            for t in (1.0, 0.5, 0.25, 0.125):
                trial = clampq([v + t * dv for v, dv in zip(q, step)])
                if sum(v * v for v in residual(trial)) < e:
                    q = trial
                    break
            else:
                break
        new = self.write(pose, q)
        h = rig.world("RightHand", new)
        miss = socket_miss(rig.world("LeftHand", new), h @ self.rel) if self.support else 0.0
        return new, miss


def hold(rig, poses, wpn, guides, ref_grip, let_go=False, seed=None):
    """Both hands on the weapon, the weapon in the firing hand. The firing arm reaches for its guide (the
    placement's socket) and the weapon hangs from wherever that hand lands (so it is always exactly in the
    hand, as it is in the game); the support hand is put exactly on its socket (LeftHandSocket: the grip, as the
    weapon's model places it) while its source hand keeps the two-handed grip it has in its family's aiming idle
    (user: the hands stick to their sockets, so only a reload, `let_go`, lets it go). A forward pass solves
    each frame from the one before, a backward pass retries a miss from the frame after, and a support hand
    still off its grip gets the torso and the firing arm to help. `seed`, a pose known to hold the weapon (the family's
    aiming idle), gives both arms another start. Fingers close to the grip poses.
    Returns (poses, weapon placements, worst support miss, support weights)."""
    (sr, grip_r), (sl, grip_l) = wpn["socks"]["Right"], wpn["socks"]["Left"]
    n = len(poses)
    weights = []
    for x in ((hand_to_hand(rig, p) - ref_grip).length if let_go else 0.0 for p in poses):
        w = 1.0 - smoothstep((x - SUPPORT_NEAR) / (SUPPORT_FAR - SUPPORT_NEAR))
        weights.append(1.0 if w > 0.9 else 0.0 if w < 0.1 else w)   # a grip is held or let go, not half-held
    fire = ChainIK(rig, ARM_DOFS("Right"), "RightHand", rot_weight=AIM_W)
    reach = {s: ChainIK(rig, ARM_DOFS(s), f"{s}Hand") for s in ("Left", "Right")}
    support = ChainIK(rig, ARM_DOFS("Left"), "LeftHand", rot_weight=SOCKET_W)
    work, place = [], []
    q_prev = None
    for i in range(n):                                       # the firing hand, then the weapon in it
        g = guides[i] @ sr
        reach["Right"].solve(poses[i], g, pos_only=True, iters=40)
        best = None
        def aim(q0, iters):
            nonlocal best
            solved, err = fire.solve(poses[i], g, q0=q0, iters=iters)
            err += fire.turn * 0.002                         # its turn counts as much as its place (2 mm a degree)
            c = arm_clash(rig, solved, "Right", rig.world("RightHand", solved) @ sr.inverted(), wpn)
            key = err + CLASH_W * max(0.0, c - CLASH_TOL)
            if best is None or key < best[3] - 1e-4:
                best = (solved, err, fire.last, key)

        for q0 in ([q_prev] if q_prev else []) + [None, reach["Right"].last] + ([fire.read(seed)] if seed else []):
            aim(q0, 40)
        if best[3] > TOL_HAND:                               # short of it or through it: from the global starts
            for q0 in arm_starts(rig, poses[i], "Right", g, k=8):
                aim(q0, 60)
                if best[3] <= TOL_HAND:
                    break
        work.append(best[0])
        q_prev = best[2]
        place.append(rig.world("RightHand", best[0]) @ sr.inverted())
    q = [None] * n
    err = [0.0] * n

    def grip(i, starts):
        best = None
        t = place[i] @ sl

        def take(q0, iters):
            nonlocal best
            solved, _ = support.solve(work[i], t, q0=q0, iters=iters)
            e = socket_miss(rig.world("LeftHand", solved), t)
            key = e + CLASH_W * max(0.0, arm_clash(rig, solved, "Left", place[i], wpn) - CLASH_TOL)
            if best is None or key < best[3] - 1e-4:
                best = (solved, e, support.last, key)

        for q0 in starts:
            take(q0, 40)
            if best[3] < 0.0005:
                break
        if best[3] > TOL_HAND:                               # short of it or through it: from the global starts
            for q0 in arm_starts(rig, work[i], "Left", t, k=8):
                take(q0, 60)
                if best[3] <= TOL_HAND:
                    break
        return best[:3]

    for i in range(n):                                       # forward
        if weights[i] <= 0.0:
            continue
        reach["Left"].solve(work[i], place[i] @ sl, pos_only=True, iters=40)
        starts = ([q[i - 1]] if i and q[i - 1] else []) + [None, reach["Left"].last] + ([support.read(seed)] if seed else [])
        _, err[i], q[i] = grip(i, starts)
    for i in range(n - 2, -1, -1):                           # backward
        if q[i] and q[i + 1] and err[i] > TOL_HAND:
            _, e, qq = grip(i, [q[i + 1]])
            if e < err[i]:
                err[i], q[i] = e, qq
    for i in range(1, n - 1):                                # a lone miss: from its neighbours' average
        if q[i] and q[i - 1] and q[i + 1] and err[i] > TOL_HAND:
            _, e, qq = grip(i, [[(a + b) / 2 for a, b in zip(q[i - 1], q[i + 1])]])
            if e < err[i]:
                err[i], q[i] = e, qq
    out, worst, miss, per_frame, aim_worst = [], 0.0, (0.0, -1), [], 0.0
    aim_err = lambda i: socket_error(place[i], guides[i])[1]   # how far the weapon is turned from where it points
    for i in range(n):
        pose, wl = dict(work[i]), weights[i]
        if wl > 0.0 and q[i]:
            if wl >= 1.0:
                pose = support.write(pose, q[i])
            else:   # taking hold or letting go: the arm's joints between the source's and the grip's
                q_src = support.read(work[i])
                pose = support.write(pose, [a + (b - a) * wl for a, b in zip(q_src, q[i])])
        e_now = err[i] if wl >= 1.0 else 0.0
        a_now = aim_err(i)
        for prior in (None, 0.0001):                         # the torso and the firing arm help (the torso freer
            if e_now <= TOL_HAND and a_now <= TOL_AIM:        # from the source's the second time)
                break
            solved, e2 = TwoHandIK(rig, sr, sl, support=wl >= 1.0, prior=prior).solve_pair(pose, guides[i] @ sr)
            was = place[i]
            place[i] = rig.world("RightHand", solved) @ sr.inverted()
            a2 = aim_err(i)
            if max(e2, a2 * TOL_HAND / TOL_AIM) < max(e_now, a_now * TOL_HAND / TOL_AIM):
                pose, e_now, a_now = solved, e2, a2
            else:
                place[i] = was
        aim_worst = max(aim_worst, a_now)
        per_frame.append(e_now)
        if e_now > miss[0]:
            miss = (e_now, i)
        worst = max(worst, e_now)
        for side, grip_pose, weight in (("Right", grip_r, 1.0), ("Left", grip_l, wl)):
            for bone, rot in grip_pose.items():
                if bone not in pose or weight <= 0.0:
                    continue
                order = rig.order[bone]
                cur = pose[bone].to_3x3().to_euler(order)
                tgt = [math.radians(v) for v in rot]
                pose[bone] = Euler([a + (b - a) * weight for a, b in zip(cur, tgt)], order).to_matrix().to_4x4()
        if DEBUG:
            print(f"[retarget]     f{i} support {wl:.2f} miss {e_now * 1000:.1f}")
        out.append(pose)
    hold.miss = {"Left": miss, "Right": (0.0, -1)}
    hold.clash = [max(arm_clash(rig, pose, "Right", place[i], wpn),
                      arm_clash(rig, pose, "Left", place[i], wpn) if weights[i] >= 1.0 else 0.0)
                  for i, pose in enumerate(out)]                  # each frame's deepest arm in the weapon
    hold.aim = aim_worst
    hold.per_frame = per_frame
    return out, place, worst, weights


def smoothstep(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def weapon_events(rig, poses, wpn, place, motion, weights):
    """What the weapon's own bones do over a clip: its fire loop through a fire clip, a reload (reload_pass), else its
    idle. Returns the poses (a reload moves the support hand) and the events."""
    if motion.startswith("fire"):
        return poses, {"kind": "fire"}
    if motion.startswith("reload") and wpn["ammo_sock"] is not None:
        return reload_pass(rig, poses, wpn, place, weights)
    return poses, {"kind": "idle"}


def actor_weapon(rig, poses, wpn, calib):
    """The weapon as the actor held it: its grip in the source's right hand (level in the aiming idle), not moved to
    where Tensor carries it."""
    sr = wpn["socks"]["Right"][0]
    out = []
    for p in poses:
        h = rig.world("RightHand", p)
        t = (h.to_3x3() @ calib["C"]).to_4x4()
        t.translation = h.translation
        out.append(t @ sr.inverted())
    return out


def free_hand_on_weapon(rig, poses, src, native, place, weights):
    """The support hand off its grip (a reload): where the source's hand is against the weapon as the actor held it
    (`native`, actor_weapon) it is put against the weapon as Tensor holds it, so the actor's reach for his magazine
    reaches this weapon's pack wherever it is carried (user: weapons on the right, at the shoulder). Returns the
    poses."""
    arm = ChainIK(rig, ARM_DOFS("Left"), "LeftHand", rot_weight=SOCKET_W)
    out, q_prev = [], None
    for f, pose in enumerate(poses):
        if weights[f] >= 1.0:
            out.append(pose)
            q_prev = None
            continue
        t = place[f] @ native[f].inverted() @ rig.world("LeftHand", src[f])
        arm.solve(pose, t, q0=q_prev, iters=40)
        q_prev = arm.last
        q_now = arm.read(pose)
        out.append(arm.write(pose, [a + (b - a) * (1.0 - weights[f]) for a, b in zip(q_now, arm.last)]))
    return out


def reload_pass(rig, poses, wpn, place, weights):
    """A reload through the ammo pack's socket (AmmoHandSocket, riding the pack): the pack runs out of its well
    (mag_release) and the support hand, easing onto the socket over AMMO_EASE frames, takes it where the source's
    hand, off its grip, first passes closest; the pack rides the hand exactly (pack = hand x socket^-1; eased in and out
    over the same frames, so a hand short of the socket doesn't snap it) until the hand,
    easing onto the socket where the released pack goes back, brings it there and pushes it home (mag_insert's travel,
    retimed to end before the source's hand moves on; the upper body holds still while it does), then lets go. Where the arm alone can't reach the socket the
    torso and the firing arm help (TwoHandIK; the weapon hangs from the firing hand wherever it goes). Returns the
    poses and the events (the pack's frame in the weapon's space on every frame)."""
    n = len(poses)
    acts = wpn["actions"]
    rel = [mag_frame(wpn, v) for v in acts.get("mag_release", [])] or [wpn["mag_rest"]]
    ins = [mag_frame(wpn, v) for v in acts.get("mag_insert", [])] or [wpn["mag_rest"]]
    sock, grip_pose = wpn["ammo_sock"]
    sr = wpn["socks"]["Right"][0]
    place = list(place)
    s_mag = wpn["mag_rest"].inverted() @ sock                      # the socket in the pack's frame
    out_frame = rel[-1]                                            # the pack released (free of its well)
    d = [(rig.world("LeftHand", p).translation - (w @ out_frame @ s_mag).translation).length for p, w in zip(poses, place)]
    minima = [i for i in range(2, n - 2) if d[i] <= min(d[i - 2:i + 3]) and weights[i] <= 0.0]   # off the grip
    grab = max(minima[0] if minima else int(n * 0.3), AMMO_EASE)
    put = minima[-1] if len(minima) > 1 and minima[-1] - grab >= 15 else int(n * 0.7)
    home = next((k for k, m in enumerate(ins) if (m.translation - wpn["mag_rest"].translation).length < 0.0005),
                len(ins) - 1) + 1                                # the insert's frames until the pack is seated
    put = min(put, n - home - AMMO_EASE - 1)                     # (before the grab is chosen: it stays 15 ahead)
    grab = max(AMMO_EASE, min(grab, put - 16))                   # (the pack carried at least 15 frames)
    probe, fits = ChainIK(rig, ARM_DOFS("Left"), "LeftHand", rot_weight=SOCKET_W), []
    for f in range(max(AMMO_EASE, grab - 4), min(put - 15, grab + 13)):   # the grab where the arm lands on the pack
        t = place[f] @ out_frame @ s_mag
        m = socket_miss(rig.world("LeftHand", probe.solve(poses[f], t, iters=40)[0]), t)
        for q0 in arm_starts(rig, poses[f], "Left", t, k=4) if m > TOL_HAND else []:   # (as the pass will solve it)
            m = min(m, socket_miss(rig.world("LeftHand", probe.solve(poses[f], t, q0=q0, iters=60)[0]), t))
            if m <= TOL_HAND:
                break
        fits.append((max(m, TOL_HAND * 0.3), abs(f - grab), f))   # (any frame it lands on, the nearest the source's)
    grab = min(fits)[2] if fits else grab
    stay = next((f for f in range(put + 1, put + home) if d[f] > d[put] + 0.03), put + home) - put
    push = max(3, min(home, stay))                               # the push home, over the source hand's stay

    def free(f):   # the pack on its own actions: released as the hand comes, pushed home, then the insert's rest
        if f < put:
            k = f - (grab - len(rel) + 1)
            return rel[min(k, len(rel) - 1)] if k >= 0 else wpn["mag_rest"]
        k = f - put
        if k < push:
            return ins[round(k * (home - 1) / max(push - 1, 1))]
        return ins[min(home - 1 + k - push + 1, len(ins) - 1)]

    # The hand on the socket: (weight, the pack's frame it holds it at) per frame.
    on = [None] * n
    for f in range(n):
        if grab - AMMO_EASE <= f <= grab:
            on[f] = (smoothstep((f - grab + AMMO_EASE) / AMMO_EASE), free(f))
        elif grab < f <= grab + AMMO_EASE:
            on[f] = (1.0 - smoothstep((f - grab) / AMMO_EASE), out_frame)
        elif put - AMMO_EASE <= f < put:
            on[f] = (smoothstep((f - put + AMMO_EASE) / AMMO_EASE), out_frame)
        elif put <= f < put + push:
            on[f] = (1.0, free(f))
        elif put + push <= f < put + push + AMMO_EASE:
            on[f] = (1.0 - smoothstep((f - put - push + 1) / AMMO_EASE), wpn["mag_rest"])
    arm = ChainIK(rig, ARM_DOFS("Left"), "LeftHand", rot_weight=SOCKET_W)
    out, q_prev, worst, held = [], None, 0.0, None
    for f, pose in enumerate(poses):
        pose = dict(pose)
        if held is not None and put < f < put + push + AMMO_EASE:
            # Pushing the pack home the upper body holds still (as it was when the hand brought the pack), then eases
            # back into the source's motion; the weapon hangs from the firing hand wherever that leaves it.
            u = smoothstep((f - put - push + 1) / AMMO_EASE) if f >= put + push else 0.0
            for b in UPPER_BODY:
                q = held[b].to_quaternion().slerp(pose[b].to_quaternion(), u)
                pose[b] = q.to_matrix().to_4x4()
            place[f] = rig.world("RightHand", pose) @ sr.inverted()
        if on[f] and on[f][0] > 0.0:
            wt, frame = on[f]
            target = place[f] @ frame @ s_mag
            best = None
            for q0 in ([q_prev] if q_prev else []) + [None]:
                solved, _ = arm.solve(pose, target, q0=q0, iters=40)
                e = socket_miss(rig.world("LeftHand", solved), target)
                if best is None or e < best[1] - 1e-4:
                    best = (arm.last, e)
            if best[1] > TOL_HAND:                               # (from the actor's arm it can land turned right round)
                for q0 in arm_starts(rig, pose, "Left", target, k=8):
                    solved, _ = arm.solve(pose, target, q0=q0, iters=60)
                    e = socket_miss(rig.world("LeftHand", solved), target)
                    if e < best[1] - 1e-4:
                        best = (arm.last, e)
                    if best[1] <= TOL_HAND:
                        break
            q_prev = best[0]
            e = best[1]
            reached = arm.write(pose, best[0])
            if e > TOL_HAND:                                     # the torso and the firing arm help
                helper = TwoHandIK(rig, sr, frame @ s_mag, torso=RELOAD_TORSO)
                solved, e2 = helper.solve_pair(reached, place[f] @ sr)
                if e2 < e:
                    q_now = helper.read(pose)
                    pose = helper.write(pose, [a + (b - a) * wt for a, b in zip(q_now, helper.read(solved))])
                    place[f] = rig.world("RightHand", pose) @ sr.inverted()
                    e = e2
                else:
                    q_now = arm.read(pose)
                    pose = arm.write(pose, [a + (b - a) * wt for a, b in zip(q_now, best[0])])
            else:
                q_now = arm.read(pose)
                pose = arm.write(pose, [a + (b - a) * wt for a, b in zip(q_now, best[0])])
            if wt >= 1.0:
                worst = max(worst, e)
            if DEBUG:
                pos, turn = socket_error(rig.world("LeftHand", pose), place[f] @ frame @ s_mag)
                print(f"[retarget]     ammo f{f} weight {wt:.2f} source hand {d[f] * 1000:.0f} mm off, "
                      f"now {pos * 1000:.1f} mm {turn:.1f} deg")
            for bone, rot in grip_pose.items():
                if bone in pose:
                    order = rig.order[bone]
                    cur = pose[bone].to_3x3().to_euler(order)
                    pose[bone] = Euler([a + (math.radians(b) - a) * wt for a, b in zip(cur, rot)], order).to_matrix().to_4x4()
        else:
            q_prev = None
        if f == put:
            held = dict(pose)
        out.append(pose)
    mags = []
    for f in range(n):
        if grab <= f < put:   # in the hand (easing from and back to where it's taken and put, as the hand does)
            in_hand = place[f].inverted() @ rig.world("LeftHand", out[f]) @ s_mag.inverted()
            u = smoothstep(min(1.0, (f - grab) / AMMO_EASE, (put - f) / AMMO_EASE))
            mags.append(Matrix.LocRotScale(out_frame.translation.lerp(in_hand.translation, u),
                                           out_frame.to_quaternion().slerp(in_hand.to_quaternion(), u), None))
        else:
            mags.append(free(f))
    reload_pass.miss = worst
    return out, {"kind": "reload", "grab": grab, "insert": put, "push": push, "mag": mags}


def export_weapon_clip(wpn, name, n, events, path):
    """The weapon's bones over the clip, from its own actions (and the ammo pack where a reload has it)."""
    bpy.ops.wm.open_mainfile(filepath=str(WEAPONS / wpn["name"] / f"{wpn['name']}.blend"))
    arm = bpy.data.objects[wpn["rig"]]
    for o in list(bpy.data.objects):
        if o != arm:
            bpy.data.objects.remove(o)
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    act = bpy.data.actions.new(name)
    arm.animation_data.action = act
    acts = wpn["actions"]
    if events["kind"] == "reload":   # out of its well the pack is free: off its rails' limit
        mag = arm.pose.bones["Mag"]
        for c in [c for c in mag.constraints if c.type == "LIMIT_LOCATION"]:
            mag.constraints.remove(c)

    def sample(action, f, loop=True):
        seq = acts.get(action)
        if not seq:
            return {}
        return seq[f % len(seq)] if loop else seq[min(f, len(seq) - 1)]

    for f in range(n):
        vals = {}
        kind = events["kind"]
        if kind == "fire":
            vals = sample("fire", f) or sample("spin_up", f, loop=False)
        elif kind == "reload":
            g, ins = events["grab"], events["insert"]
            rel = acts.get("mag_release", [])
            ins_a = acts.get("mag_insert", [])
            if f < g:
                vals = dict(sample("idle", f)) if "idle" in acts else {}
                k = f - (g - len(rel))
                if rel and k >= 0:
                    vals.update(rel[min(k, len(rel) - 1)])
            elif f < ins:
                vals = dict(rel[-1]) if rel else {}
            else:
                k = f - ins
                vals = dict(ins_a[min(k, len(ins_a) - 1)]) if ins_a else {}
        else:
            vals = sample("idle", f)
        for (dp, idx), v in vals.items():
            try:
                prop = arm.path_resolve(dp)
                prop[idx] = v
                arm.keyframe_insert(data_path=dp, index=idx, frame=f)
            except (ValueError, TypeError, AttributeError):
                pass
        if kind == "reload":   # the pack where the reload has it (on its actions, or in the hand by its socket)
            pb = arm.pose.bones["Mag"]
            pb.matrix_basis = wpn["mag_rest"].inverted() @ events["mag"][f]
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 0, n - 1
    for o in scene.objects:
        o.select_set(o == arm)
    bpy.context.view_layer.objects.active = arm
    path.parent.mkdir(parents=True, exist_ok=True)
    lib = OUT / "blend" / path.relative_to(OUT).with_suffix(".blend")
    lib.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(lib), {act}, fake_user=True, compress=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIVE_ACTIONS", export_force_sampling=True, export_yup=True,
                              export_def_bones=False, export_frame_range=True)


def aim_poses(rig, wpn, ref, mode, calib, ref_grip, seed=None):
    """The aim poses for a weapon: from its family's aiming idle (held), the weapon raised or lowered AIM_PITCH (deg)
    to where the crosshair is. The chest leans AIM_CHEST_SHARE of the way (spread over the waist and chest in
    proportion to their ranges, within their limits); the arms raise or lower the weapon about the shoulders for the
    rest, the clavicles, shoulders, elbows and wrists solved with both hands back on it; the head nods to keep the
    eyes on the line of fire. Each way is solved as a ramp from level in AIM_STEP steps (each from the one before),
    the poses kept every AIM_PITCH. Returns [(name, pose, placement, pitch, support miss)]; aim_level is the aiming
    idle itself, the additive blend's base."""
    shares = {"Spine": 25.0, "Chest": 20.0, "UpperChest": 15.0}
    total = sum(shares.values())

    def lifted(pitch):
        pose = dict(ref)
        for b, share in shares.items():
            e = list(pose[b].to_3x3().to_euler(rig.order[b]))
            lim = rig.limits[b]["limits_deg"]["x"]
            e[0] = math.radians(min(max(math.degrees(e[0]) - pitch * AIM_CHEST_SHARE * share / total, lim[0]), lim[1]))
            pose[b] = Euler(e, rig.order[b]).to_matrix().to_4x4()                  # up = leaning back (-x)
        achieved = -sum(math.degrees(pose[b].to_3x3().to_euler(rig.order[b])[0])
                        - math.degrees(ref[b].to_3x3().to_euler(rig.order[b])[0]) for b in shares)
        head = list(pose["Head"].to_3x3().to_euler(rig.order["Head"]))
        hl = rig.limits["Head"]["limits_deg"]["x"]
        head[0] = math.radians(min(max(math.degrees(head[0]) - (pitch - achieved), hl[0]), hl[1]))
        pose["Head"] = Euler(head, rig.order["Head"]).to_matrix().to_4x4()
        place = placements(rig, [pose], wpn, mode, calib)[0]   # where the leaning upper body carries the weapon...
        pivot = (rig.world("LeftUpperArm", pose).translation + rig.world("RightUpperArm", pose).translation) / 2
        axis = facing_of(rig, pose) @ Vector((1, 0, 0))   # Tensor's own sideways axis: the weapon never tilts sideways
        now = math.degrees(math.asin(max(-1.0, min(1.0, (place.to_3x3() @ Vector((0, -1, 0))).normalized().z))))
        turn = Matrix.Rotation(math.radians(-(pitch - now)), 4, axis)             # ...then raised about the shoulders
        return pose, Matrix.Translation(pivot) @ turn @ Matrix.Translation(-pivot) @ place

    out = {}
    for sign in (1, -1):
        ramp = [sign * a for a in range(0, max(abs(p) for p in AIM_PITCH) + 1, AIM_STEP)]
        steps = [lifted(pitch) for pitch in ramp]
        poses, placed, _, _ = hold(rig, [a for a, _ in steps], wpn, [b for _, b in steps], ref_grip, seed=seed or ref)
        misses = hold.per_frame
        for k, pitch in enumerate(ramp):
            if pitch in AIM_PITCH and pitch not in out:
                out[pitch] = (poses[k], placed[k], misses[k])
    result = []
    for pitch in AIM_PITCH:
        pose, place, miss = out[pitch]
        name = f"aim_{'level' if pitch == 0 else ('up' if pitch > 0 else 'down') + str(abs(pitch))}"
        result.append((name, pose, place, pitch, 0, miss))
    return result


# ----------------------------------------------------------------------------------- main
def base_poses(rig, spec, cache):
    """A source motion retargeted, rooted and planted (Tensor's pose per frame, the lowest point)."""
    src_dir, file, loop, root_mode = spec
    path = source_path(src_dir, file, cache) if file else SRC / src_dir
    open_tensor()
    src, names, f0, f1 = import_source(path)
    poses = retarget(rig, src, names, f0, f1, root_mode)
    lowest = plant_feet(rig, poses)
    return poses, lowest


def pistol_name(rig, key, poses):
    """The pistol pack's strafes and arcs named by where they go: walk/run, left/right."""
    if not key.startswith(("strafe", "walk_arc", "run_arc", "walk_backward_arc", "run_backward_arc")):
        return key
    end = rig.world("Root", poses[-1])
    d, yaw = end.translation, end.to_3x3().to_euler().z
    if key.startswith("strafe"):
        speed = d.length / (len(poses) / FPS)
        return f"{'run' if speed > 2.2 else 'walk'}_{'left' if d.x > 0 else 'right'}"
    stem = key.rsplit("_", 1)[0]
    return f"{stem}_{'left' if yaw > 0 else 'right'}"


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    wanted = lambda key: not args or any(fnmatch.fnmatch(key, pat) for pat in args)
    info = json.loads((CHAR / "tensor_rig.json").read_text())
    arm = open_tensor()
    rig = Rig(arm, info)
    body_points(rig)
    cache = {}
    man_path = OUT / "manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() and args else {}

    def record(key, n, loop, root_mode, source, extra):
        manifest[key] = {"file": f"tensor/{key}.glb", "frames": n, "fps": FPS, "loop": loop, "root_motion": root_mode,
                         "source": source, **extra}
        man_path.parent.mkdir(parents=True, exist_ok=True)
        man_path.write_text(json.dumps(manifest, indent=2))

    # The character's own clips.
    for k, spec in COMMON.items():
        key = f"common/{k}"
        if not wanted(key):
            continue
        poses, lowest = base_poses(rig, spec, cache)
        arm = open_tensor()
        key_poses(arm, poses, k)
        bake_and_export(arm, k, len(poses), OUT / "tensor" / f"{key}.glb")
        record(key, len(poses), spec[2], spec[3], f"{spec[0]}::{spec[1]}" if spec[1] else spec[0], {"lowest_m": round(lowest, 4)})
        print(f"[retarget] {key}: {len(poses)} frames, lowest {lowest * 1000:.1f} mm")

    # The weapons: calibration from each family's aiming idle.
    weapons = {w: load_weapon(w) for w in WEAPON_FAMILY if any(fnmatch.fnmatch(f"{w}/x", p.split("/")[0] + "/x") for p in args) or not args}
    if not weapons:
        return
    refs = {}
    for fam, (src_fam, motion) in CALIBRATE.items():
        spec = (RIFLE_MOTIONS if src_fam == "rifle" else PISTOL_MOTIONS)[motion]
        poses, _ = base_poses(rig, spec, cache)
        refs[fam] = squared(rig, poses[:1])[0]
    ref_grips = {f: hand_to_hand(rig, refs[f]) for f in refs}           # each source family's two-handed grip
    calib = {}   # per weapon: per source family its calibration in that family's aiming idle
    seats = {}   # per weapon: per source family its aiming idle held (a start for the holds)
    for w, wpn in weapons.items():
        calib[w] = {src_fam: calibrate(rig, ref, wpn) for src_fam, ref in refs.items()}
        seats[w] = {}
        for src_fam, ref in refs.items():
            seats[w][src_fam] = seat(rig, ref, wpn, calib[w][src_fam], ref_grips[src_fam])
            print(f"[retarget] {w} seated in the {src_fam} aiming idle: support {seat.miss * 1000:.1f} mm, "
                  f"weapon turned {seat.aim:.1f} deg")
            if weapons[w]["ammo_sock"] and src_fam == "rifle":   # (every reload is the rifle pack's)
                guides = None
                if w != REFERENCE and w not in TOP_RELOAD:          # the reference's reload carry, reused
                    ref_wpn, ref_seat, ref_carry = reference_carry(rig, ref, ref_grips[src_fam])
                    ref_place = rig.world("UpperChest", seats[w][src_fam]) @ ref_carry
                    guides = [ref_place @ ref_wpn["socks"]["Right"][0] @ wpn["socks"]["Right"][0].inverted()]
                calib[w][src_fam]["RELOAD"], _, m = reload_carry(rig, seats[w][src_fam], wpn, guides)
                print(f"[retarget] {w} reload carry ({src_fam}, {'own' if guides is None else REFERENCE + chr(39) + 's'}): "
                      f"the pack's socket {m * 1000:.1f} mm off")

    # Every weapon's clips: its family's own motions (the pistol also rides its hand on the rifle motions it lacks).
    plan = {}   # (source family, motion key) -> [(weapon, clip name, mode)]
    pistol_names = {}
    for w, wpn in weapons.items():
        fam = wpn["family"]
        own = FAMILIES[fam]["source"]
        if own == "pistol":
            for k in PISTOL_MOTIONS:
                plan.setdefault(("pistol", k), []).append((w, k, "native"))
        for k in RIFLE_MOTIONS:
            plan.setdefault(("rifle", k), []).append((w, k, "native"))
    have = {w: set() for w in weapons}
    for (src_fam, k), users in sorted(plan.items(), key=lambda kv: kv[0][0] != "pistol"):
        spec = (RIFLE_MOTIONS if src_fam == "rifle" else PISTOL_MOTIONS)[k]
        users = [u for u in users if wanted(f"{u[0]}/{u[1]}")]
        if not users:
            continue
        base, lowest = base_poses(rig, spec, cache)
        base = squared(rig, base)                            # with a weapon in hand the chest and head face front
        for w, clip, mode in users:
            wpn = weapons[w]
            name = pistol_name(rig, clip, base) if src_fam == "pistol" else clip
            if src_fam == "rifle" and name in have[w] and wpn["family"] == "pistol":
                continue  # the pistol's own pack has it
            have[w].add(name)
            src = base
            # The weapon from the source's hand, or riding the upper chest as in the aiming idle (two ways): the one
            # held best kept, the source's hand first (a sprint carries the rifle across the chest, so only the
            # chest there).
            sprint = name.startswith("sprint")
            reload = name.startswith("reload")   # (user: a reload may turn and tilt the weapon; its accuracy first)
            best = None
            for how in (("chest", "chest_facing") if sprint else
                        ("carry_phase", "chest_phase", "chest_facing_phase", "native_phase", "native", "chest",
                         "chest_facing") if reload
                        else ("native", "chest", "chest_facing")):
                if how == "carry_phase":                        # a reload: on the chest while both hands hold it,
                    place = blend_places(                           # in its reload carry while the support hand is off
                        placements(rig, src, wpn, "chest", calib[w][src_fam]),
                        placements(rig, src, wpn, "reload_carry", calib[w][src_fam]),
                        off_grip(rig, src, ref_grips[src_fam]))
                elif how in ("chest_phase", "chest_facing_phase"):   # a reload: on the chest while both hands hold it,
                    place = blend_places(                           # as the source's hand has it while the support
                        placements(rig, src, wpn, how[:-6], calib[w][src_fam]),   # hand is off doing the reload
                        placements(rig, src, wpn, "native", calib[w][src_fam], {"free": True}),
                        off_grip(rig, src, ref_grips[src_fam]))
                else:
                    align = {"free": how == "native", "phase": off_grip(rig, src, ref_grips[src_fam])
                             if how == "native_phase" else None} if reload else {}
                    place = placements(rig, src, wpn, "native" if how == "native_phase" else how, calib[w][src_fam], align)
                held = hold(rig, src, wpn, place, ref_grips[src_fam], let_go=name.startswith("reload"), seed=seats[w][src_fam])
                score = held[2] if reload else max(held[2], hold.aim * 5 * TOL_HAND / TOL_AIM)   # (straight: user)
                clash = max(hold.clash, default=0.0)            # (no arm through the weapon)
                score = max(score, CLASH_W * max(0.0, clash - CLASH_TOL))
                hand = held[0]
                if reload:                                        # the source's reload, on this weapon where it is
                    hand = free_hand_on_weapon(rig, held[0], src, actor_weapon(rig, src, wpn, calib[w][src_fam]),
                                               held[1], held[3])
                done = weapon_events(rig, hand, wpn, held[1], name, held[3])   # (a reload's pack counts too)
                if done[1]["kind"] == "reload":
                    score = max(score, reload_pass.miss)
                if best is None or score < best[0] - 1e-4:
                    best = (score, held, hold.aim, dict(hold.miss), how, done, getattr(reload_pass, "miss", 0.0), clash)
                if score <= 1e-4:
                    break
            _, (poses, place, worst, weights), hold.aim, hold.miss, how, (poses, events), reload_pass.miss, clash = best
            ammo = {"ammo_miss_m": round(reload_pass.miss, 4)} if events["kind"] == "reload" else {}
            key = f"{w}/{name}"
            arm = open_tensor()
            key_poses(arm, poses, name)
            bake_and_export(arm, name, len(poses), OUT / "tensor" / f"{key}.glb")
            export_weapon_clip(wpn, name, len(poses), events, OUT / "weapons" / f"{key}.glb")
            record(key, len(poses), spec[2], spec[3], f"{spec[0]}::{spec[1]}",
                   {"weapon": w, "family": wpn["family"], "hold": how, "weapon_file": f"weapons/{key}.glb",
                    "hand_miss_m": round(worst, 4), "aim_miss_deg": round(hold.aim, 1), "arm_clash_m": round(clash, 4),
                    "lowest_m": round(lowest, 4),
                    "weapon_events": events["kind"], **ammo})
            print(f"[retarget]   worst misses: " + ", ".join(f"{s} {m * 1000:.1f} mm @ {f}" for s, (m, f) in hold.miss.items())
                  + (f", ammo pack {reload_pass.miss * 1000:.1f} mm (grab {events['grab']}, put back {events['insert']})"
                     if ammo else ""))
            print(f"[retarget] {key}: {len(poses)} frames, {how} hold, hands within {worst * 1000:.1f} mm, "
                  f"weapon turned within {hold.aim:.1f} deg, arms in it {clash * 1000:.0f} mm, "
                  f"lowest {lowest * 1000:.1f} mm, weapon {events['kind']}")

    # Each weapon's aim poses, from its family's aiming idle.
    for w, wpn in weapons.items():
        if not wanted(f"{w}/aim_level"):
            continue
        fam = wpn["family"]
        src_fam = FAMILIES[fam]["source"]
        mode, ref, c = "native", refs[src_fam], calib[w][src_fam]
        for name, pose, place, pitch, yaw, miss in aim_poses(rig, wpn, ref, mode, c, ref_grips[src_fam], seats[w][src_fam]):
            key = f"{w}/{name}"
            arm = open_tensor()
            key_poses(arm, [pose, pose], name)
            bake_and_export(arm, name, 2, OUT / "tensor" / f"{key}.glb")
            export_weapon_clip(wpn, name, 2, {"kind": "idle"}, OUT / "weapons" / f"{key}.glb")
            record(key, 2, True, "none", f"aim grid from {src_fam} aiming idle",
                   {"weapon": w, "family": fam, "hold": mode, "weapon_file": f"weapons/{key}.glb",
                    "hand_miss_m": round(miss, 4), "lowest_m": 0.0, "weapon_events": "idle",
                    "aim": {"pitch_deg": pitch, "additive_base": f"{w}/aim_level"}})
            print(f"[retarget] {key}: pitch {pitch}, support within {miss * 1000:.1f} mm")


if __name__ == "__main__":
    main()
