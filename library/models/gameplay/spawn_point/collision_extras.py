"""The spawn point's own colliders, for collision.py (which imports this module when it sits next to it).

    SK_SpawnPointTrigger      an area (not a solid) over the lift plate, on its bone so it rides up and down with it:
                              the player spawned on PlayerMount is in it; play retract once he leaves it

The frame and shaft (Root) are built here as boxes of what a player can reach, instead of convex pieces of the
render mesh: its housing's hidden pockets (where the panels slide) and tiers are sunk in the level's cut-out.
From the rig JSON's cut-out: the frame's top round the hatch (flush with the floor, as deep as the housing), the
shaft's four walls and its floor behind the render mesh's inner faces, and the guide rails in the shaft's corners.
The panels, their carriages and the plate keep their convex pieces.
"""

import json
from pathlib import Path

import numpy as np

engine = None  # (collision.py, set on import)

HERE = Path(__file__).resolve().parent
WALL = 0.02  # m: the shaft's walls and floor, behind their inner faces (inside the cut-out's tier)


def root_boxes(rig):
    cut = json.loads((HERE / f"{HERE.name}_rig.json").read_text())["cutout_m"]
    frame, shaft = cut["tiers"]
    fx, fy = frame["size"][0] / 2, frame["size"][1] / 2
    hx, hy = cut["hatch"][0] / 2, cut["hatch"][1] / 2
    top, housing, bottom = frame["from_z"], frame["to_z"], shaft["to_z"]
    box = engine.box
    out = [box("Root", (-fx, hy, housing), (fx, fy, top)), box("Root", (-fx, -fy, housing), (fx, -hy, top)),
           box("Root", (hx, -hy, housing), (fx, hy, top)), box("Root", (-fx, -hy, housing), (-hx, hy, top))]
    wx, wy = hx + WALL, hy + WALL
    out += [box("Root", (-wx, hy, bottom), (wx, wy, housing)), box("Root", (-wx, -wy, bottom), (wx, -hy, housing)),
            box("Root", (hx, -hy, bottom), (wx, hy, housing)), box("Root", (-wx, -hy, bottom), (-hx, hy, housing)),
            box("Root", (-hx, -hy, bottom), (hx, hy, bottom + WALL))]
    # The guide rails: the frame's parts standing in the shaft's corners, below the housing.
    P = engine.bone_points(rig, "Root")
    inside = P[(np.abs(P[:, 0]) < hx - 1e-3) & (np.abs(P[:, 1]) < hy - 1e-3) & (P[:, 2] < housing) & (P[:, 2] > bottom + WALL)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = inside[(np.sign(inside[:, 0]) == sx) & (np.sign(inside[:, 1]) == sy)]
            if len(q):
                out.append(box("Root", q.min(0), q.max(0)))
    return out


EXTRAS = [lambda rig: engine.trigger_on_bone(rig, "Plate", "SK_SpawnPointTrigger", height=0.10)]
BONE_OVERRIDE = {"Root": root_boxes}

# The panels' carriages slide in the housing's pockets, under the frame, where nobody reaches: no collider.
BONE_OVERRIDE.update({f"{side}{tier}Carriage{end}": lambda rig: [] for side in ("Left", "Right")
                      for tier in ("Outer", "Inner") for end in ("Front", "Back")})
