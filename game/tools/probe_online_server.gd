extends SceneTree
var transport: OnlineTransport
func _initialize(): run.call_deferred()
func run():
	transport = OnlineTransport.new()
	transport.name = "OnlineTransport"
	root.add_child(transport)
	await transport.start_server()
	var seeded := false
	var forced_finish := false
	var original := transport.generation
	var deadline := Time.get_ticks_msec()+90000
	while Time.get_ticks_msec() < deadline:
		await physics_frame
		if not transport.game or transport.building: continue
		var game := transport.game
		if game.phase == "Active" and not seeded and game.robots.size() >= 2 and game.elapsed > 6:
			seeded = true
			# Actual server-owned shots against physical robot hit regions.
			var shooter: ArenaRobot = game.robots[0]
			var target: ArenaRobot = game.robots[1]
			var floor := StaticBody3D.new()
			var shape := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size = Vector3(12,1,12)
			shape.shape = box
			floor.add_child(shape)
			game.add_child(floor)
			floor.position = Vector3(0,60,0)
			shooter.global_position = Vector3(0,60.51,0)
			target.global_position = shooter.global_position+Vector3(0,0,-3)
			for robot in [shooter,target]: robot.spawn_remaining = 0; robot.protection = 0; robot.velocity = Vector3.ZERO; robot.show()
			shooter.yaw = 0
			shooter.pitch = 0
			for shot in 12:
				shooter.yaw = 0
				shooter.pitch = 0
				shooter.update_aim_pose(0)
				shooter.cooldown = 0
				shooter.wants_fire = true
				game.combat.trigger(shooter,1.0/60)
				await physics_frame
			print("ONLINE_COMBAT target_deaths=",target.deaths," shooter_kills=",shooter.kills)
		# The probe must admit its late third client before it closes admission.
		if game.phase == "Active" and game.elapsed > 12 and game.robots.size() >= 3 and not forced_finish:
			forced_finish = true
			game.finish()
		if transport.generation != original:
			print("ONLINE_NEXT_MAP advanced=true")
			break
	await create_timer(15).timeout
	transport.close()
	quit()
