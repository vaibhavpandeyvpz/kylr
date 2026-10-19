"""Pickup collision LOD: solid lathed body sections and a closed circular cassette.
Internal bores/inspection ports are visual detail; grip and stock openings retain
the default convex decomposition. Moving ram and grenade keep their own bones.
"""
import math
import numpy as np

def SOLID_ISLAND(piece):
    lo, hi = piece['lo'], piece['hi']
    solid = (piece['bone'] == 'Root' and lo[0] < -.030 and hi[0] > .030
             and lo[2] > .11 and hi[2] > .225 and lo[1] <= .050
             and hi[1]-lo[1] > .035)
    if solid:
        print(f"[grenade_launcher] solid body proxy: {len(piece['T'])} hull triangles", flush=True)
    return solid

def AMMO_CUSTOM(objects):
    points = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in objects])
    pieces=[]
    def add(p):
        V,T=engine.hull(p)
        pieces.append(dict(bone='Root',V=V,T=T))
    # Circumscribed octagon keeps the full drum silhouette, with <7 mm bulge.
    radius=.080/math.cos(math.pi/8)
    add(np.array([(radius*math.cos(math.pi/8+i*math.pi/4), y,
                   .092+radius*math.sin(math.pi/8+i*math.pi/4))
                  for y in (-.059,.059) for i in range(8)]))
    # Integral palm flat and the two concealed magazine tangs.
    foot=points[points[:,2]<.035]
    top=foot.copy();top[:,2]=.040
    add(np.concatenate([foot,top]))
    for sign in (-1,1):
        tang=points[(points[:,1]>.059)&(points[:,0]*sign>.015)]
        if len(tang):add(tang)
    return pieces
