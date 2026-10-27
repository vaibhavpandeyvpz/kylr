"""Validate lunar terrain topology, elevated sockets and paired native formats."""
import json
import sys
from pathlib import Path
import bpy
import bmesh

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from layout import data
from layout import HEIGHTS
from mathutils import Vector, Euler

report=json.loads((HERE/'skyfall_rig.json').read_text())
decks,markers=json.loads(json.dumps(data()))
assert markers==report['markers'] and decks==report['deck_sections']
assert report['total_map_triangles']<=report['triangle_budget']
assert report['level_surface_z_m']==HEIGHTS
counts={}
for extension in ('glb','fbx'):
    for suffix in ('','_col','_scenery','_scenery_col'):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        path=HERE/('skyfall'+suffix+'.'+extension)
        if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        if suffix=='':
            for arm in bpy.context.scene.objects:
                if arm.type!='ARMATURE':continue
                if arm.animation_data:
                    arm.animation_data.action=None
                    for track in arm.animation_data.nla_tracks:track.mute=True
                for bone in arm.pose.bones:
                    bone.location=(0,0,0);bone.rotation_quaternion=(1,0,0,0)
            bpy.context.view_layer.update()
            for marker in report['markers']:
                ob=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
                point=Vector(marker.get('mount_position_blender',marker['position_blender']))
                assert (ob.matrix_world.translation-point).length<.0001,(extension,marker['name'],'socket elevation')
                axes=Euler(marker.get('mount_rotation_euler',marker['rotation_blender'])).to_matrix()
                assert all((ob.matrix_world.to_3x3().col[i]-axes.col[i]).length<.0001 for i in range(3)),(extension,marker['name'],'socket rotation')
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
        count=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        if suffix=='':assert count==0,'Only native placement sockets belong to map assembly'
        else:assert count>0
        if suffix=='_scenery_col':
            vertices=[];faces=[]
            for ob in meshes:
                offset=len(vertices);vertices.extend(ob.matrix_world@v.co for v in ob.data.vertices)
                faces.extend(tuple(offset+i for i in p.vertices) for p in ob.data.polygons)
            joined=bpy.data.meshes.new('ValidationCombinedTerrain');joined.from_pydata(vertices,[],faces)
            bm=bmesh.new();bm.from_mesh(joined)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
            bad=[e for e in bm.edges if not e.is_manifold]
            assert not bad,(extension,'open combined collision',len(bad),[(len(e.link_faces),[tuple(v.co) for v in e.verts]) for e in bad[:3]])
            bm.free();bpy.data.meshes.remove(joined)
        if extension=='glb':counts[suffix]=count
        else:assert counts[suffix]==count,(suffix,'GLB/FBX triangle mismatch')
        print('SKYFALL_TERRAIN_EXPORT',extension,suffix or 'placements',count,flush=True)
output=HERE.parents[2]/'.local/skyfall-update/native-validation.json'
output.write_text(json.dumps(dict(passed=True,triangles=counts,map_owned_triangles=report['total_map_triangles']),indent=2)+'\n')
print('SKYFALL_TERRAIN_VALIDATED',flush=True)
