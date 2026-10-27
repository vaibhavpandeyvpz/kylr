"""Figma-grounded volcanic excavations; authored metres and native closed cuts."""
import json
import math
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
DEPTH=10.0
SURFACE=-.5


def path_points(path):
    tokens=re.findall(r'[MLCZ]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?',path)
    points=[];i=0
    while i<len(tokens):
        command=tokens[i];i+=1
        if command=='Z':break
        if command in ('M','L'):
            points.append([float(tokens[i]),float(tokens[i+1])]);i+=2
        elif command=='C':
            a=points[-1];b,c,d=[list(map(float,tokens[i+j:i+j+2])) for j in (0,2,4)];i+=6
            for step in range(1,17):
                t=step/16;s=1-t
                points.append([s*s*s*a[k]+3*s*s*t*b[k]+3*s*t*t*c[k]+t*t*t*d[k] for k in (0,1)])
        else:raise ValueError(command)
    if points[-1]==points[0]:points.pop()
    return points


def data():
    snapshot=json.loads((HERE/'sources/ground_holes.json').read_text())
    origin=snapshot['frame']['transform'];result=[]
    for node in sorted(snapshot['node']['children'],key=lambda n:int(n['name'].split()[-1])):
        if node['type']=='ELLIPSE':
            points=[[node['width']*(.5+.5*math.cos(i*math.tau/48)),node['height']*(.5+.5*math.sin(i*math.tau/48))] for i in range(48)]
        else:points=path_points(node['vectorPaths'][0]['data'])
        transform=node['transform']
        polygon=[[(transform[0][0]*x+transform[0][1]*y+transform[0][2]-origin[0][2])/100-37.5,
                  (transform[1][0]*x+transform[1][1]*y+transform[1][2]-origin[1][2])/100-37.5] for x,y in points]
        # Round sharp surveyed corners without replacing the authored footprint.
        rounded=[]
        for i,p in enumerate(polygon):
            before=polygon[i-1];after=polygon[(i+1)%len(polygon)]
            for other in (before,after):
                distance=math.dist(p,other);t=min(.15,.22/max(distance,.001))
                rounded.append([p[k]*(1-t)+other[k]*t for k in (0,1)])
        samples=[]
        for i,p in enumerate(rounded):
            q=rounded[(i+1)%len(rounded)];count=max(1,math.ceil(math.dist(p,q)/.65))
            for j in range(count):samples.append([p[k]+(q[k]-p[k])*j/count for k in (0,1)])
        cx=sum(p[0] for p in samples)/len(samples);cz=sum(p[1] for p in samples)/len(samples)
        seed=int(node['name'].split()[-1])
        rim=[]
        for x,z in samples:
            angle=math.atan2(z-cz,x-cx);radius=math.hypot(x-cx,z-cz)
            erosion=.10*math.sin(angle*7+seed)+.045*math.sin(angle*17-seed)
            rim.append([x+(x-cx)/radius*erosion,z+(z-cz)/radius*erosion])
        result.append(dict(id=node['id'],name=node['name'],outline=polygon,rim=rim,center=[cx,cz],depth_m=DEPTH,surface_m=SURFACE))
    assert result
    return result


def excavate(ground,holes=()):
    import bpy
    import time
    from map_shells import shell,recess_size,RECESS_TOP_M
    started=time.perf_counter()
    collection=bpy.data.collections.new('TEMP_Excavations');bpy.context.scene.collection.children.link(collection)
    cutters=[]
    for pit in data():
        rim=pit['rim'];cx,cz=pit['center'];count=len(rim);vertices=[];faces=[]
        radius=max(.5,min(math.dist(p,[cx,cz]) for p in rim));taper=min(.22,1.3/radius)
        elevations=[6,0,-1.5,-3.5,-5.5,-7.5,-10]
        for level,y in enumerate(elevations):
            factor=1-taper*max(0,-y)/DEPTH
            for i,(x,z) in enumerate(rim):
                angle=math.atan2(z-cz,x-cx)
                fracture=0 if y>=0 or y==-10 else .08*math.sin(angle*11+level*1.7)
                vertices.append((cx+(x-cx)*(factor+fracture/radius),-(cz+(z-cz)*(factor+fracture/radius)),y))
            if level:
                for i in range(count):
                    j=(i+1)%count;faces.append(((level-1)*count+i,(level-1)*count+j,level*count+j,level*count+i))
        faces.extend([tuple(range(count-1,-1,-1)),tuple((len(elevations)-1)*count+i for i in range(count))])
        mesh=bpy.data.meshes.new(pit['name']);mesh.from_pydata(vertices,[],faces);mesh.update()
        cutter=bpy.data.objects.new('TEMP_LavaPit',mesh);collection.objects.link(cutter)
        import bmesh
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        cutters.append(cutter)
    for hole in holes:
        if hole['center'][2]-hole['depth']>=0:continue
        w,h=recess_size(hole['size'])
        cutter=shell('TEMP_Recess',[-w/2,-h/2,w/2,h/2],RECESS_TOP_M,hole['depth']+RECESS_TOP_M)
        cutter.location=hole['center'];cutter.rotation_euler.z=hole['yaw']
        for owner in list(cutter.users_collection):owner.objects.unlink(cutter)
        collection.objects.link(cutter);cutters.append(cutter)
    bpy.context.view_layer.objects.active=ground
    modifier=ground.modifiers.new('Batched source excavations','BOOLEAN')
    modifier.operation='DIFFERENCE';modifier.solver='MANIFOLD'
    modifier.operand_type='COLLECTION';modifier.collection=collection
    modifier.use_self=True;modifier.use_hole_tolerant=True
    print('FACEOFF_BOOLEAN_BATCH',len(cutters),'cutters',flush=True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    for cutter in cutters:bpy.data.objects.remove(cutter,do_unlink=True)
    bpy.data.collections.remove(collection)
    print('FACEOFF_BOOLEAN_SECONDS',round(time.perf_counter()-started,3),flush=True)
