extends GutTest

func fixture() -> ArenaMatch:
	var game := ArenaMatch.new()
	game.online = true
	game.replicating = true
	add_child_autoqfree(game)
	return game

func test_network_restore_preserves_crouch_stream_and_dark_death_then_respawn():
	var game := fixture()
	await wait_physics_frames(3)
	var robot: ArenaRobot = game.add_robot(1,"Pilot",0,true,"raptor")
	var state := robot.network_state()
	state.weapon = "flamethrower"
	state.motor.crouched = true
	state.motor.streaming = true
	robot.restore_network(state)
	assert_almost_eq(robot.body_capsule.height,1.18,0.001)
	assert_true(robot.streaming,"Equipping a snapshot weapon preserves its held stream")
	state.alive = false
	robot.restore_network(state)
	assert_eq(emissive_surfaces(robot.body),0,"Remote deaths darken every armor surface")
	state.alive = true
	robot.restore_network(state)
	assert_gt(emissive_surfaces(robot.body),0,"Respawn restores authored emission")

func emissive_surfaces(node: Node) -> int:
	var count := 0
	for mesh in node.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(index) as StandardMaterial3D
			if material != null and material.emission_enabled: count += 1
	return count

func test_accepted_damage_events_reach_only_the_correct_local_feedback():
	var game := fixture()
	await wait_physics_frames(3)
	game.authority = false
	var transport := OnlineTransport.new()
	transport.game = game
	transport.closed = true
	transport.local_id = 1
	add_child_autoqfree(transport)
	watch_signals(game)
	transport.apply_presentation({"kind":"damage","attacker":1,"victim":2,"source":Vector3.RIGHT,"amount":4.0})
	assert_almost_eq(game.hit_marker,0.24,0.001)
	assert_signal_not_emitted(game,"damage_taken")
	transport.apply_presentation({"kind":"damage","attacker":2,"victim":1,"source":Vector3.LEFT,"amount":5.0})
	assert_signal_emitted_with_parameters(game,"damage_taken",[Vector3.LEFT,5.0])

func test_countdown_aborts_when_one_team_is_empty_even_with_two_players():
	var game := fixture()
	await wait_physics_frames(3)
	game.match_type = "TDM"
	game.add_robot(1,"One",0,true,"raptor")
	game.add_robot(2,"Two",0,true,"raptor")
	game.replicating = true
	game.phase = "Countdown"
	game._physics_process(0.02)
	assert_eq(game.phase,"Finished")
	assert_true(game.result.canceled)
	assert_false(game.result.reason.is_empty())

func test_server_captions_do_not_apply_its_own_listener_preferences():
	var game := fixture()
	await wait_physics_frames(3)
	game.replicating = true
	game.callouts.frequency = 2
	assert_true(game.callouts.publish("Energy acquired","Remote",1,false,Vector3(50,0,0)))
	assert_eq(game.presentation_events.size(),1)
	assert_true(game.callouts.captions.is_empty())
	game.authority = false
	assert_false(game.callouts.publish("Energy acquired","Remote",1,false,Vector3(50,0,0)),"The receiving client decides whether to suppress robot speech")

func test_reliable_shots_survive_newer_snapshots_without_duplicate_reports():
	var game := fixture()
	await wait_physics_frames(3)
	game.authority = false
	game.replicating = true
	var robot: ArenaRobot = game.add_robot(1,"Remote",0,true,"raptor")
	var state := robot.network_state()
	robot.restore_network(state)
	state.shots = 3
	robot.restore_network(state)
	assert_eq(robot.network_presented_shot,0,"Snapshots do not consume pending reliable presentation events")
	var transport := OnlineTransport.new()
	transport.game = game
	transport.closed = true
	add_child_autoqfree(transport)
	var event := {"kind":"shot","robot":1,"number":1,"weapon":"pistol","secondary":false,"barrel":0,"trace":Vector3.ZERO}
	transport.apply_presentation(event)
	var started: int = game.audio.metrics.started
	game.audio.clock += 0.13
	transport.apply_presentation(event)
	assert_eq(game.audio.metrics.started,started,"Duplicate accepted shots do not replay audio")
	event.number = 3
	transport.apply_presentation(event)
	assert_eq(robot.network_presented_shot,3)
	assert_eq(game.audio.metrics.started,started+1,"A delayed newer accepted shot still plays")

func test_spawn_geometry_rejects_solid_cover_and_fall_boundary():
	var game := fixture()
	await wait_physics_frames(3)
	game.map.start_loadout()
	var spawn: Dictionary = game.map.spawns[0]
	game.map.assembly.seek(5.0,true)
	var blocker := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	blocker.add_child(shape)
	game.add_child(blocker)
	blocker.global_position = spawn.point+Vector3.UP
	await wait_physics_frames(3)
	assert_false(game.spawn_geometry_safe(spawn),"Solid geometry prevents this marker from being chosen")
	var invalid := spawn.duplicate()
	invalid.point.y = game.map.config.fall_boundary-1
	assert_false(game.spawn_geometry_safe(invalid))

func test_late_join_snapshot_restores_repair_carried_flag_death_and_event_phase():
	var server_game := fixture()
	await wait_physics_frames(3)
	server_game.match_type = "CTF"
	server_game.map.start_loadout()
	server_game.phase = "Active"
	server_game.countdown = ArenaMatch.OPENING_SECONDS
	var repairing: ArenaRobot = server_game.add_robot(1,"Repairing",0,true,"raptor")
	server_game.add_robot(2,"Joining",1,true,"raptor")
	var victim: ArenaRobot = server_game.add_robot(3,"Victim",1,true,"raptor")
	victim.protection = 0
	repairing.protection = 0
	victim.hit(200,repairing,"pistol")
	var station: Dictionary
	for item in server_game.map.fixtures:
		if item.kind == "repair_station": station = item; break
	station.occupant = repairing
	station.elapsed = 2.0
	station.repair_active = true
	repairing.repair = station
	repairing.carrying = 1
	server_game.flags[1].state = "carried"
	server_game.flags[1].carrier = 1
	Assets.play(server_game.flags[1].node,"flutter")
	server_game.map.event_warned = true
	server_game.set_physics_process(false)
	for robot in server_game.robots: robot.set_physics_process(false)
	var sender := OnlineTransport.new()
	sender.game = server_game
	sender.closed = true
	sender.peers[2] = {"ack":0}
	add_child_autoqfree(sender)
	server_game.combat.launch(repairing, "emp_gun")
	var launched: ArenaProjectile = server_game.get_children().filter(func(node): return node is ArenaProjectile)[0]
	launched.set_physics_process(false)
	var snapshot := sender.make_snapshot(2)
	assert_eq(snapshot.missiles[0].shooter, repairing.robot_id)
	var receiver_game := fixture()
	await wait_physics_frames(3)
	receiver_game.authority = false
	receiver_game.match_type = "CTF"
	var receiver := OnlineTransport.new()
	receiver.game = receiver_game
	receiver.closed = true
	receiver.local_id = 2
	add_child_autoqfree(receiver)
	receiver.apply_snapshot(snapshot,true)
	var restored: ArenaRobot = receiver_game.robot_by_id(1)
	var replicated: ArenaProjectile = receiver.projectiles[snapshot.missiles[0].id]
	assert_same(replicated.shooter, restored, "Projectile ownership survives replication")
	assert_almost_eq(replicated.visual.global_position, launched.global_position, Vector3.ONE * 0.001, "Another player's projectile retains its world origin")
	assert_not_null(restored.repair)
	assert_almost_eq(restored.repair.elapsed,2.0,0.001)
	assert_eq(restored.repair.occupant.robot_id,1)
	assert_eq(restored.carrying,1)
	assert_eq(receiver_game.flags[1].carrier,1)
	assert_eq(receiver_game.flags[1].state,"carried")
	assert_true(String((Assets.find(receiver_game.flags[1].node,"AnimationPlayer") as AnimationPlayer).current_animation).ends_with("flutter"))
	assert_false(receiver_game.robot_by_id(3).alive)
	assert_eq(emissive_surfaces(receiver_game.robot_by_id(3).body),0)
	assert_eq(receiver.remote_corpses.size(),1)
	assert_true(receiver_game.map.event_warned)
	assert_false(receiver_game.map.event_done)

	var newest := snapshot.duplicate(true)
	newest.number = 10
	newest.elapsed = 12.0
	var stale := snapshot.duplicate(true)
	stale.number = 9
	receiver.queue_snapshot(newest)
	receiver.queue_snapshot(stale)
	receiver.round_ready = true
	receiver.pending_presentation.append({"kind":"damage","attacker":2,"victim":1,"source":Vector3.ZERO,"amount":2.0})
	receiver.flush_client_state()
	assert_eq(receiver.last_snapshot,10,"One receive burst applies only its newest complete state")
	assert_eq(receiver_game.elapsed,12.0)
	assert_true(receiver.pending_snapshot.is_empty())
	assert_true(receiver.pending_presentation.is_empty())
	assert_almost_eq(receiver_game.hit_marker,0.24,0.001,"Reliable feedback survives snapshot coalescing")
