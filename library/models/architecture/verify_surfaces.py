"""Round-trip optional surface contract across all architectural props."""
import json
import sys
import math
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent

def main():
    names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ('bunker','cistern','hangar','laboratory','bastion')
    for name in names:
        report=json.loads((HERE/name/f'{name}_rig.json').read_text())
        assert report['optional_surface']['object']=='SK_ArchitectureRegolith'
        for extension in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/name/f'{name}.{extension}'
            if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            terrain=next(o for o in meshes if o.name=='SK_ArchitectureRegolith')
            assert {terrain.data.materials[p.material_index].name for p in terrain.data.polygons}=={'M_Regolith'}
            assert all(len(v.groups)==1 and terrain.vertex_groups[v.groups[0].group].name=='Root' and abs(v.groups[0].weight-1)<1e-6 for v in terrain.data.vertices)
            assert terrain.data.uv_layers and all(math.isfinite(c) for d in terrain.data.uv_layers.active.data for c in d.uv)
            assert len(meshes)==len(report['meshes']),(path,[o.name for o in meshes],report['meshes'])
            count=0
            for mesh in meshes:
                mesh.data.calc_loop_triangles();n=len(mesh.data.loop_triangles)
                assert n<=5000;count+=n
            assert count==report['triangles'] and count<=report['triangle_budget']
            assert not any(o.type=='LIGHT' for o in bpy.context.scene.objects)
            terrain.hide_render=True
            assert all(not o.hide_render for o in meshes if o!=terrain)
            print(f'[{name}.{extension}] optional perimeter PASS, {count} total triangles',flush=True)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=HERE/name/f'{name}_col.{extension}'
            if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            assert not any(o.name=='SK_ArchitectureRegolith' for o in bpy.context.scene.objects)

if __name__=='__main__':main()
