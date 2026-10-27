"""Build Ramparts rock islands, native machined platforms and carrier sockets."""
MATERIAL_CLASSIFIERS = {
    'M_Frame':'Diffuse', 'M_Joint':'Diffuse', 'M_Primary':'Diffuse',
    'M_Secondary':'Diffuse', 'M_Regolith':'Diffuse', 'M_RegolithLight':'Diffuse',
    'M_RegolithDark':'Diffuse', 'M_Emissive':'Emissive',
    'M_RampartsPlain':'Diffuse', 'M_RampartsRock':'Diffuse', 'M_RampartsStone':'Diffuse',
}
import json
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'common'))
sys.path.insert(0,str(HERE.parent/'common/platform'))
sys.path.insert(0,str(HERE.parents[1]))
from layout import data, settings, HEIGHT, ROCK_BOTTOM
from map_shells import shell, boolean, cutter, recess_size, export
from platform_builder import build as platform
from platform_common import split_large, kit
from material_uv import prepare_export


def triangles(objects):
    return sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in objects)


def bind(ob,rig,bone='Root'):
    ob.parent=rig
    group=ob.vertex_groups.get(bone) or ob.vertex_groups.new(name=bone)
    group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
    if not any(m.type=='ARMATURE' for m in ob.modifiers):ob.modifiers.new('rigid map shell','ARMATURE').object=rig


def build_deck(d):
    stem='ramparts_deck_'+d['name']
    rects=d['rects'];extensions=[r for r in rects if r!=[-3.75,-3.75,3.75,3.75]] if d['name']=='Junction' else []
    rig,meshes,mounts,report=platform(HERE,stem,d['size_m'],extensions,(),False)
    w,h=d['size_m']
    col=shell('SK_'+stem+'_DeckCol',[-w/2,-h/2,w/2,h/2],0,.8)
    for rect in extensions:boolean(col,shell('TEMP_extension',rect,0,.8),'UNION')
    x,y,z=d['position']
    for hole in d['holes']:
        hx,hy,hz=hole['center'];local=[hx-x,hy-y,hz-z];hw,hh=hole['size'];depth=hole['depth']
        # A closed integral well supports fixtures deeper than the deck casting.
        if depth>.8:
            for target in (meshes[0],col):
                well=shell('TEMP_well',[-hw/2-.06,-hh/2-.06,hw/2+.06,hh/2+.06],-.72,depth-.72+.06)
                well.location=(local[0],local[1],0);well.rotation_euler.z=hole['yaw']
                if target.data.materials:well.data.materials.append(target.data.materials[0])
                boolean(target,well,'UNION')
        for target in [*meshes,col]:cutter(target,local,recess_size(hole['size']),depth,hole['yaw'])
    for ob in [*meshes,col]:
        ob.data.validate()
        ob.data.update()
    bind(col,rig)
    for ob in meshes:bind(ob,rig)
    prepare_export(meshes,HERE,stem)
    count=triangles(meshes)
    report.update(name=stem,triangles=count,meshes={o.name:triangles([o]) for o in meshes},
                  cutouts=d['holes'],recess_clearance_per_side_m=.001)
    (HERE/(stem+'_rig.json')).write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/(stem+'.blend')),compress=True)
    export([rig,*meshes,*mounts],HERE,stem)
    export([rig,col],HERE,stem+'_col')
    print('RAMPARTS_DECK',d['name'],count,flush=True)
    return count


def rock(name,center,seed):
    """Closed eroded mesa; native seats remain at the authored deck datum."""
    from terrain import geometry
    verts,faces=geometry(center,seed)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    # Fractured strata need independent planar painting charts. Connected
    # curved charts can fold across adjacent geological ridges.
    ob['uv_face_charts']=True
    for label,color in [('M_RampartsPlain_Diffuse',(.22,.24,.23,1)),('M_RampartsRock_Diffuse',(.15,.18,.19,1))]:
        mat=bpy.data.materials.get(label) or bpy.data.materials.new(label);mat.diffuse_color=color
        bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=color;bsdf.inputs['Roughness'].default_value=.91
        ob.data.materials.append(mat)
    for p in mesh.polygons:
        p.material_index=0 if p.normal.z>.65 else 1
        p.use_smooth=True
    return ob


def main():
    decks,markers=data()
    selected=set(sys.argv[sys.argv.index('--only-decks')+1].split(',')) if '--only-decks' in sys.argv else None
    helper=sum(json.loads((HERE/('ramparts_deck_'+d['name']+'_rig.json')).read_text())['triangles']
               if '--shell-only' in sys.argv or (selected is not None and d['name'] not in selected) else build_deck(d) for d in decks if not d['rock'])
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.render.fps=24;scene.frame_end=73
    arm_data=bpy.data.armatures.new('RIG_Ramparts');rig=bpy.data.objects.new('RIG_Ramparts',arm_data);scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    root=arm_data.edit_bones.new('Root');root.head=(0,0,0);root.tail=(0,0,1)
    for d in decks:
        bone=arm_data.edit_bones.new('Deck_'+d['name']);bone.head=(0,0,0);bone.tail=(0,0,1);bone.parent=root
    bpy.ops.object.mode_set(mode='OBJECT')
    meshes=[];colliders=[]
    for d in decks:
        if not d['rock']:continue
        ob=rock('SK_RampartsRock_'+d['name'],d['position'],319 if d['name'].startswith('A') else 841)
        for h in d['holes']:
            for tier in h.get('tiers',[dict(size=h['size'],from_z=0,to_z=-h['depth'])]):
                p=[*h['center']];p[2]+=tier['from_z']
                cutter(ob,p,recess_size(tier['size']),tier['from_z']-tier['to_z'],h['yaw'])
        col=ob.copy();col.data=ob.data.copy();col.name=ob.name+'Col';scene.collection.objects.link(col);bind(col,rig);colliders.append(col)
        bind(ob,rig);meshes.extend(split_large(ob,rig,'RampartsRock'+d['name']))
    from crater import build as build_crater
    arm_data=bpy.data.armatures.new('RIG_RampartsScenery')
    scenery_rig=bpy.data.objects.new('RIG_RampartsScenery',arm_data);scene.collection.objects.link(scenery_rig)
    bpy.context.view_layer.objects.active=scenery_rig;scenery_rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT');bone=arm_data.edit_bones.new('Root');bone.head=(0,0,0);bone.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
    scenery=[];scenery_collision=[]
    for basin in build_crater():
        is_terrain='Crater' in basin.name
        collider=basin.copy();collider.data=basin.data.copy();collider.name=basin.name+'Col'
        scene.collection.objects.link(collider);bind(collider,scenery_rig);scenery_collision.append(collider)
        bind(basin,scenery_rig);parts=split_large(basin,scenery_rig,basin.name.removeprefix('SK_'))
        if is_terrain:
            from planetary_surface import validate_atlas
            validate_atlas(parts,HERE,'ramparts_scenery')
        else:prepare_export(parts,HERE,'ramparts_scenery')
        scenery.extend(parts)
    prepare_export(scenery,HERE,'ramparts_scenery')
    scenery_count=triangles(scenery)
    export([scenery_rig,*scenery],HERE,'ramparts_scenery')
    export([scenery_rig,*scenery_collision],HERE,'ramparts_scenery_col')
    (HERE/'ramparts_scenery_rig.json').write_text(json.dumps(dict(name='ramparts_scenery',triangles=scenery_count,triangle_budget=60000,
        budget_excluded=True,static=True,terrain_authoring='Terrain3D 1.0.2',stone_count=72,gizmos=[]),indent=2)+'\n')
    for ob in [*scenery,*scenery_collision,scenery_rig]:bpy.data.objects.remove(ob,do_unlink=True)
    sockets=[]
    for m in markers:
        ob=bpy.data.objects.new('Gizmo_'+m['name'].replace('-','_'),None);scene.collection.objects.link(ob)
        ob.parent=rig;ob.parent_type='BONE';ob.parent_bone='Deck_'+m['deck'] if m['deck'] else 'Root'
        bpy.context.view_layer.update()
        ob.matrix_world=Matrix.Translation(Vector(m['position_blender']))@Euler(m['rotation_blender']).to_matrix().to_4x4()
        ob['placement_asset']=m['asset']
        if m['figma_node'] is not None:ob['figma_node']=m['figma_node']
        sockets.append(ob)
    # Required assembly channel is separate from deterministic gameplay motion.
    rig.animation_data_create();action=bpy.data.actions.new('RIG_Ramparts_assemble');rig.animation_data.action=action
    bone=rig.pose.bones['Root']
    for frame in (1,73):bone.location=(0,0,0);bone.keyframe_insert('location',frame=frame)
    scene.frame_set(73)
    prepare_export(meshes,HERE,'ramparts')
    machining=sum(json.loads((HERE/('ramparts'+m['asset_suffix']+'_rig.json')).read_text())['map_owned_boolean_triangles']
                  for m in markers if m.get('source_asset')=='cistern')
    total=helper+triangles(meshes)+machining;assert total<=25000,('Map geometry budget',total)
    report=dict(name='ramparts',canvas_m=[75,75],triangle_budget=25000,triangles=triangles(meshes),
        helper_triangles=helper,architecture_machining_triangles=machining,total_map_triangles=total,scenery_triangles=scenery_count,markers=markers,deck_sections=decks,
        level_surface_z_m=[HEIGHT],water_surface_m=0,rock_bottom_m=ROCK_BOTTOM,crater=settings()['crater'],
        recess_clearance_per_side_m=.001,actions=[dict(name='assemble',frames=[1,73],fps=24)],
        skeleton='RIG_Ramparts',meshes={o.name:triangles([o]) for o in meshes},gizmos=[],
        budget_scope='Integral rock islands, native deck castings and machining; imported native props excluded')
    (HERE/'ramparts_rig.json').write_text(json.dumps(report,indent=2)+'\n')
    for ob in colliders:ob.hide_render=True
    from planetary_surface import clean_authoring_defaults
    clean_authoring_defaults()
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'ramparts.blend'),compress=True)
    export([rig,*meshes,*sockets],HERE,'ramparts',animated=True)
    export([rig,*colliders],HERE,'ramparts_col')
    print('RAMPARTS',total,'map triangles',len(markers),'native placements',flush=True)


if __name__=='__main__':main()
