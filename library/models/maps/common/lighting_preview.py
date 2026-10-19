"""Native projected-light beams for Blender, matching authored Godot specs."""
import bpy,math
from mathutils import Matrix

def install(asset,objects,metadata,hidden=False):
    if asset=='jumbotron':
        beams=[dict(name=s['gizmo'],cone_half_angle_deg=s['cone_half_angle_deg'],range_m=s['range_m']) for s in metadata['spots']];power=6000
    elif asset in ('sconce_light','batten_light','pole_light'):
        beams=[g for g in metadata['gizmos'] if g['name'].startswith('LightProjection')]
        power={'sconce_light':60,'batten_light':120,'pole_light':500}[asset]
    else:return []
    lights=[]
    for beam in beams:
        mount=next(o for o in objects if o.name.split('.')[0]==beam['name'])
        data=bpy.data.lights.new('LGT_Native_'+asset,'SPOT');data.energy=power;data.color=(.86,.94,1)
        data.spot_size=math.radians(2*beam['cone_half_angle_deg']);data.spot_blend=.6;data.shadow_soft_size=.08
        data.use_custom_distance=True;data.cutoff_distance=beam['range_m']
        light=bpy.data.objects.new('LGT_Native_'+asset,data);bpy.context.scene.collection.objects.link(light)
        light.parent=mount;light.matrix_parent_inverse=Matrix.Identity(4)
        # Blender light -Z aligns to the native source gizmo +Y; the exporter
        # maps that source forward axis to Godot -Z.
        light.matrix_basis=Matrix.Rotation(math.pi/2,4,'X');light.hide_render=hidden;lights.append(light)
    return lights
