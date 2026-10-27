"""Budgeted, closed lunar impact ejecta on the actual baked terrain."""
import math
import random
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def build(terrain, qa_points=()):
    rng = random.Random(31971)
    surface = BVHTree.FromPolygons([v.co for v in terrain.data.vertices],
                                  [list(p.vertices) for p in terrain.data.polygons])
    rocks = []
    for index in range(192):
        angle = rng.random()*math.tau
        radius = rng.uniform(62, 80) if index < 16 else rng.uniform(8, 126)
        x = math.cos(angle)*radius; z = math.sin(angle)*radius
        if any(math.hypot(x-p[0], z-p[2]) < 3 for p in qa_points):
            continue
        point, _, _, _ = surface.ray_cast(Vector((x, -z, 100)), Vector((0, 0, -1)), 150)
        assert point is not None, 'Impact ejecta must meet the baked terrain'
        size = rng.uniform(1.0, 2.1) if index < 16 else rng.uniform(.15, .8)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2 if index < 16 else 1, radius=1)
        ob = bpy.context.object
        for vertex in ob.data.vertices:
            vertex.co *= rng.uniform(.78, 1.17)
            vertex.co.x *= size
            vertex.co.y *= size*rng.uniform(.65, 1.05)
            vertex.co.z *= size*.60
        ob.location = (x, -z, point.z+size*.24)
        ob.rotation_euler = (rng.uniform(-.2, .2), rng.uniform(-.2, .2), angle)
        # Angular fractures retain a readable silhouette at lunar lighting angles.
        for polygon in ob.data.polygons:
            polygon.use_smooth = index < 16
        rocks.append(ob)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in rocks:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rocks[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = 'SK_SkyfallLunarStones_LethalSurface'
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    material = bpy.data.materials.get('M_RegolithDark_Diffuse') or bpy.data.materials.new('M_RegolithDark_Diffuse')
    material.diffuse_color = (.26, .25, .25, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = material.diffuse_color
    shader.inputs['Roughness'].default_value = .95
    result.data.materials.clear(); result.data.materials.append(material)
    result['uv_face_charts'] = True
    result['stone_count'] = len(rocks)
    assert sum(len(p.vertices)-2 for p in result.data.polygons) <= 5000
    return result
