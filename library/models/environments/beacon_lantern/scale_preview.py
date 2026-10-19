"""Render the static beacon lantern beside Tensor, without saving either.

Run Blender 5.2 headless from library/ after model.py and Tensor's model.py.
The comparison includes Tensor's existing body, default head and actual rig;
no rescaling, generated animation or exported stand-in geometry is involved.
"""
import sys
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview

preview.open_model()
tensor=HERE.parents[1]/'characters/tensor/tensor.blend'
with bpy.data.libraries.load(str(tensor),link=False) as (src,dst):
    dst.objects=[name for name in src.objects if name in
                 ('SK_Tensor','SK_TensorHeadProjector','RIG_Tensor')]
objects=[obj for obj in dst.objects if obj]
assert len(objects)==3,'Build Tensor before rendering the scale comparison'
for obj in objects:
    bpy.context.scene.collection.objects.link(obj)
    obj.hide_render=False;obj.hide_set(False)
rig=next(obj for obj in objects if obj.type=='ARMATURE')
rig.location.x=1.02
rig.animation_data_clear()
for pb in rig.pose.bones:
    pb.location=(0,0,0);pb.rotation_quaternion=(1,0,0,0)
    pb.rotation_euler=(0,0,0);pb.scale=(1,1,1)
preview.setup_render()
cam=preview.create_camera();lights=preview.create_lights()
preview.render_view(cam,lights,'front',suffix='tensor_scale_front')
preview.render_view(cam,lights,'front_left',suffix='tensor_scale_front_left')
