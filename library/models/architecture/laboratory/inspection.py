"""Studio detail and cutaway inspection, never saved or exported."""
import json
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import preview as studio
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import dimensions

def cutaway():
    """Remove the front wall and roof from preview copies of fixed assemblies."""
    originals=[];copies=[]
    for obj in list(bpy.context.scene.objects):
        if obj.type!='MESH' or not obj.name.startswith('SK_') or obj.name.endswith('Mechanisms'):continue
        new=obj.copy();new.data=obj.data.copy();new.name='Inspection_'+obj.name
        bpy.context.scene.collection.objects.link(new)
        bm=bmesh.new();bm.from_mesh(new.data)
        gone=[f for f in bm.faces if (min(v.co.z for v in f.verts)>7.68*dimensions.HEIGHT[HERE.name]) or
             (max(v.co.y for v in f.verts)<-6.25 and min(v.co.z for v in f.verts)>.321*dimensions.HEIGHT[HERE.name])]
        bmesh.ops.delete(bm,geom=gone,context='FACES_ONLY')
        bm.to_mesh(new.data);bm.free();obj.hide_render=True
        originals.append(obj);copies.append(new)
    return originals,copies

def inspection_lights():
    for z in (3.8,7.1):
        data=bpy.data.lights.new('LGT_InteriorInspection','AREA');data.energy=1400;data.size=5
        obj=bpy.data.objects.new(data.name,data);bpy.context.scene.collection.objects.link(obj);obj.location=dimensions.point(HERE.name,(0,1,z))

def view(cam,lights,name,at,target,lens=45):
    at=dimensions.point(HERE.name,at);target=dimensions.point(HERE.name,target)
    cam.data.type='PERSP';cam.data.lens=lens;cam.location=at
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    studio.aim_lights(lights,cam)
    bpy.context.scene.render.filepath=str(HERE/f'laboratory_{name}.png')
    bpy.ops.render.render(write_still=True)

def main():
    studio.open_model();studio.setup_render()
    scene=bpy.context.scene;scene.render.resolution_x=1600;scene.render.resolution_y=1100
    cam=studio.create_camera();lights=studio.create_lights();rig=next(o for o in scene.objects if o.type=='ARMATURE')
    view(cam,lights,'door_detail',(3.7,-12.5,3.3),(0,-6.75,2.1),55)
    view(cam,lights,'entrance_slope',(2.5,-10.0,1.6),(0,-7.15,.50),55)
    view(cam,lights,'rear_corner',(14,18,6.4),(6.4,6.4,5.45),65)
    studio.apply_pose(rig,json.loads(rig['preview_poses'])['open'])
    inspection_lights()
    view(cam,lights,'interior',(0,-6.5,1.94),(0,4.0,2.0),20)
    cutaway()
    view(cam,lights,'cutaway_lower',(17,-22,19),(0,0,3.2),45)
    view(cam,lights,'lift_lower',(6,-2,4.0),(0,5.4,2.5),45)
    studio.apply_pose(rig,json.loads(rig['preview_poses'])['lift_upper'])
    view(cam,lights,'cutaway_upper',(17,-22,19),(0,0,3.2),45)
    view(cam,lights,'lift_upper',(6,-2,7.0),(0,5.4,5.0),45)

if __name__=='__main__':main()
