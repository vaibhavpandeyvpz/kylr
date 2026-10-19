"""Fitted convex courses preserve the dome cavity and the open passage.

One collider per glazing course and separate foundation/entry colliders keep every
mesh below 500 triangles. The door's own collider follows Door. Lock and pins
are mechanical detail rather than separate player-blocking volumes.
"""
import math
import sys
from pathlib import Path
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import dimensions
N=20
PHI=(0,.40,.78,1.15,1.445)
R,Z,WALL=2.92,.18,.045
TRI_MAX=500
ALLOWANCE=.02


def piece(points,bone='Root'):
    points=[dimensions.point('lunar_dome',p) for p in points]
    v,t=engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)


def clipped(points,axis,threshold,positive=True):
    # Convex clipping: retain vertices and all intersecting chords; the hull
    # restores only the convex slice, with no concave cavity filled in.
    inside=lambda p:(p[axis]>=threshold if positive else p[axis]<=threshold)
    result=[p for p in points if inside(p)]
    for a in points:
        for b in points:
            if inside(a)==inside(b):continue
            t=(threshold-a[axis])/(b[axis]-a[axis])
            result.append(tuple(a[j]+t*(b[j]-a[j]) for j in range(3)))
    return result


def cell(i,p,q):
    result=[]
    for inside in (False,True):
        radius=R-(WALL if inside else 0)
        for phi in (p,q):
            for j in (i,i+1):
                angle=j*math.tau/N
                result.append((radius*math.cos(phi)*math.cos(angle),radius*math.cos(phi)*math.sin(angle),Z+radius*math.sin(phi)))
    return result


def course(index):
    parts=[]
    for i in range(N):
        points=cell(i,PHI[index],PHI[index+1])
        if i in (14,15) and index<2:
            for positive in (False,True):
                clip=clipped(points,0,.70 if positive else -.70,positive)
                if len(clip)>=4:parts.append(piece(clip))
            if index==1:parts.append(piece(clipped(points,2,2.04)))
        elif i in (14,15) and index==2:
            parts.append(piece(clipped(points,2,2.04)))
        else:parts.append(piece(points))
    if index==3:
        parts.append(piece([(r*math.cos(i*math.tau/N),r*math.sin(i*math.tau/N),z)
            for r,z in ((.30,3.05),(.35,3.11),(.30,3.16)) for i in range(N)]))
    assert sum(len(p['T']) for p in parts)<=500
    return f'SK_LunarDomeCanopy{index+1}Col',parts


def floor_entry(rig):
    parts=[piece([(2.76*math.cos(i*math.tau/N),2.76*math.sin(i*math.tau/N),z) for z in (0,.10) for i in range(N)])]
    for i in range(N):
        points=[(r*math.cos(j*math.tau/N),r*math.sin(j*math.tau/N),z)
            for r,z in ((3,0),(3,.10),(2.92,.18),(2.76,0),(2.76,.18)) for j in (i,i+1)]
        if i in (14,15):
            for positive in (False,True):
                clip=clipped(points,0,.716 if positive else -.716,positive)
                if len(clip)>=4:parts.append(piece(clip))
            rear=clipped(points,1,-2.86)
            for positive in (False,True):
                clip=clipped(rear,0,.51 if positive else -.51,positive)
                if len(clip)>=4:parts.append(piece(clip))
        else:parts.append(piece(points))
    parts.append(piece([(x,y,z) for x in (-.51,.51) for y in (-2.94,-1.70) for z in (0,.10)]))
    assert sum(len(p['T']) for p in parts)<=500
    return 'SK_LunarDomeFoundationCol',parts


def entry(rig):
    # Match both the wider leaf counterbore and the chamfered passage.
    # Each station is y, outer halfwidth, roof, aperture halfwidth/top/chamfer.
    stations=[(-2.94,.64,2.19,.57,2.105,.13),
        (-2.875,.68875,2.23875,.57,2.105,.13),
        (-2.875,.68875,2.23875,.51,2.04,.12),
        (-2.86,.70,2.25,.51,2.04,.12),
        (-2.25,.70,2.25,.51,2.04,.12),
        (-1.85,.58,2.16,.51,2.04,.12)]
    parts=[]
    for a,b in zip(stations,stations[1:]):
        if a[0]==b[0]:continue
        for s in (-1,1):
            parts.append(piece([(s*x,y,z) for y,w,top,iw,it,ch in (a,b) for x in (iw,w) for z in (.10,top)]))
            # Chamfered feet below the clear opening also carry the shroud.
            parts.append(piece([(s*x,y,z) for y,w,top,iw,it,ch in (a,b)
                for x,z in ((iw,0),(w-.13,0),(w,.13),(iw,.10))]))
            parts.append(piece([(s*x,y,z) for y,w,top,iw,it,ch in (a,b)
                for x,z in ((iw-ch,it),(iw,it-ch),(iw,it))]))
            parts.append(piece([(s*x,y,z) for y,w,top,iw,it,ch in (a,b)
                for x,z in ((iw-ch,.10),(iw,.10),(iw,.10+ch))]))
        parts.append(piece([(x,y,z) for y,w,top,iw,it,ch in (a,b) for x in (-w,w) for z in (it,top)]))
    for centre in (.43,1.82):
        parts.append(piece([(.59+.028*math.cos(i*math.tau/8),-2.97+.028*math.sin(i*math.tau/8),z)
            for z in (centre-.112,centre+.112) for i in range(8)]))
    assert sum(len(p['T']) for p in parts)<=500
    return 'SK_LunarDomeEntryCol',parts


def leaf(rig):
    # The leaf is a convex chamfered plate; include the welded hinge necks.
    points=[]
    for x,z in [(-.418,.111),(.418,.111),(.548,.241),(.548,1.959),
                (.418,2.089),(-.418,2.089),(-.548,1.959),(-.548,.241)]:
        for y in (-2.927,-2.885):points.append((x,y,z))
    for centre in (.43,1.82):
        points += [(.59+.024*math.cos(i*math.tau/8),-2.97+.024*math.sin(i*math.tau/8),z)
            for z in (centre-.040,centre+.040) for i in range(8)]
        points += [(x,-2.905,z) for x in (.578,.602) for z in (centre-.040,centre+.040)]
    return [piece(points,'Door')]

BONE_OVERRIDE={'Root':lambda rig:[],'Door':leaf,'Lock':lambda rig:[]}
EXTRAS=[floor_entry,entry]+[(lambda rig,index=i:course(index)) for i in range(4)]
