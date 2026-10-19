"""Repeatable fresh-scene GLB/FBX and native GLB projection-frame validation.

Run Blender 5.2 headless, optionally with -- batten_light (or another name).
Checks generated companions without touching the game repository.
"""
import json
import math
import struct
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

HERE=Path(__file__).resolve().parent
NAMES=('batten_light','sconce_light','pole_light')


def check_glb(folder,report):
    raw=(folder/(folder.name+'.glb')).read_bytes()
    assert raw[:4]==b'glTF'
    size,kind=struct.unpack_from('<II',raw,12)
    assert kind==0x4e4f534a
    doc=json.loads(raw[20:20+size])
    assert not doc.get('animations')
    parents={child:i for i,node in enumerate(doc['nodes']) for child in node.get('children',[])}
    def world(i):
        node=doc['nodes'][i]
        if 'matrix' in node:
            m=Matrix([node['matrix'][r::4] for r in range(4)])
        else:
            x,y,z,w=node.get('rotation',[0,0,0,1])
            m=Quaternion((w,x,y,z)).to_matrix().to_4x4()
            for col,scale in enumerate(node.get('scale',[1,1,1])):
                for row in range(3):m[row][col]*=scale
            m.translation=node.get('translation',[0,0,0])
        return world(parents[i])@m if i in parents else m
    convert=lambda v:Vector((v[0],v[2],-v[1]))
    for beam in report['gizmos']:
        i=next(i for i,node in enumerate(doc['nodes']) if node.get('name')==beam['name'])
        m=world(i)
        assert (m.translation-convert(beam['origin'])).length<1e-5
        assert (m.to_3x3()@Vector((0,0,-1))).normalized().dot(convert(beam['forward']).normalized())>.99999
        assert (m.to_3x3()@Vector((0,1,0))).normalized().dot(convert(beam['up']).normalized())>.99999
    lens=next(m for m in doc['materials'] if m['name']=='M_Light')
    strength=lens.get('extensions',{}).get('KHR_materials_emissive_strength',{}).get('emissiveStrength',1)
    assert strength>=3 and min(lens['emissiveFactor'])>.5,(strength,lens)
    return strength


def validate(name):
    folder=HERE/name;path=folder/f'{name}_rig.json';report=json.loads(path.read_text())
    strength=check_glb(folder,report)
    for suffix in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        filepath=str(folder/f'{name}.{suffix}')
        if suffix=='glb':bpy.ops.import_scene.gltf(filepath=filepath)
        else:bpy.ops.import_scene.fbx(filepath=filepath)
        objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in report['meshes']]
        assert set(o.name for o in objects)==set(report['meshes'])
        points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
        bounds={'lo':[min(p[i] for p in points) for i in range(3)],'hi':[max(p[i] for p in points) for i in range(3)]}
        assert all(abs(bounds[k][i]-report['bounds_m'][k][i])<1e-4 for k in bounds for i in range(3))
        materials=set()
        for obj in objects:
            assert all(abs(s-1)<1e-5 for s in obj.scale)
            obj.data.calc_loop_triangles()
            assert len(obj.data.loop_triangles)==report['meshes'][obj.name]<=5000
            materials.update(obj.data.materials[p.material_index].name for p in obj.data.polygons)
            for vertex in obj.data.vertices:
                assert len(vertex.groups)==1 and abs(vertex.groups[0].weight-1)<1e-6
                assert obj.vertex_groups[vertex.groups[0].group].name=='Root'
            assert obj.data.uv_layers
            assert all(math.isfinite(c) and -1e-5<=c<=1.00001 for uv in obj.data.uv_layers for d in uv.data for c in d.uv)
        assert materials==set(report['materials']),(suffix,materials,report['materials'])
        rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
        assert len(rigs)==1 and set(rigs[0].data.bones.keys())=={'Root'}
        assert not bpy.data.actions
        for beam in report['gizmos']:
            obj=bpy.data.objects[beam['name']]
            assert (obj.matrix_world.translation-Vector(beam['origin'])).length<1e-5
            assert (obj.matrix_world.to_3x3()@Vector((0,1,0))).normalized().dot(Vector(beam['forward']).normalized())>.99999
        print(f'[{name}] {suffix.upper()} round-trip PASS: scale, bounds, {report["triangles"]} tris, materials, UVs, Root weights, no actions, {len(report["gizmos"])} projection frames',flush=True)
    report['checks']['roundtrips']=['glb','fbx']
    report['checks']['glb_emission_strength']=strength
    report['checks']['native_glb_negative_z_projection']=True
    if (folder/f'{name}_col.glb').exists():
        counts=[]
        for suffix in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            filepath=str(folder/f'{name}_col.{suffix}')
            if suffix=='glb':bpy.ops.import_scene.gltf(filepath=filepath)
            else:bpy.ops.import_scene.fbx(filepath=filepath)
            objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert len(objects)==1
            obj=objects[0];obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
            assert 0<count<=500
            assert all(abs(s-1)<1e-5 for s in obj.scale)
            assert not bpy.data.actions
            for v in obj.data.vertices:
                assert len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6
                assert obj.vertex_groups[v.groups[0].group].name=='Root'
            # Piece colours survive both formats. Weld each piece separately:
            # global welding would incorrectly join touching convex hulls.
            colors=obj.data.color_attributes.active_color
            assert colors and colors.domain=='CORNER'
            groups={}
            for poly in obj.data.polygons:
                key=tuple(round(c,3) for c in colors.data[poly.loop_start].color[:3])
                groups.setdefault(key,[]).append(poly)
            pieces=0
            for polygons in groups.values():
                bm=bmesh.new()
                for poly in polygons:
                    bm.faces.new([bm.verts.new(obj.data.vertices[i].co) for i in poly.vertices])
                bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-6)
                assert all(e.is_manifold for e in bm.edges)
                bm.normal_update()
                assert all(face.normal.dot(v.co-face.verts[0].co)<1e-4 for face in bm.faces for v in bm.verts)
                assert bm.calc_volume()>0
                bm.free();pieces+=1
            counts.append(count)
            print(f'[{name}] {suffix.upper()} collider round-trip PASS: {count} triangles, {pieces} closed convex pieces, Root weights and no actions',flush=True)
        assert counts[0]==counts[1]
        report['checks']['collider_roundtrips']=['glb','fbx']
        report['checks']['collider_triangles']=counts[0]
    path.write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else NAMES
    for name in args:
        assert name in NAMES,name
        validate(name)
