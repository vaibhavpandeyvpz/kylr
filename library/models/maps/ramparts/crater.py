"""Budgeted Terrain3D mesh handoff and native fractured rock geometry."""
import math
import random
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def triangles(ob):return sum(len(p.vertices)-2 for p in ob.data.polygons)


def build():
    from planetary_surface import build as bake
    terrain=bake('ramparts','SK_RampartsLethalSurfaceCrater')
    terrain.data.materials.clear();terrain.data.materials.append(bpy.data.materials['M_RampartsRock_Diffuse'])
    assert triangles(terrain)<58000
    from planetary_surface import apply_materials
    apply_materials(terrain,'ramparts',terrain.data.materials[0])
    terrain['terrain_authoring']='Terrain3D 1.0.2 static bake'
    rng=random.Random(43807);rocks=[]
    # Outside the playable deck footprint: no fixture or travel-lane obstruction.
    surface=BVHTree.FromPolygons([v.co for v in terrain.data.vertices],[list(p.vertices) for p in terrain.data.polygons])
    for index in range(72):
        angle=math.tau*(index+rng.uniform(-.22,.22))/72
        radius=rng.uniform(74,88) if index<36 else rng.uniform(90,143)
        x=math.cos(angle)*radius;z=math.sin(angle)*radius
        point,_,_,_=surface.ray_cast(Vector((x,-z,100)),Vector((0,0,-1)),150)
        assert point is not None,'Stone must meet the actual baked terrain'
        height=point.z
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2 if index<10 else 1,radius=1)
        ob=bpy.context.object;ob.name=f'CraterStone_{index}'
        scale=rng.uniform(1.1,2.7) if index<10 else rng.uniform(.3,1.9)
        for vertex in ob.data.vertices:
            vertex.co*=rng.uniform(.8,1.13)
            vertex.co.x*=scale;vertex.co.y*=scale*rng.uniform(.65,1.1);vertex.co.z*=scale*.65
        ob.location=(x,-z,height+scale*.32)
        ob.rotation_euler=(rng.uniform(-.2,.2),rng.uniform(-.2,.2),angle)
        for polygon in ob.data.polygons:polygon.use_smooth=True
        rocks.append(ob)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in rocks:ob.select_set(True)
    bpy.context.view_layer.objects.active=rocks[0];bpy.ops.object.join()
    stones=bpy.context.object;stones.name='SK_RampartsLethalSurfaceStones'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    material=bpy.data.materials.get('M_RampartsStone_Diffuse') or bpy.data.materials.new('M_RampartsStone_Diffuse')
    material.diffuse_color=(.24,.14,.09,1);stones.data.materials.clear();stones.data.materials.append(material)
    stones['uv_face_charts']=True
    assert triangles(terrain)+triangles(stones)<60000
    return [terrain,stones]
