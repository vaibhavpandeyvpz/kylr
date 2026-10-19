extends SceneTree

# Compare the cached sky with the same shader still marked as time-dependent.
var views: Array[SubViewport] = []
var materials: Array[ShaderMaterial] = []

func _initialize() -> void:
	run.call_deferred()

func capture() -> Array[Image]:
	for frame in 12:
		await process_frame
	await RenderingServer.frame_post_draw
	var images: Array[Image] = []
	for view in views: images.append(view.get_texture().get_image())
	return images

func error(a: Image, b: Image, region: Rect2i) -> float:
	var maximum := 0.0
	for y in range(region.position.y, region.end.y):
		for x in range(region.position.x, region.end.x):
			var delta := a.get_pixel(x, y) - b.get_pixel(x, y)
			maximum = maxf(maximum, maxf(absf(delta.r), maxf(absf(delta.g), absf(delta.b))))
	return maximum

func run() -> void:
	DirAccess.make_dir_recursive_absolute("res://reports/sky-clock")
	for legacy in [true, false]:
		var view := SubViewport.new()
		view.size = Vector2i(800, 600)
		view.own_world_3d = true
		view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(view)
		views.append(view)
		var map := ArenaMap.new()
		map.add_world()
		for child in map.get_children():
			map.remove_child(child)
			view.add_child(child)
			if child is WorldEnvironment:
				var material: ShaderMaterial = child.environment.sky.sky_material
				if legacy:
					var shader := Shader.new()
					var clock := "float clock = reduced_motion ? 0.0 : arena_sky_time;"
					if not material.shader.code.contains(clock):
						push_error("Sky clock probe no longer matches the runtime shader");quit(2);return
					shader.code = material.shader.code.replace(clock,"float clock = reduced_motion ? 0.0 : (arena_sky_time + TIME * 0.0);")
					material.shader = shader
				materials.append(material)
		map.free()
		for index in 3:
			var ball := MeshInstance3D.new()
			var sphere := SphereMesh.new()
			sphere.radius = 0.45
			sphere.height = 0.9
			ball.mesh = sphere
			var material := StandardMaterial3D.new()
			material.metallic = 1.0
			material.albedo_color = Color(0.65, 0.68, 0.72)
			material.roughness = [0.05, 0.3, 0.65][index]
			ball.material_override = material
			view.add_child(ball)
			ball.position.x = (index - 1) * 1.15
		var camera := Camera3D.new()
		view.add_child(camera)
		camera.position = Vector3(0, 0, 3.5)
		camera.current = true
	RenderingServer.global_shader_parameter_set("arena_sky_time", 1.0)
	await create_timer(3).timeout
	var first := await capture()
	RenderingServer.global_shader_parameter_set("arena_sky_time", 61.0)
	var later := await capture()
	var full := Rect2i(0, 0, 800, 600)
	var parity := maxf(error(first[0], first[1], full), error(later[0], later[1], full))
	var cloud_change := error(first[1], later[1], Rect2i(0, 0, 800, 120))
	var metal_change := error(first[1], later[1], Rect2i(365, 265, 70, 70))
	for material in materials: material.set_shader_parameter("reduced_motion", true)
	var frozen := await capture()
	RenderingServer.global_shader_parameter_set("arena_sky_time", 121.0)
	var still := await capture()
	var reduced_motion_error := error(frozen[1], still[1], full)
	first[1].save_png("res://reports/sky-clock/start.png")
	later[1].save_png("res://reports/sky-clock/later.png")
	print("SKY_CLOCK parity=", parity, " cloud_change=", cloud_change,
		" metal_change=", metal_change, " reduced_motion_error=", reduced_motion_error)
	quit(0 if parity <= 1.0 / 255.0 and cloud_change > 1.0 / 255.0
		and metal_change <= 1.0 / 255.0 and reduced_motion_error <= 1.0 / 255.0 else 1)
