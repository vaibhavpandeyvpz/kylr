"""Static floating ground-piece family. Metres, deck z=0, front -Y.

Only load-bearing platform geometry is exported. Fixtures are named placements.
"""
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
MODELS = HERE.parents[2]
sys.path.insert(0, str(MODELS / 'architecture'))
sys.path.insert(0, str(MODELS / 'environments'))
import light_common as common
kit = common.kit
DEPTH = .8
TRI_BUDGET = 10000


from platform_placements import thruster_positions


def sconce_positions(length):
    """Mirror-symmetric equal spacing, 1.1 m corner inset on every edge."""
    if length<2.2:return []
    count=max(1,math.ceil((length-2.2)/4.5)+1)
    if count==1:return [0.0]
    span=length-2.2
    return [-span/2+span*i/(count-1) for i in range(count)]




def fascia_recesses(length,with_lamps=True):
    """Symmetric service panels occupy the clear gaps between lamp lands."""
    count=max(1,int(length//10)) if length!=20 else 1
    if count==1:return [0.0]
    lamps=sconce_positions(length) if with_lamps else []
    gaps=[(a+b)/2 for a,b in zip(lamps,lamps[1:]) if a+b>0]
    center=min(gaps,key=lambda p:abs(p-length/4)) if gaps else length/4
    return [-center,center]

REGOLITH_CUTOUT_GAP_M = .20

def residue(rig,panels,d,cutouts=()):
    """Seeded irregular lunar residue, 1.5–60 mm relief, wholly on the deck."""
    import random
    import perimeter_surface as surface
    xmin=min(p[0] for p in panels);xmax=max(p[2] for p in panels)
    ymin=min(p[1] for p in panels);ymax=max(p[3] for p in panels)
    width,height=xmax-xmin,ymax-ymin
    rng=random.Random(53117+int(d)*37+round(width*101))
    deposits=[]
    # Deposits belong to the whole deck, never to its tile lattice. Sparse
    # elongated drifts cross seams; satellites gather around only some drifts.
    count=max(1,round(width*height/65))
    specs=[]
    for index in range(count):
        cx=rng.uniform(xmin+width*.20,xmax-width*.20)
        cy=rng.uniform(ymin+height*.20,ymax-height*.20)
        rx=rng.uniform(.6,1.65)*min(1,width/3)
        ry=rng.uniform(.26,.72)*min(1,height/3)
        if count==1:rx=min(width*.36,rx*1.5);ry=min(height*.24,ry*1.4)
        specs.append((cx,cy,rx,ry,rng.uniform(0,math.tau)))
        if rng.random()<.55:
            specs.append((cx+rng.uniform(-rx,rx),cy+rng.uniform(-ry,ry),
                          rx*rng.uniform(.18,.4),ry*rng.uniform(.25,.5),rng.uniform(0,math.tau)))
    for cx,cy,rx,ry,rotation in specs:
            # Reject complete deposits near native cutouts, retaining feathered rims.
            radius=1.5*max(rx,ry)
            blocked=False
            for hole in cutouts:
                hx,hy,_=hole["center"]; yaw=hole.get("yaw",0)
                dx=cx-hx;dy=cy-hy
                u=math.cos(yaw)*dx+math.sin(yaw)*dy
                v=-math.sin(yaw)*dx+math.cos(yaw)*dy
                hw,hh=hole["size"]
                if abs(u)<hw/2+.001+REGOLITH_CUTOUT_GAP_M+radius and abs(v)<hh/2+.001+REGOLITH_CUTOUT_GAP_M+radius:
                    blocked=True;break
            if blocked:continue
            vertices=[];faces=[]
            n=24;start=len(vertices);outline=[]
            phase=rng.uniform(0,math.tau)
            for i in range(n):
                angle=2*math.pi*i/n
                radius=1+.24*math.sin(3*angle+phase)+.15*math.sin(5*angle-phase)+rng.uniform(-.08,.08)
                u=rx*radius*math.cos(angle);v=ry*radius*math.sin(angle)
                outline.append((cx+u*math.cos(rotation)-v*math.sin(rotation),
                                cy+u*math.sin(rotation)+v*math.cos(rotation)))
            peak=rng.uniform(.018,.058)
            for row,t in enumerate((1,.72,.30)):
                for x,y in outline:
                    z=.0015 if row==0 else peak*rng.uniform(*((.14,.30) if row==1 else (.6,.86)))
                    vertices.append((cx+(x-cx)*t,cy+(y-cy)*t,z))
            center=len(vertices);vertices.append((cx,cy,peak))
            for i in range(n):
                j=(i+1)%n
                for row in range(2):
                    a=start+row*n;b=a+n
                    faces.extend(((a+i,a+j,b+j),(a+i,b+j,b+i)))
                faces.append((start+2*n+i,start+2*n+j,center))
            # Boolean solid deposits, rather than intersecting open sheets.
            # Their hidden flat bases sit inside the deck; visible relief stays
            # above it. Union removes every overlapping internal surface.
            bottom=len(vertices)
            vertices.extend((x,y,-.01) for x,y in outline)
            faces.append(tuple(bottom+i for i in reversed(range(n))))
            for i in range(n):
                j=(i+1)%n;faces.append((i,bottom+i,bottom+j,j))
            mesh=bpy.data.meshes.new(surface.NAME+'_Deposit');mesh.from_pydata(vertices,[],faces);mesh.update()
            obj=bpy.data.objects.new('TEMP_RegolithDeposit',mesh);bpy.context.scene.collection.objects.link(obj)
            mesh.materials.append(bpy.data.materials[surface.MATERIAL]);deposits.append(obj)
    from map_shells import boolean
    if not deposits:
        mesh=bpy.data.meshes.new(surface.NAME+"_Empty")
        obj=bpy.data.objects.new(surface.NAME,mesh);bpy.context.scene.collection.objects.link(obj)
        mesh.materials.append(bpy.data.materials[surface.MATERIAL]);deposits.append(obj)
    obj=deposits[0]
    for other in deposits[1:]:boolean(obj,other,'UNION')
    obj.name=surface.NAME;mesh=obj.data
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()
    # These low-relief facets use their actual face normals. Smooth shading
    # would blend the buried underside into the visible feathered rim.
    for polygon in mesh.polygons:polygon.use_smooth=False
    from lunar_material import install
    install(bpy.data.materials[surface.MATERIAL])
    obj.vertex_groups.new(name='Root').add(list(range(len(mesh.vertices))),1,'REPLACE')
    obj.parent=rig;obj.modifiers.new('Armature','ARMATURE').object=rig
    obj['optional']=True;obj['collision_role']='none'
    obj['purpose']='Shallow scattered lunar residue on the mechanical deck; independently toggleable'
    obj['surface_construction']='Boolean-unioned solid deposits; no overlapping sheets'
    return obj


def split_large(body,rig,title):
    """Retain the default 5K ceiling per render mesh inside the 10K model budget."""
    if kit.triangles(body)<=5000:return [body]
    out=[]
    for tag,selected in [('',list(body.data.polygons))]:
        batches=[];batch=[];count=0
        for polygon in selected:
            n=len(polygon.vertices)-2
            if batch and count+n>4800:
                batches.append(batch);batch=[];count=0
            batch.append(polygon);count+=n
        if batch:batches.append(batch)
        for i,selected in enumerate(batches):
            part_tag=tag if i==0 else tag+str(i+1).zfill(2)
            indices=sorted({i for p in selected for i in p.vertices});lookup={old:i for i,old in enumerate(indices)}
            mesh=bpy.data.meshes.new('SK_'+title+part_tag+'_Mesh')
            mesh.from_pydata([body.data.vertices[i].co for i in indices],[],
                             [[lookup[i] for i in p.vertices] for p in selected]);mesh.update()
            for material in body.data.materials:mesh.materials.append(material)
            for poly,source in zip(mesh.polygons,selected):poly.material_index=source.material_index;poly.use_smooth=source.use_smooth
            for source_color in body.data.color_attributes:
                target=mesh.color_attributes.new(name=source_color.name,type=source_color.data_type,domain=source_color.domain)
                if source_color.domain=='POINT':
                    for new,old in enumerate(indices):target.data[new].color=source_color.data[old].color
                elif source_color.domain=='CORNER':
                    for polygon,source in zip(mesh.polygons,selected):
                        for new,old in zip(polygon.loop_indices,source.loop_indices):target.data[new].color=source_color.data[old].color
            # Map recess machining can split already-atlased native meshes.
            for source_uv in body.data.uv_layers:
                target_uv=mesh.uv_layers.new(name=source_uv.name)
                for polygon,source in zip(mesh.polygons,selected):
                    for new_loop,old_loop in zip(polygon.loop_indices,source.loop_indices):
                        target_uv.data[new_loop].uv=source_uv.data[old_loop].uv
            mesh.set_sharp_from_angle(angle=math.radians(40))
            obj=bpy.data.objects.new('SK_'+title+part_tag,mesh);bpy.context.scene.collection.objects.link(obj)
            obj.vertex_groups.new(name='Root').add(list(range(len(indices))),1,'REPLACE')
            obj.parent=rig;obj.modifiers.new('Armature','ARMATURE').object=rig
            assert kit.triangles(obj)<=5000,(obj.name,kit.triangles(obj))
            out.append(obj)
    bpy.data.objects.remove(body,do_unlink=True)
    return out


def export(objects, path):
    kit.select_only(objects)
    bpy.ops.export_scene.fbx(filepath=str(path.with_suffix('.fbx')), use_selection=True,
        object_types={'MESH', 'ARMATURE', 'EMPTY'}, global_scale=1, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
        use_mesh_modifiers=False, mesh_smooth_type='OFF', add_leaf_bones=False,
        primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=True,
        bake_anim=False, path_mode='COPY', embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')), export_format='GLB',
        use_selection=True, export_yup=True, export_apply=False, export_skins=True,
        export_def_bones=True, export_animations=False, export_materials='EXPORT', export_extras=True)
