"""Lunar ground recesses, perimeter blockers and authored flag capture areas."""
import bpy,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'common'));sys.path.insert(0,str(HERE.parent/'common/platform'));from map_shells import shell,export
bpy.ops.wm.open_mainfile(filepath=str(HERE/'faceoff.blend'));bpy.context.scene.frame_set(73)
rig=bpy.data.objects['RIG_Faceoff'];data=json.loads((HERE/'faceoff_rig.json').read_text());objects=[]
material=bpy.data.materials.new('M_Collision')
def bind(ob):
    ob.parent=rig;group=ob.vertex_groups.get('Root') or ob.vertex_groups.new(name='Root');group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
    if not any(m.type=='ARMATURE' for m in ob.modifiers):ob.modifiers.new('fixed lunar collider','ARMATURE').object=rig
    ob.data.materials.clear();ob.data.materials.append(material)
    for p in ob.data.polygons:p.material_index=0
    objects.append(ob)
for i,rect in enumerate([[-37.75,-37.75,-37.5,37.75],[37.5,-37.75,37.75,37.75],[-37.5,-37.75,37.5,-37.5],[-37.5,37.5,37.5,37.75]]):bind(shell('SK_FaceoffBoundary'+str(i),rect,100,102))
for marker in data['markers']:
    if marker['role']!='flag_base':continue
    x,y,z=marker['position_blender'];bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=1,depth=.1,location=(x,y,z+.05));ob=bpy.context.object;ob.name='SK_FaceoffFlagCaptureTrigger_'+marker['zone']
    bpy.ops.object.transform_apply(location=True,rotation=False,scale=False);bind(ob)
export([rig,*objects],HERE,'faceoff_col',animated=True)
print('FACEOFF_COLLISION',len(objects),'proxies')
