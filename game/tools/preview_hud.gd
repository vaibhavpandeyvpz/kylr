extends SceneTree

func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	var mode := "CTF" if "--ctf" in OS.get_cmdline_user_args() else "TDM"
	var app = load("res://app.tscn").instantiate()
	root.add_child(app)
	if not app.startup_complete: await app.startup_finished
	app.prefs.values.count = 4
	app.prefs.values.type = 2 if mode == "CTF" else 1
	await app.start_match()
	await create_timer(20.0).timeout
	var game: ArenaMatch = app.match_node
	var pilot: ArenaRobot = game.local_robot
	pilot.sh = 74
	pilot.shield_time = 41
	pilot.pickup_weapon = "rifle"
	pilot.loaded = 27
	pilot.packs = 2
	pilot.equip("rifle")
	game.push_feed({"kind":"kill", "killer":game.robots[0].display_name, "killer_team":0,
		"victim":game.robots[1].display_name, "victim_team":1, "weapon":"Minigun"})
	game.push_feed({"kind":"kill", "killer":game.robots[3].display_name, "killer_team":1,
		"victim":game.robots[2].display_name, "victim_team":0, "weapon":"Rifle"})
	if mode == "CTF":
		game.push_feed({"kind":"flag", "actor":game.robots[1].display_name,
			"team":1, "action":"took the flag"})
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/hud-%s.png" % mode.to_lower())
	app.request_quit()
