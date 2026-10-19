extends SceneTree
## Render inventory states without altering the player's saved preferences.
func _initialize(): call_deferred("capture")

func capture():
	var app = load("res://app.tscn").instantiate()
	root.add_child(app)
	if not app.startup_complete: await app.startup_finished
	app.prefs.storage_path="user://inventory-preview.cfg"
	app.prefs.values.quality_benchmarked=true
	app.prefs.values.count=2
	app.prefs.values.tutorial_hints=false
	app.prefs.values.third_person=false
	app.prefs.values.hud_scale=1.0
	await app.start_match()
	await create_timer(23).timeout
	var game: ArenaMatch = app.match_node
	game.set_physics_process(false)
	var shooter: ArenaRobot = game.local_robot
	for actor in game.robots:
		actor.set_physics_process(false)
		actor.protection=0
		actor.spawn_remaining=0
		actor.wants_fire=false
		actor.streaming=false
	shooter.global_position=game.map.world_point([0,0,-8])
	shooter.yaw=0
	shooter.pitch=0
	shooter.sh=83
	shooter.shield_time=42
	shooter.ah=76
	shooter.ep=61
	game.third_person=false
	game.camera_snap=true
	DirAccess.make_dir_recursive_absolute("res://reports/inventory")
	root.size=Vector2i(1920,1080)
	for id in Arsenal.WEAPONS:
		if id!="pistol":
			shooter.take_weapon(id)
			shooter.loaded-=7
			shooter.pickup_ammo(id)
		await create_timer(.3).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://reports/inventory/slots-%d.png" % shooter.owned_weapons.size())
	for resolution in [Vector2i(1920,1080),Vector2i(1280,720),Vector2i(720,1280)]:
		root.size=resolution
		for id in Arsenal.WEAPONS:
			shooter.select_weapon(id)
			await create_timer(.3).timeout
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://reports/inventory/%dx%d-%s.png" % [resolution.x,resolution.y,id])
	if "--messages" in OS.get_cmdline_user_args():
		root.size=Vector2i(1920,1080)
		shooter.select_weapon("rifle")
		app.prefs.values.subtitles=true
		app.prefs.values.tutorial_hints=true
		app.ui.tutorial_hints.finished=false
		app.ui.tutorial_hints.clock=16
		game.callouts.captions.clear()
		game.callouts.publish("ARENA / Cover changing", "Announcer", -1, true)
		game.callouts.publish("Cover me", "Kestrel", shooter.team, false, shooter.global_position, -1, 1)
		for kind in ["ammo", "weapon"]:
			app.ui.show_notice(ArenaMap.pickup_notice({"kind":kind,"weapon":"rifle"}))
			await create_timer(.2).timeout
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://reports/inventory/messages-%s.png" % kind)
		app.prefs.values.contrast=true
		app.ui.show_notice("POWER / Low energy")
		await create_timer(.2).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://reports/inventory/messages-contrast.png")
	print("INVENTORY previews complete")
	app.request_quit()
