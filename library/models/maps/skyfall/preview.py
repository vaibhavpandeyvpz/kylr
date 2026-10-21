"""Inspect the authored map with visible axes and native imported props."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Matrix,Vector,Euler
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
bpy.ops.wm.open_mainfile(filepath=str(HERE/'skyfall.blend'))
scene=bpy.context.scene;scene.frame_set(73)
rig=json.loads((HERE/'skyfall_rig.json').read_text())
def material(name,color,glow=0):
    m=bpy.data.materials.new(name);p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=glow;return m
world=bpy.data.worlds.new('Lunar preview');world.node_tree.nodes['Background'].inputs['Color'].default_value=(.14,.16,.20,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5;scene.world=world
for name,loc,power,size in [('Key',(-35,-45,80),18000,60),('Fill',(45,25,55),11000,45),('Rim',(-20,50,40),8000,25)]:
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new('LGT_'+name,d);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(-Vector(loc)).to_track_quat('-Z','Y').to_euler()
camera_data=bpy.data.cameras.new('Skyfall');camera=bpy.data.objects.new('CAM_Skyfall',camera_data);scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO';camera_data.ortho_scale=115
def view(position,target,scale):camera.location=position;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.ortho_scale=scale
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
preferences=bpy.context.preferences.addons['cycles'].preferences
try:
    preferences.compute_device_type='OPTIX';preferences.get_devices()
    for device in preferences.devices:device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
except Exception:pass
gizmo_collection=bpy.data.collections.new('PRV / placement axes');scene.collection.children.link(gizmo_collection)
axis_materials=[material('PRV_axis_'+str(i),c,1.5) for i,c in enumerate([(1,.15,.08),(.10,1,.25),(.12,.45,1)])]
for marker in rig['markers']:
    mount=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
    for axis in range(3):
        curve=bpy.data.curves.new('axis','CURVE');curve.dimensions='3D';curve.bevel_depth=.04;curve.bevel_resolution=0
        line=curve.splines.new('POLY');line.points.add(1);line.points[0].co=(0,0,0,1);tip=[0,0,0,1];tip[axis]=.6;line.points[1].co=tip;curve.materials.append(axis_materials[axis])
        ob=bpy.data.objects.new('PRV_'+marker['name']+'_'+str(axis),curve);gizmo_collection.objects.link(ob);ob.matrix_world=mount.matrix_world.copy()
sys.path.insert(0,str(HERE.parent/'common'));sys.path.insert(0,str(HERE.parent/'common/platform'))
from lighting_preview import install as install_projection_lights
sys.path.insert(0,str(HERE.parents[1]/'architecture'))
from lunar_material import preview as lunar_preview
templates={};imported=[];placements={};hidden_fixtures=[];gizmo_phase=True
template_collection=bpy.data.collections.new('PRV / native templates');scene.collection.children.link(template_collection);template_collection.hide_render=True
def instance(category,asset,suffix,mount):
    key=(category,asset,suffix)
    if key not in templates:
        before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/category/asset/(asset+suffix+'.glb')))
        source=list(set(bpy.data.objects)-before)
        helpers={bone.custom_shape for ob in source if ob.type=='ARMATURE' for bone in ob.pose.bones if bone.custom_shape}
        for helper in helpers:helper.hide_render=True
        source=[ob for ob in source if ob not in helpers]
        for ob in source:
            for col in list(ob.users_collection):col.objects.unlink(ob)
            template_collection.objects.link(ob)
        templates[key]=source
    source=templates[key];copies={}
    for ob in source:
        clone=ob.copy()
        if ob.type=='ARMATURE':
            clone.data=ob.data.copy();clone['preview_asset']=asset;clone['preview_category']=category
        scene.collection.objects.link(clone);copies[ob]=clone;imported.append(clone)
        if gizmo_phase and asset in ('sconce_light','batten_light','pillar_platform','weapon_holder_wall'):
            clone.hide_render=True;hidden_fixtures.append(clone)
    roots=[]
    for ob,clone in copies.items():
        if ob.parent in copies:clone.parent=copies[ob.parent]
        else:roots.append(clone)
        for modifier in clone.modifiers:
            if modifier.type=='ARMATURE' and modifier.object in copies:modifier.object=copies[modifier.object]
    for ob in roots:ob.parent=mount;ob.matrix_parent_inverse=Matrix.Identity(4)
    bpy.context.view_layer.update()
    meta_path=ROOT/category/asset/(asset+suffix+'_rig.json')
    if meta_path.exists():
        native_metadata=json.loads(meta_path.read_text())
        hidden_fixtures.extend(install_projection_lights(asset,list(copies.values()),native_metadata,gizmo_phase))
        for gizmo in native_metadata.get('gizmos',[]):
            if not isinstance(gizmo,dict):continue
            lamp_asset=gizmo.get('attachment')
            if lamp_asset not in ('sconce_light','batten_light'):continue
            lamp_mount=socket(list(copies.values()),gizmo['name'])
            assert lamp_mount is not None,(asset,gizmo['name'])
            lamps=instance('environments',lamp_asset,'',lamp_mount)
    return list(copies.values())
def socket(objects,name):return next((o for o in objects if o.name.split('.')[0]==name),None)
def pose(objects,label,selected=None,time_s=None):
    for arm in objects:
        if arm.type!='ARMATURE':continue
        actions=[]
        if arm.animation_data:
            for track in arm.animation_data.nla_tracks:
                for strip in track.strips:
                    if label.lower() in strip.action.name.lower() and (not selected or any(n in strip.action.name for n in selected)):actions.append(strip.action)
            if arm.animation_data.action and label.lower() in arm.animation_data.action.name.lower():actions.append(arm.animation_data.action)
        if actions:
            for track in arm.animation_data.nla_tracks:track.mute=True
            states={}
            for action in actions:
                arm.animation_data.action=action
                scene.frame_set(int(action.frame_range[0]));bpy.context.view_layer.update()
                closed={bone.name:bone.matrix_basis.copy() for bone in arm.pose.bones}
                frame=action.frame_range[1] if time_s is None else action.frame_range[0]+time_s*scene.render.fps
                scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update()
                for bone in arm.pose.bones:
                    if bone.name not in states or max(abs(bone.matrix_basis[i][j]-closed[bone.name][i][j]) for i in range(4) for j in range(4))>1e-6:
                        states[bone.name]=bone.matrix_basis.copy()
            arm.animation_data.action=None
            for bone in arm.pose.bones:bone.matrix_basis=states.get(bone.name,Matrix.Identity(4))
    scene.frame_set(73)
for marker in rig['markers']:
    if marker['role']=='platform' or marker.get('load_at_start'):
        mount=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
        if marker.get('parent_fixture'):mount=socket(placements[marker['parent_fixture']],marker['parent_socket'])
        placements[marker['name']]=instance(marker['category'],marker['asset'],marker.get('asset_suffix',''),mount)
lunar_preview()
view((70,-95,88),(0,0,5),125)
lunar_preview()
scene.render.filepath=str(HERE/'skyfall_preview_gizmos.png');bpy.ops.render.render(write_still=True)
gizmo_collection.hide_render=True
gizmo_phase=False
for fixture in hidden_fixtures:fixture.hide_render=False
for marker in rig['markers']:
    if not marker['asset'] or marker['role']=='platform' or marker.get('load_at_start'):continue
    mount=bpy.data.objects['Gizmo_'+marker['name'].replace('-','_')]
    if marker.get('parent_fixture'):
        mount=socket(placements[marker['parent_fixture']],marker['parent_socket'])
        assert mount is not None,marker['name']
    objects=instance(marker['category'],marker['asset'],'_ammo' if marker['role']=='ammo' else marker.get('asset_suffix',''),mount)
    if marker['asset']=='pillar':
        pose(objects,'open',time_s=marker.get('support_open_time_s'))
        for arm in objects:
            if arm.type=='ARMATURE':arm['support_open_time_s']=marker['support_open_time_s']
    if marker['asset'] in ('weapon_holder','item_table'):pose(objects,'deploy')
    if marker['asset']=='item_cradle':pose(objects,'close')
    if marker['role']=='flag_base':pose(objects,'deploy')
    if marker['role']=='jumbotron':pose(objects,'flood')
    if marker['asset']=='stasis_chamber':pose(objects,'close')
    elif marker['category']=='architecture':pose(objects,'open',marker.get('open_actions'))
    if marker['role']=='barricade':pose(objects,'lower')
    if marker['role']=='pulse_gun':pose(objects,'armed')
    if marker['role'] in ('weapon','energy','shield'):
        attachment=socket(objects,'WeaponMount' if marker['asset']=='weapon_holder' else 'ItemMount')
        assert attachment is not None,(marker['name'],'missing payload axis')
        if marker['role']=='weapon':
            gun=instance('weapons',marker['weapon'],'',attachment);pack=socket(gun,'AmmoMount')
            if pack:instance('weapons',marker['weapon'],'_ammo',pack)
        else:instance('gameplay',marker['role']+'_core','',attachment)
lunar_preview()
sys.path.insert(0,str(HERE.parent/'common'))
from planetary_surface import preview as planetary_preview
planetary_preview()
view((70,-95,88),(0,0,5),125);scene.render.filepath=str(HERE/'skyfall_preview_models.png');bpy.ops.render.render(write_still=True)
view((0,0,130),(0,0,0),90);scene.render.filepath=str(HERE/'skyfall_preview_top.png');bpy.ops.render.render(write_still=True)
view((44,-46,42),(23,-22,25),42);scene.render.filepath=str(HERE/'skyfall_preview_layers.png');bpy.ops.render.render(write_still=True)
view((85,-115,95),(0,0,10),185);scene.render.filepath=str(HERE/'skyfall_preview_crater.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'skyfall_preview.blend'),compress=True)
print('SKYFALL_PREVIEW',len(rig['markers']),'native placements')
