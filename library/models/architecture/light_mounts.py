"""Surface-seated fixture attachment empties; no lamp geometry or illumination."""
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


EXTERIOR_ASSETS = ('bastion','bunker','cistern','hangar','lodge','laboratory','hub','habitat_pod')


def exterior_specs(name):
    """Outside-in rays in the generator's reference frame, centred on solid bays."""
    if name not in EXTERIOR_ASSETS:return []
    specs=[]
    if name in ('bastion','laboratory'):
        for side,axis,sign in [('Front',1,-1),('Rear',1,1),('Left',0,1),('Right',0,-1)]:
            offset=3.5
            bays=[('A',-offset),('B',offset)]
            for tag,t in bays:
                height=1.77
                p=[0,0,height];p[axis]=sign*12;p[1-axis]=t
                ray=[0,0,0];ray[axis]=-sign
                specs.append((side+tag,p,ray))
    elif name=='bunker':
        for tag,x,y in [('Left',1,0),('Right',-1,0),('Rear',0,1),('FrontLeft',1,-1),('FrontRight',-1,-1)]:
            specs.append((tag,(x*10,.30+y*10,1.4),(-x,-y,0)))
    elif name=='cistern':
        for tag,s in [('Left',1),('Right',-1)]:
            specs.append((tag,(s*12,0,1.7),(-s,0,0)))
    elif name=='hangar':
        for side,s in [('Front',-1),('Rear',1)]:
            for tag,x in [('Left',2.95),('Right',-2.95)]:
                specs.append((side+tag,(x,s*12,1.95),(0,-s,0)))
    elif name=='lodge':
        for side,s in [('Front',-1),('Rear',1)]:
            for tag,x in [('A',-3.5),('B',3.5)]:
                specs.append((side+tag,(x,s*12,1.8),(0,-s,0)))
    elif name=='hub':
        for tag,x,y in [('Front',0,-1),('Left',1,0),('Rear',0,1),('Right',-1,0)]:
            specs.append((tag,(x*8,y*8,3.33),(-x,-y,0)))
    elif name=='habitat_pod':
        for tag,s in [('Left',1),('Right',-1)]:
            specs.append((tag,(s*8,0,3.145),(-s,0,0)))
    return [('Exterior'+tag,origin,direction) for tag,origin,direction in specs]

def install(rig,meshes,ceiling,wall,absolute=False):
    name=rig.get('architecture_asset','')
    exterior=exterior_specs(name)
    if exterior:
        import dimensions
        exterior=[(tag,dimensions.point(name,origin),direction) for tag,origin,direction in exterior]
    if 'architecture_asset' in rig and not absolute:
        import dimensions
        name=rig['architecture_asset']
        ceiling=[(tag,dimensions.point(name,origin),direction) for tag,origin,direction in ceiling]
        wall=[(tag,dimensions.point(name,origin),direction) for tag,origin,direction in wall]
    wall=[*wall,*exterior]
    verts=[];faces=[];materials=[]
    for obj in meshes:
        start=len(verts);verts.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        for p in obj.data.polygons:
            if all(any(obj.vertex_groups[g.group].name=='Root' for g in obj.data.vertices[i].groups) for i in p.vertices):
                faces.append(tuple(start+i for i in p.vertices))
                materials.append(obj.data.materials[p.material_index].name)
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
            outside=tag.startswith('Exterior')
            if outside:
                assert normal.dot(-ray)>.5,('exterior wall facing',name,tag)
                assert hit.dot(-ray)>0,('exterior ray passed through building',name,tag)
                # The 430 x 300 mm backplate must sit flush on opaque wall,
                # with 100 mm horizontal and 75 mm vertical extra wall land.
                for u in (-.315,0,.315):
                    for v in (-.225,0,.225):
                        sample=hit+matrix.to_3x3()@Vector((u,0,v))
                        support,n,index,_=tree.ray_cast(sample+normal*.04,-normal,.08)
                        assert support is not None and (support-sample).length<.001,('exterior backplate clearance',name,tag,u,v)
                        assert abs(n.dot(normal))>.999,('exterior backplate flatness',name,tag)
                        assert 'Glass' not in materials[index] and 'Emissive' not in materials[index],('exterior solid wall',name,tag)
            node=bpy.data.objects.new(kind+tag,None);bpy.context.scene.collection.objects.link(node)
            node.parent=rig;node.parent_type='BONE';node.parent_bone='Root';node.matrix_world=matrix
            node.empty_display_type='ARROWS';node.empty_display_size=.20
            node['attachment']='batten_light' if kind.startswith('Batten') else 'sconce_light'
            node['purpose']='Separate fixture back mounted on actual '+('exterior' if outside else 'interior')+' architectural surface'
            node['surface']='exterior' if outside else 'interior'
            nodes.append(node)
            metadata.append(dict(name=node.name,bone='Root',origin=list(hit),mount_normal=list(normal),
                attachment=node['attachment'],surface=node['surface'],matrix_world=[list(row) for row in matrix]))
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
