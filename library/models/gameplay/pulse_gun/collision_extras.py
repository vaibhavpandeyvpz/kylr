"""Asset-specific convex proxies. Preserve base, guard, yoke and gun concavities.
The pinned hydraulic actuator has no blocking proxy, like other project pistons.
"""
import bmesh
import math
import numpy as np
engine=None
# Coarser pockets and bearing reliefs are needed to retain all blocking surfaces
# within 500 triangles. The measured standoff is bounded and reported.
ALLOWANCE=.055
PARTS=[]
NO_COLLIDER={'ElevatorCylinder','ElevatorRod'}

def piece(bone,points,fit=True):
    v,t=engine.hull(np.asarray(points,dtype=float))
    if fit:v,t=engine.fit(v,t,.018)
    normals,_=engine.planes(v,t)
    normals=np.unique(np.round(normals,2),axis=0)
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    supported=engine.polytope(normals,np.max(np.asarray(points)@normals.T,axis=0)+.000002)
    v,t=engine.hull(supported)
    bm=bmesh.new()
    vs=[bm.verts.new(tuple(p)) for p in v]
    for tri in t:bm.faces.new([vs[int(i)] for i in tri])
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    bmesh.ops.dissolve_limit(bm,angle_limit=1e-5,verts=bm.verts[:],edges=bm.edges[:])
    bmesh.ops.triangulate(bm,faces=bm.faces[:]);bm.verts.ensure_lookup_table()
    v=np.array([tuple(p.co) for p in bm.verts]);t=np.array([tuple(p.index for p in f.verts) for f in bm.faces]);bm.free()
    print(f'[pulse_gun] collision {bone}: {len(t)} triangles',flush=True)
    q={'bone':bone,'V':v,'T':t};PARTS.append(q);return q

def radial_piece(bone,p,n,tilt):
    normals=np.array([(math.cos(a),math.sin(a),z) for z in (0,tilt) for a in np.arange(n)*math.tau/n]+[(0,0,1),(0,0,-1)],dtype=float)
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    v=engine.polytope(normals,np.max(np.asarray(p)@normals.T,axis=0))
    return piece(bone,v)

def root(rig):
    p=engine.bone_points(rig,'Root');out=[radial_piece('Root',p[p[:,2]<=.215],16,.60)]
    for angle in (45,135,225,315):
        n=np.array((math.cos(math.radians(angle)),math.sin(math.radians(angle))))
        tangent=np.array((-n[1],n[0]));q=p[(p[:,2]>=.165)&(p[:,:2]@n>.32)&(np.abs(p[:,:2]@tangent)<.065)]
        normals=np.array([(*n,0),(*-n,0),(*tangent,0),(*-tangent,0),(0,0,1),(0,0,-1)])
        bounds=engine.polytope(normals,np.max(q@normals.T,axis=0))
        out.append(piece('Root',bounds,fit=False))
    return out

def yaw(rig):
    p=engine.bone_points(rig,'Yaw');out=[radial_piece('Yaw',p[p[:,2]<=.2231],12,-2)]
    for sign in (-1,1):out.append(piece('Yaw',p[(p[:,0]*sign>.10)&(p[:,0]*sign<.225)&(np.abs(p[:,1])<.161)&(p[:,2]>=.223)]))
    out.append(piece('Yaw',p[(np.abs(p[:,0])<.051)&(p[:,1]<-.23)&(p[:,2]>=.194)]))
    return out

def elevation(rig):
    p=engine.bone_points(rig,'Elevation');out=[]
    # Separate transverse shaft, breech/barrel shell and lower mounting clevis.
    out.append(piece('Elevation',p[(np.abs(p[:,0])<=.1111)&(p[:,2]>=.416)]))
    shaft=[(x,.04+r*math.cos(a),.49+r*math.sin(a)) for x,r in ((-.219,.038),(-.111,.05955),(.111,.05955),(.219,.038)) for a in np.arange(8)*math.tau/8]
    out.append(piece('Elevation',shaft,fit=False))
    out.append(piece('Elevation',p[(p[:,2]<=.457)&(np.abs(p[:,0])<=.051)&(p[:,1]>=-.131)&(p[:,1]<=-.079)]))
    return out

def barrel(rig):
    p=engine.bone_points(rig,'Barrel');angles=np.arange(8)*math.tau/8
    normals=np.array([(math.cos(a),0,math.sin(a)) for a in angles]+[(0,1,0),(0,-1,0)])
    v=engine.polytope(normals,np.max(p@normals.T,axis=0));return [piece('Barrel',v,fit=False)]

# Retain the barrel's own rigid proxy and recoil alignment.
def collision_bones(rig):return {b.name:b.name for b in rig.data.bones}
COLLISION_BONES=collision_bones
def bounded(fn):
    def build(rig):
        result=fn(rig)
        total=sum(len(q['T']) for q in result)
        assert total<500,(fn.__name__,total)
        if fn is barrel:audit(rig)
        return result
    return build
BONE_OVERRIDE={'Root':bounded(root),'Yaw':bounded(yaw),'Elevation':bounded(elevation),'Barrel':bounded(barrel)}


def audit(rig):
    import json
    from pathlib import Path
    tri=[];by_bone={}
    for obj in engine.SOURCES[rig.name]:
        me=obj.data;me.calc_loop_triangles()
        names={g.index:g.name for g in obj.vertex_groups}
        for t in me.loop_triangles:
            bone=names[me.vertices[t.vertices[0]].groups[0].group]
            if bone in NO_COLLIDER:continue
            face=[tuple(obj.matrix_world@me.vertices[i].co) for i in t.vertices]
            tri.append(face);by_bone.setdefault(bone,[]).append(face)
    worst,share=engine.coverage(PARTS,np.array(tri))
    if worst>=.0001:
        for bone,faces in by_bone.items():
            points=np.concatenate((np.array(faces).reshape(-1,3),np.array(faces).mean(1)));dist=np.full(len(points),np.inf)
            for q in PARTS:
                q['planes']=engine.planes(q['V'],q['T']);dist=np.minimum(dist,engine.outside(points,q))
            if dist.max()>.0001:print('UNCOVERED',bone,points[np.argmax(dist)],dist.max(),flush=True)
    assert worst<.0001 and share==1,(worst,share)
    count=sum(len(q['T']) for q in PARTS)
    standoff={}
    source=json.loads((Path(__file__).parent/'pulse_gun_collision_source_report.json').read_text())
    full=np.array([[q['vertices'][i] for i in face] for q in source if q['bone'] not in NO_COLLIDER for face in q['faces']])
    model=engine.Model(full)
    for bone,faces in by_bone.items():
        samples=np.concatenate([engine.surface_samples(q['V'],q['T'],.010,cap=256) for q in PARTS if q['bone']==bone])
        distance=np.array([model.bvh.find_nearest(engine.Vector(p))[3] for p in samples])
        far=distance>.020
        if far.any():distance[far&model.inside(samples)]=0
        standoff[bone]=float(distance.max())
    report=dict(triangles=count,pieces=len(PARTS),blocking_surface_coverage=share,maximum_source_protrusion_m=float(worst),
                proxy_standoff_m=standoff,allowance_m=ALLOWANCE,excluded_bones=sorted(NO_COLLIDER))
    (Path(__file__).parent/'pulse_gun_collision_report.json').write_text(json.dumps(report,indent=2))
    print('[pulse_gun] blocking coverage and proxy fit:',report,flush=True)
    assert count<=500,count
    assert max(standoff.values())<=ALLOWANCE,standoff



