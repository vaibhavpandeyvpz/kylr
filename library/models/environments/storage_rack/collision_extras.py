"""Static load-bearing rack proxy, 43 convex pieces / 500 triangles.

Open bays and picking-bin interiors remain open. Punched grate holes are too
small for a player's foot and use continuous shelf collision. Slender braces
use enclosing triangular sections; the 500-triangle budget permits a maximum
80 mm stand-off, as with the generic generator's budget-driven coarse fit.
"""
import importlib.util
from pathlib import Path

import numpy as np
from mathutils import Vector

spec=importlib.util.spec_from_file_location('storage_rack_collision_spec',Path(__file__).with_name('model.py'))
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)


def convex(points):
    v,t=engine.hull(np.array(points,dtype=float))
    return {'bone':'Root','V':v,'T':t}


def beam(a,b,width=.072,thickness=.038,square=False):
    """Six-vertex enclosing triangular prism round a rectangular brace."""
    a,b=Vector(a),Vector(b)
    axis=(b-a).normalized()
    across=Vector((1,0,0))
    up=axis.cross(across).normalized()
    # This triangle encloses the entire width x thickness rectangle; none of
    # the rendered brace can poke out. Plane fitting uses the same tradeoff.
    cross=([(-thickness/2,-width/2),(thickness/2,-width/2),
            (thickness/2,width/2),(-thickness/2,width/2)] if square else
           [(-thickness/2,-width/2),(-thickness/2,1.5*width),
            (1.5*thickness,-width/2)])
    return convex([p+across*u+up*v for p in (a,b) for u,v in cross])


def root(_rig):
    out=[]
    # Each support also encloses the end casting's continuous vertical rail.
    # Their inner edge is y=+/- .194, so an 80 mm half-depth includes both the
    # upright and this rail while retaining the large openings between them.
    for x in (-source.POST_X,source.POST_X):
        for y in (-source.POST_Y,source.POST_Y):
            out.append(convex([(x+dx*r,y+dy*.08,z) for z,r in ((0,.0755),(1.90,.04))
                               for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1))]))
    for top in source.SHELVES:
        out.append(engine.box('Root',(-.63,-.273,top-.070),(.63,.27,top+.016)))
    for x in (-source.POST_X,source.POST_X):
        for z0,z1 in ((.36,.91),(.97,1.52)):
            # Cast diagonals meet the posts, not a bounding slab filling a bay.
            for sign in (-1,1):
                out.append(beam((x,sign*-.23,z0),(x,sign*.23,z1)))
            for z in (z0+.018,z1-.018):
                out.append(beam((x,-.23,z),(x,.23,z),.036,square=True))
        out.append(beam((x,-.23,1.6025),(x,.23,1.6025),.045))
        out.append(beam((x,-.23,1.8275),(x,.23,1.8275),.045))
    for x,top in ((-.43,source.SHELVES[2]),(-.11,source.SHELVES[2]),
                  (.11,source.SHELVES[1]),(.43,source.SHELVES[1])):
        profile=[(-.19,top),(.19,top),(.19,top+.24),(-.07,top+.24),(-.19,top+.11)]
        for lo,hi in ((-.145,-.131),(.131,.145)):
            out.append(convex([(x+dx,y,z) for dx in (lo,hi) for y,z in profile]))
        # The entire sole is already contained by its shelf's continuous
        # collision slab, including its 14 mm material thickness.
        out.append(engine.box('Root',(x-.131,.176,top+.014),(x+.131,.19,top+.24)))
        # The front wall terminates on the actual sloping mouth section.
        front=[(-.19,top+.014),(-.177,top+.014),
               (-.177,top+.11+.013*.13/.12),(-.19,top+.11)]
        out.append(convex([(x+dx,y,z) for dx in (-.131,.131) for y,z in front]))
    assert len(out)==43
    assert sum(len(p['T']) for p in out)==500
    return out


BONE_OVERRIDE={'Root':root}
TRI_MAX=500
PIECE_MAX=43
