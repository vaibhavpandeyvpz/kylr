"""Render joint seats and support ends close up, without altering the build."""
import json
import sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview

preview.open_model();preview.setup_render()
cam=preview.create_camera();lights=preview.create_lights()
views={
    'shoulder_joint':([- .23,-.25,.925],[.23,.25,1.115],'front_left'),
    'brace_joints':([-.52,-.54,.335],[.52,.54,.55],'front_left'),
    'foot_joint':([-.10,-.78,0],[.10,-.60,.15],'front_left'),
    'instrument_flange':([.30,-.08,2.08],[.46,.08,2.33],'front_left'),
    'mast_instruments':([-.16,-.31,1.12],[.30,.15,1.95],'rear_right'),
    'dish_rear_seat':([-.13,-.20,2.18],[.13,.12,2.30],'rear_right'),
}
for name,(lo,hi,view) in views.items():
    bpy.context.scene['preview_frame']=json.dumps(dict(lo=lo,hi=hi))
    preview.render_view(cam,lights,view,suffix='detail_'+name)
