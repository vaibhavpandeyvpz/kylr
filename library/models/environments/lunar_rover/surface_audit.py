"""Coplanar surface audit for manufactured rover assemblies."""
import bmesh

def check_coplanar(obj):
    """The shared prop audit, with a common projection axis for each pair.

    On diagonal planes equal X/Y normals can differ in their last float bit.
    Projecting each face on its own dominant axis compares unrelated coordinates
    and falsely reports opposite landing feet as overlapping. Both faces here
    use the first face's axis, and plane distances are also verified explicitly.
    """
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    pieces={}
    for face in bm.faces:
        if face in pieces:
            continue
        group=len(pieces)
        stack=[face]
        pieces[face]=group
        while stack:
            for edge in stack.pop().edges:
                for other in edge.link_faces:
                    if other not in pieces:
                        pieces[other]=group
                        stack.append(other)
    planes={}
    for face in bm.faces:
        if face.calc_area()>1e-7:
            n=face.normal
            key=(*[round(x,3) for x in n],round(n.dot(face.verts[0].co),4))
            planes.setdefault(key,[]).append(face)

    def inside(point,polygon):
        x,y=point
        result=False
        for (x0,y0),(x1,y1) in zip(polygon,polygon[1:]+polygon[:1]):
            if (y0>y)!=(y1>y) and x<x0+(x1-x0)*(y-y0)/(y1-y0):
                result=not result
        return result

    def samples(polygon):
        cx=sum(p[0] for p in polygon)/len(polygon)
        cy=sum(p[1] for p in polygon)/len(polygon)
        return [p for p in [(cx,cy)]+[(x+(cx-x)*.2,y+(cy-y)*.2) for x,y in polygon]
                if inside(p,polygon)]

    for faces in planes.values():
        for i,a in enumerate(faces):
            ax=max(range(3),key=lambda j:abs(a.normal[j]))
            u,v=[j for j in range(3) if j!=ax]
            pa=[(p.co[u],p.co[v]) for p in a.verts]
            for b in faces[i+1:]:
                if pieces[a]==pieces[b]:
                    continue
                if a.normal.dot(b.normal)<.999999 or any(
                    abs(a.normal.dot(p.co-a.verts[0].co))>1e-5 for p in b.verts):
                    continue
                pb=[(p.co[u],p.co[v]) for p in b.verts]
                if any(inside(p,pb) for p in samples(pa)) or any(inside(p,pa) for p in samples(pb)):
                    raise AssertionError(f'z-fighting at {tuple(a.calc_center_median())}')
    bm.free()
