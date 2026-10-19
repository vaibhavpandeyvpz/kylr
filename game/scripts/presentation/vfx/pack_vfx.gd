class_name PackVfx
extends RefCounted

# Instantiate isolated runtime effect resources while sharing immutable geometry.
static func instantiate(scene: PackedScene) -> Node3D:
	var root := scene.instantiate() as Node3D
	if "autoplay" in root: root.set("autoplay", false)
	prepare(root)
	return root

static func apply_palette(root: Node3D) -> void:
	# PackedScene exports can be assigned before controller children exist.
	# Apply the authored controller palette after resource isolation and parenting.
	for key in ["primary_color", "secondary_color", "tertiary_color"]:
		if key in root:
			var color: Color = root.get(key)
			for material in materials(root): material.set_shader_parameter(key, color)

static func prepare(node: Node) -> void:
	if node is GeometryInstance3D:
		node.layers = 1
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if node.material_override: node.material_override = node.material_override.duplicate()
	if node is MeshInstance3D and node.mesh and node.material_override == null:
		# Geometry is immutable; isolate only the per-instance surface materials.
		for index in node.mesh.get_surface_count():
			var material: Material = node.get_active_material(index)
			if material: node.set_surface_override_material(index, material.duplicate())
	if node is GPUParticles3D:
		if node.process_material: node.process_material = node.process_material.duplicate()
		for index in node.draw_passes:
			var mesh: Mesh = node.get("draw_pass_" + str(index + 1))
			# Projectile controllers animate material_override. Their
			# draw geometry can stay shared across every shot and exhaust plume.
			if mesh and node.material_override == null and mesh is PrimitiveMesh and mesh.material:
				mesh = mesh.duplicate()
				mesh.material = mesh.material.duplicate()
				node.set("draw_pass_" + str(index + 1), mesh)
	if node is Light3D:
		node.shadow_enabled = false
		node.light_cull_mask = 1
		if node is OmniLight3D: node.omni_range = minf(node.omni_range, 3.5)
	if node is Decal: node.visible = false
	for child in node.get_children(): prepare(child)

static func materials(root: Node) -> Array[ShaderMaterial]:
	var result: Array[ShaderMaterial] = []
	if root is GeometryInstance3D and root.material_override is ShaderMaterial: result.append(root.material_override)
	if root is MeshInstance3D and root.mesh:
		for index in root.mesh.get_surface_count():
			var material: Material = root.get_active_material(index)
			if material is ShaderMaterial and not result.has(material): result.append(material)
	if root is GPUParticles3D:
		for index in root.draw_passes:
			var mesh: Mesh = root.get("draw_pass_" + str(index + 1))
			if mesh is PrimitiveMesh and mesh.material is ShaderMaterial: result.append(mesh.material)
	for child in root.get_children(): result.append_array(materials(child))
	return result

static func motion(root: Node, reduced: bool) -> void:
	if root is OriginalEffect: root.reduced_motion = reduced
	for material in materials(root):
		material.set_shader_parameter("time_scale", 0.0 if reduced else 1.0)
		material.set_shader_parameter("speed_scale", 0.0 if reduced else 1.0)
	for child in root.get_children():
		if child is AnimationPlayer: child.speed_scale = 0.0 if reduced else 1.0
		if child is GPUParticles3D: child.speed_scale = 0.0 if reduced else 1.0

static func play_once(root: Node3D) -> float:
	if root is OriginalEffect: return root.play()
	var animation := root.get_node_or_null("AnimationPlayer") as AnimationPlayer
	var duration := 0.0
	if animation:
		animation.stop()
		var id := "oneshot" if animation.has_animation("oneshot") else "main"
		animation.play(id)
		animation.seek(0.0, true)
		duration = animation.get_animation(id).length / maxf(animation.speed_scale, 0.01)
	for child in root.get_children():
		if child is GPUParticles3D:
			child.restart()
			child.emitting = true
			duration = maxf(duration, child.lifetime / maxf(child.speed_scale, 0.01))
	return maxf(duration, 0.1)
