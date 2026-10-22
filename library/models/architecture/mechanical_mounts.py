"""Reversible pillar pedestal and forward-facing recessed weapon-holder block."""
import json
import math
import sys
import importlib.util
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix,Vector

MODELS=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(MODELS))
from material_uv import prepare_export
CLEARANCE=.001


def box(name,lo,hi,material=None):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob=bpy.context.object;ob.name=name
    ob.location=(Vector(lo)+Vector(hi))/2;ob.scale=Vector(hi)-Vector(lo)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if material:ob.data.materials.append(material)
    return ob


def cut(ob,tool):
    bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new('Machined pocket','BOOLEAN')
    mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=tool;mod.material_mode='TRANSFER'
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool,do_unlink=True)


def prop_materials():
    # Source palette owns colour, metalness, roughness and emission together.
    spec=importlib.util.spec_from_file_location('mount_prop_palette',MODELS/'gameplay/item_table/model.py')
    kit=importlib.util.module_from_spec(spec);sys.modules[spec.name]=kit;spec.loader.exec_module(kit)
    kit.build_materials()
    return bpy.data.materials['M_Primary'],bpy.data.materials['M_Frame']


def rig_and_skin(objects,title):
    arm=bpy.data.armatures.new(title+'Rig');rig=bpy.data.objects.new('RIG_'+title,arm)
    bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig
    rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    b=arm.edit_bones.new('Root');b.head=(0,0,0);b.tail=(0,0,.2)
    bpy.ops.object.mode_set(mode='OBJECT')
    for ob in objects:
        ob.parent=rig;g=ob.vertex_groups.new(name='Root');g.add(list(range(len(ob.data.vertices))),1,'REPLACE')
        ob.modifiers.new('Rigid mounting casting','ARMATURE').object=rig
    return rig


def export(folder,stem,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(folder/f'{stem}.glb'),export_format='GLB',use_selection=True,
        export_skins=True,export_animations=False,export_extras=True)
    bpy.ops.export_scene.fbx(filepath=str(folder/f'{stem}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE','EMPTY'},axis_forward='-Z',axis_up='Y',add_leaf_bones=False,bake_anim=False)


def socket(rig,name,at,rotation,attachment):
    ob=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(ob)
    ob.parent=rig;ob.parent_type='BONE';ob.parent_bone='Root'
    bpy.context.view_layer.update()
    ob.matrix_world=Matrix.Translation(Vector(at))@rotation
    ob.empty_display_type='ARROWS';ob.empty_display_size=.2;ob['attachment']=attachment
    return ob


def pocket(ob,frame,w,h,depth,dark,bevel=.012):
    tool=box('CUT_ServicePocket',(-w/2,-h/2,-depth),(w/2,h/2,.01),dark)
    if bevel:
        bpy.context.view_layer.objects.active=tool
        mod=tool.modifiers.new('Formed recess shoulder','BEVEL');mod.width=bevel;mod.segments=1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    tool.matrix_world=frame@tool.matrix_world
    cut(ob,tool)


DETAIL_PARTS=[]


def formed_plate(name,w,h,z0,z1,material):
    # Platform-family chamfered panel outline and 45-degree formed rim.
    verts=[];faces=[]
    for ww,hh,z,c in ((w,h,z0,.018),(w,h,z1-.006,.018),(w-.012,h-.012,z1,.014)):
        x,y=ww/2,hh/2
        verts.extend((u,v,z) for u,v in ((-x+c,-y),(x-c,-y),(x,-y+c),(x,y-c),(x-c,y),(-x+c,y),(-x,y-c),(-x,-y+c)))
    faces=[tuple(reversed(range(8))),tuple(range(16,24))]
    for j in range(2):
        for i in range(8):k=(i+1)%8;faces.append((8*j+i,8*j+k,8*(j+1)+k,8*(j+1)+i))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob);mesh.materials.append(material)
    return ob


def details(ob,frames,dark,width,height):
    # Real fitted access plates and retained hex fasteners, matching platform
    # underside construction rather than colour-coded cuts into a solid block.
    for frame in frames:
        pocket(ob,frame,width,height,.040,dark,.018)
        cover=formed_plate('ServiceCover',width-.008,height-.008,-.040,-.012,bpy.data.materials['M_Joint'])
        cover.data.materials.append(dark)
        for y in (-height*.18,0,height*.18):
            pocket(cover,Matrix.Translation(Vector((0,y,-.012))),width*.58,.018,.008,dark,.003)
        cover.matrix_world=frame;DETAIL_PARTS.append(cover)
        for x in (-width*.39,width*.39):
            for y in (-height*.33,height*.33):
                bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=.009,depth=.006,location=(x,y,-.009))
                head=bpy.context.object;head.name='CaptiveHexFastener';head.data.materials.append(bpy.data.materials['M_Joint'])
                head.matrix_world=frame@head.matrix_world;DETAIL_PARTS.append(head)


def service_bay(ob,frame,height,dark,well_material):
    # Closed service well, supported stainless thermal line with compression
    # unions and retaining clamps, as on the native tapered platform chassis.
    pocket(ob,frame,.25,height,.065,well_material,.018)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=.018,depth=height*.72,location=(0,0,-.036))
    pipe=bpy.context.object;pipe.name='ThermalReturn';pipe.rotation_euler.x=math.pi/2
    pipe.data.materials.append(bpy.data.materials['M_Joint']);bpy.context.view_layer.update();pipe.matrix_world=frame@pipe.matrix_world;DETAIL_PARTS.append(pipe)
    for y in (-height*.34,height*.34):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.029,depth=.045,location=(0,y,-.036))
        union=bpy.context.object;union.name='CompressionUnion';union.rotation_euler.x=math.pi/2
        union.data.materials.append(bpy.data.materials['M_Joint']);bpy.context.view_layer.update();union.matrix_world=frame@union.matrix_world;DETAIL_PARTS.append(union)
        foot=box('BulkheadSeat',(-.044,y-.031,-.065),(.044,y+.031,-.030),bpy.data.materials['M_Secondary'])
        # Seats stop below the line: avoid intersecting the finished pipe.
        cut(foot,box('CUT_LineBore',(-.032,y-.04,-.062),(.032,y+.04,-.010),dark))
        foot.matrix_world=frame@foot.matrix_world;DETAIL_PARTS.append(foot)
    clamp=box('RetainingSaddle',(-.055,-.024,-.065),(.055,.024,-.052),bpy.data.materials['M_Secondary'])
    clamp.matrix_world=frame@clamp.matrix_world;DETAIL_PARTS.append(clamp)


def lodge_roof_unit():
    spec=importlib.util.spec_from_file_location('mount_lodge_roof',MODELS/'architecture/lodge/model.py')
    lodge=importlib.util.module_from_spec(spec);sys.modules[spec.name]=lodge;spec.loader.exec_module(lodge)
    lodge.common.CORNER_STEPS=1;lodge.common.LABELS.clear()
    # Lodge's existing service-indicator material contract.
    indicator=bpy.data.materials['M_Emissive'];shader=indicator.node_tree.nodes['Principled BSDF']
    indicator.diffuse_color=(.025,.55,.62,1)
    for socket_name in ('Base Color','Emission Color'):shader.inputs[socket_name].default_value=(.025,.55,.62,1)
    shader.inputs['Emission Strength'].default_value=1.5
    k=lodge.kit.Kit() if hasattr(lodge.kit,'Kit') else lodge.kit.Geometry()
    lodge.equipment(k,0,0,1.8,1.6)
    # Fuse the two exact collar/pedestal bearing lands. Their native separate
    # parts share full contact rectangles; remove both buried interfaces before
    # welding, so the delivery remains a closed solid after import seam welding.
    low=4.12-.051*math.sqrt(3)/2
    contacts=[]
    for yy in (-.65,.20):
        contacts.extend(f for f in k.bm.faces if all(abs(v.co.z-low)<1e-5 and
            abs(v.co.x-1.16)<=.02551 and abs(v.co.y-yy)<=.02501 for v in f.verts))
    assert len(contacts)==8,len(contacts)
    bmesh.ops.delete(k.bm,geom=contacts,context='FACES')
    bmesh.ops.remove_doubles(k.bm,verts=list(k.bm.verts),dist=1e-6)
    assert all(e.is_manifold for e in k.bm.edges),'Roof bearing-land union'
    # Retain closed source parts: this smaller exposed assembly needs its
    # underside surfaces, including those culled against the lodge's roof.
    mesh=bpy.data.meshes.new('RoofServiceUnit');k.bm.to_mesh(mesh);k.bm.free()
    obj=bpy.data.objects.new('RoofServiceUnit',mesh);bpy.context.collection.objects.link(obj)
    for slot in lodge.kit.SLOTS:mesh.materials.append(bpy.data.materials[slot])
    mesh.set_sharp_from_angle(angle=lodge.kit.SHARP_ANGLE)
    lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    zscale=1/(hi[0]-lo[0])
    for v in obj.data.vertices:
        v.co.x=(v.co.x-(lo[0]+hi[0])/2)/(hi[0]-lo[0])
        v.co.y=(v.co.y-(lo[1]+hi[1])/2)/(hi[1]-lo[1])
        v.co.z=2+(v.co.z-lo[2])*zscale
    return obj


def build(folder):
    DETAIL_PARTS.clear()
    name=folder.name;pillar=name=='pillar_platform';title=''.join(x.title() for x in name.split('_'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC'
    primary,dark=prop_materials()
    if pillar:
        # Native container rail profile: wider end bands, formed transitions,
        # chamfered corner posts and genuine three-face lifting pockets.
        kit=sys.modules['mount_prop_palette'];grey=bpy.data.materials['M_Secondary']
        rings=[]
        for w,c,z in ((1,.012,-.5),(1,.012,-.482),(.972,.010,-.465),(.972,.010,.465),(1,.012,.482),(1,.012,.5)):
            h=w/2
            rings.append([(-h+c,-h,z),(h-c,-h,z),(h,-h+c,z),(h,h-c,z),(h-c,h,z),(-h+c,h,z),(-h,h-c,z),(-h,-h+c,z)])
        bm=kit.loft_rings(rings);mesh=bpy.data.meshes.new(title);bm.to_mesh(mesh);bm.free()
        ob=bpy.data.objects.new('SK_'+title,mesh);bpy.context.collection.objects.link(ob)
        mesh.materials.append(grey);mesh.materials.append(primary)
        cut(ob,box('CUT_HollowFrame',(-.38,-.38,-.38),(.38,.38,.38),grey))
        for angle in (0,math.pi/2,math.pi,3*math.pi/2):
            tool=box('CUT_FrameWindow',(-.38,-.51,-.38),(.38,-.379,.38),grey)
            tool.matrix_world=Matrix.Rotation(angle,4,'Z')@tool.matrix_world
            cut(ob,tool)
        for x in (-.443,.443):
            for y in (-.443,.443):
                for sign in (-1,1):
                    z=sign*.458
                    ya,yb=(-.51,-.416) if y<0 else (.416,.51)
                    cut(ob,box('CUT_CornerLiftSide',(x-.020,ya,z-.015),(x+.020,yb,z+.015),grey))
                    xa,xb=(-.51,-.416) if x<0 else (.416,.51)
                    cut(ob,box('CUT_CornerLiftEnd',(xa,y-.020,z-.015),(xb,y+.020,z+.015),grey))
                    za,zb=(-.51,-.44) if sign<0 else (.44,.51)
                    cut(ob,box('CUT_CornerLiftTop',(x-.020,y-.020,za),(x+.020,y+.020,zb),grey))
        for face in ob.data.polygons:
            face.material_index=0  # Solid end faces and border share the native grey frame finish.
        # Use the container's six-station fold profile, including real 8 mm
        # sheet thickness; corrugations stay recessed behind the load frame.
        kit=sys.modules['mount_prop_palette']
        for angle in (0,math.pi/2,math.pi,3*math.pi/2):
            profile=[]
            for i in range(6):
                start=-.38+.76*i/6
                for t,depth_fold in ((0,0),(.16,0),(.32,.025),(.68,.025),(.84,0),(1,0)):
                    point=(start+.76*t/6,depth_fold)
                    if not profile or point!=profile[-1]:profile.append(point)
            polygon=[(x,0,z) for x,z in profile]+[(x,0,z-.008) for x,z in reversed(profile)]
            bm=kit.prism_bm(polygon,.76,(0,1,0))
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            mesh=bpy.data.meshes.new('CorrugatedSheet');bm.to_mesh(mesh);bm.free()
            panel=bpy.data.objects.new('CorrugatedSidePanel',mesh);bpy.context.collection.objects.link(panel)
            mesh.materials.append(primary)
            panel.matrix_world=Matrix.Rotation(angle,4,'Z')@Matrix.Translation(Vector((0,-.435,0)))@Matrix.Rotation(math.pi/2,4,'X')
            DETAIL_PARTS.append(panel)
        specs=[('PillarMountTop',(0,0,.5),Matrix.Identity(4),'pillar'),
               ('PillarMountBottom',(0,0,-.5),Matrix.Rotation(math.pi,4,'X'),'pillar')]
        bounds=[[-.5]*3,[.5]*3];depth=None
    else:
        holder=json.loads((MODELS/'gameplay/weapon_holder/weapon_holder_rig.json').read_text(encoding='utf-8'))
        depth=holder['cutout_m']['depth']+CLEARANCE
        ob=box('SK_'+title,(-1,-1,0),(1,1,2),primary)
        ob.data.materials.append(dark)
        tool=box('CUT_WeaponHolderEnvelope',(-.501,-1.01,.499),(.501,-1+depth,1.501),dark)
        cut(ob,tool)
        # Plain front lands around the opening; mechanical side service panels.
        front=Matrix.Rotation(math.pi/2,4,'X')
        for x,sign in ((1,1),(-1,-1)):
            side=Matrix.Translation(Vector((x,0,1)))@Matrix(((0,sign,0),(0,0,1),(sign,0,0))).transposed().to_4x4()
            details(ob,[side],dark,.63,1.17)
            for offset in (-.65,.65):
                service_bay(ob,side@Matrix.Translation(Vector((offset,0,0))),1.20,dark,primary)
        # Lower strakes remain; the top receives the lodge service assembly.
        for z,rot in ((0,Matrix.Rotation(math.pi,4,'X')),):
            for x in (-.72,.72):
                pocket(ob,Matrix.Translation(Vector((x,0,z)))@rot,.14,1.55,.018,dark,.006)
        specs=[('WeaponHolderMount',(0,-1,1),front,'weapon_holder')]
        bounds=[[-1,-1,0],[1,1,2]]
    roof=None
    if not pillar:
        roof=lodge_roof_unit()
        DETAIL_PARTS.append(roof)
        bounds[1][2]=max(v.co.z for v in roof.data.vertices)
    # Join closed fitted parts without discarding native material assignments.
    if DETAIL_PARTS:
        bpy.ops.object.select_all(action='DESELECT')
        for part in [ob,*DETAIL_PARTS]:part.select_set(True)
        bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
    # Recalculate winding after exact Boolean machining.
    bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
    bpy.context.view_layer.update()
    points=[ob.matrix_world@v.co for v in ob.data.vertices]
    assert all(abs(min(p[i] for p in points)-bounds[0][i])<1e-6 and abs(max(p[i] for p in points)-bounds[1][i])<1e-6 for i in range(3)),[(min(p[i] for p in points),max(p[i] for p in points)) for i in range(3)]
    rig=rig_and_skin([ob],title)
    sockets=[socket(rig,*s) for s in specs]
    tris=sum(len(p.vertices)-2 for p in ob.data.polygons);assert tris<=5000,tris
    prepare_export([rig,ob,*sockets],folder,name)
    export(folder,name,[rig,ob,*sockets])
    report=dict(name=name,static=True,animations=[],triangles=tris,triangle_budget=5000,
        bounds_m=dict(lo=bounds[0],hi=bounds[1]),origin='block centre' if pillar else 'floor centre',
        bones=[dict(name='Root',kind='fixed')],materials_source='gameplay/item_table/model.py MATERIALS',recess_clearance_per_side_m=CLEARANCE,
        block_dimensions_m=[1,1,1] if pillar else [2,2,2],
        roof_equipment=None if pillar else dict(source='lodge/model.py equipment()',footprint_m=[1,1],base_z_m=2,height_m=bounds[1][2]-2),
        cavity_depth_m=depth,gizmos=[dict(name=s.name,attachment=s['attachment'],bone='Root',
        matrix_world=[list(r) for r in s.matrix_world],origin=list(s.matrix_world.translation)) for s in sockets],
        preview_only='Separate native fixture imported onto attachment gizmo; not exported')
    (folder/f'{name}_rig.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/f'{name}.blend'),compress=True)
    print(name,'BUILD PASS',tris,'triangles')


def collision(folder):
    name=folder.name;pillar=name=='pillar_platform'
    report=json.loads((folder/f'{name}_rig.json').read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if pillar:
        slabs=[((-.5,-.5,-.5),(.5,.5,-.38)),((-.5,-.5,.38),(.5,.5,.5))]
        for x in (-.486,.38):
            for y in (-.486,.38):slabs.append(((x,y,-.38),(x+.106,y+.106,.38)))
        slabs.extend([((-.38,-.460,-.38),(.38,-.427,.38)),
                      ((-.38,.427,-.38),(.38,.460,.38)),
                      ((-.460,-.38,-.38),(-.427,.38,.38)),
                      ((.427,-.38,-.38),(.460,.38,.38))])
        shapes=[box('proxy',a,b) for a,b in slabs]
    else:
        rear=-1+report['cavity_depth_m']
        slabs=[((-1,-1,0),(-.501,1,2)),((.501,-1,0),(1,1,2)),
               ((-.501,-1,0),(.501,1,.499)),((-.501,-1,1.501),(.501,1,2)),
               ((-.501,rear,.499),(.501,1,1.501))]
        shapes=[box('proxy',a,b) for a,b in slabs]
        if report.get('roof_equipment'):shapes.append(box('roof_proxy',(-.5,-.5,2),(.5,.5,report['bounds_m']['hi'][2])))
    bpy.ops.object.select_all(action='DESELECT')
    for ob in shapes:ob.select_set(True)
    bpy.context.view_layer.objects.active=shapes[0];bpy.ops.object.join()
    obj=shapes[0];obj.name='SK_'+''.join(x.title() for x in name.split('_'))+'Col'
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    rig=rig_and_skin([obj],name+'Collision')
    tris=sum(len(p.vertices)-2 for p in obj.data.polygons);assert tris<=500
    export(folder,name+'_col',[rig,obj]);print(name,'COLLISION PASS',tris)


def studio(folder):
    path=MODELS/'gameplay/item_table/preview.py'
    spec=importlib.util.spec_from_file_location('mount_studio',path);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.HERE=folder;p.NAME=folder.name;p.BLEND_PATH=folder/f'{folder.name}.blend'
    p.open_model();p.setup_render();return p


def preview(folder):
    p=studio(folder);p.render_views()
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    cam=bpy.context.scene.camera;lights={n:bpy.data.objects[n] for n in p.LIGHTS}
    if folder.name=='weapon_holder_wall':
        mount=bpy.data.objects['WeaponHolderMount']
        asset=MODELS/'gameplay/weapon_holder/weapon_holder.glb'
        before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(asset))
        imported=[o for o in bpy.data.objects if o not in before]
        for ob in imported:
            if ob.parent not in imported:ob.parent=mount;ob.matrix_parent_inverse=Matrix.Identity(4);ob.matrix_basis=Matrix.Identity(4)
        p.render_view(cam,lights,'front_left','assembled_front_left')
        p.render_view(cam,lights,'front','assembled_front')
    else:
        # Native pillar, positioned from its lower-foot origin on either socket.
        for label in ('Top','Bottom'):
            mount=bpy.data.objects['PillarMount'+label]
            before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(MODELS/'environments/pillar/pillar.glb'))
            imported=[o for o in bpy.data.objects if o not in before]
            for ob in imported:
                if ob.parent not in imported:ob.parent=mount;ob.matrix_parent_inverse=Matrix.Identity(4);ob.matrix_basis=Matrix.Identity(4)
            p.render_view(cam,lights,'front_left','assembled_'+label.lower())
            for ob in imported:bpy.data.objects.remove(ob,do_unlink=True)


def validate(folder):
    name=folder.name;meta=json.loads((folder/f'{name}_rig.json').read_text())
    for suffix in ('','_col'):
        for ext in ('glb','fbx'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path=str(folder/f'{name}{suffix}.{ext}')
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=path)
            else:bpy.ops.import_scene.fbx(filepath=path)
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
            assert meshes
            points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
            for i in range(3):
                assert abs(min(p[i] for p in points)-meta['bounds_m']['lo'][i])<1e-5
                assert abs(max(p[i] for p in points)-meta['bounds_m']['hi'][i])<1e-5
            rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
            assert set(b.name for b in rig.data.bones)=={'Root'}
            assert not bpy.data.actions
            for obj in meshes:
                bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
                # Collider convex pieces touch at seams, so audit components before welding.
                if not suffix:assert all(e.is_manifold for e in bm.edges),(obj.name,'open casting')
                assert bm.calc_volume()>0;bm.free()
                assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
                if not suffix:
                    assert obj.data.uv_layers.active is not None
                    assert all(-1e-5<=c<=1.00001 for uv in obj.data.uv_layers.active.data for c in uv.uv)
            if not suffix:
                for g in meta['gizmos']:
                    ob=bpy.data.objects.get(g['name']);assert ob is not None,g['name']
                    assert max(abs(ob.matrix_world[i][j]-g['matrix_world'][i][j]) for i in range(4) for j in range(4))<1e-5,g['name']
            print(name,suffix,ext,'ROUND TRIP PASS')
    if name=='weapon_holder_wall':audit_holder_fit(folder,meta)


def audit_holder_fit(folder,meta):
    """Check evaluated native holder geometry on the unchanged exported socket."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(MODELS/'gameplay/weapon_holder/weapon_holder.glb'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    transform=Matrix(next(g['matrix_world'] for g in meta['gizmos'] if g['name']=='WeaponHolderMount'))
    roots=[o for o in bpy.context.scene.objects if o.parent is None and o.type!='MESH']
    for root in roots:root.matrix_world=transform@root.matrix_world
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_')]
    for track in rig.animation_data.nla_tracks:track.mute=True
    deps=bpy.context.evaluated_depsgraph_get();samples=0
    for action in list(bpy.data.actions):
        rig.animation_data.action=action
        if action.slots:rig.animation_data.action_slot=action.slots[0]
        first,last=action.frame_range
        for half in range(math.ceil(first*2),math.floor(last*2)+1):
            frame=half/2;whole=math.floor(frame);bpy.context.scene.frame_set(whole,subframe=frame-whole)
            for ob in meshes:
                evaluated=ob.evaluated_get(deps);mesh=evaluated.to_mesh()
                for v in mesh.vertices:
                    p=ob.matrix_world@v.co
                    if -1+1e-5<p.x<1-1e-5 and -1+1e-5<p.y<1-1e-5 and 1e-5<p.z<2-1e-5:
                        assert -.501-1e-5<=p.x<=.501+1e-5 and .499-1e-5<=p.z<=1.501+1e-5 and p.y<=-1+meta['cavity_depth_m']+1e-5,(action.name,frame,list(p),'holder intersects wall')
                evaluated.to_mesh_clear()
            samples+=1
    print(folder.name,'FIT PASS',samples,'half-frame samples; native holder clears wall and collision cavity')
