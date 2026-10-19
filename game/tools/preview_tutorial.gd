extends SceneTree
func _initialize(): run.call_deferred()
func run():
	var app = load("res://app.tscn").instantiate()
	root.add_child(app)
	if not app.startup_complete: await app.startup_finished
	app.prefs = Preferences.new("res://reports/online/tutorial-preview.cfg")
	app.prefs.values.count = 2
	app.prefs.values.name = "Learner"
	app.prefs.values.type = 2
	app.prefs.values.tutorial_hints = true
	await app.start_match()
	await create_timer(ArenaMatch.OPENING_SECONDS+6).timeout
	var game: ArenaMatch = app.match_node
	game.set_physics_process(false)
	for robot in game.robots: robot.set_physics_process(false)
	game.local_robot.protection = 0
	game.phase = "Active"
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/online/tutorial-first-life.png")
	assert(not app.ui.tutorial.text.is_empty())
	assert(not app.ui.resources.accessibility_name.is_empty())
	assert(not app.ui.weapon.accessibility_name.is_empty())
	app.request_quit()
