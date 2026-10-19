"""Render-only authored socket axes and names; never exported as model geometry."""
import bpy
from mathutils import Vector

def install(length=None):
    if length is None:
        points=[o.matrix_world@Vector(v) for o in bpy.context.scene.objects if o.type=="MESH" and o.name.startswith("SK_") for v in o.bound_box]
        span=max((max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)),default=1)
        length=max(.18,min(.75,span*.06))
    mounts=[o for o in bpy.context.scene.objects if o.type=='EMPTY' and o.empty_display_type in ('ARROWS','PLAIN_AXES') and not o.hide_render]
    materials=[]
    for axis,color in zip('XYZ',[(1,.04,.02),(.04,1,.12),(.06,.25,1)]):
        mat=bpy.data.materials.new('PRV_Gizmo'+axis);mat.use_nodes=True
        shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=(*color,1)
        shader.inputs['Emission Color'].default_value=(*color,1);shader.inputs['Emission Strength'].default_value=2
        materials.append(mat)
    label_material=bpy.data.materials.new("PRV_GizmoLabel");label_material.use_nodes=True
    label_nodes=label_material.node_tree.nodes;label_nodes.clear()
    emitter=label_nodes.new("ShaderNodeEmission");emitter.inputs["Color"].default_value=(.008,.012,.018,1)
    output=label_nodes.new("ShaderNodeOutputMaterial");label_material.node_tree.links.new(emitter.outputs[0],output.inputs[0])
    for mount in mounts:
        for axis in range(3):
            curve=bpy.data.curves.new('PRV_SocketAxis','CURVE');curve.dimensions='3D';curve.bevel_depth=length*.02;curve.bevel_resolution=0
            line=curve.splines.new('POLY');line.points.add(1);line.points[0].co=(0,0,0,1)
            tip=[0,0,0,1];tip[axis]=length;line.points[1].co=tip
            for sign in (-1,1):
                head=curve.splines.new('POLY');head.points.add(1);head.points[0].co=tip
                tail=tip.copy();tail[axis]-=length*.18;tail[(axis+1)%3]+=sign*length*.07;head.points[1].co=tail
            curve.materials.append(materials[axis]);obj=bpy.data.objects.new('PRV_'+mount.name+'_'+str(axis),curve)
            bpy.context.collection.objects.link(obj);obj.parent=mount
        text=bpy.data.curves.new('PRV_SocketName','FONT');text.body=mount.name;text.size=length*.18
        text.align_x='CENTER';text.materials.append(label_material);label=bpy.data.objects.new('PRV_Label_'+mount.name,text)
        bpy.context.collection.objects.link(label);label.parent=mount;label.location=(0,0,length*1.15)
        label['preview_gizmo_label']=True
    print('PREVIEW_GIZMOS',len(mounts),'authored sockets',flush=True)

def face_labels(camera):
    bpy.context.view_layer.update()
    for obj in bpy.context.scene.objects:
        if obj.get('preview_gizmo_label'):
            obj.rotation_euler=(obj.parent.matrix_world.to_3x3().inverted()@camera.matrix_world.to_quaternion().to_matrix()).to_euler()


def ghost_model():
    """Dedicated socket inspection: translucent native shells reveal interior mounts."""
    saved=[]
    for material in bpy.data.materials:
        if material.name.startswith('PRV_') or not material.node_tree:continue
        for shader in material.node_tree.nodes:
            if shader.type=='BSDF_PRINCIPLED':
                saved.append((material,shader,shader.inputs['Alpha'].default_value,material.surface_render_method))
                shader.inputs['Alpha'].default_value=.18
        material.surface_render_method='DITHERED'

    return saved

def restore_model(saved):
    for material,shader,alpha,method in saved:
        shader.inputs['Alpha'].default_value=alpha;material.surface_render_method=method
