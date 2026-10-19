"""Render manufactured assemblies close enough to inspect their seating."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import dimensions
sys.path.insert(0,str(HERE))
import preview
if '--reference' in sys.argv:
    preview.BLEND_PATH=Path(sys.argv[sys.argv.index('--reference')+1])
preview.open_model();preview.setup_render()
cam=preview.create_camera();lights=preview.create_lights()
views=[]
for s in (-1,1):
    for y in (-.70,.70):
        bounds=([.65,y-.19,.03],[1.89,y+.27,.63]) if s>0 else ([-1.89,y-.19,.03],[-.65,y+.27,.63])
        views.append((f'landing_{s}_{y}',*bounds,(s,-1,-.06)))
        views.append((f'hydraulic_{s}_{y}',*bounds,(s,1,-.06)))
views += [('services',[1.70,-.83,1.28],[1.99,.85,2.65],(1,-.40,.2)),
          ('hatch',[-.82,-1.94,.62],[.82,-1.65,2.99],(.4,-1,.15)),
          ('crown',[-.50,-.69,3.47],[.50,.69,3.70],(1,-1,1))]
for name,lo,hi,direction in views:
    lo,hi=dimensions.point(HERE.name,lo),dimensions.point(HERE.name,hi);center=(lo+hi)*.5
    box=[Vector((x,y,z)) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]
    preview.orient_camera(cam,direction)
    preview.frame_camera(cam,center,box,direction,'PERSP',(1280,960),1.08)
    preview.aim_lights(lights,cam)
    scene=bpy.context.scene;scene.render.resolution_x=1280;scene.render.resolution_y=960
    scene.render.filepath=str(HERE/f'habitat_pod_detail_{name}.png')
    bpy.ops.render.render(write_still=True)
