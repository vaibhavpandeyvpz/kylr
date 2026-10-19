"""Scripted unibody terrain/well operations shared by standalone map builders."""
import bpy
from mathutils import Vector

RECESS_CLEARANCE_M = .001
RECESS_TOP_M = .5

def recess_size(footprint):
    """One millimetre of clearance at each outer fixture face."""
    return [dimension + 2 * RECESS_CLEARANCE_M for dimension in footprint]
def shell(name,rect,z,depth):
    a,b,c,d=rect;vertices=[(a,b,z-depth),(c,b,z-depth),(c,d,z-depth),(a,d,z-depth),(a,b,z),(c,b,z),(c,d,z),(a,d,z)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob);return ob
def boolean(target,other,operation):
    if operation=='DIFFERENCE':
        bpy.context.view_layer.update()
        bounds=[]
        for obj in (target,other):
            points=[obj.matrix_world@Vector(p) for p in obj.bound_box]
            bounds.append(([min(p[i] for p in points) for i in range(3)],
                           [max(p[i] for p in points) for i in range(3)]))
        if any(min(bounds[0][1][i],bounds[1][1][i])-max(bounds[0][0][i],bounds[1][0][i])<=1e-8 for i in range(3)):
            # Even an empty Exact Boolean can triangulate a complex native mesh.
            # Preserve untouched surfaces rather than rewriting their topology.
            bpy.data.objects.remove(other,do_unlink=True)
            return False
    bpy.context.view_layer.objects.active=target
    mod=target.modifiers.new('machined map shell','BOOLEAN');mod.operation=operation;mod.solver='EXACT';mod.object=other;mod.use_self=True;mod.use_hole_tolerant=True
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(other,do_unlink=True)
    return True
def cutter(target,center,size,depth,yaw=0):
    w,h=size;cut=shell('TEMP / recess',[-w/2,-h/2,w/2,h/2],RECESS_TOP_M,depth+RECESS_TOP_M);cut.location=center;cut.rotation_euler.z=yaw;boolean(target,cut,'DIFFERENCE')
def export(objects,folder,stem,animated=False):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(folder/(stem+'.glb')),export_format='GLB',use_selection=True,export_animations=animated,export_extras=True,export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(folder/(stem+'.fbx')),use_selection=True,object_types={'MESH','ARMATURE','EMPTY'},add_leaf_bones=False,axis_forward='-Z',axis_up='Y',bake_anim=animated,bake_anim_simplify_factor=0)
