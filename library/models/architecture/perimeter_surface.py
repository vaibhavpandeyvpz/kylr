"""Optional foundation-fitted lunar apron, shared by architectural generators."""
import math
import bpy
from mathutils import Vector

NAME='SK_ArchitectureRegolith'
MATERIAL='M_Regolith'

def configure(kit):
    kit.MATERIALS[MATERIAL]=((.27,.255,.235),0,.94,0)

def create(rig,contour,clear_width,rear_entrance=False,subdivisions=1):
    """Open grounded band; keep approach lanes flat and the room completely clear."""
    points=[]
    for a,b in zip(contour,contour[1:]+contour[:1]):
        a,b=Vector(a),Vector(b)
        points.extend(a.lerp(b,i/subdivisions) for i in range(subdivisions))
    vertices=[];faces=[];n=len(points)
    for row,t in enumerate((0,.30,.65,1)):
        for i,p in enumerate(points):
            radius=1.05+.12*math.sin(i*1.73)+.12*math.cos(i*.77)
            radial=Vector((p.x,p.y,0)).normalized()
            v=p+radial*radius*t
            z=(0,.24,.12,0)[row]*(.8+.2*math.sin(i*.81))
            if abs(v.x)<clear_width/2 and (p.y<0 or rear_entrance):z=0
            vertices.append((v.x,v.y,z))
    for row in range(3):
        for i in range(n):
            j=(i+1)%n;faces.extend(((row*n+i,row*n+j,(row+1)*n+j),
                                 (row*n+i,(row+1)*n+j,(row+1)*n+i)))
    mesh=bpy.data.meshes.new(NAME+'_Mesh');mesh.from_pydata(vertices,[],faces);mesh.update()
    if sum(a.x*b.y-b.x*a.y for a,b in zip(points,points[1:]+points[:1]))>0:
        for polygon in mesh.polygons:polygon.flip()
    obj=bpy.data.objects.new(NAME,mesh);bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(bpy.data.materials[MATERIAL])
    obj.vertex_groups.new(name='Root').add(list(range(len(vertices))),1,'REPLACE')
    obj.parent=rig;obj.modifiers.new('Armature','ARMATURE').object=rig
    for face in mesh.polygons:face.use_smooth=True
    uv=mesh.uv_layers.new(name='SurfaceUV')
    lo=[min(p[i] for p in vertices) for i in range(2)];hi=[max(p[i] for p in vertices) for i in range(2)]
    for loop in mesh.loops:
        p=mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=((p.x-lo[0])/(hi[0]-lo[0]),(p.y-lo[1])/(hi[1]-lo[1]))
    from lunar_material import install
    install(mesh.materials[0])
    annotate(obj)
    return obj

def annotate(obj):
    obj.name=NAME;obj['optional']=True;obj['collision_role']='none'
    obj['purpose']='Optional lunar perimeter; toggle independently of architecture'

def metadata():
    return dict(object=NAME,material=MATERIAL,bone='Root',optional=True,collision=False,
                scope='visual apron only; excluded from building placement and traversal')

def update_report(report,meshes,kit):
    report['optional_surface']=metadata()
    report['meshes']={o.name:kit.triangles(o) for o in meshes}
    report['triangles']=sum(report['meshes'].values())
    report['materials']=sorted({o.data.materials[f.material_index].name for o in meshes for f in o.data.polygons})
    building=[o for o in meshes if o.name!=NAME]
    report['building_bounds_m']=dict(lo=[min(v.co[i] for o in building for v in o.data.vertices) for i in range(3)],
                                   hi=[max(v.co[i] for o in building for v in o.data.vertices) for i in range(3)])
    report['bounds_m']=dict(lo=[min(v.co[i] for o in meshes for v in o.data.vertices) for i in range(3)],
                          hi=[max(v.co[i] for o in meshes for v in o.data.vertices) for i in range(3)])
    assert report['triangles']<=report['triangle_budget'],report['triangles']

def install_material(kit):
    configure(kit)
    if MATERIAL not in kit.SLOTS:kit.SLOTS.append(MATERIAL)
    if MATERIAL not in bpy.data.materials:
        mat=bpy.data.materials.new(MATERIAL);mat.use_nodes=True
        node=mat.node_tree.nodes.get('Principled BSDF')
        node.inputs['Base Color'].default_value=(.27,.255,.235,1)
        node.inputs['Metallic'].default_value=0;node.inputs['Roughness'].default_value=.94
        mat.diffuse_color=(.27,.255,.235,1)

def refresh(here,name,kit,contour,clear_width,export,rear_entrance=False,subdivisions=1):
    import json
    bpy.ops.wm.open_mainfile(filepath=str(here/f'{name}.blend'))
    report=json.loads((here/f'{name}_rig.json').read_text());kit.SLOTS=report['materials']
    install_material(kit)
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    old=next((o for o in bpy.context.scene.objects if o.type=='MESH' and 'Regolith' in o.name),None)
    if old and contour:
        mesh=old.data;bpy.data.objects.remove(old,do_unlink=True);bpy.data.meshes.remove(mesh)
        old=None
    if old:annotate(old)
    else:create(rig,contour,clear_width,rear_entrance,subdivisions)
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
    markers=[o for o in bpy.context.scene.objects if o.type=='EMPTY']
    update_report(report,meshes,kit)
    export(rig,meshes,markers)
    (here/f'{name}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(here/f'{name}.blend'))
    print(f'[{name}] optional {NAME}; total {report["triangles"]} triangles',flush=True)
