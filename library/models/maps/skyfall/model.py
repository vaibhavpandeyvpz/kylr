"""Standalone authored shells, bone sockets and lunar ground for Skyfall."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Regolith': 'Diffuse',
    'M_RegolithDark': 'Diffuse',
    'M_RegolithLight': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import bpy,json,math,sys,bmesh
from pathlib import Path
from mathutils import Vector,Matrix,Euler
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'architecture'))
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from layout import data,HEIGHTS
sys.path.insert(0,str(HERE.parent/'common'));sys.path.insert(0,str(HERE.parent/'common/platform'));from map_shells import recess_size,RECESS_CLEARANCE_M,RECESS_TOP_M
NAME='skyfall';DEPTH=2.0
def shell(name,rect,z,depth=DEPTH):
    a,b,c,d=rect;v=[(a,b,z-depth),(c,b,z-depth),(c,d,z-depth),(a,d,z-depth),(a,b,z),(c,b,z),(c,d,z),(a,d,z)]
    f=[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(v,[],f);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);return o
def boolean(target,other,operation):
    from map_shells import boolean as apply_boolean
    return apply_boolean(target,other,operation)
def cutter(target,center,size,depth,yaw=0,rotation=None):
    x,y,z=center;w,h=size
    cut=shell('TEMP / recess',[-w/2,-h/2,w/2,h/2],RECESS_TOP_M,depth+RECESS_TOP_M)
    cut.location=(x,y,z);cut.rotation_euler=rotation or (0,0,yaw);boolean(target,cut,'DIFFERENCE')
def save_export(objects,suffix):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(HERE/(NAME+suffix+'.glb')),export_format='GLB',use_selection=True,export_animations=True,export_extras=True,export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(HERE/(NAME+suffix+'.fbx')),use_selection=True,add_leaf_bones=False,axis_forward='-Z',axis_up='Y',bake_anim=True,apply_unit_scale=True)
def build():
    if '--placements-only' in sys.argv:
        deck_data,markers=data()
        report=json.loads((HERE/'skyfall_rig.json').read_text())
        assert deck_data==report['deck_sections'], 'Changed machining requires a full map rebuild'
        bpy.ops.wm.open_mainfile(filepath=str(HERE/'skyfall.blend'))
        for marker in markers:
            ob=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
            ob.matrix_world=Matrix.Translation(Vector(marker.get('mount_position_blender',marker['position_blender'])))@Euler(marker.get('mount_rotation_euler',marker['rotation_blender'])).to_matrix().to_4x4()
        bpy.context.view_layer.update()
        report['markers']=markers
        (HERE/'skyfall_rig.json').write_text(json.dumps(report,indent=2)+'\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'skyfall.blend'),compress=True)
        save_export([ob for ob in bpy.data.objects if ob.type in {'ARMATURE','MESH','EMPTY'}],'')
        print('SKYFALL_PLACEMENTS',len(markers),'unchanged machining',flush=True)
        return
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.render.fps=24;scene.frame_start=1;scene.frame_end=73
    deck_data,markers=data()
    parts=[];ownership={}
    from lunar_surface import build as lunar_surface
    ground=lunar_surface('SK_SkyfallLunar_LethalSurface')
    from lunar_surface import apply_materials
    apply_materials(ground)
    parts.append(ground);ownership[ground.name]='Root'
    # Platforms and mechanical support/wall props are native gizmo imports.
    arm_data=bpy.data.armatures.new('RIG_Skyfall');arm=bpy.data.objects.new('RIG_Skyfall',arm_data);bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    root=arm_data.edit_bones.new('Root');root.head=(0,0,0);root.tail=(0,0,1)
    for d in deck_data:
        b=arm_data.edit_bones.new('Deck_'+d['name']);b.head=(0,0,d['z']);b.tail=(0,0,d['z']+.5);b.parent=root
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in parts:
        group=o.vertex_groups.new(name=ownership[o.name]);group.add(list(range(len(o.data.vertices))),1,'REPLACE')
        mod=o.modifiers.new('rigid architectural section','ARMATURE');mod.object=arm;o.parent=arm
    sockets=[]
    for m in markers:
        ob=bpy.data.objects.new('Gizmo_'+m['name'].replace('-','_'),None);bpy.context.collection.objects.link(ob)
        ob.rotation_mode='QUATERNION'
        ob.empty_display_type='ARROWS';ob.empty_display_size=.35;ob['placement_asset']=m['asset'] or 'flag_base';ob['figma_node']=m['figma_node'] or 'mirrored '+str(m.get('mirrored_from'))
        bone='Deck_'+m['deck'] if any(d['name']==m['deck'] for d in deck_data) else 'Root'
        # Native bone-relative matrix becomes the same world axes in all consumers.
        ob.parent=arm;ob.parent_type='BONE';ob.parent_bone=bone
        bpy.context.view_layer.update()
        ob.matrix_world=Matrix.Translation(Vector(m.get('mount_position_blender',m['position_blender']))) @ Euler(m.get('mount_rotation_euler',m['rotation_blender'])).to_matrix().to_4x4()
        bpy.context.view_layer.update();sockets.append(ob)
        if m.get('pickup_contact_gizmo'):
            contact=bpy.data.objects.new(m['pickup_contact_gizmo'],None);bpy.context.collection.objects.link(contact)
            contact.rotation_mode='QUATERNION';contact.empty_display_type='ARROWS';contact.empty_display_size=.3
            contact.parent=arm;contact.parent_type='BONE';contact.parent_bone=bone
            x,z,negative_y=m['pickup_position_godot']
            bpy.context.view_layer.update();contact.matrix_world=Matrix.Translation((x,-negative_y,z))
            sockets.append(contact)
    arm.animation_data_create();action=bpy.data.actions.new('RIG_Skyfall_assemble');arm.animation_data.action=action
    for d in deck_data:
        bone=arm.pose.bones['Deck_'+d['name']]
        travel=2
        for frame,t in [(1,0),(25,0),(49,1),(73,1)]:
            bone.location=(0,-travel*(1-t),0);bone.keyframe_insert('location',frame=frame)
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(73);bpy.context.view_layer.update()
    sys.path.insert(0,str(HERE.parents[1]));from material_uv import prepare_export
    from platform_common import split_large
    ground_details=dict(interior_gravel_stone_count=ground['interior_gravel_stone_count'],maximum_interior_stone_height_m=.24)
    scenery=split_large(ground,arm,'SkyfallLunarLethalSurface')
    parts=scenery
    prepare_export(parts,HERE,NAME)
    scenery_tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in scenery)
    save_export([arm,*scenery],'_scenery')
    save_export([arm,*scenery],'_scenery_col')
    (HERE/'skyfall_scenery_rig.json').write_text(json.dumps(dict(name='skyfall_scenery',triangles=scenery_tris,budget_excluded=True,gizmos=[],**ground_details),indent=2)+'\n')
    parts=[o for o in parts if o not in scenery]
    tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in parts)
    helper_tris=sum(json.loads((HERE/(m['asset']+m['asset_suffix']+'_rig.json')).read_text())['triangles'] for m in markers if m['role']=='platform')
    BUDGET=tris+helper_tris # Map-owned geometry only; native props have independent budgets.
    rig=dict(name=NAME,source='Figma 0pxQrXAGeHplJ0ANVYwD8e / 69:3, '+json.loads((HERE/'figma_layout.json').read_text())['inspected'],triangles=tris,triangle_budget=BUDGET,helper_triangles=helper_tris,total_map_triangles=tris+helper_tris,canvas_m=[75,75],level_surface_z_m=HEIGHTS,markers=markers,deck_sections=deck_data,
        skeleton='RIG_Skyfall',assembly_seconds=3,lunar_surface=dict(lethal=True,playable=False,boundary=False),scenery_triangles=scenery_tris,geometry='placement rig; native floors, pillar platforms and weapon-holder walls imported on gizmos',budget_approval='2026-10-13: restore all native geometry and raise map-owned geometry limit to measured total; separately imported props excluded',
        actions=[dict(name='assemble',frames=[1,73],fps=24)],recess_clearance_per_side_m=RECESS_CLEARANCE_M,recess_authoring='final-union cuts using native prop footprint plus 1 mm per side and pit depth',budget_scope='platforms, bridges, lips and machined wells only; imported props and lunar scenery excluded')
    (HERE/'skyfall_rig.json').write_text(json.dumps(rig,indent=2)+'\n')
    for ob in scenery:bpy.data.objects.remove(ob,do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'skyfall.blend'),compress=True)
    save_export([arm,*parts,*sockets],'')
    print('SKYFALL',tris,'triangles',len(markers),'gizmos',len(deck_data),'deck sections')
if __name__=='__main__':build()
