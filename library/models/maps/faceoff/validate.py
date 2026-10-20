"""Native imported architecture/fixture axes and 1 mm machined clearances."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector,Matrix,Euler
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from layout import data
markers,holes=data();report=json.loads((HERE/'faceoff_rig.json').read_text())
upper_weapons=[m for m in markers if m['role']=='weapon' and m['building'] in ('bastion','laboratory') and m['level']=='upper']
assert len(upper_weapons)==2 and all(m['asset']=='item_cradle' for m in upper_weapons), 'First-floor weapons require native item cradles'
assert not any(h['marker'] in {m['name'] for m in upper_weapons} for h in holes), 'Freestanding cradles must not cut holder pits'
jumbo=next(m for m in markers if m['role']=='jumbotron')
assert abs(jumbo['position_godot'][1]-10)<1e-6, 'Jumbotron must be 10 m above ground'
floor_spawns=[m for m in markers if m['asset']=='spawn_point']
assert len(floor_spawns)==8,'Eight front-facing floor spawn pits required'
for spawn in floor_spawns:
    host=next(m for m in markers if m.get('source_asset',m['asset'])==spawn['building'] and m['role']=='prop')
    forward=Euler(spawn['rotation_blender']).to_matrix()@Vector((0,1,0))
    front=Euler(host['rotation_blender']).to_matrix()@Vector((0,-1,0))
    assert forward.dot(front)>.9999,(spawn['name'],'spawn pit must face the building front')
pole_lights=[m for m in markers if m['asset']=='pole_light']
assert len(pole_lights)==4,'Four outward-facing pole lights required'
for marker in pole_lights:
    outward=Vector(marker['position_blender']).normalized()
    facing=Euler(marker['rotation_blender']).to_matrix()@Vector((0,-1,0))
    assert facing.dot(outward)>.9999,(marker['name'],'pole light must face away from the centre')
assert report['recess_clearance_per_side_m']==.001
assert report['total_map_triangles']<=report['triangle_budget']
for building in ('bastion','laboratory'):
    host=next(m for m in markers if m.get('source_asset')==building)
    frame=Euler(host['rotation_blender']).to_matrix()
    racks=[m for m in markers if m['asset']=='storage_rack' and m['building']==building]
    assert len(racks)==2,(building,'two wall racks required')
    for marker in racks:
        back=Euler(marker['rotation_blender']).to_matrix()@Vector((0,1,0))
        assert back.dot(frame@Vector((1,0,0)))>.9999,(marker['name'],'rack back must face the building right wall')
for marker in markers:
    if marker['asset']=='item_cradle' and marker['building'] in ('container','container_long'):
        asset=marker['building']
        metadata=json.loads((HERE.parents[1]/'architecture'/asset/(asset+'_rig.json')).read_text())
        floor=metadata['architecture_dimensions']['rooms'][0]['floor_m']
        host=next(m for m in markers if m['category']=='architecture' and m['asset']==asset)
        assert abs(marker['position_blender'][2]-host['position_blender'][2]-floor)<1e-6,marker['name']
bpy.ops.wm.open_mainfile(filepath=str(HERE/'faceoff.blend'))
assert not any(o.type=='MESH' for o in bpy.context.scene.objects),'Props/scenery must be imported, not embedded in map'
for marker in markers:
    gizmo=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
    expected=Matrix.Translation(Vector(marker['position_blender']))@Euler(marker['rotation_blender']).to_matrix().to_4x4()
    assert max(abs(gizmo.matrix_world[i][j]-expected[i][j]) for i in range(4) for j in range(4))<1e-5,marker['name']
results={}
for extension in ('glb','fbx'):
    for collision in (False,True):
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        def load(stem,transform):
            before=set(bpy.data.objects);path=HERE/(stem+'.'+extension)
            if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            imported=set(bpy.data.objects)-before
            for ob in imported:
                if ob.type=='ARMATURE':
                    if ob.animation_data:
                        ob.animation_data.action=None
                        for track in ob.animation_data.nla_tracks:track.mute=True
                    for bone in ob.pose.bones:bone.matrix_basis=Matrix.Identity(4)
                if ob.parent not in imported:ob.matrix_world=transform@ob.matrix_world
        suffix='_col' if collision else ''
        if collision:
            load('faceoff_col',Matrix.Identity(4))
            walls=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_FaceoffBoundary')]
            assert len(walls)==4,(extension,'four perimeter walls required')
            for wall in walls:
                points=[wall.matrix_world@v.co for v in wall.data.vertices]
                assert abs(min(v.z for v in points)+2)<.001 and abs(max(v.z for v in points)-100)<.001,wall.name
        load('faceoff_scenery'+suffix,Matrix.Identity(4))
        for marker in markers:
            if not marker.get('source_asset'):continue
            meta=json.loads((HERE/('faceoff'+marker['asset_suffix']+'_rig.json')).read_text())
            assert meta['recess_clearance_per_side_m']==.001
            assert max(meta['meshes'].values())<=5000,meta['meshes']
            load('faceoff'+marker['asset_suffix']+suffix,Matrix.Translation(Vector(marker['position_blender']))@Euler(marker['rotation_blender']).to_matrix().to_4x4())
        bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
        meshes=[o.evaluated_get(dg) for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_') and 'Trigger' not in o.name and 'Regolith' not in o.name and 'Dunes' not in o.name]
        for hole in holes:
            w,h=hole['size'];rotation=Euler((0,0,hole['yaw'])).to_matrix();center=Vector(hole['center'])
            for u in (-w/2-.0005,0,w/2+.0005):
                for v in (-h/2-.0005,0,h/2+.0005):
                    origin=center+rotation@Vector((u,v,.01))
                    for mesh in meshes:
                        inv=mesh.matrix_world.inverted();hit,point,_,_=mesh.ray_cast(inv@origin,inv.to_3x3()@Vector((0,0,-1)),distance=hole['depth']+.009)
                        assert not hit,(extension,collision,hole['marker'],mesh.name,tuple(mesh.matrix_world@point))
        results[extension+suffix]=len(holes)
out=dict(map_owned_triangles=report['total_map_triangles'],budget=report['triangle_budget'],imported_props_excluded=True,recess_clearance_per_side_m=.001,roundtrip=results)
(HERE/'faceoff_validation.json').write_text(json.dumps(out,indent=2)+'\n')
print('FACEOFF_VALIDATION',json.dumps(out))
