"""Fresh-scene GLB and FBX round-trip checks for the static lander."""
import bpy, json, math
from pathlib import Path
folder=Path(__file__).resolve().parent
metadata=json.loads((folder/'lunar_lander_rig.json').read_text())
for suffix in ('glb','fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=str(folder/('lunar_lander.'+suffix))
    if suffix=='glb': bpy.ops.import_scene.gltf(filepath=path)
    else: bpy.ops.import_scene.fbx(filepath=path)
    objs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_LunarLander')]
    assert set(o.name for o in objs)==set(metadata['meshes']), [o.name for o in objs]
    pts=[o.matrix_world@v.co for o in objs for v in o.data.vertices]
    lo=[min(v[i] for v in pts) for i in range(3)];hi=[max(v[i] for v in pts) for i in range(3)]
    assert all(abs(x-y)<1e-4 for x,y in zip(lo,[-2.5,-2.5,0])),(suffix,lo)
    assert all(abs(x-y)<1e-4 for x,y in zip(hi,[2.5,2.5,5])),(suffix,hi)
    mats=set();counts={}
    for o in objs:
        assert all(abs(s-1)<1e-5 for s in o.scale),(suffix,o.name,o.scale[:])
        o.data.calc_loop_triangles();counts[o.name]=len(o.data.loop_triangles)
        assert counts[o.name]==metadata['meshes'][o.name] and counts[o.name]<=5000
        mats.update(o.data.materials[p.material_index].name for p in o.data.polygons)
        for v in o.data.vertices:assert len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6
        assert o.data.uv_layers
        for uv in o.data.uv_layers:
            assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for d in uv.data for c in d.uv)
    assert mats==set(metadata['materials']),mats
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    assert len(rigs)==1 and set(rigs[0].data.bones.keys())=={'Root'}
    assert not bpy.data.actions,(suffix,list(bpy.data.actions))
    assert sum(counts.values())==metadata['triangles']
    print(f'[lunar_lander] {suffix.upper()} round-trip PASS: {counts}; 5 x 5 x 5 m; materials, unit scale, Root weights, UVs and no animation verified',flush=True)
metadata['checks']['roundtrips']=['glb','fbx']
(folder/'lunar_lander_rig.json').write_text(json.dumps(metadata,indent=2))
