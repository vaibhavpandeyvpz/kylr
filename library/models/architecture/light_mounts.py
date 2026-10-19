"""Surface-seated fixture attachment empties; no lamp geometry or illumination."""
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

def install(rig,meshes,ceiling,wall,absolute=False):
    if 'architecture_asset' in rig and not absolute:
        import dimensions
        name=rig['architecture_asset']
        ceiling=[(tag,dimensions.point(name,origin),direction) for tag,origin,direction in ceiling]
        wall=[(tag,dimensions.point(name,origin),direction) for tag,origin,direction in wall]
    verts=[];faces=[]
    for obj in meshes:
        start=len(verts);verts.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        for p in obj.data.polygons:
            if all(any(obj.vertex_groups[g.group].name=='Root' for g in obj.data.vertices[i].groups) for i in p.vertices):
                faces.append(tuple(start+i for i in p.vertices))
    tree=BVHTree.FromPolygons(verts,faces)
    for old in list(bpy.data.objects):
        if old.type=='EMPTY' and (old.name.startswith(('BattenLightMount','SconceLightMount','InteriorLight'))):
            bpy.data.objects.remove(old,do_unlink=True)
    nodes=[];metadata=[]
    for kind,specs in (('BattenLightMount',ceiling),('SconceLightMount',wall)):
        for tag,origin,direction in specs:
            ray=Vector(direction).normalized()
            hit,normal,face,distance=tree.ray_cast(Vector(origin),ray,30)
            assert hit is not None,('missing fixture support',kind,tag)
            normal=-normal if normal.dot(ray)>0 else normal
            normal.normalize()
            up=Vector((0,1,0)) if kind.startswith('Batten') or abs(normal.z)>.95 else Vector((0,0,1))
            up=(up-normal*up.dot(normal)).normalized()
            if kind.startswith('Batten'):
                back=-normal
                matrix=Matrix((up.cross(back),up,back)).transposed().to_4x4()
            else:
                back=-normal
                matrix=Matrix((back.cross(up),back,up)).transposed().to_4x4()
            matrix.translation=hit
            node=bpy.data.objects.new(kind+tag,None);bpy.context.scene.collection.objects.link(node)
            node.parent=rig;node.parent_type='BONE';node.parent_bone='Root';node.matrix_world=matrix
            node.empty_display_type='ARROWS';node.empty_display_size=.20
            node['attachment']='batten_light' if kind.startswith('Batten') else 'sconce_light'
            node['purpose']='Separate fixture mount on actual interior architectural surface'
            nodes.append(node)
            metadata.append(dict(name=node.name,bone='Root',origin=list(hit),mount_normal=list(normal),
                attachment=node['attachment'],matrix_world=[list(row) for row in matrix]))
    return nodes,metadata


def default_specs(name):
    """Reference-coordinate plans shared by full native builds and mount refreshes."""
    if name.startswith('container'):
        ceiling=[('Center',(0,0,2.0),(0,0,1))] if name=='container' else [(tag,(0,y,2.0),(0,0,1)) for tag,y in [('Front',-1.6),('Rear',1.6)]]
        return ceiling,[]
    if name=='habitat_pod':return [('Center',(0,0,2.5),(0,0,1))],[]
    if name=='lunar_dome':return [],[('TopCenter',(0,0,2.7),(0,0,1))]
    raise KeyError(name)

def install_default(rig,meshes,name):
    return install(rig,meshes,*default_specs(name))
