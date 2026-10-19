import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
F=Path(__file__).resolve().parent
sys.path.insert(0,str(F.parents[1]))
from material_classes import classified_name,policy
D=json.loads((F/'grenade_launcher_rig.json').read_text())
srgb=[int(D['primary_srgb'][i:i+2],16)/255 for i in (1,3,5)]
primary=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in srgb]
for ext in ('glb','fbx'):
 assert (F/f'grenade_launcher_grenade.{ext}').read_bytes()==(F/f'grenade_launcher_rocket.{ext}').read_bytes(),('projectile alias',ext)

def rest():
 for o in bpy.context.scene.objects:
  if o.type!='ARMATURE':continue
  if o.animation_data:
   o.animation_data.action=None
   for t in o.animation_data.nla_tracks:t.mute=True
  for p in o.pose.bones:
   p.location=(0,0,0);p.rotation_euler=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
 bpy.context.view_layer.update()

def bounds(obj):
 p=[obj.matrix_world@v.co for v in obj.data.vertices]
 return [Vector(min(q[i] for q in p) for i in range(3)),Vector(max(q[i] for q in p) for i in range(3))]

def names():return {a.name.split('|')[-1] for a in bpy.data.actions}

def motion(rig):
 result={}
 for a in bpy.data.actions:
  if not a.slots:continue
  slot=next((s for s in a.slots if s.target_id_type=='OBJECT'),None)
  if slot is None:continue
  rest();rig.animation_data_create();rig.animation_data.action=a;rig.animation_data.action_slot=slot
  f0,f1=a.frame_range;fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
  samples=[]
  for u in (0,.25,.5,.75,1):
   frame=f0+(f1-f0)*u;bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
   samples.append(((frame-f0)/fps,{p.name:(p.matrix@p.bone.matrix_local.inverted()).copy() for p in rig.pose.bones}))
  result[a.name.split('|')[-1]]=samples
 rest();return result

def validate_models():
 report=[]
 for stem,mname,budget in [('grenade_launcher','SK_GrenadeLauncher',5000),('grenade_launcher_ammo','SM_GrenadeLauncherAmmo',1500),('grenade_launcher_grenade','SK_GrenadeLauncherRocket',500)]:
  bpy.ops.wm.read_factory_settings(use_empty=True)
  if stem=='grenade_launcher':bpy.ops.wm.open_mainfile(filepath=str(F/(stem+'.blend')))
  else:
   with bpy.data.libraries.load(str(F/(stem+'.blend'))) as (s,t):t.objects=s.objects
   for o in t.objects:bpy.context.scene.collection.objects.link(o)
  rest();obj=bpy.data.objects[mname];lo,hi=bounds(obj);rig=obj.find_armature()
  expected_bones={b.name for b in rig.data.bones} if rig else set()
  mats={obj.data.materials[p.material_index].name for p in obj.data.polygons}
  expected_motion=motion(rig) if stem=='grenade_launcher' else {}
  markers={o.name:o.matrix_world.copy() for o in bpy.context.scene.objects if o.type=='EMPTY' and (not rig or o.parent==rig)}
  clips=set(D['animations']) if stem=='grenade_launcher' else set()
  for ext in ('glb','fbx'):
   bpy.ops.wm.read_factory_settings(use_empty=True)
   if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(F/(stem+'.glb')))
   else:bpy.ops.import_scene.fbx(filepath=str(F/(stem+'.fbx')))
   rest();o=bpy.data.objects[mname];o.data.calc_loop_triangles();tris=len(o.data.loop_triangles);il,ih=bounds(o)
   assert tris<=budget,(stem,ext,'budget',tris)
   assert max((il-lo).length,(ih-hi).length)<.0001,(stem,ext,'bounds',list(il),list(lo))
   assert all(abs(x-1)<1e-5 for x in o.scale),(stem,ext,'scale')
   assert {o.data.materials[p.material_index].name for p in o.data.polygons}==mats,(stem,ext,'materials')
   mat=bpy.data.materials[classified_name('M_Primary',policy(F))]
   rgb=mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value[:3]
   assert max(abs(a-b) for a,b in zip(rgb,primary))<1e-5,(stem,ext,'primary finish',rgb,primary)
   assert o.data.uv_layers and all(math.isfinite(c) and -.0001<=c<=1.0001 for p in o.data.uv_layers.active.data for c in p.uv),(stem,ext,'UV')
   r=o.find_armature();bones={b.name for b in r.data.bones} if r else set()
   assert bones==expected_bones,(stem,ext,'bones',bones,expected_bones)
   if r:
    assert all(len([g for g in v.groups if g.weight>1e-6])==1 and abs(sum(g.weight for g in v.groups)-1)<1e-5 for v in o.data.vertices),(stem,ext,'weights')
   assert names()==clips,(stem,ext,'clips',names(),clips)
   for n,m in markers.items():
    node=bpy.data.objects.get(n);assert node and (node.matrix_world.translation-m.translation).length<.0001,(stem,ext,'marker',n)
   if stem=='grenade_launcher':
    got=motion(r)
    for name,samples in expected_motion.items():
     if name not in clips:continue
     for (sec,poses),(isec,iposes) in zip(samples,got[name]):
      assert abs(sec-isec)<.001,(stem,ext,'time',name,sec,isec)
      for b,m in poses.items():
       err=max(abs(m[i][j]-iposes[b][i][j]) for i in range(4) for j in range(4))
       assert err<.0004,(stem,ext,'motion',name,b,err)
   entry=dict(asset=stem,format=ext,tris=tris,bones=len(bones),size=list(ih-il),clips=sorted(clips));report.append(entry)
   print('ROUNDTRIP PASS',entry,flush=True)
 (F/'validation.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':validate_models()
