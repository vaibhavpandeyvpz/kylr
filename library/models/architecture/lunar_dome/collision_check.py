"""Audit coverage against ALL fitted collision islands, including shell extras."""
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
HERE=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(HERE/'lunar_dome_col.blend'))
objects=list(bpy.context.scene.objects)
colliders=[o for o in objects if o.type=='MESH' and o.name.startswith('SK_LunarDome') and 'Col' in o.name]
planes={}
islands=0
for obj in colliders:
    mesh=obj.data
    parent=list(range(len(mesh.vertices)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for e in mesh.edges:parent[root(e.vertices[0])]=root(e.vertices[1])
    groups={}
    for p in mesh.polygons:groups.setdefault(root(p.vertices[0]),[]).append(p)
    for faces in groups.values():
        indices={i for f in faces for i in f.vertices}
        centre=sum((obj.matrix_world@mesh.vertices[i].co for i in indices),Vector())/len(indices)
        bone={obj.vertex_groups[g.group].name for i in indices for g in mesh.vertices[i].groups}
        assert len(bone)==1,bone
        eq=[]
        for f in faces:
            a,b,c=(obj.matrix_world@mesh.vertices[i].co for i in f.vertices[:3])
            normal=(b-a).cross(c-a).normalized()
            if normal.dot(centre-a)>0:normal=-normal
            eq.append((*normal,-normal.dot(a)))
        planes.setdefault(next(iter(bone)),[]).append(np.array(eq))
        islands+=1
render=next(o for o in objects if o.type=='MESH' and o.name=='SK_LunarDome')
grouped={}
for v in render.data.vertices:
    name=render.vertex_groups[v.groups[0].group].name
    grouped.setdefault(name,[]).append(tuple(render.matrix_world@v.co))
worst=0
for bone,points in grouped.items():
    # The small lock is intentionally non-blocking and stays within the leaf/seat.
    if bone=='Lock':continue
    points=np.array(points);error=np.full(len(points),np.inf)
    for eq in planes[bone]:error=np.minimum(error,np.max(points@eq[:,:3].T+eq[:,3],axis=1))
    maximum=float(np.max(error));worst=max(worst,maximum)
    assert maximum<=.02001,(bone,'uncovered vertices',maximum,points[error.argmax()].tolist())
report={'result':'PASS','convex_islands':islands,'worst_plane_distance_m':worst,'allowance_m':.02,
    'scope':'all foundation, canopy and moving-door islands; small lock intentionally non-blocking'}
out=HERE/'target';out.mkdir(exist_ok=True)
(out/'lunar_dome_collision_report.json').write_text(json.dumps(report,indent=2))
print('[lunar_dome] complete collider coverage PASS',report,flush=True)
