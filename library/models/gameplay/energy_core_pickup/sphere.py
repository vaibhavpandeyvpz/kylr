"""25 cm hollow spherical pickup, reusing the authored energy bolt and finish."""
import sys
import json
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'energy_core'))
import cube
common=cube.common
STEM='energy_core_pickup'
RADIUS=.125
WALL=.0125
BOLT_SCALE=1.0


def build(directory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    glass=common.material('M_CoreOuter',cube.BLUE,.25,0)
    glass.surface_render_method='BLENDED'
    glass.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.12
    light=common.material('M_CoreInner',(.12,.8,1),1,5)
    surfaces=[]
    for radius,inward in ((RADIUS,False),(RADIUS-WALL,True)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,radius=radius)
        obj=bpy.context.object
        obj.data.materials.append(glass)
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        if inward:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
        bm.to_mesh(obj.data);bm.free()
        for face in obj.data.polygons:face.use_smooth=True
        surfaces.append(obj)
    shell=cube.join(surfaces,'SK_CoreSphereShell')
    symbol=cube.bolt(light)
    for vertex in symbol.data.vertices:vertex.co*=BOLT_SCALE
    clearance=RADIUS-WALL-max(v.co.length for v in symbol.data.vertices)
    assert clearance>.005,clearance
    rig=common.make_rig();rig.name='RIG_EnergyCorePickup'
    common.skin(shell,rig,'Outer');common.skin(symbol,rig,'Inner')
    common.animate(rig)
    action=next(a for a in bpy.data.actions if a.name=='spin')
    curves=(list(action.fcurves) if hasattr(action,'fcurves') else
            [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves])
    for curve in curves:
        if curve.data_path.endswith('rotation_euler'):curve.array_index=2
    scene.frame_set(1);scene.render.fps=24
    tris=sum(len(p.vertices)-2 for o in (shell,symbol) for p in o.data.polygons)
    assert tris<=5000,tris
    common.export(directory,STEM,[rig,shell,symbol])
    rig.animation_data.action=None
    for track in rig.animation_data.nla_tracks:track.mute=True
    for bone in rig.pose.bones:bone.rotation_euler=(0,0,0)
    scene.frame_set(1)
    metadata=dict(name=STEM,outer_shape='hollow_sphere',outer_diameter_m=RADIUS*2,
                  wall_thickness_m=WALL,outer_opacity=.25,authored_lwh_m=[RADIUS*2]*3,
                  origin='centre',inner_shape='solid_bolt_symmetric',bolt_scale=BOLT_SCALE,
                  bolt_lwh_m=[dimension*BOLT_SCALE for dimension in (.0364,.13,.19)],symbol_clearance_m=clearance,
                  bones=['Outer','Inner'],animations=['spin'],triangles=tris,
                  animation_settings={'spin':{'loop':True,'fps':24,'frames':[1,121],
                  'axis':'Blender +Z / Godot +Y','Outer_degrees':360,'Inner_degrees':-360}},
                  collision='no solid collision companion authored')
    (directory/f'{STEM}_rig.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(directory/f'{STEM}.blend'),compress=True)
    print(STEM,'PASS',tris,'triangles; swept bolt clearance',clearance)


def preview(directory,render=True):
    cube.preview(directory,render=False,stem=STEM)
    scene=bpy.context.scene
    scene.camera.data.ortho_scale=RADIUS*3.2
    if render:
        for suffix in ('front_left','preview'):
            scene.render.filepath=str(directory/f'{STEM}_{suffix}.png')
            bpy.ops.render.render(write_still=True)
        scene.camera.location=(0,-.72,0)
        scene.camera.rotation_euler=(-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        scene.camera.data.ortho_scale=RADIUS*2.6
        scene.render.filepath=str(directory/f'{STEM}_front.png')
        bpy.ops.render.render(write_still=True)


def showcase(directory):
    original=common.preview
    def setup(directory,stem,render=True):
        common.preview=original
        preview(directory,render=render)
    common.preview=setup
    common.showcase(directory,STEM)


def validate(directory):
    for ext in ('glb','fbx'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=str(directory/f'{STEM}.{ext}')
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=path)
        else:bpy.ops.import_scene.fbx(filepath=path)
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        assert set(b.name for b in rig.data.bones)=={'Outer','Inner'}
        rig.animation_data.action=None
        for track in rig.animation_data.nla_tracks:track.mute=True
        for bone in rig.pose.bones:bone.matrix_basis.identity()
        bpy.context.view_layer.update()
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('SK_Core')]
        assert len(meshes)==2,[o.name for o in meshes]
        shell=next(o for o in meshes if 'SphereShell' in o.name)
        symbol=next(o for o in meshes if 'Bolt' in o.name)
        radii=[(shell.matrix_world@v.co).length for v in shell.data.vertices]
        assert all(min(abs(r-RADIUS),abs(r-(RADIUS-WALL)))<1e-6 for r in radii),'Nonuniform shell'
        assert abs(max(radii)-min(radii)-WALL)<1e-6,'Authored radial wall'
        points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
        assert all(abs(max(p[i] for p in points)-min(p[i] for p in points)-RADIUS*2)<1e-6 for i in range(3))
        assert max((symbol.matrix_world@v.co).length for v in symbol.data.vertices)<RADIUS-WALL-.005
        tris=0
        for obj in meshes:
            assert all(abs(s-1)<1e-6 for s in obj.scale)
            assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in obj.data.vertices)
            assert obj.data.uv_layers.active is not None
            assert all(-1e-5<=c<=1.00001 for uv in obj.data.uv_layers.active.data for c in uv.uv)
            bm=bmesh.new();bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
            assert all(e.is_manifold for e in bm.edges),'Open surface'
            assert bm.calc_volume()>0,'Inverted shell'
            if obj==shell:
                assert all((v.co.normalized().dot(f.normal)>0 if v.co.length>RADIUS-WALL/2 else v.co.normalized().dot(f.normal)<0)
                           for f in bm.faces for v in f.verts),'Shell normal orientation'
            bm.free()
            tris+=sum(len(p.vertices)-2 for p in obj.data.polygons)
        assert tris<=5000
        if ext=='glb':
            material=next(m for m in bpy.data.materials if m.name.startswith('M_CoreOuter'))
            assert abs(material.diffuse_color[3]-.25)<1e-6
        action=next(a for a in bpy.data.actions if 'spin' in a.name.lower())
        rig.animation_data.action=action
        if action.slots:rig.animation_data.action_slot=action.slots[0]
        start,end=action.frame_range
        frames=[]
        for frame in (start,start+(end-start)/4,end):
            whole=math.floor(frame);bpy.context.scene.frame_set(whole,subframe=frame-whole)
            frames.append({b.name:(rig.matrix_world@b.matrix).to_3x3().copy() for b in rig.pose.bones})
        for bone,direction in (('Outer',1),('Inner',-1)):
            delta=frames[1][bone]@frames[0][bone].inverted()
            assert (delta@Vector((0,0,1))-Vector((0,0,1))).length<1e-4
            assert abs(delta[1][0]-direction)<1e-4
            assert max(abs(frames[0][bone][i][j]-frames[2][bone][i][j]) for i in range(3) for j in range(3))<1e-4
        print(STEM,ext,'PASS: exact 25 cm bounds, 12.5 mm hollow walls, UVs, rigid skin, spin;',tris,'triangles')
