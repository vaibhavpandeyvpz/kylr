"""Deterministic convex static proxy, conserving the lid dish and silhouette.
Hardware bounds come from generated, checked manufacturing parts. Tiny bores
and clamp/guard recesses are simplified. No trigger or gameplay integration.
"""
import json
import math
import numpy as np
import model

ALLOWANCE=.030

def piece(points):
    vertices,triangles=engine.hull(np.array(points,dtype=float))
    return {'bone':model.ROOT,'V':vertices,'T':triangles}

def round_hull(stations,n,xy=(0,0)):
    return piece([(xy[0]+r/math.cos(math.pi/n)*math.cos(i*math.tau/n),
                   xy[1]+r/math.cos(math.pi/n)*math.sin(i*math.tau/n),z)
                  for z,r in stations for i in range(n)])

def box(lo,hi):
    return piece([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])

def barrel(rig):
    parts=json.loads((model.HERE/'barrel_collision_source_report.json').read_text())
    result=[round_hull([(0,.260),(.031,.300),(.080,.300),(.120,.258)],12),
            round_hull([(.120,.275),(.820,.275)],12),
            round_hull([(.820,.258),(.850,.300),(.890,.300)],12)]
    for i in range(8):
        a=i*math.pi/4
        result.append(piece([model.polar(r,a+j*math.pi/4,z)
                             for z,ro in ((.890,.300),(.892,.300),(.925,.275))
                             for r in (.247,ro/math.cos(math.pi/8)) for j in (0,1)]))
    # The true flat service casting and recessed mechanical pressure gauge.
    result.append(box((-.093,-.308,.140),(.093,-.232,.800)))
    groups=[lambda t:'drain' in t,
            lambda t:t in ('lid toggle hinge pin','closed lid toggle lever and retained hook'),
            lambda t:t.startswith('rear lid'),
            lambda t:t=='two-foot top lifting grip',
            lambda t:t.startswith('charge') or t.startswith('threaded charge')]
    for select in groups:
        p=np.array([v for p in parts if select(p['label']) for v in p['vertices']])
        assert len(p)
        lo,hi=p.min(0),p.max(0)
        if select('lid toggle hinge pin'):
            # The clevis cheeks and upper catch are fused into larger source
            # castings; include their exposed extents with the toggle proxy.
            lo=np.minimum(lo,(-.029,-.333,.746));hi=np.maximum(hi,(.029,-.265,.856))
        result.append(box(lo,hi))
    result.append(round_hull([(.887,.032),(.910,.032)],6,(-.085,-.055)))
    tris,_=engine.mesh_islands([o for o in rig.children if o.type=='MESH'],{},rig.matrix_world.inverted())
    worst,share=engine.coverage(result,tris)
    assert worst<.0001 and share==1,(worst,share)
    count=sum(len(p['T']) for p in result);assert count<=500,count
    report={'triangles':count,'pieces':len(result),'surface_coverage':share,
            'worst_protrusion_m':float(worst),'allowance_m':ALLOWANCE,'animations':[]}
    (model.HERE/'barrel_collision_report.json').write_text(json.dumps(report,indent=2))
    print(f'[barrel] authored collision: {len(result)} pieces, {count} triangles; 100% surface coverage',flush=True)
    return result

BONE_OVERRIDE={model.ROOT:barrel}
