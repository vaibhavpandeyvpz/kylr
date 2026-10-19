"""Continuous native-door and cargo-shaft fly-by in Blender world coordinates."""
import math
from mathutils import Vector

def author(scene,fps=24,last=312):
    camera=scene.camera;camera.animation_data_clear();camera.data.type='PERSP';camera.data.lens=35
    knots=[(3,(-55,65,52),(0,0,2)),(5,(16,16,1.5),(24,24,1.5)),
        (6,(22,22,1.5),(27.15,27.15,1.5)),(7,(27.15,27.15,1.8),(24,24,1.8)),
        (8,(27.15,27.15,4.8),(24,20,4.5)),(9,(24,20,4.8),(24.4,17.25,4.2)),
        (10,(27.15,27.15,4.8),(24,24,4.2)),(11,(27.15,27.15,1.8),(19,19,1.5)),
        (12,(19,19,1.5),(0,0,4)),
        (13,(-12,-12,10),(-24,-24,3))]
    for frame in range(1,last+1):
        t=(frame-1)/fps
        if t<=3:
            angle=math.atan2(-65,55)+math.pi*t/3;radius=math.hypot(55,65)
            position=Vector((radius*math.cos(angle),radius*math.sin(angle),52));focus=Vector((0,0,2))
        else:
            index=next(i for i in range(len(knots)-1) if knots[i][0]<=t<=knots[i+1][0])
            a,b=knots[index:index+2];u=(t-a[0])/(b[0]-a[0]);u=u*u*(3-2*u)
            position=Vector(a[1]).lerp(Vector(b[1]),u);focus=Vector(a[2]).lerp(Vector(b[2]),u)
        camera.location=position;camera.rotation_mode='QUATERNION';camera.rotation_quaternion=(focus-position).to_track_quat('-Z','Y')
        camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_quaternion',frame=frame)
