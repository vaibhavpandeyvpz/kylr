"""Coarse rigid convex pieces preserving the reflector bowl and frame passage.

Thin fasteners, small loom apertures and the side tower knee-brace bays are
filled; the central frame opening and parabolic reflecting aperture stay open.
The runtime budget is 500 triangles. Coverage is checked against actual mesh
samples, independently of the modelling geometry audit.
"""
import json
import math
import numpy as np
import model

ALLOWANCE=.10
TRI_MAX=500


def piece(points,bone=model.ROOT):
    v,t=engine.hull(np.array(points,dtype=float))
    return dict(bone=bone,V=v,T=t)


def box(lo,hi,bone=model.ROOT):
    return piece([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)


def beam(a,b,r,bone=model.ROOT):
    a,b=model.Vector(a),model.Vector(b);d=(b-a).normalized()
    ref=model.Vector((0,0,1)) if abs(d.z)<.9 else model.Vector((1,0,0))
    u=d.cross(ref).normalized()*r;v=d.cross(u).normalized()*r
    return piece([p+s*u+t*v for p in (a,b) for s in (-1,1) for t in (-1,1)],bone)


def assembly(rig):
    ps=[box((-1.21,-.72,0),(1.21,.72,.145)),
        box((-.29,-.224,.14),(.338,.22,.49)),
        box((-.145,.196,.555),(.145,.32,.845)),
        box((1.235,.115,1.79),(1.394,.405,2.145))]
    for s in (-1,1):
        # Rectangular side bays keep the full central opening unobstructed.
        ps.append(box((s*1.10-.145,-.60,.14),(s*1.10+.145,.67,2.145)))
        for a,b in (((s*1.01,.26,.30),(0,.26,.70)),
                    ((s*1.01,.26,1.64),(0,.26,.70))):
            ps.append(beam(a,b,.085))
    points=[(.335,.12,.33),(.48,.12,.33),(.68,.44,.33),
            (1.10,.62,.50),(1.10,.62,1.76),(1.31,.62,1.80),
            (1.31,.26,1.80),(1.31,.26,1.845)]
    for index in (0,1,2,4,5):
        a,b=map(model.Vector,(points[index],points[index+1]));axis=(b-a).normalized()
        ps.append(beam(a-axis*.012,b+axis*.012,.030))
    # Two radial bands in eight angular wedges follow the paraboloid instead
    # of using a convex disc that fills the entire front aperture.
    secant=1/math.cos(math.pi/8)
    for i in range(8):
        angles=[i*math.tau/8,(i+1)*math.tau/8]
        for r0,r1,back0,back1 in ((0,.70,.365,.10),(.70,1.025,.10,-.139)):
            verts=[]
            for r,back in ((r0,back0),(r1,back1)):
                rr=r*secant
                front=.12-.30*rr*rr-.006
                for a in angles:
                    for y in (front,back):verts.append((rr*math.cos(a),y,2+rr*math.sin(a)))
            ps.append(piece(verts,model.ELEV))
    ps.append(box((-.217,.14,1.783),(.217,.366,2.217),model.ELEV))
    ps.append(box((-.21,model.FOCUS_Y-.149,1.79),(.21,model.FOCUS_Y+.003,2.21),model.ELEV))
    for s in (-1,1):
        ps.append(box((min(0,s*1.239),.165,1.905),(max(0,s*1.239),.355,2.095),model.ELEV))
    for i in range(3):
        a=math.pi/2+i*math.tau/3;c,s=math.cos(a),math.sin(a)
        at=model.Vector((.91*c,.12-.30*.91**2,2+.91*s))
        n=model.Vector((-.57*c,-1,-.57*s)).normalized()
        m=model.common.frame(at,n,(-s,0,c))
        ps.append(piece([m@model.Vector((x,y,z)) for x in (-.061,.061) for y in (-.076,.076) for z in (-.004,.035)],model.ELEV))
        target=model.Vector((.145*c,model.FOCUS_Y-.065,2+.145*s))
        for t in (-.032,.032):
            start=m@model.Vector((0,t,.030));end=target+model.Vector((-s*t,0,c*t))
            axis=(end-start).normalized()
            ps.append(beam(start-axis*.008,end+axis*.008,.031,model.ELEV))
    tris,_=engine.mesh_islands([o for o in rig.children if o.type=='MESH'],{},rig.matrix_world.inverted())
    worst,share=engine.coverage(ps,tris);count=sum(len(p['T']) for p in ps)
    if worst>=.0001:
        pts=np.concatenate([tris.reshape(-1,3),tris.mean(1)])
        distances=np.minimum.reduce([engine.outside(pts,p) for p in ps])
        print('Uncovered samples',pts[np.argsort(distances)[-15:]].tolist(),flush=True)
    assert count<=500,count
    assert worst<.0001 and share==1,(worst,share)
    report=dict(triangles=count,pieces=len(ps),surface_coverage=share,
                worst_uncovered_distance_m=float(worst),allowance_m=ALLOWANCE,
                filled_regions=['small fasteners and loom apertures','side tower brace bays'],
                preserved_regions=['central frame opening','reflector concavity'])
    (model.HERE/'satellite_collision_report.json').write_text(json.dumps(report,indent=2))
    print(f'[satellite] collision PASS: {count} triangles, {len(ps)} convex pieces; 100% sampled coverage',flush=True)
    return ps


BONE_OVERRIDE={model.ROOT:assembly,model.ELEV:lambda rig:[]}
