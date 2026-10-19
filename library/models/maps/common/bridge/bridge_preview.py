"""Studio option states and genuine platform/fixture assembly previews."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'platform'))
from platform_common import common


def import_asset(path,matrix):
    before=set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects=set(bpy.context.scene.objects)-before
    for obj in objects:
        if obj.parent not in objects:obj.matrix_world=matrix@obj.matrix_world
        if obj.type=='ARMATURE':obj.animation_data_clear()
    return objects


def render(studio):
    from platform_builder import generate
    platform=HERE.parents[3]/'target/platforms/bridge_reference'
    report=generate(platform,'platform',dict(size_m=[10,10],underbody=False,
        omit_border_segments_m=[[[-2.5,-5],[2.5,-5]],[[-2.5,5],[2.5,5]]]))
    studio.open_model();studio.setup_render()
    for mount in [o for o in bpy.context.scene.objects if o.type=='EMPTY' and o.get('attachment')=='sconce_light']:
        path=HERE.parents[2]/'environments/sconce_light/sconce_light.glb'
        import_asset(path,mount.matrix_world.copy())
    batten=import_asset(HERE.parents[2]/'environments/batten_light/batten_light.glb',
                        bpy.data.objects['BattenLightMount'].matrix_world.copy())
    studio.VIEWS['front_left']=((1,-1,.65),'PERSP',(1280,900))
    studio.VIEWS['rear_right']=((-1,1,-.65),'PERSP',(1280,900))
    cam=studio.create_camera();lights=studio.create_lights()
    for view in studio.VIEWS:studio.render_view(cam,lights,view)
    rails=[bpy.data.objects['SK_Bridge5X5Railing'+side] for side in ('Left','Right')]
    cover=bpy.data.objects['SK_Bridge5X5Cover']
    frames=[bpy.data.objects['SK_Bridge5X5SideFrame'+side] for side in ('Left','Right')]
    for tag,has_rails,has_cover in (('bare',False,False),('railed',True,False),
                                  ('covered',False,True),('railed_covered',True,True)):
        for obj in rails:obj.hide_render=not has_rails
        cover.hide_render=not has_cover
        for obj in batten:obj.hide_render=not has_cover
        for obj in frames:obj.hide_render=not (has_rails or has_cover)
        studio.render_view(cam,lights,'front_left',tag)
    for socket_name,plug_name in (('BridgeSocketRear','BridgePlugFront'),('BridgeSocketFront','BridgePlugRear')):
        socket=bpy.data.objects[socket_name].matrix_world
        plug=next(g for g in report['gizmos'] if g['name']==plug_name)
        transform=socket@Matrix(plug['matrix_world']).inverted()
        imported=import_asset(platform/'platform.glb',transform)
        # Preview attachments use authored assets and their exact live frames.
        for gizmo in report['gizmos']:
            if 'attachment' not in gizmo or gizmo['name'] in plug['omit_fixture_mounts']:continue
            asset=gizmo['attachment'];folder=HERE.parents[2]/'environments'/asset
            import_asset(folder/f'{asset}.glb',transform@Matrix(gizmo['matrix_world']))
    studio.render_view(cam,lights,'front_left','assembled_railed_covered')
    cover.hide_render=True
    for obj in batten:obj.hide_render=True
    studio.render_view(cam,lights,'front_left','assembled_railed')
    print('[bridge] optional states and actual platform assemblies PASS',flush=True)
