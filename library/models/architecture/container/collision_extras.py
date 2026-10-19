"""Convex slabs retain the traversable cargo cavity and articulated doors.
Small folds and sealed mechanisms are filled; no gameplay trigger is authored.
"""
import json
import numpy as np
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAME=HERE.name
ALLOWANCE=.045
TRI_MAX=500

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dimensions

def box(lo,hi,bone):
    v,t=engine.hull(np.array([(x,y,z) for x in (lo[0],hi[0])
        for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],dtype=float))
    return dict(bone=bone,V=v,T=t)

def root(rig):
    report=json.loads((HERE/f'{NAME}_rig.json').read_text())
    half=report['dimensions_m']['depth']/dimensions.PLAN[NAME]/2
    double=True
    result=[box((-1.219,-half,0),(1.219,half,.20),'Root'),
            box((-1.219,-half-.03,.20),(-1.047,half+(.03 if double else 0),2.591),'Root'),
            box((1.047,-half-.03,.20),(1.219,half+(.03 if double else 0),2.591),'Root'),
            box((-1.047,-half,2.40),(1.047,half,2.591),'Root')]
    if not double:result.append(box((-1.047,half-.1405,.20),(1.047,half,2.591),'Root'))
    return [dict(piece,bone=piece['bone'],V=np.array([dimensions.point(NAME,v) for v in piece['V']],dtype=float)) for piece in result]

def moving(bone):
    def build(rig):
        source=json.loads((HERE/f'{NAME}_source_report.json').read_text())
        points=np.array([v for p in source if p['bone']==bone for v in p['vertices']])
        return [box(points.min(0),points.max(0),bone)]
    return build

BONE_OVERRIDE={'Root':root,**{bn:moving(bn) for prefix in ('', 'Rear')
    for side in ('Left','Right') for bn in (prefix+side+'Door',prefix+side+'DoorTopBolt',prefix+side+'DoorBottomBolt')}}
