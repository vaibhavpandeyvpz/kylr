"""Convex architectural slabs preserve entry and pressure-room void.
No trigger or game integration. Moving lock hardware inherits its door.
"""
import math
import numpy as np
TRI_MAX=500
ALLOWANCE=.045

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions

def hull(points,bone='Root'):
    points=np.array(points,dtype=float)
    points[:,1]+=.30
    points[:,2]*=dimensions.HEIGHT['bunker']
    v,t=engine.hull(points)
    return dict(bone=bone,V=v,T=t)

def box(lo,hi,bone='Root'):
    return hull([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)

def ring(r,z):
    c=r*.42
    return [(-r+c,-r,z),(r-c,-r,z),(r,-r+c,z),(r,r-c,z),
            (r-c,r,z),(-r+c,r,z),(-r,r-c,z),(-r,-r+c,z)]

def root(rig):
    result=[hull(ring(3.3,0)+ring(3.12,.12)),hull(ring(2.22,3.20)+ring(2.30,3.38))]
    for i in range(1,8):
        j=(i+1)%8
        for z0,z1,ro0,ro1,ri0,ri1 in ((.12,2.61,3.3,2.61,3.12,2.48),(2.61,3.20,2.61,2.40,2.48,2.22)):
            points=[]
            for r,z in ((ro0,z0),(ri0,z0),(ro1,z1),(ri1,z1)):
                points.extend((ring(r,z)[i],ring(r,z)[j]))
            result.append(hull(points))
    # Front wall has a real 1.35 m passage; side slabs taper above the entry.
    for s in (-1,1):
        points=[]
        for z,outer,inner in ((.12,3.3,3.12),(2.37,2.672,2.544)):
            for y,r in ((-outer,outer),(-inner,inner)):
                points.extend([(s*.675,y,z),(s*r*.58,y,z)])
        result.append(hull(points))
    result.append(hull([p for r,z in ((2.672,2.37),(2.544,2.37),(2.30,3.38),(2.22,3.20)) for p in ring(r,z)[:2]]))
    result.extend([box((-.98,-3.4,.12),(-.675,-2.38,2.37)),box((.675,-3.4,.12),(.98,-2.38,2.37)),
                   box((-.98,-3.4,2.37),(.98,-2.38,2.60)),
                   hull([(-.67,-4.10,0),(.67,-4.10,0),(-.67,-3.4,0),(.67,-3.4,0),(-.67,-3.4,.12),(.67,-3.4,.12)])])
    return result

def leaf(rig):
    return [box((-.731,-3.48,.127),(.731,-3.385,2.425),'Door')]

BONE_OVERRIDE={'Root':root,'Door':leaf,'TopBolt':lambda rig:[],'BottomBolt':lambda rig:[]}
