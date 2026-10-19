"""Reproducible close-up inspection; uses the unchanged studio renderer."""
import importlib.util
import json
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('rover_preview',HERE/'preview.py')
preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)
DETAILS={
    'hero':([-1,-1.5,0],[1,1.5,2.16],(1,-1,.70)),
    'suspension':([.38,-.10,.25],[.92,1.30,.88],(1,-1,.30)),
    'wheel_mount':([.55,-1.39,.15],[1.01,-.86,.65],(-.30,-1,.35)),
    'solar_sections':([.27,-1.51,.91],[1.01,.08,1.06],(1,-1,1.8)),
    'solar_supports':([-.99,-.63,.86],[.99,.63,1.14],(1,1,-.25)),
    'instruments':([-.55,-.20,.92],[.51,.59,2.18],(1,-1,.40)),
    'sampler':([-.51,-1.40,.31],[-.08,-.70,.81],(1,-1,.25)),
}
preview.open_model();preview.setup_render()
camera=preview.create_camera();lights=preview.create_lights()
for name,(lo,hi,direction) in DETAILS.items():
    bpy.context.scene['preview_frame']=json.dumps({'lo':lo,'hi':hi})
    view='inspection_'+name
    preview.VIEWS[view]=(direction,'PERSP',preview.CINEMATIC_RES)
    preview.render_view(camera,lights,view,'detail_'+name)
print('[lunar_rover] elevated hero and six mechanical close-ups rendered',flush=True)
