"""Convex architectural pieces leave all three shelter approaches open.

The apron and internal impellers are visual only. Every arch is decomposed
along its actual profile; no convex hull bridges a walkable side opening.
"""
import numpy as np
TRI_MAX=500
ALLOWANCE=.045
CUSTOM={'SK_ArchitectureRegolith':lambda rig,mesh:[]}

def hull(points,bone='Root'):
    v,t=engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)

def box(lo,hi,bone='Root'):
    return hull([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)

def root(rig):
    def outline(w,c,z):
        r=w/2
        return [(-r+c,-r,z),(r-c,-r,z),(r,-r+c,z),(r,r-c,z),
                (r-c,r,z),(-r+c,r,z),(-r,r-c,z),(-r,-r+c,z)]
    pieces=[hull(outline(4.60,.32,0)+outline(4.02,.23,.12))]
    outer=[(-1.90,.12),(-1.90,.62),(-1.61,2.03),(-.83,2.96),(1.77,2.96),(1.87,.12)]
    inner=[(-1.45,.12),(-1.45,.60),(-1.18,1.86),(-.57,2.50),(1.24,2.50),(1.24,.12)]
    for s in (-1,1):
        for i in range(5):
            points=[(x,y,z) for x in (s*1.40,s*1.82)
                    for y,z in (outer[i],outer[i+1],inner[i],inner[i+1])]
            pieces.append(hull(points))
    # Complete roof upper band, continuously seated on the two arch crowns.
    pieces.append(hull([(x,y,z) for x in (-1.82,1.82)
        for y,z in ((-.947,2.82),(1.87,2.82),(1.87,2.96),(1.77,3.08),(-.73,3.08),(-.83,2.96))]))
    # Rear bulkhead slabs preserve the rigged service hatch recess.
    pieces.extend([box((-1.4,1.52,.12),(-.273,1.87,2.82)),
        box((.273,1.52,.12),(1.4,1.87,2.82)),
        box((-.273,1.52,.12),(.273,1.87,1.025)),
        box((-.273,1.52,1.935),(.273,1.87,2.82)),
        box((-.273,1.52,1.025),(.273,1.67,1.935))])
    # Sealed pump cartridges: their protected covers block entry.
    for x in (-1.04,1.04):pieces.append(box((x-.345,1.85,1.00),(x+.345,2.08,1.86)))
    return pieces

def hatch(rig):return [box((-.272,1.857,1.026),(.272,1.910,1.934),'ServiceHatch')]

BONE_OVERRIDE={'Root':root,'ServiceHatch':hatch,'CoolantRotorLeft':lambda rig:[],'CoolantRotorRight':lambda rig:[]}
