"""Tensor's own collider settings, for collision.py (which imports this module when it sits next to it).

The body (SK_Tensor) is convex pieces on his humanoid bones only (user: a middle ground of 3.5 cm, about
2,200 triangles and 120 pieces): each finger's parts join its hand and each toe's its foot, each mechanical stage's
join the limb it turns (the shoulder's pitch and roll the upper arm, the hip's yaw and roll the thigh, the elbow's
hinge the forearm, the ankle's pitch the foot), and the pistons and struts get none. The game drives only the
humanoid bones, and a hit box needs no finger joints.

Each head variant (SK_TensorHead<Variant>) is one fitted hull on the Head bone, SK_TensorHead<Variant>Col, so the
game takes the collider of the head he wears (and a head shot is one clean shape).
"""

engine = None  # (collision.py, set on import)

HUMANOID = {"Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head"} | {
    f"{side}{part}" for side in ("Left", "Right")
    for part in ("Shoulder", "UpperArm", "LowerArm", "Hand", "UpperLeg", "LowerLeg", "Foot")}
STAGE_LIMB = {"ShoulderPitch": "UpperArm", "ShoulderRoll": "UpperArm", "HipYaw": "UpperLeg", "HipRoll": "UpperLeg",
              "ElbowHinge": "LowerArm", "AnklePitch": "Foot", "Toes": "Foot"}
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")

# (user: 2 cm, 1,500 triangles and 100 pieces can't all hold: 2 cm took about 4,200 triangles in 170 pieces, and
# 1,500 / 100 about 5 cm; the user chose the middle ground)
ALLOWANCE = 0.035  # m
TRI_MAX = 2300
PIECE_MAX = 125


def collision_bones(rig):
    out = {}
    for b in rig.data.bones:
        name = b.name
        side = "Left" if name.startswith("Left") else "Right" if name.startswith("Right") else ""
        rest = name[len(side):]
        if name in HUMANOID:
            out[name] = name
        elif side and rest in STAGE_LIMB:
            out[name] = side + STAGE_LIMB[rest]
        elif side and rest.startswith(FINGERS):
            out[name] = side + "Hand"
        else:  # a piston's, a strut's, a marker's: the humanoid bone it hangs from
            x = b.parent
            while x is not None and x.name not in HUMANOID:
                x = x.parent
            out[name] = x.name if x is not None else name
    return out


COLLISION_BONES = collision_bones

# The pistons and struts get no collider: 2-3 cm thin lines inside the limbs' shapes, which aim at each other, so a
# piece joined to a limb would stick out of it once the joint bends (a crouch showed them as stray rods).
NO_COLLIDER = {f"{side}{name}{end}" for side in ("Left", "Right") for end in ("Cylinder", "Rod")
               for name in ("HeadPiston", "ElbowPiston", "KneePiston", "AnklePiston", "SpineStrut")}


def _heads():
    return {f"SK_TensorHead{v}": (lambda rig, mesh: engine.hull_piece(rig, mesh))
            for v in ("Projector", "Sentinel", "Porthole", "Raptor", "Arachne")}


CUSTOM = _heads()
