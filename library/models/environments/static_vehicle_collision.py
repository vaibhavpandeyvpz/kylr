"""Rigid vehicle proxies: separate substantial formed shells, no sealed hardware.

Convex hulls retain the individual wheel/leg envelopes and the free space
between them. Tiny captive hardware does not become a player obstacle.
"""
import numpy as np

def shells(engine,rig,mesh):
    groups=[];links=[set() for _ in mesh.data.vertices]
    for edge in mesh.data.edges:
        a,b=edge.vertices;links[a].add(b);links[b].add(a)
    unseen=set(range(len(links)))
    while unseen:
        todo=[unseen.pop()];indices=[]
        while todo:
            index=todo.pop();indices.append(index)
            neighbours=links[index]&unseen;unseen.difference_update(neighbours);todo.extend(neighbours)
        points=np.array([tuple(mesh.data.vertices[i].co) for i in indices])
        extent=np.ptp(points,axis=0)
        if sorted(extent)[1]<.1:continue
        vertices,triangles=engine.hull(points)
        groups.append(dict(bone='Root',mesh=mesh.name,V=vertices,T=triangles,tri=vertices[triangles]))
    groups=engine.drop_covered(groups,{'Root':{'Root':[np.eye(4)]}},.02)
    for group in groups:
        group['V'],group['T']=engine.fit(group['V'],group['T'],.02)
    count=sum(len(g['T']) for g in groups)
    assert count<=1500,(mesh.name,count)
    return groups

def split_export(objects,limit=500):
    import bpy
    result=[]
    for ob in objects:
        if ob.type!='MESH' or sum(len(p.vertices)-2 for p in ob.data.polygons)<=limit:
            result.append(ob);continue
        batches=[];batch=[];triangles=0
        for polygon in ob.data.polygons:
            count=len(polygon.vertices)-2
            if batch and triangles+count>limit:batches.append(batch);batch=[];triangles=0
            batch.append(polygon);triangles+=count
        if batch:batches.append(batch)
        for i,batch in enumerate(batches):
            indices=sorted({v for p in batch for v in p.vertices});lookup={old:new for new,old in enumerate(indices)}
            mesh=bpy.data.meshes.new(ob.data.name+str(i));mesh.from_pydata([ob.data.vertices[v].co for v in indices],[],[[lookup[v] for v in p.vertices] for p in batch]);mesh.update()
            clone=ob.copy();clone.data=mesh;clone.name=ob.name+str(i);bpy.context.scene.collection.objects.link(clone)
            clone.vertex_groups.clear();clone.vertex_groups.new(name='Root').add(list(range(len(indices))),1,'REPLACE')
            result.append(clone)
    return result
