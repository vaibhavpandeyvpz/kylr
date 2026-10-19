"""The repair station's own colliders, for collision.py (which imports this module when it sits next to it).

    SK_RepairStationShieldCol   the shield's: a closed, thick low-poly shell round the shield on its bone (so it
                                grows and sinks with activate / deactivate), to stop hits while it is up. Hollow:
                                the patient stands inside it, so use it as a concave (trimesh) shape, not a convex one
    SK_RepairStationPadTrigger  a flat disc on the pad, centred on PlayerMount: an area, not a solid. The player's
                                capsule overlaps it once his centre is over the pad (its radius is the pad's less
                                PLAYER_RADIUS), so the game starts the repair then

Both are in the rig's space (Blender: +Z up, front -Y), from the rig JSON's shield shape and PlayerMount gizmo.
"""

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RIG_JSON = HERE / f"{HERE.name}_rig.json"

SHIELD_SIDES = 12  # round the shield (its outer corners stay on the 2 x 2 m tile: 0.96 / cos 15 deg = 0.994 m)
DOME_STEPS = 3  # facets up the dome's quarter ellipse
SHELL_GAP = 0.001  # the shell stands this far clear of the shield, outside and in

PAD_RADIUS = 0.585  # the repair pad's radius (model.py's PAD)
PLAYER_RADIUS = 0.30  # the player's capsule radius: the trigger is the pad less this, so his centre is on the pad
TRIGGER_SIDES = 16
TRIGGER_HEIGHT = 0.10  # m over the deck (and 1 cm into it): flat, but a capsule standing on the deck overlaps it


def rig_json():
    return json.loads(RIG_JSON.read_text())


def ring(radius, z, sides, phase=0.0):
    a = phase + 2 * math.pi * np.arange(sides) / sides
    return np.stack([radius * np.cos(a), radius * np.sin(a), np.full(sides, z)], axis=1)


def band(lo, hi, sides):
    """Quads (two triangles each) between ring lo and ring hi (vertex indices), outward for rings counter-clockwise
    seen from above with hi over lo."""
    tris = []
    for k in range(sides):
        a, b = lo + k, lo + (k + 1) % sides
        c, d = hi + (k + 1) % sides, hi + k
        tris += [(a, b, c), (a, c, d)]
    return tris


def shield_shell(rig, mesh):
    """A closed shell between two polyhedra of revolution: outside, the shield's profile's tangent polygon swept by a
    circumscribed polygon (it contains the shield exactly); inside, an inscribed one (the shield contains it)."""
    shape = rig_json()["shield"]["shape"]
    r, zw, apex, foot = shape["radius"], shape["wall_top"], shape["apex"], shape["foot_z"]
    h, n = apex - zw, SHIELD_SIDES
    grow = 1 / math.cos(math.pi / n)  # a circle's circumscribed polygon
    steps = np.radians(np.linspace(0, 90, DOME_STEPS + 1))
    half = (steps[1] - steps[0]) / 2
    # Outside: the wall, then the dome's tangents at `steps` meeting at the mid angles (a flat cap on the last).
    outer = [(r, foot)] + [(r * math.cos(m) / math.cos(half), zw + h * math.sin(m) / math.cos(half))
                           for m in steps[:-1] + half]
    # Inside: the wall's foot and top, then up the dome to a point at the apex, each ring inscribed in the render
    # mesh's own (its rings' polygons, its profile's chords), so the shield contains it.
    co = np.array([mesh.matrix_world @ v.co for v in mesh.data.vertices])
    levels = np.unique(np.round(co[:, 2], 4))
    radius_at = np.array([np.linalg.norm(co[np.abs(co[:, 2] - z) < 5e-5, :2], axis=1).max() for z in levels])
    sides = max(int(np.sum(np.abs(co[:, 2] - levels[0]) < 5e-5)), 3)

    def inscribed(z):
        return float(np.interp(z, levels, radius_at)) * math.cos(math.pi / sides)

    inner = [(inscribed(foot), foot)] + [(min(r * math.cos(a), inscribed(zw + h * math.sin(a))), zw + h * math.sin(a))
                                         for a in steps]
    V, T = [], []
    rings_out = []
    for rr, z in outer:
        rings_out.append(len(V))
        V += list(ring(rr * grow + SHELL_GAP, z - (SHELL_GAP if z == foot else 0) + (SHELL_GAP if z > zw else 0), n))
    rings_in = []
    for rr, z in inner[:-1]:
        rings_in.append(len(V))
        V += list(ring(max(rr - SHELL_GAP, 0.0), z + (SHELL_GAP if z == foot else 0) - (SHELL_GAP if z > zw else 0), n))
    tip = len(V)
    V.append((0.0, 0.0, inner[-1][1] - SHELL_GAP))
    for lo, hi in zip(rings_out, rings_out[1:]):
        T += band(lo, hi, n)
    cap = rings_out[-1]
    T += [(cap, cap + k, cap + k + 1) for k in range(1, n - 1)]  # the flat cap on top, facing up
    for lo, hi in zip(rings_in, rings_in[1:]):
        T += [(a, c, b) for a, b, c in band(lo, hi, n)]  # (facing into the bay)
    last = rings_in[-1]
    T += [(last + (k + 1) % n, last + k, tip) for k in range(n)]
    T += band(rings_in[0], rings_out[0], n)  # the foot: the ring between them, facing down
    return [{"bone": rig_json()["shield"]["bone"], "V": np.array(V), "T": np.array(T)}]


def pad_trigger(rig):
    """A flat 16-sided disc over the pad, centred on PlayerMount, on the Root bone."""
    mount = next(g for g in rig_json()["gizmos"] if g["name"] == "PlayerMount")
    x, y, deck = mount["origin"]
    radius = (PAD_RADIUS - PLAYER_RADIUS) / math.cos(math.pi / TRIGGER_SIDES)
    n = TRIGGER_SIDES
    V = np.concatenate([ring(radius, deck - 0.01, n), ring(radius, deck + TRIGGER_HEIGHT, n)]) + (x, y, 0)
    T = band(0, n, n) + [(0, k + 1, k) for k in range(1, n - 1)] + [(n, n + k, n + k + 1) for k in range(1, n - 1)]
    return "SK_RepairStationPadTrigger", [{"bone": "Root", "V": V, "T": np.array(T)}]


CUSTOM = {"SK_RepairStationShield": shield_shell}
EXTRAS = [pad_trigger]

TRI_MAX = 1000  # (user: up to 1,000 triangles for the repair station)
