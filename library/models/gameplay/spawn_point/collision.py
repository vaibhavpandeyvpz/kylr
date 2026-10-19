"""Build the collision models of the weapon built by model.py, and render their previews.

Run headless from the repo root (after model.py):
    blender --background --factory-startup --python models/gameplay/spawn_point/collision.py

Model-agnostic: the name comes from the folder, so this file can be copied as-is. It opens <folder>.blend and
<folder>_ammo.blend and writes, for each rig in the file (the weapon's, and a projectile's if it has one), and for
the ammo pack:
    <folder>_col.glb/.fbx           SK_<Mesh>Col for each of the weapon's meshes (SK_RifleCol, SK_RifleOpticCol),
                                    on the weapon's own skeleton (same bones, same actions)
    <folder>_<extra>_col.glb/.fbx   the projectile's, on its own skeleton (e.g. _rocket_col)
    <folder>_ammo_col.glb/.fbx      SM_<Title>AmmoCol, unskinned, in the pack model's frame (hang it on AmmoMount)
    <folder>_col_*.png              previews: the colliders over the model (translucent, one colour per piece),
                                    alone, and in the model's test poses; _col_<own>_* an asset's own (below)
    <folder>_col.blend              the model with its colliders, for inspection
The .blend files it reads are never saved.

A smooth-skinned mesh (a flag's cloth: its vertices weighted to several bones) gets no collider. An asset can add
its own in collision_extras.py next to this file (the repair station's shield shell and pad trigger):
    CUSTOM = {mesh name: fn(rig, mesh) -> pieces | (object name, pieces)}   that mesh's collider (<mesh>Col by
                                    default) instead of convex pieces; no pieces, no collider (a flame's lining)
    EXTRAS = [fn(rig) -> (object name, pieces)]     more collider objects on the rig (an area over a plate)
    CLIP_BELOW = z                                  no collider for the parts under this height (in a cut-out,
                                    where no player reaches)
    BONE_OVERRIDE = {bone: fn(rig) -> pieces}       that bone's pieces built the asset's way instead (the
                                    spawn point's frame and shaft: the surfaces a player reaches, not the
                                    housing's hidden pockets); no pieces, no collider (parts nobody reaches)
    ALLOWANCE = m                                   how far its collider may stand off its mesh (ALLOWANCE)
    TRI_MAX = n                                     its collider's triangle limit (TRI_MAX)
    PIECE_MAX = n                                   and its piece limit (none by default)
    NO_COLLIDER = {bone, ...}                       bones whose parts get no collider (Tensor's pistons, which aim)
    COLLISION_BONES = fn(rig) -> {bone: bone}       the bone each bone's parts join (instead of the motion rule:
                                    Tensor's fingers in his hands, his mechanical stages in their limbs)
where a piece is {"bone", "V" (n x 3, the rig's space), "T" (m x 3, outward triangles)}. The module gets this one
as `engine`, for `trigger_on_bone` (an area over a bone's parts, riding the bone), `slab` (a box round a mesh),
`box` and `hull_piece` (one fitted hull round a mesh: a head). A rig with no actions (a character's) samples its
preview poses for the motion tests instead.

Each collider is a set of convex pieces, each rigidly weighted to one bone (every vertex 1.0 on one bone, the render
mesh's rule), each piece its own closed island, so the engine can make one convex shape per piece. They are made
from the render mesh at rest:
  0. a bone whose parts move less than MOVE_MAX against its parent, over its joint's full range (<folder>_rig.json)
     and every action (a barrel's 1 cm recoil, a trigger's pull, a latch), joins its parent's pieces;
  1. every part (mesh islands, the vertices the render mesh splits along sharp edges welded back)
     starts as its convex hull; a part whose hull stands more than `tol` off the model anywhere (an L-shaped frame,
     a thumbhole stock) is split by planes (its triangles clipped) until each piece's does not. A point of a hull
     inside the model's solid (a winding number test) counts as on it. "The model" is the bone's own parts and
     those of bones that move less than FAR_MOTION: a part that travels far (a lift down in its shaft, a hatch's
     panels shut over it) fills a gap at rest that opens when it moves;
  2. neighbouring pieces on the same bone (of the same mesh) are merged, cheapest first, while the merged hull stays
     within `tol` of the model: gaps and cuts narrower than about 2 * `tol` are filled, real concavities (under a
     grip, round a guard) are not. A small piece (at most SMALL across) may join a neighbour up to CLUSTER_RATIO *
     `tol` off, so a cluster of small parts in a small area becomes one bounding hull (user);
  3. a piece that its own bone's or an ancestor bone's other pieces (of the same mesh) cover to within
     DROP_RATIO * `tol` in every pose of its motion (joint ranges and actions) is dropped: pins, bolts, a pinion in
     its cradle, but not a fin folded in its slot that deploys (a child never covers its parent);
  4. each hull is fitted with a polytope of its supporting planes, refined where it stands more than
     FIT_RATIO * `tol` out of the hull, pruned of the planes it can do without and of its sliver edges: it contains
     the piece, so no geometry is lost.
`tol` starts at ALLOWANCE / (1 + FIT_RATIO) and grows until the collider is within TRI_MAX
triangles, so a simpler model gets fewer.
`-- --no-render` skips the previews.
"""

import itertools
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
NAME = HERE.name
sys.path.insert(0, str(HERE))
import preview  # noqa: E402  (the studio, cameras and framing: the previews match the model's)

try:  # an asset's own colliders (collision_extras.py next to this file: see `main`)
    import collision_extras as extras  # noqa: E402
    extras.engine = sys.modules[__name__]  # (its builders may use the helpers here: `trigger_on_bone`, `slab`)
except ImportError:
    extras = None

TRI_MAX = 500  # per collider (user: 100-500 by the geometry's complexity, the fewer the better)
ALLOWANCE = 0.02  # m: how far a collider may stand off its mesh (user: up to 2 cm is fine), unless TRI_MAX needs more
FIT_RATIO = 1.0  # the fit may stand as far out of its hull as the hull off the mesh: `tol` is half the allowance
DROP_RATIO = 0.5  # a piece covered by others to within DROP_RATIO * tol is dropped
SMALL = 0.05  # m: a piece at most this big across is small: it may join a neighbour up to CLUSTER_RATIO * tol off
CLUSTER_RATIO = 3.0  # (user: many small pieces in a small area make one bounding collider)
MOVE_MAX = 0.012  # a bone whose parts move less than this against its parent (over its range) joins its parent
POSES = 96  # the poses of the joints' ranges and the actions sampled for the covering test
SPLIT_DEPTH = 6  # a part is split at most this many times over (8 took the barricade's 4 m slab over 20 minutes)
FAR_MOTION = 0.05  # m: a bone's parts that move more than this are not counted filling others' gaps
SAMPLES = 1500  # surface samples per hull when measuring how far it stands off the model
PREVIEW_VIEWS = list(preview.VIEWS)
SOLO_VIEWS = ["front_left", "rear_right"]
OWN_VIEWS = ["front_left", "front"]


# --------------------------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------------------------

def mesh_islands(objects, bone_map, space=None):
    """The render meshes at rest (in `space` @ world, a rig's own space, or in each mesh's own with None): triangles
    for the distance
    queries, and each rigid part (a mesh island of one collision bone, see `collision_bones`) as its triangles, a
    soup whose clipped halves (`clip`) are still exact."""
    tris, islands = [], []
    for obj in objects:
        me, mw = obj.data, Matrix.Identity(4) if space is None else space @ obj.matrix_world
        co = np.array([mw @ v.co for v in me.vertices], dtype=np.float64)
        none = set(getattr(extras, "NO_COLLIDER", ()))  # (an asset's bones whose parts get no collider)
        names = {g.index: None if g.name in none else bone_map.get(g.name, g.name) for g in obj.vertex_groups}
        bone = [names[max(v.groups, key=lambda g: g.weight).group] if v.groups else None for v in me.vertices]
        me.calc_loop_triangles()
        loops = [list(t.vertices) for t in me.loop_triangles]
        tris += [co[t] for t in loops]
        parent = list(range(len(me.vertices)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        edges = [tuple(e.vertices) for e in me.edges]
        for a, b in edges:
            if bone[a] == bone[b]:
                parent[find(a)] = find(b)
        seat = {}  # (the render mesh splits its vertices along sharp edges: weld them back)
        for i, key in enumerate(map(tuple, np.round(co, 6))):
            j = seat.setdefault((key, bone[i]), i)
            parent[find(i)] = find(j)
        groups = {}
        for t in loops:
            if bone[t[0]] is not None:
                groups.setdefault(find(t[0]), []).append(t)
        for ts in groups.values():
            islands.append({"mesh": obj.name, "bone": bone[ts[0][0]], "tri": co[np.array(ts)]})
    return np.array(tris), islands


def soup_points(tri):
    return np.unique(np.round(tri.reshape(-1, 3), 7), axis=0)


def hull(points):
    """Convex hull of `points`: (vertices, triangles). A flat or thin set is given 1 mm in each thin direction."""
    pts = np.unique(np.round(np.asarray(points, dtype=np.float64).reshape(-1, 3), 7), axis=0)
    c = pts.mean(0)
    _, sv, vt = np.linalg.svd(pts - c, full_matrices=False)
    basis = np.eye(3) if len(vt) < 3 else vt
    sv = np.concatenate([sv, np.zeros(3 - len(sv))])
    for k in range(3):
        if sv[k] < 1e-4 * math.sqrt(len(pts)):  # thin along this axis (rms spread under 0.1 mm)
            pts = np.concatenate([pts + 5e-4 * basis[k], pts - 5e-4 * basis[k]])
    # bmesh's hull is fast but not reliable on big coplanar sets (a flank's face): it can leave points out or dent
    # the shell. It only proposes the candidates; an exact incremental hull of them is the result, hulled again with
    # any point still outside it.
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
    loose = {g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)}
    cand = np.array([v.co for v in bm.verts if v not in loose], dtype=np.float64)
    bm.free()
    if len(cand) < 4:
        cand = pts
    for _ in range(8):
        V, T = incremental_hull(cand)
        n, d = planes(V, T)
        missed = np.max(pts @ n.T - d, axis=1) > 1e-6
        if not missed.any():
            break
        cand = np.concatenate([V, pts[missed]])
    return V, T


def incremental_hull(P):
    """Exact convex hull of the points P (not all coplanar): (vertices, outward triangles)."""
    P = np.unique(P, axis=0)
    i0 = int(np.argmin(P[:, 0]))
    i1 = int(np.argmax(np.linalg.norm(P - P[i0], axis=1)))
    u = P[i1] - P[i0]
    i2 = int(np.argmax(np.linalg.norm(np.cross(P - P[i0], u), axis=1)))
    n0 = np.cross(u, P[i2] - P[i0])
    i3 = int(np.argmax(np.abs((P - P[i0]) @ n0)))
    if (P[i3] - P[i0]) @ n0 > 0:
        i1, i2 = i2, i1
    faces = [(i0, i1, i2), (i0, i3, i1), (i1, i3, i2), (i2, i3, i0)]
    eps = 1e-9
    order = [k for k in np.argsort(-np.linalg.norm(P - P[[i0, i1, i2, i3]].mean(0), axis=1))
             if k not in (i0, i1, i2, i3)]
    for k in order:
        F = np.array(faces)
        a, b, c = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
        nrm = np.cross(b - a, c - a)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-300)[:, None]
        vis = np.einsum("ij,ij->i", nrm, P[k] - a) > eps
        if not vis.any():
            continue
        edges = {}
        for f in F[vis]:
            for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                edges[e] = True
        horizon = [e for e in edges if (e[1], e[0]) not in edges]
        faces = [tuple(f) for f in F[~vis]] + [(e[0], e[1], k) for e in horizon]
    F = np.array(faces)
    used, inv = np.unique(F, return_inverse=True)
    return P[used], inv.reshape(-1, 3).astype(np.int64)


def volume(V, T):
    if len(T) == 0:
        return 0.0
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    return abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0


def planes(V, T):
    """Outward face planes (n, d) of a convex hull: n . x <= d inside."""
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.cross(b - a, c - a)
    L = np.linalg.norm(n, axis=1)
    ok = L > 1e-9  # (no sliver faces)
    n, a = n[ok] / L[ok, None], a[ok]
    centre = V.mean(0)
    flip = np.einsum("ij,ij->i", n, a - centre) < 0
    n[flip] *= -1
    return n, np.einsum("ij,ij->i", n, a)


def surface_samples(V, T, spacing, cap=SAMPLES, seed=0):
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    count = np.ceil(area / spacing ** 2)
    if count.sum() > cap:
        count = np.ceil(count * cap / count.sum())
    count = count.astype(int)
    rng = np.random.default_rng(seed)
    idx = np.repeat(np.arange(len(T)), count)
    r1, r2 = np.sqrt(rng.random(len(idx))), rng.random(len(idx))
    pts = (1 - r1)[:, None] * a[idx] + (r1 * (1 - r2))[:, None] * b[idx] + (r1 * r2)[:, None] * c[idx]
    mids = np.concatenate([(a + b) / 2, (b + c) / 2, (c + a) / 2])
    pts = np.concatenate([pts, V, mids])
    return pts[rng.permutation(len(pts))]


class Model:
    """The render model at rest: its surface for nearest-point queries and its triangles for the winding number."""

    def __init__(self, tris):
        self.tris = tris
        self.bvh = BVHTree.FromPolygons([Vector(p) for t in tris for p in t],
                                        [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(tris))])

    def inside(self, pts):
        """Generalised winding number over 0.5: inside the solid. Robust to the overlapping parts and to the faces
        the build culled (each is hidden inside another part of its bone, so the union's boundary stays closed). An
        inward-facing shell (a pocket under a plate, a pit) winds negative round its hollow, which counts as solid
        too: nobody reaches into it, and one block takes far fewer triangles (a shaft a player stands in, the spawn
        point's, is built by its asset instead: BONE_OVERRIDE)."""
        return np.abs(self.winding(pts)) > 0.5

    def winding(self, pts):
        out = np.zeros(len(pts))
        A, B, C = self.tris[:, 0], self.tris[:, 1], self.tris[:, 2]
        for k in range(0, len(pts), 64):
            q = pts[k:k + 64, None, :]
            a, b, c = A[None] - q, B[None] - q, C[None] - q
            la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
            det = np.einsum("pmi,pmi->pm", a, np.cross(b, c))
            den = (la * lb * lc + np.einsum("pmi,pmi->pm", a, b) * lc + np.einsum("pmi,pmi->pm", b, c) * la
                   + np.einsum("pmi,pmi->pm", c, a) * lb)
            w = (2 * np.arctan2(det, den)).sum(1) / (4 * math.pi)
            out[k:k + 64] = w
        return out


def standoff(V, T, model, tol):
    """How far the hull's surface stands off the model (max over samples outside its solid); tol * 2 once past."""
    pts = surface_samples(V, T, tol)
    dist = np.empty(len(pts))
    for i, p in enumerate(pts):
        hit = model.bvh.find_nearest(Vector(p), 4 * tol)
        dist[i] = 4 * tol if hit[0] is None else hit[3]
    far = dist > tol
    if far.any():
        # The samples are shuffled and the first one outside the solid settles it: test the far ones in growing
        # batches and stop there (the winding test is the costly part).
        idx = np.flatnonzero(far)
        for lo, hi in ((0, 8), (8, 32), (32, 128), (128, len(idx))):
            if lo < len(idx) and not model.inside(pts[idx[lo:hi]]).all():
                return tol * 2
        dist[far] = 0.0
    return float(dist.max())


# --------------------------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------------------------

def clip(tri, axis, c, keep_below):
    """The part of a triangle soup on one side of the plane x[axis] = c, as triangles (the cut faces' edges included,
    so a piece cut again is still exact)."""
    d = tri[:, :, axis] - c
    if not keep_below:
        d = -d
    inside = d <= 0
    count = inside.sum(1)
    out = [tri[count == 3]]
    for t, dt, it in zip(tri[(count == 1) | (count == 2)], d[(count == 1) | (count == 2)],
                         inside[(count == 1) | (count == 2)]):
        poly = []
        for k in range(3):  # Sutherland-Hodgman against one plane
            a, b, da, db = t[k], t[(k + 1) % 3], dt[k], dt[(k + 1) % 3]
            if it[k]:
                poly.append(a)
            if it[k] != it[(k + 1) % 3]:
                poly.append(a + (da / (da - db)) * (b - a))
        out.append(np.array([[poly[0], poly[m], poly[m + 1]] for m in range(1, len(poly) - 1)]))
    return np.concatenate([o.reshape(-1, 3, 3) for o in out])


def best_split(piece):
    """The axis-aligned cut that leaves the least hull volume on its two sides."""
    pts = soup_points(piece["tri"])
    lo, hi = pts.min(0), pts.max(0)
    best = None
    for axis in range(3):
        if hi[axis] - lo[axis] < 1e-3:
            continue
        for f in np.linspace(0.1, 0.9, 9):
            c = lo[axis] + f * (hi[axis] - lo[axis])
            halves = [clip(piece["tri"], axis, c, below) for below in (True, False)]
            if any(len(h) == 0 for h in halves):
                continue
            vol = sum(quick_volume(soup_points(h)) for h in halves)
            if best is None or vol < best[0]:
                best = (vol, halves)
    return None if best is None else [dict(piece, tri=h) for h in best[1]]


def quick_volume(points):
    """The volume of bmesh's convex hull of `points`: fast, for scoring cuts (`hull` makes the exact one)."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    try:
        bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
        vol = abs(bm.calc_volume()) if bm.faces else 0.0
    except Exception:
        vol = 0.0
    bm.free()
    return vol


def with_hull(piece):
    piece["V"], piece["T"] = hull(soup_points(piece["tri"]))
    piece["lo"], piece["hi"] = piece["V"].min(0), piece["V"].max(0)
    return piece


def decompose(piece, model, tol, depth=0):
    with_hull(piece)
    size = np.linalg.norm(piece["hi"] - piece["lo"])
    if depth >= SPLIT_DEPTH or size < 3 * tol or standoff(piece["V"], piece["T"], model, tol) <= tol:
        return [piece]
    halves = best_split(piece)
    if halves is None:
        return [piece]
    return [p for h in halves for p in decompose(h, model, tol, depth + 1)]


def merge_bone(pieces, model, tol):
    """Greedy merging of one bone's pieces (of one mesh), cheapest first, while the merged hull stays within tol, or
    within CLUSTER_RATIO * tol where one of the two is small: a cluster of small parts becomes one bounding hull."""
    pieces = list(pieces)
    cost = {}

    def small(p):
        return float((p["hi"] - p["lo"]).max()) <= SMALL

    def evaluate(i, j):
        a, b = pieces[i], pieces[j]
        if a is None or b is None:
            return
        limit = CLUSTER_RATIO * tol if small(a) or small(b) else tol
        if not (np.all(a["lo"] - limit <= b["hi"]) and np.all(b["lo"] - limit <= a["hi"])):
            return
        V, T = hull(np.concatenate([a["V"], b["V"]]))
        s = standoff(V, T, model, limit)
        if s <= limit:
            cost[(i, j)] = (s, V, T)

    for i, j in itertools.combinations(range(len(pieces)), 2):
        evaluate(i, j)
    while cost:
        (i, j), (s, V, T) = min(cost.items(), key=lambda kv: kv[1][0])
        a, b = pieces[i], pieces[j]
        merged = {"mesh": a["mesh"], "bone": a["bone"], "tri": np.concatenate([a["tri"], b["tri"]]), "V": V, "T": T,
                  "lo": V.min(0), "hi": V.max(0)}
        pieces[i] = pieces[j] = None
        cost = {k: v for k, v in cost.items() if i not in k and j not in k}
        pieces.append(merged)
        k = len(pieces) - 1
        for m in range(k):
            evaluate(m, k)
    return [p for p in pieces if p is not None]


def outside(pts, piece):
    """Distance of each point outside a piece's hull (0 inside)."""
    n, d = piece["planes"]
    out = np.zeros(len(pts))
    far = np.max(pts @ n.T - d, axis=1) > 1e-7
    if far.any():
        if "bvh" not in piece:
            piece["bvh"] = BVHTree.FromPolygons([Vector(v) for v in piece["V"]],
                                                [list(map(int, t)) for t in piece["T"]])
        out[far] = [piece["bvh"].find_nearest(Vector(x))[3] for x in pts[far]]
    return out


def drop_covered(pieces, cover, drop):
    """Drop, smallest first, every piece whose own geometry lies within `drop` of the other pieces of its own bone or
    of an ancestor bone (a child's never cover its parent's), in every pose of its motion relative to them
    (`cover`: a folded fin that deploys, or a lid that opens, stays; a pinion turning in its cradle goes)."""
    for p in pieces:
        p["planes"] = planes(p["V"], p["T"])
    kept = sorted(pieces, key=lambda p: volume(p["V"], p["T"]))
    for p in list(kept):
        rel = cover[p["bone"]]
        others = [q for q in kept if q is not p and q["mesh"] == p["mesh"] and q["bone"] in rel]
        if not others:
            continue
        pts = np.concatenate([soup_points(p["tri"]), p["tri"].mean(1)])  # (its own geometry, not its hull)
        P = np.concatenate([pts, np.ones((len(pts), 1))], axis=1)
        bones = sorted({q["bone"] for q in others})
        poses = {}
        for k in range(len(rel[bones[0]])):  # (the distinct poses of p relative to its covers)
            key = b"".join(np.round(rel[b][k], 5).tobytes() for b in bones)
            poses.setdefault(key, k)
        covered = True
        for k in poses.values():
            moved = {b: (P @ rel[b][k].T)[:, :3] for b in bones}
            out = np.full(len(pts), np.inf)
            for q in others:
                live = out > drop
                if not live.any():
                    break
                out[live] = np.minimum(out[live], outside(moved[q["bone"]][live], q))
            if out.max() > drop:
                covered = False
                break
        if covered:
            kept = [q for q in kept if q is not p]
    return kept


# --------------------------------------------------------------------------------------------
# Fitting: a polytope of supporting planes round each hull
# --------------------------------------------------------------------------------------------

AXES = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], dtype=np.float64)
BOUND = 100.0  # m: a polytope reaching this far is unbounded


def polytope(n, h):
    """Vertices of {x : n . x <= h}, or None if it is unbounded."""
    n = np.concatenate([n, AXES])
    h = np.concatenate([h, np.full(6, BOUND)])
    tri = np.array(list(itertools.combinations(range(len(n)), 3)))
    M = n[tri]
    det = np.linalg.det(M)
    ok = np.abs(det) > 1e-14  # (planes nearly meeting along an edge still make a corner)
    X = np.linalg.solve(M[ok], h[tri[ok]][..., None])[..., 0]
    X = X[np.all(X @ n.T <= h + 1e-7, axis=1) & np.all(np.isfinite(X), axis=1)]
    if len(X) == 0 or np.abs(X).max() > BOUND * 0.99:
        return None
    return np.unique(np.round(X, 5), axis=0)  # (corners where several planes meet, to 10 um)


def fit(V, T, fit_tol):
    """Supporting planes of the hull (V, T), refined at the polytope's worst vertex until every vertex is within
    fit_tol of the hull, then pruned of every plane it can do without. Contains the hull: nothing is lost."""
    tree = BVHTree.FromPolygons([Vector(v) for v in V], [list(map(int, t)) for t in T])

    def support(n):
        return (V @ n.T).max(0)

    def worst(n):
        X = polytope(n, support(n))
        if X is None:
            return math.inf, None, None
        hits = [(tree.find_nearest(Vector(x)), x) for x in X]
        (q, _, _, d), x = max(hits, key=lambda t: t[0][3])
        return d, x, q

    normals = AXES.copy()
    for _ in range(64):
        err, x, q = worst(normals)
        if err <= fit_tol or x is None:
            break
        n = np.asarray(x) - np.asarray(q)
        n /= np.linalg.norm(n)
        if np.max(normals @ n) > 0.99999:
            break
        normals = np.concatenate([normals, n[None]])
    # Prune: drop planes (the least-used first) while the polytope stays bounded and within fit_tol.
    i = 0
    while i < len(normals):
        trial = np.delete(normals, i, axis=0)
        if worst(trial)[0] <= fit_tol:
            normals = trial
        else:
            i += 1
    V0, T0 = V, T = hull(polytope(normals, support(normals)))
    # Collapse the slivers where planes meet almost at a point: the shortest edge, while under fit_tol. Collapsing
    # moves the polytope in, so its faces' planes are then pushed back out to support the hull again: it keeps its
    # fewer faces and contains the piece.
    while len(V) > 4:
        e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        L = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1)
        k = int(np.argmin(L))
        if L[k] >= fit_tol:
            break
        i, j = e[k]
        merged = np.delete(V, [i, j], axis=0)
        W, U = hull(np.concatenate([merged, (V[i] + V[j])[None] / 2]))
        if len(U) >= len(T):
            break
        V, T = W, U
    if len(T) < len(T0):
        n = planes(V, T)[0]
        n = n[np.unique(np.round(n, 3), axis=0, return_index=True)[1]]
        X = polytope(n, support(n))
        if X is not None:
            V, T = hull(X)
            if len(T) < len(T0) and worst(n)[0] <= fit_tol:
                return V, T
    return V0, T0


# --------------------------------------------------------------------------------------------
# One collider
# --------------------------------------------------------------------------------------------

def build_pieces(objects, cover, bone_map, tol, space, far=(), fixed=(), skip=()):
    tris, islands = mesh_islands(objects, bone_map, space)
    islands = [i for i in islands if i["bone"] not in skip]  # (the asset builds those, or leaves them out)
    near = [i["tri"] for i in islands if i["bone"] not in far]
    models = {None: Model(np.concatenate(near)) if near else None}

    def model_of(bone):
        """The parts a bone's pieces are measured against: its own and every near bone's."""
        key = bone if bone in far else None
        if key not in models:
            models[key] = Model(np.concatenate(near + [i["tri"] for i in islands if i["bone"] == bone]))
        return models[key]

    clip_below = getattr(extras, "CLIP_BELOW", None)  # (an asset's height under which no player reaches its parts)
    if clip_below is not None:
        for isl in islands:
            isl["tri"] = clip(isl["tri"], 2, clip_below, keep_below=False)
        islands = [isl for isl in islands if len(isl["tri"])]
        tris = clip(tris, 2, clip_below, keep_below=False)  # (and the coverage report skips what is cut away)
    by_bone = {}
    for isl in islands:
        parts = decompose(isl, model_of(isl["bone"]), tol)
        by_bone.setdefault((isl["mesh"], isl["bone"]), []).extend(parts)
    pieces = [p for (mesh, bone), ps in by_bone.items() for p in merge_bone(ps, model_of(bone), tol)]
    pieces = drop_covered(pieces, cover, DROP_RATIO * tol)
    fitted = []
    for p in pieces:
        V, T = fit(p["V"], p["T"], FIT_RATIO * tol)
        fitted.append({"mesh": p["mesh"], "bone": p["bone"], "V": V, "T": T})
    return fitted + list(fixed), tris


def coverage(pieces, tris):
    """How far the model's surface pokes out of the collider at worst, and the share of it inside."""
    pts = np.concatenate([tris.reshape(-1, 3), tris.mean(1)])
    out = np.full(len(pts), np.inf)
    for p in pieces:
        p["planes"] = planes(p["V"], p["T"])
        live = out > 1e-4
        out[live] = np.minimum(out[live], outside(pts[live], p))
    return out.max(), float(np.mean(out <= 1e-3))


def make_collider(objects, cover, label, bone_map=None, space=None, far=(), fixed=(), skip=()):
    bone_map = bone_map or {}
    tol = getattr(extras, "ALLOWANCE", ALLOWANCE) / (1 + FIT_RATIO)
    limit = getattr(extras, "TRI_MAX", TRI_MAX)  # (an asset may take more: the repair station, user)
    piece_limit = getattr(extras, "PIECE_MAX", None)  # (and may cap its pieces: Tensor, user)
    while True:
        pieces, tris = build_pieces(objects, cover, bone_map, tol, space, far, fixed, skip)
        count = sum(len(p["T"]) for p in pieces)
        if count <= limit and (piece_limit is None or len(pieces) <= piece_limit):
            break
        print(f"[{NAME}] {label}: {count} triangles, {len(pieces)} pieces at tol {tol * 1000:.1f} mm, over "
              f"{limit}{f' / {piece_limit} pieces' if piece_limit else ''}: coarser")
        tol *= 1.2
    worst, share = coverage(pieces, tris)
    print(f"[{NAME}] {label}: {len(pieces)} convex pieces on {len({p['bone'] for p in pieces})} bones, {count} "
          f"triangles (tol {tol * 1000:.1f} mm); the model pokes out {worst * 1000:.1f} mm at worst, "
          f"{share * 100:.1f}% of its surface inside")
    for p in pieces:
        p.pop("bvh", None)
    return pieces, count, tol


def collider_object(name, pieces, rig=None):
    """One mesh, each piece its own closed island, rigidly weighted to its bone; a colour per piece (previews)."""
    V, F, piece_of = [], [], []
    for k, p in enumerate(pieces):
        base = len(V)
        V += [tuple(v) for v in p["V"]]
        F += [tuple(int(i) + base for i in t) for t in p["T"]]
        piece_of += [k] * len(p["T"])
    me = bpy.data.meshes.new(name)
    me.from_pydata(V, [], F)
    me.validate()
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = False
    col = me.color_attributes.new("Piece", "BYTE_COLOR", "CORNER")
    for poly, k in zip(me.polygons, piece_of):
        rgb = piece_color(k)
        for li in poly.loop_indices:
            col.data[li].color = (*rgb, 1.0)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if rig is not None:
        for p in pieces:
            if p["bone"] not in obj.vertex_groups:
                obj.vertex_groups.new(name=p["bone"])
        base = 0
        for p in pieces:
            obj.vertex_groups[p["bone"]].add(list(range(base, base + len(p["V"]))), 1.0, "REPLACE")
            base += len(p["V"])
        obj.parent = rig  # (its vertices are in the rig's space)
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = Matrix.Identity(4)
        obj.modifiers.new("Armature", "ARMATURE").object = rig
    return obj


def piece_color(k):
    h = (k * 0.618034) % 1.0
    r, g, b = [min(1, max(0, abs((h * 6 + o) % 6 - 3) - 1)) for o in (0, 4, 2)]
    return tuple(0.35 + 0.6 * c for c in (r, g, b))


# --------------------------------------------------------------------------------------------
# Scene, previews and export
# --------------------------------------------------------------------------------------------

def open_model():
    path = HERE / f"{NAME}.blend"
    if not path.exists():
        raise SystemExit(f"[{NAME}] {path} not found - run model.py first")
    bpy.ops.wm.open_mainfile(filepath=str(path))


def rigid(obj):
    """Rigidly skinned: every vertex on one bone (a cloth's are blended over several)."""
    return all(sum(1 for g in v.groups if g.weight > 1e-6) <= 1 for v in obj.data.vertices)


def rig_meshes(rig):
    return [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("PRV_")
            and any(m.type == "ARMATURE" and m.object is rig for m in o.modifiers)]


def bone_motion(rig, meshes):
    """How far each bone's parts move relative to its parent's frame: over its joint's full range (<name>_rig.json)
    and over every action the rig plays. Also the poses sampled (each bone's deform matrix, the rest pose first)."""
    points = {}
    inv = rig.matrix_world.inverted()
    for obj in meshes:
        names = {g.index: g.name for g in obj.vertex_groups}
        m = inv @ obj.matrix_world
        for v in obj.data.vertices:
            if v.groups:
                points.setdefault(names[max(v.groups, key=lambda g: g.weight).group], []).append(m @ v.co)
    points = {b: np.array([(*p, 1.0) for p in ps]) for b, ps in points.items()}
    motion = {b: 0.0 for b in points}
    poses = []

    def measure():
        bpy.context.view_layer.update()
        poses.append({pb.name: np.array(pb.matrix @ pb.bone.matrix_local.inverted()) for pb in rig.pose.bones})
        for b, P in points.items():
            pb = rig.pose.bones[b]
            D = np.array(pb.matrix @ pb.bone.matrix_local.inverted())
            if pb.parent is not None:
                D = np.linalg.inv(np.array(pb.parent.matrix @ pb.parent.bone.matrix_local.inverted())) @ D
            motion[b] = max(motion[b], float(np.linalg.norm((P @ D.T - P)[:, :3], axis=1).max()))

    ad = rig.animation_data or rig.animation_data_create()
    saved = ad.action
    rig_json = HERE / f"{NAME}_rig.json"
    joints = json.loads(rig_json.read_text()).get("joints", []) if rig_json.exists() else []
    ad.action = None
    for j in joints:
        if j["bone"] not in points or not j.get("range"):
            continue
        pb = rig.pose.bones[j["bone"]]
        for v in np.linspace(j["range"][0], j["range"][1], 9):
            preview.reset_pose(rig)
            if j["type"] == "hinge":
                pb.rotation_mode = "XYZ"
                pb.rotation_euler = (math.radians(v), 0, 0)
            elif j["type"] == "slide":
                pb.location = (0, v, 0)
            measure()
    preview.reset_pose(rig)
    bones = {b.name for b in rig.data.bones}
    for act in bpy.data.actions:
        paths = [fc.data_path for fc in action_fcurves(act)]
        if not any(p.startswith("pose.bones[") and p.split('"')[1] in bones for p in paths):
            continue
        ad.action = act
        if len(getattr(act, "slots", [])):
            ad.action_slot = act.slots[0]
        f0, f1 = (int(round(f)) for f in act.frame_range)
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            measure()
    if not any(action_fcurves(a) for a in bpy.data.actions) and "preview_poses" in rig:
        ad.action = None  # (no actions: a character's clips live in the animation library; its test poses stand in)
        for bones in json.loads(rig["preview_poses"]).values():
            preview.apply_pose(rig, bones)
            measure()
    ad.action = saved
    preview.reset_pose(rig)
    bpy.context.scene.frame_set(0)
    rest = {pb.name: np.eye(4) for pb in rig.pose.bones}
    step = max(1, len(poses) // POSES)
    return motion, [rest] + poses[::step]


def action_fcurves(act):
    """An action's F-curves (the layered actions of Blender 4.4+ keep them in channel bags)."""
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out += list(bag.fcurves)
    if not out and hasattr(act, "fcurves"):
        out = list(act.fcurves)
    return out


def collision_bones(rig, motion):
    """Each bone's collision bone: itself if its parts move more than MOVE_MAX against its parent, else its
    parent's (a barrel's 1 cm recoil, a trigger's pull, a latch's click)."""
    out = {}

    def resolve(b):
        if b.name not in out:
            moves = motion.get(b.name, 0.0) > MOVE_MAX
            out[b.name] = b.name if b.parent is None or moves else resolve(b.parent)
        return out[b.name]

    for b in rig.data.bones:
        resolve(b)
    return out


def cover_poses(rig, bone_map, poses):
    """For each collision bone, the bones whose pieces may cover its own (itself and its collision ancestors), each
    with its transform into their rest frame in every pose: {bone: {coverer: [4x4, ...]}}."""
    out = {}
    for b in set(bone_map.values()):
        rel, x = {}, rig.data.bones[b]
        while x is not None:
            a = bone_map[x.name]
            if a not in rel:
                rel[a] = [np.eye(4) if a == b else np.linalg.inv(pose[a]) @ pose[b] for pose in poses]
            x = x.parent
        out[b] = rel
    return out


def bone_points(rig, bone):
    """The rig-space vertices of the rigid meshes' parts on `bone`."""
    out = []
    inv = rig.matrix_world.inverted()
    for obj in SOURCES.get(rig.name, []):  # (the model's own meshes, not the colliders on the same bones)
        if not rigid(obj) or obj.name in getattr(extras, "CUSTOM", {}):
            continue
        g = obj.vertex_groups.get(bone)
        if g is None:
            continue
        m = inv @ obj.matrix_world
        out += [m @ v.co for v in obj.data.vertices if any(x.group == g.index and x.weight > 0.5 for x in v.groups)]
    return np.array(out)


SOURCES = {}  # rig name -> its render meshes, as main found them before making any collider


def convex_polygon(xy, sides):
    """The 2D convex hull of `xy` (counter-clockwise), cut down to `sides` corners by dropping, one at a time, the
    corner whose removal loses the least area."""
    pts = sorted(map(tuple, np.round(xy, 6)))

    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (q[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(q)
        return h

    poly = np.array(half(pts)[:-1] + half(pts[::-1])[:-1])
    while len(poly) > sides:
        a, b, c = np.roll(poly, 1, 0), poly, np.roll(poly, -1, 0)
        loss = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))
        poly = np.delete(poly, int(np.argmin(loss)), axis=0)
    return poly


def prism(poly, z0, z1):
    """A closed prism over a counter-clockwise convex polygon, from z0 up to z1: (V, T) outward."""
    n = len(poly)
    V = np.concatenate([np.c_[poly, np.full(n, z0)], np.c_[poly, np.full(n, z1)]])
    T = [(k, (k + 1) % n, n + (k + 1) % n) for k in range(n)] + [(k, n + (k + 1) % n, n + k) for k in range(n)]
    T += [(0, k + 1, k) for k in range(1, n - 1)] + [(n, n + k, n + k + 1) for k in range(1, n - 1)]
    return V, np.array(T)


def trigger_on_bone(rig, bone, name, height=0.10, below=0.01, sides=16):
    """An area (not a solid) over `bone`'s parts, riding the bone: their footprint's convex hull (at most `sides`
    corners), from `below` under their top to `height` over it, so a player standing on them overlaps it."""
    P = bone_points(rig, bone)
    top = float(P[:, 2].max())
    V, T = prism(convex_polygon(P[:, :2], sides), top - below, top + height)
    return name, [{"bone": bone, "V": V, "T": T}]


def box(bone, lo, hi):
    """A box piece on `bone` from corner `lo` to corner `hi` (the rig's space)."""
    V, T = prism(np.array([(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])]), lo[2], hi[2])
    return {"bone": bone, "V": V, "T": T}


def hull_piece(rig, mesh, allowance=ALLOWANCE):
    """One convex piece round a whole rigid mesh (a swappable head), fitted within `allowance`, on its bone."""
    co = np.array([rig.matrix_world.inverted() @ mesh.matrix_world @ v.co for v in mesh.data.vertices])
    V, T = hull(co)
    V, T = fit(V, T, allowance / 2)
    bone = max(mesh.vertex_groups, key=lambda g: sum(1 for v in mesh.data.vertices
                                                      for x in v.groups if x.group == g.index)).name
    return [{"bone": bone, "V": V, "T": T}]


def slab(rig, mesh, name, depth):
    """An area round a flat mesh (a portal's field): its bounding box, `depth` thick along its thinnest axis."""
    co = np.array([rig.matrix_world.inverted() @ mesh.matrix_world @ v.co for v in mesh.data.vertices])
    lo, hi = co.min(0), co.max(0)
    k = int(np.argmin(hi - lo))
    mid = (lo[k] + hi[k]) / 2
    lo[k], hi[k] = mid - depth / 2, mid + depth / 2
    V = np.array([(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    T = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
                  (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    bone = max(mesh.vertex_groups, key=lambda g: sum(1 for v in mesh.data.vertices
                                                      for x in v.groups if x.group == g.index)).name
    return name, [{"bone": bone, "V": V, "T": T}]


def collision_materials():
    """The previews' materials: a translucent fill (a colour per piece) and dark edges."""
    fill = bpy.data.materials.new("M_Collision")
    nt = fill.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Piece"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    bsdf.inputs["Alpha"].default_value = 0.35
    if hasattr(fill, "surface_render_method"):
        fill.surface_render_method = "BLENDED"
    fill.use_backface_culling = True
    edge = bpy.data.materials.new("M_CollisionEdge")
    eb = next(n for n in edge.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    eb.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1)
    eb.inputs["Roughness"].default_value = 0.8
    return fill, edge


def edge_object(obj, material):
    """A preview-only copy of the collider drawn as its edges (wireframe after the armature)."""
    me = obj.data.copy()
    me.materials.clear()
    me.materials.append(material)
    wire = bpy.data.objects.new(f"PRV_{obj.name}Edges", me)
    bpy.context.scene.collection.objects.link(wire)
    wire.parent, wire.matrix_parent_inverse = obj.parent, obj.matrix_parent_inverse.copy()
    wire.matrix_basis = obj.matrix_basis.copy()
    for m in obj.modifiers:
        wire.modifiers.new(m.name, m.type).object = m.object
    for g in obj.vertex_groups:
        wire.vertex_groups.new(name=g.name)
    for v in obj.data.vertices:
        for g in v.groups:
            wire.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
    mod = wire.modifiers.new("Edges", "WIREFRAME")
    mod.thickness, mod.use_even_offset, mod.use_replace = 0.0008, False, True
    return wire


def render_all(rig, colliders, model_meshes, extra, own=()):
    """Colliders over the model (every view), alone, in the model's test poses, each extra collider (a
    projectile's) over its own model, and each of the asset's own (a shield's shell, a trigger) over the model."""
    preview.setup_render()
    cam, lights = preview.create_camera(), preview.create_lights()
    fill = bpy.data.materials["M_Collision"]
    alpha = next(n for n in fill.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Alpha"]
    shown = {o.name: o.hide_render for o in bpy.context.scene.objects}

    def show(objs):
        names = {o.name for o in objs}
        for o in bpy.context.scene.objects:
            if o.type == "MESH":
                o.hide_render = o.name not in names

    edges = {c.name: bpy.data.objects[f"PRV_{c.name}Edges"] for c in colliders + [e[0] for e in extra]
             + [o for o, _ in own]}
    overlay = model_meshes + colliders + [edges[c.name] for c in colliders]
    show(overlay)
    alpha.default_value = 0.35
    for view in PREVIEW_VIEWS:
        preview.render_view(cam, lights, view, f"col_{view}", subject=model_meshes)
    if "preview_poses" in rig:
        pose_show = json.loads(rig["preview_pose_show"]) if "preview_pose_show" in rig else {}
        for pose, bones in json.loads(rig["preview_poses"]).items():
            stand_ins = [bpy.data.objects[n] for n in pose_show.get(pose, []) if n in bpy.data.objects]
            show(overlay + stand_ins)  # (and the pose's stand-ins: the repair station's patient, its shield)
            preview.apply_pose(rig, bones)
            preview.render_view(cam, lights, "front_left", f"col_pose_{pose}", subject=model_meshes)
        preview.reset_pose(rig)
    alpha.default_value = 1.0
    show(colliders + [edges[c.name] for c in colliders])
    for view in SOLO_VIEWS:
        preview.render_view(cam, lights, view, f"col_solo_{view}", subject=colliders)
    for col, meshes, tag in extra:
        show(meshes + [col, edges[col.name]])
        alpha.default_value = 0.35
        preview.render_view(cam, lights, "front_left", f"{tag}_col_front_left", subject=meshes)
        alpha.default_value = 1.0
        show([col, edges[col.name]])
        preview.render_view(cam, lights, "rear_right", f"{tag}_col_solo_rear_right", subject=[col])
    alpha.default_value = 0.35
    for col, tag in own:
        show(model_meshes + [col, edges[col.name]])
        for view in OWN_VIEWS:
            preview.render_view(cam, lights, view, f"col_{tag}_{view}", subject=model_meshes + [col])
    for o in bpy.context.scene.objects:
        if o.name in shown:
            o.hide_render = shown[o.name]


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.hide_select = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def export(objs, stem, skinned):
    """The weapon's export settings: a skinned collider with its rig and the rig's actions (the constraints and
    drivers removed first, as model.py does), an unskinned one (the pack's) as the pickup is exported. No materials:
    a collider is never drawn."""
    for o in objs:
        if o.type == "MESH":  # smooth, so the glTF exporter keeps each piece's corners shared: a closed island
            for poly in o.data.polygons:
                poly.use_smooth = True
        if o.type == "ARMATURE":
            o.matrix_world = Matrix.Identity(4)  # (as its model is exported: model.py moves a projectile's rig aside)
            for pb in o.pose.bones:
                for c in list(pb.constraints):
                    pb.constraints.remove(c)
            for fc in list(o.animation_data.drivers if o.animation_data else []):
                o.animation_data.drivers.remove(fc)
    select_only(objs)
    fbx = dict(filepath=str(HERE / f"{stem}.fbx"), use_selection=True, global_scale=1.0, apply_unit_scale=True,
               apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", bake_space_transform=False,
               use_mesh_modifiers=False, mesh_smooth_type="OFF", add_leaf_bones=False, path_mode="COPY",
               embed_textures=True)
    gltf = dict(filepath=str(HERE / f"{stem}.glb"), export_format="GLB", use_selection=True, export_yup=True,
                export_apply=False, export_materials="NONE")
    if skinned:
        bpy.ops.export_scene.fbx(
            **fbx, object_types={"MESH", "ARMATURE"}, primary_bone_axis="Y", secondary_bone_axis="X",
            use_armature_deform_only=True, bake_anim=True, bake_anim_use_all_bones=False,
            bake_anim_use_nla_strips=False, bake_anim_use_all_actions=True, bake_anim_force_startend_keying=True)
        bpy.ops.export_scene.gltf(
            **gltf, export_skins=True, export_def_bones=True, export_animations=True,
            export_animation_mode="ACTIONS", export_anim_single_armature=True, export_reset_pose_bones=True,
            export_force_sampling=True, export_optimize_animation_size=True,
            export_optimize_animation_keep_anim_armature=False, export_anim_slide_to_zero=True)
    else:
        bpy.ops.export_scene.fbx(**fbx, object_types={"MESH"}, bake_anim=False)
        bpy.ops.export_scene.gltf(**gltf, export_skins=False, export_animations=False)
    print(f"[{NAME}] exported {stem}.glb/.fbx")


def load_pack():
    """The ammo pack's model (<name>_ammo.blend), hung on AmmoMount as the previews hang it."""
    path = HERE / f"{NAME}_ammo.blend"
    if not path.exists() or not hasattr(preview, "attach_pack"):
        return []
    before = set(bpy.data.objects)
    preview.attach_pack()
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def main():
    open_model()
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    weapon = next(r for r in rigs if "preview_poses" in r)
    title = weapon.name.removeprefix("RIG_")
    fill, edge = collision_materials()
    model_meshes = [o for o in rig_meshes(weapon) if not o.hide_render]  # (before any collider is made)
    SOURCES.update({r.name: rig_meshes(r) for r in rigs})
    colliders, extra, own_cols, exports, report = [], [], [], [], {}

    custom = getattr(extras, "CUSTOM", {})
    for rig in rigs:
        meshes = [o for o in rig_meshes(rig) if rigid(o)]
        skipped = [o.name for o in rig_meshes(rig) if not rigid(o)]
        if skipped:
            print(f"[{NAME}] no collider for {', '.join(skipped)} (smooth-skinned)")
        special = [o for o in meshes if o.name in custom]
        meshes = [o for o in meshes if o.name not in custom]
        if not meshes:
            continue
        tag = "" if rig is weapon else rig.name.removeprefix(f"RIG_{title}").lower()
        label = f"{NAME}{'_' + tag if tag else ''}_col"
        motion, poses = bone_motion(rig, meshes)
        bone_map = collision_bones(rig, motion)
        if hasattr(extras, "COLLISION_BONES") and rig is weapon:  # (the asset's own: Tensor's fingers in his hands)
            bone_map = {b: extras.COLLISION_BONES(rig).get(b, b) for b in bone_map}
        joined = sorted(b for b, c in bone_map.items() if b != c and b in motion)  # (bones with parts)
        print(f"[{NAME}] {label}: joined to their parents (moving under {MOVE_MAX * 1000:.0f} mm): "
              f"{', '.join(joined) or 'none'}")
        far = {c for c in set(bone_map.values()) if motion.get(c, 0.0) > FAR_MOTION}
        override = getattr(extras, "BONE_OVERRIDE", {}) if rig is weapon else {}
        fixed = [dict(q, mesh=meshes[0].name) for fn in override.values() for q in fn(rig)]
        pieces, count, tol = make_collider(meshes, cover_poses(rig, bone_map, poses), label, bone_map,
                                           rig.matrix_world.inverted(), far, fixed, set(override))
        objs = []
        for mesh in meshes:  # a collider mesh per render mesh (the rifle's optic is its own: the game hides it)
            own = [p for p in pieces if p["mesh"] == mesh.name]
            if own:
                obj = collider_object(f"{mesh.name}Col", own, rig)
                obj.data.materials.append(fill)
                edge_object(obj, edge)
                objs.append(obj)
        report[label] = count
        made = []
        for m in special:  # (the asset's own: a shield's shell, a portal's field)
            got = custom[m.name](rig, m)
            name, ps = got if isinstance(got, tuple) else (f"{m.name}Col", got)
            if not ps:
                print(f"[{NAME}] no collider for {m.name} (the asset's choice)")
                continue
            made.append((name, ps))
        made += [fn(rig) for fn in getattr(extras, "EXTRAS", [])] if rig is weapon else []
        for name, ps in made:
            obj = collider_object(name, ps, rig)
            obj.data.materials.append(fill)
            edge_object(obj, edge)
            objs.append(obj)
            own_cols.append((obj, name.removeprefix(f"SK_{title}").removesuffix("Col").lower()))
            report[name] = sum(len(q["T"]) for q in ps)
            print(f"[{NAME}] {name}: {len(ps)} pieces, {report[name]} triangles (the asset's own)")
        exports.append(([rig, *objs], label, True))
        if rig is weapon:
            colliders += [o for o in objs if all(o is not x for x, _ in own_cols)]
        else:
            extra += [(obj, meshes, f"{tag}") for obj in objs]

    pack = load_pack()
    mount = bpy.data.objects.get("AmmoMount")
    if pack and mount is not None:
        label = f"{NAME}_ammo_col"
        groups = {g.name for o in pack for g in o.vertex_groups}  # (the pack keeps its bone's group: one rigid body)
        root = {g: {h: [np.eye(4)] for h in groups} for g in groups}
        pieces, count, tol = make_collider(pack, root, label)  # (in the pack model's own frame)
        obj = collider_object(f"SM_{title}AmmoCol", pieces)  # (one mesh even if the pack's model has several)
        obj.data.materials.append(fill)
        obj.parent = mount
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = Matrix.Identity(4)
        edge_object(obj, edge)
        report[label] = count
        exports.append(([obj], label, False))
        colliders.append(obj)

    model_meshes += pack
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f"{NAME}_col.blend"), compress=True, copy=True)
    if "--no-render" not in sys.argv:
        render_all(weapon, colliders, model_meshes, extra, own_cols)

    for objs, stem, skinned in exports:
        if not skinned:  # the pack's collider in its own frame (the pack model's), as the pickup is
            objs[0].parent = None
            objs[0].matrix_world = Matrix.Identity(4)
        export(objs, stem, skinned)
    print(f"[{NAME}] colliders: " + ", ".join(f"{k} {v} tris" for k, v in report.items()))


if __name__ == "__main__":
    main()
