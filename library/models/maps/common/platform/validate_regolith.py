"""Audit delivered platform dressing for intersecting visible surface sheets."""
import bpy,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;FOLDER=HERE.parents[1]/'skyfall'

def check(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix=='.glb':bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path))
    meta=json.loads(path.with_name(path.stem.removesuffix("_regolith")+"_rig.json").read_text())
    triangles=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not obj.name.startswith('SK_ArchitectureRegolith'):continue
        mesh=obj.data;mesh.calc_loop_triangles()
        assert len(mesh.loop_triangles)<=5000,(path,obj.name)
        assert max(v.co.z for v in mesh.vertices)<=.060001,(path,'excessive relief')
        for vertex in mesh.vertices:
            for hole in meta["cutouts"]:
                x,y,_=hole["center"];angle=hole.get("yaw",0);dx=vertex.co.x-x;dy=vertex.co.y-y
                u=math.cos(angle)*dx+math.sin(angle)*dy;v=-math.sin(angle)*dx+math.cos(angle)*dy
                w,h=hole["size"]
                assert abs(u)>=w/2+.201-1e-5 or abs(v)>=h/2+.201-1e-5,(path,"regolith near cutout",vertex.co[:])
        triangles.extend([mesh.vertices[i].co.copy() for i in t.vertices] for t in mesh.loop_triangles
                         if t.normal.z>.05 and min(mesh.vertices[i].co.z for i in t.vertices)>=.001)
    assert triangles,path
    bins={};cell=.5
    for index,tri in enumerate(triangles):
        lo=[math.floor(min(v[i] for v in tri)/cell) for i in range(2)]
        hi=[math.floor(max(v[i] for v in tri)/cell) for i in range(2)]
        for x in range(lo[0],hi[0]+1):
            for y in range(lo[1],hi[1]+1):bins.setdefault((x,y),[]).append(index)
    for tri in triangles:
        q=sum(tri,tri[0]*0)/3;hits=0
        for index in bins[(math.floor(q.x/cell),math.floor(q.y/cell))]:
            a,b,c=triangles[index];den=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y)
            if abs(den)<1e-10:continue
            u=((b.y-c.y)*(q.x-c.x)+(c.x-b.x)*(q.y-c.y))/den
            v=((c.y-a.y)*(q.x-c.x)+(a.x-c.x)*(q.y-c.y))/den
            if min(u,v,1-u-v)>1e-6:hits+=1
        assert hits<=1,(path,'overlapping visible regolith sheets',list(q),hits)
    print('REGOLITH_SURFACE',path.name,len(triangles),'visible triangle samples; no overlaps',flush=True)

if __name__=='__main__':
    for path in sorted(FOLDER.glob('skyfall_module_platform_*_rig.json')):
        if json.loads(path.read_text()).get('source_helper')!='platform':continue
        stem=path.name.removesuffix('_rig.json')+'_regolith'
        for ext in ('glb','fbx'):check(FOLDER/(stem+'.'+ext))
