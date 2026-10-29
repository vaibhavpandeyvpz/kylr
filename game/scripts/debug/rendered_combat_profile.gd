class_name RenderedCombatProfile
extends Node
const MapOcclusion = preload("res://scripts/debug/map_occlusion_diagnostic.gd")
const AlphaPassIsolation = preload("res://scripts/debug/alpha_pass_isolation.gd")
## Real-time frame percentiles, with live match/UI, isolated preferences and seed.
var root: Window:
	get: return get_tree().root
var app: Node3D
var game: ArenaMatch
var measuring := false
var last_usec := 0
var rows: Array = []
var draw_rows: Array = []
var occlusion_report: Dictionary = {}
var occlusion_phase_rows: Array = [[],[],[]]
var occlusion_phase_queries: Array = [{},{},{}]
var occlusion_phase := 0
var measure_started_usec := 0
var occlusion_query_start: Dictionary = {}
var options := {}
var alpha_isolation: RefCounted
var separate_render_thread := false
var rendering_preparation: Dictionary = {}
var preparation_audio_was_muted := false
var stress_clock := 0.0
var arena_stress: RefCounted
var stress_active := false
var retained_brains: Array = []
var stress_weapons: Array[String] = []
var shot_counts := {}
var shot_baselines := {}
var stream_samples := {}
var contact_samples := {}
var damage_samples := 0
var repair_fixture := {}
var repair_pending := false
var repair_started := false
var repair_samples := 0
var world_event_requested := false
var cost_ticks := 0
var tree_updates_by_physics_frame: Dictionary = {}
var tree_updates_since_frame := 0
var tree_updates_discarded := 0
var tree_frame_samples: Dictionary = {}
var stress_center := Vector3.ZERO
var stress_camera_position := Vector3.ZERO
var requested_size := Vector2i.ZERO
var display_screen := 0
var display_changed_during_sample := false
var requested_vsync:int=DisplayServer.VSYNC_ENABLED
var followed_bot: ArenaRobot
var follow_previous := Vector3.ZERO
var follow_camera_previous := Vector3.ZERO
var follow_distance := 0.0
var follow_camera_distance := 0.0
var follow_moving_seconds := 0.0
var follow_active_seconds := 0.0
var follow_shots_started := 0
var match_pass := 0
var timeline: Array = []
var timeline_clock := 0.0
var timeline_row_start := 0
var timeline_frames: Array = []
var timeline_stages := {}
var timeline_ticks := 0
var simulation_checkpoints: Array = []
var next_simulation_checkpoint := 0.0

func record_simulation_checkpoint() -> void:
	var actors: Array = []
	for robot: ArenaRobot in game.robots:
		actors.append({"id":robot.robot_id,"team":robot.team,"position":[robot.position.x,robot.position.y,robot.position.z],"velocity":[robot.velocity.x,robot.velocity.y,robot.velocity.z],"goal":robot.brain.goal_kind if robot.brain else "human","decision":robot.brain.decision if robot.brain else 0.0,"spawn_remaining":robot.spawn_remaining,"protection":robot.protection,"ah":robot.ah,"ep":robot.ep})
	simulation_checkpoints.append({"elapsed":game.elapsed,"countdown":game.countdown,"rng_state":str(game.rng.state),"robots":actors})

func report_directory() -> String:
	return ProjectSettings.globalize_path(String(options.get("report-dir", "res://reports/performance")))

func wait_wall_seconds(seconds: float) -> void:
	var started:=Time.get_ticks_usec()
	while Time.get_ticks_usec()-started<seconds*1000000.0:
		await get_tree().process_frame

func record_tree_update(_status: int) -> void:
	if not measuring: return
	var frame := Engine.get_physics_frames()
	tree_updates_by_physics_frame[frame] = int(tree_updates_by_physics_frame.get(frame, 0)) + 1
	tree_updates_since_frame += 1

func record_timeline(label: String) -> void:
	var row := {"label":label,"pass":match_pass,"uptime_s":Time.get_ticks_msec()/1000.0,
		"nodes":Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		"objects":Performance.get_monitor(Performance.OBJECT_COUNT),
		"resources":Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT),
		"orphan_nodes":Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT),
		"physics_active_objects":Performance.get_monitor(Performance.PHYSICS_3D_ACTIVE_OBJECTS),
		"physics_collision_pairs":Performance.get_monitor(Performance.PHYSICS_3D_COLLISION_PAIRS),
		"video_memory_bytes":Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED),
		"texture_memory_bytes":Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED),
		"buffer_memory_bytes":Performance.get_monitor(Performance.RENDER_BUFFER_MEM_USED),
		"scene_cache":Assets.scenes.size(),"animation_cache":Assets.animations.size(),
		"matte_cache":Assets.matte_finishes.size(),"glass_cache":Assets.glass_finishes.size(),
		"hull_cache":CollisionRig.hull_cache.size()}
	if is_instance_valid(game) and game.is_inside_tree():
		row["match_elapsed_s"]=game.elapsed
		row["corpses"]=game.corpses.size()
		row["drops"]=game.drops.size()
		row["effects_children"]=game.effects.get_child_count()
		row["kills"]=game.robots.reduce(func(total,robot): return total+robot.kills,0)
		row["deaths"]=game.robots.reduce(func(total,robot): return total+robot.deaths,0)
		row["alive"]=game.robots.filter(func(robot): return robot.alive).size()
		row["effect_pools"]={}
		for key in ["spark_pool","lightning_pool","emp_pool","rocket_pool","grenade_pool","pulse_pool","bio_pool","flak_pool","fire_orb_pool","muzzle_pool","idle_emp_charges"]:
			row.effect_pools[key]=game.effects.get(key).size()
	if not timeline_frames.is_empty():
		var total := 0.0
		for ms in timeline_frames: total += ms
		row["fps"]=1000.0*timeline_frames.size()/total
		row["frame_ms"]=summary(timeline_frames)
		timeline_frames=[]
	if rows.size()>timeline_row_start:
		var gpu: Array=[]
		var render_cpu: Array=[]
		for index in range(timeline_row_start,rows.size()):
			gpu.append(rows[index][3])
			render_cpu.append(rows[index][4])
		row["gpu_ms"]=summary(gpu)
		row["render_cpu_ms"]=summary(render_cpu)
		timeline_row_start=rows.size()
	if options.has("costs") and cost_ticks>timeline_ticks:
		row["robot_stages_us_per_tick"]={}
		for key in ArenaRobot.stage_usec:
			row.robot_stages_us_per_tick[key]=(ArenaRobot.stage_usec[key]-timeline_stages.get(key,0))/float(cost_ticks-timeline_ticks)
		timeline_stages=ArenaRobot.stage_usec.duplicate()
		timeline_ticks=cost_ticks
	timeline.append(row)
	var directory := report_directory()
	DirAccess.make_dir_recursive_absolute(directory)
	FileAccess.open(directory+"/"+String(options.get("name","baseline"))+"-timeline.json",FileAccess.WRITE).store_string(JSON.stringify(timeline,"  "))

func _ready() -> void:
	process_priority = -1000
	process_physics_priority = -1000
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			options[arg.get_slice("=",0).trim_prefix("--")] = arg.get_slice("=",1)
	if options.has("arena-stress"):
		if options.has("stress") or options.has("follow-bot") or options.get("view","")=="overview" or int(options.get("matches",1))!=1:
			push_error("Arena stress cannot combine with stationary stress, follow-bot, overview or repeated matches")
			get_tree().quit(1)
			return
		for key in {"mode":"DM","robots":10,"warmup":6,"seconds":12}:
			if not options.has(key): options[key]={"mode":"DM","robots":10,"warmup":6,"seconds":12}[key]
	if options.has("stress") and int(options.get("matches",1))>1:
		push_error("Repeated matches currently require live AI, without --stress")
		get_tree().quit(1)
		return
	if options.has("frame-times-only") and (options.has("timeline") or options.has("draw-stats")):
		push_error("Frame-times-only excludes synchronous timeline/draw-stat capture")
		get_tree().quit(1)
		return
	if options.has("alpha-isolation"):
		if String(options["alpha-isolation"]) not in ["overview","effects","layered"] or not options.has("arena-stress") or not options.has("gpu-profile-markers") or absf(float(options.get("seconds",0))-56.0)>0.001 or OS.get_environment("GODOT_GPU_PROFILE_ALPHA_FILTER")!="1":
			push_error("Alpha isolation requires arena stress, native profiling, 56 seconds and the explicit engine diagnostic")
			get_tree().quit(1)
			return
	if options.has("diagnostic-raster-scale") or options.has("diagnostic-raster-upscaler"):
		var scale_text := String(options.get("diagnostic-raster-scale","1.0"))
		if not scale_text.is_valid_float() or not is_finite(float(scale_text)) or float(scale_text)<0.5 or float(scale_text)>1.0 or String(options.get("diagnostic-raster-upscaler","fsr2")) not in ["bilinear","fsr2"] or int(options.get("quality",2)) not in [0,1,2]:
			push_error("Raster diagnostic requires a raster preset, scale 0.5..1.0 and bilinear or fsr2")
			get_tree().quit(1)
			return
	run.call_deferred()

func display_state() -> Dictionary:
	var screen_count:=DisplayServer.get_screen_count()
	var screen_available:=display_screen>=0 and display_screen<screen_count
	return {"mode":int(root.mode),"screen":display_screen,"screen_count":screen_count,"screen_available":screen_available,"vsync":int(DisplayServer.window_get_vsync_mode()),"requested_vsync":requested_vsync,"max_fps":Engine.max_fps,
		"focused":DisplayServer.window_is_focused(),"visible":root.visible,
		"screen_position":str(DisplayServer.screen_get_position(display_screen)) if screen_available else null,
		"screen_size":str(DisplayServer.screen_get_size(display_screen)) if screen_available else null,
		"window_position":str(DisplayServer.window_get_position()),
		"window_size":str(DisplayServer.window_get_size()),
		"render_size":str(physical_render_size()),
		"ui_raster_size":str(Preferences.effective_area(root.size,requested_size).size),
		"requested_size":str(requested_size),"changed_during_sample":display_changed_during_sample}

func physical_render_size() -> Vector2i:
	var extent:=Preferences.effective_area(root.size,requested_size).size
	return Vector2i((Vector2(extent)*root.scaling_3d_scale).round())

func valid_display() -> bool:
	var valid: bool = display_screen>=0 and display_screen<DisplayServer.get_screen_count() and \
		root.mode == Window.MODE_FULLSCREEN and \
		int(DisplayServer.window_get_vsync_mode()) == requested_vsync and \
		DisplayServer.window_get_position() == DisplayServer.screen_get_position(display_screen) and \
		DisplayServer.window_get_size() == DisplayServer.screen_get_size(display_screen) and \
		root.content_scale_mode == Window.CONTENT_SCALE_MODE_CANVAS_ITEMS and \
		(options.has("diagnostic-raster-scale") or physical_render_size() == requested_size)
	if not valid: push_error("Invalid benchmark display: " + JSON.stringify(display_state()))
	return valid

func run() -> void:
	match_pass += 1
	if options.has("arena-stress"):
		# GPU warm-up exercises real weapon/effect pipelines, but is not the
		# presented run. Silence it before creating the menu or match audio.
		preparation_audio_was_muted=AudioServer.is_bus_mute(0)
		AudioServer.set_bus_mute(0,true)
		print("ARENA_STRESS_PREPARATION_AUDIO muted=",AudioServer.is_bus_mute(0))
	rows.clear()
	draw_rows.clear()
	cost_ticks=0
	follow_distance=0
	follow_camera_distance=0
	follow_moving_seconds=0
	follow_active_seconds=0
	timeline_clock=0
	timeline_row_start=0
	timeline_frames.clear()
	timeline_stages.clear()
	timeline_ticks=0
	simulation_checkpoints.clear()
	next_simulation_checkpoint=0.0
	seed(int(options.get("seed",120)))
	ArenaBrain.decision_phases = clampi(int(options.get("decision-phases",ArenaBrain.decision_phases)),1,16)
	var presentation:=String(options.get("vsync","project"))
	if presentation not in ["project","off","on"]:
		push_error("Profiler V-Sync must be project, off or on")
		get_tree().quit(1);return
	requested_vsync=int(ProjectSettings.get_setting("display/window/vsync/vsync_mode",DisplayServer.VSYNC_ENABLED)) if presentation=="project" else DisplayServer.VSYNC_ENABLED if presentation=="on" else DisplayServer.VSYNC_DISABLED
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(requested_vsync)
	var size := Vector2i(int(options.get("width",1920)),int(options.get("height",1080)))
	if app == null:
		app = load("res://app.tscn").instantiate()
		app.set_meta("automated_profile",true)
		root.add_child(app)
		if not app.startup_complete: await app.startup_finished
	app.prefs = Preferences.new(report_directory().path_join("preferences.cfg"))
	app.prefs.values.quality_benchmarked = true
	requested_size = size
	app.prefs.values.native_resolution=false
	app.prefs.values.resolution=size
	app.prefs.display_options.clear()
	display_screen = int(options.get("screen",DisplayServer.window_get_current_screen()))
	if display_screen<0 or display_screen>=DisplayServer.get_screen_count():
		push_error("Requested benchmark screen is unavailable: "+JSON.stringify(display_state()))
		await app.request_quit();return
	# Fullscreen owns desktop placement. Manual borderless resize/position calls
	# can race Windows' pending centering events and leave the window offscreen.
	DisplayServer.window_set_current_screen(display_screen)
	root.mode = Window.MODE_FULLSCREEN
	await get_tree().process_frame
	await get_tree().process_frame
	app.prefs.update_display_frame(root)
	# Fullscreen recreation can restore a presentation setting on some drivers.
	DisplayServer.window_set_vsync_mode(requested_vsync)
	if not valid_display():
		get_tree().quit(1)
		return
	if match_pass==1:
		root.size_changed.connect(func():
			if measuring: display_changed_during_sample = true)
	app.prefs.values.map = options.get("map","skyfall")
	app.prefs.values.type = MatchTypes.ALL.find(options.get("mode","TDM"))
	app.prefs.values.count = int(options.get("robots",10))
	app.prefs.values.difficulty = clampi(int(options.get("difficulty",1)),0,3)
	app.prefs.values.goal = 999
	app.prefs.values.name = "Profiler"
	app.prefs.values.quality = clampi(int(options.get("quality",2)),0,2)
	var preset: Dictionary = Preferences.QUALITY_PRESETS[app.prefs.values.quality]
	for key in preset: app.prefs.values[key] = preset[key]
	if options.has("arena-stress") and String(options.get("preset-lighting","0"))!="1":
		app.prefs.values.fixture_lighting = true
	if options.has("timeline"): record_timeline("before_match")
	app.set_meta("profile_roster_seed",int(options.get("seed",120)))
	await app.start_match()
	game = app.match_node
	if options.has("diagnostic-raster-scale") or options.has("diagnostic-raster-upscaler"):
		var upscaler := String(options.get("diagnostic-raster-upscaler","fsr2"))
		root.msaa_3d=Viewport.MSAA_DISABLED
		root.use_taa=false
		root.screen_space_aa=Viewport.SCREEN_SPACE_AA_DISABLED
		root.scaling_3d_mode=Viewport.SCALING_3D_MODE_FSR2 if upscaler=="fsr2" else Viewport.SCALING_3D_MODE_BILINEAR
		root.scaling_3d_scale=float(options.get("diagnostic-raster-scale",1.0))
		print("DIAGNOSTIC_RASTER_RECONSTRUCTION scale=",root.scaling_3d_scale," mode=",root.scaling_3d_mode," not_for_preset_acceptance=true")
	if options.has("arena-stress"):
		# Match loading precedes the diagnostic-only deck and weapon setup.
		# Keep preparation covered until those new materials are usable too.
		app.loading_screen.begin("Preparing benchmark…")
		await app.loading_screen.paint()
	separate_render_thread = not RenderingServer.is_on_render_thread()
	# Profiling is automated; desktop typing must not pause or steer a sample.
	app.set_process_input(false)
	app.set_process_unhandled_input(false)
	app.set_meta("automated_profile",true)
	game.set_process_unhandled_input(false)
	app.ui.set_process_input(false)
	app.ui.set_process_unhandled_input(false)
	game.rng.seed = int(options.get("seed",120))
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(),not options.has("frame-times-only"))
	# Set the diagnostic view/scale during initial readiness, rather than after
	# a wall-time delay that can switch the observer at different physics ticks.
	while game.local_robot == null and game.phase == "Waiting":
		await get_tree().physics_frame
	# Diagnostic overrides retain the shipping scene and simulation.
	if options.has("follow-bot"):
		if options.has("stress"):
			push_error("Bot following requires live AI, without --stress")
			await app.request_quit()
			return
		var id := int(options["follow-bot"])
		for candidate: ArenaRobot in game.robots:
			if candidate.robot_id == id and candidate.brain != null: followed_bot = candidate
		if followed_bot == null:
			push_error("Requested camera robot is not a live AI bot")
			await app.request_quit()
			return
		game.local_robot.body.show()
		game.local_robot.gun.visible = game.local_robot.weapon_pose_visible
		game.local_robot = followed_bot
		game.first_person.robot = followed_bot
		followed_bot.listener.make_current()
		game.camera_snap = true
		app.ui.start_hud()
		await get_tree().create_timer(2).timeout
	await get_tree().create_timer(float(options.get("warmup",20))).timeout
	if game.phase != "Active":
		push_error("Rendered profiling requires a longer warmup to reach Active play")
		get_tree().quit(1)
		return
	if options.has("stress"):
		if not start_stress(): return
		if options.has("occlusion") or options.has("occlusion-phases"):
			occlusion_report = MapOcclusion.install(game.map,root)
			if options.has("occlusion-phases"): root.use_occlusion_culling = false
		await get_tree().create_timer(5).timeout # Warm every shot/impact pipeline before sampling.
		for robot in game.robots: shot_baselines[robot.robot_id]=robot.network_shots
	if options.has("arena-stress"):
		arena_stress = preload("res://scripts/debug/arena_stress.gd").new()
		if not arena_stress.install(game,float(options.get("seconds",12)),String(options.get("preset-lighting","0"))=="1"): return
		if options.has("diagnostic-sdfgi"):
			if String(options["diagnostic-sdfgi"]) not in ["0","1"]:
				push_error("SDFGI diagnostic expects 0 or 1");await app.request_quit();return
			for world in game.find_children("*","WorldEnvironment",true,false):
				world.environment.sdfgi_enabled=String(options["diagnostic-sdfgi"])=="1"
			print("DIAGNOSTIC_SDFGI enabled=",String(options["diagnostic-sdfgi"])=="1"," not_for_acceptance=true")
		var warmup_seconds := maxf(float(options.get("combat-warmup",5)),arena_stress.orbit_seconds)
		await wait_wall_seconds(warmup_seconds)
		# The physics-driven camera can trail the wall timer by one tick. Wait
		# for its completed orbit to be drawn before reporting render readiness.
		var orbit_deadline := Time.get_ticks_msec()+10000
		while arena_stress.clock<warmup_seconds and Time.get_ticks_msec()<orbit_deadline:
			await RenderingServer.frame_post_draw
		if arena_stress.clock<warmup_seconds:
			push_error("Benchmark camera did not complete its warmup orbit")
			await app.request_quit();return
		# Installing the deck, weapons and lights can compile new shader pipelines.
		# Never count missing world geometry as a fast rendered sample.
		rendering_preparation=await app.ResourcePreparation.wait_for_rendering(get_tree(),root)
		if not rendering_preparation.ready:
			push_error("Stress rendering was not ready: "+JSON.stringify(rendering_preparation))
			arena_stress=null
			await app.request_quit()
			return
		rendering_preparation["warmup_seconds"]=warmup_seconds
		rendering_preparation["warmup_orbit_degrees"]=rad_to_deg(TAU*arena_stress.clock/arena_stress.orbit_seconds)
		rendering_preparation["loading_overlay"]=true
		app.loading_screen.finish()
		for frame in 3: await RenderingServer.frame_post_draw
		rendering_preparation["preparation_audio_muted"]=AudioServer.is_bus_mute(0)
		AudioServer.set_bus_mute(0,preparation_audio_was_muted)
		rendering_preparation["audio_state_restored"]=AudioServer.is_bus_mute(0)==preparation_audio_was_muted
		print("ARENA_STRESS_VISIBLE rendering=ready warmup_degrees=",rendering_preparation.warmup_orbit_degrees," audio_muted=",AudioServer.is_bus_mute(0))
	if options.get("view", "fpv") == "overview":
		game.third_person = true
		game.camera_rig.host.set_process(false)
		game.camera.global_position = Vector3(23,18,28)
		game.camera.look_at(Vector3(0,2,0))
		game.first_person.hide()
		game.first_person.set_process(false)
	if options.get("isolate", "") == "cpu":
		RenderingServer.viewport_set_disable_3d(root.get_viewport_rid(),true)
	if options.get("isolate", "") == "props":
		for motion in game.map.machinery: motion.set_physics_process(false)
	if options.get("isolate", "") == "armor-overlay":
		RenderingServer.frame_pre_draw.connect(func():
			for robot in game.robots:
				for mesh in robot.surface_meshes: mesh.material_overlay = null)
	if options.get("isolate", "") == "shadows":
		for light: Light3D in game.find_children("*","Light3D",true,false):
			light.shadow_enabled = false
	if options.get("isolate", "") == "fixture-shadows":
		for light: Light3D in game.find_children("NativeProjectionLight","Light3D",true,false):
			light.shadow_enabled = false
	if options.get("isolate", "") == "kinematic-hitboxes":
		for robot in game.robots:
			for body: StaticBody3D in robot.find_children("*","StaticBody3D",true,false):
				PhysicsServer3D.body_set_mode(body.get_rid(),PhysicsServer3D.BODY_MODE_KINEMATIC)
	if options.get("isolate", "") == "hitboxes":
		for robot in game.robots:
			for body: StaticBody3D in robot.find_children("*","StaticBody3D",true,false):
				body.collision_layer = 0
				body.top_level = true
	if options.has("planning-cache") and String(options["planning-cache"]) not in ["0","1"]:
		push_error("Planning-cache diagnostic expects 0 or 1")
		await app.request_quit()
		return
	game.map.traversal.planning_cache_enabled = String(options.get("planning-cache","1")) == "1"
	game.map.traversal.reuse_query_shapes = String(options.get("reuse-nav-shapes",str(int(game.map.traversal.reuse_query_shapes)))) == "1"
	if options.has("sample-at-sim"):
		var sample_time := float(options["sample-at-sim"])
		if not is_finite(sample_time) or sample_time <= game.elapsed:
			push_error("Simulation sample time must be later than completed warmup")
			await app.request_quit()
			return
		while game.phase == "Active" and game.elapsed < sample_time:
			await get_tree().physics_frame
		if game.phase != "Active":
			push_error("Match finished before simulation sample time")
			await app.request_quit()
			return
	var sample_start_simulation := game.elapsed
	var sample_start_rng := str(game.rng.state)
	var sample_start_robots: Array = []
	for robot: ArenaRobot in game.robots:
		sample_start_robots.append({"id":robot.robot_id,"head":robot.head,"team":robot.team,"position":[robot.position.x,robot.position.y,robot.position.z],"weapon":robot.equipped,"ah":robot.ah,"ep":robot.ep,"goal":robot.brain.goal_kind if robot.brain != null else "human"})
	if options.has("costs"):
		cost_ticks = 0
		tree_updates_by_physics_frame.clear()
		tree_updates_since_frame = 0
		tree_updates_discarded = 0
		tree_frame_samples.clear()
		for robot: ArenaRobot in game.robots:
			if robot.brain != null: robot.brain.behavior.updated.connect(record_tree_update)
		ArenaRobot.profile_stages = true
		ArenaRobot.stage_usec.clear()
		ArenaMap.profile_ticks = true
		ArenaMap.tick_costs.clear()
		SpatialAudioDirector.profile_ticks = true
		SpatialAudioDirector.tick_costs.clear()
		SpatialAudioDirector.profile_callbacks = 0
		SpatialAudioDirector.profile_acoustic_samples = 0
		TraversalGraph.profile_paths = true
		TraversalGraph.path_stats.clear()
		ArenaCombat.profile_queries = true
		ArenaCombat.query_stats.clear()
		Assets.profile_loads = true
		Assets.load_stats.clear()
	last_usec = 0
	if followed_bot:
		follow_previous = followed_bot.global_position
		follow_camera_previous = game.camera.global_position
		follow_shots_started = followed_bot.network_shots
	if not valid_display():
		await app.request_quit()
		return
	if String(options.get("abort-after-ready","0"))=="1":
		print("PROFILE_ABORT_AFTER_READY backend=",Preferences.active_renderer_label(app))
		await app.request_quit()
		print("PROFILE_ABORT_SHUTDOWN_COMPLETE")
		return
		var deadline := Time.get_ticks_usec()+90000000
		while Time.get_ticks_usec()<deadline:
			await get_tree().process_frame
			await app.request_quit();return
	measure_started_usec = Time.get_ticks_usec()
	if arena_stress: arena_stress.begin_sample()
	if options.has("alpha-isolation"): arena_stress.orbit_seconds=AlphaPassIsolation.PHASE_SECONDS
	occlusion_query_start = ArenaCombat.query_stats.duplicate()
	measuring = true
	if options.has("gpu-profile-markers"): print("PROFILE_SAMPLE_BEGIN ",String(options.get("name","baseline"))," uptime_s=",Time.get_ticks_usec()/1000000.0)
	if options.has("alpha-isolation"):
		alpha_isolation=AlphaPassIsolation.new()
		alpha_isolation.begin(measure_started_usec,String(options["alpha-isolation"]))
	if options.has("timeline"): record_timeline("measurement_start")
	if options.has("script-profile"): EngineDebugger.send_message("arena:profile_begin",[])
	await wait_wall_seconds(float(options.get("seconds",30)))
	var measurement_wall_seconds:float=(Time.get_ticks_usec()-measure_started_usec)/1000000.0
	measuring = false
	if alpha_isolation: alpha_isolation.finish(Time.get_ticks_usec())
	if options.has("gpu-profile-markers"): print("PROFILE_SAMPLE_END ",String(options.get("name","baseline")))
	if options.has("timeline"): record_timeline("measurement_end")
	if display_changed_during_sample or not valid_display():
		push_error("Invalid rendered sample: fullscreen display changed during measurement")
		await app.request_quit()
		return
	if options.has("occlusion-phases"): occlusion_phase_queries[occlusion_phase] = query_delta(occlusion_query_start)
	if options.has("script-profile"): EngineDebugger.send_message("arena:profile_end",[])
	if rows.size() < 60:
		push_error("Invalid rendered sample: fewer than 60 frames (%d in %.2f wall seconds)" % [rows.size(),measurement_wall_seconds])
		await app.request_quit()
		return
	if followed_bot and follow_moving_seconds < 3.0:
		push_error("Invalid moving-view capture: followed bot moved for fewer than three seconds")
		await app.request_quit()
		return
	var frames: Array = []
	var cpu: Array = []
	var physics: Array = []
	var gpu: Array = []
	var render_cpu: Array = []
	var total := 0.0
	var slow := 0
	var target_slow := 0
	var target_fps := float(options.get("target-fps",60))
	for row in rows:
		frames.append(row[0]); total += row[0]
		cpu.append(row[1]); physics.append(row[2]); gpu.append(row[3]); render_cpu.append(row[4])
		if row[0] > 1000.0/120.0: slow += 1
		if row[0] > 1000.0/target_fps: target_slow += 1
	var result := {"options":options,"release":OS.has_feature("release"),"resolution":str(root.get_texture().get_size()),"display":display_state(),"adapter":RenderingServer.get_video_adapter_name(),
		"cpu":OS.get_processor_name(),"difficulty":game.difficulty,"frames":rows.size(),"average_fps":frames.size()*1000.0/total,
		"quality_settings":{"quality":app.prefs.values.quality,"fixture_lighting":app.prefs.values.fixture_lighting,"shadows":app.prefs.values.shadows,"ambient_occlusion":app.prefs.values.ambient_occlusion,"bloom":app.prefs.values.bloom,"msaa_3d":int(root.msaa_3d),"sprint_blur":app.prefs.values.sprint_blur,"speed_lines":app.prefs.values.speed_lines,"reduced_motion":app.prefs.values.reduced_motion},
		"sample_seconds":total/1000.0,
		"frame_ms":summary(frames),"process_ms":summary(cpu),"physics_ms":summary(physics),
		"gpu_ms":summary(gpu),"render_cpu_ms":summary(render_cpu),"over_120_budget_percent":slow*100.0/frames.size(),
		"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"triangles":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
		"static_bodies":game.find_children("*","StaticBody3D",true,false).size(),
		"bone_attachments":game.find_children("*","BoneAttachment3D",true,false).size(),
		"kills":game.robots.reduce(func(sum,robot): return sum+robot.kills,0),"audio":game.audio.metrics.duplicate()}
	result["target_fps"] = target_fps
	result["measurement_wall_seconds"] = measurement_wall_seconds
	result["diagnostic_sdfgi_override"] = options.get("diagnostic-sdfgi",null)
	# Preserve each measured interval so isolated stalls can be located instead
	# of being hidden by an average or a periodically refreshed CPU monitor.
	result["frame_intervals_ms"] = frames
	result["decision_phases"] = ArenaBrain.decision_phases
	result["separate_render_thread"] = separate_render_thread
	result["gpu_timing_sampled"] = not options.has("frame-times-only")
	if options.has("frame-times-only"):
		result["gpu_ms"] = null
		result["render_cpu_ms"] = null
	result["planning_query_cache_enabled"] = game.map.traversal.planning_cache_enabled
	result["navigation_query_shape_reuse"] = game.map.traversal.reuse_query_shapes
	if options.has("simulation-checkpoints"): result["simulation_checkpoints"] = simulation_checkpoints.duplicate(true)
	result["simulation_sample"] = {"start":sample_start_simulation,"end":game.elapsed,"rng_state_start":sample_start_rng,"robots_start":sample_start_robots,"team_colors":game.team_colors.map(func(color): return color.to_html())}
	result.quality_settings["active_renderer"]=Preferences.active_renderer_label(app)
	result.quality_settings["scaling_3d_mode"]=int(root.scaling_3d_mode)
	result.quality_settings["scaling_3d_scale"]=root.scaling_3d_scale
	result["environments"]=[]
	result["fixture_light_state"]={"total":0,"illuminating":0,"shadow_casting":0}
	for light in game.find_children("*","Light3D",true,false):
		if not light.get_meta("fixture_light",false):continue
		result.fixture_light_state.total+=1
		if light.is_visible_in_tree() and light.light_cull_mask!=0 and light.light_energy>0:result.fixture_light_state.illuminating+=1
		if light.shadow_enabled:result.fixture_light_state.shadow_casting+=1
	for environment in app.find_children("*","WorldEnvironment",true,false):
		var env: Environment=environment.environment
		if env==null: continue
		result.environments.append({"node":String(environment.get_path()),
			"ambient_light_source":env.ambient_light_source,"sdfgi_enabled":env.sdfgi_enabled,"ssil_enabled":env.ssil_enabled,
			"reflected_light_source":env.reflected_light_source,"reflection_maps_disabled":env.has_meta("quality_reflection_maps")})
	if followed_bot:
		result["follow_bot"] = {"id":followed_bot.robot_id,"travelled_m":follow_distance,
			"camera_travelled_m":follow_camera_distance,"moving_seconds":follow_moving_seconds,
			"active_seconds":follow_active_seconds,"shots":followed_bot.network_shots-follow_shots_started}
	result["over_target_budget_percent"] = target_slow*100.0/frames.size()
	result["meets_target_every_frame"] = target_slow == 0
	result["scene_audit"] = scene_audit()
	if alpha_isolation: result["alpha_isolation"] = alpha_isolation.report()
	if options.has("material-audit"): result["material_audit"] = material_audit()
	if arena_stress:
		result["arena_stress"] = arena_stress.report()
		result["rendering_preparation"] = rendering_preparation
	if not draw_rows.is_empty(): result["draw_calls_distribution"] = summary(draw_rows)
	if not occlusion_report.is_empty(): result["occlusion_diagnostic"] = occlusion_report
	if options.has("occlusion-phases"): result["occlusion_phases"] = occlusion_phase_results()
	if options.has("costs"): result["navigation_paths"] = TraversalGraph.path_stats.duplicate()
	if options.has("costs"): result["collision_queries"] = ArenaCombat.query_stats.duplicate()
	if options.has("costs"):
		result["asset_loads"] = Assets.load_stats.duplicate(true)
		Assets.profile_loads = false
	if options.has("costs"):
		ArenaRobot.profile_stages = false
		ArenaMap.profile_ticks = false
		SpatialAudioDirector.profile_ticks = false
		result["audio_stages_us_per_tick"] = {}
		for key in SpatialAudioDirector.tick_costs:
			result.audio_stages_us_per_tick[key] = SpatialAudioDirector.tick_costs[key]/maxf(1,cost_ticks)
		result["audio_profile_calls"] = {"physics_callbacks":SpatialAudioDirector.profile_callbacks,"acoustic_samples":SpatialAudioDirector.profile_acoustic_samples}
		var updates := tree_updates_by_physics_frame.values()
		var grouped_updates := 0
		result["frame_cost_by_tree_updates"] = {}
		for count in tree_frame_samples:
			var samples: Array = tree_frame_samples[count]
			grouped_updates += int(count)*samples.size()
			result.frame_cost_by_tree_updates[str(count)] = {"frames":samples.size(),"frame_ms":summary(samples)}
		var recorded_updates: int = updates.reduce(func(total, count): return total + count, 0)
		result["tree_frame_accounting"] = {"recorded_updates":recorded_updates,"grouped_updates":grouped_updates,"discarded_first_frame":tree_updates_discarded,"unmeasured_tail":tree_updates_since_frame,"consistent":recorded_updates==grouped_updates+tree_updates_discarded+tree_updates_since_frame}
		result["behavior_tree_updates"] = {
			"physics_ticks": cost_ticks,
			"ticks_with_updates": updates.size(),
			"calls": updates.reduce(func(total, count): return total + count, 0),
			"updates_per_active_tick": summary(updates) if not updates.is_empty() else {}}
		result["map_stages_us_per_tick"] = {}
		for key in ArenaMap.tick_costs:
			result.map_stages_us_per_tick[key] = ArenaMap.tick_costs[key]/maxf(1,cost_ticks)
		result["robot_stages_us_per_tick"] = {}
		for key in ArenaRobot.stage_usec:
			result.robot_stages_us_per_tick[key] = ArenaRobot.stage_usec[key]/maxf(1,cost_ticks)
		result["cost_instrumentation"] = "inline_timers_v2"
	if stress_active:
		result["weapons"] = shot_counts
		result["stream_samples"] = stream_samples
		result["contact_samples"] = contact_samples
		result["damage_samples"] = damage_samples
		result["repair_samples"] = repair_samples
		result["world_event"] = world_event_requested and game.map.event_done
	var directory := report_directory()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(directory))
	var name: String = options.get("name","baseline")
	if int(options.get("matches",1)) > 1: name += "-match%d" % match_pass
	FileAccess.open(directory+"/"+name+".json",FileAccess.WRITE).store_string(JSON.stringify(result,"  "))
	print("FRAME_PROFILE ",JSON.stringify(result))
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(directory+"/"+name+".png")
	stress_active = false
	arena_stress = null
	if match_pass < int(options.get("matches",1)):
		followed_bot=null
		await app.leave_match()
		game=null
		await get_tree().create_timer(2.0).timeout
		if options.has("timeline"): record_timeline("returned_to_menu")
		run.call_deferred()
		return
	await app.request_quit()
	retained_brains.clear()

func start_stress() -> bool:
	var weapons: Array = Arsenal.WEAPONS.keys()
	# Search live walkable nodes instead of assuming the former ground at y=0.
	# Ten shooters need five clear, supported lanes on one authored deck.
	var positions := stress_positions()
	if positions.size() < game.robots.size():
		push_error("No supported combat lanes for this map/roster")
		get_tree().quit(1)
		return false
	game.map.abort_all_repairs("profile_setup")
	for index in game.robots.size():
		var robot: ArenaRobot = game.robots[index]
		retained_brains.append(robot.brain)
		robot.brain = null
		robot.human = false
		game.spawn_robot(robot)
		if not robot.alive:
			push_error("Cannot reset stress robot through a safe spawn")
			get_tree().quit(1)
			return false
		robot.show()
		robot.ah = 10000
		robot.protection = 0
		robot.spawn_remaining = 0
		robot.global_position = positions[index]
		robot.last_safe = robot.global_position
		var weapon: String = weapons[index%weapons.size()]
		# Warmup AI may have filled inventory or queued a delayed switch.
		# Neither may replace an assigned stress weapon after setup.
		robot.reset_inventory()
		robot.pickup_weapon = weapon if weapon!="pistol" else ""
		robot.equip(weapon)
		robot.loaded = 1000
		robot.packs = 1000
		stress_weapons.append(weapon)
		shot_counts[weapon] = 0
		shot_baselines[robot.robot_id] = robot.network_shots
	game.third_person = true
	game.camera_snap = false # Normal respawn requested a gameplay snap; keep the stress view.
	game.camera_rig.host.set_process(false)
	game.first_person.set_process(false)
	game.first_person.hide()
	# Stay below stacked ceilings rather than viewing combat through a roof.
	for offset in [Vector3(12,2.5,13),Vector3(-12,2.5,13),Vector3(12,2.5,-13),Vector3(-12,2.5,-13)]:
		game.camera.global_position=stress_center+offset
		if game.combat.clear(game.camera.global_position,stress_center+Vector3.UP): break
	game.camera.look_at(stress_center + Vector3.UP)
	stress_camera_position = game.camera.global_position
	stress_active = true
	return true

func stress_positions() -> Array[Vector3]:
	var columns := int(ceil(game.robots.size()/2.0))
	for point_id in game.map.traversal.graph.get_point_ids():
		var center: Vector3 = game.map.traversal.graph.get_point_position(point_id)
		var points: Array[Vector3] = []
		for index in game.robots.size():
			var desired: Vector3 = center + Vector3((index%columns-(columns-1)*0.5)*2.0,0.3,-3.5 if index<columns else 3.5)
			var hit := SurfacePlacement.below(game.get_world_3d(),desired,game.map.config.fall_boundary)
			if hit.is_empty() or absf(hit.position.y-center.y)>0.4: break
			var point: Vector3 = hit.position+Vector3.UP*0.02
			if not game.map.traversal.standing_clear(point): break
			points.append(point)
		if points.size()!=game.robots.size(): continue
		var clear_lanes := true
		for index in columns:
			if index+columns>=points.size(): continue
			if not game.combat.clear(points[index]+Vector3.UP,points[index+columns]+Vector3.UP):
				clear_lanes=false
		if clear_lanes:
			stress_center=center
			return points
	return []

func material_audit() -> Dictionary:
	# One-shot resource inspection after measurement. Scene visibility does not
	# establish frustum visibility or GPU pass membership; these are candidates
	# for further rendered isolation, not attributed draw-call timings.
	var materials := {}
	for node: MeshInstance3D in game.find_children("*","MeshInstance3D",true,false):
		if node.mesh == null or not node.is_visible_in_tree(): continue
		for surface in node.mesh.get_surface_count():
			var passes: Array[Material] = [node.get_active_material(surface),node.material_overlay]
			var visited := {}
			while not passes.is_empty():
				var material: Material = passes.pop_back()
				if material == null or visited.has(material.get_instance_id()): continue
				visited[material.get_instance_id()] = true
				if material.next_pass != null: passes.append(material.next_pass)
				var key := material.resource_path
				if key.is_empty(): key = "%s:%s:%d" % [material.get_class(),material.resource_name,material.get_instance_id()]
				if not materials.has(key):
					var row := {"class":material.get_class(),"name":material.resource_name,"surface_uses":0,"example_nodes":[]}
					if material is BaseMaterial3D:
						row["transparency"] = material.transparency
						row["blend_mode"] = material.blend_mode
					if material is ShaderMaterial and material.shader != null:
						row["shader"] = material.shader.resource_path
						row["shader_mentions_alpha"] = material.shader.code.contains("ALPHA")
					materials[key] = row
				materials[key].surface_uses += 1
				if materials[key].example_nodes.size() < 3:
					materials[key].example_nodes.append(String(node.get_path()))
	return {"scope":"scene-visible surface material references, including overlays and next passes; not GPU timings","materials":materials}

func scene_audit() -> Dictionary:
	var meshes := {}
	for node: MeshInstance3D in game.find_children("*","MeshInstance3D",true,false):
		if node.mesh == null: continue
		var path: String = node.mesh.get_meta("source_mesh_path",node.mesh.resource_path)
		if path.is_empty(): path="runtime"
		if not meshes.has(path): meshes[path]={"instances":0,"surfaces":0,"visible_instances":0,"visible_surfaces":0}
		meshes[path].instances+=1
		meshes[path].surfaces+=node.mesh.get_surface_count()
		# Scene visibility only, not a claim about frustum/occlusion/shadow draws.
		if node.is_visible_in_tree():
			meshes[path].visible_instances+=1
			meshes[path].visible_surfaces+=node.mesh.get_surface_count()
	var lights := {}
	for node: Light3D in game.find_children("*","Light3D",true,false):
		var key := String(node.name)
		if not lights.has(key): lights[key]={"count":0,"shadows":0,"illuminating":0}
		lights[key].count+=1
		if node.shadow_enabled: lights[key].shadows+=1
		if node.is_visible_in_tree() and node.light_cull_mask != 0 and node.light_energy > 0:
			lights[key].illuminating+=1
	return {"meshes":meshes,"lights":lights}

func _physics_process(dt: float) -> void:
	# Abort paths also wait for asynchronous application shutdown. The match
	# can be freed during that wait while the orbit helper is still retained.
	if not is_instance_valid(game) or (is_instance_valid(app) and app.closing): return
	if arena_stress: arena_stress.tick(dt)
	if options.has("simulation-checkpoints") and is_instance_valid(game) and game.phase == "Active" and game.elapsed >= next_simulation_checkpoint:
		record_simulation_checkpoint()
		next_simulation_checkpoint += 1.0
	if measuring and followed_bot:
		var distance := followed_bot.global_position.distance_to(follow_previous)
		if followed_bot.can_act():
			follow_active_seconds += dt
			if distance > 0.002 and distance < 2.0:
				follow_distance += distance
				follow_moving_seconds += dt
		follow_previous = followed_bot.global_position
	if stress_active:
		if game.camera.global_position.distance_squared_to(stress_camera_position) > 0.01:
			push_error("Invalid stress coverage: camera moved away from combat")
			get_tree().quit(1)
			return
		stress_clock += dt
		for weapon in shot_counts: shot_counts[weapon] = 0
		for index in game.robots.size():
			var robot: ArenaRobot = game.robots[index]
			if not robot.alive or not robot.is_visible_in_tree():
				push_error("Invalid stress coverage: robot %d is dead or hidden" % robot.robot_id)
				get_tree().quit(1)
				return
			if robot.equipped != stress_weapons[index]:
				push_error("Invalid stress coverage: robot %d switched from %s to %s" % [robot.robot_id,stress_weapons[index],robot.equipped])
				get_tree().quit(1)
				return
			if measuring and robot.ah < 9999.0: damage_samples += 1
			if measuring and robot.streaming: stream_samples[robot.equipped] = stream_samples.get(robot.equipped,0)+1
			if measuring and robot.network_contact != Vector3.INF: contact_samples[robot.equipped] = contact_samples.get(robot.equipped,0)+1
			robot.ah = 10000
			robot.ep = 100
			robot.sh = 1000 if int(stress_clock/4)%2 == 1 else 0
			robot.shield_time = 100
			robot.loaded = 1000
			robot.packs = 1000
			robot.move_input = Vector2.ZERO
			robot.knockback_velocity = Vector3.ZERO
			var columns := int(ceil(game.robots.size()/2.0))
			var target_index := index+columns if index<columns else index-columns
			var target := game.robots[target_index%game.robots.size()] as ArenaRobot
			var direction := (target.eye()-robot.eye()).normalized()
			robot.yaw = atan2(-direction.x,-direction.z)
			robot.pitch = asin(clampf(direction.y,-1,1))
			robot.bot_aim = direction
			robot.wants_fire = true
			robot.wants_secondary = int(stress_clock/3)%2 == 1
			shot_counts[robot.equipped] += robot.network_shots-int(shot_baselines[robot.robot_id])
		if options.has("world"):
			stress_world()

	if measuring and options.has("costs"):
		cost_ticks += 1

func stress_world() -> void:
	var patient: ArenaRobot = game.robots.back()
	if measuring and patient.repair != null: repair_samples += 1
	if measuring and stress_clock >= 10 and not repair_started:
		if not repair_pending:
			var stations: Array = game.map.fixtures.filter(func(f): return f.kind == "repair_station")
			stations.sort_custom(func(a,b): return a.point.distance_squared_to(game.camera.global_position) < b.point.distance_squared_to(game.camera.global_position))
			repair_fixture = stations[0]
			repair_fixture.cooldown = 0
			repair_pending = true
		if patient.repair != null:
			repair_started = true
		else:
			patient.ah = 50
			patient.velocity = Vector3.ZERO
			patient.wants_fire = false
			patient.wants_secondary = false
			patient.global_position = Assets.socket(repair_fixture.node,"PlayerMount").global_position
			patient.last_safe = patient.global_position
	if measuring and stress_clock >= 20 and not world_event_requested and game.map.config.event.get("type","") != "none":
		# Exercise the real scheduled cover event during this short capture.
		game.elapsed = maxf(game.elapsed,float(game.map.config.event.time))
		world_event_requested = true

func summary(values: Array) -> Dictionary:
	var ordered := values.duplicate()
	ordered.sort()
	return {"p50":ordered[int(ordered.size()*.5)],"p95":ordered[mini(ordered.size()-1,int(ordered.size()*.95))],
		"p99":ordered[mini(ordered.size()-1,int(ordered.size()*.99))],"max":ordered.back()}

func query_delta(before: Dictionary) -> Dictionary:
	var delta := {}
	for key: String in ArenaCombat.query_stats:
		if key.ends_with("_max_us"): continue
		delta[key] = int(ArenaCombat.query_stats[key])-int(before.get(key,0))
	return delta

func occlusion_phase_results() -> Array:
	var results: Array = []
	for phase in 3:
		var frames: Array = []
		var gpu: Array = []
		var render_cpu: Array = []
		var total := 0.0
		for row in occlusion_phase_rows[phase]:
			frames.append(row[0]); gpu.append(row[3]); render_cpu.append(row[4])
			total += row[0]
		if frames.is_empty(): continue
		results.append({"phase":phase,"occlusion_enabled":phase==1,"frames":frames.size(),"sample_seconds":total/1000.0,
			"average_fps":frames.size()*1000.0/total,"frame_ms":summary(frames),"gpu_ms":summary(gpu),
			"render_cpu_ms":summary(render_cpu),"collision_queries":occlusion_phase_queries[phase]})
	return results

func _process(_dt: float) -> void:
	if not is_instance_valid(game) or (is_instance_valid(app) and app.closing): return
	if followed_bot:
		followed_bot.pitch = asin(clampf(followed_bot.bot_aim.y,-1,1))
		followed_bot.listener.position.y = 1.08 if followed_bot.crouched else followed_bot.character.eye_height
		followed_bot.listener.basis = Basis(Vector3.UP,followed_bot.yaw)*Basis(Vector3.RIGHT,followed_bot.pitch)
		if measuring:
			var distance := game.camera.global_position.distance_to(follow_camera_previous)
			if distance < 2.0: follow_camera_distance += distance
			follow_camera_previous = game.camera.global_position
	if measuring:
		var now := Time.get_ticks_usec()
		if alpha_isolation: alpha_isolation.tick(now)
		if last_usec == 0:
			last_usec = now
			if options.has("costs"):
				tree_updates_discarded += tree_updates_since_frame
				tree_updates_since_frame = 0
			return
		var rid := root.get_viewport_rid()
		if options.has("stall-window-state") and now-last_usec>70000:
			print("PROFILE_STALL_WINDOW ",JSON.stringify({"interval_ms":float(now-last_usec)/1000.0,"uptime_s":float(now)/1000000.0,"display":display_state()}))
		var gpu_ms := 0.0
		var render_cpu_ms := 0.0
		if not options.has("frame-times-only"):
			gpu_ms = RenderingServer.viewport_get_measured_render_time_gpu(rid)
			render_cpu_ms = RenderingServer.viewport_get_measured_render_time_cpu(rid)+RenderingServer.get_frame_setup_time_cpu()
		rows.append([(now-last_usec)/1000.0,Performance.get_monitor(Performance.TIME_PROCESS)*1000.0,
			Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0,
			gpu_ms,render_cpu_ms])
		if alpha_isolation: alpha_isolation.record_frame()
		if options.has("costs"):
			if not tree_frame_samples.has(tree_updates_since_frame): tree_frame_samples[tree_updates_since_frame] = []
			tree_frame_samples[tree_updates_since_frame].append(rows.back()[0])
			tree_updates_since_frame = 0
		if options.has("timeline"):
			timeline_frames.append(rows.back()[0])
			timeline_clock += rows.back()[0]/1000.0
			if timeline_clock >= 5.0:
				timeline_clock=0
				record_timeline("sample")
		if options.has("draw-stats"): draw_rows.append(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		if options.has("occlusion-phases"):
			var elapsed := (now-measure_started_usec)/1000000.0
			var period := float(options.get("seconds",72))/3.0
			var phase := mini(2,int(elapsed/period))
			if phase != occlusion_phase:
				occlusion_phase_queries[occlusion_phase] = query_delta(occlusion_query_start)
				occlusion_query_start = ArenaCombat.query_stats.duplicate()
				occlusion_phase = phase
				root.use_occlusion_culling = phase==1
			if fmod(elapsed,period)>=2.0: occlusion_phase_rows[phase].append(rows.back())
		last_usec = now
