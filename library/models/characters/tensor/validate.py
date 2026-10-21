"""Check exposed upper-body detailing on the delivered GLB in a fresh scene.

Run from library/: blender --background --factory-startup --python
models/characters/tensor/validate.py
"""
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


HERE = Path(__file__).resolve().parent


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(HERE / "tensor.glb"))
    meshes = {o.name: o for o in bpy.context.scene.objects if o.type == "MESH"}

    def sampler(variant):
        obj = meshes["SK_TensorUpperBody" + variant.capitalize()]
        obj.data.calc_loop_triangles()
        triangles = list(obj.data.loop_triangles)
        tree = BVHTree.FromPolygons([obj.matrix_world @ v.co for v in obj.data.vertices],
                                   [t.vertices for t in triangles], all_triangles=True)

        def sample(x, z):
            point, normal, index, distance = tree.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), 2)
            if index is None: return None
            return obj.data.materials[triangles[index].material_index].name
        return sample

    vesper = sampler("vesper")
    count = 0
    for side in (1, -1):
        for row in range(14):
            z = 1.35 + row * .005
            width = .126 + (.154 - .126) * (z - 1.35) / (1.435 - 1.35)
            for fraction in (.48, .53, .58, .63, .68):
                material = vesper(side * fraction * width, z)
                assert material and not material.startswith("M_Primary"), ("Vesper shell breaks through cover", side, z, fraction, material)
                count += 1

    aegis = sampler("aegis")
    assert aegis(0, 1.452).startswith("M_Secondary"), "Aegis has no fitted upper service cover"
    assert aegis(.04, 1.486).startswith("M_Primary"), "Aegis accent leaks beyond its physical cover"
    assert aegis(-.04, 1.426).startswith("M_Primary"), "Aegis accent leaks below its physical cover"

    reactor = sampler("reactor")
    for side in (1, -1):
        for row in range(13):
            z = 1.267 + row * .003
            for column in range(16):
                x = side * (.049 + column * .003)
                if x*x + (z - 1.355)**2 < .07**2: continue
                material = reactor(x, z)
                if material:
                    assert material.startswith("M_Primary"), ("Stray Reactor cut below the core", x, z, material)
                    count += 1
    print(f"[tensor] exposed-detail audit passed: {count} cover/vent/shell rays; no primary breakthrough or stray Reactor cuts")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(HERE / "tensor_col.glb"))
    counts = {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        obj.data.calc_loop_triangles()
        counts[obj.name] = len(obj.data.loop_triangles)
    shared = counts["SK_TensorCol"]
    head = max(n for name, n in counts.items() if name.startswith("SK_TensorHead"))
    upper = max(n for name, n in counts.items() if name.startswith("SK_TensorUpperBody"))
    equipped = shared + head + upper
    assert equipped <= 2300, ("Equipped collision budget exceeded", equipped)
    print(f"[tensor] equipped collision audit passed: {equipped}/2300 triangles")


if __name__ == "__main__":
    main()
