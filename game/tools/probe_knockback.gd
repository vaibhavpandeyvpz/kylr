extends SceneTree

func _initialize() -> void:
	call_deferred("probe")

func probe() -> void:
	var game := ArenaMatch.new()
	game.online=true
	root.add_child(game)
	await physics_frame
	await physics_frame
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	await physics_frame
	game.phase="Active"
	game.goal=1000
	game.time_limit=10000
	var robot: ArenaRobot=game.add_robot(0,"Impulse probe",0,true,"projector")
	robot.spawn_remaining=0
	robot.protection=0
	robot.move_input=Vector2.ZERO
	# Faceoff's broad upper walkway provides room for a collision-free impulse.
	var start := Vector3(6,0.05,20)
	var output: Array=[]
	for weapon in ["emp", "rocket"]:
		robot.position=start
		robot.velocity=Vector3.ZERO
		robot.knockback_velocity=Vector3.ZERO
		robot.applied_knockback=Vector3.ZERO
		for frame in 4: await physics_frame
		var origin := robot.position
		var impulse := Knockback.emp(Vector3.FORWARD) if weapon=="emp" else Knockback.rocket(Vector3.FORWARD)
		robot.apply_knockback(impulse)
		var peak := origin.y
		var immediately := robot.position
		for frame in 100:
			await physics_frame
			peak=maxf(peak,robot.position.y)
		var travel := Vector2(robot.position.x-origin.x,robot.position.z-origin.z).length()
		output.append({"weapon":weapon,"travel":travel,"bounce":peak-origin.y,"no_warp":immediately==origin,"landed":robot.is_on_floor()})
		if travel<0.4 or not robot.is_on_floor(): push_error("Knockback failed: "+weapon); quit(1); return
	if output[1].travel <= output[0].travel or output[1].bounce <= output[0].bounce:
		push_error("Rocket must push farther and bounce higher than EMP"); quit(1); return
	var wall := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size=Vector3(4,4,0.2)
	shape.shape=box
	wall.add_child(shape)
	wall.position=Vector3(6,2,18)
	root.add_child(wall)
	robot.position=start
	robot.velocity=Vector3.ZERO
	robot.knockback_velocity=Vector3.ZERO
	robot.applied_knockback=Vector3.ZERO
	for frame in 4: await physics_frame
	robot.apply_knockback(Knockback.rocket(Vector3.FORWARD))
	for frame in 100: await physics_frame
	if robot.position.z < 18.4: push_error("Knockback crossed the wall"); quit(1); return
	output.append({"wall_stop_z":robot.position.z,"remaining_impulse":robot.knockback_velocity.length()})
	print("KNOCKBACK_PROBE ",JSON.stringify(output))
	game.phase="Finished"
	for voice in game.audio.voices: voice.stop()
	OS.delay_msec(100) # Let the audio thread release stopped WAV playback before teardown.
	game.queue_free()
	wall.queue_free()
	for frame in 3: await physics_frame
	quit()
