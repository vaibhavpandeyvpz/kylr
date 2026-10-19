"""Audit delivered parametric castings, dimensions, union seams and socket axes."""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]/'skyfall'))
from layout import data
from platform_footprint import contains
folder=HERE.parents[1]/'skyfall';_,markers=data()
for marker in markers:
    if marker['role']!='platform':continue
    stem=marker['asset']+marker['asset_suffix'];report=json.loads((folder/(stem+'_rig.json')).read_text())
    for extension in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=folder/(stem+'.'+extension)
        if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
        assert {o.name for o in meshes}==set(report['meshes']),(stem,extension,'unexpected render/collider geometry')
        count=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        assert count==report['triangles'],(stem,extension,count,report['triangles'])
        assert max(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)<=5000
        for g in report['gizmos']:
            obj=bpy.data.objects.get(g['name']);assert obj is not None,(stem,g['name'])
            expected=Matrix(g['matrix_world'])
            assert max(abs(obj.matrix_world[i][j]-expected[i][j]) for i in range(4) for j in range(4))<.0001,(stem,g['name'])
        print('PLATFORM_CASTING',stem,extension,count,'native render only',flush=True)
    if marker['helper_family']!='platform':continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(folder/(stem+'_col.glb')))
    colliders=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
    w,d=marker['size_m'];base=[-w/2,-d/2,w/2,d/2]
    seams=[]
    for a,b,c,e in marker['extension_rects_m']:
        if abs(c-base[0])<.001 or abs(a-base[2])<.001:
            x=c if abs(c-base[0])<.001 else a
            seams.extend([(x+delta,b+(e-b)*t) for t in (.15,.35,.65,.85) for delta in (-.01,0,.01)])
        if abs(e-base[1])<.001 or abs(b-base[3])<.001:
            y=e if abs(e-base[1])<.001 else b
            seams.extend([(a+(c-a)*t,y+delta) for t in (.15,.35,.65,.85) for delta in (-.01,0,.01)])
    tested=0
    for x,y in seams:
        occupied=False
        for hole in report['cutouts']:
            cx,cy,_=hole['center'];angle=hole['yaw'];dx=x-cx;dy=y-cy
            u=math.cos(angle)*dx+math.sin(angle)*dy;v=-math.sin(angle)*dx+math.cos(angle)*dy
            if abs(u)<hole['size'][0]/2+.002 and abs(v)<hole['size'][1]/2+.002:occupied=True;break
        if occupied:continue
        supported=False
        for mesh in colliders:
            inv=mesh.matrix_world.inverted();hit,point,_,_=mesh.ray_cast(inv@Vector((x,y,.01)),inv.to_3x3()@Vector((0,0,-1)),distance=.02)
            if hit and abs((mesh.matrix_world@point).z)<.0001:supported=True;break
        assert supported,(stem,'extension seam is not a continuous walkable plane',x,y)
        tested+=1
    print('PLATFORM_UNION_SEAMS',stem,tested,'flush samples',flush=True)
