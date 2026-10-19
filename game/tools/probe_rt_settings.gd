extends SceneTree

func _initialize():
	call_deferred("run")

func run():
	var reason := Preferences.ray_tracing_unavailable_reason()
	if not reason.is_empty():
		push_error(reason)
		quit(2)
		return
	var game := ArenaMatch.new()
	game.count=2
	game.map_id="skyfall"
	root.add_child(game)
	for frame in range(12): await physics_frame
	game.map.assembly.seek(5.0,true)
	game.map.assembly.pause()
	var camera := Camera3D.new()
	game.add_child(camera)
	camera.position=Vector3(55,38,60)
	camera.look_at(Vector3(0,8,0))
	camera.current=true
	var prefs := Preferences.new("user://rt_probe_unused.cfg")
	for key in Preferences.QUALITY_PRESETS[3]: prefs.values[key]=Preferences.QUALITY_PRESETS[3][key]
	var diagnostic := "--diagnostic" in OS.get_cmdline_user_args()
	for enabled in ([true] if diagnostic else [true,false,true]):
		printerr("RT_SETTINGS_PHASE ",enabled)
		prefs.values.ray_tracing=enabled
		prefs.apply_rendering(game)
		assert(game.get_world_3d().environment.get("pathtracing_enabled")==enabled)
		assert(root.msaa_3d==(Viewport.MSAA_DISABLED if enabled else Viewport.MSAA_8X))
		for frame in range(6 if diagnostic else 90): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://reports/rt-settings-%s.png" % str(enabled))
	game.queue_free()
	for frame in range(5): await process_frame
	print("RT_SETTINGS_DIAGNOSTIC_DONE" if diagnostic else "RT_SETTINGS_PASS: supported Ultra, raster restore and RT re-enable")
	quit()
