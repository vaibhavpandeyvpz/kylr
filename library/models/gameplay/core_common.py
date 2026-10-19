"""Shared scripted source for the Energy and Shield Core gameplay props.

Blender units are metres, Z is up. A closed UV sphere surrounds a sharp-edged,
watertight symbol. Both surfaces carry UVs for the runtime orb materials.
"""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

OUTER_DIAMETER = 0.4
INNER_DIAMETER = 0.25
ANIMATION_FRAMES = 121


def material(name, rgb, alpha=1.0, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, alpha)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*rgb, alpha)
    shader.inputs["Alpha"].default_value = alpha
    shader.inputs["Roughness"].default_value = 0.22
    shader.inputs["Emission Color"].default_value = (*rgb, 1.0)
    shader.inputs["Emission Strength"].default_value = emission
    if alpha < 1.0:
        mat.surface_render_method = "DITHERED"
    return mat


def mesh_object(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        point = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (point.x / INNER_DIAMETER + 0.5,
                                  point.z / INNER_DIAMETER + 0.5)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def outer_shell(mat):
    """Closed sphere with continuous latitude/longitude UVs and smooth normals."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20,
                                       radius=OUTER_DIAMETER / 2)
    obj = bpy.context.object
    obj.name = "SK_CoreOuterShroud"
    obj.data.name = obj.name
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def plus_outline():
    extent = INNER_DIAMETER / 2
    arm = 0.028
    return [(-arm, -extent), (arm, -extent), (arm, -arm),
            (extent, -arm), (extent, arm), (arm, arm),
            (arm, extent), (-arm, extent), (-arm, arm),
            (-extent, arm), (-extent, -arm), (-arm, -arm)]


def bolt_outline():
    """Six-point angular lightning silhouette, scaled to the 0.25 m core."""
    return [(0.036, 0.125), (0.023, 0.025), (0.125, 0.025),
            (-0.012, -0.125), (-0.006, -0.025), (-0.125, -0.025)]


def symbol_shroud(name, outline, mat):
    """Loft one continuous, sharp-edged symbol shell from a closed outline."""
    n = len(outline)
    vertices = [(x, y, z) for y in (-0.035, 0.035) for x, z in outline]
    faces = []
    triangles = tessellate_polygon([[Vector((x, z, 0)) for x, z in outline]])
    for tri in triangles:
        a, b, c = tri
        faces.extend(((c, b, a), (n + a, n + b, n + c)))
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return mesh_object(name, vertices, faces, mat)


def plus_shroud(mat):
    return symbol_shroud("SK_CorePlusShroud", plus_outline(), mat)


def bolt_shroud(mat):
    return symbol_shroud("SK_CoreBoltShroud", bolt_outline(), mat)


def make_rig():
    armature = bpy.data.armatures.new("CoreRig")
    rig = bpy.data.objects.new("RIG_Core", armature)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name in ("Outer", "Inner"):
        bone = armature.edit_bones.new(name)
        bone.head = (0, 0, 0)
        bone.tail = (0, 0.1, 0)
        bone.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"
    return rig


def skin(obj, rig, bone_name):
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Core skin", "ARMATURE")
    modifier.object = rig
    obj.parent = rig


def animate(rig):
    action = bpy.data.actions.new("spin")
    action.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = action
    for name, direction in (("Outer", 1), ("Inner", -1)):
        bone = rig.pose.bones[name]
        for frame, angle in ((1, 0.0), (ANIMATION_FRAMES, direction * 2 * math.pi)):
            bone.rotation_euler[1] = angle
            bone.keyframe_insert("rotation_euler", index=1, frame=frame)
    curves = (list(action.fcurves) if hasattr(action, "fcurves") else
              [curve for layer in action.layers for strip in layer.strips
               for bag in strip.channelbags for curve in bag.fcurves])
    for curve in curves:
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
    action.use_cyclic = True
    rig.animation_data.action = None
    track = rig.animation_data.nla_tracks.new()
    track.name = "spin"
    track.strips.new("spin", 1, action)


def export(directory, stem, objects):
    import sys
    sys.path.insert(0, str(directory.parents[1]))
    from material_uv import prepare_export
    prepare_export(objects, directory, stem)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=str(directory / f"{stem}.glb"), export_format="GLB",
                              use_selection=True, export_yup=True, export_skins=True,
                              export_animations=True, export_animation_mode="ACTIONS",
                              export_anim_single_armature=True, export_materials="EXPORT")
    bpy.ops.export_scene.fbx(filepath=str(directory / f"{stem}.fbx"), use_selection=True,
                             object_types={"MESH", "ARMATURE"}, axis_forward="-Z", axis_up="Y",
                             bake_anim=True, bake_anim_use_all_actions=True,
                             bake_anim_use_nla_strips=False, add_leaf_bones=False)


def build(directory, stem, kind, outer_color, inner_color):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablock in list(bpy.data.materials):
        bpy.data.materials.remove(datablock)
    outer = outer_shell(material("M_CoreOuter", outer_color, 0.25, 0.08))
    inner = (bolt_shroud if kind == "energy" else plus_shroud)(
        material("M_CoreInner", inner_color, 1.0, 2.5))
    rig = make_rig()
    skin(outer, rig, "Outer")
    skin(inner, rig, "Inner")
    animate(rig)
    assert max(abs(v.co[i]) for v in outer.data.vertices for i in (0, 1, 2)) <= 0.200001
    assert max(abs(v.co[i]) for v in inner.data.vertices for i in (0, 1, 2)) <= 0.125001
    assert len(outer.data.polygons) * 2 + len(inner.data.polygons) * 2 <= 1500
    export(directory, stem, [rig, outer, inner])
    metadata = {"name": stem, "outer_diameter_m": OUTER_DIAMETER,
                "inner_diameter_m": INNER_DIAMETER, "outer_opacity": 0.25,
                "bones": ["Outer", "Inner"], "animations": ["spin"],
                "inner_shape": "bolt" if kind == "energy" else "plus",
                "outer_shape": "uv_sphere"}
    (directory / f"{stem}_rig.json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / f"{stem}.blend"), compress=True)
    print(f"[{stem}] model and animation exported: {metadata}")


def preview(directory, stem, render=True):
    bpy.ops.wm.open_mainfile(filepath=str(directory / f"{stem}.blend"))
    world = bpy.data.worlds.new("Core preview world")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.16, 0.18, 0.21, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7
    bpy.ops.object.camera_add(location=(0.18, -0.95, 0.16))
    camera = bpy.context.object
    direction = Vector((0, 0, 0)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 0.72
    bpy.context.scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(0.3, -0.45, 0.8))
    bpy.context.object.data.energy = 180
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 1.0
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.render.resolution_x = 640
    bpy.context.scene.render.resolution_y = 640
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.frame_set(1)
    bpy.context.scene.render.filepath = str(directory / f"{stem}_preview.png")
    if render:
        bpy.ops.render.render(write_still=True)


def showcase(directory, stem):
    """Ten seconds of the authored counter-rotation on a camera turntable."""
    preview(directory, stem, render=False)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.eevee.taa_render_samples = 16
    scene.frame_start, scene.frame_end = 1, 240
    rig = bpy.data.objects.get('RIG_Core')
    if rig is None:
        rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    action = next(a for a in bpy.data.actions if a.name == 'spin')
    rig.animation_data_create()
    for track in list(rig.animation_data.nla_tracks): rig.animation_data.nla_tracks.remove(track)
    rig.animation_data.action = None
    track = rig.animation_data.nla_tracks.new()
    track.name = 'spin showcase'
    strip = track.strips.new('spin', 1, action)
    strip.repeat = 239 / (ANIMATION_FRAMES - 1)
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.filepath = str(directory / f'{stem}_showcase.mp4')
    camera = scene.camera
    radius = math.hypot(camera.location.x, camera.location.y)
    angle0 = math.atan2(camera.location.y, camera.location.x)
    for frame in range(1,241):
        angle = angle0 + math.tau*(frame-1)/239
        camera.location.x, camera.location.y = radius*math.cos(angle), radius*math.sin(angle)
        camera.rotation_euler = (-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.keyframe_insert('location',frame=frame)
        camera.keyframe_insert('rotation_euler',frame=frame)
    bpy.ops.render.render(animation=True)
    print(f'[{stem}] rendered {scene.render.filepath}',flush=True)


def validate(directory, stem, kind):
    meta = json.loads((directory / f"{stem}_rig.json").read_text(encoding="utf8"))
    assert meta["outer_diameter_m"] == 0.4 and meta["inner_diameter_m"] == 0.25
    assert meta["outer_opacity"] == 0.25 and meta["animations"] == ["spin"]
    assert meta["inner_shape"] == ("bolt" if kind == "energy" else "plus")
    assert meta["outer_shape"] == "uv_sphere"
    for ext in ("glb", "fbx"):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        path = directory / f"{stem}.{ext}"
        if ext == "glb":
            bpy.ops.import_scene.gltf(filepath=str(path))
        else:
            bpy.ops.import_scene.fbx(filepath=str(path))
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and
                  obj.name.startswith("SK_Core")]
        assert len(meshes) == 2, (path, [obj.name for obj in meshes])
        assert any(("Bolt" if kind == "energy" else "Plus") in obj.name for obj in meshes)
        for obj in meshes:
            assert obj.data.uv_layers.active is not None, obj.name
        outer = next(obj for obj in meshes if "OuterShroud" in obj.name)
        assert all(abs(vertex.co.length - 0.2) < 0.0001
                   for vertex in outer.data.vertices), "Outer must be spherical"
        # Exporters split vertices at UV seams; weld before checking sphere topology.
        import bmesh
        topology = bmesh.new()
        topology.from_mesh(outer.data)
        bmesh.ops.remove_doubles(topology, verts=list(topology.verts), dist=0.00001)
        assert all(edge.is_manifold for edge in topology.edges), "Sphere has an opening"
        assert len(topology.verts) - len(topology.edges) + len(topology.faces) == 2
        topology.free()
        bounds = []
        for obj in meshes:
            world = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
            bounds.append((obj.name, max(abs(point.x) for point in world),
                           max(abs(point.y) for point in world),
                           max(abs(point.z) for point in world)))
        assert max(max(bound[1:]) for bound in bounds) <= 0.201, bounds
        arms = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
        assert len(arms) == 1 and {bone.name for bone in arms[0].data.bones} >= {"Outer", "Inner"}
        if ext == "glb":
            assert any("spin" in action.name.lower() for action in bpy.data.actions)
            outer = next(obj for obj in meshes if "OuterShroud" in obj.name)
            alpha = outer.data.materials[0].diffuse_color[3]
            assert abs(alpha - 0.25) < 0.01, alpha
        print(f"[{stem}] {ext} round trip: {len(meshes)} meshes, 2 bones, bounds={bounds}")
