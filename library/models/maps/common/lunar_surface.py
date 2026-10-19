"""One continuous regolith surface: no coplanar floor/dune join or square trench."""
import bpy,math,random

def build(name,flat_radius=60,protected=()):
    """Continuous crater bowl; low faceted stones, irregular raised ejecta rim.

    Interior stones peak at 24 cm with shallow approaches. Protected native
    fixture/architecture seating regions stay exactly on the authored zero plane.
    """
    rng=random.Random(92317+round(flat_radius*100));steps=128;vertices=[(0,0,0)];faces=[]
    stones=[]
    for i in range(round(math.pi*flat_radius**2/38)):
        angle=rng.uniform(0,math.tau);radius=flat_radius*math.sqrt(rng.random())
        stones.append((math.cos(angle)*radius,math.sin(angle)*radius,rng.uniform(1.2,2.4),rng.uniform(.035,.24),rng.uniform(0,math.tau)))
    def relief(x,y):
        if any((x-a)**2+(y-b)**2<r*r for a,b,r in protected):return 0
        height=0
        for cx,cy,r,h,rot in stones:
            dx=x-cx;dy=y-cy
            if abs(dx)>r*1.3 or abs(dy)>r*1.3:continue
            u=(math.cos(rot)*dx+math.sin(rot)*dy)/r;v=(-math.sin(rot)*dx+math.cos(rot)*dy)/(r*.72)
            # Angular octahedral stones belong to the continuous terrain skin.
            profile=max(abs(u),abs(v),abs(u+v)/1.45,abs(u-v)/1.45)
            height=max(height,h*max(0,1-profile))
        return height
    rings=[(flat_radius*i/max(1,math.ceil(flat_radius/1.5)),0) for i in range(1,max(1,math.ceil(flat_radius/1.5))+1)]
    rings.extend([(flat_radius+4,.15),(flat_radius+10,2.2),(flat_radius+17,8.5),
                  (flat_radius+23,11),(flat_radius+31,6.5),(flat_radius+43,1.2),
                  (flat_radius+62,.2),(160,.12),(230,0)])
    for row,(radius,height) in enumerate(rings):
        for i in range(steps):
            angle=math.tau*i/steps
            rim=.52*math.sin(5*angle+.4)+.31*math.sin(11*angle+1.1)+.17*math.sin(19*angle-.7)
            detail=math.sin(31*angle+row*.62)*.13
            r=radius+(rim*3+detail if radius>flat_radius else math.sin(17*angle+row*.37)*.12)
            x,y=math.cos(angle)*r,math.sin(angle)*r
            z=relief(x,y) if radius<=flat_radius else max(0,height*(1+rim*.30+detail*.35))
            vertices.append((x,y,z))
    for i in range(steps):faces.append((0,1+i,1+(i+1)%steps))
    for row in range(len(rings)-1):
        for i in range(steps):
            a=1+row*steps+i;b=1+row*steps+(i+1)%steps;faces.append((a,a+steps,b+steps,b))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    solid=ob.modifiers.new('continuous buried terrain volume','SOLIDIFY');solid.thickness=2;solid.offset=-1
    bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=solid.name)
    # The broad height field alone cannot resolve small gravel. Add actual
    # closed, faceted stones on clear interior land, with buried bases and
    # walkable peaks. They belong to this separate scenery asset/collider.
    mesh=ob.data
    vertices=[tuple(v.co) for v in mesh.vertices];faces=[tuple(p.vertices) for p in mesh.polygons]
    placed=[]
    for attempt in range(round(math.pi*flat_radius**2/18)):
        angle=rng.uniform(0,math.tau);radius=(flat_radius-2)*math.sqrt(rng.random())
        cx,cy=math.cos(angle)*radius,math.sin(angle)*radius
        size=rng.uniform(.09,.28) if rng.random()<.8 else rng.uniform(.35,.7)
        if any((cx-a)**2+(cy-b)**2<(r+size+.3)**2 for a,b,r in protected):continue
        if any((cx-a)**2+(cy-b)**2<(size+r+.06)**2 for a,b,r in placed):continue
        if relief(cx,cy)>.015:continue
        peak=min(.24,rng.uniform(.03,.10) if size<.3 else rng.uniform(.12,.22))
        start=len(vertices);turn=rng.uniform(0,math.tau);n=6
        outline=[]
        for i in range(n):
            a=turn+math.tau*i/n;s=size*rng.uniform(.8,1.15)
            outline.append((cx+math.cos(a)*s,cy+math.sin(a)*s*.75))
        if any(relief(x,y)>.015 for x,y in outline):continue
        vertices.extend((x,y,relief(x,y)-.02) for x,y in outline)
        vertices.extend((cx+(x-cx)*.82,cy+(y-cy)*.82,peak*rng.uniform(.55,.82)) for x,y in outline)
        top=len(vertices);vertices.append((cx+size*.12,cy-size*.08,peak))
        faces.append(tuple(start+i for i in reversed(range(n))))
        for i in range(n):
            j=(i+1)%n
            faces.extend(((start+i,start+j,start+n+j,start+n+i),(start+n+i,start+n+j,top)))
        placed.append((cx,cy,size))
    detailed=bpy.data.meshes.new(name+'_Detailed');detailed.from_pydata(vertices,[],faces);detailed.update()
    ob.data=detailed;bpy.data.meshes.remove(mesh)
    for polygon in ob.data.polygons:polygon.use_smooth=False
    ob['terrain_style']='irregular crater bowl with raised ejecta rim and low faceted stones'
    ob['maximum_interior_stone_height_m']=.24
    ob['interior_gravel_stone_count']=len(placed)
    return ob

def apply_materials(ob,preserve_partition=False):
    """Uniform paint across UV partitions; lunar texture supplies continuous tones."""
    palette=[(name,(.29,.30,.31)) for name in ('M_Regolith','M_RegolithLight','M_RegolithDark')]
    old_names=[ob.data.materials[f.material_index].name.split('.')[0] for f in ob.data.polygons] if preserve_partition else []
    ob.data.materials.clear()
    for name,color in palette:
        mat=bpy.data.materials.get(name) or bpy.data.materials.new(name);mat.use_nodes=True
        mat.diffuse_color=(*color,1)
        shader=mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value=(*color,1);shader.inputs['Roughness'].default_value=.95
        for link in list(shader.inputs['Base Color'].links):mat.node_tree.links.remove(link)
        ob.data.materials.append(mat)
    old_tint=ob.data.color_attributes.get('RegolithTint')
    if old_tint:ob.data.color_attributes.remove(old_tint)
    for index,face in enumerate(ob.data.polygons):
        if preserve_partition:
            face.material_index=[name for name,_ in palette].index(old_names[index]);continue
        x,y=face.center.x,face.center.y
        tone=math.sin(x*.14+.3)*math.cos(y*.11)+.35*math.sin((x+y)*.26)
        face.material_index=1 if tone>.55 else 2 if tone<-.55 else 0

    from lunar_material import install
    for mat in ob.data.materials:install(mat)
