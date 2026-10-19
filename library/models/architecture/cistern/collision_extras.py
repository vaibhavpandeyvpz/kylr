"""Architectural blocking slabs preserve the room and 1.5 m entry void.
Small service fittings/buttress guards are omitted from blocking collision.
"""
import math
import numpy as np
TRI_MAX=1000  # Two blocking meshes; each retains the 500-triangle limit.
MESH_TRI_MAX=500
ALLOWANCE=.085

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions

def hull(points,bone='Root'):
    v,t=engine.hull(np.array([dimensions.point('cistern',p) for p in points],dtype=float))
    return dict(bone=bone,V=v,T=t)

def delivered_hull(points,bone='Root'):
    # Mirrored source pieces already have their delivered height.
    v,t=engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)

def box(lo,hi,bone='Root'):
    return hull([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)

def clip(points,s):
    result=[]
    for a,b in zip(points,points[1:]+points[:1]):
        aa,bb=s*a[0]>=.75,s*b[0]>=.75
        if aa:result.append(a)
        if aa!=bb:
            f=(s*.75-a[0])/(b[0]-a[0]);result.append((s*.75,a[1]+f*(b[1]-a[1])))
    return result

def root(rig):
    result=[]
    for r,z0,z1,n in ((7.5,0,.10,18),(7.15,3.10,3.34,20)):
        points=[(r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),z) for z in (z0,z1) for i in range(n)]
        # Entrance ramp: clip low floor proxy behind the ramp crest.
        if z0==0:
            points=[p for p in points if -6.90<=p[1]<=6.90]
            points.extend((x,y,z) for x in (-2.7,2.7) for y in (-6.90,6.90) for z in (0,.10))
        result.append(hull(points))
    for i in range(1,24):
        if i==12:continue
        a=-math.pi/2-math.tau/48+i*math.tau/24;b=a+math.tau/24
        polygon=[(r*math.cos(t),r*math.sin(t)) for r,t in ((6.50,a),(6.85,a),(6.85,b),(6.50,b))]
        if i==1:polygon=clip(polygon,1)
        if i==23:polygon=clip(polygon,-1)
        if i==11:polygon=clip(polygon,1)
        if i==13:polygon=clip(polygon,-1)
        result.append(hull([(x,y,z) for z in (.10,3.10) for x,y in polygon]))
    result.extend([box((-1.27,-7.30,.10),(-.75,-6.30,2.80)),
                   box((.75,-7.30,.10),(1.27,-6.30,2.80)),
                   box((-1.27,-7.30,2.80),(1.27,-6.30,3.10)),
                   hull([(x,y,z) for x in (-.84,.84) for y,z in ((-7.50,0),(-6.90,0),(-6.90,.10))])])
    for piece in result[-4:]:result.append(delivered_hull([(-x,-y,z) for x,y,z in piece['V']]))
    return result

def leaf(rig):
    from mathutils import Vector
    import model as source
    cartridge=source.PRESSURE_FRAME if hasattr(source,'PRESSURE_FRAME') else source.cs.PRESSURE_FRAME
    return [hull([cartridge@Vector((x,y,z)) for y,w,lo,hi in ((-7.295,.965,.136,2.764),(-7.18,.950,.151,2.749))
        for x,z in ((-w+.16,lo),(w-.16,lo),(w,lo+.16),(w,hi-.16),(w-.16,hi),(-w+.16,hi),(-w,hi-.16),(-w,lo+.16))],'Door')]

BONE_OVERRIDE={'Root':root,'Door':leaf,'Lock':lambda rig:[]}
def rear_leaf(rig):
    return [delivered_hull([(-x,-y,z) for x,y,z in piece['V']],'RearDoor') for piece in leaf(rig)]
BONE_OVERRIDE.update(RearDoor=rear_leaf,RearLock=lambda rig:[])
