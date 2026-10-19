"""Faceoff lunar terrain, machined fixture wells and native placement gizmos."""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Regolith': 'Diffuse',
    'M_RegolithDark': 'Diffuse',
    'M_RegolithLight': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import bpy,json,math,sys
from pathlib import Path
from mathutils import Matrix,Vector,Euler
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'architecture'))
HERE=Path(__file__).resolve().parent;MODELS=HERE.parents[1];NAME='faceoff';BUDGET=25000
sys.path.insert(0,str(HERE));from layout import data
sys.path.insert(0,str(HERE.parent/'common'));sys.path.insert(0,str(HERE.parent/'common/platform'));from map_shells import shell,cutter,export,recess_size,RECESS_CLEARANCE_M
def main():
    if '--placements-only' in sys.argv:
        markers,holes=data()
        report=json.loads((HERE/'faceoff_rig.json').read_text())
        assert holes==report['holes'], 'Changed machining requires a full map rebuild'
        bpy.ops.wm.open_mainfile(filepath=str(HERE/'faceoff.blend'))
        rig=bpy.data.objects['RIG_Faceoff']
        for marker in markers:
            ob=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
            ob.matrix_world=Matrix.Translation(Vector(marker['position_blender']))@Euler(marker['rotation_blender']).to_matrix().to_4x4()
        bpy.context.view_layer.update()
        report['markers']=markers
        (HERE/'faceoff_rig.json').write_text(json.dumps(report,indent=2)+'\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'faceoff.blend'),compress=True)
        export([rig,*[ob for ob in bpy.data.objects if ob.type=='EMPTY']],HERE,NAME,animated=True)
        print('FACEOFF_PLACEMENTS',len(markers),'unchanged machining',flush=True)
        return
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.render.fps=24;scene.frame_start=1;scene.frame_end=73
    from lunar_surface import build as lunar_surface
    markers,holes=data()
    protected=[]
    for marker in markers:
        if marker['position_blender'][2]>.6 and marker.get('source_category')!='architecture':continue
        x,y,_=marker['position_blender']
        radius=1.5
        asset=marker.get('source_asset',marker['asset'])
        if marker.get('source_category')=='architecture':
            meta=json.loads((MODELS/'architecture'/asset/(asset+'_rig.json')).read_text())
            bounds=meta['bounds_m']
            radius=math.hypot(max(abs(bounds['lo'][0]),abs(bounds['hi'][0])),max(abs(bounds['lo'][1]),abs(bounds['hi'][1])))+.35
        protected.append((x,y,radius))
    ground=lunar_surface('SK_FaceoffLunarGround',flat_radius=60,protected=protected)
    ground_baseline_triangles=sum(len(p.vertices)-2 for p in ground.data.polygons)
    for hole in holes:
        if hole['center'][2]-hole['depth']<0:cutter(ground,hole['center'],recess_size(hole['size']),hole['depth'],hole['yaw'])
    from lunar_surface import apply_materials
    apply_materials(ground)
    arm_data=bpy.data.armatures.new('RIG_Faceoff');rig=bpy.data.objects.new('RIG_Faceoff',arm_data);scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    root=arm_data.edit_bones.new('Root');root.head=(0,0,0);root.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
    for ob in (ground,):
        ob.parent=rig;ob.vertex_groups.new(name='Root').add(list(range(len(ob.data.vertices))),1,'REPLACE');ob.modifiers.new('lunar Root','ARMATURE').object=rig
    empties=[]
    for marker in markers:
        ob=bpy.data.objects.new('Gizmo_'+marker['name'].replace('-','_'),None);scene.collection.objects.link(ob);ob.parent=rig
        ob.empty_display_type='ARROWS';ob.empty_display_size=.35;ob['placement_asset']=marker['asset'];ob['figma_node']=marker['figma_node']
        ob.matrix_world=Matrix.Translation(Vector(marker['position_blender']))@Euler(marker['rotation_blender']).to_matrix().to_4x4();empties.append(ob)
    rig.animation_data_create();action=bpy.data.actions.new('RIG_Faceoff_assemble');rig.animation_data.action=action
    for frame in (1,73):rig.pose.bones['Root'].keyframe_insert('location',frame=frame)
    sys.path.insert(0,str(MODELS));from material_uv import prepare_export
    from platform_common import split_large
    ground_details=dict(interior_gravel_stone_count=ground['interior_gravel_stone_count'],maximum_interior_stone_height_m=.24)
    scenery=split_large(ground,rig,'FaceoffLunarGround')
    prepare_export(scenery,HERE,NAME)
    scenery_count=sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in scenery)
    export([rig,*scenery],HERE,'faceoff_scenery',animated=True)
    export([rig,*scenery],HERE,'faceoff_scenery_col',animated=True)
    (HERE/'faceoff_scenery_rig.json').write_text(json.dumps(dict(name='faceoff_scenery',triangles=scenery_count,budget_excluded=True,gizmos=[],**ground_details),indent=2)+'\n')
    count=0
    ground_machining=max(0,scenery_count-ground_baseline_triangles)
    machining=ground_machining+sum(json.loads((HERE/('faceoff'+m['asset_suffix']+'_rig.json')).read_text()).get('map_owned_boolean_triangles',0) for m in markers if m.get('source_asset'))
    assert machining<=BUDGET
    report=dict(name=NAME,source='Figma 0pxQrXAGeHplJ0ANVYwD8e / 143:891',canvas_m=[75,75],triangles=count,total_map_triangles=machining,scenery_triangles=scenery_count,triangle_budget=BUDGET,markers=markers,holes=holes,recess_clearance_per_side_m=RECESS_CLEARANCE_M,
        skeleton='RIG_Faceoff',assembly_seconds=3,actions=[dict(name='assemble',frames=[1,73],fps=24)],geometry='playable lunar terrain and fixture wells; native architecture/props imported at gizmos',native_architecture_variants=[m['source_asset'] for m in markers if m.get('source_asset')])
    (HERE/'faceoff_rig.json').write_text(json.dumps(report,indent=2)+'\n')
    for ob in scenery:bpy.data.objects.remove(ob,do_unlink=True)
    scene.frame_set(73);bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'faceoff.blend'),compress=True)
    export([rig,*empties],HERE,NAME,animated=True)
    print('FACEOFF',count,'triangles',len(markers),'gizmos',flush=True)
if __name__=='__main__':main()
