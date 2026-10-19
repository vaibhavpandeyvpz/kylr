"""Studio detail views of the fitted load path and functional components."""
import json,sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview
preview.open_model();preview.setup_render()
cam=preview.create_camera();lights=preview.create_lights()
for name,(lo,hi,view) in {
    'guard_root':([.22,-.36,.08],[.36,-.22,.30],'front_left'),
    'yoke_alignment':([.11,-.12,.21],[.24,.20,.565],'left'),
    'trunnion':([.10,-.045,.41],[.24,.145,.56],'front_left'),
    'foot_flange':([.10,-.11,.21],[.23,.16,.29],'front_left'),
    'coolant':([-.10,.23,.44],[.10,.35,.57],'rear_right'),
    'display':([.06,.11,.47],[.10,.23,.54],'left'),
    'accelerator':([-.11,-.45,.41],[.11,-.02,.61],'front_left'),
    'actuator':([-.055,-.325,.19],[.055,-.08,.46],'front_left'),
}.items():
    bpy.context.scene['preview_frame']=json.dumps(dict(lo=lo,hi=hi))
    preview.render_view(cam,lights,view,suffix='detail_'+name)

