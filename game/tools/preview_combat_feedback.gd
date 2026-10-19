extends SceneTree

func _initialize(): call_deferred("capture")

func capture():
	var app = load("res://app.tscn").instantiate()
	root.add_child(app)
	if not app.startup_complete: await app.startup_finished
	app.prefs.values.count = 2
	app.prefs.values.name = "Feedback"
	await app.start_match()
	await create_timer(23).timeout
	var game: ArenaMatch = app.match_node
	game.set_physics_process(false)
	var shooter: ArenaRobot = game.local_robot
	var victim: ArenaRobot = game.robots[1]
	for robot in game.robots:
		robot.set_physics_process(false)
		robot.protection = 0
		robot.spawn_remaining = 0
		robot.streaming = false
		robot.wants_fire = false
		robot.recoil = 0
		robot.pose("idle")
	shooter.global_position = game.map.world_point([0,0,-8])
	shooter.yaw = 0
	shooter.pitch = 0
	victim.global_position = shooter.global_position + Vector3(0,0,-12)
	victim.yaw = PI
	for view in [false,true]:
		game.third_person = view
		game.camera_snap = true
		for weapon in ["pistol","rifle"]:
			shooter.equip(weapon)
			await create_timer(0.25).timeout
			shooter.weapon_vfx.begin_shot()
			shooter.weapon_vfx.shot()
			victim.hit(1,shooter,weapon)
			game.effects.impact(victim.eye(),Vector3.BACK,false,null,true)
			await create_timer(0.025).timeout
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://reports/feedback-%s-%s.png" % ["tpv" if view else "fpv",weapon])
	game.third_person = false
	game.camera_snap = true
	await create_timer(0.3).timeout
	game.hit_marker = 0.0
	shooter.hit(20,victim,"rifle")
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/feedback-incoming.png")
	app.request_quit()
