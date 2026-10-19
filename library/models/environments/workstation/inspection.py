"""Reference-angle beauty and actual Tensor scale comparison; preview only."""
import sys
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview


def main():
    preview.open_model();preview.setup_render()
    preview.VIEWS['hero']=((1,-1,.65),'PERSP',(1280,1280))
    cam=preview.create_camera();lights=preview.create_lights()
    preview.render_view(cam,lights,'hero')
    tensor=HERE.parents[1]/'characters/tensor/tensor.blend'
    if not tensor.exists():
        raise FileNotFoundError('Build Tensor before rendering the scale comparison')
    with bpy.data.libraries.load(str(tensor),link=False) as (src,dst):
        dst.objects=[n for n in ('RIG_Tensor','SK_Tensor','SK_TensorHeadProjector') if n in src.objects]
    assert len(dst.objects)==3
    for obj in dst.objects:
        bpy.context.scene.collection.objects.link(obj)
        obj.hide_render=False;obj.hide_set(False)
    rig=next(o for o in dst.objects if o.type=='ARMATURE')
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    rig.location.x=1.30
    preview.VIEWS['scale']=((0,-1,.12),'ORTHO',(1920,1080))
    preview.render_view(cam,lights,'scale')


if __name__=='__main__':main()
