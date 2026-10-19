"""Analytic riding collider and a separate stepped-on trigger.
Tangential belt motion uses a fixed smooth collider; covers keep hinge weights.
"""
import json
import math
from pathlib import Path
import numpy as np
engine=None
HERE=Path(__file__).resolve().parent
INFO=json.loads((HERE/"speed_ramp_rig.json").read_text())
B=INFO["authoring_belt"]
SCALE=INFO['delivery_scale']
OFFSET=np.array((0,0,INFO['ground_offset_m']))
ENTRY,EXIT,T,N=[np.array(B[k]) for k in ("entry","exit","axis","normal")]
TOP=B["surface_offset_m"]


def hull(bone,points):
    v,t=engine.hull(np.array(points));return {"bone":bone,"V":v*SCALE+OFFSET,"T":t}

def box(bone,lo,hi):
    return engine.box(bone,np.array(lo)*SCALE+OFFSET,np.array(hi)*SCALE+OFFSET)


def surface(x0,x1,a,b,bottom=-.31):
    return hull("Root",[(x,p[1],z) for p in (a,b) for x in (x0,x1) for z in (bottom,p[2])])


def fixed(rig):
    a,b=ENTRY+N*TOP,EXIT+N*TOP
    low_a,low_b=ENTRY-N*TOP,EXIT-N*TOP
    # The top and return tangencies have different Y coordinates on an incline.
    # Include both: a vertical wedge ending at the top lip misses the lower run.
    points=[a,b,low_a,low_b,np.array((0,a[1],-.31)),np.array((0,low_b[1],-.31))]
    pieces=[hull("Root",[(x,p[1],p[2]) for x in (-1.024,1.024) for p in points])]
    for s in (-1,1):
        vertices=[]
        for y,top,w in INFO["authoring_shroud_stations"]:
            shoulder=[(w-.025+.025*math.cos(i*math.pi/6),top-.025+.025*math.sin(i*math.pi/6)) for i in range(4)]
            vertices += [(s*x,y,z) for x,z in [(1.026,-.31),(1.5,-.31),(w,-.28),*shoulder,
                         (1.12,top),(1.026,top-.075)]]
        pieces.append(hull("Root",vertices))
    for center,sign in ((ENTRY,-1),(EXIT,1)):
        arc=[center+(N*math.cos(i*math.pi/6)+sign*T*math.sin(i*math.pi/6))*TOP for i in range(7)]
        for p,q in zip(arc,arc[1:]):
            pieces.append(hull("Root",[(x,v[1],v[2]) for x in (-1.024,1.024) for v in (center,p,q)]))
    y=INFO['authoring_nose_y']
    pieces += [box("Root",(-1.28,y-.026,-.31),(1.28,y+.026,.45))]
    return pieces


def cover(side):
    def make(rig):
        s=1 if side=="Left" else -1
        return [box(side+"Service",(min(s*1.302,s*1.318),-.405,.044),
                           (max(s*1.302,s*1.318),.075,.338))]
    return make


def trigger(rig):
    a,b=ENTRY+N*TOP,EXIT+N*TOP
    return "SK_SpeedRampTrigger",[hull("Root",[(x,p[1],p[2]+z) for p in (a,b)
                                             for x in (-.985,.985) for z in (-.008,.13)])]


BONE_OVERRIDE={"Root":fixed,"Drive":lambda r:[],"Idler":lambda r:[],
               "LeftService":cover("Left"),"RightService":cover("Right")}
for side in ("Left","Right"):
    for i in range(B["station_count_per_lane"]):BONE_OVERRIDE[f"{side}Tread{i:02}"]=lambda r:[]
EXTRAS=[trigger]
