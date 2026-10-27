"""Validate changed Faceoff terrain exports, native topology and paired formats."""
import json
import sys
from pathlib import Path
import bpy
import bmesh

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from layout import data
from lava_pits import data as pits

report=json.loads((HERE/'faceoff_rig.json').read_text())
assert data()[0]==report['markers'] and data()[1]==report['holes']
assert report['total_map_triangles']<=report['triangle_budget']
assert len(pits())==len(json.loads((HERE/'sources/ground_holes.json').read_text())['node']['children'])
counts={}
for extension in ('glb','fbx'):
    for suffix in ('','_col','_scenery','_scenery_col'):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        path=HERE/('faceoff'+suffix+'.'+extension)
        if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
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
        print('FACEOFF_LAVA_EXPORT',extension,suffix or 'placements',count,flush=True)
output=HERE.parents[2]/'.local/faceoff-lava/native-validation.json'
output.write_text(json.dumps(dict(passed=True,triangles=counts,pit_count=len(pits()),map_owned_triangles=report['total_map_triangles']),indent=2)+'\n')
print('FACEOFF_LAVA_VALIDATED',flush=True)
