"""Native fixture seating, aim and GLB/FBX gizmo round trips."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
NAMES=['bastion','cistern','container','container_long','habitat_pod','hangar','hub','laboratory','lodge','shelter','bunker','lunar_dome']
if '--only' in sys.argv:NAMES=sys.argv[sys.argv.index('--only')+1:]
counts={}
for name in NAMES:
    folder=HERE/name;metadata=json.loads((folder/(name+'_rig.json')).read_text())
    mounts=[m for m in metadata['gizmos'] if m.get('attachment') in ('sconce_light','batten_light')]
    assert mounts,name
    if name=='habitat_pod':assert len(mounts)==1 and mounts[0]['attachment']=='batten_light'
    if name=='lunar_dome':assert len(mounts)==1 and mounts[0]['name']=='SconceLightMountTopCenter'
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
        for mount in mounts:
            ob=bpy.data.objects.get(mount['name']);assert ob is not None,(name,suffix,mount['name'])
            expected=Matrix(mount['matrix_world'])
            assert max(abs(ob.matrix_world[i][j]-expected[i][j]) for i in range(4) for j in range(4))<.0001,(name,suffix,mount['name'],'frame')
            forward=ob.matrix_world.to_3x3()@Vector((0,0,-1) if mount['attachment']=='batten_light' else (0,-1,0))
            assert forward.dot(Vector(mount['mount_normal']))>.999,(name,suffix,mount['name'],'inward light')
    counts[name]=len(mounts)
print('NATIVE_LIGHTING_VALIDATION',json.dumps(counts))
(HERE/'lighting_validation.json').write_text(json.dumps(counts,indent=2)+'\n')
