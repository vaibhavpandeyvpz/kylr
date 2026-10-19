"""Reference-facing hero, dark emission and detail stills for static lights.

Preview-only cameras, bloom and studio lighting never enter the exports.
Run headless Blender 5.2 --python models/environments/light_inspection.py.
"""
import importlib.util
import json
import sys
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
NAMES=('batten_light','sconce_light','pole_light')


def inspect(name):
    spec=importlib.util.spec_from_file_location('fixture_preview',HERE/name/'preview.py')
    preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)
    preview.open_model();preview.setup_render()
    scene=bpy.context.scene
    direction=(1,-1,-.65) if name=='batten_light' else (1,-1,.35)
    preview.VIEWS['hero']=(direction,'PERSP',(1280,1280))
    cam=preview.create_camera();lights=preview.create_lights()
    preview.render_view(cam,lights,'hero')
    if name=='pole_light':
        scene['preview_frame']=json.dumps({'lo':[-1.325,-.20,3.30],'hi':[1.325,.20,4.20]})
        preview.render_view(cam,lights,'hero','head_detail')
        del scene['preview_frame']
    # Dark studio + restrained bloom demonstrates the exported emission.
    # No preview SpotLight is used: the emitter is the material itself.
    for node in scene.world.node_tree.nodes:
        if node.type=='BACKGROUND':node.inputs['Strength'].default_value=.025
    for key,(offset,energy) in preview.LIGHTS.items():
        preview.LIGHTS[key]=(offset,energy*.065)
    group=bpy.data.node_groups.new('LuminairePreviewGlow','CompositorNodeTree')
    group.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
    scene.compositing_node_group=group
    source=group.nodes.new('CompositorNodeRLayers')
    glare=group.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value='Fog Glow'
    glare.inputs['Quality'].default_value='High'
    if 'Threshold' in glare.inputs:glare.inputs['Threshold'].default_value=1.2
    output=group.nodes.new('NodeGroupOutput')
    group.links.new(source.outputs['Image'],glare.inputs['Image'])
    group.links.new(glare.outputs['Image'],output.inputs['Image'])
    preview.render_view(cam,lights,'hero','emission')


if __name__=='__main__':
    names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else NAMES
    for name in names:
        assert name in NAMES,name
        inspect(name)
