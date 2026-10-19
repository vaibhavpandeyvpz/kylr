"""Convex architectural blockers preserve pressure-room and door voids."""
import numpy as np
from mathutils import Vector
import model as source
TRI_MAX=500
ALLOWANCE=.02
OUTER=source.OUTER
INNER=source.INNER
RAMP_HALF=max(abs(x) for x,z in source.portal_offset(.59) if abs(z-source.DECK)<1e-7)*source.ENTRY_RESIZE[0][0]
PORTAL=[(x*source.ENTRY_RESIZE[0][0],source.DECK+(z-source.DECK)*source.ENTRY_RESIZE[2][2]) for x,z in source.PORTAL]
RIB=[(-4.34,.15),(4.34,.15),(4.66,.47),(4.66,3.55),(3.65,4.56),(-3.65,4.56),(-4.66,3.55),(-4.66,.47)]

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions

def hull(points,bone='Root'):
    v,t=engine.hull(np.array([dimensions.point('hangar',p) for p in points],dtype=float))
    return dict(bone=bone,V=v,T=t)

def slab(a,b,y0,y1):
    return hull([(x,y,z) for y in (y0,y1) for x,z in (a+b)])

def root(rig):
    result=[hull([(x,y,z) for x in (-RAMP_HALF,RAMP_HALF) for y,z in ((-5.5,0),(5.1,0),(5.1,.15),(-5.08,.15))])]
    for span in ((-4.5,-RAMP_HALF),(RAMP_HALF,4.5)):
        result.append(hull([(x,y,z) for x in span for y in (-5.08,5.1) for z in (0,.15)]))
    for i in range(1,8):
        j=(i+1)%8
        result.append(slab([OUTER[i],OUTER[j]],[INNER[i],INNER[j]],-4.68,4.88))
        aperture=[(x*source.ENTRY_RESIZE[0][0],source.DECK+(z-source.DECK)*source.ENTRY_RESIZE[2][2]) for x,z in source.portal_offset(.59)]
        result.append(slab([OUTER[i],OUTER[j]],[aperture[i],aperture[j]],-4.90,-4.68))
    result.append(hull([(x,y,z) for y in (4.88,5.10) for x,z in OUTER]))
    # Collar stays outside the nominal entry boundary.
    collar=[(x*source.ENTRY_RESIZE[0][0],source.DECK+(z-source.DECK)*source.ENTRY_RESIZE[2][2]) for x,z in source.portal_offset(.59)]
    for i in range(1,8):
        j=(i+1)%8
        result.append(slab([collar[i],collar[j]],[PORTAL[i],PORTAL[j]],-4.90,-4.74))
    # Dominant exposed ribs; tiny utility clamps and control fittings omitted.
    for y in (-4.77,-1.58,1.75,4.97):
        for i in (2,4,6):
            j=(i+1)%8
            result.append(slab([RIB[i],RIB[j]],[OUTER[i],OUTER[j]],y-.11,y+.11))
    return result

def leaf(s,bone):
    p=source.half_leaf(s)
    return [hull([source.ENTRY_FRAME@Vector((x,y,z)) for y in (-2.204,-2.33) for x,z in p],bone)]

BONE_OVERRIDE={'Root':root,'LeftDoor':lambda rig:leaf(1,'LeftDoor'),
    'RightDoor':lambda rig:leaf(-1,'RightDoor'),'LeftDoorBolt':lambda rig:[],
    'RightDoorBolt':lambda rig:[]}
