"""Convex pressure-wall bands retain the cabin and doorway; no occupancy area."""
import json, numpy as np
from pathlib import Path
HERE=Path(__file__).resolve().parent
ALLOWANCE=.02
TRI_MAX=500

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions
BODY_RISE=.20
LANDING_FOOT_X=1.70

def section(w,low,high,c,y):
    return [(x,y,z) for x,z in [(-w/2+c,low),(w/2-c,low),(w/2,low+c),
        (w/2,high-c),(w/2-c,high),(-w/2+c,high),(-w/2,high-c),(-w/2,low+c)]]

def hull(points,bone='Root'):
    v,t=engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)

def bands(outer,inner):
    return [hull([row[j] for row in [*outer,*inner] for j in (i,(i+1)%8)]) for i in range(8)]

def root(rig):
    rows=[section(3.202,.38,3.186,.72,-1.48),section(3.5,.38,3.32,.75,-.95),
          section(3.5,.38,3.32,.75,.95),section(3.210,.386,3.186,.72,1.46)]
    inside=[section(3.16,.55,2.96,.54,y) for y in (-1.48,-.95,.95,1.46)]
    def raised(rows):return [[(x,y,z+BODY_RISE) for x,y,z in row] for row in rows]
    pieces=[]
    # Each band lies outside one fixed supporting plane of the convex cabin.
    # Its longitudinal outer loft is convex, so one hull preserves all stations.
    pieces+=bands(raised(rows),raised(inside))
    pieces+=bands(raised([section(2.9,.4,3.05,.65,-1.7),rows[0]]),
        raised([section(1.2,.55,2.66,.13,y) for y in (-1.7,-1.48)]))
    pieces.append(hull(raised([[*rows[-1],*section(2.9,.4,3.05,.65,1.65)]])[0]))
    for s in (-1,1):
        for y in (-.70,.70):
            a=np.array((s*.88,y,.25+BODY_RISE));b=np.array((s*LANDING_FOOT_X,y,.085))
            d=(b-a)/np.linalg.norm(b-a);n=np.array((-d[2],0,d[0]))
            # Circumscribed hexagonal end caps enclose the authored circular
            # eyes with at most 12.4 mm excess, preserving their full extent.
            r0,r1=.08,.055;q=1/np.sqrt(3)
            profile=[a+n*r0*(2*q),a-d*r0+n*r0*q,a-d*r0-n*r0*q,a-n*r0*(2*q),
                     b-n*r1*(2*q),b+d*r1-n*r1*q,b+d*r1+n*r1*q,b+n*r1*(2*q)]
            pieces.append(hull([p+np.array((0,t,0)) for p in profile for t in (-.05,.05)]))
            pieces.append(hull([(x,v,z) for x in (s*LANDING_FOOT_X-.19,s*LANDING_FOOT_X+.19)
                               for v in (y-.15,y+.15) for z in (0,.025)]))
    return [dict(p,V=np.array([dimensions.point('habitat_pod',v) for v in p['V']],dtype=float)) for p in pieces]

def door(rig):
    source=json.loads((HERE/'habitat_pod_source_report.json').read_text())
    return [hull(next(p['vertices'] for p in source if p['label'].startswith('formed pressure door')),'Door')]

BONE_OVERRIDE={'Root':root,'Door':door,'Lock':lambda rig:[]}
