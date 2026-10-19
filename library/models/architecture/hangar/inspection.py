"""Render hinge/drive details and the walkable interior; never save the scene."""
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
    cam.data.type='ORTHO';cam.data.ortho_scale=3.4
    cam.location=dimensions.point(HERE.name,(0,-10,1.56));target=dimensions.point(HERE.name,(0,-4.9,1.56))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    v.aim_lights(lights,cam)
    scene.render.filepath=str(HERE/'hangar_door_detail.png')
    bpy.ops.render.render(write_still=True)
    cam.data.ortho_scale=3.4;cam.location=dimensions.point(HERE.name,(0,8,2.18));target=dimensions.point(HERE.name,(0,5.1,2.18))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    v.aim_lights(lights,cam)
    scene.render.filepath=str(HERE/'hangar_rear_detail.png')
    bpy.ops.render.render(write_still=True)
    cam.data.type='PERSP';cam.data.lens=65
    cam.location=dimensions.point(HERE.name,(.7,-2.0,1.75))
    report=json.loads((HERE/'hangar_rig.json').read_text())
    target=Vector(next(j['pivot'] for j in report['joints'] if j['bone']=='RightDoor'))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    v.aim_lights(lights,cam)
    scene.render.filepath=str(HERE/'hangar_hinge_detail.png')
    bpy.ops.render.render(write_still=True)
    rig=next(o for o in scene.objects if o.type=='ARMATURE')
    v.apply_pose(rig,json.loads(rig['preview_poses'])['open'])
    cam.data.lens=22;cam.location=dimensions.point(HERE.name,(0,-4.55,1.78));target=dimensions.point(HERE.name,(0,4.80,2.05))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.lights.new('LGT_InteriorInspection','AREA')
    data.energy=450;data.shape='RECTANGLE';data.size=3;data.size_y=.8
    obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj)
    obj.location=dimensions.point(HERE.name,(0,.60,4.04))
    scene.render.filepath=str(HERE/'hangar_interior.png')
    bpy.ops.render.render(write_still=True)

if __name__=='__main__':main()
