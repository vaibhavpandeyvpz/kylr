"""Sealed static collider, derived from authored manufacturing solids.
The closed canopy makes the occupant bay inaccessible. Opening mechanics
would need a new collider contract; none are authored for this static prop.
"""
import importlib.util
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('cryo_collision_source',Path(__file__).with_name('model.py'))
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)

def hull(points):
    v,t=engine.hull(np.round(np.array(points),5));v,t=engine.fit(v,t,.020);return {'bone':'Root','V':v,'T':t}

def root(_rig):
    source.kit.SLOTS=[source.PRI,source.SEC,source.FRM,source.JNT,source.EMI,source.BRZ,source.GLASS,'M_Screen']
    source.common.CORNER_STEPS=2;source.common.LABELS.clear()
    k=source.kit.Kit()
    for fn in (source.base,source.enclosure,source.hardware):fn(k)
    parts=list(zip(k.parts,source.common.LABELS));out=[]
    groups=[('lofted pressure tub','canopy retaining frame'),
            ('head half cyan canopy','foot half lofted insulated hood','canopy to hood pressure joint'),
            ('anchored skid flange',),('coolant plant spine',)]
    for tags in groups:
        if tags==('coolant plant spine',):
            # Preserve the fore/aft silhouette and tapers, simplify the 40 mm
            # rounded corners only (16.6 mm maximum diagonal stand-off).
            points=[(sx*w/2,sy*.54,z) for w,z in ((.53,.075),(.58,.10),(.58,.215),(.53,.25)) for sx in (-1,1) for sy in (-1,1)]
            v,t=engine.hull(np.array(points));out.append({'bone':'Root','V':v,'T':t})
        else:out.append(hull([v for p,label in parts if label in tags for v in p.verts]))
    for part,label in parts:
        if label=='load bearing saddle':
            y=(part.lo.y+part.hi.y)/2
            points=[(sx*.40,y+sy*d/2,z) for d,z in ((.32,.075),(.32,.15),(.28,.25)) for sx in (-1,1) for sy in (-1,1)]
            v,t=engine.hull(np.array(points));out.append({'bone':'Root','V':v,'T':t})
    for y in (-.57,.57):
        points=[v for p,tag in parts if tag in ('hinge clevis foot','canopy hinge knuckle','retained hinge axle','hinge pin retainer')
                and abs((p.lo.y+p.hi.y)/2-y)<.08 for v in p.verts]
        out.append(hull(points))
        points=[v for p,tag in parts if tag in ('compression latch bed','compression latch handle')
                and abs((p.lo.y+p.hi.y)/2-y)<.08 for v in p.verts]
        out.append(hull(points))
    for x in (-.105,.105):
        out.append(hull([v for p,tag in parts if tag=='rear pressure service collar' and abs((p.lo.x+p.hi.x)/2-x)<.01 for v in p.verts]))
    for part,label in parts:
        if label=='retained coolant return':
            vertices=np.array(part.verts)
            for subset in (vertices[:24],vertices[16:32],vertices[24:]):out.append(engine.box('Root',subset.min(0),subset.max(0)))
    loom=next(p for p,tag in parts if tag=='service signal loom')
    out.append(engine.box('Root',np.array(loom.verts).min(0),np.array(loom.verts).max(0)))
    ranked=[]
    for part,label in parts:
        points=np.array(part.verts);distance=np.full(len(points),np.inf)
        for proxy in out:
            proxy['planes']=engine.planes(proxy['V'],proxy['T'])
            distance=np.minimum(distance,engine.outside(points,proxy))
        ranked.append((float(distance.max()),label))
    print('coverage worst parts',sorted(ranked,reverse=True)[:8],flush=True)
    assert max(d for d,label in ranked)<=.02,'collider render coverage'
    k.bm.free()
    print('[cryo_pod] sealed-state collider',len(out),'pieces',sum(len(p['T']) for p in out),'triangles',flush=True)
    assert sum(len(p['T']) for p in out)<=500,'authored collision budget'
    return out
CUSTOM={'SK_CryoPodGlass':lambda rig,mesh:[], 'SK_CryoPodScreen':lambda rig,mesh:[]}
BONE_OVERRIDE={'Root':root}
TRI_MAX=500
