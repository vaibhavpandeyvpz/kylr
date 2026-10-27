class_name Assets
extends RefCounted

static var scenes: Dictionary = {}
static var animations: Dictionary = {}
static var playback_animations: Dictionary = {}
static var matte_finishes: Dictionary = {}
static var glass_finishes: Dictionary = {}
static var profile_loads := false
static var load_stats: Dictionary = {}
const GLASS_SHADER = preload("res://shaders/original/frosted_glass.gdshader")
const REGOLITH_ALBEDO = preload("res://assets/textures/lunar_surface/regolith_albedo.png")
const REGOLITH_NORMAL = preload("res://assets/textures/lunar_surface/regolith_normal.png")
const REGOLITH_ORM = preload("res://assets/textures/lunar_surface/regolith_orm.png")

static func regolith_material(source: StandardMaterial3D = null, local_surface := false) -> StandardMaterial3D:
	var material: StandardMaterial3D = source.duplicate() if source else StandardMaterial3D.new()
	if source == null: material.resource_name = "M_Regolith_Diffuse"
	material.albedo_texture = REGOLITH_ALBEDO
	material.albedo_color = Color.WHITE
	material.vertex_color_use_as_albedo = false
	material.normal_enabled = true
	material.normal_texture = REGOLITH_NORMAL
	material.normal_scale = 0.55
	material.roughness = 1.0
	material.roughness_texture = REGOLITH_ORM
	material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	material.ao_enabled = true
	material.ao_texture = material.roughness_texture
	material.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.metallic = 0.0
	material.uv1_triplanar = true
	material.uv1_world_triplanar = not local_surface
	material.uv1_scale = Vector3.ONE * 0.24
	return material

static func record_load(key: String, started: int) -> void:
	var elapsed := Time.get_ticks_usec()-started
	if not load_stats.has(key): load_stats[key] = {"calls":0,"total_us":0,"max_us":0}
	var entry: Dictionary = load_stats[key]
	entry.calls += 1
	entry.total_us += elapsed
	entry.max_us = maxi(entry.max_us,elapsed)

static func model(category: String, id: String, suffix := "") -> Node3D:
	var path := "res://assets/models/%s/%s/%s%s.glb" % [category, id, id, suffix]
	return scene(path)

static func scene(path: String) -> Node3D:
	var started := Time.get_ticks_usec() if profile_loads else 0
	if not scenes.has(path):
		scenes[path] = load(path)
	var instance: Node3D = scenes[path].instantiate()
	finish_metals(instance)
	finish_glass(instance)
	if profile_loads: record_load(path,started)
	return instance

static func finish_glass(root: Node) -> void:
	if root is MeshInstance3D and root.mesh != null:
		for surface in root.mesh.get_surface_count():
			var source := root.get_active_material(surface) as StandardMaterial3D
			if source == null or not source.resource_name.ends_with("_Glass"): continue
			var key := source.get_instance_id()
			if not glass_finishes.has(key):
				var finish := ShaderMaterial.new()
				finish.resource_name = source.resource_name
				finish.shader = GLASS_SHADER
				finish.set_shader_parameter("color", source.albedo_color)
				finish.set_shader_parameter("opacity", source.albedo_color.a)
				finish.set_shader_parameter("refraction_strength", 0.008)
				finish.set_shader_parameter("blur_amount", 1.5)
				finish.set_shader_parameter("roughness", maxf(source.roughness, 0.12))
				glass_finishes[key] = finish
			root.set_surface_override_material(surface, glass_finishes[key])
	for child in root.get_children():
		finish_glass(child)

static func material_role(name: String) -> String:
	for classifier in ["Metallic","Glass","Emissive","Diffuse"]:
		var suffix: String = "_"+classifier
		if name.ends_with(suffix) and name not in ["M_Glass","M_Emissive"]:
			return name.trim_suffix(suffix)
	return name

static func finish_metals(root: Node) -> void:
	if root is MeshInstance3D:
		for surface in root.mesh.get_surface_count():
			var source := root.get_active_material(surface) as StandardMaterial3D
			if source == null: continue
			# Only explicit source classifiers opt into reflections. Preserve all
			# authored albedo, metallic strength, roughness and texture variation.
			if source.resource_name.ends_with("_Metallic") or source.resource_name.ends_with("_Glass"): continue
			var key := source.get_instance_id()
			if not matte_finishes.has(key):
				var finish: StandardMaterial3D = source.duplicate()
				finish.metallic = 0.0
				finish.metallic_specular = 0.0
				finish.clearcoat_enabled = false
				matte_finishes[key] = finish
			root.set_surface_override_material(surface,matte_finishes[key])
	for child in root.get_children():
		finish_metals(child)

static func find(root: Node, kind: String) -> Node:
	if root.is_class(kind):
		return root
	# Prefer the asset's own controller over those in mounted child assets.
	for child in root.get_children():
		if child.is_class(kind):
			return child
	for child in root.get_children():
		var result := find(child, kind)
		if result:
			return result
	return null

static func socket(root: Node, id: String) -> Node3D:
	var node := root.find_child(id, true, false) as Node3D
	if node is BoneAttachment3D:
		var child := node.find_child(id, true, false) as Node3D
		if child: return child
	return node

static func socket_world_transform(mount: Node3D) -> Transform3D:
	# BoneAttachment presentation updates can follow the physics tick. Query
	# the live bone pose plus the authored socket frame for same-tick effects.
	var relative:=Transform3D.IDENTITY
	var node: Node3D=mount
	while node!=null and not node is BoneAttachment3D:
		relative=node.transform*relative
		node=node.get_parent() as Node3D
	if node is BoneAttachment3D:
		var skeleton:=node.get_parent() as Skeleton3D
		if skeleton!=null:
			var bone:=skeleton.find_bone(node.bone_name)
			if bone>=0:return socket_world_transform(skeleton)*skeleton.get_bone_global_pose(bone)*relative
	return mount.global_transform

static func play(root: Node, clip: String, loop := false, speed := 1.0) -> void:
	var player := find(root, "AnimationPlayer") as AnimationPlayer
	if not player:
		return
	for key in player.get_animation_list():
		if key == clip or key.ends_with("/" + clip) or key.ends_with("|" + clip):
			player.get_animation(key).loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
			player.play(key, 0.15, speed)
			return

static func animation(id: String, family := "tensor") -> Animation:
	var cache_id := family + "/" + id
	if animations.has(cache_id):
		return animations[cache_id]
	var started := Time.get_ticks_usec() if profile_loads else 0
	var path := "res://assets/animations/%s/%s.glb" % [family,id]
	if not ResourceLoader.exists(path):
		return null
	var result: Animation
	var packed := load(path) as PackedScene
	var state := packed.get_state()
	# Imported animation libraries are resources. Extract the clip directly
	# instead of constructing and freeing an entire robot skeleton per clip.
	for node in state.get_node_count():
		if state.get_node_type(node)!=&"AnimationPlayer": continue
		for property in state.get_node_property_count(node):
			if state.get_node_property_name(node,property)!=&"libraries": continue
			var libraries: Dictionary=state.get_node_property_value(node,property)
			for library: AnimationLibrary in libraries.values():
				for key in library.get_animation_list():
					if key!="RESET":
						result=library.get_animation(key).duplicate()
						break
				if result: break
			if result: break
		if result: break
	# Preserve support for scenes whose controller comes from an instanced scene.
	if result==null:
		var root: Node=packed.instantiate()
		var player:=find(root,"AnimationPlayer") as AnimationPlayer
		if player:
			for key in player.get_animation_list():
				if key!="RESET":
					result=player.get_animation(key).duplicate()
					break
		root.free()
	if result:
		# Animation-only exports have the same skeleton but different scene roots.
		for track in range(result.get_track_count() - 1, -1, -1):
			var old := String(result.track_get_path(track))
			if not ":" in old:
				result.remove_track(track)
				continue
			var bone := old.get_slice(":", 1)
			if bone == "Root" and result.track_get_type(track) == Animation.TYPE_POSITION_3D:
				# Preserve stride calibration before removing physical root translation.
				var count := result.track_get_key_count(track)
				if count > 1:
					var first: Vector3 = result.track_get_key_value(track, 0)
					var last: Vector3 = result.track_get_key_value(track, count - 1)
					var travel := Vector2(last.x-first.x,last.z-first.z).length()
					result.set_meta("stride_distance",travel)
				result.remove_track(track)
			else:
				result.track_set_path(track, NodePath("Skeleton3D:" + bone))
	animations[cache_id] = result
	if profile_loads: record_load("animation/"+cache_id,started)
	return result

static func playback_animation(id: String, family: String, one_shot: bool, strip_root_rotation: bool) -> Animation:
	var source := animation(id,family)
	if source==null: return null
	var key := [source.get_instance_id(),one_shot,strip_root_rotation]
	if playback_animations.has(key): return playback_animations[key]
	# Players own their clocks/blends; these derived clips are shared read-only.
	# Keep source tracks intact for locomotion and aim sampling.
	var result := source.duplicate() as Animation
	result.loop_mode=Animation.LOOP_NONE if one_shot else Animation.LOOP_LINEAR
	if strip_root_rotation:
		for track in range(result.get_track_count()-1,-1,-1):
			if result.track_get_type(track)==Animation.TYPE_ROTATION_3D and String(result.track_get_path(track)).ends_with(":Root"):
				result.remove_track(track)
	playback_animations[key]=result
	return result

static func robot_accent(root: Node, primary: Color, model: String) -> Color:
	var teams := {"ecb846":"yellow", "689649":"green", "3878b4":"blue", "b74740":"red"}
	var team: String = teams.get(primary.to_html(false), "")
	if not team.is_empty():
		var rig: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/characters/%s/%s_rig.json" % [model, model]))
		var preset: Dictionary = rig.team_presets[team]
		var secondary_key: String = preset.keys().filter(func(key): return material_role(key)=="M_Secondary")[0]
		var rgb: Array = preset[secondary_key]
		# Blender's material values are linear; Godot's albedo property is sRGB.
		return Color(rgb[0], rgb[1], rgb[2]).linear_to_srgb()
	for mesh: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.mesh.surface_get_material(surface) as StandardMaterial3D
			if material != null and material_role(material.resource_name) == "M_Secondary": return material.albedo_color
	return Color("707073")

static func paint(root: Node, primary: Color, secondary: Color, head := "projector", dark := false, upper_body := "default") -> void:
	if root is MeshInstance3D:
		if String(root.name).begins_with("SK_TensorHead"):
			root.visible = String(root.name).to_lower().ends_with(head)
		if String(root.name).begins_with("SK_TensorUpperBody"):
			root.visible = String(root.name).to_lower().ends_with(upper_body)
		for i in root.mesh.get_surface_count():
			var source = root.get_active_material(i)
			if source is StandardMaterial3D:
				var mat: StandardMaterial3D = source if source.get_meta("paint_owner",0) == root.get_instance_id() else source.duplicate()
				mat.set_meta("paint_owner",root.get_instance_id())
				var authored_emission: bool = source.get_meta("authored_emission",source.emission_enabled)
				mat.set_meta("authored_emission",authored_emission)
				mat.emission_enabled = authored_emission and not dark
				if material_role(source.resource_name) == "M_Primary": mat.albedo_color = primary
				if material_role(source.resource_name) == "M_Secondary": mat.albedo_color = secondary
				root.set_surface_override_material(i, mat)
	for child in root.get_children():
		paint(child, primary, secondary, head, dark, upper_body)

static func extinguished_material(source: Material, cache: Dictionary) -> Material:
	if not source is StandardMaterial3D: return source
	# Match-owned immutable finishes outlive individual corpse instances.
	var key := [source.get_instance_id(), source.albedo_color]
	if cache.has(key): return cache[key]
	var result := source.duplicate() as StandardMaterial3D
	result.emission_enabled = false
	cache[key] = result
	return result

static func material(color: Color, emission := 0.0) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.6
	mat.emission_enabled = emission > 0
	mat.emission = color
	mat.emission_energy_multiplier = emission
	return mat

static func sphere(parent: Node3D, radius: float, color: Color) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2
	node.mesh = mesh
	node.material_override = material(color, 2.0)
	parent.add_child(node)
	return node
