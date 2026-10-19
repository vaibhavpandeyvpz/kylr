"""Metre-based architecture sizing, baked into procedural geometry and rigs.

Authoring frames preserve common door cartridges. Equal X/Y scaling commutes
with vertical hinges; Z scaling commutes with their rotation and slide travel.
Object scales remain one. Collision builders use these same frames.
"""
from mathutils import Matrix, Vector

SINGLE_MAX = (1.5, 2.1)
DOUBLE_STANDARD = (2.0, 2.1)
INTERIOR_MAX = 3.0

# Authoring geometry is resized before the existing physical audits/export.
# Do not scale Tensor or relax any contact/motion/triangle validation.
HEIGHT = dict(bunker=2.1/2.298, hangar=3/4.03, cistern=2.1/2.7,
              laboratory=3/3.76, bastion=3/3.76, lodge=3/3.88,
              hub=3/3.72, habitat_pod=2.1/2.11,
              shelter=1.0, container=2.1/2.231, container_long=2.1/2.231,
              lunar_dome=1.0)
PLAN = dict(container=2/2.158, container_long=2/2.158, lunar_dome=1.0)


def matrix(name):
    xy = PLAN.get(name, 1.0)
    if name == 'lunar_dome':
        assert abs(xy-HEIGHT[name])<1e-9, 'The hemisphere requires uniform XYZ scaling'
    return Matrix.Diagonal((xy, xy, HEIGHT[name], 1.0))


def point(name, value):
    return matrix(name) @ Vector(value)


def require_land(part, point, normal):
    """Double-precision planar support test, avoiding Blender float BVH drift."""
    def sub(a,b):return tuple(float(a[i])-float(b[i]) for i in range(3))
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    axis=tuple(Vector(normal).normalized())
    for face in part.faces:
        a,b,c=(part.verts[i] for i in face[:3])
        u,v,q=sub(b,a),sub(c,a),sub(point,a)
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        length=dot(n,n)**.5
        if length<1e-10:continue
        n=tuple(x/length for x in n)
        if abs(dot(n,q))>1e-5 or abs(dot(n,axis))<.999:continue
        uu,uv,vv,uq,vq=dot(u,u),dot(u,v),dot(v,v),dot(u,q),dot(v,q)
        denominator=uu*vv-uv*uv
        if denominator<1e-15:continue
        s,t=(vv*uq-uv*vq)/denominator,(uu*vq-uv*uq)/denominator
        if s>=-1e-6 and t>=-1e-6 and s+t<=1+1e-6:return
    raise AssertionError(('unsupported flange corner',part.line,tuple(point)))


def entry_frame(anchor, xy, z=1.0):
    anchor = Vector(anchor)
    return Matrix.Translation(anchor) @ Matrix.Diagonal((xy, xy, z, 1)) @ Matrix.Translation(-anchor)


def value(name, bone, number, joints):
    joint = joints[bone]
    if joint.kind != 'slide': return number
    return number * (matrix(name).to_3x3() @ joint.axis).length


def bake(name, kit, k, joints, rig):
    """Resize the source parts and rebuild the physical rig before checks."""
    import bpy
    resize = matrix(name)
    for v in k.bm.verts: v.co = resize @ v.co
    k.bm.normal_update()
    k.parts = [p.moved(resize) for p in k.parts]
    for joint in joints.values():
        joint.pivot = resize @ joint.pivot
        if joint.kind == 'hinge':
            assert abs(joint.axis.z) > .999, 'Sizing requires vertical door hinges'
        elif joint.kind == 'slide':
            distance = (resize.to_3x3() @ joint.axis).length
            joint.axis = (resize.to_3x3() @ joint.axis).normalized()
            joint.dir = joint.axis.copy()
            joint.limits = tuple(v * distance for v in joint.limits)
    kit.ANIMATIONS = {name_: (loop, mode, {bn: [(f, value(name, bn, v, joints)) for f, v in keys]
        for bn, keys in tracks.items()}) for name_, (loop, mode, tracks) in kit.ANIMATIONS.items()}
    bpy.data.objects.remove(rig, do_unlink=True)
    rig = kit.build_rig(joints, [])
    rig['architecture_asset'] = name
    return rig


def scale_tracks(animations, factors):
    return {name: (loop, mode, {bn: [(f, v*factors.get(bn,1)) for f,v in keys]
        for bn,keys in tracks.items()}) for name,(loop,mode,tracks) in animations.items()}


def preview(name, rig, joints):
    import json
    if 'preview_poses' in rig:
        data=json.loads(rig['preview_poses'])
        poses(name,data,joints)
        for pose in data.values():
            for bone,channels in pose.items():
                if 'loc' not in channels:continue
                factor=1
                if name in ('cistern','lodge') and 'Lock' in bone:factor=.75
                if name in ('hangar','laboratory') and 'Bolt' in bone:
                    factor=(2.1/3.48)/HEIGHT[name]
                if name=='bastion' and bone=='Lock':factor=(2.1/2.9)/HEIGHT[name]
                channels['loc']=[v*factor for v in channels['loc']]
        rig['preview_poses']=json.dumps(data)


def poses(name, data, joints):
    for pose in data.values():
        for bone, channels in pose.items():
            if 'loc' in channels:
                channels['loc'] = [v * (matrix(name).to_3x3() @ joints[bone].axis).length for v in channels['loc']]
    return data


def report(name, data, *, width, height, floors, ceilings, double=False):
    """Add the delivered, surface-to-surface dimensions; reject bad specs."""
    xy, z = PLAN.get(name, 1), HEIGHT[name]
    actual_width, actual_height = width*xy, height*z
    assert actual_width <= (DOUBLE_STANDARD[0] if double else SINGLE_MAX[0]) + 1e-6
    assert actual_height <= SINGLE_MAX[1] + 1e-6
    rooms = [dict(floor_m=f*z, ceiling_m=c*z, height_m=(c-f)*z) for f,c in zip(floors,ceilings)]
    assert all(0 < room['height_m'] <= INTERIOR_MAX+1e-6 for room in rooms)
    data['architecture_dimensions'] = dict(door_type='double' if double else 'single',
        opening_width_m=actual_width, opening_height_m=actual_height, rooms=rooms,
        measurement='Open structural aperture; floor top to ceiling underside; chamfers reduce local clearance')
    if 'passage_m' in data:
        data['passage_m'].update(width=actual_width, height=actual_height)
        for key in ('threshold','interior_height'):
            if key in data['passage_m']: data['passage_m'][key] *= z
    if 'entrance' in data:
        data['entrance'].update(width_m=actual_width,height_m=actual_height)
        for key in ('floor_m','ceiling_m'):
            if key in data['entrance']: data['entrance'][key] *= z
    if 'upper_floor_m' in data: data['upper_floor_m']['elevation'] *= z
    if 'cargo_lift_m' in data:
        for key in ('travel','lower','upper'): data['cargo_lift_m'][key] *= z
    if 'dimensions_m' in data:
        for key in ('width','depth'): data['dimensions_m'][key] *= xy
        data['dimensions_m']['height'] *= z
    if 'floor_slab_m' in data: data['floor_slab_m']['height'] *= z
    if 'deck_height_m' in data:data['deck_height_m']*=z
    if 'clear_door_m' in data:data['clear_door_m']=[actual_width,actual_height]
