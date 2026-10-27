"""13 s native-rig showcase: assembly then a continuous drone fly-by.
Run after preview.py. -- --no-render builds/validates the cinematic only.
All items inherit their real rigged sockets; imported native loops are sampled.
"""
import bpy,json,math,re,sys
from pathlib import Path
from mathutils import Vector,Matrix
HERE=Path(__file__).resolve().parent
elevation=json.loads((HERE/'settings.json').read_text())['elevation_offset_m']
sections=json.loads((HERE/'skyfall_rig.json').read_text())['deck_sections']
bpy.ops.wm.open_mainfile(filepath=str(HERE/'skyfall_preview.blend'))
scene=bpy.context.scene;scene.frame_set(73);FPS=24;LAST=13*FPS
scene.render.fps=FPS;scene.frame_start=1;scene.frame_end=LAST
scene.render.resolution_x=1280;scene.render.resolution_y=720
scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=8;scene.cycles.samples=8;scene.render.use_persistent_data=True
scene.eevee.shadow_pool_size='1024'
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
except Exception:pass

def curves(action):
    return [curve for layer in action.layers for strip in layer.strips for bag in strip.channelbags for curve in bag.fcurves]
def actions(arm):
    out={}
    if not arm.animation_data:return out
    for track in arm.animation_data.nla_tracks:
        for strip in track.strips:out[strip.action.name]=strip.action
    if arm.animation_data.action:out[arm.animation_data.action.name]=arm.animation_data.action
    return out

def apply(arm,action,frame,dynamic=False):
    fcurves=curves(action);moving=set()
    for curve in fcurves:
        match=re.match(r'pose.bones\["(.*?)"\]',curve.data_path)
        values=[key.co.y for key in curve.keyframe_points]
        if match and values and max(values)-min(values)>1e-6:moving.add(match.group(1))
    for curve in fcurves:
        match=re.match(r'pose.bones\["(.*?)"\]',curve.data_path)
        if not match or (dynamic and match.group(1) not in moving):continue
        value=arm.path_resolve(curve.data_path)
        value[curve.array_index]=curve.evaluate(frame)
    return moving

plans=[];loop_count=0
for arm in scene.objects:
    if arm.type!='ARMATURE' or any(c.name=='PRV / native templates' for c in arm.users_collection):continue
    clips=actions(arm);asset=arm.get('preview_asset','skyfall' if arm.name=='RIG_Skyfall' else '')
    loop_label={'weapon_holder':'spin','item_table':'spin','thruster':'idle','portal_gate':'active','jumbotron':'hover','ctf_flag':'wave','energy_core':'spin','shield_core':'spin'}.get(asset)
    if not loop_label and asset:
        meta=HERE.parents[1]/arm.get('preview_category','')/asset/(asset+'_rig.json')
        if meta.exists():
            animations=json.loads(meta.read_text()).get('animations',{})
            if isinstance(animations,dict):loop_label=next((name for name,info in animations.items() if isinstance(info,dict) and info.get('loop')),None)
    pick=lambda label:next((action for name,action in clips.items() if re.sub(r'\.\d+$','',name).lower().endswith('_'+label.lower()) or re.sub(r'\.\d+$','',name).lower()==label.lower()),None) if label else None
    loop=pick(loop_label);intro=pick('assemble' if asset=='skyfall' else 'deploy' if asset in ('weapon_holder','item_table') else 'lower' if asset=='barricade' else 'open' if asset=='pillar' else '')
    if loop is None and intro is None:continue
    if asset=='barricade':
        raised=pick('raise')
        if raised:apply(arm,raised,raised.frame_range[1])
    base={bone.name:bone.matrix_basis.copy() for bone in arm.pose.bones}
    arm.animation_data_create();arm.animation_data.action=None
    for track in arm.animation_data.nla_tracks:track.mute=True
    bake=bpy.data.actions.new('PRV_'+arm.name);arm.animation_data.action=bake
    plans.append((arm,asset,base,loop,intro,bake));loop_count+=int(loop is not None)
for frame in range(1,LAST+1):
    t=(frame-1)/FPS
    for arm,asset,base,loop,intro,bake in plans:
        for bone in arm.pose.bones:bone.matrix_basis=base[bone.name]
        if intro:
            phase=min(1,t/3) if asset=='skyfall' else min(1,max(0,t-2))
            if asset=='pillar':
                phase=min(1,max(0,t-1))
                apply(arm,intro,intro.frame_range[0]+phase*arm['support_open_time_s']*FPS)
            else:apply(arm,intro,intro.frame_range[0]+phase*(intro.frame_range[1]-intro.frame_range[0]))
        if loop and (t>=3 or asset not in ('weapon_holder','item_table')):
            span=loop.frame_range[1]-loop.frame_range[0]
            if span>0:apply(arm,loop,loop.frame_range[0]+((max(0,t-3) if asset in ('weapon_holder','item_table') else t)*FPS)%span,True)
        if arm.name=='RIG_Skyfall' and t>=3:
            for section in sections:
                motion=section['motion'];bone=arm.pose.bones.get('Deck_'+section['name'])
                if bone:bone.location.y+=motion['bob_amplitude']*math.sin(math.tau*(t-3)/motion['period'])
        for bone in arm.pose.bones:
            bone.rotation_mode='QUATERNION'
            for field in ('location','rotation_quaternion','scale'):bone.keyframe_insert(field,frame=frame)
    if frame%FPS==0:print('SKYFALL_BAKE',frame,flush=True)
for arm,asset,base,loop,intro,bake in plans:
    for curve in curves(bake):
        for key in curve.keyframe_points:key.interpolation='LINEAR'
cam=scene.camera;cam.data.type='PERSP';cam.data.lens=35
knots=[(3,(-70,95,88),(0,0,17)),(5,(32,32,35),(25,22,30)),
       (6,(22.5,22.5,32),(22.5,22.5,28)),(7,(22.5,22.5,27.8),(17,26.5,26.5)),
       (8,(15.5,26.5,27.8),(14,26.5,26.5)),(9.5,(14,26.5,32),(25,22.5,31)),
       (11,(25,18,32),(25,22.5,31)),(13,(34,12,35),(25,22.5,28))]
for frame in range(1,LAST+1):
    t=(frame-1)/FPS
    if t<=3:
        angle=math.atan2(-95,70)+math.pi*t/3;radius=math.hypot(70,95)
        position=Vector((radius*math.cos(angle),radius*math.sin(angle),88));focus=Vector((0,0,17))
    else:
        index=next(i for i in range(len(knots)-1) if knots[i][0]<=t<=knots[i+1][0])
        a,b=knots[index:index+2];u=(t-a[0])/(b[0]-a[0]);u=u*u*(3-2*u)
        position=Vector(a[1]).lerp(Vector(b[1]),u);focus=Vector(a[2]).lerp(Vector(b[2]),u)
    position.z+=elevation;focus.z+=elevation
    cam.location=position;direction=focus-position
    cam.rotation_mode='QUATERNION';cam.rotation_quaternion=direction.to_track_quat('-Z','Y')
    cam.keyframe_insert('location',frame=frame);cam.keyframe_insert('rotation_quaternion',frame=frame)
scene.frame_set(1)
report=dict(duration_s=13,fps=FPS,frames=LAST,native_loop_rigs=loop_count,attachment='native rigged sockets; identity payload axes',camera='180 degree assembly view followed by continuous drone route through rooftop drop hole and jump-pad ascent')
(HERE/'skyfall_showcase_report.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'skyfall_showcase.blend'),compress=True)
print('SKYFALL_SHOWCASE',json.dumps(report),flush=True)
if '--no-render' not in sys.argv:
    scene.render.image_settings.media_type='VIDEO';scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='HIGH'
    scene.render.filepath=str(HERE/'skyfall_showcase.mp4');bpy.ops.render.render(animation=True)
