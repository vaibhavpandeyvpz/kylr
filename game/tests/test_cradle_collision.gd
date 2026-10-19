extends GutTest

func test_collected_cradle_disables_each_claw_and_hidden_payload_but_keeps_base():
	var game := ArenaMatch.new();game.map_id="faceoff";game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5.0,true);game.map.start_loadout()
	await wait_physics_frames(5)
	game.phase="Active"
	var cradles: Array=game.map.fixtures.filter(func(item):return item.has("claw_colliders") and item.kind=="weapon")
	assert_gte(cradles.size(),2)
	var first: Dictionary=cradles[0]
	var second: Dictionary=cradles[1]
	for fixture in [first,second]:
		game.map.pickup_animation_finished("close",fixture)
	await wait_physics_frames(2)
	assert_eq(first.claw_colliders.size(),4)
	for body in first.claw_colliders:
		assert_true(String(body.name).begins_with("SK_ItemCradleClaw"))
		assert_eq(body.collision_layer,1)
	assert_gt(first.payload_colliders.size(),0,"Pickup weapon has native physical bodies")
	var robot: ArenaRobot=game.add_robot(0,"Cradle probe",0,false,"projector")
	robot.set_physics_process(false);robot.protection=0
	assert_true(game.map.can_collect(first,robot))
	game.map.collect(first,robot)
	await wait_physics_frames(2)
	assert_false(first.ready)
	assert_false(first.payload.visible)
	for body in first.claw_colliders+first.payload_colliders:assert_eq(body.collision_layer,0,"Empty cradle cannot snag the robot")
	var bases: Array=first.node.find_children("SK_ItemCradleBaseCol","StaticBody3D",true,false)
	assert_eq(bases.size(),1)
	assert_eq(bases[0].collision_layer,1,"Fixed plinth remains solid")
	for body in second.claw_colliders:assert_eq(body.collision_layer,1,"Shared collider resources preserve independent occupancy")
	# Walk the real robot motor across the empty cradle, on an isolated floor.
	game.set_physics_process(false)
	var ground := StaticBody3D.new();game.add_child(ground)
	var shape := CollisionShape3D.new();var box := BoxShape3D.new()
	box.size=Vector3(6,.1,6);shape.shape=box;ground.add_child(shape)
	ground.position=Vector3(100,9.95,100)
	first.node.global_position=Vector3(100,10,100)
	robot.global_position=first.node.to_global(Vector3(0,.025,1.0));robot.velocity=Vector3.ZERO
	var forward: Vector3=-first.node.global_basis.z.normalized()
	robot.yaw=atan2(-forward.x,-forward.z);robot.move_input=Vector2(0,-1)
	await wait_physics_frames(2)
	for frame in 120:
		robot.simulate_movement(1.0/60.0,false,true)
		await wait_physics_frames(1)
		if first.node.to_local(robot.global_position).z<-.8: break
	assert_lt(first.node.to_local(robot.global_position).z,-.7,"Real robot crosses the empty cradle without snagging")
	assert_gt(robot.global_position.y,9.9,"Solid base and ground still support the robot")
	first.cooldown=0
	game.map.pickup_animation_finished("close",first)
	await wait_physics_frames(2)
	assert_true(first.ready)
	for body in first.claw_colliders+first.payload_colliders:assert_eq(body.collision_layer,1,"Occupied cradle collision returns on respawn")
	# Online snapshots use the same transition helper on each client.
	game.map.set_pickup_collision(first,false)
	await wait_physics_frames(2)
	for body in first.claw_colliders+first.payload_colliders:assert_eq(body.collision_layer,0)
