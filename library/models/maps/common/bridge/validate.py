"""Reproducible native round trips, option/collision and actual Tensor clearance."""
import itertools
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
NAME=HERE.name
sys.path.insert(0,str(HERE.parent/'platform'))
from validate_platforms import fixture_vertices


def tree(objects):
    vertices=[];faces=[]
    for obj in objects:
        obj.data.calc_loop_triangles();offset=len(vertices)
        vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        faces.extend(tuple(offset+i for i in t.vertices) for t in obj.data.loop_triangles)
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True)


def tensor_envelope():
    path=HERE.parents[2]/'characters/tensor/tensor.blend'
    with bpy.data.libraries.load(str(path),link=False) as (available,loaded):
        loaded.objects=[name for name in available.objects if name.startswith('SK_')]
    points=[o.matrix_world@v.co for o in loaded.objects if o.type=='MESH' and not o.hide_render for v in o.data.vertices]
    assert points,'missing actual authored Tensor'
    bounds=[max(abs(p.x) for p in points),max(p.z for p in points)-min(p.z for p in points)]
    for obj in loaded.objects:bpy.data.objects.remove(obj,do_unlink=True)
    return bounds


def main():
    report=json.loads((HERE/f'{NAME}_rig.json').read_text())
    for extension in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=HERE/f'{NAME}.{extension}'
        if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in report['meshes']]
        assert {o.name for o in meshes}==set(report['meshes'])
        rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
        assert len(rigs)==1 and set(rigs[0].data.bones.keys())=={'Root'}
        assert not bpy.data.actions
        total=0
        for obj in meshes:
            obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
            assert count==report['meshes'][obj.name]<=5000;total+=count
            assert obj.data.uv_layers and all(abs(s-1)<1e-5 for s in obj.scale)
            for v in obj.data.vertices:
                assert len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-5
                assert obj.vertex_groups[v.groups[0].group].name=='Root'
            assert bool(obj.get('optional',False))==(obj.name in report['options']) if extension=='glb' else True
        assert total==report['triangles']<=5000
        assert {o.data.materials[p.material_index].name for o in meshes for p in o.data.polygons}==set(report['materials'])
        points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
        for key,fn in (('lo',min),('hi',max)):
            assert all(abs(fn(p[i] for p in points)-report['bounds_m'][key][i])<1e-4 for i in range(3))
        for gizmo in report['gizmos']:
            actual=bpy.data.objects[gizmo['name']].matrix_world
            expected=Matrix(gizmo['matrix_world'])
            assert max(abs(actual[r][c]-expected[r][c]) for r in range(4) for c in range(4))<1e-4
        canopy=next(o for o in meshes if o.name.endswith('Cover'))
        for railing in [o for o in meshes if o.name in ('SK_Bridge5X5RailingLeft','SK_Bridge5X5RailingRight')]:
            assert max(v.co.z for v in railing.data.vertices)<=1.1201,('guard exceeds shared post joint',extension)
        for sign,side in ((-1,'Left'),(1,'Right')):
            frame=next(o for o in meshes if o.name=='SK_Bridge5X5SideFrame'+side)
            for y in (-4.85,-.15):
                for obj,z in ((frame,.8),(canopy,1.25)):
                    hit,where,normal,face=obj.ray_cast(Vector((sign*2.32-1,y,z)),Vector((1,0,0)),distance=2)
                    assert hit and abs(where.x-(sign*2.32-.04))<1e-4,('column width mismatch',extension,side,z)
                hit,where,normal,face=frame.ray_cast(Vector((sign*2.32,y,1.10)),Vector((0,0,-1)),distance=.03)
                assert hit and abs(where.z-1.09)<1e-4,('lower column seam',extension)
                hit,where,normal,face=canopy.ray_cast(Vector((sign*2.32,y,1.08)),Vector((0,0,1)),distance=.03)
                assert hit and abs(where.z-1.09)<1e-4,('upper column seam',extension)
        deck=next(o for o in meshes if o.name.endswith('Deck'))
        light=next(g for g in report['gizmos'] if g.get('attachment')=='batten_light')
        matrix=Matrix(light['matrix_world'])
        assert light['required_mesh']==canopy.name
        assert (matrix.to_3x3()@Vector((1,0,0))-Vector((0,1,0))).length<1e-5
        for x,y in itertools.product((-.51,.51),(-.105,.105)):
            p=matrix@Vector((x,y,-.0001))
            hit,where,normal,face=canopy.ray_cast(p,Vector((0,0,1)),distance=.002)
            assert hit,('unsupported batten foot',extension)
        path=HERE.parents[2]/'environments/batten_light/batten_light.glb'
        previous=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(path))
        imported=set(bpy.data.objects)-previous
        bpy.context.view_layer.update()
        fixture=[matrix@o.matrix_world@v.co for o in imported if o.type=='MESH' and o.name.startswith('SK_BattenLight') for v in o.data.vertices]
        assert fixture and min(p.z for p in fixture)>2.70, ('batten clearance',min(p.z for p in fixture),max(p.z for p in fixture))
        assert max(p.z for p in fixture)<=matrix.translation.z+1e-5
        for obj in imported:bpy.data.objects.remove(obj,do_unlink=True)
        lamps=[g for g in report['gizmos'] if g.get('attachment')=='sconce_light']
        assert {g['name'] for g in lamps}=={'SconceLightMountLeft','SconceLightMountRight'}
        actual_fixture=fixture_vertices()
        for lamp in lamps:
            expected=Matrix(lamp['matrix_world']);at=expected.translation
            assert abs(abs(at.x)-2.5)<1e-5 and abs(at.y+2.5)<1e-5 and abs(at.z+.4)<1e-5
            for x,z in itertools.product((-.215,.215),(-.15,.15)):
                p=expected@Vector((x,-.0001,z));normal=expected.to_3x3()@Vector((0,1,0))
                hit,where,n,face=deck.ray_cast(p,normal,distance=.002)
                assert hit,('unsupported bridge sconce',extension,lamp['name'])
            points=[expected@p for p in actual_fixture]
            assert all(-5<p.y<0 and p.z<0 for p in points),('bridge fixture entrance clearance',lamp['name'])
        for ix,iy in itertools.product(range(21),repeat=2):
            x=-2.49+4.98*ix/20;y=-4.99+4.98*iy/20
            hit,where,normal,face=deck.ray_cast(Vector((x,y,-1.1)),Vector((0,0,1)),distance=.6)
            assert hit and normal.z<-.99,('open underside',extension,x,y)
        half_width,height=tensor_envelope()
        assert half_width+.05<2.24 and height+.05<2.80,('Tensor envelope',half_width,height)
        # Every option state retains the open level traversal corridor. All
        # combinations of independently optional left/right rails and canopy.
        for left,right,cover in itertools.product((False,True),repeat=3):
            flags=dict(zip(('SK_Bridge5X5RailingLeft','SK_Bridge5X5RailingRight','SK_Bridge5X5Cover'),(left,right,cover)))
            for name,option in report['options'].items():
                if 'enabled_if_any' in option:flags[name]=any(flags[n] for n in option['enabled_if_any'])
            enabled=[o for o in meshes if o==deck or flags.get(o.name,False)]
            assert flags['SK_Bridge5X5SideFrameLeft']==(left or cover)
            assert flags['SK_Bridge5X5SideFrameRight']==(right or cover)
            geometry=tree(enabled)
            for y in (-4.9,-4,-2.5,-1,-.1):
                for x in (-half_width,0,half_width):
                    hit=geometry.ray_cast(Vector((x,y,.03)),Vector((0,0,1)),4)[0]
                    if cover:assert hit is not None and height+.05<hit.z<=3.001,(extension,'canopy headroom',hit)
                    else:assert hit is None,('unexpected overhead',extension)
            for o in meshes:o.hide_render=o not in enabled
            assert not deck.hide_render
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=HERE/f'{NAME}_col.{extension}'
        if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        colliders=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.endswith('Col')]
        assert {o.name for o in colliders}=={name+'Col' for name in report['meshes']}
        for obj in colliders:
            obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
            assert count<=500
            if obj.name.endswith('DeckCol'):assert count==12
            for v in obj.data.vertices:
                assert len(v.groups)==1 and obj.vertex_groups[v.groups[0].group].name=='Root'
        for mesh,option in report['options'].items():
            assert option['collider']==mesh+'Col'
        for left,right,cover in itertools.product((False,True),repeat=3):
            flags=dict(zip(('SK_Bridge5X5RailingLeft','SK_Bridge5X5RailingRight','SK_Bridge5X5Cover'),(left,right,cover)))
            for name,option in report['options'].items():
                if 'enabled_if_any' in option:flags[name]=any(flags[n] for n in option['enabled_if_any'])
            enabled=[o for o in colliders if o.name.endswith('DeckCol') or flags.get(o.name[:-3],False)]
            geometry=tree(enabled)
            for y in (-4.9,-4,-2.5,-1,-.1):
                for x in (-half_width,0,half_width):
                    floor=geometry.ray_cast(Vector((x,y,.03)),Vector((0,0,-1)),.10)[0]
                    assert floor is not None and abs(floor.z)<1e-5,('collider floor',extension)
                    ceiling=geometry.ray_cast(Vector((x,y,.03)),Vector((0,0,1)),4)[0]
                    if cover:assert ceiling is not None and height+.05<ceiling.z<=3.001
                    else:assert ceiling is None,('unwanted overhead collider',extension)
        print(f'[{NAME}.{extension}] PASS {total} triangles; closed belly, 8 option states, Tensor clearance, 6 colliders',flush=True)


if __name__=='__main__':main()
