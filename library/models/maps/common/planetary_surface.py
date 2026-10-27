"""Blender handoff for Terrain3D-baked landforms, seamless LOD joins and native cuts."""
from pathlib import Path
import json
import math
import bpy
import bmesh

ROOT=Path(__file__).resolve().parents[3]
CACHE=ROOT/'.local/planetary'
LAYERS=('dust','basalt','bedrock','rubble','compacted','scorch')


def clean_authoring_defaults():
    """Drop orphan factory meshes/materials before saving the placement rig."""
    for mesh in list(bpy.data.meshes):
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        if mat.users==0:bpy.data.materials.remove(mat)


def build(map_id,name,bottom_elevation=None):
    path=CACHE/(map_id+'_baked.json')
    assert path.exists(), 'Run tools/build_planetary_terrain.py '+map_id+' first'
    data=json.loads(path.read_text(encoding='utf-8'))
    has_inner=any(part['inner'] for part in data['parts'])
    vertices=[];faces=[];lookup={}
    height={}
    for part in data['parts']:
        if part['inner']:
            height={(round(v[0]),round(v[2])):v[1] for v in part['vertices']}
    def vertex(value):
        x,y,z=value
        key=(round(x,5),round(y,5),round(z,5))
        if key not in lookup:
            lookup[key]=len(vertices);vertices.append((x,-z,y))
        return lookup[key]
    for part in data['parts']:
        source=part['vertices'];indices=part['indices']
        for i in range(0,len(indices),3):
            triangle=[source[index] for index in indices[i:i+3]]
            cx=sum(v[0] for v in triangle)/3;cz=sum(v[2] for v in triangle)/3
            if part['inner']:
                if abs(cx)>64 or abs(cz)>64:continue
            elif (has_inner and abs(cx)<64 and abs(cz)<64) or math.hypot(cx,cz)>240:
                continue
            # Match every fine boundary vertex; split coarse boundary triangles.
            # No overlapping skins, T junctions or vertical skirts at the join.
            split=False
            if not part['inner'] and has_inner:
                for edge in range(3):
                    a,b=triangle[edge],triangle[(edge+1)%3];c=triangle[(edge+2)%3]
                    same_x=abs(a[0])==64 and a[0]==b[0] and max(abs(a[2]),abs(b[2]))<=64
                    same_z=abs(a[2])==64 and a[2]==b[2] and max(abs(a[0]),abs(b[0]))<=64
                    if not (same_x or same_z):continue
                    count=round(max(abs(a[0]-b[0]),abs(a[2]-b[2])))
                    points=[]
                    for step in range(count+1):
                        t=step/count;x=round(a[0]+(b[0]-a[0])*t);z=round(a[2]+(b[2]-a[2])*t)
                        points.append(vertex((x,height[(x,z)],z)))
                    other=vertex(c)
                    for step in range(count):faces.append((points[step+1],points[step],other))
                    split=True;break
            if not split:faces.append(tuple(vertex(v) for v in reversed(triangle)))
    # Extrude vertically, rather than along steep normals: both skins remain
    # height fields, so tight concave grades cannot fold the buried surface.
    count=len(vertices);edges={}
    for face in faces:
        for a,b in zip(face,(*face[1:],face[0])):
            key=tuple(sorted((a,b)))
            if key in edges:edges[key]=None
            else:edges[key]=(a,b)
    bottom=[(x,y,z-2 if bottom_elevation is None else min(z-2,bottom_elevation)) for x,y,z in vertices]
    lower=[tuple(index+count for index in reversed(face)) for face in faces]
    walls=[(b,a,a+count,b+count) for edge in edges.values() if edge is not None for a,b in [edge]]
    vertices.extend(bottom);faces.extend(lower);faces.extend(walls)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert not any(not edge.is_manifold for edge in bm.edges),'Terrain must be a closed joined volume'
    bm.to_mesh(ob.data);bm.free()
    for polygon in ob.data.polygons:polygon.use_smooth=True
    ob['terrain_style']='Terrain3D static planetary landforms'
    ob['interior_gravel_stone_count']=0
    ob['maximum_interior_stone_height_m']=0.0
    return ob


def material(map_id):
    texture_folder='volcanic_soil' if map_id=='faceoff' else 'planetary'
    name='M_Planetary'+map_id.capitalize()
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True;mat.diffuse_color=(.35,.34,.32,1)
    nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
    shader=nodes.new('ShaderNodeBsdfPrincipled');out=nodes.new('ShaderNodeOutputMaterial')
    links.new(shader.outputs['BSDF'],out.inputs['Surface']);shader.inputs['Roughness'].default_value=.92
    coordinate=nodes.new('ShaderNodeNewGeometry')
    # Blender XY becomes Godot X,-Z. Image UVs have their vertical origin below.
    separate=nodes.new('ShaderNodeSeparateXYZ');links.new(coordinate.outputs['Position'],separate.inputs[0])
    def scaled(value,scale,offset=0):
        node=nodes.new('ShaderNodeMath');node.operation='MULTIPLY_ADD';node.inputs[1].default_value=scale;node.inputs[2].default_value=offset
        links.new(value,node.inputs[0]);return node.outputs[0]
    control=nodes.new('ShaderNodeCombineXYZ')
    links.new(scaled(separate.outputs['X'],1/512,.5),control.inputs['X'])
    links.new(scaled(separate.outputs['Y'],1/512,.5),control.inputs['Y'])
    tiled=nodes.new('ShaderNodeCombineXYZ')
    links.new(scaled(separate.outputs['X'],.25),tiled.inputs['X']);links.new(scaled(separate.outputs['Y'],.25),tiled.inputs['Y'])
    links.new(scaled(separate.outputs['Z'],.25),tiled.inputs['Z'])
    def texture(path,vector,color,box=False):
        image=bpy.data.images.load(str(path),check_existing=True);image.colorspace_settings.name='sRGB' if color else 'Non-Color'
        node=nodes.new('ShaderNodeTexImage');node.image=image;links.new(vector,node.inputs['Vector'])
        if box:node.projection='BOX';node.projection_blend=.15
        return node
    channels=[]
    for index in range(2):
        tex=texture(CACHE/f'{map_id}_weights{index}.png',control.outputs[0],False)
        rgb=nodes.new('ShaderNodeSeparateColor');links.new(tex.outputs['Color'],rgb.inputs[0]);channels.extend([rgb.outputs[c] for c in ['Red','Green','Blue']])
    total=None;normal_total=None;roughness_total=None
    for layer,weight in zip(LAYERS,channels):
        tex=texture(ROOT.parent/'game/assets/textures'/texture_folder/f'{layer}_albedo_height.png',tiled.outputs[0],True,True)
        multiply=nodes.new('ShaderNodeVectorMath');multiply.operation='SCALE';links.new(tex.outputs['Color'],multiply.inputs[0]);links.new(weight,multiply.inputs['Scale'])
        if total is None:total=multiply.outputs[0]
        else:
            add=nodes.new('ShaderNodeVectorMath');add.operation='ADD';links.new(total,add.inputs[0]);links.new(multiply.outputs[0],add.inputs[1]);total=add.outputs[0]
        packed=texture(ROOT.parent/'game/assets/textures'/texture_folder/f'{layer}_normal_roughness.png',tiled.outputs[0],False,True)
        scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';links.new(packed.outputs['Color'],scale.inputs[0]);links.new(weight,scale.inputs['Scale'])
        if normal_total is None:normal_total=scale.outputs[0]
        else:
            add=nodes.new('ShaderNodeVectorMath');add.operation='ADD';links.new(normal_total,add.inputs[0]);links.new(scale.outputs[0],add.inputs[1]);normal_total=add.outputs[0]
        rough=nodes.new('ShaderNodeMath');rough.operation='MULTIPLY';links.new(packed.outputs['Alpha'],rough.inputs[0]);links.new(weight,rough.inputs[1])
        if roughness_total is None:roughness_total=rough.outputs[0]
        else:
            add=nodes.new('ShaderNodeMath');add.operation='ADD';links.new(roughness_total,add.inputs[0]);links.new(rough.outputs[0],add.inputs[1]);roughness_total=add.outputs[0]
    links.new(total,shader.inputs['Base Color'])
    normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.7
    links.new(normal_total,normal.inputs['Color']);links.new(normal.outputs['Normal'],shader.inputs['Normal'])
    links.new(roughness_total,shader.inputs['Roughness'])
    return mat


def preview():
    """Restore the authored blend after importing the standard GLB fallback."""
    replacements={}
    for ob in bpy.data.objects:
        if ob.type!='MESH':continue
        for index,source in enumerate(ob.data.materials):
            if source is None:continue
            for map_id in ('faceoff','skyfall'):
                if source.name.startswith('M_Planetary'+map_id.capitalize()):
                    if map_id not in replacements:replacements[map_id]=material(map_id)
                    ob.data.materials[index]=replacements[map_id]


def apply_materials(ob,map_id,source_material=None,wall_face_charts=False):
    mat=source_material if source_material is not None else material(map_id)
    ob.data.materials.clear();ob.data.materials.append(mat)
    uv=ob.data.uv_layers.get('TiledSurface') or ob.data.uv_layers.new(name='TiledSurface')
    for polygon in ob.data.polygons:
        polygon.material_index=0
        for loop in polygon.loop_indices:
            point=ob.data.vertices[ob.data.loops[loop].vertex_index].co
            uv.data[loop].uv=(point.x*.25,point.y*.25)
    ob.data.uv_layers.active=uv
    # Height-field charts are planar and unique. Only vertical excavation walls
    # need unwrapping; treating the full terrain as small props folds charts.
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm,faces=[face for face in bm.faces if len(face.verts)>3])
    if wall_face_charts:
        # Native cuts may leave opposite faces enclosing a sub-float32 fin.
        # Canonicalize those aliases before glTF quantization creates a seam.
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
        bm.verts.index_update();groups={}
        for face in bm.faces:groups.setdefault(tuple(sorted(v.index for v in face.verts)),[]).append(face)
        fins=[]
        for faces in groups.values():
            if len(faces)==2 and faces[0].normal.dot(faces[1].normal)<-.999:fins.extend(faces)
        bmesh.ops.delete(bm,geom=fins,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[edge for edge in bm.edges if not edge.link_faces],context='EDGES')
        print('TERRAIN_QUANTIZATION_FINS',len(fins),flush=True)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
    if wall_face_charts:assert all(edge.is_manifold for edge in bm.edges),'Excavated terrain must remain closed'
    bm.to_mesh(ob.data);bm.free();ob.data.update()
    atlas=ob.data.uv_layers.get('MaterialAtlas') or ob.data.uv_layers.new(name='MaterialAtlas');ob.data.uv_layers.active=atlas
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    walls=[]
    for polygon in ob.data.polygons:
        polygon.select=abs(polygon.normal.z)<.4 or (wall_face_charts and abs(polygon.normal.z)<.999999 and min(ob.data.vertices[i].co.z for i in polygon.vertices)<-1.25)
        if polygon.select:walls.append(polygon.index)
    if walls and not wall_face_charts:
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.uv.smart_project(angle_limit=math.radians(60),island_margin=.02,scale_to_bounds=True)
        bpy.ops.object.mode_set(mode='OBJECT')
    ob.data.update()
    # Edit mesh conversion rebuilds UV storage; reacquire RNA layer handles.
    atlas=ob.data.uv_layers['MaterialAtlas'];uv=ob.data.uv_layers['TiledSurface']
    wall_indices={index:slot for slot,index in enumerate(walls)}
    columns=max(1,math.ceil(math.sqrt(len(walls))))
    rows=max(1,math.ceil(len(walls)/columns))
    for polygon in ob.data.polygons:
        if wall_face_charts and polygon.index in wall_indices:
            slot=wall_indices[polygon.index];cell_x=.992/columns;cell_y=.30/rows
            gutter=min(.004,min(cell_x,cell_y)*.15)
            points=[ob.data.vertices[ob.data.loops[loop].vertex_index].co for loop in polygon.loop_indices]
            axis=(points[1]-points[0]).normalized();other=polygon.normal.cross(axis)
            projected=[((p-points[0]).dot(axis),(p-points[0]).dot(other)) for p in points]
            lo=[min(p[k] for p in projected) for k in (0,1)];hi=[max(p[k] for p in projected) for k in (0,1)]
            scale=min((cell_x-2*gutter)/max(hi[0]-lo[0],1e-9),(cell_y-2*gutter)/max(hi[1]-lo[1],1e-9))
            for loop,p in zip(polygon.loop_indices,projected):
                atlas.data[loop].uv=(.004+(slot%columns)*cell_x+gutter+(p[0]-lo[0])*scale,.004+(slot//columns)*cell_y+gutter+(p[1]-lo[1])*scale)
            continue
        if wall_face_charts and all(abs(ob.data.vertices[i].co.z+10)<1e-5 for i in polygon.vertices):
            # Undercut pit floors can lie below intact rim terrain at the same
            # XY coordinate, so their painting charts own a separate strip.
            for loop in polygon.loop_indices:
                point=ob.data.vertices[ob.data.loops[loop].vertex_index].co
                atlas.data[loop].uv=(.004+(point.x+37.5)/75*.992,.308+(point.y+37.5)/75*.102)
            continue
        for loop in polygon.loop_indices:
            # Edit-mode unwrap can reorder polygons; classify the current face.
            if abs(polygon.normal.z)<.4:
                point=atlas.data[loop].uv.copy()
                atlas.data[loop].uv=(.004+point.x*.992,.004+point.y*.364)
            else:
                point=ob.data.vertices[ob.data.loops[loop].vertex_index].co
                x=(point.x+256)/512;y=(point.y+256)/512
                atlas.data[loop].uv=(.004+x*.488+(.504 if polygon.normal.z<0 else 0),.428+y*.568)
    # Microscopic boolean slivers can collapse under float32 planar UVs even
    # when their geometry has finite area. Give those triangles spare charts.
    isolated=0
    for polygon in ob.data.polygons:
        loops=list(polygon.loop_indices)
        if len(loops)!=3:continue
        a,b,c=[atlas.data[index].uv.copy() for index in loops]
        area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))
        if area<1e-14:
            assert isolated<40,'Terrain needs more than the reserved UV exception strip'
            u=.008+isolated*.024
            v=.414 if wall_face_charts else .392
            for index,value in zip(loops,[(u,v),(u+.012,v),(u,v+(.006 if wall_face_charts else .012))]):atlas.data[index].uv=value
            isolated+=1
    ob.data.uv_layers.active=uv;uv.active_render=True


def validate_atlas(objects,folder,stem):
    from material_uv import validate_layouts,write_wireframe
    groups=sorted({mat.name for ob in objects for mat in ob.data.materials})
    for ob in objects:ob.data.uv_layers.active=ob.data.uv_layers['MaterialAtlas']
    try:
        validate_layouts(objects,groups,folder)
    except Exception as error:
        for name,index in getattr(error,'faces',[]):
            ob=bpy.data.objects[name];polygon=ob.data.polygons[index]
            print('TERRAIN_UV_ERROR',name,index,tuple(polygon.normal),[tuple(ob.data.uv_layers.active.data[i].uv) for i in polygon.loop_indices],flush=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(CACHE/(stem+'_uv_diagnostic.blend')),compress=True)
        raise
    for group in groups:write_wireframe(objects,group,folder)
    for ob in objects:
        ob['material_uv_atlas']=stem
        ob.data.uv_layers.active=ob.data.uv_layers['TiledSurface'];ob.data.uv_layers.active.active_render=True
