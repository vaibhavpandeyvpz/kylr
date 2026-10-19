"""Convex architectural blocking: four passages and an empty central room.
Hydraulic sleeves and optional regolith have no blocking collision.
"""
import math
import numpy as np
TRI_MAX=1000
MESH_TRI_MAX=500
ALLOWANCE=.10
CUSTOM={'SK_ArchitectureRegolith':lambda rig,mesh:[],
        'SK_HubStructure':lambda rig,mesh:root(rig)}

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions

def hull(points,bone='Root'):
    v,t=engine.hull(np.array([dimensions.point('hub',p) for p in points],dtype=float))
    return dict(bone=bone,V=v,T=t)

def box(lo,hi,bone='Root'):
    return hull([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)

def ring(r,z):
    c=r*.42
    return [(-r+c,-r,z),(r-c,-r,z),(r,-r+c,z),(r,r-c,z),
            (r-c,r,z),(-r+c,r,z),(-r,r-c,z),(-r,-r+c,z)]

def rotate(points,angle):
    c,s=math.cos(angle),math.sin(angle)
    return [(c*x-s*y,s*x+c*y,z) for x,y,z in points]

def root(rig):
    result=[hull(ring(2.78,0)+ring(2.78,.12)),hull(ring(1.28,3.84)+ring(1.35,4.04))]
    # Sloping pressure walls at diagonals, with no hull spanning an entry.
    for i in (1,3,5,7):
        j=(i+1)%8
        result.append(hull([p for r,z in ((2.72,.12),(2.35,.12),(2.50,2.48),(2.35,2.48)) for p in (ring(r,z)[i],ring(r,z)[j])]))
        result.append(hull([p for r,z in ((2.48,2.60),(2.35,2.48),(1.43,3.94),(1.28,3.84)) for p in (ring(r,z)[i],ring(r,z)[j])]))
    for angle in (0,math.pi/2,math.pi,-math.pi/2):
        def add(lo,hi):
            result.append(hull(rotate([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],angle)))
        # Guides and machinery are outside the 1.60m walkable passage.
        for sign in (-1,1):
            x0,x1=sorted((sign*.75,sign*1.11))
            add((x0,-2.735,.12),(x1,-2.14,4.215))
            x0,x1=sorted((sign*1.11,sign*1.44))
            add((x0,-2.73,.12),(x1,-2.35,2.60))
        # Pocket back and cap remain outside the door storage lanes.
        add((-1.11,-2.14,2.52),(1.11,-2.04,3.94))
        add((-1.11,-2.735,4.215),(1.11,-2.14,4.34))
        result.append(hull(rotate([(x,y,z) for x in (-.75,.75) for y,z in ((-2.98,0),(-2.78,0),(-2.78,.12))],angle)))
    return result

def leaf(tag,upper):
    angle={'Front':0,'Left':math.pi/2,'Rear':math.pi,'Right':-math.pi/2}[tag]
    z0,z1,y0,y1=(1.32,2.48,-2.53,-2.41) if upper else (.14,1.30,-2.70,-2.58)
    def build(rig):
        return [hull(rotate([(x,y,z) for x in (-.74,.74) for y in (y0,y1) for z in (z0,z1)],angle),'Door'+tag+('Upper' if upper else 'Lower'))]
    return build

BONE_OVERRIDE={}
for tag in ('Front','Left','Rear','Right'):
    for upper in (False,True):BONE_OVERRIDE['Door'+tag+('Upper' if upper else 'Lower')]=leaf(tag,upper)
    for side in ('Left','Right'):BONE_OVERRIDE['Stage'+tag+side]=lambda rig:[]
