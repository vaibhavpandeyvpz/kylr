"""Fresh GLB/FBX collider rig, rigid-weight, clip and closed-island audit."""
import json,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dimensions import TARGET_LWH
names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(TARGET_LWH)
report=[]
for name in names:
 info=json.loads((HERE/name/f'{name}_rig.json').read_text())
 clipnames=list(info['animations']) if isinstance(info['animations'],dict) else [a['name'] for a in info['animations']]
 for ext in ('glb','fbx'):
  bpy.ops.wm.read_factory_settings(use_empty=True)
  path=HERE/name/f'{name}_col.{ext}'
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
  else:bpy.ops.import_scene.fbx(filepath=str(path))
  rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
  rig.animation_data_create();rig.animation_data.action=None
  for track in rig.animation_data.nla_tracks:track.mute=True
  for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
  bpy.context.view_layer.update()
  assert all(any(n.lower() in a.name.lower() for a in bpy.data.actions) for n in clipnames),(name,ext,'missing clip')
  meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
  counts={}
  for obj in meshes:
   assert all(abs(s-1)<1e-5 for s in obj.scale),(name,ext,obj.name)
   for vertex in obj.data.vertices:
    weights=[g.weight for g in vertex.groups if g.weight>1e-6]
    assert len(weights)==1 and abs(weights[0]-1)<1e-5,(name,ext,obj.name,vertex.index)
   # The repair shield is an intentional hollow trimesh effect, not convex.
   if 'Shield' not in obj.name:
    bm=bmesh.new();bm.from_mesh(obj.data)
    assert all(len(e.link_faces)==2 for e in bm.edges),(name,ext,obj.name,'open collider')
    pending=set(bm.verts)
    while pending:
     seed=pending.pop();island={seed};stack=[seed]
     while stack:
      for edge in stack.pop().link_edges:
       for vertex in edge.verts:
        if vertex in pending:pending.remove(vertex);island.add(vertex);stack.append(vertex)
     volume=sum(t[0].vert.co.dot(t[1].vert.co.cross(t[2].vert.co))/6 for t in bm.calc_loop_triangles() if t[0].vert in island)
     assert volume>1e-10,(name,ext,obj.name,'inward island',volume)
    bm.free()
   counts[obj.name]=sum(len(p.vertices)-2 for p in obj.data.polygons)
  print(f'[{name}] {path.name}: PASS {counts}; {len(clipnames)} clips',flush=True)
  report.append({'asset':name,'format':ext,'triangles':counts,'clips':clipnames,'status':'PASS'})
(HERE.parents[1]/'target/gameplay_collider_roundtrips.json').write_text(json.dumps(report,indent=2))
