extends SceneTree

# Runs against the custom NVIDIA backport only; never enables the addon.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	var simple := "--simple" in args
	var raster := "--raster" in args
	var rr := "--rr" in args
	var rr_supported: bool = Engine.has_singleton("Streamline") and Engine.get_singleton("Streamline").get_capability(2)
	if rr and not rr_supported:
		push_error("DLSS Ray Reconstruction is unavailable; refusing to report a fallback as RR.")
		quit(4)
		return
	root.size = Vector2i(1920, 1080)
	root.msaa_3d = Viewport.MSAA_DISABLED
	root.scaling_3d_scale = 0.5
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var scene: Node3D
	if simple:
		scene = Node3D.new()
		root.add_child(scene)
		for i in range(4):
			var mesh := MeshInstance3D.new()
			var box := BoxMesh.new()
			box.size = Vector3(12, 0.2, 12) if i == 0 else Vector3.ONE * 1.5
			mesh.mesh = box
			mesh.position = Vector3(0, -0.1, 0) if i == 0 else Vector3((i - 2) * 2, 0.75, 0)
			var material := StandardMaterial3D.new()
			material.albedo_color = [Color(0.6,0.6,0.6), Color(0.8,0.1,0.05), Color(0.9,0.7,0.2), Color(0.1,0.3,0.8)][i]
			material.metallic = 0.9 if i == 2 else 0.0
			material.roughness = 0.08 if i == 0 or i == 2 else 0.6
			mesh.material_override = material
			scene.add_child(mesh)
		var light := DirectionalLight3D.new()
		light.rotation_degrees = Vector3(-45,-30,0)
		light.light_energy = 2.0
		light.shadow_enabled = true
		scene.add_child(light)
		var world := WorldEnvironment.new()
		world.environment = Environment.new()
		world.environment.background_mode = Environment.BG_COLOR
		world.environment.background_color = Color(0.15,0.2,0.3)
		world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		world.environment.ambient_light_color = Color(0.3,0.3,0.3)
		scene.add_child(world)
	else:
		var game := ArenaMatch.new()
		game.count = 2
		game.map_id = "faceoff"
		root.add_child(game)
		scene = game
		for frame in range(12):
			await physics_frame
		game.map.assembly.seek(5.0, true)
		game.map.assembly.pause()
		for robot in game.robots:
			robot.show()
	var camera := Camera3D.new()
	scene.add_child(camera)
	camera.position = Vector3(6,4,8) if simple else Vector3(55,38,60)
	camera.look_at(Vector3(0,0.5,0) if simple else Vector3(0,8,0))
	camera.current = true
	var environment := scene.get_world_3d().environment
	if not environment.has_method("set_pathtracing_enabled"):
		push_error("This executable does not contain NVIDIA path tracing.")
		quit(2)
		return
	environment.set("pathtracing_samples_per_pixel", 1)
	environment.set("pathtracing_max_bounces", 3)
	environment.set("pathtracing_denoiser", 1 if rr else 0)
	environment.set("pathtracing_enabled", not raster)
	if rr:
		root.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS
	var samples := PackedFloat64Array()
	var previous := Time.get_ticks_usec()
	var max_instances := 0
	for frame in range(240):
		await process_frame
		var now := Time.get_ticks_usec()
		if frame >= 120:
			samples.append((now - previous) / 1000.0)
		previous = now
		max_instances = maxi(max_instances, root.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_RT_TLAS_INSTANCES))
		if frame % 60 == 0:
			print("NVIDIA_RT_PROGRESS frame=",frame," tlas=",max_instances)
	await RenderingServer.frame_post_draw
	var name := "nvidia-" + ("simple" if simple else "faceoff") + ("-raster" if raster else ("-rr" if rr else "-raw"))
	if "--validation" in args:
		name += "-validation"
	DirAccess.make_dir_recursive_absolute("res://reports")
	root.get_texture().get_image().save_png("res://reports/" + name + ".png")
	samples.sort()
	var report := {"engine": Engine.get_version_info(), "scene": "simple" if simple else "live Faceoff, 2 robots", "raytracing_requested": not raster, "rr_requested": rr, "max_tlas_instances": max_instances, "output": "1920x1080", "internal_scale": 0.5, "frame_ms_p50": samples[60], "frame_ms_p95": samples[114], "frame_ms_max": samples[-1], "production_release": false}
	report["rr_supported"] = rr_supported
	report["validation_requested"] = "--validation" in args
	FileAccess.open("res://reports/" + name + ".json", FileAccess.WRITE).store_string(JSON.stringify(report,"\t"))
	print("NVIDIA_RT_RESULT ", JSON.stringify(report))
	scene.queue_free()
	await process_frame
	quit(0 if raster or max_instances > 0 else 3)
