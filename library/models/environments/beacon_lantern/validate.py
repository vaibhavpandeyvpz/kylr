"""Factory-scene GLB and FBX round trips of the render/collision deliveries."""
import json
import math
from pathlib import Path
import bpy

HERE = Path(__file__).resolve().parent
NAME = HERE.name


def main():
    source = json.loads((HERE/f'{NAME}_rig.json').read_text())
    collision = json.loads((HERE/f'{NAME}_collision_report.json').read_text())
    results = []
    for suffix, expected in (('', source['triangles']), ('_col', collision['triangles'])):
        for ext in ('glb', 'fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path = HERE/f'{NAME}{suffix}.{ext}'
            if ext == 'glb':
                bpy.ops.import_scene.gltf(filepath=str(path))
            else:
                bpy.ops.import_scene.fbx(filepath=str(path))
            # glTF's Blender importer creates an Icosphere bone-display helper.
            # It is not an exported asset mesh.
            meshes = [o for o in bpy.context.scene.objects
                      if o.type == 'MESH' and o.name.startswith('SK_')]
            rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
            assert len(meshes) == 1 and len(rigs) == 1, [(o.name, o.type) for o in bpy.context.scene.objects]
            assert [b.name for b in rigs[0].data.bones] == ['Root']
            assert not bpy.data.actions
            count = 0
            points = []
            for obj in meshes:
                obj.data.calc_loop_triangles()
                count += len(obj.data.loop_triangles)
                points += [obj.matrix_world@v.co for v in obj.data.vertices]
                assert max(abs(s-1) for s in obj.scale) < 1e-5
                assert all(len(v.groups) == 1 and abs(v.groups[0].weight-1) < 1e-6
                           for v in obj.data.vertices)
                if not suffix:
                    assert obj.data.uv_layers
                    for layer in obj.data.uv_layers:
                        assert all(math.isfinite(c) and -.00001 <= c <= 1.00001
                                   for d in layer.data for c in d.uv)
                    used = {obj.data.materials[p.material_index].name for p in obj.data.polygons}
                    assert used == set(source['materials']), used
            assert count == expected, (suffix, ext, count, expected)
            lo = [min(p[i] for p in points) for i in range(3)]
            hi = [max(p[i] for p in points) for i in range(3)]
            assert abs(lo[2]) < .0001 and abs(hi[2]-1.0) < .0001, (lo, hi)
            if not suffix:
                assert max(abs(lo[i]-source['bounds_m']['lo'][i]) for i in range(3)) < .0001
                assert max(abs(hi[i]-source['bounds_m']['hi'][i]) for i in range(3)) < .0001
            results.append(dict(file=path.name, triangles=count, bounds_m=dict(lo=lo, hi=hi), passed=True))
            print(f'[{NAME}] {suffix or "render"} {ext.upper()} round trip PASS: {count} triangles', flush=True)
    (HERE/f'{NAME}_roundtrip_report.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
