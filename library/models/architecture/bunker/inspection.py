"""Close studio views of physical hinge seating and the traversable room.
Preview lights are inspection illumination only; no scene is saved.
"""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import dimensions
sys.path.insert(0,str(HERE))
import preview as v

def main():
    v.open_model();v.setup_render();cam=v.create_camera();lights=v.create_lights()
    scene=bpy.context.scene
    scene.render.resolution_x=1280;scene.render.resolution_y=1280
    cam.data.type='PERSP';cam.data.lens=70
    cam.location=dimensions.point(HERE.name,(-2.45,-5.4,1.62));target=dimensions.point(HERE.name,(-.80,-3.20,1.27))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    v.aim_lights(lights,cam)
    scene.render.filepath=str(HERE/'bunker_hinge_detail.png')
    bpy.ops.render.render(write_still=True)
    rig=next(o for o in scene.objects if o.type=='ARMATURE')
    v.apply_pose(rig,json.loads(rig['preview_poses'])['open'])
    cam.data.lens=22;cam.location=dimensions.point(HERE.name,(0,-2.75,1.62));target=dimensions.point(HERE.name,(0,2.20,1.45))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.lights.new('LGT_InteriorInspection','AREA')
    data.energy=180;data.shape='RECTANGLE';data.size=2.0;data.size_y=.4
    obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj)
    obj.location=dimensions.point(HERE.name,(0,.30,3.1))
    scene.render.filepath=str(HERE/'bunker_interior.png')
    bpy.ops.render.render(write_still=True)

if __name__=='__main__':main()
