extends SceneTree
## Rendered menu/match readiness and repeat-load coverage, with isolated settings.
var output := "res://reports/performance/loading-lifecycle"
var app
var denoiser:="dlss"
var backend_checks:Array[Dictionary]=[]

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	create_timer(240).timeout.connect(func(): push_error("LOADING_LIFECYCLE_TIMEOUT");quit(2))
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--report-dir="): output=argument.trim_prefix("--report-dir=")
		if argument.begins_with("--denoiser="): denoiser=argument.trim_prefix("--denoiser=")
	if denoiser!="dlss":push_error("Unknown denoiser");quit(3);return
	var requested:=Preferences.DENOISER_DLSS
	if Preferences.resolve_rt_denoiser(requested,Preferences.rt_denoiser_capabilities())!=requested:
		push_error("Requested qualification backend is unavailable");quit(3);return
	DirAccess.make_dir_recursive_absolute(output)
	seed(120)
	var preferences := Preferences.new(output+"/preferences.cfg")
	preferences.values.quality=3
	preferences.values.quality_benchmarked=true
	preferences.values.resolution=Vector2i(1920,1080)
	preferences.values.display_mode=1
	preferences.values.count=10
	preferences.values.type=0
	for key in Preferences.QUALITY_PRESETS[3]: preferences.values[key]=Preferences.QUALITY_PRESETS[3][key]
	preferences.values.rt_denoiser=requested
	preferences.values.rt_upscaling=denoiser=="dlss"
	if preferences.save()!=OK: push_error("Cannot save isolated loading preferences");quit(3);return
	app=load("res://app.tscn").instantiate()
	app.set_meta("preferences_path",output+"/preferences.cfg")
	app.set_meta("automated_profile",true)
	root.add_child(app)
	await process_frame
	await snap("spinner")
	if not app.startup_complete: await app.startup_finished
	if not verify_backend("menu"):return
	await snap("menu")
	for map_id in ["skyfall","faceoff","skyfall"]:
		app.prefs.values.map=map_id
		await app.start_match()
		if not is_instance_valid(app.match_node): push_error("Match failed to load");quit(4);return
		if not verify_backend(map_id):return
		print("LOADING_MATCH_READY map=",map_id," cached_navigation=",app.match_node.map.navigation_cache_hit)
		await create_timer(1.0).timeout
		await snap(map_id+"-"+str(app.loading_reports.size()))
		if app.loading_reports.size()==2:
			for frame in 60:await RenderingServer.frame_post_draw
			await snap("skyfall-settled")
		await app.leave_match()
		await snap("menu-return-"+map_id+"-"+str(app.loading_reports.size()))
	var report := {"engine":Engine.get_version_info(),"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"denoiser":denoiser,"backend_checks":backend_checks,"loading":app.loading_reports,"complete":true}
	var file := FileAccess.open(output+"/report.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"\t"))
	file.close()
	print("LOADING_LIFECYCLE_PASS ",JSON.stringify(report))
	await app.request_quit()

func verify_backend(label: String) -> bool:
	var expected:=1
	var worlds:=0
	for world in app.find_children("*","WorldEnvironment",true,false):
		if world.environment==null:continue
		if not world.environment.get("pathtracing_enabled") or world.environment.get("pathtracing_denoiser")!=expected:
			push_error("Wrong backend at "+label);quit(4);return false
		worlds+=1
	var viewport:Viewport=app.get_viewport()
	var native:=false
	var expected_aa:=Viewport.SCREEN_SPACE_AA_SMAA if native else Viewport.SCREEN_SPACE_AA_DISABLED
	if worlds==0 or viewport.scaling_3d_mode!=(Viewport.SCALING_3D_MODE_BILINEAR if native else Viewport.SCALING_3D_MODE_DLSS) or not is_equal_approx(viewport.scaling_3d_scale,1.0 if native else .5):
		push_error("Wrong viewport configuration at "+label);quit(4);return false
	if viewport.screen_space_aa!=expected_aa or viewport.use_taa or viewport.msaa_3d!=Viewport.MSAA_DISABLED:
		push_error("Wrong RT antialiasing at "+label);quit(4);return false
	backend_checks.append({"stage":label,"environments":worlds,"denoiser":expected,"scale":viewport.scaling_3d_scale,"upscaler":viewport.scaling_3d_mode,"screen_space_aa":viewport.screen_space_aa,"taa":viewport.use_taa,"msaa":viewport.msaa_3d})
	return true

func snap(name: String) -> void:
	if DisplayServer.get_name()=="headless": return
	# A separate render worker may still be presenting the previous frame.
	for frame in 3: await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if image.get_size()!=Vector2i(1920,1080):
		push_error("Lifecycle output must be 1920x1080, got "+str(image.get_size()));quit(5);return
	image.save_png(output+"/"+name+".png")
