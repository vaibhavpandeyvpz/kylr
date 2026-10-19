"""Supplement standard previews with a reference-angle hero and hinge close-up."""
import importlib.util
import sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cradle_studio',HERE/'preview.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
source_spec=importlib.util.spec_from_file_location('cradle_detail_spec',HERE/'model.py')
source=importlib.util.module_from_spec(source_spec);sys.modules[source_spec.name]=source;source_spec.loader.exec_module(source)
p.open_model();p.setup_render()
cam,lights=p.create_camera(),p.create_lights()
p.VIEWS['hero']=((.75,-1.3,.9),'PERSP',(1600,1200))
p.render_view(cam,lights,'hero','hero')
# A temporary framing mesh specifies the assembly to inspect; it never exports.
mesh=bpy.data.meshes.new('PRV_InspectionBounds')
mesh.from_pydata([(x*source.SCALE,y*source.SCALE,z*source.SCALE)
                 for x in (.29,.52) for y in (-.52,-.29) for z in (.19,.37)],[],[])
target=bpy.data.objects.new('PRV_InspectionBounds',mesh)
bpy.context.scene.collection.objects.link(target)
target.hide_render=True
p.VIEWS['detail']=((1,.3,.5),'PERSP',(1200,1200))
p.render_view(cam,lights,'detail','hinge_detail',subject=[target],margin=1.3)
bpy.data.objects.remove(target,do_unlink=True);bpy.data.meshes.remove(mesh)
print('[item_cradle] reference-angle hero and hinge detail rendered')
