"""Fresh render/collider GLB/FBX audit and actual door-clip checks."""
import json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
INFO=json.loads((HERE/'stasis_chamber_rig.json').read_text())

def reset(rig):
 rig.animation_data_create();rig.animation_data.action=None
 for track in rig.animation_data.nla_tracks:track.mute=True
 for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
 bpy.context.view_layer.update()

def check(stem,extension):
 bpy.ops.wm.read_factory_settings(use_empty=True)
 path=HERE/f'{stem}.{extension}'
 if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
 else:bpy.ops.import_scene.fbx(filepath=str(path))
 rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
 assert set(rig.data.bones.keys())=={'Root','Door'}
 reset(rig)
 meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
 for obj in meshes:
  assert all(abs(s-1)<1e-5 for s in obj.scale)
  for vertex in obj.data.vertices:
   weights=[g.weight for g in vertex.groups if g.weight>1e-6]
   assert len(weights)==1 and abs(weights[0]-1)<1e-5,(obj.name,vertex.index,weights)
 counts={o.name:sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes}
 if stem=='stasis_chamber':
  assert counts==INFO['meshes'],counts
  for obj in meshes:
   assert obj.data.uv_layers
   assert all(math.isfinite(c) and -.0001<=c<=1.0001 for layer in obj.data.uv_layers for uv in layer.data for c in uv.uv)
  points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
  bounds={'lo':[min(v[i] for v in points) for i in range(3)],'hi':[max(v[i] for v in points) for i in range(3)]}
  assert all(abs(a-b)<.0002 for side in ('lo','hi') for a,b in zip(bounds[side],INFO['bounds_m'][side]))
  assert abs(bounds['hi'][1]-bounds['lo'][1]-1.5)<.0002
  assert abs(bounds['hi'][0]-bounds['lo'][0]-1.25)<.0002
  pane=next(o for o in meshes if 'Glass' in o.name)
  assert all(pane.vertex_groups[g.group].name=='Door' for v in pane.data.vertices for g in v.groups if g.weight>1e-6)
 else:
  assert all(n<=500 for n in counts.values()),counts
  # Every solid island is closed and outward-facing.
  for obj in meshes:
   bm=bmesh.new();bm.from_mesh(obj.data)
   assert all(len(e.link_faces)==2 for e in bm.edges),(obj.name,'open collider')
   assert bm.calc_volume()>0,(obj.name,'inward collider');bm.free()
 clips={n:next((a for a in bpy.data.actions if n in a.name.lower()),None) for n in ('open','close')}
 assert all(clips.values()),[a.name for a in bpy.data.actions]
 for name,action in clips.items():
  reset(rig);rig.animation_data.action=action
  if action.slots:rig.animation_data.action_slot=action.slots[0]
  endpoints=[]
  for frame in action.frame_range:
   whole=math.floor(frame);bpy.context.scene.frame_set(whole,subframe=frame-whole);bpy.context.view_layer.update()
   endpoints.append(rig.pose.bones['Door'].matrix.copy())
  turn=(endpoints[0].to_3x3().inverted()@endpoints[1].to_3x3()).to_quaternion().angle
  assert abs(math.degrees(turn)-120)<.02,(name,turn)
  pivot=Vector(INFO['joints'][1]['pivot'])
  assert all((m.translation-pivot).length<.0002 for m in endpoints),(name,'moving hinge axis')
  for half in range(int(action.frame_range[0]*2),int(action.frame_range[1]*2)+1):
   bpy.context.scene.frame_set(half//2,subframe=(half%2)/2)
   pose=rig.pose.bones['Door']
   assert all(abs(x-1)<1e-5 for x in pose.scale)
   assert (pose.matrix.translation-pivot).length<.0002,(name,'hinge drift')
   turn=(rig.data.bones['Door'].matrix_local.inverted()@pose.matrix).to_quaternion().angle
   assert math.degrees(turn)<=120.02,(name,'overshoot',turn)
 print(f'[stasis_chamber] {path.name}: PASS {counts}; supported fixed-axis 120 degree open/close',flush=True)
 return {'file':path.name,'triangles':counts,'status':'PASS','door_angle_deg':120}
# Measure the native render surface against all authored collision pieces.
bpy.ops.wm.open_mainfile(filepath=str(HERE/'stasis_chamber.blend'))
rig=bpy.data.objects['RIG_StasisChamber'];reset(rig)
sys.path.insert(0,str(HERE));import collision as collider
pieces=collider.extras.root(rig)+collider.extras.door(rig)+collider.extras.panel(rig,None)[1]
meshes=[bpy.data.objects[n] for n in ('SK_StasisChamber','SK_StasisChamberGlass')]
triangles,_=collider.mesh_islands(meshes,{},rig.matrix_world.inverted())
worst,share=collider.coverage(pieces,triangles)
assert worst<=.0201,('collider misses render geometry',worst)
print(f'[stasis_chamber] collider coverage: {worst*1000:.2f} mm worst protrusion; {share*100:.1f}% surface inside',flush=True)
report=[check(stem,ext) for stem in ('stasis_chamber','stasis_chamber_col') for ext in ('glb','fbx')]
(HERE.parents[2]/'target'/'stasis_chamber_validation.json').write_text(json.dumps(report,indent=2))
