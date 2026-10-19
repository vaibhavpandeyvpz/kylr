"""Shared lunar PBR for native regolith exports and metre-based previews."""
from pathlib import Path
import bpy
DIRECTORY=Path(__file__).resolve().parents[2]/'textures/lunar_surface'
NAMES={'M_Regolith','M_RegolithLight','M_RegolithDark'}
SCALE=.24
_images={}

def output_group():
    from io_scene_gltf2.blender.com.material_helpers import create_settings_group
    group=bpy.data.node_groups.get('glTF Material Output')
    if group is None:return create_settings_group('glTF Material Output')
    # Keep the complete schema expected by Blender's glTF round-trip importer,
    # even though this material uses only the core occlusion input.
    schema=create_settings_group('_LunarOutputSchema')
    names={s.name for s in group.interface.items_tree if s.item_type=='SOCKET' and s.in_out=='INPUT'}
    for socket in schema.interface.items_tree:
        if socket.item_type=='SOCKET' and socket.in_out=='INPUT' and socket.name not in names:
            added=group.interface.new_socket(name=socket.name,in_out='INPUT',socket_type=socket.socket_type)
            added.default_value=socket.default_value
    bpy.data.node_groups.remove(schema)
    return group

def install(material,world=False):
    material.use_nodes=True;nodes=material.node_tree.nodes;nodes.clear();links=material.node_tree.links
    shader=nodes.new('ShaderNodeBsdfPrincipled');out=nodes.new('ShaderNodeOutputMaterial')
    links.new(shader.outputs['BSDF'],out.inputs['Surface']);shader.inputs['Metallic'].default_value=0
    uv=nodes.new('ShaderNodeTexCoord')
    vector=uv.outputs['UV']
    if world:
        position=nodes.new('ShaderNodeNewGeometry');scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=SCALE
        links.new(position.outputs['Position'],scale.inputs[0]);vector=scale.outputs['Vector']
    material.diffuse_color=(1,1,1,1)
    shader.inputs['Base Color'].default_value=(1,1,1,1)
    shader.inputs['Roughness'].default_value=1
    def texture(channel,color=False):
        path=DIRECTORY/f'regolith_{channel}.png'
        key=(channel,path.stat().st_mtime_ns)
        image=_images.get(key)
        try:valid=image is not None and image.name in bpy.data.images
        except ReferenceError:valid=False
        if not valid:
            image=bpy.data.images.load(str(path),check_existing=True)
            # Local blend caches may carry packed bytes; canonical files own this set.
            if image.packed_file:image.unpack(method='REMOVE')
            image.filepath=str(path);image.reload()
            image.colorspace_settings.name='sRGB' if color else 'Non-Color';image.pack()
            _images[key]=image
        node=nodes.new('ShaderNodeTexImage');node.image=image;node.extension='REPEAT'
        if world:node.projection='BOX';node.projection_blend=.2
        links.new(vector,node.inputs['Vector']);return node
    albedo=texture('albedo',True)
    links.new(albedo.outputs['Color'],shader.inputs['Base Color'])
    packed=texture('orm')
    channels=nodes.new('ShaderNodeSeparateColor');channels.mode='RGB'
    links.new(packed.outputs['Color'],channels.inputs['Color'])
    links.new(channels.outputs['Green'],shader.inputs['Roughness'])
    occlusion=nodes.new('ShaderNodeGroup');occlusion.node_tree=output_group()
    links.new(channels.outputs['Red'],occlusion.inputs['Occlusion'])
    normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.55
    links.new(texture('normal').outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],shader.inputs['Normal'])
    material['lunar_texture_set']='textures/lunar_surface';material['world_repeat_scale']=SCALE

def preview():
    for mat in bpy.data.materials:
        if mat.name.split('.')[0].removesuffix('_Diffuse') in NAMES:install(mat,world=True)
