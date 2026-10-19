"""Check actual room surfaces and open doorways in Blender, GLB and FBX.

Run headless from library/. Optional -- --only asset ... limits the audit.
Report is generated under target/architecture_dimensions/.
"""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import dimensions

# Authoring-space entry sections and occupied room grids. Tensor stays at
# its original scale; these coordinates position probes, never resize them.
SECTIONS=dict(bunker=(-2.95,.12),hangar=(-4.88,.15),cistern=(-7.34,.10),
    laboratory=(-6.88,.32),bastion=(-6.64,.32),lodge=(-7.34,.10),
    hub=(-2.73,.12),habitat_pod=(-1.74,.75),lunar_dome=(-2.82,.10))
ROOM_GRID=dict(bunker=(1.2,1.2),hangar=(3,3),cistern=(4,4),
    laboratory=(4,1),bastion=(4,1),lodge=(4,4),hub=(.6,.6),
    habitat_pod=(.7,.7),container=(.4,.5),container_long=(.4,2),shelter=(1,.5),lunar_dome=(1.,1.))


def pose(rig, values):
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.location=(0,0,0);bone.rotation_mode='XYZ'
        bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)
        for constraint in list(bone.constraints):bone.constraints.remove(constraint)
    for name,channels in values.items():
        bone=rig.pose.bones[name]
        if 'rot' in channels:bone.rotation_euler=tuple(math.radians(v) for v in channels['rot'])
        if 'loc' in channels:bone.location=channels['loc']
    bpy.context.view_layer.update()


def geometry():
    vertices=[];triangles=[]
    deps=bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not obj.name.startswith('SK_') or 'Regolith' in obj.name:continue
        ev=obj.evaluated_get(deps);mesh=ev.to_mesh();mesh.calc_loop_triangles()
        offset=len(vertices);vertices.extend(ev.matrix_world@v.co for v in mesh.vertices)
        for face in mesh.loop_triangles:
            material=mesh.materials[face.material_index]
            if material and material.name=='M_Glass' and not obj.get('glazing_is_pressure_ceiling'):continue
            triangles.append(tuple(offset+i for i in face.vertices))
        ev.to_mesh_clear()
    assert triangles
    return BVHTree.FromPolygons(vertices,triangles,all_triangles=True)


def audit(name, report, tree):
    spec=report['architecture_dimensions']
    heights=[];samples=0
    rx,ry=ROOM_GRID[name]
    for room in spec['rooms']:
        floor=room['floor_m']
        for x in (-rx,0,rx):
            for y in (-ry,0,ry):
                if name in ('laboratory','bastion'):y-=2
                start=Vector((x,y,floor+.03))
                ceiling=tree.ray_cast(start,Vector((0,0,1)),10)[0]
                assert ceiling is not None,(name,'missing inside ceiling',tuple(start))
                height=ceiling.z-floor
                assert height<=dimensions.INTERIOR_MAX+.001,(name,'oversized room',height,tuple(start))
                assert height>=1.753+.02,(name,'Tensor headroom',height,tuple(start))
                heights.append(height);samples+=1
    opening=None
    if spec['door_type']!='open':
        if name.startswith('container'):
            y=-report['dimensions_m']['depth']/2+.04
            floor=spec['rooms'][0]['floor_m']
        else:
            y,z=SECTIONS[name];floor=z*dimensions.HEIGHT[name]
        start=Vector((0,y,floor+.03))
        header=tree.ray_cast(start,Vector((0,0,1)),5)[0]
        assert header is not None,(name,'missing doorway header')
        height=header.z-floor
        assert height<=dimensions.SINGLE_MAX[1]+.001,(name,'oversized doorway height',height)
        # Probe at torso height so chamfers at the sill/header cannot hide a
        # door-sized opening in the surrounding pressure wall.
        start.z=floor+1
        left=tree.ray_cast(start,Vector((-1,0,0)),10)[0]
        right=tree.ray_cast(start,Vector((1,0,0)),10)[0]
        assert left is not None and right is not None,(name,'missing doorway jamb')
        width=right.x-left.x
        maximum=dimensions.DOUBLE_STANDARD[0] if spec['door_type']=='double' else dimensions.SINGLE_MAX[0]
        assert width<=maximum+.001,(name,'oversized doorway width',width)
        assert width>=.64+.04 and height>=1.753+.02,(name,'Tensor aperture',width,height)
        opening=dict(width_m=width,height_m=height)
    return dict(asset=name,room_samples=samples,maximum_inside_height_m=max(heights),opening=opening)


def main():
    names=sorted(ROOM_GRID)
    if '--only' in sys.argv:names=sys.argv[sys.argv.index('--only')+1:]
    results=[]
    for name in names:
        folder=HERE/name
        report=json.loads((folder/f'{name}_rig.json').read_text())
        bpy.ops.wm.open_mainfile(filepath=str(folder/f'{name}.blend'))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        poses=json.loads(rig.get('preview_poses','{}'))
        preferred={'cistern':'both_open','lodge':'both_open','hub':'open_all','container_long':'open','shelter':'open'}
        opened=poses.get(preferred.get(name,'open'),{})
        for extension in ('blend','glb','fbx'):
            if extension!='blend':
                bpy.ops.wm.read_factory_settings(use_empty=True)
                path=folder/f'{name}.{extension}'
                if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
                else:bpy.ops.import_scene.fbx(filepath=str(path))
                rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
            pose(rig,opened)
            result=audit(name,report,geometry());result['format']=extension
            results.append(result)
            print(f'[{name}] {extension} dimensions PASS {result}',flush=True)
    target=HERE.parents[1]/'target/architecture_dimensions'
    target.mkdir(parents=True,exist_ok=True)
    (target/'dimensions_report.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
