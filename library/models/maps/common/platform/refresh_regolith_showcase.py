"""Reimport static scenery/dressing on existing native showcase gizmos.

Uses regenerated library exports. Retains native rig actions and cinematic keys;
no mesh coordinates, payload axes or rig poses are edited in the assembly.
"""
import bpy,sys,json
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;MAPS=HERE.parents[1]

def refresh(path):
    bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene
    sources={}
    for meta in (MAPS/'skyfall').glob('skyfall_module_platform_*_rig.json'):
        if json.loads(meta.read_text()).get('source_helper')!='platform':continue
        stem=meta.name.removesuffix('_rig.json')
        sources['RIG_'+''.join(p.title() for p in stem.split('_'))]=meta.parent/(stem+'_regolith.glb')
    sources['RIG_ItemCradle']=MAPS.parents[0]/'gameplay/item_cradle/item_cradle.glb'
    groups={}
    for obj in list(bpy.data.objects):
        if obj.type!='MESH':continue
        arm=next((m.object for m in obj.modifiers if m.type=='ARMATURE' and m.object),None)
        if arm is None:continue
        key=arm.name.split('.')[0]
        source=None
        if (obj.name.startswith('SK_ArchitectureRegolith') or obj.name.startswith('SK_ItemCradle')) and key in sources:source=sources[key]
        if obj.name.startswith('SK_SkyfallLunarLethalSurface'):source=MAPS/'skyfall/skyfall_scenery.glb'
        if obj.name.startswith('SK_FaceoffLunarGround'):source=MAPS/'faceoff/faceoff_scenery.glb'
        if source:groups[arm]=source
    for old,source in groups.items():
        name=old.name;parent=old.parent;basis=old.matrix_basis.copy();inverse=old.matrix_parent_inverse.copy()
        collections=list(old.users_collection);props=dict(old.items())
        action=old.animation_data.action if old.animation_data else None
        owned=[old,*old.children_recursive]
        nested=[o for o in old.children_recursive if o.type=='ARMATURE']
        payloads=[]
        for child in nested:
            ancestor=child.parent;inside_payload=False
            while ancestor is not None and ancestor!=old:
                if ancestor in nested:inside_payload=True;break
                ancestor=ancestor.parent
            if inside_payload:continue
            payloads.append((child,child.parent.name.split('.')[0],child.matrix_basis.copy(),child.matrix_parent_inverse.copy()))
            for external in [child,*child.children_recursive]:
                if external in owned:owned.remove(external)
            child.parent=None

        before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(source))
        imported=set(bpy.data.objects)-before
        shapes={b.custom_shape for o in imported if o.type=='ARMATURE' for b in o.pose.bones if b.custom_shape}
        for shape in shapes:shape.hide_render=True
        actual=[o for o in imported if o not in shapes]
        roots=[o for o in actual if o.parent not in imported]
        assert len(roots)==1,(source,[o.name for o in roots])
        new=roots[0];assert new.type=='ARMATURE',source
        for obj in actual:
            for collection in list(obj.users_collection):collection.objects.unlink(obj)
            for collection in collections:collection.objects.link(obj)
        new.parent=parent;new.matrix_parent_inverse=inverse;new.matrix_basis=basis
        for key,value in props.items():new[key]=value
        new.animation_data_clear()
        if action:new.animation_data_create();new.animation_data.action=action
        for obj in reversed(owned):bpy.data.objects.remove(obj,do_unlink=True)
        new.name=name
        for child,socket_name,local,parent_inverse in payloads:
            socket=next(o for o in actual if o.name.split('.')[0]==socket_name)
            child.parent=socket;child.matrix_parent_inverse=parent_inverse;child.matrix_basis=local
        print('SHOWCASE_NATIVE_REIMPORT',source.name,'on',parent.name if parent else 'hidden template',flush=True)
    assert groups,'No native scenery or platform dressing found'
    sys.path.insert(0,str(MAPS.parents[0]/'architecture'))
    from lunar_material import preview
    preview()
    scene.eevee.shadow_pool_size='1536' if path.parent.name=='faceoff' else '1024'
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
    if '--render-stills' in sys.argv:
        map=path.parent.name;scene.frame_set(73)
        scene.render.engine='CYCLES';scene.cycles.samples=16
        try:
            prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
            for device in prefs.devices:device.use=device.type=='OPTIX'
            scene.cycles.device='GPU'
        except Exception:pass
        scene.render.image_settings.media_type='IMAGE';scene.render.image_settings.file_format='PNG'
        cam=scene.camera;cam.animation_data_clear();cam.data.type='ORTHO'
        def view(at,focus,size,label):
            cam.location=at;cam.rotation_mode='QUATERNION';cam.rotation_quaternion=(Vector(focus)-cam.location).to_track_quat('-Z','Y')
            cam.data.ortho_scale=size;scene.render.filepath=str(path.parent/(map+'_preview_'+label+'.png'))
            bpy.ops.render.render(write_still=True)
        prop_objects=set()
        for arm in bpy.data.objects:
            if arm.type=='ARMATURE' and arm.get('preview_category') not in (None,'maps'):
                prop_objects.update([arm,*arm.children_recursive])
        flags={obj:obj.hide_render for obj in prop_objects}
        for obj in prop_objects:obj.hide_render=True
        axes=bpy.data.collections.get('PRV / placement axes');axes.hide_render=False
        view((70,-95,88),(0,0,5),125,'gizmos')
        axes.hide_render=True
        for obj,flag in flags.items():obj.hide_render=flag
        view((70,-95,88),(0,0,5),125,'models')
        view((0,0,130),(0,0,0),90,'top')
        if map=='skyfall':view((44,-46,42),(23,-22,25),42,'layers')
        else:view((36,-36,22),(24,-24,2),35,'layers')
        view((85,-115,95),(0,0,10),185,'crater')
        if map=='skyfall':view((9,-11,6),(3,-4,0),14,'ground')
        else:view((14,-20,6),(9,-15,0),14,'ground')
        bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
    if '--check-frame' in sys.argv:
        scene.frame_set(241);scene.render.image_settings.media_type='IMAGE';scene.render.image_settings.file_format='PNG'
        scene.render.filepath=str(path.parent/(path.stem+'_regolith_check.png'));bpy.ops.render.render(write_still=True)

if __name__=='__main__':refresh(Path(sys.argv[sys.argv.index('--')+1]).resolve())
