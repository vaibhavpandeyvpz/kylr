"""Rigid convex companions, preserving the gap between the module wings.

Small lattice apertures and sealed gearbox interiors are filled. Foundation
openings and the outside panel silhouette are retained. No trigger.
"""
import json
import math
import numpy as np
import model

ALLOWANCE = .045
TRI_MAX = 500


def piece(points,bone=model.ROOT):
    v,t = engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)


def box(lo,hi,bone=model.ROOT):
    return piece([(x,y,z) for x in (lo[0],hi[0])
                  for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)


def tower(rig):
    result = []
    # The foundation's window openings remain open.
    for s in (-1,1):
        result.append(box((-.52,s*.4775-.0425,0),(.52,s*.4775+.0425,.065)))
        result.append(box((s*.4775-.0425,-.435,0),(s*.4775+.0425,.435,.065)))
    for sx in (-1,1):
        for sy in (-1,1):
            # Conservative rectangular web around the six-sided welded beam.
            a=np.array((sx*.465,sy*.465,.037));b=np.array((0,0,.037))
            u=np.array((-sy,sx,0))* .030/math.sqrt(2)
            h=np.array((0,0,.037))
            result.append(piece([p+t*u+q*h for p in (a,b) for t in (-1,1) for q in (-1,1)]))
    def round_hull(stations,bone):
        return piece([(r/math.cos(math.pi/8)*math.cos(i*math.tau/8),
                       r/math.cos(math.pi/8)*math.sin(i*math.tau/8),z)
                      for z,r in stations for i in range(8)],bone)
    result.append(round_hull([(0,.286),(.12,.286),(.145,.235)],model.ROOT))
    result.append(round_hull([(.145,.235),(.325,.235),(.350,.255),(.359,.255)],model.ROOT))
    result.append(round_hull([(.359,.271),(.377,.271),(.400,.210),(.430,.210),(.452,.17)],model.AZIMUTH))
    model.common.CORNER_STEPS=1
    m=model.common.frame((0,-.20,.235),(0,-1,0),(0,0,1))
    result.append(piece([m@model.Vector((x,y,z)) for x in (-.125,.125)
                         for y in (-.1,.1) for z in (-.03,.15)]))
    for s in (-1,1):
        result.append(box((s*.202-.042,-.115,.418),(s*.202+.042,.115,.715),model.AZIMUTH))
    result.append(box((-.16,-.105,.560),(.16,.14,.785),model.ELEVATION))
    result.append(box((-.143,-.154,.785),(.143,.170,3.0),model.ELEVATION))
    # Separate thin convex plates preserve the paired silhouette.
    for i in range(5):
        for s in (-1,1):
            m=model.row_frame(i,s*.54)
            result.append(piece([m@model.Vector((x,y,z))
                for x in (-.411,.411)
                for y in (-model.PANEL_H/2,model.PANEL_H/2) for z in (-.093,.042)],model.ELEVATION))
        result.append(box((-.30,-.154,model.ROW_Z[i]+.070),
                          (.30,.154,model.ROW_Z[i]+.130),model.ELEVATION))
    tris,_ = engine.mesh_islands([o for o in rig.children if o.type=='MESH'],{},rig.matrix_world.inverted())
    worst,share = engine.coverage(result,tris)
    count = sum(len(p['T']) for p in result)
    assert count<=500,count
    assert worst<.0001 and share==1,(worst,share)
    report=dict(triangles=count,pieces=len(result),surface_coverage=share,
                worst_protrusion_m=float(worst),allowance_m=ALLOWANCE,
                animations=['track','service_lower','service_raise'])
    (model.HERE/f'{model.NAME}_collision_report.json').write_text(json.dumps(report,indent=2))
    print(f'[solar_tower] collision PASS: {count} triangles, {len(result)} pieces; 100% sampled coverage',flush=True)
    return result


BONE_OVERRIDE={model.ROOT:tower,model.AZIMUTH:lambda rig:[],model.ELEVATION:lambda rig:[]}
