"""GLB/FBX collider budgets and motion round trips, ignoring importer bone widgets."""
import bpy,json,sys
from pathlib import Path
F=Path(__file__).resolve().parent
sys.path.insert(0,str(F))
from validate import rest,motion,names,D
report=[]
bpy.ops.wm.open_mainfile(filepath=str(F/'grenade_launcher_col.blend'));rest();rig=bpy.data.objects['RIG_GrenadeLauncher'];expected=motion(rig)
for stem,clips in [('grenade_launcher_col',set(D['animations'])),('grenade_launcher_ammo_col',set()),('grenade_launcher_grenade_col',set())]:
 for ext in ('glb','fbx'):
  bpy.ops.wm.read_factory_settings(use_empty=True)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(F/(stem+'.glb')))
  else:bpy.ops.import_scene.fbx(filepath=str(F/(stem+'.fbx')))
  rest();meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.endswith('Col')];tris=0
  for o in meshes:
   o.data.calc_loop_triangles();tris+=len(o.data.loop_triangles)
   assert all(abs(c-1)<1e-5 for c in o.scale),(stem,ext,'scale')
  assert 0<tris<=500,(stem,ext,'budget',tris)
  assert names()==clips,(stem,ext,'clips',names(),clips)
  if stem=='grenade_launcher_col':
   r=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');got=motion(r)
   for name,ss in expected.items():
    if name not in clips:continue
    for (sec,poses),(isec,iposes) in zip(ss,got[name]):
     assert abs(sec-isec)<.001,(ext,name,'time')
     for b,m in poses.items():
      err=max(abs(m[i][j]-iposes[b][i][j]) for i in range(4) for j in range(4));assert err<.0004,(ext,name,b,err)
  row=dict(asset=stem,format=ext,triangles=tris,clips=sorted(clips));report.append(row);print('COLLIDER ROUNDTRIP PASS',row,flush=True)
(F/'collision_validation.json').write_text(json.dumps(report,indent=2))
