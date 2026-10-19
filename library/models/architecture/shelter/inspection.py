"""Close views of both corrected canopy joints, centred header and service hinge."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import preview as studio

def main():
    studio.open_model();studio.setup_render();scene=bpy.context.scene
    cam=studio.create_camera();lights=studio.create_lights()
    scene.render.resolution_x=1280;scene.render.resolution_y=1024
    cam.data.type='PERSP';cam.data.lens=70
    views={'front_joint':((3.15,-3.2,3.55),(1.57,-.79,2.94)),
           'rear_joint':((3.5,3.15,3.65),(1.58,1.67,2.96)),
           'header':((0,-4.25,2.91),(0,-.99,2.91)),
           'hinge':((-.85,3.2,1.7),(-.29,1.91,1.48))}
    for tag,(at,target) in views.items():
        cam.location=at;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
        studio.aim_lights(lights,cam);scene.render.filepath=str(HERE/f'shelter_detail_{tag}.png')
        bpy.ops.render.render(write_still=True)

if __name__=='__main__':main()
