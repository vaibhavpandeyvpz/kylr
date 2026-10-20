"""Physical surface heights, socket axes, pit clearance and exchange checks."""
import bpy,json,math,bmesh
from pathlib import Path
from mathutils import Vector,Euler,Matrix
HERE=Path(__file__).resolve().parent
rig=json.loads((HERE/'skyfall_rig.json').read_text())
assert rig['canvas_m']==[75,75] and rig['total_map_triangles']<=rig['triangle_budget']
assert rig['recess_clearance_per_side_m']==.001
assert rig['level_surface_z_m']==dict(common=0,lower=22,higher=26,roof=30)
jumbo=next(m for m in rig['markers'] if m['role']=='jumbotron')
assert jumbo['position_godot']==[0,35,0], 'Jumbotron must be 5 m above the rooftop level'
spawns=[m for m in rig['markers'] if m['role']=='spawn']
assert len(spawns)==10,'Ten island-facing spawns required'
for spawn in spawns:
    native_forward=Vector((0,1 if spawn['asset']=='spawn_point' else -1,0))
    forward=Euler(spawn['rotation_blender']).to_matrix()@native_forward
    toward_island=Vector((-1 if spawn['position_blender'][0]>0 else 1,0,0))
    assert forward.dot(toward_island)>.9999,(spawn['name'],'spawn must face the island side')
helper_counts={};bottoms={}
for marker in rig['markers']:
    if marker['role']!='platform':continue
    stem=marker['asset']+marker['asset_suffix']
    metadata=json.loads((HERE/(stem+'_rig.json')).read_text())
    assert metadata['recess_clearance_per_side_m']==.001,stem
    assert metadata['recess_top_above_surface_m']==.5,stem
    assert metadata['triangles']<=metadata['triangle_budget'] and max(metadata['meshes'].values())<=5000,stem
    helper_counts[stem]=metadata['triangles']
    if marker['underbody']:
        assert abs(metadata['depth_m']-.8-1.5)<1e-6,stem
        bottom=marker['position_blender'][2]-metadata['depth_m']
        assert bottom>=15-1e-5,(stem,bottom)
        bottoms[stem]=bottom
# Native supports and walls retain their independent geometry and socket frames.
markers={m['name']:m for m in rig['markers']}
for zone in ('A','B'):
    assert not any(m['zone']==zone and m['deck']==f'{zone}_mainland_1_higher'
                   and m['role'] in ('barricade','pressure_plate') for m in markers.values())
    for deck in (f'{zone}_mainland_1_lower',f'{zone}_mainland_2_higher'):
        assert sum(m['deck']==deck and m['role']=='barricade' for m in markers.values())==1
        assert sum(m['deck']==deck and m['role']=='pressure_plate' for m in markers.values())==1
pads=[m for m in rig['markers'] if m['asset']=='pillar_platform']
assert len(pads)==len([m for m in rig['markers'] if m['role']=='pillar'])
for m in rig['markers']:
    if m.get('parent_socket') not in ('PillarMountTop','WeaponHolderMount'):continue
    parent=markers[m['parent_fixture']]
    meta=json.loads((HERE.parents[1]/'architecture'/parent['asset']/(parent['asset']+'_rig.json')).read_text())
    socket=next(g for g in meta['gizmos'] if g['name']==m['parent_socket'])
    frame=Matrix.Translation(Vector(parent['position_blender']))@Euler(parent['rotation_blender']).to_matrix().to_4x4()@Matrix(socket['matrix_world'])
    expected=Matrix.Translation(Vector(m['mount_position_blender']))@Euler(m.get('mount_rotation_euler',m['rotation_blender'])).to_matrix().to_4x4()
    assert max(abs(frame[i][j]-expected[i][j]) for i in range(4) for j in range(4))<.0001,m['name']
    if m['role']=='pillar':
        assert abs(parent['position_blender'][2]-.5+1+m['support_height_m']-(m['position_blender'][2]+4-.8))<1e-6

thruster_count=0
for marker in rig['markers']:
    if marker['role']!='thruster':continue
    parent=next(m for m in rig['markers'] if m['name']==marker['parent_fixture'])
    metadata=json.loads((HERE/(parent['asset']+parent['asset_suffix']+'_rig.json')).read_text())
    socket=next(g for g in metadata['gizmos'] if g['name']==marker['parent_socket'])
    world=Matrix.Translation(Vector(parent['position_blender']))@Euler(parent['rotation_blender']).to_matrix().to_4x4()@Matrix(socket['matrix_world'])
    assert (world.translation-Vector(marker['position_blender'])).length<.0001,marker['name']
    expected=Euler(marker['rotation_blender']).to_matrix()
    assert all((world.to_3x3().col[i]-expected.col[i]).length<.0001 for i in range(3)),marker['name']
    w,h=metadata['size_m']
    x,y,_=socket['origin']
    assert abs(x)+2.5<=float(w)*.35 and abs(y)+2.5<=float(h)*.35,marker['name']
    thruster_count+=1
assert abs(min(bottoms.values())-19.7)<1e-6
assert rig['level_surface_z_m']['higher']-rig['level_surface_z_m']['lower']==4
assert rig['level_surface_z_m']['roof']-rig['level_surface_z_m']['higher']==4

def audit(source):
    bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
    meshes=[o.evaluated_get(dg) for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_') and 'Dunes' not in o.name and 'Trigger' not in o.name and 'Boundary' not in o.name]
    tested=0
    # Deleted upper Mainland 1 fixtures must leave solid floors, including their
    # former native wells, in both render and collision exchange formats.
    for sign in (-1,1):
        for x in (14,17):
            origin=Vector((sign*x,-sign*22.5,26.1))
            hits=[]
            for mesh in meshes:
                inv=mesh.matrix_world.inverted()
                hit,at,_,_=mesh.ray_cast(inv@origin,inv.to_3x3()@Vector((0,0,-1)),distance=.2)
                if hit:hits.append((mesh.matrix_world@at).z)
            assert any(abs(z-26)<.01 for z in hits),(source,'deleted fixture left a floor hole',tuple(origin),hits)
    for d in rig['deck_sections']:
        for hole in d['holes']:
            tested+=1;w,h=hole['size'];rot=Euler(hole.get('rotation',[0,0,hole.get('yaw',0)])).to_matrix();center=Vector(hole['center'])
            direction=rot @ Vector((0,0,-1))
            for u in (-w/2-.0005,0,w/2+.0005):
                for v in (-h/2-.0005,0,h/2+.0005):
                    origin=center+rot@Vector((u,v,.501))
                    for mesh in meshes:
                        inv=mesh.matrix_world.inverted();hit,at,_,_=mesh.ray_cast(inv@origin,inv.to_3x3()@direction,distance=hole['depth']+.5)
                        assert not hit,(source,'blocked recess',d['name'],hole,mesh.name,tuple(mesh.matrix_world@at))
    return tested

def import_platforms(extension='glb',collision=False):
    for marker in rig['markers']:
        if marker['role']!='platform' and not (marker.get('no_collision') and not collision):continue
        before=set(bpy.data.objects)
        stem=marker['asset']+marker['asset_suffix']+('_col' if collision else '')
        path=HERE/(stem+'.'+extension)
        if extension=='fbx':bpy.ops.import_scene.fbx(filepath=str(path))
        else:bpy.ops.import_scene.gltf(filepath=str(path))
        objects=set(bpy.data.objects)-before
        transform=Matrix.Translation(Vector(marker['position_blender']))@Euler(marker['rotation_blender']).to_matrix().to_4x4()
        for ob in objects:
            if ob.parent not in objects:ob.matrix_world=transform@ob.matrix_world
    bpy.context.view_layer.update()
bpy.ops.wm.open_mainfile(filepath=str(HERE/'skyfall.blend'));bpy.context.scene.frame_set(73)
owned=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert not owned,'Map exports placements only; architectural supports are native imports'
assert rig['total_map_triangles']==rig['triangles']+sum(helper_counts.values())
for marker in rig['markers']:
    ob=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
    expected=Vector(marker.get('mount_position_blender',marker['position_blender']))
    assert (ob.matrix_world.translation-expected).length<.0001,(marker['name'],tuple(ob.matrix_world.translation),tuple(expected))
    mat=Euler(marker.get('mount_rotation_euler',marker['rotation_blender'])).to_matrix()
    assert all((ob.matrix_world.to_3x3().col[i]-mat.col[i]).length<.0001 for i in range(3)),marker['name']
import_platforms();recesses=audit('source with native platforms');exchange={}
for suffix in ('','.fbx','_col','_col.fbx'):
    is_fbx=suffix.endswith('.fbx');path=HERE/('skyfall'+suffix if is_fbx else 'skyfall'+suffix+'.glb')
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    if is_fbx:bpy.ops.import_scene.fbx(filepath=str(path))
    else:bpy.ops.import_scene.gltf(filepath=str(path))
    # The importer evaluates the exported final frame for this static check.
    for ob in bpy.context.scene.objects:
        if ob.type=='ARMATURE' and ob.animation_data:ob.animation_data.action=None
    for ob in bpy.context.scene.objects:
        if ob.type=='ARMATURE':
            for bone in ob.pose.bones:bone.location=(0,0,0);bone.rotation_quaternion=(1,0,0,0)
    import_platforms('fbx' if is_fbx else 'glb',suffix.startswith('_col'))
    exchange[path.name]={'recesses':audit(path.name),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_Skyfall'))}
report=dict(triangles=rig['triangles'],total_map_triangles=rig['total_map_triangles'],markers=len(rig['markers']),deck_sections=len(rig['deck_sections']),recesses=recesses,budget=rig['triangle_budget'],helper_instance_triangles=helper_counts,minimum_platform_bottom_m=min(bottoms.values()),native_thruster_mounts=thruster_count,roundtrip=exchange)
(HERE/'skyfall_validation.json').write_text(json.dumps(report,indent=2)+'\n');print('SKYFALL_VALIDATION',json.dumps(report))
