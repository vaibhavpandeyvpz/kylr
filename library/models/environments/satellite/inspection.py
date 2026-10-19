"""Studio closeups of the physical connector interfaces, no scene writes."""
import json
import sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview
preview.VIEWS['front_right']=((-1,-1,.35),'PERSP',preview.CINEMATIC_RES)

preview.open_model();preview.setup_render()
cam=preview.create_camera();lights=preview.create_lights()
boxes={
    'foot_clevis':([.91,-.63,.10],[1.29,-.31,.43]),
    'tower_flange':([.92,.03,.08],[1.30,.50,.38]),
    'shoulder_clevis':([.91,-.015,1.20],[1.29,.23,1.49]),
    'diagonal_socket':([.74,.11,.19],[1.18,.41,.50]),
    'feed_foot':([-.13,-.24,2.78],[.13,-.04,3.02]),
    'receiver_sockets':([-.19,-.93,1.80],[.19,-.63,2.21]),
    'bearing_drive':([.93,.03,1.80],[1.48,.50,2.23]),
}
for name,(lo,hi) in boxes.items():
    bpy.context.scene['preview_frame']=json.dumps(dict(lo=lo,hi=hi))
    preview.render_view(cam,lights,'front_right' if name=='diagonal_socket' else 'front_left',suffix='inspection_'+name)
