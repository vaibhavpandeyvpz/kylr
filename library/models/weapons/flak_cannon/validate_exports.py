"""Round-trip native weapon, cassette and collider exports in headless Blender."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector

folder = Path(__file__).resolve().parent
metadata = json.loads((folder/'flak_cannon_rig.json').read_text())
def rest_rigs():
    # Importers may activate an arbitrary take. Compare attachment frames at rest.
    for obj in bpy.context.scene.objects:
        if obj.type!='ARMATURE':continue
        if obj.animation_data:
            obj.animation_data.action=None
            for track in obj.animation_data.nla_tracks:track.mute=True
        for bone in obj.pose.bones:
            bone.location=(0,0,0)
            bone.rotation_euler=(0,0,0)
            bone.rotation_quaternion=(1,0,0,0)
            bone.scale=(1,1,1)
    bpy.context.view_layer.update()

def motion_samples():
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if not rigs:return {}
    rig=rigs[0];result={}
    fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
    for action in bpy.data.actions:
        rest_rigs()
        name=action.name.split('|')[-1]
        rig.animation_data.action=action
        f0,f1=action.frame_range
        samples=[]
        for fraction in (0,.25,.5,.75,1):
            frame=f0+(f1-f0)*fraction
            bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
            inv=rig.matrix_world.inverted()
            transforms={bone.name:(rig.matrix_world@bone.matrix@
                        bone.bone.matrix_local.inverted()@inv).copy() for bone in rig.pose.bones}
            samples.append(((frame-f0)/fps,transforms))
        result[name]=samples
    rest_rigs()
    return result

reports = []
for stem, mesh_name in [('flak_cannon','SK_FlakCannon'),('flak_cannon_ammo','SM_FlakCannonAmmo')]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if stem.endswith('_ammo'):
        with bpy.data.libraries.load(str(folder/(stem+'.blend'))) as (src,dst):
            dst.objects=src.objects
        for obj in dst.objects:
            bpy.context.scene.collection.objects.link(obj)
    else:
        bpy.ops.wm.open_mainfile(filepath=str(folder/(stem+'.blend')))
    rest_rigs()
    baseline = bpy.data.objects[mesh_name]
    points = [baseline.matrix_world@v.co for v in baseline.data.vertices]
    lo=Vector(min(p[i] for p in points) for i in range(3))
    hi=Vector(max(p[i] for p in points) for i in range(3))
    used={baseline.data.materials[f.material_index].name for f in baseline.data.polygons}
    expected_motion=motion_samples()
    wanted_bones={b.name for o in bpy.context.scene.objects if o.type=='ARMATURE' for b in o.data.bones}
    expected_markers={o.name: o.matrix_world.copy() for o in bpy.context.scene.objects if o.type=='EMPTY'}
    for ext in ['glb','fbx']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if ext=='glb': bpy.ops.import_scene.gltf(filepath=str(folder/(stem+'.glb')))
        else: bpy.ops.import_scene.fbx(filepath=str(folder/(stem+'.fbx')))
        rest_rigs()
        obj=bpy.data.objects[mesh_name]
        obj.data.calc_loop_triangles()
        tris=len(obj.data.loop_triangles)
        assert tris==metadata['triangles'][mesh_name], (stem,ext,tris)
        assert tris<=metadata['triangle_budgets'][mesh_name],(stem,ext,'budget',tris)
        assert all(abs(v-1)<1e-5 for v in obj.scale), (stem,ext,'scale')
        p=[obj.matrix_world@v.co for v in obj.data.vertices]
        ilo=Vector(min(q[i] for q in p) for i in range(3))
        ihi=Vector(max(q[i] for q in p) for i in range(3))
        assert (ilo-lo).length<1e-4 and (ihi-hi).length<1e-4,(stem,ext,'bounds',list(ilo),list(lo))
        assert abs(ilo.z)<1e-4,(stem,ext,'ground')
        mats={obj.data.materials[f.material_index].name for f in obj.data.polygons}
        assert mats==used,(stem,ext,'materials',mats,used)
        assert obj.data.uv_layers and all(math.isfinite(c) and -.0001<=c<=1.0001 for d in obj.data.uv_layers.active.data for c in d.uv)
        bones={b.name for o in bpy.context.scene.objects if o.type=='ARMATURE' for b in o.data.bones}
        assert bones==wanted_bones,(stem,ext,'bones',bones,wanted_bones)
        if bones:
            for v in obj.data.vertices:
                weights=[g.weight for g in v.groups if g.weight>1e-6]
                assert len(weights)==1 and abs(weights[0]-1)<1e-5,(stem,ext,'weights',v.index,weights)
            for name,matrix in expected_markers.items():
                node=bpy.data.objects.get(name)
                assert node and (node.matrix_world.translation-matrix.translation).length<1e-4,(stem,ext,'marker',name)
        clip_names={a.name.split('|')[-1] for a in bpy.data.actions}
        expected_clips=set() if stem.endswith('_ammo') else set(metadata['animations'])
        assert clip_names==expected_clips,(stem,ext,'clips',clip_names,expected_clips)
        for action in bpy.data.actions:
            name=action.name.split('|')[-1]
            span=float(action.frame_range[1]-action.frame_range[0])
            expected_seconds=metadata['animations'][name]['frames'][1]/metadata['animations'][name]['fps']
            actual_seconds=span/(bpy.context.scene.render.fps/bpy.context.scene.render.fps_base)
            assert abs(actual_seconds-expected_seconds)<.001,(stem,ext,'duration',name,actual_seconds)
        imported_motion=motion_samples()
        for name,samples in expected_motion.items():
            for (seconds,poses),(imported_seconds,imported_poses) in zip(samples,imported_motion[name]):
                assert abs(seconds-imported_seconds)<.001,(stem,ext,'sample time',name)
                for bone,matrix in poses.items():
                    error=max(abs(matrix[i][j]-imported_poses[bone][i][j]) for i in range(4) for j in range(4))
                    assert error<.0003,(stem,ext,'motion transform',name,seconds,bone,error)
        entry=dict(stem=stem,format=ext,triangles=tris,size_m=list(ihi-ilo),bones=sorted(bones),materials=sorted(mats),markers=sorted(expected_markers))
        reports.append(entry)
        print('[flak_cannon] ROUNDTRIP PASS',stem,ext,tris,'triangles',len(bones),'bones',flush=True)
(folder/'flak_cannon_validation.json').write_text(json.dumps(reports,indent=2))

# Independently validate rigid collision companions.
reports=[]
for stem,name in [('flak_cannon_col','SK_FlakCannonCol'),('flak_cannon_ammo_col','SM_FlakCannonAmmoCol')]:
 for ext in ['glb','fbx']:
  bpy.ops.wm.read_factory_settings(use_empty=True)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(folder/(stem+'.'+ext)))
  else:bpy.ops.import_scene.fbx(filepath=str(folder/(stem+'.'+ext)))
  obj=bpy.data.objects[name];obj.data.calc_loop_triangles()
  tris=len(obj.data.loop_triangles)
  assert (100<=tris<=500 if stem=='flak_cannon_col' else tris<=500),(name,tris)
  assert all(abs(v-1)<1e-5 for v in obj.scale)
  assert len(obj.data.vertices)>0
  bones={b.name for o in bpy.context.scene.objects if o.type=='ARMATURE' for b in o.data.bones}
  clip_names={a.name.split('|')[-1] for a in bpy.data.actions}
  assert clip_names==(set(metadata['animations']) if stem=='flak_cannon_col' else set()),(stem,ext,'collision clips',clip_names)
  if stem=='flak_cannon_col':
   assert len(bones)==8,bones
   for v in obj.data.vertices:
    weights=[g.weight for g in v.groups if g.weight>1e-6]
    assert len(weights)==1 and abs(weights[0]-1)<1e-5
  else:assert not bones
  reports.append(dict(asset=stem,format=ext,triangles=tris,bones=sorted(bones)))
  print('COLLIDER ROUNDTRIP PASS',stem,ext,tris,flush=True)
(folder/'flak_cannon_collision_validation.json').write_text(json.dumps(reports,indent=2))
