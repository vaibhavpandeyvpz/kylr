extends SceneTree
## Real boot/menu/map transitions. Captures are visual QA, never FPS samples.
const Observer = preload("res://scripts/debug/reconstruction_observer.gd")
var output := ""
var app
var rows: Array = []
var observer
var current_world: WorldEnvironment
var thread_mode := "safe"
var observer_attachment_frames := 0
var maps: Array[String] = ["faceoff", "skyfall"]
var loading_hold_observations := {}
var loading_hold_robot_ids := {}
var preparation_error := ""

func check_preparation_hold():
	if app == null or not is_instance_valid(app.match_node) or not app.match_node.loading_hold or not preparation_error.is_empty(): return
	var game: ArenaMatch = app.match_node
	for robot in game.robots:
		if not robot.alive or robot.spawn_fixture.is_empty(): continue
		var expected: float = robot.spawn_fixture.get("duration",104.0/30.0)
		if robot.spawn_started or not is_equal_approx(robot.spawn_remaining,expected):
			preparation_error="Robot spawn advanced while scene preparation was held"
			fail(preparation_error)
			return
		loading_hold_observations[game.map_id]=int(loading_hold_observations.get(game.map_id,0))+1
		if not loading_hold_robot_ids.has(game.map_id): loading_hold_robot_ids[game.map_id]={}
		loading_hold_robot_ids[game.map_id][str(robot.robot_id)]=true

func _initialize(): run.call_deferred()

func fail(message: String):
	push_error(message)
	quit(2)

func write_report(passed: bool):
	FileAccess.open(output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify({
		"passed": passed, "boot_scene_exercised": true, "preferences_isolated_before_ready": true,
		"engine_sha256": FileAccess.get_sha256(OS.get_executable_path()), "render_thread": thread_mode,
		"roster_seed": 120,
		"loading_hold_robot_observations": loading_hold_observations,
		"loading_hold_robot_ids": loading_hold_robot_ids,
		"preparation_error": preparation_error,
		"first_capture_timing": "After loading and read-only compositor attachment; not the exact first presented frame",
		"rows": rows, "visual_quality_accepted": false, "performance_accepted": false}, "\t"))

func retire_observer():
	if observer:
		observer.release()
		for frame in 4: await process_frame
		if not observer.stats().released: fail("Startup observer did not retire")
		if is_instance_valid(current_world): current_world.compositor = null
		observer = null
		current_world = null

func observe_world() -> bool:
	var worlds: Array = app.find_children("*", "WorldEnvironment", true, false)
	if worlds.size() != 1: fail("Expected one active world after loading"); return false
	current_world = worlds[0]
	if not current_world.environment.get("pathtracing_enabled") or current_world.environment.get("pathtracing_denoiser") != 1:
		fail("Actual startup environment is not DLSS Ray Reconstruction"); return false
	if current_world.compositor != null: fail("Startup fixture must not replace an existing compositor"); return false
	observer = Observer.new()
	var compositor := Compositor.new()
	compositor.compositor_effects = [observer]
	current_world.compositor = compositor
	# Separate rendering applies a newly attached compositor asynchronously. Wait
	# for its first actual callback, not an arbitrary delay or a backend fallback.
	observer_attachment_frames = 0
	while observer.stats().frames == 0 and observer_attachment_frames < 8:
		await RenderingServer.frame_post_draw
		observer_attachment_frames += 1
	if observer.stats().frames == 0:
		fail("Read-only startup observer did not receive renderer telemetry"); return false
	return true

func capture(label: String) -> bool:
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if image.get_size() != Vector2i(1920, 1080): fail("Startup capture is not 1080p"); return false
	if image.save_png(output.path_join(label + ".png")) != OK: fail("Cannot save startup image"); return false
	var state: Dictionary = observer.stats()
	var adapter: Dictionary = state.get("adapter", {})
	if not String(state.get("error", "")).is_empty() or adapter.get("backend") != "DLSS" or not adapter.get("viewport_renderer", false) or adapter.get("denoiser") != "Ray Reconstruction" or not adapter.get("evaluation_succeeded", false) or int(adapter.get("frames", 0)) <= 0:
		var failure := FileAccess.open(output.path_join(label + "-observer-failure.json"), FileAccess.WRITE)
		if failure != null: failure.store_string(JSON.stringify(state, "\t"))
		fail("Startup image lacks successful DLSS Ray Reconstruction activity"); return false
	if app.loading_screen.canvas.visible: fail("Loading cover remained visible after preparation"); return false
	if label.ends_with("-settled") and not rows.is_empty() and int(adapter.frames) <= int(rows[-1].denoiser.adapter.frames):
		fail("DLSS Ray Reconstruction stopped processing during the settling interval"); return false
	var row := {"label": label, "denoiser": state, "size": [image.get_width(), image.get_height()],
		"observer_attachment_render_frames": observer_attachment_frames,
		"loading_reports": app.loading_reports.duplicate(true), "phase": app.match_node.phase if app.match_node else "menu",
		"match_elapsed": app.match_node.elapsed if app.match_node else 0.0,
		"countdown": app.match_node.countdown if app.match_node else 0.0}
	if app.match_node and is_instance_valid(app.match_node.local_robot):
		var robot: ArenaRobot=app.match_node.local_robot
		row["local_spawn"]={"visible":robot.visible,"started":robot.spawn_started,"remaining":robot.spawn_remaining}
	rows.append(row)
	write_report(false)
	print("RENDERER_STARTUP_CAPTURE ", label)
	return true

func run():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		if argument.begins_with("--thread="): thread_mode = argument.trim_prefix("--thread=")
	if output.is_empty() or DisplayServer.get_name() == "headless" or OS.get_environment("GODOT_DLSS_DIAGNOSTICS") != "1": fail("Startup probe requires graphical DLSS Ray Reconstruction diagnostics"); return
	if FileAccess.file_exists(output.path_join("report.json")): fail("Use fresh startup output"); return
	DirAccess.make_dir_recursive_absolute(output)
	create_timer(300).timeout.connect(func(): fail("Renderer startup probe timed out"))
	AudioServer.set_bus_mute(0, true)
	var config := ConfigFile.new()
	var values := Preferences.DEFAULTS.duplicate(true)
	for key in Preferences.QUALITY_PRESETS[3]: values[key] = Preferences.QUALITY_PRESETS[3][key]
	values.quality = 3
	values.quality_benchmarked = true
	values.rt_denoiser = Preferences.DENOISER_DLSS
	values.resolution = Vector2i(1920, 1080)
	values.display_mode = 1
	values.separate_rendering_thread = thread_mode == "separate"
	values.name = "StartupProbe"
	values.count = 10
	values.type = 0
	values.goal = 999
	values.tutorial_hints = false
	for key in values: config.set_value("preferences", key, values[key])
	var preferences_path := output.path_join("preferences.cfg")
	if config.save(preferences_path) != OK: fail("Cannot save isolated startup preferences"); return
	var boot: Node = load("res://main.tscn").instantiate()
	boot.set_meta("preferences_path", preferences_path)
	boot.set_meta("automated_profile", true)
	root.add_child(boot)
	while current_scene == null or not current_scene.get("startup_complete"): await process_frame
	app = current_scene
	process_frame.connect(check_preparation_hold)
	if app.prefs.storage_path != preferences_path: fail("Startup consumed real user preferences"); return
	app.set_meta("profile_roster_seed", 120)
	if not await observe_world(): return
	if not await capture("menu-first"): return
	for frame in 60: await RenderingServer.frame_post_draw
	if not await capture("menu-settled"): return
	for map_id in maps:
		await retire_observer()
		app.prefs.values.map = map_id
		await app.start_match()
		if not preparation_error.is_empty(): return
		if loading_hold_robot_ids.get(map_id,{}).size() != 10:
			fail("Startup did not observe the complete roster during preparation"); return
		if app.match_node.phase != "Countdown" or app.match_node.elapsed != 0.0 or app.match_node.countdown > 0.5:
			fail("Match countdown advanced behind the loading cover"); return
		if not await observe_world(): return
		if not await capture(map_id + "-first"): return
		for frame in 60: await RenderingServer.frame_post_draw
		if not await capture(map_id + "-settled"): return
		var reveal_started:=Time.get_ticks_msec()
		while not app.match_node.local_robot.visible:
			if Time.get_ticks_msec()-reveal_started>15000:
				fail("Local robot did not reveal after preparation"); return
			await process_frame
		if not app.match_node.local_robot.spawn_started:
			fail("Robot revealed before its spawn sequence began"); return
		if not await capture(map_id + "-spawn-revealed"): return
		await retire_observer()
		await app.leave_match()
		if not await observe_world(): return
		if not await capture("menu-after-" + map_id): return
	await retire_observer()
	write_report(true)
	print("RENDERER_STARTUP_PASS captures=", rows.size())
	await app.request_quit()
