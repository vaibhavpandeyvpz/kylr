"""Static solid proxy: the cage apertures are too small for traversal.

Three coaxial convex pieces preserve the pedestal/head neck and domed crown.
The guard's small apertures and fastener sockets are conservatively filled.
"""
import json
import math
import numpy as np
import model

ALLOWANCE = .045


def hull(stations, n=24):
    # Circumscribed rings keep every render facet inside the proxy.
    points = [(r/math.cos(math.pi/n)*math.cos(i*math.tau/n),
               r/math.cos(math.pi/n)*math.sin(i*math.tau/n), z)
              for z, r in stations for i in range(n)]
    v, t = engine.hull(np.array(points))
    return dict(bone=model.ROOT, V=v, T=t)


def lantern(rig):
    pieces = [hull([(0, .230), (.048, .230)], 24),
              hull([(.048, .184), (.510, .184), (.530, .165)], 16),
              hull([(.530, .180), (.542, .180), (.614, .321),
                    (.678, .391), (.752, .391), (.822, .339),
                    (.900, .276), (.928, .267), (.974, .204),
                    (1.0, .100)], 16)]
    triangles, _ = engine.mesh_islands([o for o in rig.children if o.type == 'MESH'],
                                      {}, rig.matrix_world.inverted())
    worst, share = engine.coverage(pieces, triangles)
    count = sum(len(p['T']) for p in pieces)
    assert count <= 500, count
    assert worst < .0001 and share == 1, (worst, share)
    (model.HERE/'beacon_lantern_collision_report.json').write_text(json.dumps(dict(
        triangles=count, pieces=len(pieces), surface_coverage=share,
        worst_protrusion_m=float(worst), allowance_m=ALLOWANCE), indent=2))
    return pieces


BONE_OVERRIDE = {model.ROOT: lantern}
