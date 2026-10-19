"""The barricade's own colliders, for collision.py (which imports this module when it sits next to it).

The pit's liner and the frame (Root) and the deck are built here, not as convex pieces of the render mesh: the pit
is never reached (lowered, the slab fills it; raised, the slab's foot and the deck, risen flush behind it, cover it),
and decomposing the open liner and the notched deck took most of the build's time. Root is the frame's rim round the
pit's opening (flush with the floor, RIM_DEPTH deep), from the rig JSON's cut-out; the deck is one box round its
parts, riding its bone. The slab and the struts keep their convex pieces.
"""

import json
from pathlib import Path

engine = None  # (collision.py, set on import)

HERE = Path(__file__).resolve().parent
RIM_DEPTH = 0.05  # m: the frame's rim, down from the floor


def rim(rig):
    info = json.loads((HERE / f"{HERE.name}_rig.json").read_text())
    cut, up = info["cutout_m"], info["raised_m"]
    (x0, x1), (y0, y1) = cut["x"], cut["y"]
    hx = up["width"] / 2                        # the pit's opening: the slab's width,
    hy0, hy1 = up["front_face_y"], up["deck_y"][1]  # from the slab's front face to the deck's back edge
    z0, z1 = -RIM_DEPTH, 0.0
    box = engine.box
    return [box("Root", (x0, y0, z0), (x1, hy0, z1)), box("Root", (x0, hy1, z0), (x1, y1, z1)),
            box("Root", (x0, hy0, z0), (-hx, hy1, z1)), box("Root", (hx, hy0, z0), (x1, hy1, z1))]


def deck(rig):
    P = engine.bone_points(rig, "Deck")
    return [engine.box("Deck", P.min(0), P.max(0))]


BONE_OVERRIDE = {"Root": rim, "Deck": deck}
