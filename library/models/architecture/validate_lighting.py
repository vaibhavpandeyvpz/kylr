"""Native fixture seating, aim and GLB/FBX gizmo round trips."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
NAMES=['bastion','cistern','container','container_long','habitat_pod','hangar','hub','laboratory','lodge','shelter','bunker','lunar_dome']
if '--only' in sys.argv:NAMES=sys.argv[sys.argv.index('--only')+1:]
counts={}


def validate_exterior_support(name,mounts):
    vertices=[];faces=[];materials=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not obj.name.startswith('SK_') or 'Regolith' in obj.name:continue
        offset=len(vertices)
        vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        root=obj.vertex_groups.get('Root')
        if root is None:continue
        for face in obj.data.polygons:
            if not all(any(g.group==root.index and g.weight>.99 for g in obj.data.vertices[i].groups) for i in face.vertices):continue
            faces.append(tuple(offset+i for i in face.vertices))
            materials.append(obj.data.materials[face.material_index].name)
    tree=BVHTree.FromPolygons(vertices,faces)
    for mount in mounts:
        if mount.get('surface')!='exterior':continue
        frame=Matrix(mount['matrix_world']);normal=Vector(mount['mount_normal'])
        assert normal.dot(Vector((frame.translation.x,frame.translation.y,0)))>0,(name,mount['name'],'outward surface')
        for i in range(9):
            for j in range(7):
                sample=frame@Vector((-.315+i*.63/8,0,-.225+j*.45/6))
                hit,n,index,_=tree.ray_cast(sample+normal*.04,-normal,.08)
                assert hit is not None and (hit-sample).length<.001,(name,mount['name'],'backplate unsupported',i,j)
                assert abs(n.dot(normal))>.999,(name,mount['name'],'backplate not flush')
                assert 'Glass' not in materials[index] and 'Emissive' not in materials[index],(name,mount['name'],'non-solid support')


for name in NAMES:
    folder=HERE/name;metadata=json.loads((folder/(name+'_rig.json')).read_text())
    mounts=[m for m in metadata['gizmos'] if m.get('attachment') in ('sconce_light','batten_light')]
    assert mounts,name
    if name=='habitat_pod':assert sum(m['attachment']=='batten_light' for m in mounts)==1
    if name=='lunar_dome':assert len(mounts)==1 and mounts[0]['name']=='SconceLightMountTopCenter'
    expected_exterior=dict(bastion=8,bunker=5,cistern=2,hangar=4,lodge=4,laboratory=8,hub=4,habitat_pod=2)
    if name in expected_exterior:
        assert sum(m.get('surface')=='exterior' for m in mounts)==expected_exterior[name],(name,'exterior mount count')
    for suffix in ('glb','fbx'):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        path=folder/(name+'.'+suffix)
        if suffix=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        for ob in bpy.context.scene.objects:
            if ob.type=='ARMATURE':
                if ob.animation_data:
                    ob.animation_data.action=None
                    for track in ob.animation_data.nla_tracks:track.mute=True
                for bone in ob.pose.bones:bone.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        validate_exterior_support(name,mounts)
        for mount in mounts:
            ob=bpy.data.objects.get(mount['name']);assert ob is not None,(name,suffix,mount['name'])
            expected=Matrix(mount['matrix_world'])
            assert max(abs(ob.matrix_world[i][j]-expected[i][j]) for i in range(4) for j in range(4))<.0001,(name,suffix,mount['name'],'frame')
            forward=ob.matrix_world.to_3x3()@Vector((0,0,-1) if mount['attachment']=='batten_light' else (0,-1,0))
            assert forward.dot(Vector(mount['mount_normal']))>.999,(name,suffix,mount['name'],'light follows surface normal')
    counts[name]=len(mounts)
print('NATIVE_LIGHTING_VALIDATION',json.dumps(counts))
(HERE/'lighting_validation.json').write_text(json.dumps(counts,indent=2)+'\n')
