extends GutTest

func test_bots_clear_both_native_lifts_and_board_only_when_the_deck_returns():
	var game := ArenaMatch.new()
	game.online=true
	game.map_id="faceoff"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	await wait_physics_frames(2)
	game.map.build_navigation()
	game.set_physics_process(false)
	game.phase="Active"
	for controller in game.map.cargo_lifts: controller.set_physics_process(false)
	assert_eq(game.map.cargo_lifts.size(),2)
	for controller: ArchitectureLift in game.map.cargo_lifts:
		controller.motion.play("lift_up")
		var state: Dictionary=controller.motion.channels.main
		state.time=state.player.get_animation("lift_up").length
		controller.motion.sample(state)
		state.done=true
		controller.requested=controller.upper
		controller.traveling=false
		controller.hold=0
		await wait_physics_frames(2)
		var robot: ArenaRobot=game.add_robot(game.robots.size(),"Lift waiter",0,false,"projector")
		robot.set_physics_process(false)
		robot.set_process(false)
		robot.protection=0
		robot.spawn_remaining=0
		robot.global_position=controller.surface.global_position
		robot.position.y=controller.lower+0.01
		var source := robot.position
		var destination := Vector3(source.x,controller.upper,source.z)
		robot.brain=ArenaBrain.new(robot)
		var brain: ArenaBrain=robot.brain
		brain.goal=destination
		brain.path=[{"action":"walk","from":source,"point":source,"entry":Vector3.INF},{"action":"lift","from":source,"point":destination,"entry":Vector3.INF}]
		brain.path_index=0
		brain.retarget=1000
		var waiting: Vector3=controller.waiting_point(robot,controller.lower)
		assert_false(controller.needs_clearance(robot,waiting),"Waiting point clears the entire capsule")
		assert_true(game.map.traversal.supported(waiting),"Wait on real room flooring")
		assert_true(controller.needs_clearance(robot,robot.position),"Bot starts underneath the absent deck")
		var rider: ArenaRobot=game.add_robot(game.robots.size(),"Upper rider",0,false,"projector")
		rider.set_physics_process(false)
		rider.set_process(false)
		rider.protection=0
		rider.spawn_remaining=0
		rider.global_position=controller.surface.global_position+Vector3.UP*0.01
		rider.brain=ArenaBrain.new(rider)
		rider.brain.goal=waiting
		rider.brain.path=[{"action":"lift","from":destination,"point":source,"entry":Vector3.INF}]
		rider.brain.transition_index=0
		rider.brain.transition_launched=true
		rider.brain.retarget=1000
		var returned := false
		var boarded := false
		for frame in 900:
			brain.steer(1.0/60.0)
			rider.brain.steer(1.0/60.0)
			robot.simulate_movement(1.0/60.0)
			rider.simulate_movement(1.0/60.0)
			controller._physics_process(1.0/60.0)
			await wait_physics_frames(1)
			if controller.boarding_ready(controller.lower): returned=true
			if brain.transition_launched: boarded=true
			if boarded and controller.boarding_ready(controller.upper): break
		assert_true(returned,"The lower waiter no longer traps the deck upstairs")
		assert_true(boarded,"Bot boards through the native occupancy trigger")
		assert_true(controller.boarding_ready(controller.upper),"The lift can complete the next trip")
		assert_lt(rider.position.y,controller.lower+0.2,"The upstairs robot returns to the lower room")
		assert_false(controller.needs_clearance(rider,rider.position),"Returning rider exits the descent footprint")
		robot.position.x+=20
		rider.position.x+=20
