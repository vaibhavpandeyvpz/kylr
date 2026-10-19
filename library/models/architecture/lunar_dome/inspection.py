"""Reproducible elevated hero and interface close-ups using the studio renderer."""
import importlib.util
import json
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('dome_preview',HERE/'preview.py')
preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)
DETAILS={
    'hero':([-3,-3,0],[3,3,3.16],(1,-1,.70)),
    'hatch':([-.75,-3.02,0],[.75,-2.15,2.3],(.35,-1,.35)),
    'glazing_seats':([1.25,-2.6,.35],[2.7,-.9,2.25],(1,-1,.50)),
    'crown':([-1,-1,2.75],[1,1,3.20],(1,-1,1)),
    'foundation':([1,-2.5,0],[2.8,-.8,.9],(1,-1,.4)),
}
preview.open_model();preview.setup_render()
camera=preview.create_camera();lights=preview.create_lights()
for name,(lo,hi,direction) in DETAILS.items():
    bpy.context.scene['preview_frame']=json.dumps({'lo':lo,'hi':hi})
    view='inspection_'+name
    preview.VIEWS[view]=(direction,'PERSP',preview.CINEMATIC_RES)
    preview.render_view(camera,lights,view,'detail_'+name)
print('[lunar_dome] elevated hero and four interface close-ups rendered',flush=True)
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
preview.apply_pose(rig,json.loads(rig['preview_poses'])['open'])
bpy.context.scene['preview_frame']=json.dumps({'lo':[-3,-4.2,0],'hi':[3,3,3.16]})
preview.render_view(camera,lights,'front_left','door_open')
