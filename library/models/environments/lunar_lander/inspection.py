"""Reproducible close-up studio inspection of the lander's mechanical interfaces.

Run headless from library after model.py; renders PNGs without saving the blend.
Uses the unchanged generic preview renderer and its studio.
"""
import importlib.util
import json
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('lander_inspection_preview',HERE/'preview.py')
preview=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

DETAILS={
    'upper_joint':([.86,-1.50,1.75],[1.55,-.90,2.40],(1,-1,.35)),
    'upper_pin':([.86,-1.50,1.75],[1.55,-.90,2.40],(1,1,.25)),
    'foot_joint':([1.80,-2.50,0],[2.50,-1.75,.60],(1,-1,.35)),
    'foot_pin':([1.80,-2.50,0],[2.50,-1.75,.60],(1,1,.25)),
    'hatch':([-.70,-1.85,2.55],[.70,-1.05,4.35],(1,-1,.35)),
    'ladder_shoes':([-.55,-2.35,0],[.55,-1.88,.45],(1,-1,.50)),
    'antenna':([-.40,-.35,4.50],[.50,.40,5.0],(1,-1,.45)),
}


def main():
    preview.open_model()
    preview.setup_render()
    cam,lights=preview.create_camera(),preview.create_lights()
    for name,(lo,hi,direction) in DETAILS.items():
        bpy.context.scene['preview_frame']=json.dumps({'lo':lo,'hi':hi})
        view='inspection_'+name
        preview.VIEWS[view]=(direction,'PERSP',preview.CINEMATIC_RES)
        preview.render_view(cam,lights,view,'detail_'+name)
    print('[lunar_lander] close-up interface views rendered',flush=True)


if __name__=='__main__':
    main()
