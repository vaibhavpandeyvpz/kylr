extends Node

var app
var config: Dictionary
var rows: Array = []
var sampling := false
var ticks := 0
var previous_usec := 0
var batch_results: Array = []

func _ready() -> void:
	config = JSON.parse_string(FileAccess.get_file_as_string("user://mobile-profile.json"))
	run.call_deferred()

func run() -> void:
	var base := config.duplicate(true)
	var cases: Array = base.get("cases",[base])
	for entry in cases:
		config = base.duplicate(true)
		config.erase("cases")
		config.merge(entry,true)
		rows = []
		ticks = 0
		await run_case()
		FileAccess.open("user://mobile-profile-batch.json",FileAccess.WRITE).store_string(JSON.stringify(batch_results))
		if entry != cases.back(): await app.leave_match()
	print("MOBILE_BATCH_DONE cases=",batch_results.size())

func run_case() -> void:
	seed(int(config.get("seed",120)))
	app.set_meta("profile_roster_seed",int(config.get("seed",120)))
	app.prefs.values.map = config.get("map","skyfall")
	app.prefs.values.name = "MobileBenchmark"
	app.prefs.values.count = int(config.get("robots",10))
	app.prefs.values.type = MatchTypes.ALL.find(config.get("mode","DM"))
	var quality := int(config.get("quality",2))
	app.prefs.values.quality = quality
	app.prefs.values.quality_benchmarked = true
	for key in Preferences.QUALITY_PRESETS[quality]: app.prefs.values[key] = Preferences.QUALITY_PRESETS[quality][key]
	await app.start_match()
	while app.match_node.phase != "Active": await get_tree().process_frame
	var warm_until := Time.get_ticks_msec()+int(float(config.get("warmup",15))*1000.0)
	while Time.get_ticks_msec()<warm_until: await get_tree().process_frame
	var costs := bool(config.get("costs",false))
	ArenaRobot.profile_stages = costs
	ArenaRobot.stage_usec.clear()
	ArenaBrain.profile_decisions = costs
	ArenaBrain.decision_usec = 0
	ArenaMap.profile_ticks = costs
	ArenaMap.tick_costs.clear()
	SpatialAudioDirector.profile_ticks = costs
	SpatialAudioDirector.tick_costs.clear()
	PropMotion.profile_ticks = costs
	PropMotion.tick_usec = 0
	var render_loop := bool(config.get("render_loop",true))
	var previous_limit := Engine.max_fps
	if not render_loop: Engine.max_fps=60
	RenderingServer.set_render_loop_enabled(render_loop)
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), costs and render_loop)
	previous_usec = Time.get_ticks_usec()
	var started := previous_usec
	sampling = true
	var sample_until := Time.get_ticks_msec()+int(float(config.get("seconds",30))*1000.0)
	while Time.get_ticks_msec()<sample_until: await get_tree().process_frame
	sampling = false
	var elapsed := (Time.get_ticks_usec()-started)/1000000.0
	var frames: Array = []
	var window_ms:=0.0
	var window_frames:=0
	var min_window_fps:=INF
	for row in rows:
		window_ms+=row[0]
		window_frames+=1
		if window_ms>=1000.0:
			min_window_fps=minf(min_window_fps,window_frames*1000.0/window_ms)
			window_ms=0
			window_frames=0
	for row in rows: frames.append(row[0])
	frames.sort()
	var result := {"config":config,"logical_resolution":str(get_viewport().get_visible_rect().size),"resolution":str(get_viewport().get_texture().get_size()),"renderer":RenderingServer.get_current_rendering_method(),"adapter":RenderingServer.get_video_adapter_name(),"quality":app.prefs.values.duplicate(true),"rows":rows,"seconds":elapsed,"fps":rows.size()/elapsed,"physics_ticks":ticks,"frame_ms":{},"robot_us_per_tick":{},"decision_us_per_tick":ArenaBrain.decision_usec/maxf(1,ticks)}
	if not frames.is_empty():
		for percentile in [50,95,99,100]: result.frame_ms[str(percentile)]=frames[mini(frames.size()-1,int(ceil(frames.size()*percentile/100.0))-1)]
	for key in ArenaRobot.stage_usec: result.robot_us_per_tick[key]=ArenaRobot.stage_usec[key]/maxf(1,ticks)
	result["map_us_per_tick"]={}
	for key in ArenaMap.tick_costs: result.map_us_per_tick[key]=ArenaMap.tick_costs[key]/maxf(1,ticks)
	result["audio_us_per_frame"]={}
	for key in SpatialAudioDirector.tick_costs: result.audio_us_per_frame[key]=SpatialAudioDirector.tick_costs[key]/maxf(1,rows.size())
	result["prop_motion_us_per_tick"]=PropMotion.tick_usec/maxf(1,ticks)
	result["fixed_mesh_batches"]=app.match_node.map.get_meta("fixed_mesh_batches",{})
	result["min_1s_window_fps"]=min_window_fps if is_finite(min_window_fps) else 0.0
	result["passes_30fps"]=render_loop and not costs and result.min_1s_window_fps>=30.0
	result["render_scale"]=get_viewport().scaling_3d_scale
	var output: Vector2i=app.prefs.update_display_frame(get_window())
	result["effective_display_resolution"]=str(output)
	result["rendered_3d_resolution"]=str(Vector2i(Vector2(output)*get_viewport().scaling_3d_scale))
	result["nodes"]=Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	result["physics_active_objects"]=Performance.get_monitor(Performance.PHYSICS_3D_ACTIVE_OBJECTS)
	result["physics_collision_pairs"]=Performance.get_monitor(Performance.PHYSICS_3D_COLLISION_PAIRS)
	result["lod_metadata_missing"]=MeshLods.missing
	RenderingServer.set_render_loop_enabled(true)
	Engine.max_fps=previous_limit
	ArenaMap.profile_ticks = false
	SpatialAudioDirector.profile_ticks = false
	PropMotion.profile_ticks = false
	ArenaRobot.profile_stages = false
	ArenaBrain.profile_decisions = false
	FileAccess.open("user://mobile-profile-result.json",FileAccess.WRITE).store_string(JSON.stringify(result))
	batch_results.append(result)
	print("MOBILE_BENCHMARK_DONE fps=",result.fps," frames=",rows.size()," frame_ms=",result.frame_ms," robot_costs=",result.robot_us_per_tick)

func _physics_process(_delta: float) -> void:
	if sampling: ticks += 1

func _process(_delta: float) -> void:
	if not sampling: return
	var now := Time.get_ticks_usec()
	var rid := get_viewport().get_viewport_rid()
	var costs := bool(config.get("costs",false)) and bool(config.get("render_loop",true))
	rows.append([(now-previous_usec)/1000.0,Performance.get_monitor(Performance.TIME_PROCESS)*1000.0,Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0,RenderingServer.viewport_get_measured_render_time_gpu(rid) if costs else -1,RenderingServer.viewport_get_measured_render_time_cpu(rid) if costs else -1,Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])
	previous_usec = now
