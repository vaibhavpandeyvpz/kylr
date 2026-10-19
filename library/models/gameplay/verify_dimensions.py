"""Audit authored native render assets and fresh GLB/FBX imports.

Run with headless Blender 5.2 from library/. Optional -- <asset> filters.
Owning validators supply deeper motion, clearance and collider checks.
"""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dimensions import TARGET_LWH,assert_authored_bounds

names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(TARGET_LWH)
report=[]
for name in names:
    for extension in ('blend','glb','fbx'):
        path=HERE/name/f'{name}.{extension}'
        if extension=='blend':bpy.ops.wm.open_mainfile(filepath=str(path))
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
        rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
        # Tensor is an optional repair-station preview stand-in, never delivery.
        rig=next(o for o in rigs if name.replace('_','').lower() in o.name.replace('_','').lower())
        rig.animation_data_create();rig.animation_data.action=None
        for track in rig.animation_data.nla_tracks:track.mute=True
        for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and
                o.name.startswith('SK_') and o.find_armature()==rig and
                'Shield' not in o.name and 'Trigger' not in o.name and 'Col' not in o.name]
        bounds=assert_authored_bounds(name,meshes,tolerance=.0002 if extension!='blend' else .00002)
        for obj in meshes:
            assert all(abs(s-1)<1e-5 for s in obj.scale),(name,obj.name,obj.scale)
            for v in obj.data.vertices:
                weights=[g.weight for g in v.groups if g.weight>1e-6]
                assert len(weights)==1 and abs(weights[0]-1)<1e-5,(name,obj.name,v.index)
            assert obj.data.uv_layers
            assert all(math.isfinite(c) and -1e-5<=c<=1.00001
                       for layer in obj.data.uv_layers for uv in layer.data for c in uv.uv)
        if name=='pressure_plate':
            # Read delivered clips at keys and half frames: tread crowns start
            # flush, press down 5 cm, then release to ground without overshoot.
            obj=meshes[0];group=obj.vertex_groups['Plate'].index
            moving=[v.index for v in obj.data.vertices if any(g.group==group and g.weight>.99 for g in v.groups)]
            deps=bpy.context.evaluated_depsgraph_get()
            for clip,endpoints in (('press',(0,-.05)),('release',(-.05,0))):
                action=next(a for a in bpy.data.actions if clip in a.name.lower())
                rig.animation_data.action=action
                if action.slots:rig.animation_data.action_slot=action.slots[0]
                heights=[]
                start,end=action.frame_range
                frames=[start]+[half/2 for half in range(math.ceil(start*2),math.floor(end*2)+1)]+[end]
                for frame in sorted(set(frames)):
                    whole=math.floor(frame)
                    bpy.context.scene.frame_set(whole,subframe=frame-whole)
                    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
                    top=max((obj.matrix_world@mesh.vertices[i].co).z for i in moving)
                    evaluated.to_mesh_clear();heights.append(top)
                    assert -.0502<=top<=.0002,(extension,clip,frame,top)
                assert all(abs(a-b)<.0002 for a,b in zip((heights[0],heights[-1]),endpoints)),(extension,clip,heights)
                assert all((b-a)*(1 if clip=='release' else -1)>=-1e-6 for a,b in zip(heights,heights[1:])),(extension,clip,'nonmonotonic')
            rig.animation_data.action=None
        tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        assert tris<={'item_cradle':5500,'pulse_gun':7500}.get(name,5000),(name,tris)
        report.append(dict(asset=name,format=extension,triangles=tris,**bounds,status='PASS'))
out=HERE.parents[1]/'target'/'gameplay_dimensions.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n')
