"""Repeatable fresh-scene delivery validation for the static rover."""
import bpy
import json
import math
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
from material_classes import classified_name,policy
meta=json.loads((HERE/'lunar_rover_rig.json').read_text())
for suffix in ('glb','fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=str(HERE/f'lunar_rover.{suffix}')
    if suffix=='glb':bpy.ops.import_scene.gltf(filepath=path)
    else:bpy.ops.import_scene.fbx(filepath=path)
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_LunarRover')]
    assert {o.name for o in objects}==set(meta['meshes'])
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    assert all(abs(a-b)<1e-4 for a,b in zip(lo,[-1,-1.5,0])),(suffix,lo)
    assert all(abs(a-b)<1e-4 for a,b in zip(hi,[1,1.5,2.16])),(suffix,hi)
    materials=set()
    for obj in objects:
        assert all(abs(s-1)<1e-5 for s in obj.scale)
        obj.data.calc_loop_triangles()
        assert len(obj.data.loop_triangles)==meta['meshes'][obj.name]
        assert len(obj.data.loop_triangles)<=meta['triangle_budget_per_mesh']
        for vertex in obj.data.vertices:
            assert len(vertex.groups)==1 and abs(vertex.groups[0].weight-1)<1e-6
        assert obj.data.uv_layers
        for layer in obj.data.uv_layers:
            assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for d in layer.data for c in d.uv)
        materials.update(obj.data.materials[p.material_index].name for p in obj.data.polygons)
    assert materials==set(meta['materials'])
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    assert len(rigs)==1 and set(rigs[0].data.bones.keys())=={'Root'}
    assert not bpy.data.actions
    for mat_name,metallic,roughness in [('M_Solar',0.0,.26),('M_Titanium',1.0,.45)]:
        mat=bpy.data.materials[classified_name(mat_name,policy(HERE))]
        textures=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
        assert not textures,(suffix,mat_name,'unexpected baked finish image')
        shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        for socket in ('Base Color','Metallic','Roughness'):
            assert not shader.inputs[socket].is_linked,(suffix,mat_name,socket,'expected authored flat PBR')
        assert abs(shader.inputs['Metallic'].default_value-metallic)<1e-4
        assert abs(shader.inputs['Roughness'].default_value-roughness)<1e-4
    print(f'[lunar_rover] {suffix.upper()} PASS: exact bounds, {meta["triangles"]} triangles, seven materials, flat PBR finishes, unit scale, Root weights, UVs, no actions',flush=True)
meta['checks']['roundtrips']=['glb','fbx']
(HERE/'lunar_rover_rig.json').write_text(json.dumps(meta,indent=2))
