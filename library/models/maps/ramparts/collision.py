"""Export closed native rocks and authored nonblocking CTF base triggers."""
import bpy
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from layout import data
sys.path.insert(0,str(HERE.parent/'common'));from map_shells import export

bpy.ops.wm.open_mainfile(filepath=str(HERE/'ramparts.blend'))
rig=bpy.data.objects['RIG_Ramparts']
objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.endswith('Col')]
for marker in data()[1]:
    if marker['role']!='flag_base':continue
    x,y,z=marker['position_blender']
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=1,depth=.1,location=(x,y,z+.05))
    ob=bpy.context.object;ob.name='SK_RampartsFlagCaptureTrigger_'+marker['zone']
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    ob.parent=rig;ob.vertex_groups.new(name='Root').add(list(range(len(ob.data.vertices))),1,'REPLACE')
    ob.modifiers.new('fixed base trigger','ARMATURE').object=rig;objects.append(ob)
export([rig,*objects],HERE,'ramparts_col')
print('RAMPARTS_COLLISION',len(objects),'closed shells and triggers')
