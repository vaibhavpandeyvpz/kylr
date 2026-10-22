extends GutTest

func test_lethal_surface_impact_breaks_up_once_with_local_feedback_and_no_pickup():
	var game := await fixture()
	var robot := actor(game)
	game.local_robot = robot
	game.camera_rig.set_process(false)
	game.replicating = true
	game.authority = true
	var floor_body := StaticBody3D.new()
	floor_body.set_meta("lethal_surface",true)
	game.add_child(floor_body)
	floor_body.position = Vector3(200,39.85,0)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(10,0.3,10)
	collision.shape = shape
	floor_body.add_child(collision)
	await wait_physics_frames(2)
	watch_signals(game)
	robot.velocity = Vector3(2,0,1) # Collision has already consumed vertical speed.
	robot.pose("common/falling")
	robot.animator.advance(0.4)
	var falling_poses: Array[Transform3D] = []
	for bone in robot.skeleton.get_bone_count(): falling_poses.append(robot.skeleton.get_bone_global_pose(bone))
	game.eliminate(robot,null,"Fall off map",{"velocity":Vector3(2,-25,1)})
	var corpse: Dictionary = game.corpses.back()
	assert_true(corpse.node is RobotDebris)
	assert_false(corpse.falling_out)
	assert_eq(corpse.ep,0.0)
	assert_eq(corpse.time,4.0)
	assert_eq(corpse.node.recipe.weapon,"Fall off map")
	assert_eq(corpse.node.recipe.poses,falling_poses,"Impact preserves the falling pose without sampling a standing or lying clip")
	assert_eq(corpse.node.recipe.velocity,Vector3(0.5,0,0.25),"Ground contact consumes downward speed before debris launch")
	assert_signal_emit_count(game,"fall_impact",1)
	assert_gt(game.camera_rig.impact_shake.remaining,0.0)
	assert_eq(game.presentation_events.filter(func(event):return event.kind=="fall_explosion").size(),1)
	assert_eq(game.presentation_events.filter(func(event):return event.kind=="fall_explosion")[0].incoming,Vector3(2,-25,1),"Replicate pre-contact descent for the 3D explosion frame")
	game.eliminate(robot,null,"Fall off map")
	assert_signal_emit_count(game,"fall_impact",1)
	game.tick_drops(4.01)
	assert_true(game.corpses.is_empty())
	assert_true(game.drops.is_empty())

func test_void_fall_has_no_impact_flash_explosion_or_breakup():
	var game := await fixture()
	var robot := actor(game)
	game.local_robot = robot
	game.replicating = true
	game.authority = true
	watch_signals(game)
	game.eliminate(robot,null,"Fall off map")
	assert_false(game.corpses.back().node is RobotDebris)
	assert_true(game.corpses.back().falling_out)
	assert_signal_not_emitted(game,"fall_impact")
	assert_true(game.presentation_events.filter(func(event):return event.kind=="fall_explosion").is_empty())

func test_fall_cloud_is_independent_and_has_less_dust_than_grenade():
	var fall_effect := preload("res://assets/effects/original/fall_impact.tscn").instantiate() as OriginalEffect
	var grenade := preload("res://assets/effects/original/grenade.tscn").instantiate() as OriginalEffect
	add_child_autofree(fall_effect)
	add_child_autofree(grenade)
	assert_eq(fall_effect.surfaces.size(),grenade.surfaces.size(),"Both clouds cover the complete impact sphere")
	assert_lt(float(fall_effect.surfaces[0].size),float(grenade.surfaces[0].size))
	assert_lt(fall_effect.duration,grenade.duration)
	assert_true(fall_effect.emitters.is_empty(),"Body assemblies supply physical debris")
	for surface in fall_effect.surfaces:
		if surface.layer == 3:
			assert_eq(surface.material.get_shader_parameter("effect_opacity"),0.45)

func test_replicated_fall_feedback_is_local_and_respects_reduced_motion():
	var game := await fixture()
	game.local_robot = actor(game)
	game.camera_rig.set_process(false)
	watch_signals(game)
	game.fall_impact_feedback(99,true)
	assert_signal_not_emitted(game,"fall_impact")
	assert_eq(game.camera_rig.impact_shake.remaining,0.0)
	game.reduced_motion = true
	game.fall_impact_feedback(game.local_robot.robot_id,true)
	assert_signal_emit_count(game,"fall_impact",1)
	assert_eq(game.camera_rig.impact_shake.remaining,0.0)
	game.reduced_motion = false
	game.fall_impact_feedback(game.local_robot.robot_id,true)
	assert_signal_emit_count(game,"fall_impact",2)
	assert_gt(game.camera_rig.impact_shake.remaining,0.0)
	assert_true(game.presentation_events.is_empty(),"Receiving feedback never echoes an event")

func fixture() -> ArenaMatch:
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	game.phase = "Active"
	game.set_physics_process(false)
	game.set_process(false)
	return game

func actor(game: ArenaMatch, id := 0, head := "raptor") -> ArenaRobot:
	var robot: ArenaRobot = game.add_robot(id, "Debris", id % 2, true, head)
	robot.set_process(false)
	robot.set_physics_process(false)
	robot.protection = 0
	robot.spawn_remaining = 0
	robot.sh = 0
	robot.global_position = Vector3(200, 40, 0)
	robot.last_safe = robot.global_position
	robot.update_aim_pose(0)
	return robot

func triangles(root: Node3D, skinned_only := false) -> int:
	var count := 0
	for mesh: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if not mesh.visible or (skinned_only and mesh.skin == null) or String(mesh.name).begins_with("SK_TensorShield"): continue
		for surface in mesh.mesh.get_surface_count():
			var arrays := mesh.mesh.surface_get_arrays(surface)
			count += arrays[Mesh.ARRAY_INDEX].size() / 3 if arrays[Mesh.ARRAY_INDEX] != null and not arrays[Mesh.ARRAY_INDEX].is_empty() else arrays[Mesh.ARRAY_VERTEX].size() / 3
	return count

func appearance(root: Node3D) -> Array:
	var result: Array = []
	for mesh: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(surface)
			result.append([material.get_instance_id(), material.emission_enabled if material is StandardMaterial3D else false])
	return result

func test_explosive_deaths_preserve_geometry_pose_appearance_and_expiry():
	var game := await fixture()
	var robot := actor(game)
	for weapon in RobotDebris.WEAPONS:
		robot.alive = true
		robot.show()
		robot.pose("idle")
		robot.animator.advance(0.0)
		var head_pose := robot.skeleton.global_transform * robot.skeleton.get_bone_global_pose(robot.skeleton.find_bone("Head"))
		var expected_triangles := triangles(robot.body, true)
		game.eliminate(robot, null, weapon, {"direction":Vector3.RIGHT, "point":robot.eye()})
		var debris := game.corpses.back().node as RobotDebris
		assert_not_null(debris)
		assert_eq(triangles(debris), expected_triangles, "Every visible authored triangle survives exactly once")
		assert_true(debris.bodies.Head.global_transform.is_equal_approx(head_pose), "Breakup starts from the live pose")
		assert_almost_eq(robot.respawn_time, 4.0, 0.0001)
		assert_eq(debris.bodies.size(), RobotDebris.GROUPS.size())
		for body: RigidBody3D in debris.bodies.values():
			assert_eq(body.collision_layer, 0, "Debris cannot block actors or weapon traces")
			assert_eq(body.collision_mask, 1, "Debris collides with the arena only")
			assert_gt(body.linear_velocity.x, 0.0, "Impact direction biases every piece away from the hit")
			assert_gt(body.angular_velocity.length(), 0.1)
			var shapes := 0
			for node in body.get_children():
				if node is CollisionShape3D:
					shapes += 1
					assert_true(node.shape is ConvexPolygonShape3D)
				if node is MeshInstance3D and node.material_override is StandardMaterial3D:
					assert_false(node.material_override.emission_enabled)
			assert_gt(shapes, 0, "Every assembly has authored collision geometry")
		game.tick_drops(4.001)
		assert_eq(game.corpses.size(), 0)
		await wait_process_frames(1)
		assert_false(is_instance_valid(debris), "Expiry frees all bodies and render fragments together")

func test_splash_scatters_away_from_blast_and_emp_is_tighter():
	var game := await fixture()
	var robot := actor(game)
	var contact := {"point":robot.eye() + Vector3.RIGHT * 4, "direction":Vector3.RIGHT, "radial":true}
	var recipe := RobotDebris.capture(robot, "rocket_launcher", contact, game.gravity)
	recipe.seed = 123
	var rocket := RobotCorpse.create(game, robot, robot.body.global_transform, "", recipe) as RobotDebris
	var emp_recipe := recipe.duplicate(true)
	emp_recipe.weapon = "emp_gun"
	var emp := RobotCorpse.create(game, robot, robot.body.global_transform, "", emp_recipe) as RobotDebris
	for id in rocket.bodies:
		assert_lt(rocket.bodies[id].linear_velocity.x, 0.0, "Blast position wins over incoming projectile direction for splash")
		assert_lt(emp.bodies[id].linear_velocity.length(), rocket.bodies[id].linear_velocity.length())
		assert_lt(emp.bodies[id].angular_velocity.length(), rocket.bodies[id].angular_velocity.length())
	rocket.queue_free()
	emp.queue_free()

func test_replica_starts_at_current_debris_state_and_does_not_restart():
	var game := await fixture()
	var robot := actor(game)
	game.eliminate(robot, null, "grenade_launcher", {"direction":Vector3.LEFT})
	var original := game.corpses[0].node as RobotDebris
	original.bodies.Head.global_position += Vector3(2, 3, 4)
	original.bodies.Head.linear_velocity = Vector3(1, 2, 3)
	var state := RobotCorpse.snapshot(original)
	# Replicate through the actual Variant wire representation.
	state = bytes_to_var(var_to_bytes(state))
	robot.body.global_position += Vector3(20, 0, 20)
	var previous := robot.body.global_transform
	var replica := RobotCorpse.from_snapshot(game, robot, state) as RobotDebris
	assert_eq(robot.body.global_transform, previous, "Restoring a corpse does not move its live robot")
	assert_eq(replica.bodies.Head.global_transform, original.bodies.Head.global_transform)
	assert_eq(replica.bodies.Head.linear_velocity, original.bodies.Head.linear_velocity)
	var moved: Vector3 = replica.bodies.Head.global_position + Vector3.UP
	replica.bodies.Head.global_position = moved
	RobotCorpse.apply_snapshot(replica, state)
	assert_almost_eq(replica.bodies.Head.global_position, moved, Vector3.ONE * 0.0001, "Repeated snapshots never restart local physics")
	assert_lt(var_to_bytes(state).size() * 10, 200000, "Ten simultaneous corpses leave room in the 256 KB snapshot budget")
	replica.queue_free()

func test_physics_debris_falls_and_is_supported_by_world_collision():
	var game := await fixture()
	var robot := actor(game)
	var floor := StaticBody3D.new()
	game.add_child(floor)
	floor.position = Vector3(200, 35.5, 0)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(40, 1, 40)
	shape.shape = box
	floor.add_child(shape)
	await wait_physics_frames(2)
	game.eliminate(robot, null, "emp_gun", {"direction":Vector3.DOWN})
	var debris := game.corpses[0].node as RobotDebris
	var start: Vector3 = debris.bodies.Chest.global_position
	await wait_physics_frames(180)
	assert_lt(debris.bodies.Chest.global_position.y, start.y - 1.0)
	for body: RigidBody3D in debris.bodies.values():
		assert_gt(body.global_position.y, 35.8, "World collision catches each falling assembly")
	assert_eq(game.corpses.size(), 1, "Physics settling never controls authoritative expiry")

func test_blocked_or_nonlethal_hits_do_not_break_up_and_lethal_contact_is_forwarded():
	var game := await fixture()
	var robot := actor(game)
	robot.protection = 1
	assert_false(robot.hit(200, null, "rocket_launcher"))
	assert_true(game.corpses.is_empty())
	robot.protection = 0
	assert_true(robot.hit(5, null, "emp_gun"))
	assert_true(game.corpses.is_empty())
	robot.velocity = Vector3(1, 2, 3)
	assert_true(robot.hit(200, null, "emp_gun", Knockback.emp(Vector3.LEFT), {"direction":Vector3.LEFT, "point":Vector3(201, 41, 0)}))
	var debris := game.corpses[0].node as RobotDebris
	assert_eq(debris.recipe.direction, Vector3.LEFT)
	assert_eq(debris.recipe.velocity, Vector3(1, 2, 3), "Debris inherits motion before this lethal hit's knockback")

func test_transport_restores_headless_breakup_and_removes_it_on_expiry():
	var server_game := await fixture()
	var victim := actor(server_game)
	server_game.replicating = true
	server_game.authority = true
	server_game.eliminate(victim, null, "rocket_launcher", {"direction":Vector3.BACK})
	var original := server_game.corpses[0].node as RobotDebris
	assert_eq(triangles(original), 0, "Dedicated servers simulate bodies without render fragments")
	var sender := OnlineTransport.new()
	sender.game = server_game
	sender.closed = true
	sender.peers[7] = {"ack":0}
	add_child_autoqfree(sender)
	var receiver_game := await fixture()
	var receiver := OnlineTransport.new()
	receiver.game = receiver_game
	receiver.closed = true
	receiver.local_id = 0
	add_child_autoqfree(receiver)
	var snapshot := sender.make_snapshot(7)
	receiver.apply_snapshot(bytes_to_var(var_to_bytes(snapshot)), true)
	assert_eq(receiver.remote_corpses.size(), 1)
	var replica := receiver.remote_corpses.values()[0] as RobotDebris
	assert_not_null(replica)
	assert_gt(triangles(replica), 0, "Clients restore visible fragments even from a headless server")
	assert_same(receiver_game.local_death_corpse, replica)
	assert_almost_eq(receiver_game.death_view_remaining, 4.0, 0.0001)
	var moved: Vector3 = replica.bodies.Head.global_position + Vector3.UP
	replica.bodies.Head.global_position = moved
	receiver.apply_snapshot(sender.make_snapshot(7))
	assert_almost_eq(replica.bodies.Head.global_position, moved, Vector3.ONE * 0.0001, "Transport does not rewind locally simulated debris")
	server_game.tick_drops(4.01)
	receiver.apply_snapshot(sender.make_snapshot(7))
	assert_true(receiver.remote_corpses.is_empty())
	await wait_process_frames(1)
	assert_false(is_instance_valid(replica))

func test_ten_simultaneous_breakups_fit_the_complete_snapshot_budget():
	var game := await fixture()
	game.replicating = true
	game.authority = true
	for id in 10:
		var robot := actor(game, id, ["raptor", "projector", "sentinel", "porthole", "arachne"][id % 5])
		robot.position.x += id * 2
		robot.body.rotation.y = float(id) * 0.6
		robot.skeleton.set_bone_pose_rotation(robot.skeleton.find_bone("LeftUpperArm"), Quaternion(Vector3.RIGHT, float(id) * 0.1))
		game.eliminate(robot, null, RobotDebris.WEAPONS[id % 3], {"direction":Vector3.FORWARD.rotated(Vector3.UP, float(id))})
	var sender := OnlineTransport.new()
	sender.closed = true
	sender.game = game
	sender.peers[7] = {"ack":0}
	add_child_autoqfree(sender)
	var bytes := var_to_bytes(sender.make_snapshot(7))
	var compressed := bytes.compress(FileAccess.COMPRESSION_DEFLATE)
	assert_eq(game.corpses.size(), 10)
	assert_lt(bytes.size(), 256000, "Complete maximum-roster state fits the decoded protocol budget")
	assert_lt(compressed.size(), 64000, "Complete maximum-roster state fits the compressed protocol budget")
	print("DEBRIS_SNAPSHOT ten_corpses decoded=%d compressed=%d" % [bytes.size(), compressed.size()])

func test_corpse_restoration_does_not_change_live_robot_materials_or_animation():
	var game := await fixture()
	var robot := actor(game)
	for weapon in ["pistol", "rocket_launcher"]:
		robot.alive = true
		game.eliminate(robot, null, weapon)
		var state := RobotCorpse.snapshot(game.corpses.back().node)
		robot.alive = true
		Assets.paint(robot.body, robot.tint, robot.armor_secondary, robot.head, false, robot.upper_body)
		robot.pose("idle")
		var before := appearance(robot.body)
		var animation := robot.animator.assigned_animation
		var replica := RobotCorpse.from_snapshot(game, robot, state)
		assert_eq(appearance(robot.body), before, "Corpse materials belong to the corpse, even after its robot respawns")
		assert_eq(robot.animator.assigned_animation, animation, "Loading a corpse clip cannot re-pose its live robot")
		replica.queue_free()
