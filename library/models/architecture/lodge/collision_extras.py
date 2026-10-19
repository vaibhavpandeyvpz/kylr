"""Convex architectural blocking, retaining room and both entrance voids.

Optional regolith and small roof/door fittings have no blocking collider.
"""
import math
import numpy as np
TRI_MAX=1000
MESH_TRI_MAX=500
ALLOWANCE=.085
CUSTOM={'SK_ArchitectureRegolith':lambda rig,mesh:[]}

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions

def hull(points,bone='Root'):
    v,t=engine.hull(np.array([dimensions.point('lodge',p) for p in points],dtype=float))
    return dict(bone=bone,V=v,T=t)

def delivered_hull(points,bone='Root'):
    # Mirrored source pieces already have their delivered height.
    v,t=engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)

def box(lo,hi,bone='Root'):
    return hull([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)

def outline(r,c):
    pts=[]
    for cx,cy,start in ((r-c,r-c,0),(-r+c,r-c,90),(-r+c,-r+c,180),(r-c,-r+c,270)):
        for i in range(2):
            a=math.radians(start+i*90);pts.append((cx+c*math.cos(a),cy+c*math.sin(a)))
    return pts

def clip(poly,sign):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        inside_a,inside_b=sign*a[0]>=.75,sign*b[0]>=.75
        if inside_a:out.append(a)
        if inside_a!=inside_b:
            t=(sign*.75-a[0])/(b[0]-a[0]);out.append((sign*.75,a[1]+t*(b[1]-a[1])))
    return out

def clip_axis(poly,axis,threshold,sign):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        aa,bb=sign*(a[axis]-threshold)>=0,sign*(b[axis]-threshold)>=0
        if aa:out.append(a)
        if aa!=bb:
            t=(threshold-a[axis])/(b[axis]-a[axis])
            out.append(tuple(a[d]+t*(b[d]-a[d]) for d in range(2)))
    return out

def root(rig):
    floor=outline(7.5,.85)
    middle=clip_axis(clip_axis(floor,1,-6.9,1),1,6.9,-1)
    ps=[hull([(x,y,z) for z in (0,.1) for x,y in middle]),
        hull([(x,y,z) for r,z,c in ((6.50,3.10,.60),(6.32,3.93,.62),(6.32,3.98,.62)) for x,y in outline(r,c)])]
    # Low-poly crown wedges retain the overhanging eave and upper coaming.
    # The planar hull deviates at most 74 mm from the formed shoulder.
    crown=[(outline(r,c),z) for r,z,c in ((6.5,3.,.60),(7.1,3.,.85),
        (7.1,3.16,.85),(6.32,4.14,.62),(5.98,4.14,.55),(5.98,3.98,.55))]
    for i in range(8):
        j=(i+1)%8
        ps.append(hull([(x,y,z) for pts,z in crown for x,y in (pts[i],pts[j])]))
    inside=outline(6.50,.60);outside=outline(6.85,.70)
    skirt_sections=[(outline(r,c),z) for r,z,c in ((7.4,.1,.85),(7.4,.22,.85),(6.95,.75,.72),(6.85,.8,.70))]
    for i in range(8):
        j=(i+1)%8
        p=[inside[i],outside[i],outside[j],inside[j]]
        entrance=abs(p[0][1])>6.49 and abs(p[-1][1])>6.49
        if entrance:
            for sign in (-1,1):
                clipped=clip(p,sign)
                ps.append(hull([(x,y,z) for z in (.80,3.10) for x,y in clipped]))
            ps.append(hull([(x,y,z) for z in (2.80,3.10) for x,y in p]))
        else:ps.append(hull([(x,y,z) for z in (.80,3.10) for x,y in p]))
        skirts=[]
        for points,z in skirt_sections:
            skirts.append(([(inside[i][0],inside[i][1]),points[i],points[j],(inside[j][0],inside[j][1])],z))
        if entrance:
            for sign in (-1,1):ps.append(hull([(x,y,z) for polygon,z in skirts for x,y in clip(polygon,sign)]))
        else:ps.append(hull([(x,y,z) for polygon,z in skirts for x,y in polygon]))
    front=[box((-1.27,-7.30,.10),(-.75,-6.30,2.80)),
           box((.75,-7.30,.10),(1.27,-6.30,2.80)),
           box((-1.27,-7.30,2.80),(1.27,-6.30,3.10)),
           hull([(x,y,z) for x in (-.84,.84) for y,z in ((-7.5,0),(-6.9,0),(-6.9,.10))])]
    low=clip_axis(floor,1,-6.9,-1)
    for threshold,sign in ((-.84,-1),(.84,1)):
        side=clip_axis(low,0,threshold,sign)
        front.append(hull([(x,y,z) for z in (0,.1) for x,y in side]))
    ps+=front
    ps.extend(delivered_hull([(-x,-y,z) for x,y,z in p['V']]) for p in front)
    for x,y,w,h in ((-3.75,-3.7,1.8,1.6),(3.75,-3.7,1.8,1.6),(-3.75,3.4,1.8,1.6),(3.75,3.4,1.8,1.6)):
        points=[]
        for ww,hh,c,z in ((w+.18,h+.18,.13,3.98),(w,h,.16,4.43),(w-.18,h-.18,.13,4.61)):
            points.extend((x+xx,y+yy,z) for xx,yy in
                          ((-ww/2+c,-hh/2),(ww/2-c,-hh/2),(ww/2,-hh/2+c),(ww/2,hh/2-c),
                           (ww/2-c,hh/2),(-ww/2+c,hh/2),(-ww/2,hh/2-c),(-ww/2,-hh/2+c)))
        ps.append(hull(points))
    return ps

def leaf(rig):
    from mathutils import Vector
    import model as source
    cartridge=source.PRESSURE_FRAME if hasattr(source,'PRESSURE_FRAME') else source.cs.PRESSURE_FRAME
    return [hull([cartridge@Vector((x,y,z)) for y,w,lo,hi in ((-7.295,.965,.136,2.764),(-7.18,.950,.151,2.749))
        for x,z in ((-w+.16,lo),(w-.16,lo),(w,lo+.16),(w,hi-.16),(w-.16,hi),(-w+.16,hi),(-w,hi-.16),(-w,lo+.16))],'Door')]

def rear_leaf(rig):
    return [delivered_hull([(-x,-y,z) for x,y,z in p['V']],'RearDoor') for p in leaf(rig)]

BONE_OVERRIDE={'Root':root,'Door':leaf,'RearDoor':rear_leaf,'Lock':lambda rig:[],'RearLock':lambda rig:[]}
