"""Exact deck recesses and lethal lunar terrain; no perimeter boundary walls."""
import bpy,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from model import shell,save_export
bpy.ops.wm.open_mainfile(filepath=str(HERE/'skyfall.blend'))
scene=bpy.context.scene;scene.frame_set(73)
rig=json.loads((HERE/'skyfall_rig.json').read_text());arm=bpy.data.objects['RIG_Skyfall']
proxies=[]
m=bpy.data.materials.new('M_Collision')
for ob in list(scene.objects):
    if ob.type!='MESH' or not ob.name.startswith('SK_Skyfall'):continue
    col=ob.copy();col.data=ob.data.copy();col.name=ob.name+'_Col';bpy.context.collection.objects.link(col);proxies.append(col)
    col.data.materials.clear()
    m=bpy.data.materials.get('M_Collision') or bpy.data.materials.new('M_Collision');col.data.materials.append(m)
    for face in col.data.polygons:face.material_index=0
for marker in rig['markers']:
    if marker['role']!='flag_base':continue
    x,y,z=marker['position_blender'];bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=1,depth=.1,location=(x,y,z+.05))
    ob=bpy.context.object;ob.name='SK_SkyfallFlagCaptureTrigger_'+marker['zone'];ob.data.name=ob.name;bpy.ops.object.transform_apply(location=True,rotation=False,scale=False)
    ob.parent=arm;g=ob.vertex_groups.new(name='Deck_'+marker['deck']);g.add(list(range(len(ob.data.vertices))),1,'REPLACE');mod=ob.modifiers.new('flag floor','ARMATURE');mod.object=arm;ob.data.materials.append(m);proxies.append(ob)
save_export([arm,*proxies],'_col')
print('SKYFALL_COLLISION',sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in proxies))
