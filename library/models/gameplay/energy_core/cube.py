"""Scripted hollow energy cube. Metres; centre origin retained for pickup sockets."""
import sys
import json
import math
from itertools import product
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core_common as common

SIZE = .25
GUARD_PROJECTION = .005
ASSEMBLY_SIZE = SIZE+2*GUARD_PROJECTION
LAYERS = (.25,)
WALL_THICKNESS = .005
SEAT_CLEARANCE = .0005
BLUE = (.008, .24, .8)


def box(name, size, center, material, bevel=.003):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel>0:
        mod = obj.modifiers.new('Manufactured edge chamfer', 'BEVEL')
        mod.width, mod.segments = bevel, 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def boolean(obj, cutter, operation):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Fitted '+operation,'BOOLEAN')
    mod.operation=operation;mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)


def join(objects, name):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
    obj=objects[0];obj.name=name
    bpy.context.scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return obj


def intersection_volume(first, second):
    # Audit complete solids, not a subset of corner vertices. Rest-pose meshes
    # are copied in world space; checks never modify the delivery objects.
    copies=[]
    for obj in (first,second):
        copy=bpy.data.objects.new('CHECK_Contact',obj.data.copy())
        bpy.context.collection.objects.link(copy);copy.matrix_world=obj.matrix_world
        copies.append(copy)
    boolean(copies[0],copies[1],'INTERSECT')
    bm=bmesh.new();bm.from_mesh(copies[0].data)
    volume=abs(bm.calc_volume());bm.free()
    for obj in copies:
        mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.meshes.remove(mesh)
    return volume


def bolt(material):
    # Bold lightning prism with balanced upper/lower halves: each outline
    # point has an opposite partner, giving exact 180-degree symmetry.
    outline=[(.018,.095),(.006,.021),(.065,.021),
             (-.018,-.095),(-.006,-.021),(-.065,-.021)]
    assert all((-x,-z) in outline for x,z in outline)
    obj=common.symbol_shroud('SK_CoreBoltShroud',outline,material)
    for vertex in obj.data.vertices:vertex.co.y*=.52
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free()
    return obj


def shield(material):
    # Bilaterally symmetric heraldic shield: raised crest, broad shoulders,
    # tapered curved flanks and a pointed base. Same solid-prism depth as bolt.
    outline=[(0,.095),(.025,.080),(.052,.068),(.070,.064),
             (.067,.018),(.057,-.027),(.040,-.061),(.020,-.083),
             (0,-.095),(-.020,-.083),(-.040,-.061),(-.057,-.027),
             (-.067,.018),(-.070,.064),(-.052,.068),(-.025,.080)]
    obj=common.symbol_shroud('SK_CoreShieldShroud',outline,material)
    for vertex in obj.data.vertices:vertex.co.y*=.52
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free()
    return obj


def build(directory, stem='energy_core'):
    is_shield=stem=='shield_core'

    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for mat in list(bpy.data.materials):bpy.data.materials.remove(mat)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    metal=common.material('M_CoreArmor',(.025,.035,.045))
    shader=metal.node_tree.nodes['Principled BSDF']
    shader.inputs['Metallic'].default_value=.35;shader.inputs['Roughness'].default_value=.45
    glass=common.material('M_CoreOuter',(.025,.8,.008) if is_shield else BLUE,.25,0)
    glass.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.12
    glass.surface_render_method='BLENDED'
    light=common.material('M_CoreInner',(.22,1,.06) if is_shield else (.12,.8,1),1,5)
    objects=[]
    for i,shell_size in enumerate(LAYERS):
        shell=box(f'SK_CoreGlassLayer{i+1}',(shell_size,)*3,(0,0,0),glass,.015 if i==0 else .007)
        objects.append(shell)
    # Independently authored corner cups project 5 mm beyond each cube face.
    # Their pocket is a simple manufacturing cutter, not the outer-cube mesh.
    # The finished supports, in turn, cut their exact seats into the glass.
    guards=[]
    base=box('Base',(ASSEMBLY_SIZE,ASSEMBLY_SIZE,.015),(0,0,-.1225),metal,0)
    for signs in product((-1,1),repeat=3):
        center=tuple(s*.105 for s in signs)
        guard=box('Corner',(.050,)*3,center,metal,.005 if signs[2]<0 else .009)
        # The seat cutter fills the complete support envelope, including its
        # later hollow pocket. Cut the still-solid glass blank with that volume.
        seat=box('CUT_SolidSupportSeat',(.050+2*SEAT_CLEARANCE,)*3,center,glass,0)
        boolean(objects[0],seat,'DIFFERENCE')
        bpy.data.objects.remove(seat,do_unlink=True)
        pocket=box('CUT_CornerPocket' ,(.058,)*3,tuple(s*.090 for s in signs),metal,0)
        boolean(guard,pocket,'DIFFERENCE')
        bpy.data.objects.remove(pocket,do_unlink=True)
        if signs[2]<0:
            boolean(base,guard,'UNION')
            bpy.data.objects.remove(guard,do_unlink=True)
        else:
            guards.append(guard)
    # The lower cups already have their exterior chamfers. Fuse them into a
    # plain base; adding a post-union inside bevel would intrude into the seat.
    base_seat=box('CUT_SolidBaseSeat',(ASSEMBLY_SIZE+2*SEAT_CLEARANCE,
                  ASSEMBLY_SIZE+2*SEAT_CLEARANCE,.015+2*SEAT_CLEARANCE),
                  (0,0,-.1225),glass,0)
    boolean(objects[0],base_seat,'DIFFERENCE')
    bpy.data.objects.remove(base_seat,do_unlink=True)
    # Hollow the relieved solid blank last. The offset cavity keeps straight
    # walls exactly 5 mm thick and chamfer planes parallel to the outer faces.
    inner_bevel=.015+(math.sqrt(2)-2)*WALL_THICKNESS
    cavity=box('CUT_HollowCavity',((SIZE-2*WALL_THICKNESS),)*3,(0,0,0),glass,inner_bevel)
    boolean(objects[0],cavity,'DIFFERENCE')
    bpy.data.objects.remove(cavity,do_unlink=True)
    armor=join([base,*guards],'SK_CoreCornerArmor')
    # Boolean seat faces remain blue glass rather than inheriting cutter metal.
    for face in objects[0].data.polygons:face.material_index=0
    objects[0].data.materials.clear();objects[0].data.materials.append(glass)
    objects.append(armor)
    symbol=(shield if is_shield else bolt)(light);objects.append(symbol)
    rig=common.make_rig()
    rig.name='RIG_ShieldCore' if is_shield else 'RIG_EnergyCore';rig.data.name='ShieldCoreRig' if is_shield else 'EnergyCoreRig'
    for obj in objects:common.skin(obj,rig,'Inner' if obj==symbol else 'Outer')
    common.animate(rig)
    action=next(a for a in bpy.data.actions if a.name=='spin')
    curves=(list(action.fcurves) if hasattr(action,'fcurves') else
            [curve for layer in action.layers for strip in layer.strips
             for bag in strip.channelbags for curve in bag.fcurves])
    for curve in curves:
        if curve.data_path.endswith('rotation_euler'):curve.array_index=2
    for bone in rig.pose.bones:bone.rotation_euler=(0,0,0)
    scene.frame_set(1);scene.render.fps=24
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    bounds=[max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
    assert all(abs(v-ASSEMBLY_SIZE)<1e-6 for v in bounds),bounds
    # The rotating symbol stays inside the innermost glass in every relative pose.
    radius=max(v.co.length for v in symbol.data.vertices)
    assert radius < SIZE/2-WALL_THICKNESS-.004,(radius,'symbol clearance')
    tris=sum(len(p.vertices)-2 for obj in objects for p in obj.data.polygons)
    assert tris<=5000,tris
    overlap=intersection_volume(objects[0],armor)
    assert overlap<1e-12,('glass/support overlap',overlap)
    common.export(directory,stem,[rig,*objects])
    rig.animation_data.action=None
    for track in rig.animation_data.nla_tracks:track.mute=True
    for bone in rig.pose.bones:bone.rotation_euler=(0,0,0)
    scene.frame_set(1);bpy.context.view_layer.update()
    meta=dict(name=stem,outer_shape='hollow_cube',authored_lwh_m=[ASSEMBLY_SIZE]*3,
              origin='centre',layers_m=list(LAYERS),wall_thickness_m=WALL_THICKNESS,outer_opacity=.25,base_height_m=.015,guard_projection_m=GUARD_PROJECTION,nominal_cube_m=SIZE,seat_clearance_m=SEAT_CLEARANCE,glass_support_overlap_m3=overlap,
              bones=['Outer','Inner'],animations=['spin'],
              animation_settings={'spin':{'loop':True,'fps':24,'frames':[1,121],
                                  'axis':'Blender +Z / Godot +Y','Outer_degrees':360,'Inner_degrees':-360}},inner_shape='solid_shield' if is_shield else 'solid_bolt_symmetric',
              symbol_lwh_m=[.0364,.14 if is_shield else .13,.19],
              symbol_symmetry='bilateral_X' if is_shield else '180_degree',
              triangles=tris,material_slots=[m.name for m in (metal,glass,light)],
              symbol_clearance_m=SIZE/2-WALL_THICKNESS-radius,
              preview_only=['camera','lights'],collision='no solid collision companion authored')
    if not is_shield:meta.update(bolt_lwh_m=[.0364,.13,.19],bolt_symmetry='180_degree')
    (directory/f'{stem}_rig.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(directory/f'{stem}.blend'),compress=True)
    print(f'[{stem}] 0.25 m cube + 5 mm supports;' ,tris,'triangles; symbol clearance',meta['symbol_clearance_m'])


def preview(directory, render=True, stem='energy_core'):
    common.preview(directory,stem,render=False)
    scene=bpy.context.scene
    scene.camera.location=(-.42,-.72,.34)
    scene.camera.rotation_euler=(-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.ortho_scale=.43
    scene.render.resolution_x=1024;scene.render.resolution_y=1024
    scene.eevee.taa_render_samples=64
    world=scene.world.node_tree.nodes['Background']
    world.inputs['Color'].default_value=(.018,.025,.04,1)
    world.inputs['Strength'].default_value=.35
    for obj in scene.objects:
        if obj.type=='LIGHT':obj.data.energy=45
    group=bpy.data.node_groups.new('CorePreviewGlow','CompositorNodeTree')
    group.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
    scene.compositing_node_group=group
    source=group.nodes.new('CompositorNodeRLayers')
    glare=group.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value='Fog Glow'
    glare.inputs['Quality'].default_value='High'
    glare.inputs['Threshold'].default_value=1.2
    output=group.nodes.new('NodeGroupOutput')
    group.links.new(source.outputs['Image'],glare.inputs['Image'])
    group.links.new(glare.outputs['Image'],output.inputs['Image'])
    scene.render.filepath=str(directory/f'{stem}_front_left.png')
    if render:
        bpy.ops.render.render(write_still=True)
        scene.render.filepath=str(directory/f'{stem}_preview.png')
        bpy.ops.render.render(write_still=True)
        scene.camera.location=(0,-.72,0)
        scene.camera.rotation_euler=(-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        scene.camera.data.ortho_scale=.33
        scene.render.filepath=str(directory/f'{stem}_front.png')
        bpy.ops.render.render(write_still=True)


def showcase(directory, stem='energy_core'):
    # Use the established two-bone spin and turntable renderer with cube framing.
    original=common.preview
    # preview itself delegates to the unmodified common setup.
    def setup(directory,stem,render=True):
        common.preview=original
        preview(directory,render=render,stem=stem)
    common.preview=setup
    common.showcase(directory,stem)


def validate(directory, stem='energy_core'):
    is_shield=stem=='shield_core'
    meta=json.loads((directory/f'{stem}_rig.json').read_text())
    assert meta['authored_lwh_m']==[ASSEMBLY_SIZE]*3 and meta['outer_shape']=='hollow_cube'
    assert meta['inner_shape']==('solid_shield' if is_shield else 'solid_bolt_symmetric')
    assert meta['layers_m']==[.25] and meta['wall_thickness_m']==.005 and meta['outer_opacity']==.25
    for ext in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=str(directory/f'{stem}.{ext}')
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=path)
        else:bpy.ops.import_scene.fbx(filepath=path)
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_Core')]
        assert len(meshes)==3,[o.name for o in meshes]
        assert not any('EdgeLayer' in o.name for o in meshes)
        if ext=='glb':
            material=next(m for m in bpy.data.materials if m.name.startswith('M_CoreOuter'))
            assert abs(material.diffuse_color[3]-.25)<1e-5,'Layer opacity must be 25%'
            if is_shield:assert material.diffuse_color[1]>max(material.diffuse_color[0],material.diffuse_color[2]),'Green shell'

        assert set(b.name for b in rig.data.bones)=={'Outer','Inner'}
        assert any('spin' in a.name.lower() for a in bpy.data.actions)
        if rig.animation_data:
            rig.animation_data.action=None
            for track in rig.animation_data.nla_tracks:track.mute=True
        for bone in rig.pose.bones:bone.matrix_basis.identity()
        bpy.context.view_layer.update()
        points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
        bounds=[max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
        assert all(abs(v-ASSEMBLY_SIZE)<1e-5 for v in bounds),bounds
        shell=next(o for o in meshes if 'GlassLayer' in o.name)
        assert all(shell.data.materials[p.material_index].name.startswith('M_CoreOuter') for p in shell.data.polygons)
        assert not any(all(abs(c)>.095 for c in shell.matrix_world@v.co)
                       for v in shell.data.vertices),'Glass remains inside a filled corner seat'
        armor=next(o for o in meshes if 'CornerArmor' in o.name)
        overlap=intersection_volume(shell,armor)
        assert overlap<1e-12,(ext,'glass/support intersection',overlap)
        # Opposing outer/cavity face planes prove the delivered straight walls
        # are 5 mm thick, rather than merely metadata or a transparent solid.
        for axis in range(3):
            for plane in (SIZE/2,SIZE/2-WALL_THICKNESS):
                assert any(all(abs((shell.matrix_world@shell.data.vertices[v].co)[axis]-plane)<1e-5
                               for v in face.vertices) for face in shell.data.polygons),('wall plane',axis,plane)
        tris=0
        for obj in meshes:
            assert all(abs(s-1)<1e-6 for s in obj.scale),obj.name
            assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
            assert obj.data.uv_layers.active is not None
            assert all(-1e-5<=c<=1.00001 for uv in obj.data.uv_layers.active.data for c in uv.uv)
            bm=bmesh.new();bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
            assert all(e.is_manifold for e in bm.edges),(obj.name,'open edge')
            assert bm.calc_volume()>0,(obj.name,'inverted solid')
            if 'Shield' in obj.name:
                assert len(bm.verts)-len(bm.edges)+len(bm.faces)==2,'Shield must be a filled solid'
                world=[obj.matrix_world@v.co for v in bm.verts]
                assert abs(max(p.z for p in world)-.095)<1e-5 and abs(min(p.z for p in world)+.095)<1e-5
                assert all(any((p-Vector((-q.x,q.y,q.z))).length<1e-5 for q in world)
                           for p in world),'Shield bilateral symmetry'
                assert max(p.length for p in world)<SIZE/2-WALL_THICKNESS-.004,'Shield swept clearance'
            if 'Bolt' in obj.name:
                assert len(bm.verts)-len(bm.edges)+len(bm.faces)==2,'Bolt must be a filled solid'
                world=[obj.matrix_world@v.co for v in bm.verts]
                top=max(p.z for p in world);bottom=min(p.z for p in world)
                assert abs(top-.095)<1e-5 and abs(bottom+.095)<1e-5,'Bolt height'
                assert not any(all(abs((obj.matrix_world@v.co).z-top)<1e-5 for v in f.verts)
                               for f in bm.faces),'Top must remain pointed'
                assert all(any((p-Vector((-q.x,q.y,-q.z))).length<1e-5 for q in world)
                           for p in world),'Bolt upper/lower symmetry'
            bm.free()
            tris+=sum(len(p.vertices)-2 for p in obj.data.polygons)
        assert tris<=5000
        action=next(a for a in bpy.data.actions if 'spin' in a.name.lower())
        rig.animation_data.action=action
        if action.slots:rig.animation_data.action_slot=action.slots[0]
        start,end=action.frame_range
        matrices=[];world_frames=[]
        for frame in (start,start+(end-start)/4,end):
            whole=math.floor(frame)
            bpy.context.scene.frame_set(whole,subframe=frame-whole)
            matrices.append([b.matrix.copy() for b in rig.pose.bones])
            world_frames.append({b.name:(rig.matrix_world@b.matrix).to_3x3().copy() for b in rig.pose.bones})
        assert max(abs(a[i][j]-b[i][j]) for a,b in zip(matrices[0],matrices[2])
                   for i in range(4) for j in range(4))<1e-4,'spin loop seam'
        assert max(abs(a[i][j]-b[i][j]) for a,b in zip(matrices[0],matrices[1])
                   for i in range(3) for j in range(3))>.5,'spin has no motion'
        for name,direction in (('Outer',1),('Inner',-1)):
            delta=world_frames[1][name]@world_frames[0][name].inverted()
            assert (delta@Vector((0,0,1))-Vector((0,0,1))).length<1e-4,(name,'rotation tilts vertical axis')
            assert abs(delta[1][0]-direction)<1e-4,(name,'incorrect spin direction')
        print(f'[{stem}]',ext,'PASS:',bounds,tris,'triangles, closed solids, UVs, rigid weights, spin')
