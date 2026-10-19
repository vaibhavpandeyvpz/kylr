"""Render the habitat pod beside the authored Tensor, without saving either.

Run Blender 5.2 headless from library/ after model.py and Tensor's model.py.
The comparison includes Tensor's existing body, default head and actual rig;
no rescaling, generated animation or exported stand-in geometry is involved.
"""
import sys,json
from pathlib import Path

import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview
sys.path.insert(0,str(HERE.parent))
import dimensions

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
rig.location.x=2.7
rig.animation_data_clear()
for pb in rig.pose.bones:
    pb.location=(0,0,0);pb.rotation_quaternion=(1,0,0,0)
    pb.rotation_euler=(0,0,0);pb.scale=(1,1,1)
preview.apply_pose(rig,json.loads(rig['preview_poses'])['idle'])
preview.setup_render()
cam=preview.create_camera();lights=preview.create_lights()
preview.render_view(cam,lights,'front',suffix='tensor_scale_front')
preview.render_view(cam,lights,'front_left',suffix='tensor_scale_front_left')
pod=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE' and o!=rig)
preview.apply_pose(pod,json.loads(pod['preview_poses'])['open'])
rig.location=(0,-1.2,.75*dimensions.HEIGHT[HERE.name])
bpy.context.view_layer.update()
points=[]
dg=bpy.context.evaluated_depsgraph_get()
for obj in objects:
    if obj.type!='MESH':continue
    ev=obj.evaluated_get(dg);me=ev.to_mesh()
    points.extend(ev.matrix_world@v.co for v in me.vertices);ev.to_mesh_clear()
lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
assert max(abs(lo[0]),abs(hi[0]))<.60,(lo,hi)
assert hi[2]<2.86*dimensions.HEIGHT[HERE.name] and lo[2]>=.75*dimensions.HEIGHT[HERE.name]-.001,(lo,hi)
for p in points:
    source_z=p.z/dimensions.HEIGHT[HERE.name]-.20
    width=.60-max(0,.68-source_z,source_z-2.53)
    assert abs(p.x)<width,(tuple(p),width)
(HERE/'habitat_pod_scale_report.json').write_text(json.dumps(dict(tensor_idle_bounds_m=dict(lo=lo,hi=hi),
    threshold_m=.75*dimensions.HEIGHT[HERE.name],header_clearance_m=2.86*dimensions.HEIGHT[HERE.name]-hi[2],passed=True),indent=2))
preview.render_view(cam,lights,'front',suffix='tensor_entry_front')
preview.render_view(cam,lights,'front_left',suffix='tensor_entry_front_left')
