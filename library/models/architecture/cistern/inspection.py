"""Studio interface close-ups and lunar context, never written into the asset."""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import dimensions
sys.path.insert(0,str(HERE))
import preview

def lunar_ground():
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001))
    ground=bpy.context.object;ground.name='PRV_LunarSurface'
    mat=bpy.data.materials.new('PRV_Regolith');mat.diffuse_color=(.14,.14,.145,1)
    node=mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=(.14,.14,.145,1);node.inputs['Roughness'].default_value=.97
    noise=mat.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=55
    coord=mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mat.node_tree.links.new(coord.outputs['Object'],noise.inputs['Vector'])
    bump=mat.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.007;bump.inputs['Strength'].default_value=.25
    mat.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);mat.node_tree.links.new(bump.outputs['Normal'],node.inputs['Normal'])
    ground.data.materials.append(mat)
    # Low angular fragments sit on grade. No rock is part of the runtime asset.
    for i in range(36):
        a=i*2.39996;r=8.2+(i%7)*.65
        scale=.07+(i%5)*.035
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(r*math.cos(a),r*math.sin(a),0))
        rock=bpy.context.object;rock.name='PRV_RegolithFragment'
        rock.scale=(scale,scale*.73,scale*.42)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        rock.location.z=-min(v.co.z for v in rock.data.vertices)-.001
        rock.data.materials.append(mat)

def main():
    preview.open_model();preview.setup_render()
    cam=preview.create_camera();lights=preview.create_lights()
    details={
        'buttress_service':([-3.3,-7.6,0],[-1.2,-6.1,3.45],(-.35,-1,.25)),
        'hinges':([-1.4,-7.6,.1],[-.76,-7.15,2.83],(-.7,-1,.16)),
        'door':([-1.45,-7.55,0],[1.45,-6.8,3.12],(.3,-1,.26)),
        'roof_clamps':([3.6,-5.6,2.89],[6.5,-2.6,3.5],(.6,-1,1.1))}
    for name,(lo,hi,dir) in details.items():
        if name in ('hinges','door'):
            frame=dimensions.entry_frame((0,-7.30,.10),.75)
            lo,hi=frame@Vector(lo),frame@Vector(hi)
        lo,hi=list(dimensions.point(HERE.name,lo)),list(dimensions.point(HERE.name,hi))
        bpy.context.scene['preview_frame']=json.dumps(dict(lo=lo,hi=hi))
        preview.VIEWS[name]=(dir,'PERSP',(1600,1100))
        preview.render_view(cam,lights,name,'detail_'+name)
    lunar_ground()
    scene=bpy.context.scene
    cam.data.type='PERSP';cam.data.lens=52
    cam.location=dimensions.point(HERE.name,(16,-25,14));cam.rotation_euler=(dimensions.point(HERE.name,(0,0,1.4))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x=1920;scene.render.resolution_y=1080
    preview.aim_lights(lights,cam)
    scene.render.filepath=str(HERE/'cistern_lunar.png');bpy.ops.render.render(write_still=True)
    print('[cistern] four mechanical details and lunar-context beauty rendered',flush=True)

if __name__=='__main__':main()
