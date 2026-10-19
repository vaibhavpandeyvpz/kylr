extends SceneTree

# Runs against the custom NVIDIA backport only; never enables the addon.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	# Keep the measured render target independent of desktop window resizing.
	var test_view := SubViewport.new()
	test_view.own_world_3d = true
	test_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(test_view)
	var internal_scale := 0.5
	for arg in args:
		if arg.begins_with("--scale="): internal_scale = clampf(arg.trim_prefix("--scale=").to_float(), 0.25, 1.0)
	var simple := "--simple" in args
	var raster := "--raster" in args
	var rr := "--rr" in args
	var soak := "--soak" in args
	var lifecycle := "--lifecycle" in args
	var timings := "--timings" in args
	var costs := "--costs" in args
	if timings: RenderingServer.viewport_set_measure_render_time(test_view.get_viewport_rid(), true)
	var map_id := "skyfall" if "--skyfall" in args else "faceoff"
	var robots := 10 if "--ten-robots" in args else 2
	var rr_supported: bool = Engine.has_singleton("Streamline") and Engine.get_singleton("Streamline").get_capability(2)
	if rr and not rr_supported:
		push_error("DLSS Ray Reconstruction is unavailable; refusing to report a fallback as RR.")
		quit(4)
		return
	test_view.size = Vector2i(1920, 1080)
	test_view.msaa_3d = Viewport.MSAA_DISABLED
	test_view.scaling_3d_scale = internal_scale
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var scene: Node3D
	if simple:
		scene = Node3D.new()
		test_view.add_child(scene)
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
		game.count = robots
		game.map_id = map_id
		test_view.add_child(game)
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
		test_view.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS
	if lifecycle:
		for cycle in range(3):
			environment.set("pathtracing_enabled", false)
			test_view.size = Vector2i(1280, 720)
			test_view.scaling_3d_scale = 0.67
			for frame in range(30): await process_frame
			environment.set("pathtracing_enabled", not raster)
			test_view.size = Vector2i(1920, 1080)
			test_view.scaling_3d_scale = internal_scale
			for frame in range(30): await process_frame
	var gpu_samples := PackedFloat64Array()
	var render_cpu_samples := PackedFloat64Array()
	var physics_samples := PackedFloat64Array()
	var samples := PackedFloat64Array()
	var previous := Time.get_ticks_usec()
	var max_instances := 0
	var frame := 0
	var measured_start := Time.get_ticks_usec()
	var physics_start := Engine.get_physics_frames()
	while frame < 240 or (soak and Time.get_ticks_usec() - measured_start < 60000000):
		await process_frame
		var now := Time.get_ticks_usec()
		if frame == 120:
			measured_start = now
			physics_start = Engine.get_physics_frames()
			if costs:
				ArenaRobot.profile_stages = true
				ArenaRobot.stage_usec.clear()
				ArenaMap.profile_ticks = true
				ArenaMap.tick_costs.clear()
				TraversalGraph.profile_paths = true
				TraversalGraph.path_stats.clear()
				ArenaCombat.profile_queries = true
				ArenaCombat.query_stats.clear()
				Assets.profile_loads = true
				Assets.load_stats.clear()
		if frame >= 120:
			samples.append((now - previous) / 1000.0)
			if timings:
				gpu_samples.append(RenderingServer.viewport_get_measured_render_time_gpu(test_view.get_viewport_rid()))
				render_cpu_samples.append(RenderingServer.viewport_get_measured_render_time_cpu(test_view.get_viewport_rid()))
				physics_samples.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0)
		previous = now
		max_instances = maxi(max_instances, test_view.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_RT_TLAS_INSTANCES))
		if soak and not simple:
			var angle := float(now - measured_start) / 1000000.0 * 0.1
			camera.position = Vector3(cos(angle) * 75.0, 38.0, sin(angle) * 75.0)
			camera.look_at(Vector3(0, 8, 0))
		if frame % 300 == 0:
			print("NVIDIA_RT_PROGRESS frame=",frame," tlas=",max_instances)
		frame += 1
	var measured_seconds := float(Time.get_ticks_usec() - measured_start) / 1000000.0
	await RenderingServer.frame_post_draw
	var name := "nvidia-" + ("simple" if simple else map_id) + ("-raster" if raster else ("-rr" if rr else "-raw"))
	if "--validation" in args:
		name += "-validation"
	name += "-acceptance-fixed"
	if robots == 10: name += "-10robots"
	if soak: name += "-soak"
	if lifecycle: name += "-lifecycle"
	if not is_equal_approx(internal_scale, 0.5): name += "-scale%d" % roundi(internal_scale * 100)
	if timings: name += "-timings"
	if costs: name += "-costs"
	DirAccess.make_dir_recursive_absolute("res://reports")
	var captured := test_view.get_texture().get_image()
	if captured.get_size() != Vector2i(1920, 1080):
		push_error("Acceptance render target changed dimensions: %s" % captured.get_size())
		quit(6)
		return
	captured.save_png("res://reports/" + name + ".png")
	samples.sort()
	var report := {"engine": Engine.get_version_info(), "scene": "simple" if simple else "live %s, %d robots" % [map_id, robots], "raytracing_requested": not raster, "rr_requested": rr, "max_tlas_instances": max_instances, "output": "1920x1080", "internal_scale": internal_scale, "frame_ms_p50": samples[int(samples.size() * 0.5)], "frame_ms_p95": samples[int(samples.size() * 0.95)], "frame_ms_max": samples[-1], "production_release": false}
	report["fixed_render_viewport"] = true
	report["measured_seconds"] = measured_seconds
	report["sample_count"] = samples.size()
	report["camera_orbit"] = soak
	report["resize_mode_cycles"] = 3 if lifecycle else 0
	report["meets_p95_60fps"] = samples[int(samples.size() * 0.95)] <= 1000.0 / 60.0
	if timings:
		gpu_samples.sort()
		render_cpu_samples.sort()
		physics_samples.sort()
		report["gpu_ms_p50"] = gpu_samples[int(gpu_samples.size() * 0.5)]
		report["gpu_ms_p95"] = gpu_samples[int(gpu_samples.size() * 0.95)]
		report["render_cpu_ms_p95"] = render_cpu_samples[int(render_cpu_samples.size() * 0.95)]
		report["physics_monitor_ms_p95"] = physics_samples[int(physics_samples.size() * 0.95)]
	if costs:
		var ticks := maxf(1, Engine.get_physics_frames() - physics_start)
		report["physics_ticks"] = ticks
		report["robot_stages_us_per_tick"] = {}
		report["map_stages_us_per_tick"] = {}
		for key in ArenaRobot.stage_usec: report.robot_stages_us_per_tick[key] = ArenaRobot.stage_usec[key] / ticks
		for key in ArenaMap.tick_costs: report.map_stages_us_per_tick[key] = ArenaMap.tick_costs[key] / ticks
		report["navigation_paths"] = TraversalGraph.path_stats.duplicate(true)
		report["collision_queries"] = ArenaCombat.query_stats.duplicate(true)
		report["asset_loads"] = Assets.load_stats.duplicate(true)
		ArenaRobot.profile_stages = false
		ArenaMap.profile_ticks = false
		TraversalGraph.profile_paths = false
		ArenaCombat.profile_queries = false
		Assets.profile_loads = false
	report["rr_supported"] = rr_supported
	report["validation_requested"] = "--validation" in args
	FileAccess.open("res://reports/" + name + ".json", FileAccess.WRITE).store_string(JSON.stringify(report,"\t"))
	print("NVIDIA_RT_RESULT ", JSON.stringify(report))
	scene.queue_free()
	await process_frame
	if soak and "--validation" not in args and not report.meets_p95_60fps:
		quit(5)
	else:
		quit(0 if raster or max_instances > 0 else 3)
