extends SceneTree

func _initialize(): probe.call_deferred()

func probe():
	var app=load("res://app.tscn").instantiate()
	root.add_child(app)
	if not app.startup_complete: await app.startup_finished
	app.prefs=Preferences.new("res://reports/lunar-preview.cfg")
	app.prefs.values.count=2
	app.prefs.values.quality_benchmarked=true
	await app.start_match()
	var game: ArenaMatch=app.match_node
	while game.phase!="Active": await physics_frame
	var surface: Dictionary={}
	for x in [-60,-45,-30,0,30,45,60]:
		for z in [-60,-45,-30,0,30,45,60]:
			var hit=game.combat.ray(Vector3(x,60,z),Vector3(x,-8,z),[],1)
			if not hit.is_empty() and hit.collider.get_meta("lethal_surface",false):
				surface=hit
				break
		if not surface.is_empty(): break
	assert(not surface.is_empty())
	var robot: ArenaRobot=game.local_robot
	robot.position=surface.position+Vector3.UP*6
	robot.velocity=Vector3.DOWN*8
	robot.protection=0
	for frame in 240:
		await physics_frame
		if not robot.alive: break
	assert(not robot.alive)
	var corpse: Dictionary=game.corpses[-1]
	assert(not corpse.falling_out)
	assert(absf(corpse.node.global_position.y-surface.position.y)<0.15)
	corpse.time=999
	robot.respawn_time=999
	var animator: AnimationPlayer=corpse.node.find_child("RuntimeAnimator",true,false)
	animator.seek(animator.current_animation_length,true)
	animator.pause()
	game.set_process(false)
	game.camera_rig.host.set_process(false)
	game.first_person.hide()
	game.first_person.set_process(false)
	app.ui.hide()
	game.camera.global_position=corpse.node.global_position+Vector3(3,2.5,3)
	game.camera.look_at(corpse.node.global_position+Vector3.UP*.3)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/lunar-impact.png")
	print("LUNAR_IMPACT grounded=",not corpse.falling_out," ground_y=",surface.position.y," corpse_y=",corpse.node.global_position.y)
	app.request_quit()
